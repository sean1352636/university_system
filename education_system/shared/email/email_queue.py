"""Simple threaded email queue for asynchronous sending.

Provides an ``EmailQueue`` that accepts email tasks and processes them in a
background daemon thread.  Failed sends are retried with exponential back-off
(up to *max_retries* times).

Usage::

    from education_system.shared.email.email_service import EmailService
    from education_system.shared.email.email_queue import EmailQueue

    svc = EmailService()
    eq = EmailQueue(svc)
    eq.start()

    eq.enqueue("user@example.com", "Subject", "Body text")

    # When shutting down:
    eq.stop()
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class _EmailTask:
    """Internal representation of a queued email."""

    to: str
    subject: str
    body: str
    html_body: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: Optional[List[str]] = None
    reply_to: Optional[str] = None
    attempt: int = 0
    max_retries: int = 3


class EmailQueue:
    """Background email sending queue with retry logic.

    Parameters:
        email_service: An ``EmailService`` instance used to send emails.
        max_retries: Number of times to retry a failed send (default 3).
        retry_base_delay: Base delay in seconds for exponential back-off
            (default 5).  Actual delay is ``base * 2 ** attempt``.
        poll_interval: Seconds the worker waits for a new task before
            looping (default 2).
    """

    def __init__(
        self,
        email_service,
        max_retries: int = 3,
        retry_base_delay: float = 5.0,
        poll_interval: float = 2.0,
    ):
        self._service = email_service
        self._queue: queue.Queue[_EmailTask] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.poll_interval = poll_interval

        # Simple counters (thread-safe via GIL for reads, lock for writes)
        self._sent = 0
        self._failed = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """Add an email to the send queue.

        If the worker is not running the task is still queued and will be
        processed once ``start()`` is called.

        Returns True (always succeeds for queuing).
        """
        task = _EmailTask(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            reply_to=reply_to,
            max_retries=self.max_retries,
        )
        self._queue.put(task)
        logger.debug("Email queued for %s: %s", to, subject[:60])
        return True

    def start(self) -> None:
        """Start the background worker thread (idempotent)."""
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._stop_event.clear()
            self._worker = threading.Thread(
                target=self._process_queue,
                name="shared-email-queue-worker",
                daemon=True,
            )
            self._worker.start()
            logger.info("Email queue worker started")

    def stop(self, timeout: float = 10.0) -> None:
        """Signal the worker to stop and wait for it to finish.

        Any remaining items in the queue will **not** be processed after
        the current item completes.
        """
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                return
            self._stop_event.set()
            self._worker.join(timeout=timeout)
            if self._worker.is_alive():
                logger.warning("Email queue worker did not stop within %.1fs", timeout)
            else:
                logger.info("Email queue worker stopped")
            self._worker = None

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Block until all queued tasks have been processed.

        Returns True if the queue was fully drained, False on timeout.
        """
        try:
            self._queue.join()
            return True
        except Exception:
            return False

    @property
    def is_running(self) -> bool:
        """True if the worker thread is alive."""
        return self._worker is not None and self._worker.is_alive()

    @property
    def pending(self) -> int:
        """Approximate number of tasks still in the queue."""
        return self._queue.qsize()

    @property
    def stats(self) -> Dict[str, int]:
        """Return simple send/fail counters."""
        return {"sent": self._sent, "failed": self._failed, "pending": self.pending}

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _process_queue(self) -> None:
        """Worker loop: pull tasks and send them."""
        logger.debug("Email queue worker loop entered")

        while not self._stop_event.is_set():
            try:
                task = self._queue.get(timeout=self.poll_interval)
            except queue.Empty:
                continue

            self._handle_task(task)
            self._queue.task_done()

        logger.debug("Email queue worker loop exiting")

    def _handle_task(self, task: _EmailTask) -> None:
        """Attempt to send a single task, retrying on failure."""
        while task.attempt <= task.max_retries:
            result = self._service.send_email(
                to=task.to,
                subject=task.subject,
                body=task.body,
                html_body=task.html_body,
                cc=task.cc,
                bcc=task.bcc,
                attachments=task.attachments,
                reply_to=task.reply_to,
            )

            if result.get("success"):
                self._sent += 1
                logger.info(
                    "Queued email sent to %s (attempt %d)",
                    task.to,
                    task.attempt + 1,
                )
                return

            task.attempt += 1
            error = result.get("error", "Unknown")

            if task.attempt > task.max_retries:
                break

            delay = self.retry_base_delay * (2 ** (task.attempt - 1))
            logger.warning(
                "Email to %s failed (attempt %d/%d): %s  -- retrying in %.1fs",
                task.to,
                task.attempt,
                task.max_retries + 1,
                error,
                delay,
            )

            # Sleep in small increments so we can respond to stop_event
            waited = 0.0
            while waited < delay and not self._stop_event.is_set():
                time.sleep(min(0.5, delay - waited))
                waited += 0.5

            if self._stop_event.is_set():
                logger.info("Stop requested during retry delay; abandoning email to %s", task.to)
                self._failed += 1
                return

        # Exhausted retries
        self._failed += 1
        logger.error(
            "Email to %s permanently failed after %d attempts: %s",
            task.to,
            task.attempt,
            result.get("error", "Unknown"),
        )

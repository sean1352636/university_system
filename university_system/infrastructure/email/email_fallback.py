"""
Graceful Email Service Degradation for the University System.

Provides fallback mechanisms when the primary email service is unavailable,
including retry queues, circuit breakers, and degradation strategies.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from university_system.infrastructure.exceptions import EmailError

logger = logging.getLogger(__name__)


class EmailServiceUnavailable(EmailError):
    """Exception raised when email service is unavailable."""

    def __init__(
        self,
        message: str = "Email service unavailable",
        retry_at: Optional[datetime] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if retry_at:
            details['retry_at'] = retry_at.isoformat()
        kwargs['details'] = details
        kwargs.pop('code', None)
        super().__init__(message, code="EMAIL_SERVICE_UNAVAILABLE", **kwargs)


class SendStatus(Enum):
    """Status of an email send operation."""
    SENT = 'sent'
    QUEUED = 'queued'
    FAILED = 'failed'
    PENDING_RETRY = 'pending_retry'


@dataclass
class Email:
    """Email message data."""
    recipient: str
    subject: str
    body: str
    cc: Optional[str] = None
    bcc: Optional[str] = None
    attachments: Optional[List[str]] = None
    created_at: datetime = field(default_factory=datetime.now)
    attempt_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'recipient': self.recipient,
            'subject': self.subject,
            'body': self.body,
            'cc': self.cc,
            'bcc': self.bcc,
            'attachments': self.attachments,
            'created_at': self.created_at.isoformat(),
            'attempt_count': self.attempt_count,
            'last_error': self.last_error,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Email':
        data = data.copy()
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


@dataclass
class SendResult:
    """Result of an email send operation."""
    status: SendStatus
    message_id: Optional[str] = None
    retry_at: Optional[datetime] = None
    error: Optional[str] = None
    queued_position: Optional[int] = None

    @property
    def success(self) -> bool:
        return self.status == SendStatus.SENT


class CircuitBreaker:
    """
    Circuit breaker for email service availability.

    States:
        - CLOSED: Service is working, requests go through
        - OPEN: Service is down, requests are rejected/queued
        - HALF_OPEN: Testing if service recovered
    """

    class State(Enum):
        CLOSED = 'closed'
        OPEN = 'open'
        HALF_OPEN = 'half_open'

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds to wait before half-open
            half_open_max_calls: Test calls allowed in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.State.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()

        logger.info(
            f"CircuitBreaker initialized: threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )

    @property
    def state(self) -> State:
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def is_available(self) -> bool:
        return self.state != self.State.OPEN

    def _check_state_transition(self) -> None:
        """Check and perform state transitions."""
        if self._state == self.State.OPEN:
            if self._last_failure_time:
                elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state = self.State.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker: OPEN -> HALF_OPEN")

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == self.State.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = self.State.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker: HALF_OPEN -> CLOSED (recovered)")
            elif self._state == self.State.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == self.State.HALF_OPEN:
                self._state = self.State.OPEN
                logger.warning("Circuit breaker: HALF_OPEN -> OPEN (still failing)")
            elif self._state == self.State.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = self.State.OPEN
                    logger.warning(
                        f"Circuit breaker: CLOSED -> OPEN "
                        f"(failures: {self._failure_count})"
                    )

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self._lock:
            self._state = self.State.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
            logger.info("Circuit breaker reset")


class FallbackQueue:
    """
    Persistent queue for emails that couldn't be sent.

    Stores emails in SQLite for durability across restarts.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        max_retries: int = 5,
        retry_delays: Optional[List[int]] = None
    ):
        """
        Initialize fallback queue.

        Args:
            db_path: Path to queue database
            max_retries: Maximum retry attempts
            retry_delays: Delay between retries in seconds (exponential backoff)
        """
        if db_path is None:
            from university_system.modules.shared.constants import paths
            db_path = str(Path(paths.DATA_DIR) / 'email_queue.db')

        self.db_path = db_path
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [60, 300, 900, 3600, 7200]  # 1m, 5m, 15m, 1h, 2h

        self._lock = threading.RLock()
        self._init_db()

        logger.info(f"FallbackQueue initialized: db_path={db_path}")

    def _init_db(self) -> None:
        """Initialize queue database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS email_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_data TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    attempt_count INTEGER DEFAULT 0,
                    next_retry_at TEXT,
                    last_error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_queue_status_retry
                ON email_queue(status, next_retry_at)
            ''')
            conn.commit()

    def add(self, email: Email) -> int:
        """
        Add email to queue.

        Args:
            email: Email to queue

        Returns:
            Queue position
        """
        with self._lock:
            retry_delay = self._get_retry_delay(email.attempt_count)
            next_retry = datetime.now() + timedelta(seconds=retry_delay)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    INSERT INTO email_queue (email_data, next_retry_at, attempt_count, last_error)
                    VALUES (?, ?, ?, ?)
                ''', (
                    json.dumps(email.to_dict()),
                    next_retry.isoformat(),
                    email.attempt_count,
                    email.last_error,
                ))
                conn.commit()

                # Get queue position
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM email_queue WHERE status = 'pending'"
                )
                position = cursor.fetchone()[0]

                logger.info(f"Email queued for retry: {email.recipient} (position: {position})")
                return position

    def _get_retry_delay(self, attempt: int) -> int:
        """Get retry delay for given attempt number."""
        if attempt >= len(self.retry_delays):
            return self.retry_delays[-1]
        return self.retry_delays[attempt]

    def get_pending(self, limit: int = 100) -> List[tuple[int, Email]]:
        """
        Get pending emails ready for retry.

        Args:
            limit: Maximum emails to return

        Returns:
            List of (queue_id, Email) tuples
        """
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, email_data, attempt_count, last_error
                FROM email_queue
                WHERE status = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= ?)
                ORDER BY next_retry_at ASC
                LIMIT ?
            ''', (now, limit))

            results = []
            for row in cursor.fetchall():
                email_data = json.loads(row[1])
                email_data['attempt_count'] = row[2]
                email_data['last_error'] = row[3]
                results.append((row[0], Email.from_dict(email_data)))

            return results

    def mark_sent(self, queue_id: int) -> None:
        """Mark email as successfully sent."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE email_queue
                SET status = 'sent', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (queue_id,))
            conn.commit()

    def mark_failed(self, queue_id: int, error: str) -> bool:
        """
        Mark email as failed, schedule retry or permanent failure.

        Args:
            queue_id: Queue entry ID
            error: Error message

        Returns:
            True if will retry, False if permanently failed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT attempt_count FROM email_queue WHERE id = ?",
                (queue_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            attempt_count = row[0] + 1

            if attempt_count >= self.max_retries:
                conn.execute('''
                    UPDATE email_queue
                    SET status = 'failed', last_error = ?,
                        attempt_count = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (error, attempt_count, queue_id))
                conn.commit()
                return False
            else:
                retry_delay = self._get_retry_delay(attempt_count)
                next_retry = datetime.now() + timedelta(seconds=retry_delay)
                conn.execute('''
                    UPDATE email_queue
                    SET last_error = ?, attempt_count = ?,
                        next_retry_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (error, attempt_count, next_retry.isoformat(), queue_id))
                conn.commit()
                return True

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            for status in ['pending', 'sent', 'failed']:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM email_queue WHERE status = ?",
                    (status,)
                )
                stats[status] = cursor.fetchone()[0]
            stats['total'] = sum(stats.values())
            return stats

    def clear_old_entries(self, days: int = 30) -> int:
        """
        Clear old sent/failed entries.

        Args:
            days: Remove entries older than this many days

        Returns:
            Number of entries removed
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                DELETE FROM email_queue
                WHERE status IN ('sent', 'failed') AND updated_at < ?
            ''', (cutoff,))
            conn.commit()
            return cursor.rowcount


class EmailServiceWithFallback:
    """
    Email service wrapper with graceful degradation.

    Provides circuit breaker protection and fallback queue for reliability.

    Example:
        >>> primary_service = EmailService()
        >>> service = EmailServiceWithFallback(primary_service.send)
        >>>
        >>> result = service.send(Email(
        ...     recipient="user@example.com",
        ...     subject="Test",
        ...     body="Hello"
        ... ))
        >>>
        >>> if result.status == SendStatus.QUEUED:
        ...     print(f"Email queued, retry at: {result.retry_at}")
    """

    def __init__(
        self,
        primary_send_func: Callable[[Email], bool],
        queue_db_path: Optional[str] = None,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: int = 60,
        max_retries: int = 5,
    ):
        """
        Initialize service with fallback.

        Args:
            primary_send_func: Primary email send function
            queue_db_path: Path for fallback queue database
            circuit_failure_threshold: Failures before circuit opens
            circuit_recovery_timeout: Seconds before retry after circuit opens
            max_retries: Maximum retry attempts for queued emails
        """
        self.primary_send = primary_send_func
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=circuit_recovery_timeout,
        )
        self.fallback_queue = FallbackQueue(
            db_path=queue_db_path,
            max_retries=max_retries,
        )

        self._retry_thread: Optional[threading.Thread] = None
        self._stop_retry = threading.Event()

        logger.info("EmailServiceWithFallback initialized")

    def send(self, email: Email) -> SendResult:
        """
        Send email with fallback handling.

        Args:
            email: Email to send

        Returns:
            SendResult with status and details
        """
        if not self.circuit_breaker.is_available:
            # Circuit is open, queue directly
            retry_delay = self.fallback_queue._get_retry_delay(email.attempt_count)
            retry_at = datetime.now() + timedelta(seconds=retry_delay)
            position = self.fallback_queue.add(email)

            logger.warning(
                f"Email queued (circuit open): {email.recipient}, retry at {retry_at}"
            )

            return SendResult(
                status=SendStatus.QUEUED,
                retry_at=retry_at,
                queued_position=position,
            )

        try:
            success = self.primary_send(email)
            if success:
                self.circuit_breaker.record_success()
                return SendResult(status=SendStatus.SENT)
            else:
                raise EmailServiceUnavailable("Send returned False")

        except Exception as e:
            self.circuit_breaker.record_failure()
            email.last_error = str(e)
            email.attempt_count += 1

            retry_delay = self.fallback_queue._get_retry_delay(email.attempt_count)
            retry_at = datetime.now() + timedelta(seconds=retry_delay)
            position = self.fallback_queue.add(email)

            logger.warning(
                f"Email queued for retry: {email.recipient}, error: {e}"
            )

            return SendResult(
                status=SendStatus.QUEUED,
                retry_at=retry_at,
                error=str(e),
                queued_position=position,
            )

    def process_queue(self, batch_size: int = 10) -> Dict[str, int]:
        """
        Process pending emails in queue.

        Args:
            batch_size: Number of emails to process

        Returns:
            Dictionary with sent/failed/skipped counts
        """
        results = {'sent': 0, 'failed': 0, 'skipped': 0}

        if not self.circuit_breaker.is_available:
            logger.info("Queue processing skipped: circuit breaker open")
            return results

        pending = self.fallback_queue.get_pending(limit=batch_size)

        for queue_id, email in pending:
            try:
                success = self.primary_send(email)
                if success:
                    self.fallback_queue.mark_sent(queue_id)
                    self.circuit_breaker.record_success()
                    results['sent'] += 1
                else:
                    self.fallback_queue.mark_failed(queue_id, "Send returned False")
                    self.circuit_breaker.record_failure()
                    results['failed'] += 1

            except Exception as e:
                will_retry = self.fallback_queue.mark_failed(queue_id, str(e))
                self.circuit_breaker.record_failure()

                if will_retry:
                    results['skipped'] += 1
                else:
                    results['failed'] += 1

                # Stop processing if circuit opens
                if not self.circuit_breaker.is_available:
                    break

        logger.info(f"Queue processed: {results}")
        return results

    def start_retry_worker(self, interval: int = 60) -> None:
        """
        Start background worker to process queue.

        Args:
            interval: Seconds between processing runs
        """
        if self._retry_thread and self._retry_thread.is_alive():
            return

        self._stop_retry.clear()

        def worker():
            while not self._stop_retry.wait(timeout=interval):
                try:
                    self.process_queue()
                except Exception as e:
                    logger.error(f"Retry worker error: {e}")

        self._retry_thread = threading.Thread(
            target=worker,
            daemon=True,
            name="EmailRetryWorker"
        )
        self._retry_thread.start()
        logger.info(f"Retry worker started (interval: {interval}s)")

    def stop_retry_worker(self) -> None:
        """Stop background retry worker."""
        self._stop_retry.set()
        if self._retry_thread:
            self._retry_thread.join(timeout=5)
        logger.info("Retry worker stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            'circuit_breaker': {
                'state': self.circuit_breaker.state.value,
                'is_available': self.circuit_breaker.is_available,
            },
            'queue': self.fallback_queue.get_stats(),
        }


def calculate_retry_time(attempt: int = 0) -> datetime:
    """
    Calculate next retry time using exponential backoff.

    Args:
        attempt: Current attempt number (0-based)

    Returns:
        DateTime for next retry
    """
    delays = [60, 300, 900, 3600, 7200]  # 1m, 5m, 15m, 1h, 2h
    delay = delays[min(attempt, len(delays) - 1)]
    return datetime.now() + timedelta(seconds=delay)


__all__ = [
    'EmailServiceWithFallback',
    'EmailServiceUnavailable',
    'Email',
    'SendResult',
    'SendStatus',
    'CircuitBreaker',
    'FallbackQueue',
    'calculate_retry_time',
]

"""The real-time processor: takes AI-writing readings of queued work.

Work waits in ``processing_queue`` (so it survives a restart and several
workers never take the same item):

* **text** items — queued by batch or LMS imports, or by staff
  (:func:`enqueue`), as ``{"text", "student_id", "module_code",
  "assignment_id", "title"}`` with ``queued_by`` the member of staff;
* **submission** items — assignment submissions with no reading yet, found
  by :func:`sweep_missing` (for example ones made while AI readings were
  switched off for a while, or before the automatic reading existed).

Each worker thread has its own connection, claims the next item
atomically, takes the reading through ``application/integrity/ai`` (staff
items as that member of staff, with their module permissions; submissions
through the automatic path, which respects each module's AI switch) and
marks the item done or failed with the error. :func:`status` gives the
queue and throughput for the monitor screen.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

from education_system.systems.university.shared.ai.ai_detector.core.constants import logger

WAITING = ("pending", "queued")
MAX_ATTEMPTS = 3
SWEEP_EVERY = 300          # seconds between sweeps for submissions without a reading


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure(conn) -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        ai_detector_schema,
    )
    ai_detector_schema.apply_to_connection(conn)


def enqueue(conn, data: Dict, *, priority=1, queued_by=None, kind="text") -> str:
    """Queue one piece of work (no commit)."""
    _ensure(conn)
    if kind == "text":
        missing = [k for k in ("text", "student_id", "module_code") if not data.get(k)]
        if missing:
            raise ValueError(f"Queued text needs {', '.join(missing)}")
        if not queued_by:
            raise ValueError("Queued text needs the member of staff it is checked for")
    elif kind == "submission":
        if not data.get("submission_id"):
            raise ValueError("A queued submission needs its submission id")
    else:
        raise ValueError("kind must be text or submission")
    task_id = uuid.uuid4().hex
    conn.execute("INSERT INTO processing_queue (id, submission_data, priority, status, "
                 "created_at, kind, queued_by, attempts) VALUES (?, ?, ?, 'queued', ?, ?, ?, 0)",
                 (task_id, json.dumps(data, separators=(",", ":")), int(priority), _now(), kind,
                  queued_by))
    return task_id


def sweep_missing(conn, limit=50) -> int:
    """Queue final submissions to modules with AI readings on that have no
    reading and are not already queued (no commit)."""
    _ensure(conn)
    from education_system.systems.university.application.integrity import access
    rows = conn.execute(
        "SELECT s.id, a.module_code FROM assignment_submissions s JOIN assignments a ON "
        "a.id = s.assignment_id WHERE COALESCE(s.is_final_submission, 1) = 1 AND NOT EXISTS "
        "(SELECT 1 FROM ai_detector_submissions d WHERE d.assignment_submission_id = s.id) "
        "AND NOT EXISTS (SELECT 1 FROM processing_queue q WHERE q.kind = 'submission' AND "
        "q.submission_data = json_object('submission_id', s.id)) ORDER BY s.id DESC LIMIT ?",
        (int(limit),)).fetchall()
    queued = 0
    for submission_id, module in rows:
        if access.ai_checks_enabled(conn, module):
            conn.execute("INSERT INTO processing_queue (id, submission_data, priority, status, "
                         "created_at, kind, queued_by, attempts) VALUES (?, json_object("
                         "'submission_id', ?), 0, 'queued', ?, 'submission', 'automatic', 0)",
                         (uuid.uuid4().hex, submission_id, _now()))
            queued += 1
    return queued


def _claim(conn) -> dict | None:
    row = conn.execute(
        "UPDATE processing_queue SET status = 'processing', started_at = ?, attempts = "
        "COALESCE(attempts, 0) + 1 WHERE rowid = (SELECT rowid FROM processing_queue WHERE status "
        "IN ('pending', 'queued') ORDER BY priority DESC, rowid LIMIT 1) RETURNING id, "
        "submission_data, kind, queued_by, attempts", (_now(),)).fetchone()
    conn.commit()
    if not row:
        return None
    return {"id": row[0], "data": json.loads(row[1] or "{}"), "kind": row[2] or "text",
            "queued_by": row[3], "attempts": row[4]}


def _process(conn, item) -> int | None:
    from education_system.systems.university.application.integrity import access
    from education_system.systems.university.application.integrity import ai as integrity_ai
    data = item["data"]
    if item["kind"] == "submission":
        from education_system.systems.university.infrastructure.integrity import text_extract
        text, file_type = text_extract.submission_text(conn, data["submission_id"])
        return integrity_ai.check_submission(conn, data["submission_id"], text, file_type)
    who = access.person(conn, item["queued_by"])
    return integrity_ai.run_check(conn, who, text=data["text"], module_code=data["module_code"],
                                  student_id=data.get("student_id"),
                                  assignment_id=data.get("assignment_id"),
                                  submission_id=data.get("submission_id"),
                                  title=data.get("title") or "", file_type=data.get(
                                      "file_type") or "txt")


def process_one(conn) -> dict | None:
    """Claim and process the next item; ``None`` when the queue is empty.
    Commits its own work (the claim, then the reading)."""
    _ensure(conn)
    item = _claim(conn)
    if item is None:
        return None
    try:
        result_id = _process(conn, item)
        conn.execute("UPDATE processing_queue SET status = 'done', processed_at = ?, "
                     "ai_result_id = ?, error = NULL WHERE id = ?",
                     (_now(), result_id, item["id"]))
        conn.commit()
        return {"id": item["id"], "status": "done", "ai_result_id": result_id}
    except Exception as exc:
        conn.rollback()
        status = "failed" if item["attempts"] >= MAX_ATTEMPTS or isinstance(
            exc, (ValueError, PermissionError)) else "queued"
        conn.execute("UPDATE processing_queue SET status = ?, error = ?, processed_at = ? "
                     "WHERE id = ?", (status, str(exc)[:500], _now(), item["id"]))
        conn.commit()
        return {"id": item["id"], "status": status, "error": str(exc)}


def status(conn, now=None) -> Dict[str, Any]:
    """Queue sizes and throughput over the last hour."""
    _ensure(conn)
    now = now or datetime.now()
    hour_ago = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    counts = {s: n for s, n in conn.execute(
        "SELECT status, COUNT(*) FROM processing_queue GROUP BY status")}
    done = conn.execute("SELECT COUNT(*), AVG((julianday(processed_at) - julianday(started_at)) "
                        "* 86400) FROM processing_queue WHERE status = 'done' AND processed_at "
                        ">= ?", (hour_ago,)).fetchone()
    failed = conn.execute("SELECT id, error, processed_at FROM processing_queue WHERE status = "
                          "'failed' ORDER BY rowid DESC LIMIT 10").fetchall()
    return {"waiting": sum(counts.get(s, 0) for s in WAITING),
            "processing": counts.get("processing", 0), "done": counts.get("done", 0),
            "failed": counts.get("failed", 0), "done_last_hour": done[0] or 0,
            "seconds_per_item": round(done[1], 3) if done[1] is not None else None,
            "recent_failures": [{"id": r[0], "error": r[1], "at": r[2]} for r in failed]}


def task(conn, task_id) -> Dict[str, Any]:
    _ensure(conn)
    row = conn.execute("SELECT id, status, created_at, started_at, processed_at, error, "
                       "ai_result_id, priority, rowid FROM processing_queue WHERE id = ?",
                       (str(task_id),)).fetchone()
    if not row:
        return {"status": "not_found"}
    position = None
    if row[1] in WAITING:
        position = conn.execute("SELECT COUNT(*) FROM processing_queue WHERE status IN "
                                "('pending', 'queued') AND (priority > ? OR (priority = ? AND "
                                "rowid < ?))", (row[7], row[7], row[8])).fetchone()[0]
    return {"id": row[0], "status": row[1], "queued_at": row[2], "started_at": row[3],
            "processed_at": row[4], "error": row[5], "ai_result_id": row[6],
            "position": position}


def requeue_stuck(conn, minutes=30) -> int:
    """Items left 'processing' by a worker that stopped mid-way go back."""
    cutoff = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("UPDATE processing_queue SET status = 'queued' WHERE status = "
                       "'processing' AND started_at < ?", (cutoff,))
    return cur.rowcount


class RealTimeProcessor:
    """Worker threads over ``processing_queue``, each on its own connection."""

    def __init__(self, detector_instance):
        self.detector = detector_instance
        self.workers: list = []
        self.is_running = False
        self._stop = threading.Event()
        self.processed = 0
        self.failed = 0
        self.started_at = None

    def _connect(self):
        from education_system.systems.university.infrastructure.database.db import get_connection
        return get_connection(self.detector.db_path, row_factory=False)

    def _actor(self) -> str:
        user = getattr(self.detector, "current_user", None) or {}
        return str(user.get("username") or "")

    @property
    def processing_queue(self) -> list:
        """Waiting items, highest priority first (for older screens)."""
        conn = self._connect()
        try:
            _ensure(conn)
            return [{"id": str(r[0]), "status": r[1], "priority": r[2], "queued_at": r[3],
                     "kind": r[4]} for r in conn.execute(
                "SELECT id, status, priority, created_at, kind FROM processing_queue WHERE "
                "status IN ('pending', 'queued', 'processing') ORDER BY priority DESC, rowid")]
        finally:
            conn.close()

    def start_real_time_processing(self, num_workers: int = 3):
        if self.is_running:
            return
        self._stop.clear()
        self.is_running = True
        self.started_at = _now()
        conn = self._connect()
        try:
            requeue_stuck(conn)
            conn.commit()
        finally:
            conn.close()
        for i in range(max(1, int(num_workers))):
            worker = threading.Thread(target=self._worker_process, args=(i,), daemon=True,
                                      name=f"ai-realtime-{i}")
            worker.start()
            self.workers.append(worker)
        logger.info(f"Started real-time processing with {num_workers} workers")

    def stop_real_time_processing(self):
        self.is_running = False
        self._stop.set()
        for worker in self.workers:
            worker.join(timeout=5)
        self.workers = []
        logger.info("Stopped real-time processing")

    def queue_submission(self, submission_data: Dict, priority: int = 1) -> str:
        """Queue text (``submission_data`` with text, student_id,
        module_code) or a submission (``{"submission_id"}``)."""
        kind = "submission" if set(submission_data) == {"submission_id"} else "text"
        data = dict(submission_data)
        if kind == "text":
            data.setdefault("module_code", data.pop("course_code", None))
        conn = self._connect()
        try:
            task_id = enqueue(conn, data, priority=priority, queued_by=self._actor() or None,
                              kind=kind)
            conn.commit()
            return task_id
        finally:
            conn.close()

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            return task(conn, task_id)
        finally:
            conn.close()

    def get_status(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            return {**status(conn), "running": self.is_running, "workers": len(self.workers),
                    "processed_this_session": self.processed,
                    "failed_this_session": self.failed, "started_at": self.started_at}
        finally:
            conn.close()

    def sweep_now(self, limit: int = 50) -> int:
        conn = self._connect()
        try:
            queued = sweep_missing(conn, limit)
            conn.commit()
            return queued
        finally:
            conn.close()

    def _worker_process(self, worker_id: int):
        logger.info(f"Worker {worker_id} started")
        conn = self._connect()
        last_sweep = 0.0
        try:
            while not self._stop.is_set():
                try:
                    if worker_id == 0 and time.time() - last_sweep > SWEEP_EVERY:
                        sweep_missing(conn)
                        conn.commit()
                        last_sweep = time.time()
                    done = process_one(conn)
                    if done is None:
                        self._stop.wait(1.0)
                    elif done["status"] == "done":
                        self.processed += 1
                    else:
                        self.failed += 1
                except Exception as exc:
                    conn.rollback()
                    logger.error(f"Worker {worker_id} error: {exc}")
                    self._stop.wait(2.0)
        finally:
            conn.close()
            logger.info(f"Worker {worker_id} stopped")

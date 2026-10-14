"""Mobile push notification queue — #21."""

from __future__ import annotations

import json
import sqlite3
from typing import Callable, Optional

from .log import logger


# ===========================================================================
# PushQueueService — #21
# ===========================================================================

class PushQueueService:
    """Mobile-push queue. Persists pending pushes; ``drain`` delivers them
    via an injected sender, or via shared.notifications.push.send."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def enqueue(self, user_id: str, title: str, body: str,
                payload: Optional[dict] = None) -> Optional[int]:
        try:
            cur = self.conn.execute(
                """INSERT INTO absence_push_queue(user_id, title, body, payload)
                   VALUES(?,?,?,?)""",
                (user_id, title, body, json.dumps(payload or {})))
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("push enqueue failed uid=%s", user_id)
            return None

    def drain(self,
              sender: Optional[Callable[[str, str, str, dict], bool]] = None
              ) -> int:
        if sender is None:
            try:
                from education_system.platform.features.notifications import (  # type: ignore
                    push as _push,
                )
                sender = _push.send
            except Exception:
                logger.debug("no push sender available", exc_info=True)
                return 0
        try:
            cur = self.conn.execute(
                """SELECT id, user_id, title, body, payload
                   FROM absence_push_queue
                   WHERE status='pending' ORDER BY id LIMIT 500""")
            rows = cur.fetchall()
        except sqlite3.Error:
            logger.exception("push drain query failed")
            return 0
        sent = 0
        for pid, uid, title, body, payload in rows:
            try:
                ok = sender(uid, title, body,
                            json.loads(payload or "{}"))
            except Exception:
                logger.exception("push send failed for id=%s", pid)
                ok = False
            try:
                if ok:
                    self.conn.execute(
                        "UPDATE absence_push_queue "
                        "SET status='sent', delivered_at=CURRENT_TIMESTAMP "
                        "WHERE id=?", (pid,))
                    sent += 1
                else:
                    self.conn.execute(
                        "UPDATE absence_push_queue SET status='failed' "
                        "WHERE id=?", (pid,))
            except sqlite3.Error:
                logger.exception("push status update failed id=%s", pid)
        try:
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("push drain commit failed")
        return sent


def queue_push(conn, user_id, title, body,
               payload: Optional[dict] = None) -> int:
    rid = PushQueueService(conn).enqueue(user_id, title, body, payload)
    return rid or 0


def drain_push_queue(conn,
                     sender: Optional[Callable[[str, str, str, dict], bool]
                                      ] = None) -> int:
    return PushQueueService(conn).drain(sender)


__all__ = [
    "PushQueueService",
    "queue_push",
    "drain_push_queue",
]

"""Replay-safe downstream consumers for student lifecycle work."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from education_system.systems.university.infrastructure.database.db import transaction
from education_system.systems.university.services.boundary_errors import EnrolmentBoundaryError

LifecycleHandler = Callable[[Mapping[str, Any]], None]
SUPPORTED_TARGETS = frozenset(
    {
        "finance",
        "module_enrolments",
        "visa_monitoring",
        "accommodation",
        "library",
        "student_account",
    }
)


def consume_action(
    action_id: int,
    target_system: str,
    handler: LifecycleHandler,
    *,
    handler_version: int = 1,
) -> bool:
    """Run a handler once; return ``False`` when the delivery is a replay."""
    if target_system not in SUPPORTED_TARGETS:
        raise EnrolmentBoundaryError(f"Unsupported lifecycle target {target_system!r}")
    with transaction() as conn:
        action = conn.execute(
            """SELECT * FROM student_lifecycle_actions
                WHERE action_id = ? AND target_system = ?""",
            (action_id, target_system),
        ).fetchone()
        if action is None:
            raise EnrolmentBoundaryError(
                f"Lifecycle action {action_id} does not belong to {target_system}"
            )
        receipt = conn.execute(
            """SELECT 1 FROM student_lifecycle_consumer_receipts
                WHERE action_id = ? AND target_system = ? AND handler_version = ?""",
            (action_id, target_system, handler_version),
        ).fetchone()
        if receipt:
            return False

        payload = json.loads(action["payload_json"])
        handler(payload)
        conn.execute(
            """INSERT INTO student_lifecycle_consumer_receipts
                 (action_id, target_system, handler_version, outcome)
               VALUES (?, ?, ?, 'completed')""",
            (action_id, target_system, handler_version),
        )
        conn.execute(
            """UPDATE student_lifecycle_actions
                  SET status = 'completed', attempts = attempts + 1,
                      completed_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE action_id = ?""",
            (action_id,),
        )
    return True


def consume_pending(
    handlers: Mapping[str, LifecycleHandler], *, handler_version: int = 1
) -> int:
    """Drain supported pending actions with explicitly supplied adapters."""
    unsupported = set(handlers) - SUPPORTED_TARGETS
    if unsupported:
        raise EnrolmentBoundaryError(
            f"Unsupported lifecycle targets: {', '.join(sorted(unsupported))}"
        )
    with transaction() as conn:
        pending = [
            (int(row["action_id"]), str(row["target_system"]))
            for row in conn.execute(
                "SELECT action_id, target_system FROM student_lifecycle_actions "
                "WHERE status IN ('pending', 'failed') ORDER BY action_id"
            ).fetchall()
        ]
    completed = 0
    for action_id, target in pending:
        handler = handlers.get(target)
        if handler and consume_action(
            action_id, target, handler, handler_version=handler_version
        ):
            completed += 1
    return completed


__all__ = ["SUPPORTED_TARGETS", "consume_action", "consume_pending"]

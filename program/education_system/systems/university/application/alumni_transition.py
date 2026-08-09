"""Idempotent completion-to-alumni orchestration."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from education_system.systems.university.infrastructure.database.db import transaction
from education_system.systems.university.infrastructure.events import transactional_publisher

STEPS = (
    "alumni_profile", "access_change", "account_settlement",
    "consent_capture", "graduate_outcomes",
)


def transition_to_alumni(
    student_id: str, adapters: Mapping[str, Callable[[str], Mapping[str, Any] | None]]
) -> int:
    missing = set(STEPS) - set(adapters)
    if missing:
        raise ValueError(f"Missing alumni transition adapters: {', '.join(sorted(missing))}")
    completed = 0
    for step in STEPS:
        with transaction() as conn:
            receipt = conn.execute(
                "SELECT 1 FROM alumni_transition_steps WHERE student_id=? AND step_name=?",
                (student_id, step),
            ).fetchone()
            if receipt:
                continue
            details = dict(adapters[step](student_id) or {})
            conn.execute(
                """INSERT INTO alumni_transition_steps
                     (student_id, step_name, status, details_json)
                   VALUES (?, ?, 'completed', ?)""",
                (student_id, step, json.dumps(details, sort_keys=True)),
            )
            if step == STEPS[-1]:
                conn.execute(
                    "UPDATE students SET status='Alumni' WHERE student_id=?", (student_id,)
                )
                transactional_publisher.publish(
                    conn, "student.alumni.transitioned",
                    {"student_id": student_id, "steps": list(STEPS)},
                    aggregate_id=student_id,
                    idempotency_key=f"alumni:{student_id}:transitioned",
                )
        completed += 1
    return completed


__all__ = ["STEPS", "transition_to_alumni"]

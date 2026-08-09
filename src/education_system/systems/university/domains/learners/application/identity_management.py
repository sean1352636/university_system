"""Dual-control student identity correction, merge and reversal."""

from __future__ import annotations

import json
import uuid
from typing import Any

from education_system.systems.university.infrastructure.database.db import transaction

IDENTITY_FIELDS = frozenset({"first_name", "middle_name", "last_name", "dob", "gender", "email_address"})


def correct_identity(
    student_id: str, changes: dict[str, Any], *, reason: str,
    requested_by: str, approved_by: str,
) -> str:
    if requested_by == approved_by or not changes or set(changes) - IDENTITY_FIELDS:
        raise ValueError("Identity correction requires valid fields and independent approval")
    change_id = str(uuid.uuid4())
    with transaction() as conn:
        student = conn.execute(
            "SELECT * FROM students WHERE student_id=?", (student_id,)
        ).fetchone()
        if student is None:
            raise ValueError(f"Student {student_id} does not exist")
        before = {field: student[field] for field in changes}
        assignments = ", ".join(f"{field}=?" for field in changes)
        conn.execute(
            f"UPDATE students SET {assignments} WHERE student_id=?",  # noqa: S608
            (*changes.values(), student_id),
        )
        conn.execute(
            """INSERT INTO student_identity_changes
                 (change_id, student_id, change_type, before_json, after_json,
                  reason, requested_by, approved_by)
               VALUES (?, ?, 'correction', ?, ?, ?, ?, ?)""",
            (
                change_id, student_id, json.dumps(before), json.dumps(changes),
                reason, requested_by, approved_by,
            ),
        )
    return change_id


def merge_students(
    survivor_id: str, merged_id: str, *, reason: str,
    requested_by: str, approved_by: str,
) -> str:
    if survivor_id == merged_id or requested_by == approved_by:
        raise ValueError("Merge requires distinct records and independent approval")
    merge_id = str(uuid.uuid4())
    with transaction() as conn:
        for student_id in (survivor_id, merged_id):
            if conn.execute(
                "SELECT 1 FROM students WHERE student_id=?", (student_id,)
            ).fetchone() is None:
                raise ValueError(f"Student {student_id} does not exist")
        conn.execute(
            """INSERT INTO student_identity_merges
                 (merge_id, survivor_id, merged_id, reason, requested_by, approved_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (merge_id, survivor_id, merged_id, reason, requested_by, approved_by),
        )
        conn.execute(
            "UPDATE students SET status='Merged' WHERE student_id=?", (merged_id,)
        )
    return merge_id


def reverse_merge(merge_id: str, *, reversed_by: str, reason: str) -> None:
    with transaction() as conn:
        merge = conn.execute(
            "SELECT * FROM student_identity_merges WHERE merge_id=?", (merge_id,)
        ).fetchone()
        if merge is None or merge["status"] != "active":
            raise ValueError("Active merge does not exist")
        if reversed_by in {merge["requested_by"], merge["approved_by"]}:
            raise ValueError("Merge reversal requires an independent operator")
        conn.execute(
            "UPDATE students SET status='Inactive' WHERE student_id=?",
            (merge["merged_id"],),
        )
        conn.execute(
            """UPDATE student_identity_merges SET status='reversed',
                   reversed_at=CURRENT_TIMESTAMP WHERE merge_id=?""",
            (merge_id,),
        )
        conn.execute(
            """INSERT INTO student_identity_changes
                 (change_id, student_id, change_type, before_json, after_json,
                  reason, requested_by, approved_by)
               VALUES (?, ?, 'merge_reversal', ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), merge["merged_id"], '{"status":"Merged"}',
                '{"status":"Inactive"}', reason, reversed_by, reversed_by,
            ),
        )


__all__ = ["correct_identity", "merge_students", "reverse_merge"]

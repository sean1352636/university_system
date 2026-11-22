"""Completion-to-alumni transition.

The steps (alumni profile, access change, account check, consent request,
Graduate Outcomes survey date) run inside the award conferral
(``university/application/alumni/records.on_conferral``). This module
catches up graduates conferred before that existed, and reports progress.
The student's status is left to the registration lifecycle (Completed);
"Alumni" is not a student status.
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.database.db import transaction

STEPS = ("alumni_profile", "access_change", "account_settlement", "consent_capture",
         "graduate_outcomes")


def transition_to_alumni(student_id: str, conferral_date: str | None = None) -> int:
    """Record any missing transition steps for a graduate who already has an
    alumni record. Returns how many steps were missing before."""
    from education_system.systems.university.application.alumni import records as alumni_records

    with transaction() as conn:
        if not conn.execute("SELECT 1 FROM alumni WHERE alumni_id = ?",
                            (student_id,)).fetchone():
            raise ValueError(f"{student_id} has no alumni record (confer the award first)")
        before = {r["step"] for r in alumni_records.transition_status(conn, student_id)
                  if r["done"]}
        day = conferral_date
        if not day:
            row = conn.execute("SELECT MAX(conferral_date) FROM graduation_conferrals WHERE "
                               "student_id = ? AND status = 'conferred'",
                               (student_id,)).fetchone() if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'graduation_conferrals'").fetchone() \
                else None
            day = (row[0] if row and row[0] else None) or alumni_records.aa.today()
        alumni_records.on_conferral(conn, student_id, day)
        return len(set(STEPS) - before)


__all__ = ["STEPS", "transition_to_alumni"]

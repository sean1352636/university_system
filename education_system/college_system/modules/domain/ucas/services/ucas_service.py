"""UCAS Applications service."""

import json

from education_system.college_system.core.exceptions import UCASError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class UCASService:
    """UCAS Applications service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_application(self, student_id: int, academic_year: str | None = None,
                           ucas_id: str | None = None, notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ucas_applications (student_id, academic_year, ucas_id, notes)
                   VALUES (?, ?, ?, ?)""",
                (student_id, academic_year, ucas_id, notes),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM ucas_applications WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to create application: {e}") from e
        finally:
            conn.close()

    def list_applications(self, academic_year: str | None = None,
                          status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT a.*, s.first_name, s.last_name, s.student_id as sid FROM ucas_applications a JOIN students s ON a.student_id = s.id WHERE 1=1"
            params: list = []
            if academic_year:
                sql += " AND a.academic_year = ?"
                params.append(academic_year)
            if status:
                sql += " AND a.application_status = ?"
                params.append(status)
            sql += " ORDER BY a.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_application(self, app_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM ucas_applications WHERE id = ?", (app_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_application(self, app_id: int, **updates) -> dict:
        set_parts: list[str] = []
        vals: list = []
        for col in ("application_status", "notes", "personal_statement_status",
                    "predicted_tariff", "reference_status", "ucas_id"):
            if col in updates and updates[col] is not None:
                set_parts.append(f"{col} = ?")
                vals.append(updates[col])
        if not set_parts:
            raise UCASError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(set_parts)
            vals.append(app_id)
            conn.execute(f"UPDATE ucas_applications SET {sets}, updated_at = datetime('now') WHERE id = ?", vals)
            conn.commit()
            return self.get_application(app_id)
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to update application: {e}") from e
        finally:
            conn.close()

    def submit_application(self, app_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE ucas_applications SET application_status = 'submitted', submitted_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                (app_id,),
            )
            conn.commit()
            return self.get_application(app_id)
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to submit application: {e}") from e
        finally:
            conn.close()

    def add_choice(self, application_id: int, university_name: str, course_title: str,
                   ucas_code: str | None = None, choice_number: int | None = None,
                   notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ucas_choices
                   (application_id, university_name, course_title, ucas_code, choice_number, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (application_id, university_name, course_title, ucas_code, choice_number, notes),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM ucas_choices WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to add choice: {e}") from e
        finally:
            conn.close()

    def list_choices(self, application_id: int) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM ucas_choices WHERE application_id = ? ORDER BY choice_number",
                (application_id,)).fetchall()]
        finally:
            conn.close()

    def update_choice(self, choice_id: int, **updates) -> dict:
        allowed = {"offer_type", "offer_conditions", "offer_status", "is_firm", "is_insurance", "reply_deadline", "notes"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [choice_id]
            conn.execute(f"UPDATE ucas_choices SET {sets} WHERE id = ?", vals)
            conn.commit()
            row = conn.execute("SELECT * FROM ucas_choices WHERE id = ?", (choice_id,)).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to update choice: {e}") from e
        finally:
            conn.close()

    def set_firm_insurance(self, application_id: int, firm_id: int, insurance_id: int | None = None) -> None:
        conn = self._conn()
        try:
            conn.execute("UPDATE ucas_choices SET is_firm = 0, is_insurance = 0 WHERE application_id = ?", (application_id,))
            conn.execute("UPDATE ucas_choices SET is_firm = 1 WHERE id = ?", (firm_id,))
            if insurance_id:
                conn.execute("UPDATE ucas_choices SET is_insurance = 1 WHERE id = ?", (insurance_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to set firm/insurance: {e}") from e
        finally:
            conn.close()

        # Cross-system: publish student.progression.offered targeted at the
        # university subsystem. Best-effort — the firm/insurance state is
        # already committed regardless of bus availability.
        try:
            self._publish_progression_offered(application_id, firm_id)
        except Exception:
            logger.warning(
                "Failed to publish student.progression.offered "
                "(application_id=%s, firm_id=%s)",
                application_id, firm_id, exc_info=True,
            )

    def _publish_progression_offered(self, application_id: int,
                                      firm_id: int) -> None:
        """Resolve the firm choice + the applicant's journey, then publish.

        Called only after ``set_firm_insurance`` has committed. Reads
        what we just wrote rather than trusting the caller's args, so
        tests and CLI callers are exercised the same way.
        """
        from education_system.shared.cross_system.journey_events import (
            journey_id_for_system_record,
        )
        from education_system.shared.integrations import cross_system_bus as bus

        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT c.university_name, c.course_title, c.ucas_code,
                          c.offer_conditions, c.reply_deadline,
                          a.id   AS application_id,
                          a.student_id AS student_pk,
                          s.student_id AS college_student_id
                     FROM ucas_choices c
                     JOIN ucas_applications a ON c.application_id = a.id
                     JOIN students s          ON a.student_id    = s.id
                    WHERE c.id = ?""",
                (firm_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return

        journey_id = journey_id_for_system_record(
            "college", pk=row["student_pk"],
            student_id=row["college_student_id"],
        )
        if not journey_id:
            # No journey yet (e.g. backfill not run, or DOB missing on
            # the student record). Skip silently — nothing to publish.
            logger.debug(
                "No journey_id for college student %s; "
                "skipping progression event.",
                row["college_student_id"],
            )
            return

        bus.publish_cross_system(
            bus.EVENT_STUDENT_PROGRESSION_OFFERED,
            source_system="college",
            source_module="college_system.ucas.set_firm_insurance",
            journey_id=journey_id,
            target_system="university",
            target_university=row["university_name"],
            course_title=row["course_title"],
            ucas_code=row["ucas_code"],
            application_id=row["application_id"],
            conditions=row["offer_conditions"],
            reply_deadline=row["reply_deadline"],
            college_student_id=row["college_student_id"],
        )

    def record_results(self, application_id: int, *,
                       grades: dict[str, str],
                       conditions_met: bool | None = None) -> dict:
        """Record results-day grades against a UCAS application and fire
        ``student.progression.accepted`` to the university subsystem.

        ``grades`` is a free-form dict mapping qualification (e.g.
        ``'A-Level Maths'`` or ``'BTEC Computing'``) to grade string
        (``'A*'``, ``'D*'``, ``'Pass'``...). Whatever the college
        records — the receiving uni doesn't reinterpret it, just
        stores it on the entry-qualifications field.

        ``conditions_met`` is the college's call on whether the firm
        offer's conditions were met. ``None`` means "not yet
        evaluated"; pass ``True`` / ``False`` once the assessment is
        in.

        The bus publish is best-effort — a missing journey or a bus
        outage doesn't roll back the local update.
        """
        if not isinstance(grades, dict) or not grades:
            raise UCASError("grades must be a non-empty dict.")

        grades_json = json.dumps(grades)
        cm = (None if conditions_met is None
              else (1 if conditions_met else 0))

        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE ucas_applications "
                "   SET final_grades_json = ?, conditions_met = ?, "
                "       results_recorded_at = datetime('now'), "
                "       updated_at = datetime('now') "
                " WHERE id = ?",
                (grades_json, cm, application_id),
            )
            if cur.rowcount == 0:
                raise UCASError(
                    f"UCAS application {application_id} not found."
                )
            conn.commit()
        except UCASError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to record results: {e}") from e
        finally:
            conn.close()

        try:
            self._publish_progression_accepted(application_id)
        except Exception:
            logger.warning(
                "Failed to publish student.progression.accepted "
                "(application_id=%s)", application_id, exc_info=True,
            )

        return self.get_application(application_id)

    def _publish_progression_accepted(self, application_id: int) -> None:
        """Read the firm choice + journey id and publish the event."""
        from education_system.shared.cross_system.journey_events import (
            journey_id_for_system_record,
        )
        from education_system.shared.integrations import cross_system_bus as bus

        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT a.id           AS application_id,
                          a.student_id   AS student_pk,
                          a.final_grades_json,
                          a.conditions_met,
                          s.student_id   AS college_student_id,
                          c.university_name, c.course_title, c.ucas_code
                     FROM ucas_applications a
                     JOIN students          s ON a.student_id    = s.id
                     LEFT JOIN ucas_choices c ON c.application_id = a.id
                                              AND c.is_firm = 1
                    WHERE a.id = ?""",
                (application_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return

        journey_id = journey_id_for_system_record(
            "college", pk=row["student_pk"],
            student_id=row["college_student_id"],
        )
        if not journey_id:
            logger.debug(
                "No journey_id for college student %s; "
                "skipping progression.accepted.",
                row["college_student_id"],
            )
            return

        try:
            grades = json.loads(row["final_grades_json"] or "{}")
        except (TypeError, ValueError):
            grades = {}
        conditions_met = (None if row["conditions_met"] is None
                           else bool(row["conditions_met"]))

        bus.publish_cross_system(
            bus.EVENT_STUDENT_PROGRESSION_ACCEPTED,
            source_system="college",
            source_module="college_system.ucas.record_results",
            journey_id=journey_id,
            target_system="university",
            target_university=row["university_name"],
            course_title=row["course_title"],
            ucas_code=row["ucas_code"],
            application_id=row["application_id"],
            college_student_id=row["college_student_id"],
            final_grades=grades,
            conditions_met=conditions_met,
        )

    def get_statistics(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) as c FROM ucas_applications").fetchone()["c"]
            submitted = conn.execute("SELECT COUNT(*) as c FROM ucas_applications WHERE application_status = 'submitted'").fetchone()["c"]
            offers = conn.execute("SELECT COUNT(DISTINCT application_id) as c FROM ucas_choices WHERE offer_status = 'offer'").fetchone()["c"]
            return {"total": total, "submitted": submitted, "with_offers": offers}
        finally:
            conn.close()


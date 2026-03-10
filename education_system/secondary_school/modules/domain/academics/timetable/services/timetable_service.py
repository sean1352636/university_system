"""Timetable management service."""

import logging
import random
from education_system.secondary_school.core.exceptions import TimetableError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
PERIODS = list(range(1, 7))  # 6 periods per day
TOTAL_SLOTS = len(DAYS) * len(PERIODS)  # 30 per week

# Periods per week for each core subject (code -> count)
KS3_CORE_ALLOCATION = {
    "MATH01": 5,    # Mathematics
    "ENG01": 4,     # English Language
    "ENG02": 3,     # English Literature
    "SCI01": 4,     # Science
    "PE01": 2,      # Physical Education
    "PSHE01": 1,    # PSHE & Citizenship
    "RE01": 1,      # Religious Education
    "ICT01": 2,     # ICT & Computing
}  # Total: 22 — leaves 8 for options

KS4_CORE_ALLOCATION = {
    "MATH02": 5,    # GCSE Mathematics
    "ENG03": 4,     # GCSE English Language
    "ENG04": 3,     # GCSE English Literature
    "SCI02": 5,     # GCSE Combined Science
    "PE02": 2,      # PE (non-exam)
}  # Total: 19 — leaves 11 for options


class TimetableService:
    """Service for managing the school timetable."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_slot(self, subject_id: int, day_of_week: str, period: int,
                 room: str | None = None, teacher: str | None = None,
                 year_group: str | None = None, form_group: str | None = None,
                 term: str = "Autumn", academic_year: str | None = None) -> dict:
        """Add a timetable slot."""
        if day_of_week not in DAYS:
            raise TimetableError(f"Invalid day: {day_of_week}")
        if period not in PERIODS:
            raise TimetableError(f"Invalid period: {period}")

        conn = self._conn()
        try:
            # Check for clash
            clash = conn.execute(
                """SELECT ts.*, s.title FROM timetable_slots ts
                   JOIN subjects s ON ts.subject_id = s.id
                   WHERE ts.day_of_week = ? AND ts.period = ?
                     AND ts.year_group = ? AND ts.form_group IS ?
                     AND ts.term = ?""",
                (day_of_week, period, year_group, form_group, term),
            ).fetchone()
            if clash:
                raise TimetableError(
                    f"Clash: {clash['title']} is already scheduled for "
                    f"{day_of_week} period {period}."
                )

            cursor = conn.execute(
                """INSERT INTO timetable_slots
                   (subject_id, day_of_week, period, room, teacher,
                    year_group, form_group, term, academic_year)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (subject_id, day_of_week, period, room, teacher,
                 year_group, form_group, term, academic_year),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM timetable_slots WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
        except TimetableError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise TimetableError(f"Failed to add slot: {e}") from e
        finally:
            conn.close()

    def get_timetable(self, year_group: str | None = None,
                      form_group: str | None = None,
                      teacher: str | None = None,
                      term: str | None = None) -> list[dict]:
        """Get timetable slots with optional filters."""
        sql = """SELECT ts.*, s.subject_code, s.title
                 FROM timetable_slots ts JOIN subjects s ON ts.subject_id = s.id
                 WHERE 1=1"""
        params: list = []

        if year_group:
            sql += " AND ts.year_group = ?"
            params.append(year_group)
        if form_group:
            sql += " AND ts.form_group = ?"
            params.append(form_group)
        if teacher:
            sql += " AND ts.teacher = ?"
            params.append(teacher)
        if term:
            sql += " AND ts.term = ?"
            params.append(term)

        sql += " ORDER BY CASE ts.day_of_week WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 END, ts.period"

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_slot(self, slot_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM timetable_slots WHERE id = ?", (slot_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def clear_timetable(self, year_group: str, term: str = "Autumn"):
        """Remove all timetable slots for a year group and term."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM timetable_slots WHERE year_group = ? AND term = ?",
                (year_group, term),
            )
            conn.commit()
            logger.info("Timetable cleared for Year %s (%s)", year_group, term)
        finally:
            conn.close()

    def generate_timetable(self, year_group: str, term: str = "Autumn",
                           academic_year: str | None = None) -> dict:
        """Auto-generate a full weekly timetable for a year group.

        Core subjects are allocated fixed periods per week.
        Remaining slots are filled by cycling through option subjects.
        Each subject uses the teacher and room from the subjects table.

        Returns a summary dict with counts.
        """
        from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
        from education_system.secondary_school.infrastructure.database.constants import KS3_YEARS

        subj_svc = SubjectService(self._db_path)
        ks = "KS3" if year_group in KS3_YEARS else "KS4"
        core_alloc = KS3_CORE_ALLOCATION if ks == "KS3" else KS4_CORE_ALLOCATION

        # Fetch all active subjects for this key stage
        all_subjects = subj_svc.list_subjects(status="active", key_stage=ks)
        subj_by_code = {s["subject_code"]: s for s in all_subjects}

        # Build the ordered list of (subject_dict, count) for core subjects
        core_slots: list[dict] = []
        for code, count in core_alloc.items():
            subj = subj_by_code.get(code)
            if subj:
                for _ in range(count):
                    core_slots.append(subj)

        # Option subjects: everything not in the core allocation
        option_subjects = [s for s in all_subjects if s["subject_code"] not in core_alloc]
        random.shuffle(option_subjects)

        # Fill remaining slots by cycling through options
        option_slots_needed = TOTAL_SLOTS - len(core_slots)
        option_slots: list[dict] = []
        if option_subjects:
            idx = 0
            for _ in range(option_slots_needed):
                option_slots.append(option_subjects[idx % len(option_subjects)])
                idx += 1

        # Combine and distribute across the week
        all_slots = core_slots + option_slots
        random.shuffle(all_slots)  # Spread subjects across the week

        # Clear existing timetable for this year group/term
        self.clear_timetable(year_group, term)

        conn = self._conn()
        created = 0
        try:
            slot_idx = 0
            for day in DAYS:
                for period in PERIODS:
                    if slot_idx >= len(all_slots):
                        break
                    subj = all_slots[slot_idx]
                    conn.execute(
                        """INSERT INTO timetable_slots
                           (subject_id, day_of_week, period, room, teacher,
                            year_group, term, academic_year)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (subj["id"], day, period,
                         subj.get("room"), subj.get("teacher"),
                         year_group, term, academic_year),
                    )
                    created += 1
                    slot_idx += 1

            conn.commit()
            logger.info("Timetable generated for Year %s (%s): %d slots",
                        year_group, term, created)
        except Exception as e:
            conn.rollback()
            raise TimetableError(f"Failed to generate timetable: {e}") from e
        finally:
            conn.close()

        # Build summary
        subject_counts: dict[str, int] = {}
        for s in all_slots[:created]:
            title = s["title"]
            subject_counts[title] = subject_counts.get(title, 0) + 1

        return {
            "year_group": year_group,
            "term": term,
            "total_slots": created,
            "core_slots": len(core_slots),
            "option_slots": created - len(core_slots),
            "subjects": subject_counts,
        }

    def generate_all_timetables(self, term: str = "Autumn",
                                academic_year: str | None = None) -> list[dict]:
        """Generate timetables for all year groups (7-11)."""
        from education_system.secondary_school.infrastructure.database.constants import YEAR_GROUPS
        results = []
        for yg in YEAR_GROUPS:
            result = self.generate_timetable(yg, term, academic_year)
            results.append(result)
        return results

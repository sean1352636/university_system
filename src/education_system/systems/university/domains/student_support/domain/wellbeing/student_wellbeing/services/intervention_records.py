"""Intervention support case records — the data behind the Interventions
window's Support Cases tab and its CLI.

Lifted out of the old Intervention Support Tk app, which kept its SQL
inside the window class, so the GUI and the CLI share one copy. Rows live
in the central ``student_records.db`` table ``intervention_records``,
one row per student.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

__all__ = [
    "FIELDS", "RISK_LEVELS", "STATUSES", "INTERVENTION_TYPES",
    "InterventionRecordsError", "InterventionRecordsService", "build_report",
]

FIELDS = ("student_id", "name", "program", "gpa", "email",
          "risk", "status", "intervention", "last_contact", "notes")
RISK_LEVELS = ("Low", "Medium", "High", "Critical")
STATUSES = ("Active", "Monitoring", "Resolved", "Referred")
INTERVENTION_TYPES = ("Academic Advising", "Tutoring", "Counseling",
                      "Financial Aid", "Mental Health Support",
                      "Disability Services", "Career Services",
                      "Peer Mentoring")


class InterventionRecordsError(Exception):
    """Raised for a missing, duplicate or unsaveable record."""


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class InterventionRecordsService:
    """CRUD over ``intervention_records``."""

    def __init__(self, db_path: Optional[str] = None, actor: str = "") -> None:
        self._db_path = db_path
        self.actor = actor or ""
        self.ensure_schema()

    def _conn(self):
        return get_connection(self._db_path)

    def ensure_schema(self) -> None:
        conn = self._conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intervention_records (
                    student_id   TEXT PRIMARY KEY,
                    name         TEXT,
                    program      TEXT,
                    gpa          TEXT,
                    email        TEXT,
                    risk         TEXT,
                    status       TEXT,
                    intervention TEXT,
                    last_contact TEXT,
                    notes        TEXT,
                    updated_at   TEXT,
                    updated_by   TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def load_all(self) -> list[dict]:
        """Every record. (The old app seeded five made-up sample cases on a
        fresh install; removed 2026-10-19 — they weren't real students, so
        they could never link to Early Warning.)"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT " + ", ".join(FIELDS) + " FROM intervention_records "
                "ORDER BY student_id"
            ).fetchall()
        finally:
            conn.close()

        return [dict(zip(FIELDS, r)) for r in rows]

    def get(self, student_id: str) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT " + ", ".join(FIELDS) + " FROM intervention_records "
                "WHERE student_id = ?", (student_id,),
            ).fetchone()
        finally:
            conn.close()
        return dict(zip(FIELDS, row)) if row else None

    @staticmethod
    def filter(records: list[dict], search: str = "", risk: str = "All") -> list[dict]:
        """The window's search box + risk filter, for the CLI too."""
        search = (search or "").lower()
        out = []
        for r in records:
            if search and search not in (r.get("name") or "").lower() \
                    and search not in (r.get("student_id") or "").lower():
                continue
            if risk and risk != "All" and r.get("risk") != risk:
                continue
            out.append(r)
        return out

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save_all(self, records: list[dict]) -> None:
        """Replace the table with ``records`` in one transaction.

        The window edits an in-memory list (append/replace/remove) and
        writes it back whole; this keeps that behaviour.
        """
        now = _now()
        conn = self._conn()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM intervention_records")
            for s in records:
                conn.execute(
                    "INSERT INTO intervention_records "
                    "(student_id, name, program, gpa, email, risk, status, "
                    " intervention, last_contact, notes, updated_at, updated_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(s.get(f, "") for f in FIELDS) + (now, self.actor),
                )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.exception("Failed to save intervention records")
            raise InterventionRecordsError(f"Could not save data: {exc}") from exc
        finally:
            conn.close()

    def _write(self, sql: str, params: tuple) -> int:
        conn = self._conn()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.rowcount
        except Exception as exc:
            conn.rollback()
            logger.exception("Intervention record write failed")
            raise InterventionRecordsError(f"Could not save data: {exc}") from exc
        finally:
            conn.close()

    def add(self, data: dict) -> dict:
        if not data.get("student_id") or not data.get("name"):
            raise InterventionRecordsError("Student ID and Name are required.")
        if self.get(data["student_id"]):
            raise InterventionRecordsError(
                f"Student ID {data['student_id']} already exists.")
        record = {f: data.get(f, "") for f in FIELDS}
        record["last_contact"] = _today()
        self._write(
            "INSERT INTO intervention_records "
            "(student_id, name, program, gpa, email, risk, status, "
            " intervention, last_contact, notes, updated_at, updated_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(record[f] for f in FIELDS) + (_now(), self.actor),
        )
        logger.info("Intervention record added student=%s risk=%s by %s",
                    record["student_id"], record.get("risk"), self.actor)
        return record

    def update(self, data: dict) -> dict:
        if not data.get("student_id"):
            raise InterventionRecordsError("Please select a student to update.")
        record = {f: data.get(f, "") for f in FIELDS}
        record["last_contact"] = _today()
        sets = ", ".join(f"{f} = ?" for f in FIELDS if f != "student_id")
        changed = self._write(
            f"UPDATE intervention_records SET {sets}, updated_at = ?, updated_by = ? "
            "WHERE student_id = ?",
            tuple(record[f] for f in FIELDS if f != "student_id")
            + (_now(), self.actor, record["student_id"]),
        )
        if not changed:
            raise InterventionRecordsError("Student record not found.")
        logger.info("Intervention record updated student=%s risk=%s status=%s by %s",
                    record["student_id"], record.get("risk"),
                    record.get("status"), self.actor)
        return record

    def delete(self, student_id: str) -> None:
        if not self._write("DELETE FROM intervention_records WHERE student_id = ?",
                           (student_id,)):
            raise InterventionRecordsError("Student record not found.")
        logger.info("Intervention record deleted student=%s by %s",
                    student_id, self.actor)

    def append_note(self, student_id: str, text: str) -> dict:
        """Add a timestamped line to the case history and set today as
        the last contact."""
        record = self.get(student_id)
        if not record:
            raise InterventionRecordsError("Student record not found.")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        record["notes"] = ((record.get("notes") or "").strip()
                           + f"\n[{stamp}] {text}").strip()
        record["last_contact"] = _today()
        self._write(
            "UPDATE intervention_records SET notes = ?, last_contact = ?, "
            "updated_at = ?, updated_by = ? WHERE student_id = ?",
            (record["notes"], record["last_contact"], _now(), self.actor, student_id),
        )
        return record

    def log_contact(self, student_id: str) -> dict:
        """Stamp a contact on the case history and today's date."""
        record = self.append_note(student_id, "Contact logged by advisor.")
        logger.info("Intervention contact logged student=%s by %s",
                    student_id, self.actor)
        return record


def build_report(records: list[dict]) -> str:
    """The Generate Report text: risk/status/type breakdowns + critical cases."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = "UNIVERSITY INTERVENTION SUPPORT REPORT\n"
    report += f"Generated: {now}\n"
    report += "=" * 60 + "\n\n"

    total = len(records)
    report += f"Total Student Cases: {total}\n\n"

    report += "RISK LEVEL BREAKDOWN:\n"
    report += "-" * 40 + "\n"
    for risk in ("Critical", "High", "Medium", "Low"):
        count = sum(1 for s in records if s.get("risk") == risk)
        pct = (count / total * 100) if total else 0
        report += f"  {risk:<10} {count:>4} ({pct:.1f}%)\n"

    report += "\nSTATUS BREAKDOWN:\n"
    report += "-" * 40 + "\n"
    for status in STATUSES:
        count = sum(1 for s in records if s.get("status") == status)
        report += f"  {status:<12} {count:>4}\n"

    report += "\nINTERVENTION TYPES:\n"
    report += "-" * 40 + "\n"
    interventions: dict[str, int] = {}
    for s in records:
        itype = s.get("intervention", "Unknown")
        interventions[itype] = interventions.get(itype, 0) + 1
    for itype, count in sorted(interventions.items(), key=lambda x: -x[1]):
        report += f"  {itype:<25} {count:>4}\n"

    critical_cases = [s for s in records if s.get("risk") == "Critical"]
    if critical_cases:
        report += "\n\nCRITICAL CASES REQUIRING ATTENTION:\n"
        report += "=" * 60 + "\n"
        for s in critical_cases:
            report += f"\n• {s.get('name')} (ID: {s.get('student_id')})\n"
            report += f"  Program: {s.get('program')}\n"
            report += f"  GPA: {s.get('gpa')} | Status: {s.get('status')}\n"
            report += f"  Intervention: {s.get('intervention')}\n"
    return report

"""Student mobility service — exchange agreements, placements, learning
agreements and credit recognition.

The whole point of the module is the last of those. A period abroad that
nobody converts back into home credit is indistinguishable, at graduation,
from a year the student did not study — so the service leads with the
queries that find those: :meth:`awaiting_recognition`,
:meth:`unsigned_learning_agreements` and :meth:`credit_shortfall`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)
from education_system.systems.university.domains.academics.domain.student_mobility._db_init import (
    APPROVED,
    AWAY_STATUSES,
    COMPLETED,
    CONCLUDED_STATUSES,
    DIRECTIONS,
    IN_PROGRESS,
    OUTGOING,
    PLACEMENT_STATUSES,
    RECOGNITION_MODES,
    RETURNED,
    ensure_student_mobility_schema,
)

logger = logging.getLogger(__name__)


class MobilityError(ValueError):
    """The requested mobility operation is not valid."""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


class StudentMobilityService:
    """Read/write access to the student mobility tables."""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or UNIVERSITY_DEFAULT_DB_PATH)
        ensure_student_mobility_schema(self.db_path)

    def _conn(self) -> sqlite3.Connection:
        conn = get_connection(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ---------------------------------------------------------- agreements
    def add_agreement(self, host_institution: str,
                      partner_id: Optional[int] = None,
                      country: Optional[str] = None,
                      mobility_type: Optional[str] = None,
                      subject_area: Optional[str] = None,
                      level: Optional[str] = None,
                      places_outgoing: int = 0, places_incoming: int = 0,
                      language_of_tuition: Optional[str] = None,
                      language_requirement: Optional[str] = None,
                      valid_from: Optional[str] = None,
                      valid_to: Optional[str] = None,
                      coordinator: Optional[str] = None,
                      notes: Optional[str] = None) -> int:
        if not (host_institution or "").strip():
            raise MobilityError("Host institution is required")
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO mobility_agreements "
                "(partner_id, host_institution, country, mobility_type, "
                " subject_area, level, places_outgoing, places_incoming, "
                " language_of_tuition, language_requirement, valid_from, "
                " valid_to, coordinator, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (partner_id, host_institution.strip(), country, mobility_type,
                 subject_area, level, int(places_outgoing or 0),
                 int(places_incoming or 0), language_of_tuition,
                 language_requirement, valid_from, valid_to, coordinator, notes))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_agreements(self, active_only: bool = True,
                        country: Optional[str] = None,
                        subject_area: Optional[str] = None) -> list[dict]:
        sql = "SELECT * FROM mobility_agreements WHERE 1 = 1 "
        params: list = []
        if active_only:
            sql += "AND active = 1 "
        if country and country != "All":
            sql += "AND country = ? "
            params.append(country)
        if subject_area:
            sql += "AND subject_area LIKE ? "
            params.append(f"%{subject_area}%")
        sql += "ORDER BY country, host_institution"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_agreement(self, mobility_agreement_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM mobility_agreements WHERE mobility_agreement_id = ?",
                (int(mobility_agreement_id),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_agreement(self, mobility_agreement_id: int, **fields: Any) -> bool:
        allowed = {
            "partner_id", "host_institution", "country", "mobility_type",
            "subject_area", "level", "places_outgoing", "places_incoming",
            "language_of_tuition", "language_requirement", "valid_from",
            "valid_to", "coordinator", "active", "notes",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - filtered against a literal allow-list
            conn.execute(
                f"UPDATE mobility_agreements SET {sets} "  # nosec B608
                f"WHERE mobility_agreement_id = ?",
                (*updates.values(), int(mobility_agreement_id)))
            conn.commit()
            return True
        finally:
            conn.close()

    def place_availability(self, direction: str = OUTGOING) -> list[dict]:
        """Places contracted versus places taken, per agreement.

        Over-nominating against an exchange agreement sours the partnership
        faster than anything else, and the count is not obvious from either
        table alone.
        """
        if direction not in DIRECTIONS:
            raise MobilityError(f"Unknown direction {direction!r}")
        column = ("places_outgoing" if direction == OUTGOING
                  else "places_incoming")
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - conditional between literals
            rows = conn.execute(
                f"SELECT a.mobility_agreement_id, a.host_institution, a.country, "  # nosec B608
                f"       a.{column} AS places, a.subject_area, "
                f"       COUNT(p.placement_id) AS taken "
                f"FROM mobility_agreements a "
                f"LEFT JOIN mobility_placements p "
                f"  ON p.mobility_agreement_id = a.mobility_agreement_id "
                f" AND p.direction = ? "
                f" AND p.status NOT IN ('Cancelled', 'Withdrawn') "
                f"WHERE a.active = 1 "
                f"GROUP BY a.mobility_agreement_id "
                f"ORDER BY a.country, a.host_institution", (direction,)).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            d = dict(r)
            d["remaining"] = (d["places"] or 0) - d["taken"]
            d["over_subscribed"] = d["remaining"] < 0
            out.append(d)
        return out

    # ---------------------------------------------------------- placements
    def create_placement(self, student_id: str,
                         host_institution: Optional[str] = None,
                         direction: str = OUTGOING,
                         mobility_agreement_id: Optional[int] = None,
                         host_country: Optional[str] = None,
                         mobility_type: Optional[str] = None,
                         funding_scheme: Optional[str] = None,
                         grant_amount: Optional[float] = None,
                         academic_year: Optional[str] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         home_programme: Optional[str] = None,
                         host_programme: Optional[str] = None,
                         credits_expected: Optional[float] = None,
                         recognition_mode: Optional[str] = None,
                         coordinator: Optional[str] = None,
                         notes: Optional[str] = None) -> int:
        if direction not in DIRECTIONS:
            raise MobilityError(f"Unknown direction {direction!r}")
        if recognition_mode and recognition_mode not in RECOGNITION_MODES:
            raise MobilityError(f"Unknown recognition mode {recognition_mode!r}")
        if start_date and end_date and end_date < start_date:
            raise MobilityError("End date is before start date")

        # Fill the host details from the agreement when one was chosen, so
        # the two cannot disagree.
        if mobility_agreement_id and not host_institution:
            agreement = self.get_agreement(mobility_agreement_id)
            if agreement is None:
                raise MobilityError(
                    f"No mobility agreement {mobility_agreement_id}")
            host_institution = agreement["host_institution"]
            host_country = host_country or agreement.get("country")
            mobility_type = mobility_type or agreement.get("mobility_type")
        if not (host_institution or "").strip():
            raise MobilityError("Host institution is required")

        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO mobility_placements "
                "(student_id, direction, mobility_agreement_id, host_institution, "
                " host_country, mobility_type, funding_scheme, grant_amount, "
                " academic_year, start_date, end_date, home_programme, "
                " host_programme, credits_expected, recognition_mode, "
                " coordinator, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(student_id), direction, mobility_agreement_id,
                 host_institution.strip(), host_country, mobility_type,
                 funding_scheme, grant_amount, academic_year, start_date,
                 end_date, home_programme, host_programme, credits_expected,
                 recognition_mode, coordinator, notes))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_placement(self, placement_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM mobility_placements WHERE placement_id = ?",
                (int(placement_id),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_placements(self, direction: Optional[str] = None,
                        status: Optional[str] = None,
                        student_id: Optional[str] = None,
                        academic_year: Optional[str] = None,
                        search: Optional[str] = None) -> list[dict]:
        sql = "SELECT * FROM mobility_placements WHERE 1 = 1 "
        params: list = []
        if direction and direction != "All":
            sql += "AND direction = ? "
            params.append(direction)
        if status and status != "All":
            sql += "AND status = ? "
            params.append(status)
        if student_id:
            sql += "AND student_id = ? "
            params.append(str(student_id))
        if academic_year:
            sql += "AND academic_year = ? "
            params.append(academic_year)
        if search:
            like = f"%{search}%"
            sql += "AND (student_id LIKE ? OR host_institution LIKE ? "
            sql += "     OR host_country LIKE ?) "
            params.extend([like, like, like])
        sql += "ORDER BY start_date DESC, placement_id DESC"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def set_status(self, placement_id: int, status: str,
                   actor: Optional[str] = None) -> dict:
        """Move a placement along its lifecycle.

        Guarded rather than free-form: a placement cannot be marked complete
        while its expected credit is unrecognised, which is exactly the
        shortcut that loses a student's year abroad.
        """
        if status not in PLACEMENT_STATUSES:
            raise MobilityError(f"Unknown placement status {status!r}")
        placement = self.get_placement(placement_id)
        if placement is None:
            raise MobilityError(f"No placement {placement_id}")
        if status == COMPLETED:
            expected = placement.get("credits_expected") or 0
            recognised = placement.get("credits_recognised") or 0
            if expected and recognised < expected:
                raise MobilityError(
                    f"Cannot complete: {recognised:g} of {expected:g} credits "
                    f"recognised. Record the recognition first, or mark the "
                    f"placement '{RETURNED}'.")
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE mobility_placements SET status = ?, "
                "coordinator = COALESCE(?, coordinator) WHERE placement_id = ?",
                (status, actor, int(placement_id)))
            conn.commit()
        finally:
            conn.close()
        return self.get_placement(placement_id)

    def update_placement(self, placement_id: int, **fields: Any) -> bool:
        allowed = {
            "host_institution", "host_country", "mobility_type",
            "funding_scheme", "grant_amount", "academic_year", "start_date",
            "end_date", "home_programme", "host_programme", "credits_expected",
            "recognition_mode", "recognition_state", "insurance_confirmed",
            "risk_assessed", "coordinator", "notes", "mobility_agreement_id",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - filtered against a literal allow-list
            conn.execute(
                f"UPDATE mobility_placements SET {sets} WHERE placement_id = ?",  # nosec B608
                (*updates.values(), int(placement_id)))
            conn.commit()
            return True
        finally:
            conn.close()

    def currently_away(self, as_of: Optional[str] = None) -> list[dict]:
        """Students physically at a host institution today.

        Read by anything that would otherwise chase them for non-attendance.
        """
        when = as_of or _today()
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM mobility_placements "
                "WHERE direction = ? AND status = ? "
                "  AND (start_date IS NULL OR start_date <= ?) "
                "  AND (end_date IS NULL OR end_date >= ?) "
                "ORDER BY end_date", (OUTGOING, IN_PROGRESS, when, when)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def is_away(self, student_id: str, as_of: Optional[str] = None) -> bool:
        when = as_of or _today()
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM mobility_placements "
                "WHERE student_id = ? AND status = ? "
                "  AND (start_date IS NULL OR start_date <= ?) "
                "  AND (end_date IS NULL OR end_date >= ?) LIMIT 1",
                (str(student_id), IN_PROGRESS, when, when)).fetchone()
            return row is not None
        finally:
            conn.close()

    # ------------------------------------------------- learning agreements
    def add_learning_agreement_line(self, placement_id: int,
                                    host_module_title: str,
                                    host_module_code: Optional[str] = None,
                                    host_credits: Optional[float] = None,
                                    host_credit_system: str = "ECTS",
                                    home_module_code: Optional[str] = None,
                                    home_module_title: Optional[str] = None,
                                    home_credits: Optional[float] = None,
                                    state: str = "Draft",
                                    notes: Optional[str] = None) -> int:
        if not (host_module_title or "").strip():
            raise MobilityError("Host module title is required")
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO mobility_learning_agreements "
                "(placement_id, host_module_code, host_module_title, "
                " host_credits, host_credit_system, home_module_code, "
                " home_module_title, home_credits, state, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (int(placement_id), host_module_code, host_module_title.strip(),
                 host_credits, host_credit_system, home_module_code,
                 home_module_title, home_credits, state, notes))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def list_learning_agreement(self, placement_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM mobility_learning_agreements "
                "WHERE placement_id = ? ORDER BY line_id",
                (int(placement_id),)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def sign_learning_agreement(self, placement_id: int,
                                approved_by_home: Optional[str] = None,
                                approved_by_host: Optional[str] = None) -> int:
        """Mark every draft line signed. Returns the number of lines signed."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE mobility_learning_agreements "
                "SET state = 'Signed', approved_by_home = COALESCE(?, approved_by_home), "
                "    approved_by_host = COALESCE(?, approved_by_host), approved_at = ? "
                "WHERE placement_id = ? AND state <> 'Rejected'",
                (approved_by_home, approved_by_host, _now(), int(placement_id)))
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()

    def unsigned_learning_agreements(self) -> list[dict]:
        """Approved or in-progress placements with no signed study plan.

        A student abroad without a signed learning agreement has no
        guarantee that anything they pass will count.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT p.*, "
                "  (SELECT COUNT(*) FROM mobility_learning_agreements l "
                "    WHERE l.placement_id = p.placement_id) AS lines_total, "
                "  (SELECT COUNT(*) FROM mobility_learning_agreements l "
                "    WHERE l.placement_id = p.placement_id "
                "      AND l.state = 'Signed') AS lines_signed "
                "FROM mobility_placements p "
                "WHERE p.status IN (?, ?) "
                "ORDER BY p.start_date", (APPROVED, IN_PROGRESS)).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows
                if (r["lines_total"] or 0) == 0
                or (r["lines_signed"] or 0) < (r["lines_total"] or 0)]

    # -------------------------------------------------------- recognitions
    def record_recognition(self, placement_id: int,
                           home_credits: Optional[float] = None,
                           line_id: Optional[int] = None,
                           host_module_code: Optional[str] = None,
                           host_grade: Optional[str] = None,
                           host_credits: Optional[float] = None,
                           home_module_code: Optional[str] = None,
                           converted_mark: Optional[float] = None,
                           mode: Optional[str] = None,
                           outcome: str = "Recognised",
                           recognised_by: Optional[str] = None,
                           notes: Optional[str] = None) -> int:
        """Record host credit converted into our own.

        The placement's ``credits_recognised`` total is maintained by a
        trigger, so it stays right whichever interface wrote the row.
        """
        if self.get_placement(placement_id) is None:
            raise MobilityError(f"No placement {placement_id}")
        if mode and mode not in RECOGNITION_MODES:
            raise MobilityError(f"Unknown recognition mode {mode!r}")
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO mobility_credit_recognitions "
                "(placement_id, line_id, host_module_code, host_grade, "
                " host_credits, home_module_code, home_credits, converted_mark, "
                " mode, outcome, recognised_by, recognised_at, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (int(placement_id), line_id, host_module_code, host_grade,
                 host_credits, home_module_code, home_credits, converted_mark,
                 mode, outcome, recognised_by, _now(), notes))
            conn.commit()
            recognition_id = int(cur.lastrowid)
        finally:
            conn.close()
        self._refresh_recognition_state(placement_id)
        return recognition_id

    def list_recognitions(self, placement_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM mobility_credit_recognitions "
                "WHERE placement_id = ? ORDER BY recognition_id",
                (int(placement_id),)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _refresh_recognition_state(self, placement_id: int) -> None:
        placement = self.get_placement(placement_id)
        if placement is None:
            return
        expected = placement.get("credits_expected") or 0
        recognised = placement.get("credits_recognised") or 0
        if not expected:
            state = "Recognised" if recognised else "Transcript Received"
        elif recognised >= expected:
            state = "Recognised"
        elif recognised > 0:
            state = "Partially Recognised"
        else:
            state = placement.get("recognition_state") or "Awaiting Transcript"
        self.update_placement(placement_id, recognition_state=state)

    def awaiting_recognition(self, older_than_days: int = 60) -> list[dict]:
        """Concluded placements whose credit has still not come home.

        ``older_than_days`` is measured from the placement end date — the
        grace period for a host transcript to arrive.
        """
        cutoff = (date.today() - timedelta(days=int(older_than_days))).isoformat()
        placeholders = ", ".join("?" for _ in CONCLUDED_STATUSES)
        conn = self._conn()
        try:
            # db-audit: ignore[DBW001] - string literal
            rows = conn.execute(
                f"SELECT * FROM mobility_placements "  # nosec B608
                f"WHERE status IN ({placeholders}) "
                f"  AND COALESCE(credits_expected, 0) > COALESCE(credits_recognised, 0) "
                f"  AND (end_date IS NULL OR end_date <= ?) "
                f"ORDER BY end_date",
                (*sorted(CONCLUDED_STATUSES), cutoff)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def credit_shortfall(self, placement_id: int) -> dict:
        placement = self.get_placement(placement_id)
        if placement is None:
            raise MobilityError(f"No placement {placement_id}")
        expected = placement.get("credits_expected") or 0
        recognised = placement.get("credits_recognised") or 0
        return {
            "placement_id": int(placement_id),
            "student_id": placement["student_id"],
            "host_institution": placement.get("host_institution"),
            "credits_expected": expected,
            "credits_recognised": recognised,
            "shortfall": max(0.0, float(expected) - float(recognised)),
            "recognition_state": placement.get("recognition_state"),
        }

    # ---------------------------------------------------------- monitoring
    def student_history(self, student_id: str) -> list[dict]:
        placements = self.list_placements(student_id=str(student_id))
        for placement in placements:
            placement["learning_agreement"] = self.list_learning_agreement(
                placement["placement_id"])
            placement["recognitions"] = self.list_recognitions(
                placement["placement_id"])
        return placements

    def preparation_gaps(self) -> list[dict]:
        """Approved outgoing placements missing insurance or a risk assessment."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM mobility_placements "
                "WHERE direction = ? AND status IN (?, ?) "
                "  AND (insurance_confirmed = 0 OR risk_assessed = 0) "
                "ORDER BY start_date",
                (OUTGOING, APPROVED, IN_PROGRESS)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def summary(self, academic_year: Optional[str] = None) -> dict:
        conn = self._conn()
        try:
            def count(where: str, params: tuple = ()) -> int:
                sql = f"SELECT COUNT(*) FROM mobility_placements WHERE {where} "  # nosec B608
                args = list(params)
                if academic_year:
                    sql += "AND academic_year = ? "
                    args.append(academic_year)
                return int(conn.execute(sql, args).fetchone()[0] or 0)

            away_placeholders = ", ".join("?" for _ in AWAY_STATUSES)
            return {
                "agreements": int(conn.execute(
                    "SELECT COUNT(*) FROM mobility_agreements WHERE active = 1"
                ).fetchone()[0] or 0),
                "outgoing": count("direction = ?", (OUTGOING,)),
                "incoming": count("direction = 'incoming'"),
                "away_now": count(
                    f"direction = ? AND status IN ({away_placeholders})",  # nosec B608
                    (OUTGOING, *sorted(AWAY_STATUSES))),
                "awaiting_recognition": len(self.awaiting_recognition()),
                "unsigned_agreements": len(self.unsigned_learning_agreements()),
            }
        finally:
            conn.close()


__all__ = ["StudentMobilityService", "MobilityError"]

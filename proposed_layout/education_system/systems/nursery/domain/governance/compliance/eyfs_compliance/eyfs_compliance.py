"""Domain layer for EYFS Compliance (Nursery System).

A computed, read-only statutory-framework compliance checklist. It owns no
table of its own — it interrogates the live nursery data (staff, pupils,
training, first-aid certificates, accident register, contacts and consents)
plus the Staff:Child Ratios and Occupancy reports, and grades each EYFS
welfare requirement as ok / warning / fail / info.

Every individual check is guarded so one failing query can never abort the
whole report, and tables that may not exist are probed defensively before use.

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``eyfs_compliance_cli.py``, Tk GUI in ``eyfs_compliance_views.py``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from education_system.systems.nursery.infrastructure import paths
from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "EYFS Compliance"
CATEGORY = "Compliance & Reports"

# Optional cross-module reports — guarded so a missing/broken module can't
# break the whole checklist.
try:
    from education_system.systems.nursery.domain.operations.ratios import ratios
except Exception:  # noqa: BLE001
    ratios = None  # type: ignore[assignment]
    logger.debug("ratios module unavailable for EYFS compliance", exc_info=True)

try:
    from education_system.systems.nursery.domain.operations.reporting.occupancy_report import (
        occupancy_report,
    )
except Exception:  # noqa: BLE001
    occupancy_report = None  # type: ignore[assignment]
    logger.debug("occupancy_report unavailable for EYFS compliance", exc_info=True)

# Section labels (stable order).
SEC_SAFEGUARDING = "Safeguarding & welfare"
SEC_STAFFING = "Staffing & qualifications"
SEC_HEALTH = "Health & first aid"
SEC_PREMISES = "Safety & suitability of premises"
SEC_RECORDS = "Information & records"

_SECTION_ORDER = [
    SEC_SAFEGUARDING, SEC_STAFFING, SEC_HEALTH, SEC_PREMISES, SEC_RECORDS,
]

# Warn when an expiry date falls within this many days.
_EXPIRY_WARN_DAYS = 90


@dataclass
class Check:
    section: str
    title: str
    status: str  # "ok" / "warning" / "fail" / "info"
    detail: str
    action: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for EYFS compliance")
        raise


def _today() -> _dt.date:
    return _dt.date.today()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,)).fetchone()
        return row is not None
    except sqlite3.Error:
        logger.debug("Could not probe table %s", name, exc_info=True)
        return False


def _parse_date(value: str | None) -> _dt.date | None:
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _days_until(value: str | None) -> int | None:
    d = _parse_date(value)
    if d is None:
        return None
    return (d - _today()).days


# ── Individual checks ─────────────────────────────────────────────────────────

def _check_dsl(conn: sqlite3.Connection) -> Check:
    n = conn.execute(
        "SELECT COUNT(*) FROM staff WHERE is_dsl = 1 "
        "AND (end_date IS NULL OR end_date = '')").fetchone()[0]
    if n:
        return Check(SEC_SAFEGUARDING, "Designated Safeguarding Lead", "ok",
                     f"{n} employed staff flagged as DSL.")
    return Check(SEC_SAFEGUARDING, "Designated Safeguarding Lead", "fail",
                 "No employed staff member is flagged as a DSL.",
                 "Appoint and flag a Designated Safeguarding Lead.")


def _check_dsl_training(conn: sqlite3.Connection) -> Check:
    title = "DSL safeguarding training"
    if not _table_exists(conn, "staff_training"):
        return Check(SEC_SAFEGUARDING, title, "info",
                     "Training records table not available.")
    today = _today().isoformat()
    rows = conn.execute(
        "SELECT t.expiry_date FROM staff_training t JOIN staff s "
        "ON s.staff_id = t.staff_id "
        "WHERE s.is_dsl = 1 AND (s.end_date IS NULL OR s.end_date = '') "
        "AND t.course LIKE '%afeguard%' "
        "AND (t.expiry_date IS NULL OR t.expiry_date = '' "
        "OR t.expiry_date >= ?)",
        (today,)).fetchall()
    if not rows:
        return Check(SEC_SAFEGUARDING, title, "fail",
                     "No current safeguarding training found for a DSL.",
                     "Book / renew safeguarding training for the DSL.")
    soonest: int | None = None
    for r in rows:
        d = _days_until(r["expiry_date"])
        if d is not None and (soonest is None or d < soonest):
            soonest = d
    if soonest is not None and 0 <= soonest <= _EXPIRY_WARN_DAYS:
        return Check(SEC_SAFEGUARDING, title, "warning",
                     f"DSL safeguarding training expires in {soonest} day(s).",
                     "Schedule DSL safeguarding refresher training.")
    return Check(SEC_SAFEGUARDING, title, "ok",
                 "DSL holds current safeguarding training.")


def _check_ratios() -> Check:
    title = "Staff:child ratios met"
    if ratios is None:
        return Check(SEC_STAFFING, title, "info",
                     "Ratios module not available.")
    s = ratios.summary()
    breaches = int(s.get("breaches", 0))
    no_ratio = int(s.get("no_ratio_set", 0))
    unplaced = int(s.get("unplaced_children", 0))
    extras: list[str] = []
    if no_ratio:
        extras.append(f"{no_ratio} room(s) have no ratio set")
    if unplaced:
        extras.append(f"{unplaced} child(ren) unplaced")
    suffix = (" " + "; ".join(extras) + ".") if extras else ""
    if breaches:
        return Check(SEC_STAFFING, title, "fail",
                     f"{breaches} room(s) breach the required ratio.{suffix}",
                     "Deploy more staff to under-staffed rooms.")
    if no_ratio:
        return Check(SEC_STAFFING, title, "warning",
                     f"All staffed rooms meet ratio, but{suffix}",
                     "Set a required ratio for every room.")
    return Check(SEC_STAFFING, title, "ok",
                 "All rooms meet their required staff:child ratio." + suffix)


def _check_qualifications(conn: sqlite3.Connection) -> Check:
    title = "Staff qualifications recorded"
    rows = conn.execute(
        "SELECT qualifications FROM staff "
        "WHERE (end_date IS NULL OR end_date = '')").fetchall()
    total = len(rows)
    missing = sum(1 for r in rows if not (r["qualifications"] or "").strip())
    if total == 0:
        return Check(SEC_STAFFING, title, "info",
                     "No employed staff on record.")
    if missing:
        return Check(SEC_STAFFING, title, "warning",
                     f"{missing} of {total} employed staff have no "
                     "qualifications recorded.",
                     "Record qualifications for all staff.")
    return Check(SEC_STAFFING, title, "ok",
                 f"All {total} employed staff have qualifications recorded.")


def _check_key_person(conn: sqlite3.Connection) -> Check:
    title = "Key person assigned to every child"
    total = conn.execute(
        "SELECT COUNT(*) FROM pupils WHERE status = 'active'").fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM pupils WHERE status = 'active' "
        "AND (key_person IS NULL OR key_person = '')").fetchone()[0]
    if total == 0:
        return Check(SEC_STAFFING, title, "info", "No active children on roll.")
    if missing:
        return Check(SEC_STAFFING, title, "warning",
                     f"{missing} of {total} active children have no key "
                     "person assigned.",
                     "Assign a key person to every child.")
    return Check(SEC_STAFFING, title, "ok",
                 f"All {total} active children have a key person.")


def _check_paediatric_first_aid(conn: sqlite3.Connection) -> Check:
    title = "Paediatric first aid in place"
    pfa_staff = conn.execute(
        "SELECT COUNT(*) FROM staff WHERE is_paediatric_first_aider = 1 "
        "AND (end_date IS NULL OR end_date = '')").fetchone()[0]
    if not _table_exists(conn, "paediatric_first_aid"):
        if pfa_staff:
            return Check(SEC_HEALTH, title, "warning",
                         f"{pfa_staff} PFA-flagged staff, but no certificate "
                         "records available.",
                         "Record paediatric first-aid certificates.")
        return Check(SEC_HEALTH, title, "fail",
                     "No paediatric first aider on staff.",
                     "Ensure a PFA-trained member of staff is on site.")
    today = _today().isoformat()
    certs = conn.execute(
        "SELECT p.expiry_date FROM paediatric_first_aid p JOIN staff s "
        "ON s.staff_id = p.staff_id "
        "WHERE (s.end_date IS NULL OR s.end_date = '') "
        "AND (p.expiry_date IS NULL OR p.expiry_date = '' "
        "OR p.expiry_date >= ?)",
        (today,)).fetchall()
    if not pfa_staff or not certs:
        return Check(SEC_HEALTH, title, "fail",
                     "No employed staff member holds a valid paediatric "
                     "first-aid certificate.",
                     "Arrange / renew paediatric first-aid training.")
    soonest: int | None = None
    for c in certs:
        d = _days_until(c["expiry_date"])
        if d is not None and (soonest is None or d < soonest):
            soonest = d
    if soonest is not None and 0 <= soonest <= _EXPIRY_WARN_DAYS:
        return Check(SEC_HEALTH, title, "warning",
                     f"A paediatric first-aid certificate expires in "
                     f"{soonest} day(s).",
                     "Renew the expiring paediatric first-aid certificate.")
    return Check(SEC_HEALTH, title, "ok",
                 f"{pfa_staff} PFA-trained staff with valid certificate(s).")


def _check_accident_register(conn: sqlite3.Connection) -> Check:
    title = "Accident / incident register kept"
    if not _table_exists(conn, "accident_records"):
        return Check(SEC_HEALTH, title, "info",
                     "Accident register table not available.")
    total = conn.execute(
        "SELECT COUNT(*) FROM accident_records").fetchone()[0]
    open_n = conn.execute(
        "SELECT COUNT(*) FROM accident_records WHERE status = 'open'"
    ).fetchone()[0]
    riddor = conn.execute(
        "SELECT COUNT(*) FROM accident_records WHERE riddor_reportable = 1"
    ).fetchone()[0]
    open_riddor = conn.execute(
        "SELECT COUNT(*) FROM accident_records WHERE riddor_reportable = 1 "
        "AND status = 'open'").fetchone()[0]
    detail = f"{total} record(s); {open_n} open; {riddor} RIDDOR-reportable."
    if open_riddor:
        return Check(SEC_HEALTH, title, "warning",
                     detail + f" {open_riddor} open RIDDOR-reportable.",
                     "Action / close open RIDDOR-reportable records.")
    return Check(SEC_HEALTH, title, "info", detail)


def _check_allergy_care_plans(conn: sqlite3.Connection) -> Check:
    title = "Allergy care plans recorded"
    rows = conn.execute(
        "SELECT allergies, medical_notes FROM pupils WHERE status = 'active' "
        "AND allergies IS NOT NULL AND TRIM(allergies) <> '' "
        "AND LOWER(TRIM(allergies)) <> 'none'").fetchall()
    with_allergy = len(rows)
    needing = sum(1 for r in rows if not (r["medical_notes"] or "").strip())
    if with_allergy == 0:
        return Check(SEC_HEALTH, title, "ok",
                     "No active children with a recorded allergy.")
    if needing:
        return Check(SEC_HEALTH, title, "warning",
                     f"{needing} of {with_allergy} children with an allergy "
                     "have no medical care plan.",
                     "Add a medical care plan for each child with an allergy.")
    return Check(SEC_HEALTH, title, "ok",
                 f"All {with_allergy} children with an allergy have a "
                 "care plan.")


def _check_room_capacity() -> Check:
    title = "No room over capacity"
    if occupancy_report is None:
        return Check(SEC_PREMISES, title, "info",
                     "Occupancy report module not available.")
    s = occupancy_report.summary()
    over = int(s.get("over_capacity_rooms", 0))
    if over:
        return Check(SEC_PREMISES, title, "fail",
                     f"{over} room(s) are over capacity.",
                     "Reduce numbers or open additional space.")
    return Check(SEC_PREMISES, title, "ok",
                 "No room is over its registered capacity.")


def _check_emergency_contacts(conn: sqlite3.Connection) -> Check:
    title = "Emergency contact on file for every child"
    if not _table_exists(conn, "emergency_contacts"):
        return Check(SEC_RECORDS, title, "info",
                     "Emergency contacts table not available.")
    total = conn.execute(
        "SELECT COUNT(*) FROM pupils WHERE status = 'active'").fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM pupils p WHERE p.status = 'active' "
        "AND NOT EXISTS (SELECT 1 FROM emergency_contacts e "
        "WHERE e.pupil_id = p.pupil_id)").fetchone()[0]
    if total == 0:
        return Check(SEC_RECORDS, title, "info", "No active children on roll.")
    if missing:
        return Check(SEC_RECORDS, title, "fail",
                     f"{missing} of {total} active children have no emergency "
                     "contact recorded.",
                     "Record at least one emergency contact per child.")
    return Check(SEC_RECORDS, title, "ok",
                 f"All {total} active children have an emergency contact.")


def _check_parent_contacts(conn: sqlite3.Connection) -> Check:
    title = "Parent / carer recorded for every child"
    if not _table_exists(conn, "parent_contacts"):
        return Check(SEC_RECORDS, title, "info",
                     "Parent contacts table not available.")
    total = conn.execute(
        "SELECT COUNT(*) FROM pupils WHERE status = 'active'").fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM pupils p WHERE p.status = 'active' "
        "AND NOT EXISTS (SELECT 1 FROM parent_contacts c "
        "WHERE c.pupil_id = p.pupil_id)").fetchone()[0]
    if total == 0:
        return Check(SEC_RECORDS, title, "info", "No active children on roll.")
    if missing:
        return Check(SEC_RECORDS, title, "warning",
                     f"{missing} of {total} active children have no parent / "
                     "carer recorded.",
                     "Record a parent / carer contact for every child.")
    return Check(SEC_RECORDS, title, "ok",
                 f"All {total} active children have a parent / carer recorded.")


def _check_consents(conn: sqlite3.Connection) -> Check:
    title = "Consents recorded for every child"
    if not _table_exists(conn, "consents"):
        return Check(SEC_RECORDS, title, "info",
                     "Consents table not available.")
    total = conn.execute(
        "SELECT COUNT(*) FROM pupils WHERE status = 'active'").fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM pupils p WHERE p.status = 'active' "
        "AND NOT EXISTS (SELECT 1 FROM consents c "
        "WHERE c.pupil_id = p.pupil_id)").fetchone()[0]
    if total == 0:
        return Check(SEC_RECORDS, title, "info", "No active children on roll.")
    if missing:
        return Check(SEC_RECORDS, title, "warning",
                     f"{missing} of {total} active children have no consents "
                     "recorded.",
                     "Record statutory consents for every child.")
    return Check(SEC_RECORDS, title, "ok",
                 f"All {total} active children have consents recorded.")


# ── Aggregation ───────────────────────────────────────────────────────────────

def compliance() -> list[Check]:
    """Build the full EYFS compliance checklist.

    Each check is run independently so one failure can never abort the rest.
    """
    _ensure_schema()
    checks: list[Check] = []

    def _run(fn, *args) -> None:
        try:
            checks.append(fn(*args))
        except Exception:  # noqa: BLE001
            logger.exception("EYFS compliance check failed: %s", fn.__name__)
            checks.append(Check(
                "Other", fn.__name__, "info",
                "Check could not be evaluated — see logs."))

    try:
        with connect() as conn:
            _run(_check_dsl, conn)
            _run(_check_dsl_training, conn)
            _run(_check_ratios)
            _run(_check_qualifications, conn)
            _run(_check_key_person, conn)
            _run(_check_paediatric_first_aid, conn)
            _run(_check_accident_register, conn)
            _run(_check_allergy_care_plans, conn)
            _run(_check_room_capacity)
            _run(_check_emergency_contacts, conn)
            _run(_check_parent_contacts, conn)
            _run(_check_consents, conn)
    except sqlite3.Error:
        logger.exception("EYFS compliance could not open the database")
        raise
    return checks


def section_summary() -> dict[str, dict]:
    """Per-section counts of ok / warning / fail / info."""
    out: dict[str, dict] = {}
    for c in compliance():
        bucket = out.setdefault(
            c.section, {"ok": 0, "warning": 0, "fail": 0, "info": 0})
        if c.status in bucket:
            bucket[c.status] += 1
    return out


def score() -> dict:
    """Overall compliance score across all checks (info excluded from %)."""
    counts = {"ok": 0, "warning": 0, "fail": 0, "info": 0}
    for c in compliance():
        if c.status in counts:
            counts[c.status] += 1
    total = counts["ok"] + counts["warning"] + counts["fail"]
    pct = round(counts["ok"] / total * 100, 1) if total else 0.0
    if pct >= 90:
        grade = "Fully compliant"
    elif pct >= 75:
        grade = "Mostly compliant"
    elif pct >= 50:
        grade = "Partially compliant"
    else:
        grade = "Significant gaps"
    return {
        "ok": counts["ok"], "warning": counts["warning"],
        "fail": counts["fail"], "info": counts["info"],
        "total": total, "pct": pct, "grade": grade,
    }


def sections_in_order() -> list[str]:
    """Section labels in their canonical order."""
    return list(_SECTION_ORDER)


# ── Export ───────────────────────────────────────────────────────────────────

def export_csv(path: str | Path | None = None) -> dict[str, object]:
    """Write the compliance checklist to CSV; return path + row count."""
    rows = compliance()
    if path is None:
        paths.ensure_directories()
        path = paths.DATA_DIR / (
            f"eyfs_compliance_{_dt.date.today().isoformat()}.csv")
    path = Path(path)
    headers = ["section", "title", "status", "detail", "action"]
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for c in rows:
                w.writerow([c.section, c.title, c.status, c.detail,
                            c.action or ""])
    except OSError as e:
        logger.exception("Could not write EYFS compliance CSV to %s", path)
        raise OSError(f"Could not write report — {e}") from e
    return {"path": str(path), "row_count": len(rows)}

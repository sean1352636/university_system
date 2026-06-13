"""Domain layer for the Ofsted Readiness checklist (Nursery System).

A computed, read-only inspection-readiness report. It owns no table of its own —
it runs a series of EYFS welfare-requirement checks across the existing nursery
tables (staff, pupils, rooms, training, paediatric first aid, funded hours and
the accident register) and reuses the Staff:Child Ratios and Occupancy modules
for the ratio and capacity checks. Each check yields a status (ok / warning /
fail / info), a human-readable detail and, where relevant, a suggested action.

Every check is wrapped so that a single failing query can't abort the whole
report — on error the check degrades to an "info" note. A roll-up ``score()``
turns the checks into an at-a-glance readiness grade, and ``export_csv()`` writes
the checklist to CSV.

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``ofsted_cli.py``, Tk GUI in ``ofsted_views.py``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from education_system.nursery_system.core import paths
from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Ofsted Readiness"
CATEGORY = "Compliance & Reports"

_SOON_DAYS = 90  # certificates/training expiring within this window -> warning
_EMPLOYED = "(end_date IS NULL OR end_date = '')"
_FUNDED_PRIVATE = "Private (unfunded)"


@dataclass
class Check:
    key: str
    area: str
    title: str
    status: str  # one of "ok" / "warning" / "fail" / "info"
    detail: str
    action: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for Ofsted readiness")
        raise


def _today() -> str:
    return _dt.date.today().isoformat()


def _soon() -> str:
    return (_dt.date.today() + _dt.timedelta(days=_SOON_DAYS)).isoformat()


def _info_error(key: str, area: str, title: str) -> Check:
    return Check(
        key=key, area=area, title=title, status="info",
        detail="Could not be evaluated — see logs for details.",
        action="Check the underlying records and try again.")


# ── Individual checks ─────────────────────────────────────────────────────────
# Each returns a list of Check. Each is invoked via ``readiness`` inside a
# try/except so a query error degrades to an "info" note rather than breaking
# the whole report.

def _check_dsl() -> list[Check]:
    with connect() as conn:
        n = conn.execute(
            f"SELECT COUNT(*) FROM staff WHERE is_dsl = 1 AND {_EMPLOYED}"
        ).fetchone()[0]
    if n:
        return [Check("dsl", "Safeguarding", "Designated Safeguarding Lead",
                      "ok", f"{n} employed staff recorded as DSL.")]
    return [Check("dsl", "Safeguarding", "Designated Safeguarding Lead",
                  "fail", "No Designated Safeguarding Lead on record.",
                  "Appoint and record a Designated Safeguarding Lead.")]


def _check_dsl_training() -> list[Check]:
    today = _today()
    soon = _soon()
    with connect() as conn:
        dsls = conn.execute(
            f"SELECT staff_id FROM staff WHERE is_dsl = 1 AND {_EMPLOYED}"
        ).fetchall()
        if not dsls:
            return [Check(
                "dsl_training", "Safeguarding", "DSL safeguarding training",
                "fail", "No DSL on record to evidence safeguarding training.",
                "Appoint a DSL and record their safeguarding training.")]
        ids = [r["staff_id"] for r in dsls]
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            "SELECT expiry_date FROM staff_training "
            f"WHERE staff_id IN ({placeholders}) "
            "AND course LIKE '%afeguard%' "
            "AND (expiry_date IS NULL OR expiry_date >= ?)",
            (*ids, today),
        ).fetchall()
    if not rows:
        return [Check(
            "dsl_training", "Safeguarding", "DSL safeguarding training",
            "fail", "No current safeguarding training found for the DSL(s).",
            "Book/renew safeguarding training for the DSL(s).")]
    dated = [r["expiry_date"] for r in rows if r["expiry_date"]]
    if dated and all(e < soon for e in dated) and len(dated) == len(rows):
        return [Check(
            "dsl_training", "Safeguarding", "DSL safeguarding training",
            "warning",
            f"DSL safeguarding training expires within {_SOON_DAYS} days.",
            "Schedule the safeguarding refresher before it lapses.")]
    return [Check("dsl_training", "Safeguarding", "DSL safeguarding training",
                  "ok", "DSL has current safeguarding training.")]


def _check_first_aid() -> list[Check]:
    today = _today()
    soon = _soon()
    with connect() as conn:
        flagged = conn.execute(
            "SELECT COUNT(*) FROM staff "
            f"WHERE is_paediatric_first_aider = 1 AND {_EMPLOYED}"
        ).fetchone()[0]
        valid = conn.execute(
            "SELECT expiry_date FROM paediatric_first_aid "
            "WHERE expiry_date >= ? ORDER BY expiry_date", (today,)
        ).fetchall()
    if not flagged or not valid:
        return [Check(
            "first_aid", "First Aid", "Paediatric first aid",
            "fail", "No valid paediatric first aid cover on record.",
            "Ensure a paediatric first aider with a current certificate.")]
    soonest = valid[0]["expiry_date"]
    if soonest and soonest < soon:
        return [Check(
            "first_aid", "First Aid", "Paediatric first aid",
            "warning",
            f"A paediatric first aid certificate expires within "
            f"{_SOON_DAYS} days (next: {soonest}).",
            "Book a PFA refresher before the certificate lapses.")]
    return [Check("first_aid", "First Aid", "Paediatric first aid",
                  "ok", f"{len(valid)} valid paediatric first aid "
                        "certificate(s) on record.")]


def _check_dbs() -> list[Check]:
    with connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM staff WHERE {_EMPLOYED}").fetchone()[0]
        missing = conn.execute(
            f"SELECT COUNT(*) FROM staff WHERE {_EMPLOYED} "
            "AND (dbs_checked IS NULL OR dbs_checked != 1)").fetchone()[0]
    if not missing:
        return [Check("dbs", "Suitable People", "DBS checks",
                      "ok", f"All {total} employed staff have a DBS check.")]
    return [Check(
        "dbs", "Suitable People", "DBS checks", "fail",
        f"{missing} of {total} employed staff have no DBS check recorded.",
        "Complete and record enhanced DBS checks for all staff.")]


def _check_ratios() -> list[Check]:
    from education_system.nursery_system.modules.domain.ratios import (
        ratios as _ratios,
    )
    s = _ratios.summary()
    breaches = int(s.get("breaches", 0))
    no_ratio = int(s.get("no_ratio_set", 0))
    unplaced = int(s.get("unplaced_children", 0))
    if breaches:
        status = "fail"
        detail = f"{breaches} room(s) are under the required staff:child ratio."
        action = "Deploy additional staff to bring rooms back into ratio."
        if no_ratio:
            detail += f" {no_ratio} room(s) also have no ratio set."
    elif no_ratio:
        status = "warning"
        detail = f"{no_ratio} room(s) have no staff:child ratio set."
        action = "Set the EYFS ratio for every room."
    else:
        status, detail, action = (
            "ok", "All rooms meet their staff:child ratio.", None)
    if unplaced:
        detail += f" {unplaced} active child(ren) are not placed in a room."
        if status == "ok":
            status, action = "warning", "Assign unplaced children to a room."
    return [Check("ratios", "Staffing Ratios", "Staff:child ratios",
                  status, detail, action)]


def _check_key_person() -> list[Check]:
    with connect() as conn:
        missing = conn.execute(
            "SELECT COUNT(*) FROM pupils WHERE status = 'active' "
            "AND (key_person IS NULL OR key_person = '')").fetchone()[0]
    if not missing:
        return [Check("key_person", "Key Person", "Key person assigned",
                      "ok", "Every active child has a key person.")]
    return [Check(
        "key_person", "Key Person", "Key person assigned", "warning",
        f"{missing} active child(ren) have no key person assigned.",
        "Assign a key person to every child (EYFS requirement).")]


def _check_premises() -> list[Check]:
    from education_system.nursery_system.modules.domain.occupancy_report import (
        occupancy_report as _occupancy,
    )
    s = _occupancy.summary()
    over = int(s.get("over_capacity_rooms", 0))
    if not over:
        return [Check("premises", "Premises", "Room capacity",
                      "ok", "No rooms are over capacity.")]
    names = [r.name for r in _occupancy.list_room_occupancy() if r.over_capacity]
    listing = ", ".join(names) if names else f"{over} room(s)"
    return [Check(
        "premises", "Premises", "Room capacity", "fail",
        f"{over} room(s) over capacity: {listing}.",
        "Reduce numbers or review the registered capacity for these rooms.")]


def _check_funding() -> list[Check]:
    with connect() as conn:
        children = conn.execute(
            "SELECT pupil_id, funded_hours FROM pupils WHERE status = 'active' "
            "AND funded_hours IS NOT NULL AND funded_hours != '' "
            "AND funded_hours != ?", (_FUNDED_PRIVATE,)).fetchall()
        funded_ids = {
            r["pupil_id"] for r in conn.execute(
                "SELECT DISTINCT pupil_id FROM funded_hours_records "
                "WHERE status = 'active'").fetchall()
        }
    unevidenced = sum(1 for c in children if c["pupil_id"] not in funded_ids)
    if not unevidenced:
        return [Check("funding", "Funding", "Funded hours evidenced",
                      "ok", "All funded children have a funding record.")]
    return [Check(
        "funding", "Funding", "Funded hours evidenced", "warning",
        f"{unevidenced} funded child(ren) have no active funding record.",
        "Add funded-hours records (with eligibility codes) for these children.")]


def _check_welfare_records() -> list[Check]:
    with connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM accident_records").fetchone()[0]
        open_n = conn.execute(
            "SELECT COUNT(*) FROM accident_records WHERE status = 'open'"
        ).fetchone()[0]
        riddor = conn.execute(
            "SELECT COUNT(*) FROM accident_records "
            "WHERE riddor_reportable = 1").fetchone()[0]
        open_riddor = conn.execute(
            "SELECT COUNT(*) FROM accident_records "
            "WHERE riddor_reportable = 1 AND status = 'open'").fetchone()[0]
    detail = (f"{total} accident/incident record(s); {open_n} open, "
              f"{riddor} RIDDOR-reportable.")
    if open_riddor:
        return [Check(
            "welfare", "Welfare Records", "Accident register", "warning",
            detail + f" {open_riddor} open RIDDOR-reportable.",
            "Report and close outstanding RIDDOR-reportable records.")]
    return [Check("welfare", "Welfare Records", "Accident register",
                  "info", detail)]


_CHECK_FNS = [
    (_check_dsl, "dsl", "Safeguarding", "Designated Safeguarding Lead"),
    (_check_dsl_training, "dsl_training", "Safeguarding",
     "DSL safeguarding training"),
    (_check_first_aid, "first_aid", "First Aid", "Paediatric first aid"),
    (_check_dbs, "dbs", "Suitable People", "DBS checks"),
    (_check_ratios, "ratios", "Staffing Ratios", "Staff:child ratios"),
    (_check_key_person, "key_person", "Key Person", "Key person assigned"),
    (_check_premises, "premises", "Premises", "Room capacity"),
    (_check_funding, "funding", "Funding", "Funded hours evidenced"),
    (_check_welfare_records, "welfare", "Welfare Records",
     "Accident register"),
]


def readiness() -> list[Check]:
    """Run every readiness check; degrade failures to "info" notes."""
    _ensure_schema()
    out: list[Check] = []
    for fn, key, area, title in _CHECK_FNS:
        try:
            out.extend(fn())
        except Exception:  # noqa: BLE001 — one bad check must not abort the rest
            logger.exception("Ofsted check %s failed", key)
            out.append(_info_error(key, area, title))
    return out


def score() -> dict[str, object]:
    """Roll the checks up into a readiness grade."""
    checks = readiness()
    ok = sum(1 for c in checks if c.status == "ok")
    warning = sum(1 for c in checks if c.status == "warning")
    fail = sum(1 for c in checks if c.status == "fail")
    info = sum(1 for c in checks if c.status == "info")
    total = ok + warning + fail
    pct = round(ok / total * 100, 1) if total else 0.0
    if pct >= 90:
        grade = "Ready for inspection"
    elif pct >= 75:
        grade = "Good — minor actions"
    elif pct >= 50:
        grade = "Requires improvement"
    else:
        grade = "Urgent action needed"
    return {
        "ok": ok, "warning": warning, "fail": fail, "info": info,
        "total": total, "pct": pct, "grade": grade,
    }


# ── Export ───────────────────────────────────────────────────────────────────

def export_csv(path: str | Path | None = None) -> dict[str, object]:
    """Write the readiness checklist to CSV; return path + row count."""
    checks = readiness()
    if path is None:
        paths.ensure_directories()
        path = paths.DATA_DIR / f"ofsted_readiness_{_today()}.csv"
    path = Path(path)
    headers = ["area", "title", "status", "detail", "action"]
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for c in checks:
                w.writerow([c.area, c.title, c.status, c.detail, c.action or ""])
    except OSError as e:
        logger.exception("Could not write Ofsted readiness CSV to %s", path)
        raise OSError(f"Could not write report — {e}") from e
    return {"path": str(path), "row_count": len(checks)}

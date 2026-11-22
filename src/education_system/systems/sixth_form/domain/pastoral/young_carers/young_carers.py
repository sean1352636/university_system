"""Young carers support records for the Sixth Form.

One truth, three readers. The support record lives in the wellbeing
module's ``vg_young_carers`` table (who they care for, caring tasks,
hours, support provider, support plan, review dates); this module adds
the columns a full young-carer support record needs and keeps the two
older "young carer" markers derived from it:

* ``wellbeing_flags`` "Young Carer" — re-derived by
  ``wellbeing.sync_vulnerable_flags`` after every write (unchanged).
* the 16-19 bursary **attendance exemption** with reason "Young carer"
  (``attendance_bursary_exemptions``). Ticking *Exempt from bursary
  attendance condition* on the record opens a matching exemption (or
  adopts an open hand-made one); ending the record or unticking it ends
  the exemption — never deletes it, so the protected periods stay on
  file. ``vg_young_carers.exemption_id`` remembers which exemption the
  record owns.

Added columns: the cared-for person's need, the impact of caring (level
and description), consent to share (with whom, when) and the exemption
link.

Access: PASTORAL + ``can_see_student``; every read and write goes to the
sensitive-access log (area ``vulnerable_groups``, as the wellbeing
young-carer screens do). :func:`teacher_notice` is the only thing meant
for staff without PASTORAL: it gives detail only when the learner
consented to sharing.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.systems.sixth_form.domain.pastoral import _people, _records
from education_system.systems.sixth_form.domain.pastoral.wellbeing import (
    wellbeing as _wb,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

AREA = "vulnerable_groups"
EXEMPTION_REASON = "Young carer"

CARED_FOR_NEEDS: tuple[str, ...] = (
    "Physical disability", "Long-term illness", "Mental health",
    "Substance misuse", "Learning disability", "Autism / neurodiversity",
    "Old age / frailty", "Terminal illness", "Sibling care",
    "Several needs", "Other",
)
IMPACT_LEVELS: tuple[str, ...] = ("Low", "Moderate", "High")

_EXTRA_COLUMNS: dict[str, str] = {
    "cared_for_need": "TEXT",
    "impact_level": "TEXT",
    "impact": "TEXT",
    "consent_to_share": "INTEGER NOT NULL DEFAULT 0",
    "consent_date": "TEXT",
    "share_with": "TEXT",
    "attendance_exemption": "INTEGER NOT NULL DEFAULT 0",
    "exemption_id": "INTEGER",
}


class ValidationError(ValueError):
    pass


@dataclass
class YoungCarer:
    carer_id: int
    student_id: str
    cares_for: str
    relationship: str | None
    cared_for_need: str | None
    care_tasks: str | None
    hours_per_week: int | None
    impact_level: str | None
    impact: str | None
    identified_on: str | None
    assessment_date: str | None
    support_provider: str | None
    support_plan: str | None
    consent_to_share: bool
    consent_date: str | None
    share_with: str | None
    attendance_exemption: bool
    last_reviewed: str | None
    next_review_due: str | None
    end_date: str | None
    notes: str | None
    exemption_id: int | None
    created_at: str | None
    updated_at: str | None

    @property
    def active(self) -> bool:
        return not self.end_date or self.end_date >= _records.today()

    @property
    def review_overdue(self) -> bool:
        return bool(self.active and self.next_review_due
                    and self.next_review_due < _records.today())


_C = _records.Col
_BASE = {c.name: c for c in _wb.YOUNG_CARER_SPEC.cols}

#: The wellbeing columns (same labels) plus this module's, in form order.
SPEC = _records.TableSpec(
    table="vg_young_carers", id_col="carer_id", row_type=YoungCarer,
    label="Young carer record",
    order_by="end_date IS NOT NULL, next_review_due IS NULL, "
             "next_review_due, student_id",
    cols=(
        _BASE["student_id"],
        _BASE["cares_for"],
        _BASE["relationship"],
        _C("cared_for_need", "Cared-for person's need", "choice",
           choices=CARED_FOR_NEEDS),
        _C("care_tasks", "Nature of caring (tasks)", "multiline",
           listed=False),
        _BASE["hours_per_week"],
        _C("impact_level", "Impact", "choice", choices=IMPACT_LEVELS),
        _C("impact", "Impact on study / attendance / wellbeing",
           "multiline", listed=False),
        _BASE["identified_on"],
        _BASE["assessment_date"],
        _BASE["support_provider"],
        _C("support_plan", "Support agreed", "multiline", listed=False),
        _C("consent_to_share", "Consent to share", "bool"),
        _C("consent_date", "Consent given on", "date", listed=False),
        _C("share_with", "May be shared with", listed=False),
        _C("attendance_exemption",
           "Exempt from bursary attendance condition", "bool"),
        _BASE["last_reviewed"],
        _BASE["next_review_due"],
        _BASE["end_date"],
        _BASE["notes"],
        _C("exemption_id", "Bursary exemption #", "int", hidden=True),
    ))


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    from education_system import paths
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(_wb.DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _wb.init_db()
    _ab().init_db()
    with _connect() as conn:
        _records.ensure_columns(conn, "vg_young_carers", _EXTRA_COLUMNS)
    _DB_READY = True


def _ab():
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_bursary as _a,
    )
    return _a


def _guard(action: str, student_id: str | None = None,
           ref: str | None = None) -> Any:
    return _records.guard("PASTORAL", AREA, action, student_id=student_id,
                          record_ref=ref)


def _rules(p: dict[str, Any]) -> None:
    if p["end_date"] and p["identified_on"] \
            and p["end_date"] < p["identified_on"]:
        raise ValidationError("End date cannot be before the date identified")
    if p["next_review_due"] and p["last_reviewed"] \
            and p["next_review_due"] <= p["last_reviewed"]:
        raise ValidationError("Next review must be after the last review")
    if p["consent_to_share"]:
        if not p["consent_date"]:
            p["consent_date"] = _records.today()
    else:
        p["consent_date"] = None
        p["share_with"] = None


def _fetch(carer_id: int) -> YoungCarer | None:
    with _connect() as conn:
        return _records.fetch(conn, SPEC, int(carer_id))


# ── Attendance-exemption sync ───────────────────────────────────────

def _owned_exemptions(conn: Any) -> set[int]:
    return {r[0] for r in conn.execute(
        "SELECT exemption_id FROM vg_young_carers "
        "WHERE exemption_id IS NOT NULL")}


def sync_exemption(carer_id: int) -> int | None:
    """Make the bursary attendance exemption match the record.

    Returns the exemption id the record owns afterwards (None if none).
    """
    init_db()
    rec = _fetch(carer_id)
    if rec is None:
        return None
    ab = _ab()
    today = _records.today()
    ex = ab.get_exemption(rec.exemption_id) if rec.exemption_id else None
    want = rec.attendance_exemption and rec.active
    new_id = ex.exemption_id if ex else None
    if want:
        desired_end = rec.end_date
        if ex is None:
            with _connect() as conn:
                owned = _owned_exemptions(conn)
            adopt = next((e for e in ab.list_exemptions(
                student_id=rec.student_id)
                if e.reason == EXEMPTION_REASON
                and e.exemption_id not in owned
                and (e.end_date is None or e.end_date >= today)), None)
            if adopt is not None:
                new_id = adopt.exemption_id
                if adopt.end_date != desired_end:
                    ab.set_exemption_end(new_id, desired_end)
            else:
                start = rec.identified_on if (
                    rec.identified_on and rec.identified_on <= today) \
                    else today
                new_id = ab.add_exemption(
                    rec.student_id, reason=EXEMPTION_REASON,
                    start_date=start, end_date=desired_end,
                    detail=f"Young carer support record #{rec.carer_id}",
                    granted_by=_records.current_username()).exemption_id
        elif ex.end_date != desired_end:
            ab.set_exemption_end(ex.exemption_id, desired_end)
    elif ex is not None and (ex.end_date is None or ex.end_date > today):
        end = rec.end_date if (rec.end_date and rec.end_date < today) \
            else today
        ab.set_exemption_end(ex.exemption_id, end)
    if new_id != rec.exemption_id:
        with _connect() as conn:
            conn.execute("UPDATE vg_young_carers SET exemption_id = ? "
                         "WHERE carer_id = ?", (new_id, rec.carer_id))
    return new_id


def _after_write(rec: YoungCarer) -> None:
    _wb.sync_vulnerable_flags(rec.student_id)
    sync_exemption(rec.carer_id)


# ── CRUD ────────────────────────────────────────────────────────────

def create_young_carer(data: dict[str, Any]) -> YoungCarer:
    init_db()
    p = _records.validate(SPEC, data, error=ValidationError,
                          student_exists=_people.student_exists)
    p["exemption_id"] = None
    _rules(p)
    _guard("create young carer record", p["student_id"])
    with _connect() as conn:
        new_id = _records.insert(conn, SPEC, p)
    logger.info("Young carer record #%d for %s", new_id, p["student_id"])
    rec = _fetch(new_id)
    _after_write(rec)
    return _fetch(new_id)


def get_young_carer(carer_id: int) -> YoungCarer | None:
    init_db()
    rec = _fetch(carer_id)
    if rec is not None:
        _guard("view young carer record", rec.student_id,
               f"vg_carer:{carer_id}")
    return rec


def list_young_carers(*, student_id: str | None = None,
                      active_only: bool = False,
                      review_overdue_only: bool = False,
                      no_consent_only: bool = False) -> list[YoungCarer]:
    init_db()
    _guard("list young carers", student_id)
    where, args = [], []
    if active_only or review_overdue_only:
        where.append("(end_date IS NULL OR end_date >= ?)")
        args.append(_records.today())
    if review_overdue_only:
        where.append("next_review_due IS NOT NULL AND next_review_due < ?")
        args.append(_records.today())
    if no_consent_only:
        where.append("COALESCE(consent_to_share, 0) = 0")
    with _connect() as conn:
        rows = _records.select(conn, SPEC, equals={"student_id": student_id},
                               where=where, args=args)
    return _records.visible_filter("PASTORAL", rows)


def update_young_carer(carer_id: int, data: dict[str, Any]) -> YoungCarer:
    init_db()
    existing = _fetch(carer_id)
    if existing is None:
        raise ValidationError(f"No young carer record #{carer_id}")
    data = {k: v for k, v in data.items() if k != "exemption_id"}
    p = _records.validate(SPEC, data, error=ValidationError,
                          existing=existing,
                          student_exists=_people.student_exists)
    _rules(p)
    _guard("update young carer record", existing.student_id,
           f"vg_carer:{carer_id}")
    with _connect() as conn:
        _records.update(conn, SPEC, carer_id, p)
    _after_write(existing)
    return _fetch(carer_id)


def review_young_carer(carer_id: int, *, reviewed_on: str | None = None,
                       next_review_due: str | None = None,
                       notes: str | None = None) -> YoungCarer:
    """Record a support review (the wellbeing store stamps the dates and
    appends a dated note), then re-sync the exemption."""
    init_db()
    _wb.review_young_carer(carer_id, reviewed_on=reviewed_on,
                           next_review_due=next_review_due, notes=notes)
    sync_exemption(carer_id)
    return get_young_carer(carer_id)


def end_young_carer(carer_id: int, *, on: str | None = None,
                    reason: str | None = None) -> YoungCarer:
    """No longer a young carer: end the record (flag and exemption end
    with it) and note why."""
    rec = get_young_carer(carer_id)
    if rec is None:
        raise ValidationError(f"No young carer record #{carer_id}")
    day = _records.check_date(on, "End date",
                              ValidationError) or _records.today()
    payload: dict[str, Any] = {"end_date": day}
    if reason and reason.strip():
        line = f"[{day} ended] {reason.strip()}"
        payload["notes"] = f"{rec.notes}\n{line}" if rec.notes else line
    return update_young_carer(carer_id, payload)


def delete_young_carer(carer_id: int) -> bool:
    """Delete a record entered by mistake. Its exemption is ended (not
    deleted) first so the bursary history stays."""
    init_db()
    rec = _fetch(carer_id)
    if rec is None:
        return False
    _guard("delete young carer record", rec.student_id,
           f"vg_carer:{carer_id}")
    if rec.exemption_id:
        ex = _ab().get_exemption(rec.exemption_id)
        if ex is not None and (ex.end_date is None
                               or ex.end_date > _records.today()):
            _ab().set_exemption_end(ex.exemption_id, _records.today())
    with _connect() as conn:
        ok = _records.delete(conn, SPEC, carer_id)
    _wb.sync_vulnerable_flags(rec.student_id)
    return ok


def sync_all() -> tuple[int, int]:
    """Re-derive every flag and exemption. Returns (flag changes,
    records checked)."""
    init_db()
    _guard("sync young carer flags and exemptions")
    n_flags = _wb.sync_vulnerable_flags()
    with _connect() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT carer_id FROM vg_young_carers")]
    for cid in ids:
        sync_exemption(cid)
    return n_flags, len(ids)


# ── Reports ─────────────────────────────────────────────────────────

@dataclass
class UnlinkedExemption:
    exemption_id: int
    student_id: str
    student_name: str
    start_date: str
    end_date: str | None
    detail: str | None


def exemptions_without_record() -> list[UnlinkedExemption]:
    """Open "Young carer" bursary exemptions no support record owns —
    learners recognised as young carers with nothing written down."""
    init_db()
    _guard("view young carer exemptions without a record")
    with _connect() as conn:
        owned = _owned_exemptions(conn)
    names = _people.student_names()
    today = _records.today()
    out = [UnlinkedExemption(e.exemption_id, e.student_id,
                             names.get(e.student_id, "(unknown)"),
                             e.start_date, e.end_date, e.detail)
           for e in _ab().list_exemptions()
           if e.reason == EXEMPTION_REASON and e.exemption_id not in owned
           and (e.end_date is None or e.end_date >= today)]
    return _records.visible_filter("PASTORAL", out)


@dataclass
class CarerSummary:
    active: int = 0
    reviews_overdue: int = 0
    reviews_due_30: int = 0
    no_consent: int = 0
    exempt: int = 0
    no_assessment: int = 0
    by_impact: dict[str, int] = field(default_factory=dict)
    by_need: dict[str, int] = field(default_factory=dict)
    hours_total: int = 0
    unlinked_exemptions: int = 0


def summary() -> CarerSummary:
    import datetime as _dt
    rows = list_young_carers(active_only=True)
    soon = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
    s = CarerSummary(active=len(rows))
    for r in rows:
        s.reviews_overdue += r.review_overdue
        if r.next_review_due and not r.review_overdue \
                and r.next_review_due <= soon:
            s.reviews_due_30 += 1
        s.no_consent += not r.consent_to_share
        s.exempt += bool(r.attendance_exemption)
        s.no_assessment += not r.assessment_date
        k = r.impact_level or "Not assessed"
        s.by_impact[k] = s.by_impact.get(k, 0) + 1
        n = r.cared_for_need or "Not recorded"
        s.by_need[n] = s.by_need.get(n, 0) + 1
        s.hours_total += r.hours_per_week or 0
    s.unlinked_exemptions = len(exemptions_without_record())
    return s


def teacher_notice(student_id: str) -> str | None:
    """A line other screens may show teaching staff, or None.

    Detail only with the learner's consent to share; otherwise just that
    pastoral support is in place. No PASTORAL needed, but the read is
    still logged.
    """
    init_db()
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    with _connect() as conn:
        rows = _records.select(
            conn, SPEC, equals={"student_id": student_id},
            where=["(end_date IS NULL OR end_date >= ?)"],
            args=[_records.today()])
    if not rows:
        return None
    access.log_sensitive_access(access.current(), AREA,
                                "view young carer teacher notice",
                                student_id=student_id)
    shared = [r for r in rows if r.consent_to_share]
    if not shared:
        return ("Pastoral support is in place — speak to the pastoral "
                "team before acting on attendance or deadlines.")
    r = shared[0]
    bits = [f"Young carer (cares for {r.cares_for})"]
    if r.support_plan:
        bits.append(f"support agreed: {r.support_plan}".replace("\n", "; "))
    return " — ".join(bits)

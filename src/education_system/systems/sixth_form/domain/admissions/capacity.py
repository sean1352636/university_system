"""Places per programme, oversubscription criteria and feeder schools.

* **Places** — how many learners each programme (qualification type +
  subject, as in ``admissions_programme_choices``) can take in a cycle.
  A place is held by an applicant in that cycle who chose the programme
  and is at Offer Made, Offer Accepted, Deferred (into this cycle) or
  Enrolled. A programme with no places set is unlimited.
* **Oversubscription criteria** — the order in which competing
  applicants are ranked when a programme is oversubscribed. Stored in
  the database so admissions can reorder or switch them off; the
  submission date always breaks ties last. Home-to-college distance is
  listed but cannot be applied (no distance is recorded) and is off.
* **Feeder schools** — partner schools, and the guaranteed-place scheme
  some of them are in: :func:`apply_feeder_rules` sets an applicant's
  *guaranteed place* flag when their previous school is in the scheme.

``admissions.make_offer`` calls :func:`check_offer_capacity` and raises
:class:`CapacityFull` unless the person overrides it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

#: Statuses that hold a place in a programme.
HOLDING_STATUSES: tuple[str, ...] = ("Offer Made", "Offer Accepted",
                                     "Deferred", "Enrolled")
#: Statuses still competing for a place (ranked when oversubscribed).
COMPETING_STATUSES: tuple[str, ...] = ("Submitted", "Under Review",
                                       "Interview Scheduled", "Interviewed",
                                       "Waitlisted")


class CapacityFull(ValidationError):
    """An offer would go over the places set for a programme."""

    def __init__(self, applicant_id: str, programmes: list[str]):
        self.applicant_id = applicant_id
        self.programmes = list(programmes)
        super().__init__(
            f"No places left on {', '.join(programmes)} for {applicant_id}. "
            "Waitlist the applicant, or override capacity to offer anyway.")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_programme_places (
    cycle               TEXT NOT NULL,
    qualification_type  TEXT NOT NULL COLLATE NOCASE,
    subject             TEXT NOT NULL COLLATE NOCASE,
    places              INTEGER NOT NULL,
    notes               TEXT,
    updated_by          TEXT,
    updated_at          TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (cycle, qualification_type, subject)
);

CREATE TABLE IF NOT EXISTS admissions_oversubscription_criteria (
    key          TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    priority     INTEGER NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    updated_by   TEXT,
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admissions_feeder_schools (
    school_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name                     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    urn                      TEXT,
    partner                  INTEGER NOT NULL DEFAULT 0,
    guaranteed_place_scheme  INTEGER NOT NULL DEFAULT 0,
    active                   INTEGER NOT NULL DEFAULT 1,
    notes                    TEXT,
    created_at               TEXT DEFAULT (datetime('now'))
);
"""

#: The criteria and their default order (the college's admissions
#: policy may differ: change it with :func:`set_criteria_order`).
DEFAULT_CRITERIA: tuple[tuple[str, str, bool, str | None], ...] = (
    ("ehcp", "EHCP naming the college", True, None),
    ("looked_after", "Looked after / previously looked after", True, None),
    ("care_leaver", "Care leaver", True, None),
    ("feeder_school", "Feeder / partner school", True, None),
    ("guaranteed_place", "Guaranteed place scheme", True, None),
    ("young_carer", "Young carer", True, None),
    ("distance", "Home-to-college distance", False,
     "Not available: no home-to-college distance is recorded."),
)
_UNAVAILABLE = {"distance"}

_READY = False


def init_db() -> None:
    global _READY
    if _READY:
        return
    _adm.init_db()
    with _adm._connect() as conn:
        conn.executescript(_SCHEMA)
        for i, (key, label, enabled, notes) in enumerate(DEFAULT_CRITERIA):
            conn.execute(
                "INSERT OR IGNORE INTO admissions_oversubscription_criteria "
                "(key, label, priority, enabled, notes) VALUES (?,?,?,?,?)",
                (key, label, i + 1, int(enabled), notes))
        conn.commit()
    _READY = True


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().split())


def programme_label(qualification_type: str, subject: str) -> str:
    return f"{qualification_type} {subject}"


def _split(programme: Any) -> tuple[str, str]:
    """(qualification_type, subject) from a tuple, a ProgrammeChoice or a
    ``"Type: Subject"`` string."""
    if isinstance(programme, (tuple, list)) and len(programme) >= 2:
        q, s = programme[0], programme[1]
    elif hasattr(programme, "qualification_type"):
        q, s = programme.qualification_type, programme.subject
    elif isinstance(programme, str) and ":" in programme:
        q, s = programme.split(":", 1)
    else:
        raise ValidationError(
            "Give the programme as (qualification type, subject)")
    q, s = str(q or "").strip(), str(s or "").strip()
    if not q or not s:
        raise ValidationError("Qualification type and subject are required")
    return q, s


# ── Places ─────────────────────────────────────────────────────────

@dataclass
class ProgrammePlaces:
    cycle: str
    qualification_type: str
    subject: str
    places: int | None          # None = no limit set
    held: int
    competing: int
    notes: str | None = None

    @property
    def label(self) -> str:
        return programme_label(self.qualification_type, self.subject)

    @property
    def places_left(self) -> int | None:
        return None if self.places is None else max(self.places - self.held, 0)

    @property
    def is_full(self) -> bool:
        return self.places is not None and self.held >= self.places

    @property
    def oversubscribed(self) -> bool:
        return (self.places is not None
                and self.held + self.competing > self.places)


def set_places(cycle: str, programme: Any, places: int | None, *,
               notes: str | None = None) -> None:
    """Set (or with ``places=None`` remove) the limit for a programme."""
    from education_system.systems.sixth_form.domain.admissions import cycles
    init_db()
    _guard.require("setting programme places")
    cycle = cycles.validate_cycle_name(cycle)
    q, s = _split(programme)
    with _adm._connect() as conn:
        if places is None:
            conn.execute(
                "DELETE FROM admissions_programme_places WHERE cycle = ? AND "
                "qualification_type = ? AND subject = ?", (cycle, q, s))
        else:
            try:
                n = int(places)
            except (TypeError, ValueError):
                raise ValidationError("Places must be a whole number") from None
            if n < 0:
                raise ValidationError("Places cannot be negative")
            conn.execute(
                "INSERT INTO admissions_programme_places (cycle, "
                "qualification_type, subject, places, notes, updated_by) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(cycle, qualification_type, "
                "subject) DO UPDATE SET places = excluded.places, "
                "notes = excluded.notes, updated_by = excluded.updated_by, "
                "updated_at = datetime('now')",
                (cycle, q, s, n, (notes or "").strip() or None,
                 _guard.actor()))
        conn.commit()
    logger.info("Places for %s %s in %s set to %s by %s", q, s, cycle, places,
                _guard.actor())


def _places_map(cycle: str) -> dict[tuple[str, str], tuple[int, str | None, str, str]]:
    with _adm._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admissions_programme_places WHERE cycle = ?",
            (cycle,)).fetchall()
    return {(_norm(r["qualification_type"]), _norm(r["subject"])):
            (r["places"], r["notes"], r["qualification_type"], r["subject"])
            for r in rows}


def _cycle_choices(cycle: str) -> list[tuple[Any, list[tuple[str, str]]]]:
    """(applicant row, [(type, subject)…]) for every live application in
    *cycle*. Applicants with no stored choices count their subject slots
    as A levels, as ``list_programme_choices`` does."""
    with _adm._connect() as conn:
        apps = conn.execute(
            "SELECT * FROM admissions_applicants WHERE intake_year = ? AND "
            "archived_at IS NULL", (cycle,)).fetchall()
        rows = conn.execute(
            "SELECT c.applicant_id, c.qualification_type, c.subject "
            "FROM admissions_programme_choices c JOIN admissions_applicants a "
            "ON a.applicant_id = c.applicant_id WHERE a.intake_year = ? "
            "ORDER BY c.sort_order, c.id", (cycle,)).fetchall()
    stored: dict[str, list[tuple[str, str]]] = {}
    for r in rows:
        stored.setdefault(r["applicant_id"], []).append(
            (r["qualification_type"], r["subject"]))
    out = []
    for a in apps:
        ch = stored.get(a["applicant_id"])
        if ch is None:
            ch = [("A Level", s) for s in (a["subject_1"], a["subject_2"],
                                           a["subject_3"]) if s]
        out.append((a, ch))
    return out


def programme_places(cycle: str, *, only_limited: bool = False
                     ) -> list[ProgrammePlaces]:
    """Places, places held and applicants still competing for every
    programme chosen (or limited) in *cycle*."""
    from education_system.systems.sixth_form.domain.admissions import cycles
    init_db()
    _require_read("programme places")
    cycle = cycles.validate_cycle_name(cycle)
    limits = _places_map(cycle)
    stats: dict[tuple[str, str], list[Any]] = {}
    for key, (n, notes, q, s) in limits.items():
        stats[key] = [q, s, 0, 0]
    for a, choices in _cycle_choices(cycle):
        for q, s in choices:
            key = (_norm(q), _norm(s))
            st = stats.setdefault(key, [q, s, 0, 0])
            if a["status"] in HOLDING_STATUSES:
                st[2] += 1
            elif a["status"] in COMPETING_STATUSES:
                st[3] += 1
    out = []
    for key, (q, s, held, competing) in stats.items():
        lim = limits.get(key)
        if only_limited and lim is None:
            continue
        out.append(ProgrammePlaces(
            cycle=cycle, qualification_type=q, subject=s,
            places=lim[0] if lim else None, held=held, competing=competing,
            notes=lim[1] if lim else None))
    out.sort(key=lambda p: (p.qualification_type.lower(), p.subject.lower()))
    return out


def get_programme_places(cycle: str, programme: Any) -> ProgrammePlaces:
    q, s = _split(programme)
    for p in programme_places(cycle):
        if _norm(p.qualification_type) == _norm(q) and _norm(p.subject) == _norm(s):
            return p
    return ProgrammePlaces(cycle=cycle, qualification_type=q, subject=s,
                           places=None, held=0, competing=0)


def places_left(cycle: str, programme: Any) -> int | None:
    """Places left on a programme in *cycle* (None = no limit set)."""
    return get_programme_places(cycle, programme).places_left


def check_offer_capacity(applicant_id: str) -> list[str]:
    """Programmes the applicant chose that have no place left for them in
    their cycle. A place the applicant already holds counts as theirs."""
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if not a.intake_year:
        return []
    init_db()
    limits = _places_map(a.intake_year)
    if not limits:
        return []
    held: dict[tuple[str, str], int] = {}
    for other, choices in _cycle_choices(a.intake_year):
        # The applicant's own place (a re-offer) never counts against them.
        if (other["status"] not in HOLDING_STATUSES
                or other["applicant_id"] == a.applicant_id):
            continue
        for q, s in choices:
            key = (_norm(q), _norm(s))
            held[key] = held.get(key, 0) + 1
    full = []
    for c in _adm.list_programme_choices(applicant_id):
        key = (_norm(c.qualification_type), _norm(c.subject))
        lim = limits.get(key)
        if lim is not None and held.get(key, 0) >= lim[0]:
            full.append(programme_label(c.qualification_type, c.subject))
    return full


def waitlist_if_full(applicant_id: str, *, notes: str | None = None
                     ) -> list[str]:
    """Put the applicant on the waitlist when a programme they chose is
    full (ranked at the end). Returns the full programmes (empty = there
    is room, nothing changed)."""
    full = check_offer_capacity(applicant_id)
    if not full:
        return []
    a = _adm.get_applicant(applicant_id)
    assert a is not None
    if a.status != "Waitlisted":
        _adm.record_decision(
            applicant_id, "Waitlisted", reason="Capacity reached",
            notes=notes or f"Full: {', '.join(full)}")
        last = max((w.waitlist_rank or 0 for w in _adm.get_waitlist()),
                   default=0)
        _adm.set_waitlist_rank(applicant_id, last + 1)
    return full


# ── Oversubscription criteria ──────────────────────────────────────

@dataclass
class Criterion:
    key: str
    label: str
    priority: int
    enabled: bool
    notes: str | None
    available: bool = True


def _require_read(what: str) -> None:
    _guard.require_any((_access().ADMISSIONS, _access().REPORTS), what)


def list_criteria() -> list[Criterion]:
    init_db()
    _require_read("oversubscription criteria")
    with _adm._connect() as conn:
        rows = conn.execute("SELECT * FROM admissions_oversubscription_criteria "
                            "ORDER BY priority, key").fetchall()
    return [Criterion(key=r["key"], label=r["label"], priority=r["priority"],
                      enabled=bool(r["enabled"]), notes=r["notes"],
                      available=r["key"] not in _UNAVAILABLE) for r in rows]


def set_criteria_order(keys: Iterable[str]) -> list[Criterion]:
    """Reorder the criteria (highest priority first). Keys left out keep
    their relative order after the ones given."""
    init_db()
    _guard.require("changing oversubscription criteria")
    keys = list(keys)
    current = [c.key for c in list_criteria()]
    unknown = set(keys) - set(current)
    if unknown:
        raise ValidationError(f"Unknown criteria: {', '.join(sorted(unknown))}")
    order = keys + [k for k in current if k not in keys]
    with _adm._connect() as conn:
        for i, k in enumerate(order, start=1):
            conn.execute("UPDATE admissions_oversubscription_criteria SET "
                         "priority = ?, updated_by = ?, updated_at = "
                         "datetime('now') WHERE key = ?",
                         (i, _guard.actor(), k))
        conn.commit()
    return list_criteria()


def set_criterion_enabled(key: str, enabled: bool) -> Criterion:
    init_db()
    _guard.require("changing oversubscription criteria")
    if enabled and key in _UNAVAILABLE:
        raise ValidationError("That criterion cannot be applied: the data it "
                              "needs is not recorded.")
    with _adm._connect() as conn:
        cur = conn.execute(
            "UPDATE admissions_oversubscription_criteria SET enabled = ?, "
            "updated_by = ?, updated_at = datetime('now') WHERE key = ?",
            (int(bool(enabled)), _guard.actor(), key))
        conn.commit()
    if not cur.rowcount:
        raise ValidationError(f"Unknown criterion {key!r}")
    return next(c for c in list_criteria() if c.key == key)


def _predicates(feeders: set[str]) -> dict[str, Callable[[Any], bool]]:
    return {
        "ehcp": lambda a: bool(a["ehcp"]),
        "looked_after": lambda a: bool(a["looked_after"]),
        "care_leaver": lambda a: bool(a["care_leaver"]),
        "feeder_school": lambda a: _norm(a["previous_school"]) in feeders,
        "guaranteed_place": lambda a: bool(a["guaranteed_place"]),
        "young_carer": lambda a: bool(a["young_carer"]),
    }


@dataclass
class RankedApplicant:
    position: int
    applicant_id: str
    name: str
    status: str
    submitted_at: str
    previous_school: str | None
    criteria_met: list[str] = field(default_factory=list)
    holds_place: bool = False

    @property
    def reasons(self) -> str:
        met = ", ".join(self.criteria_met) or "no priority criteria"
        return f"{met}; submitted {self.submitted_at}"


def rank_applicants(cycle: str, programme: Any, *,
                    include_holders: bool = False) -> list[RankedApplicant]:
    """Applicants in *cycle* who chose *programme*, in oversubscription
    order: enabled criteria by priority, then submission date. Those
    already holding a place are left out unless ``include_holders``
    (then they come first, as their place is not re-decided)."""
    from education_system.systems.sixth_form.domain.admissions import cycles
    init_db()
    _guard.require("ranking applicants")
    cycle = cycles.validate_cycle_name(cycle)
    q, s = _split(programme)
    crit = [c for c in list_criteria() if c.enabled and c.available]
    preds = _predicates({_norm(f.name) for f in list_feeder_schools()})
    rows = []
    for a, choices in _cycle_choices(cycle):
        if not any(_norm(cq) == _norm(q) and _norm(cs) == _norm(s)
                   for cq, cs in choices):
            continue
        holds = a["status"] in HOLDING_STATUSES
        if holds and not include_holders:
            continue
        if not holds and a["status"] not in COMPETING_STATUSES:
            continue
        met = [c.label for c in crit if preds[c.key](a)]
        key = ((0 if holds else 1),
               tuple(0 if preds[c.key](a) else 1 for c in crit),
               a["submitted_at"] or "", a["applicant_id"])
        rows.append((key, a, met, holds))
    rows.sort(key=lambda t: t[0])
    return [RankedApplicant(
        position=i, applicant_id=a["applicant_id"],
        name=f"{a['first_name']} {a['last_name']}".strip(),
        status=a["status"], submitted_at=a["submitted_at"],
        previous_school=a["previous_school"], criteria_met=met,
        holds_place=holds) for i, (_k, a, met, holds) in enumerate(rows, 1)]


# ── Feeder schools ─────────────────────────────────────────────────

@dataclass
class FeederSchool:
    school_id: int
    name: str
    urn: str | None
    partner: bool
    guaranteed_place_scheme: bool
    active: bool
    notes: str | None
    created_at: str | None = None


def _feeder(r: Any) -> FeederSchool:
    d = {k: r[k] for k in r.keys()}
    for k in ("partner", "guaranteed_place_scheme", "active"):
        d[k] = bool(d[k])
    return FeederSchool(**d)


def list_feeder_schools(*, include_inactive: bool = False
                        ) -> list[FeederSchool]:
    init_db()
    _require_read("feeder schools")
    sql = "SELECT * FROM admissions_feeder_schools"
    if not include_inactive:
        sql += " WHERE active = 1"
    with _adm._connect() as conn:
        return [_feeder(r) for r in conn.execute(sql + " ORDER BY name")]


def get_feeder_school(school_id: int) -> FeederSchool | None:
    init_db()
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_feeder_schools WHERE "
                         "school_id = ?", (school_id,)).fetchone()
    return _feeder(r) if r else None


def find_feeder_school(name: str | None) -> FeederSchool | None:
    n = _norm(name)
    if not n:
        return None
    return next((f for f in list_feeder_schools() if _norm(f.name) == n), None)


def add_feeder_school(name: str, *, partner: bool = True,
                      guaranteed_place_scheme: bool = False,
                      urn: str | None = None,
                      notes: str | None = None) -> FeederSchool:
    init_db()
    _guard.require("changing feeder schools")
    name = " ".join((name or "").split())
    if not name:
        raise ValidationError("School name is required")
    if len(name) > 160:
        raise ValidationError("School name is too long")
    with _adm._connect() as conn:
        if conn.execute("SELECT 1 FROM admissions_feeder_schools WHERE "
                        "name = ?", (name,)).fetchone():
            raise ValidationError(f"{name} is already a feeder school")
        cur = conn.execute(
            "INSERT INTO admissions_feeder_schools (name, urn, partner, "
            "guaranteed_place_scheme, notes) VALUES (?,?,?,?,?)",
            (name, (urn or "").strip() or None, int(bool(partner)),
             int(bool(guaranteed_place_scheme)), (notes or "").strip() or None))
        conn.commit()
        sid = cur.lastrowid
    out = get_feeder_school(sid)
    assert out is not None
    return out


def update_feeder_school(school_id: int, **fields: Any) -> FeederSchool:
    init_db()
    _guard.require("changing feeder schools")
    allowed = {"name", "urn", "partner", "guaranteed_place_scheme", "active",
               "notes"}
    bad = set(fields) - allowed
    if bad:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(bad))}")
    if get_feeder_school(school_id) is None:
        raise ValidationError(f"No feeder school #{school_id}")
    clean: dict[str, Any] = {}
    for k, v in fields.items():
        if k in ("partner", "guaranteed_place_scheme", "active"):
            clean[k] = int(bool(v))
        elif k == "name":
            v = " ".join(str(v or "").split())
            if not v:
                raise ValidationError("School name is required")
            clean[k] = v
        else:
            clean[k] = (str(v).strip() or None) if v is not None else None
    if clean:
        sets = ", ".join(f"{k} = ?" for k in clean)
        with _adm._connect() as conn:
            conn.execute(f"UPDATE admissions_feeder_schools SET {sets} "  # noqa: S608 — keys checked
                         "WHERE school_id = ?", (*clean.values(), school_id))
            conn.commit()
    out = get_feeder_school(school_id)
    assert out is not None
    return out


def remove_feeder_school(school_id: int) -> bool:
    """Mark a feeder school inactive (applicants' history keeps the name)."""
    init_db()
    _guard.require("changing feeder schools")
    with _adm._connect() as conn:
        cur = conn.execute("UPDATE admissions_feeder_schools SET active = 0 "
                           "WHERE school_id = ?", (school_id,))
        conn.commit()
    return cur.rowcount > 0


def apply_feeder_rules(applicant_id: str) -> bool:
    """Set the applicant's guaranteed-place flag when their previous
    school is an active feeder in the guaranteed-place scheme. Returns
    whether the applicant has a guaranteed place afterwards. Never clears
    a flag set by hand."""
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details,
    )
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.guaranteed_place:
        return True
    school = find_feeder_school(a.previous_school)
    if school is None or not school.guaranteed_place_scheme or a.is_archived:
        return False
    applicant_details.update_profile(applicant_id, guaranteed_place=True)
    with _adm._connect() as conn:
        _adm._log_event(conn, applicant_id,
                        f"Guaranteed place: {school.name} is in the "
                        "guaranteed-place scheme", kind="update")
        conn.commit()
    return True


def apply_feeder_rules_all(cycle: str) -> list[str]:
    """:func:`apply_feeder_rules` for every open application in *cycle*;
    returns the applicants given a guaranteed place."""
    from education_system.systems.sixth_form.domain.admissions import cycles
    out = []
    for a in cycles.applications_in_cycle(cycle):
        if a.is_open and not a.guaranteed_place and apply_feeder_rules(
                a.applicant_id):
            out.append(a.applicant_id)
    return out


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access

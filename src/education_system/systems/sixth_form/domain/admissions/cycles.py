"""Admissions cycles: one recruitment round per September intake.

A cycle (``"2027/28"``) is the intake year applications are for. It
records when applications open and close, the interview window, how long
an applicant has to answer an offer, GCSE results day and when enrolment
starts. Its status runs Planned → Open → Closed → Archived; only an Open
cycle takes new applications (:func:`open_cycle_for` is what
``admissions.default_intake_year`` asks first).

One application per learner per cycle: a learner who applies again for a
later intake gets a *new* application linked back by ``reapplied_from``
(:func:`reapply`), so each cycle's decisions stay separate.

Offer housekeeping used by the scheduled jobs also lives here: lapsing
offers nobody answered (:func:`lapse_expired_offers`) and the list of
offers due an expiry warning (:func:`offers_needing_warning`).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

CYCLE_STATUSES: tuple[str, ...] = ("Planned", "Open", "Closed", "Archived")
DEFAULT_OFFER_RESPONSE_DAYS: int = 14
#: Days before an offer's expiry that the applicant is warned.
WARNING_DAYS: int = 3
LAPSE_REASON: str = "No response from applicant"
#: Closed statuses a learner may re-apply from (Waitlisted is withdrawn
#: first, with the new cycle on the timeline).
REAPPLY_FROM: tuple[str, ...] = ("Offer Declined", "Rejected", "Withdrawn",
                                 "Waitlisted")

_CYCLE_RE = re.compile(r"^(\d{4})/(\d{2})$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_cycles (
    cycle                TEXT PRIMARY KEY,
    opens_on             TEXT NOT NULL,
    closes_on            TEXT NOT NULL,
    interview_from       TEXT,
    interview_to         TEXT,
    offer_response_days  INTEGER NOT NULL DEFAULT 14,
    results_day          TEXT,
    enrolment_start      TEXT,
    status               TEXT NOT NULL DEFAULT 'Planned',
    notes                TEXT,
    created_by           TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now'))
);

-- One row per expiry warning sent, so the daily job warns once per offer.
CREATE TABLE IF NOT EXISTS admissions_offer_warnings (
    applicant_id   TEXT NOT NULL,
    offer_expiry   TEXT NOT NULL,
    sent_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (applicant_id, offer_expiry),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
"""

_READY = False


def init_db() -> None:
    global _READY
    if _READY:
        return
    _adm.init_db()
    with _adm._connect() as conn:
        conn.executescript(_SCHEMA)
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(admissions_applicants)").fetchall()}
        if "reapplied_from" not in cols:
            conn.execute("ALTER TABLE admissions_applicants "
                         "ADD COLUMN reapplied_from TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_adm_reapplied "
                     "ON admissions_applicants(reapplied_from)")
        conn.commit()
    _READY = True


# ── Cycle records ──────────────────────────────────────────────────

@dataclass
class Cycle:
    cycle: str
    opens_on: str
    closes_on: str
    interview_from: str | None
    interview_to: str | None
    offer_response_days: int
    results_day: str | None
    enrolment_start: str | None
    status: str
    notes: str | None
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status == "Open"

    def contains(self, day: _dt.date) -> bool:
        return self.opens_on <= day.isoformat() <= self.closes_on


def _cycle(r: Any) -> Cycle:
    return Cycle(**{k: r[k] for k in r.keys()})


def validate_cycle_name(cycle: Any) -> str:
    c = str(cycle or "").strip()
    m = _CYCLE_RE.match(c)
    if not m or int(m.group(2)) != (int(m.group(1)) + 1) % 100:
        raise ValidationError("Cycle must look like '2027/28'")
    return c


def _date(value: Any, label: str, *, required: bool = False) -> str | None:
    v = str(value or "").strip()
    if not v:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        return _dt.date.fromisoformat(v[:10]).isoformat()
    except ValueError:
        raise ValidationError(f"{label} must be a date (YYYY-MM-DD)") from None


_FIELDS = ("opens_on", "closes_on", "interview_from", "interview_to",
           "offer_response_days", "results_day", "enrolment_start", "notes")


def _clean(fields: dict[str, Any], existing: Cycle | None) -> dict[str, Any]:
    unknown = set(fields) - set(_FIELDS)
    if unknown:
        raise ValidationError(f"Unknown cycle field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(existing, k) for k in _FIELDS} if existing else {
        k: None for k in _FIELDS}
    merged.update(fields)
    out: dict[str, Any] = {
        "opens_on": _date(merged["opens_on"], "Applications open", required=True),
        "closes_on": _date(merged["closes_on"], "Applications close",
                           required=True),
        "interview_from": _date(merged["interview_from"], "Interviews from"),
        "interview_to": _date(merged["interview_to"], "Interviews to"),
        "results_day": _date(merged["results_day"], "Results day"),
        "enrolment_start": _date(merged["enrolment_start"], "Enrolment starts"),
        "notes": (str(merged["notes"]).strip() or None)
        if merged["notes"] is not None else None,
    }
    days = merged["offer_response_days"]
    try:
        days = DEFAULT_OFFER_RESPONSE_DAYS if days in (None, "") else int(days)
    except (TypeError, ValueError):
        raise ValidationError("Offer response days must be a number") from None
    if not 1 <= days <= 120:
        raise ValidationError("Offer response days must be between 1 and 120")
    out["offer_response_days"] = days
    if out["closes_on"] < out["opens_on"]:
        raise ValidationError("Applications must close after they open")
    if (out["interview_from"] and out["interview_to"]
            and out["interview_to"] < out["interview_from"]):
        raise ValidationError("The interview window ends before it starts")
    return out


def _check_overlap(cycle: str, opens_on: str, closes_on: str) -> None:
    """Two Open cycles may not take applications on the same day, or
    :func:`open_cycle_for` could not tell which intake a form is for."""
    with _adm._connect() as conn:
        clash = conn.execute(
            "SELECT cycle FROM admissions_cycles WHERE status = 'Open' AND "
            "cycle <> ? AND opens_on <= ? AND closes_on >= ?",
            (cycle, closes_on, opens_on)).fetchone()
    if clash:
        raise ValidationError(
            f"Applications for {clash['cycle']} are open over the same "
            "dates; close it or change the dates first.")


def get_cycle(cycle: str) -> Cycle | None:
    init_db()
    with _adm._connect() as conn:
        r = conn.execute("SELECT * FROM admissions_cycles WHERE cycle = ?",
                         ((cycle or "").strip(),)).fetchone()
    return _cycle(r) if r else None


def list_cycles(*, include_archived: bool = True) -> list[Cycle]:
    init_db()
    sql = "SELECT * FROM admissions_cycles"
    if not include_archived:
        sql += " WHERE status <> 'Archived'"
    with _adm._connect() as conn:
        return [_cycle(r) for r in conn.execute(
            sql + " ORDER BY cycle DESC").fetchall()]


def create_cycle(cycle: str, **fields: Any) -> Cycle:
    """Set up a cycle (status Planned). ``fields``: opens_on, closes_on
    (required), interview_from, interview_to, offer_response_days,
    results_day, enrolment_start, notes."""
    init_db()
    _guard.require("setting up admissions cycles")
    name = validate_cycle_name(cycle)
    if get_cycle(name):
        raise ValidationError(f"Cycle {name} already exists")
    v = _clean(fields, None)
    with _adm._connect() as conn:
        conn.execute(
            "INSERT INTO admissions_cycles (cycle, opens_on, closes_on, "
            "interview_from, interview_to, offer_response_days, results_day, "
            "enrolment_start, notes, created_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (name, v["opens_on"], v["closes_on"], v["interview_from"],
             v["interview_to"], v["offer_response_days"], v["results_day"],
             v["enrolment_start"], v["notes"], _guard.actor()))
        conn.commit()
    logger.info("Admissions cycle %s created by %s", name, _guard.actor())
    out = get_cycle(name)
    assert out is not None
    return out


def update_cycle(cycle: str, **fields: Any) -> Cycle:
    init_db()
    _guard.require("changing admissions cycles")
    existing = get_cycle(cycle)
    if existing is None:
        raise ValidationError(f"No cycle {cycle!r}")
    if existing.status == "Archived":
        raise ValidationError(f"Cycle {cycle} is archived")
    v = _clean(fields, existing)
    if existing.status == "Open":
        _check_overlap(existing.cycle, v["opens_on"], v["closes_on"])
    sets = ", ".join(f"{k} = ?" for k in v)
    with _adm._connect() as conn:
        conn.execute(
            f"UPDATE admissions_cycles SET {sets}, updated_at = datetime('now') "  # noqa: S608 — keys from _FIELDS
            "WHERE cycle = ?", (*v.values(), existing.cycle))
        conn.commit()
    out = get_cycle(existing.cycle)
    assert out is not None
    return out


def set_cycle_status(cycle: str, status: str) -> Cycle:
    """Move a cycle along Planned → Open → Closed → Archived (a Closed
    cycle may be reopened to Open; nothing goes back to Planned)."""
    init_db()
    _guard.require("changing admissions cycles")
    existing = get_cycle(cycle)
    if existing is None:
        raise ValidationError(f"No cycle {cycle!r}")
    if status not in CYCLE_STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(CYCLE_STATUSES)}")
    allowed = {"Planned": ("Open", "Archived"), "Open": ("Closed",),
               "Closed": ("Open", "Archived"), "Archived": ()}
    if status == existing.status:
        return existing
    if status not in allowed[existing.status]:
        raise ValidationError(
            f"A {existing.status} cycle cannot be moved to {status}")
    if status == "Open":
        _check_overlap(existing.cycle, existing.opens_on, existing.closes_on)
    with _adm._connect() as conn:
        conn.execute("UPDATE admissions_cycles SET status = ?, "
                     "updated_at = datetime('now') WHERE cycle = ?",
                     (status, existing.cycle))
        conn.commit()
    logger.info("Admissions cycle %s: %s → %s (by %s)", existing.cycle,
                existing.status, status, _guard.actor())
    out = get_cycle(existing.cycle)
    assert out is not None
    return out


def delete_cycle(cycle: str) -> bool:
    """Delete a cycle set up by mistake: only a Planned one that no
    application belongs to."""
    init_db()
    _guard.require("changing admissions cycles")
    existing = get_cycle(cycle)
    if existing is None:
        return False
    if existing.status != "Planned":
        raise ValidationError("Only a Planned cycle can be deleted; archive "
                              "it instead.")
    with _adm._connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM admissions_applicants WHERE "
                         "intake_year = ?", (existing.cycle,)).fetchone()[0]
        if n:
            raise ValidationError(f"{n} application(s) are for {existing.cycle}")
        conn.execute("DELETE FROM admissions_cycles WHERE cycle = ?",
                     (existing.cycle,))
        conn.commit()
    return True


def open_cycle_for(day: _dt.date | None = None) -> str | None:
    """The Open cycle taking applications on *day* (opens_on <= day <=
    closes_on), or None. Configuration only — no capability needed, as
    the public form asks it too."""
    d = (day or _dt.date.today()).isoformat()
    # Read-only on purpose: admissions.create_applicant asks this while
    # its own insert is uncommitted, so creating the table here would
    # wait on that write lock. No table yet means no cycle configured.
    with _adm._connect() as conn:
        if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND "
                "name = 'admissions_cycles'").fetchone():
            return None
        r = conn.execute(
            "SELECT cycle FROM admissions_cycles WHERE status = 'Open' AND "
            "opens_on <= ? AND closes_on >= ? ORDER BY cycle LIMIT 1",
            (d, d)).fetchone()
    return r["cycle"] if r else None


def current_cycle(day: _dt.date | None = None) -> str | None:
    """The cycle admissions staff are working on: the Open one taking
    applications today, else the newest Open/Closed cycle whose
    application window has started and whose enrolment has not yet
    passed (results day and enrolment come after closing), else None."""
    d = day or _dt.date.today()
    found = open_cycle_for(d)
    if found:
        return found
    iso = d.isoformat()
    for c in list_cycles(include_archived=False):
        if c.status not in ("Open", "Closed"):
            continue
        end = max(x for x in (c.closes_on, c.results_day, c.enrolment_start)
                  if x)
        if c.opens_on <= iso <= end:
            return c.cycle
    return None


def results_day_cycle(day: _dt.date | None = None) -> str | None:
    """The configured cycle whose GCSE results day falls in *day*'s
    calendar year (results come out each August), or None."""
    year = str((day or _dt.date.today()).year)
    for c in list_cycles(include_archived=True):
        if c.results_day and c.results_day[:4] == year:
            return c.cycle
    return None


def offer_response_days(cycle: str | None) -> int | None:
    """Days an applicant in *cycle* has to answer an offer, when the
    cycle is configured."""
    c = get_cycle(cycle) if cycle else None
    return c.offer_response_days if c else None


# ── One application per learner per cycle ─────────────────────────

def applications_in_cycle(cycle: str, *, include_archived: bool = False
                          ) -> list[_adm.Applicant]:
    """Every application for *cycle* (its intake year)."""
    return _adm.list_applicants(intake_year=validate_cycle_name(cycle),
                                include_archived=include_archived)


def _same_person(a: _adm.Applicant, b: _adm.Applicant) -> bool:
    if a.email and b.email and a.email.strip().lower() == b.email.strip().lower():
        return True
    return bool(a.dob and a.dob == b.dob
                and a.first_name.strip().lower() == b.first_name.strip().lower()
                and a.last_name.strip().lower() == b.last_name.strip().lower())


def existing_application(applicant_id: str, cycle: str
                         ) -> _adm.Applicant | None:
    """Another live (not archived) application by the same person (e-mail,
    or name + date of birth) for *cycle*, if there is one."""
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    for other in applications_in_cycle(cycle):
        if other.applicant_id != a.applicant_id and _same_person(a, other):
            return other
    return None


def duplicate_applications(cycle: str) -> list[list[_adm.Applicant]]:
    """Groups of applications in *cycle* that look like the same person —
    the one-application-per-cycle rule is broken for each group."""
    apps = applications_in_cycle(cycle)
    groups: list[list[_adm.Applicant]] = []
    seen: set[str] = set()
    for i, a in enumerate(apps):
        if a.applicant_id in seen:
            continue
        group = [a] + [b for b in apps[i + 1:]
                       if b.applicant_id not in seen and _same_person(a, b)]
        if len(group) > 1:
            seen.update(x.applicant_id for x in group)
            groups.append(group)
    return groups


def reapplied_from(applicant_id: str) -> str | None:
    """The earlier application this one re-applies from."""
    init_db()
    _guard.require("applicant records")
    with _adm._connect() as conn:
        r = conn.execute("SELECT reapplied_from FROM admissions_applicants "
                         "WHERE applicant_id = ?", (applicant_id,)).fetchone()
    return r["reapplied_from"] if r else None


def reapplications_of(applicant_id: str) -> list[str]:
    """Later applications that re-apply from *applicant_id*."""
    init_db()
    _guard.require("applicant records")
    with _adm._connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT applicant_id FROM admissions_applicants WHERE "
            "reapplied_from = ? ORDER BY created_at", (applicant_id,))]


def reapply(applicant_id: str, to_cycle: str, *,
            note: str | None = None) -> _adm.Applicant:
    """Start a new application in *to_cycle* for the person behind a
    closed (or waitlisted) application: copies their details, profile,
    contacts, programme choices and GCSEs, links it with
    ``reapplied_from`` and notes both timelines. Sensitive information,
    references and the identity check are not copied — they must be
    gathered again for the new cycle."""
    init_db()
    _guard.require("creating applications")
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _det,
        entry_requirements as _er,
    )
    src = _adm.get_applicant(applicant_id)
    if src is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    to_cycle = validate_cycle_name(to_cycle)
    if src.converted_student_id or src.status == "Enrolled":
        raise ValidationError(f"{applicant_id} became a student; nothing to "
                              "re-apply from.")
    if src.merged_into:
        raise ValidationError(f"{applicant_id} was merged into "
                              f"{src.merged_into}; re-apply from that record.")
    if src.status not in REAPPLY_FROM:
        raise ValidationError(
            f"Only a closed or waitlisted application can be re-applied from "
            f"(this one is {src.status}); defer an offer instead.")
    if src.intake_year and to_cycle <= src.intake_year:
        raise ValidationError(f"Re-apply for a later intake than "
                              f"{src.intake_year}.")
    target = get_cycle(to_cycle)
    if target is not None and target.status in ("Closed", "Archived"):
        raise ValidationError(f"Cycle {to_cycle} is {target.status}")
    clash = existing_application(applicant_id, to_cycle)
    if clash:
        raise ValidationError(
            f"{clash.applicant_id} is already an application by this person "
            f"for {to_cycle} (one application per cycle).")
    if src.status == "Waitlisted":
        _adm.withdraw(applicant_id, notes=f"Re-applying for {to_cycle}")

    choices = [{"qualification_type": c.qualification_type,
                "subject": c.subject, "notes": c.notes}
               for c in _adm.list_programme_choices(applicant_id)]
    payload: dict[str, Any] = {
        "first_name": src.first_name, "last_name": src.last_name,
        "dob": src.dob, "email": src.email, "phone": src.phone,
        "address": src.address, "previous_school": src.previous_school,
        "predicted_gcses": src.predicted_gcses,
        "subject_1": src.subject_1, "subject_2": src.subject_2,
        "subject_3": src.subject_3,
        "application_source": src.application_source,
        "submitted_at": _dt.date.today().isoformat(),
        "status": "Submitted", "intake_year": to_cycle,
    }
    if choices:
        payload["programme_choices"] = choices
    new = _adm.create_applicant(payload, allow_duplicate=True)

    profile = {k: getattr(src, k) for k, _label in _det.PROFILE_FIELDS
               if k != "intake_year" and getattr(src, k) not in (None, "")}
    copied: list[str] = []
    if profile:
        _det.update_profile(new.applicant_id, **profile)
        copied.append("profile")
    if src.uln or src.upn:
        _adm._set_extra(new.applicant_id, uln=src.uln, upn=src.upn)
    n_contacts = 0
    for c in _det.list_contacts(applicant_id):
        _det.add_contact(new.applicant_id, {
            "name": c.name, "relationship": c.relationship, "phone": c.phone,
            "email": c.email, "address": c.address,
            "is_emergency": c.is_emergency,
            "parental_responsibility": c.parental_responsibility,
            "receives_correspondence": c.receives_correspondence})
        n_contacts += 1
    if n_contacts:
        copied.append(f"{n_contacts} contact(s)")
    n_gcses = 0
    for g in _er.list_gcses(applicant_id):
        _er.record_gcse(new.applicant_id, g.subject, g.grade,
                        result_type=g.result_type, kind=g.kind,
                        grade_system=g.grade_system, year=g.year,
                        exam_board=g.exam_board, source=g.source,
                        entered_by=g.entered_by)
        n_gcses += 1
    if n_gcses:
        copied.append(f"{n_gcses} GCSE result(s)")
    if choices:
        copied.append(f"{len(choices)} programme choice(s)")
    tail = f" ({note.strip()})" if note and note.strip() else ""
    with _adm._connect() as conn:
        conn.execute("UPDATE admissions_applicants SET reapplied_from = ? "
                     "WHERE applicant_id = ?", (applicant_id, new.applicant_id))
        _adm._log_event(
            conn, new.applicant_id,
            f"Re-application for {to_cycle} from {applicant_id} "
            f"({src.intake_year or 'no intake'}, {src.status}); copied "
            f"{', '.join(copied) or 'details only'}. References, sensitive "
            f"information and the identity check must be gathered again"
            + tail, kind="create")
        _adm._log_event(conn, applicant_id,
                        f"Re-applied for {to_cycle} as {new.applicant_id}"
                        + tail, kind="status")
        conn.commit()
    logger.info("Applicant %s re-applied for %s as %s", applicant_id,
                to_cycle, new.applicant_id)
    out = _adm.get_applicant(new.applicant_id)
    assert out is not None
    return out


# ── Rollover report ────────────────────────────────────────────────

@dataclass
class RolloverReport:
    from_cycle: str
    to_cycle: str
    by_status: dict[str, int] = field(default_factory=dict)
    #: Applications still open in the old cycle — each needs a decision
    #: (withdraw, defer or re-apply) before the cycle is closed.
    still_open: list[_adm.Applicant] = field(default_factory=list)
    #: Accepted offers not yet converted to students.
    accepted_not_enrolled: list[_adm.Applicant] = field(default_factory=list)
    deferred_in: list[_adm.Applicant] = field(default_factory=list)
    reapplied: list[tuple[str, str]] = field(default_factory=list)
    duplicates_in_new: list[list[_adm.Applicant]] = field(default_factory=list)
    next_cycle_configured: bool = False

    def lines(self) -> list[str]:
        out = [f"Rollover {self.from_cycle} → {self.to_cycle}"]
        out.append("By status: " + (", ".join(
            f"{k}: {v}" for k, v in sorted(self.by_status.items())) or "none"))
        out.append(f"Still open in {self.from_cycle}: {len(self.still_open)}")
        out.append(f"Accepted, not enrolled: {len(self.accepted_not_enrolled)}")
        out.append(f"Deferred into {self.to_cycle}: {len(self.deferred_in)}")
        out.append(f"Re-applied for {self.to_cycle}: {len(self.reapplied)}")
        out.append(f"Possible double applications in {self.to_cycle}: "
                   f"{len(self.duplicates_in_new)}")
        if not self.next_cycle_configured:
            out.append(f"Cycle {self.to_cycle} is not set up yet.")
        return out


def next_cycle_name(cycle: str) -> str:
    y = int(validate_cycle_name(cycle)[:4]) + 1
    return f"{y}/{str(y + 1)[-2:]}"


def rollover_report(from_cycle: str, to_cycle: str | None = None
                    ) -> RolloverReport:
    """What is left to do when moving from one cycle to the next."""
    from_cycle = validate_cycle_name(from_cycle)
    to_cycle = validate_cycle_name(to_cycle) if to_cycle else next_cycle_name(
        from_cycle)
    old = applications_in_cycle(from_cycle)
    rep = RolloverReport(from_cycle=from_cycle, to_cycle=to_cycle,
                         next_cycle_configured=get_cycle(to_cycle) is not None)
    for a in old:
        rep.by_status[a.status] = rep.by_status.get(a.status, 0) + 1
        if a.status == "Offer Accepted" and not a.converted_student_id:
            rep.accepted_not_enrolled.append(a)
        elif a.is_open:
            rep.still_open.append(a)
    new = applications_in_cycle(to_cycle)
    rep.deferred_in = [a for a in new if a.deferred_from == from_cycle]
    old_ids = {a.applicant_id for a in applications_in_cycle(
        from_cycle, include_archived=True)}
    init_db()
    with _adm._connect() as conn:
        rows = conn.execute(
            "SELECT applicant_id, reapplied_from FROM admissions_applicants "
            "WHERE intake_year = ? AND reapplied_from IS NOT NULL",
            (to_cycle,)).fetchall()
    rep.reapplied = [(r["reapplied_from"], r["applicant_id"]) for r in rows
                     if r["reapplied_from"] in old_ids]
    rep.duplicates_in_new = duplicate_applications(to_cycle)
    return rep


# ── Offer expiry housekeeping (scheduled jobs) ─────────────────────

def lapsed_offers(day: _dt.date | None = None) -> list[_adm.Applicant]:
    """Offers still waiting for an answer whose expiry date has passed."""
    today = (day or _dt.date.today()).isoformat()
    return [a for a in _adm.list_expiring_offers(within_days=0, today=day)
            if a.offer_expiry and a.offer_expiry < today]


def lapse_expired_offers(day: _dt.date | None = None
                         ) -> tuple[list[str], list[str]]:
    """Withdraw every lapsed offer with reason "No response from
    applicant". Returns (lapsed ids, error messages)."""
    done: list[str] = []
    errors: list[str] = []
    for a in lapsed_offers(day):
        try:
            _adm.withdraw(a.applicant_id, reason=LAPSE_REASON,
                          notes=f"Offer lapsed: no reply by {a.offer_expiry}")
            done.append(a.applicant_id)
        except Exception as e:  # noqa: BLE001 — one bad record must not stop the rest
            logger.exception("Could not lapse offer for %s", a.applicant_id)
            errors.append(f"{a.applicant_id}: {e}")
    return done, errors


def offers_needing_warning(days: int = WARNING_DAYS,
                           day: _dt.date | None = None) -> list[_adm.Applicant]:
    """Offers expiring within *days* (not yet expired) whose applicant has
    not been warned about this expiry date."""
    init_db()
    today = (day or _dt.date.today()).isoformat()
    due = [a for a in _adm.list_expiring_offers(within_days=days, today=day,
                                                include_expired=False)
           if a.offer_expiry and a.offer_expiry >= today]
    if not due:
        return []
    with _adm._connect() as conn:
        warned = {(r[0], r[1]) for r in conn.execute(
            "SELECT applicant_id, offer_expiry FROM admissions_offer_warnings")}
    return [a for a in due if (a.applicant_id, a.offer_expiry) not in warned]


def record_warning_sent(applicant_id: str, offer_expiry: str) -> None:
    init_db()
    _guard.require("offer reminders")
    with _adm._connect() as conn:
        conn.execute("INSERT OR IGNORE INTO admissions_offer_warnings "
                     "(applicant_id, offer_expiry) VALUES (?, ?)",
                     (applicant_id, offer_expiry))
        _adm._log_event(conn, applicant_id,
                        f"Offer expiry warning sent (expires {offer_expiry})",
                        kind="offer")
        conn.commit()

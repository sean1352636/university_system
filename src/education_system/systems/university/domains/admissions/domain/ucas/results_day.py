"""Results day: turning conditional offers into places, or not.

The offer email this module's neighbour sends has always told applicants
that if their final grades meet the conditions they "will be confirmed
automatically on results day". This is the path that keeps the promise:
it reads the grades the sixth form has recorded, checks them against the
condition we set, and gives an admissions officer a board of every firm
and insurance applicant with a verdict against each one.

**Reading results.** Through the sixth form's platform adapter
(``exam_results_for_admissions``) — never by importing the sixth form.
Every result comes back, embargoed or not, with ``released`` and
``release_at``: universities see results before the public does, and the
verdicts are worked out on all of them.

**The embargo.** Nothing an applicant could learn their results from —
a confirmation, a rejection, the e-mails those send — happens while a
result it relies on is still embargoed. Such an action is *held*
(:func:`list_holds`; "Held until results publication" on the board) with
who asked and when, and applied once every relied-on result is published:
automatically when the board is next opened or the hourly results-day job
runs (:func:`apply_released_holds`), or when an officer presses "Release
held confirmations" (:func:`release_held`). Who released it and when is
recorded beside the hold.

**What is checked.** Conditions are the structured rows on the offer
(``offer_terms.ucas_offer_conditions``), or, for an offer recorded with
free text only, that text read by the platform's condition reader
(``platform/cross_system/offer_conditions``): grade profiles in any
qualification the platform knows (A level, AS, BTEC D*D*D*…PPP, T Level
Distinction*…, EPQ, Core Maths), mixed profiles ("BB + DM"), subject
grades ("including B in Mathematics"), UCAS Tariff points ("112 points",
on the published tariff) and GCSE requirements. Only a condition that
cannot be read — or a GCSE that is not on record — goes to a person as
:data:`REVIEW`.

**What is automatic.** :func:`auto_confirm` confirms :data:`MET` firm
applicants. Declining a missed condition stays a person's call
(:func:`decline_place`). Confirming goes through ``record_decision`` and
``ucas.confirm_place``, so it is attributed, audited and e-mailed exactly
like any other decision.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from education_system.platform.cross_system import offer_conditions as _oc
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)

__all__ = [
    "MET", "MISSED", "REVIEW", "PENDING",
    "HOLD_ACTIONS", "HOLD_STATUSES",
    "Candidate",
    "Hold",
    "ResultsUnavailable",
    "apply_released_holds",
    "auto_confirm",
    "board",
    "cancel_hold",
    "confirm_place",
    "decline_place",
    "list_holds",
    "parse_grade_profile",
    "profile_is_met",
    "release_held",
]

#: Verdicts (the platform's, so both systems say the same words).
MET = _oc.MET          #: Condition checked in full and satisfied.
MISSED = _oc.MISSED    #: Condition checked in full and not satisfied.
REVIEW = _oc.REVIEW    #: Needs a person — unreadable prose, GCSE not on record.
PENDING = _oc.PENDING  #: Not enough results recorded yet.

HOLD_ACTIONS = ("confirm", "decline")
HOLD_STATUSES = ("Held", "Applied", "Lapsed", "Cancelled", "Failed")
HELD_LABEL = "Held until results publication"

#: A-level grades, best first — kept for :func:`parse_grade_profile`.
_GRADE_ORDER = ("A*", "A", "B", "C", "D", "E")
_GRADE_RANK = {g: i for i, g in enumerate(_GRADE_ORDER)}
_PROFILE_RE = re.compile(r"^(?:A\*|[A-E])+$")
_GRADE_TOKEN_RE = re.compile(r"A\*|[A-E]")


class ResultsUnavailable(RuntimeError):
    """The sixth form's results cannot be read from here right now."""


# ── A-level grade arithmetic (kept for existing callers) ───────────

def parse_grade_profile(text: str | None) -> list[str] | None:
    """The A-level grade profile a condition opens with, or ``None``.

    ``"ABB"`` → ``["A", "B", "B"]``. Results day itself now reads every
    qualification through ``offer_conditions``; this stays for callers that
    only want the A-level letters.
    """
    if not text:
        return None
    first = str(text).strip().split()[0] if str(text).strip() else ""
    first = first.upper().rstrip(",;:")
    if not first or not _PROFILE_RE.match(first):
        return None
    return _GRADE_TOKEN_RE.findall(first)


def profile_is_met(required: list[str], achieved: list[str]) -> bool:
    """Does *achieved* satisfy *required* (A-level letters, best-first)?"""
    if not required:
        return False
    if len(achieved) < len(required):
        return False
    want = sorted(required, key=lambda g: _GRADE_RANK.get(g, 99))
    got = sorted(achieved, key=lambda g: _GRADE_RANK.get(g, 99))
    return all(_GRADE_RANK.get(got[i], 99) <= _GRADE_RANK.get(want[i], 99)
               for i in range(len(want)))


# ── Reading results through the sixth form adapter ─────────────────

def _results_for(student_id: str, year: int | None = None) -> list[dict]:
    """Every exam result the sixth form holds for *student_id*, embargoed
    or not, in the adapter's shape.

    All years are read, not just *year*: a resit or an AS from last summer
    counts, and an applicant who deferred has results from the year before
    their entry. Raises :class:`ResultsUnavailable` when the adapter is not
    there or does not provide results yet.
    """
    try:
        from education_system.platform.cross_system.adapters import registry
        from education_system.platform.cross_system.adapters.base import (
            AdapterNotImplemented,
        )
    except Exception as exc:  # pragma: no cover - platform always present
        raise ResultsUnavailable(f"adapter registry unavailable: {exc}") from exc
    try:
        adapter = registry.load("sixth_form")
    except Exception as exc:
        raise ResultsUnavailable(f"sixth form adapter failed to load: {exc}") from exc
    if adapter is None:
        raise ResultsUnavailable("no sixth form adapter is registered")
    method = getattr(adapter, "exam_results_for_admissions", None)
    if method is None:
        raise ResultsUnavailable(
            "the sixth form adapter does not provide exam results")
    try:
        rows = method(student_id)
    except AdapterNotImplemented as exc:
        raise ResultsUnavailable(
            "the sixth form adapter does not provide exam results yet") from exc
    except Exception as exc:
        logger.info("Exam results unavailable for %s", student_id, exc_info=True)
        raise ResultsUnavailable(f"exam results could not be read: {exc}") from exc
    return [dict(r) for r in rows or ()]


def _achieved_grades(student_id: str, year: int | None) -> dict[str, str]:
    """``{subject: grade}`` — every result, for a quick display."""
    try:
        rows = _results_for(student_id, year)
    except ResultsUnavailable:
        return {}
    return {str(r.get("subject") or ""): str(r.get("grade") or "")
            for r in rows if r.get("grade")}


# ── The board ──────────────────────────────────────────────────────

@dataclass
class Hold:
    """A results-day action waiting for results to be published."""

    hold_id: int
    sf_choice_id: int
    sf_student_id: str | None
    action: str
    automatic: bool
    verdict: str | None
    reason: str | None
    note: str | None
    status: str
    release_at: str | None
    held_by: str | None
    held_at: str
    released_by: str | None
    released_at: str | None
    outcome: str | None

    @property
    def label(self) -> str:
        what = "Confirmation" if self.action == "confirm" else "Decline"
        if self.status == "Held":
            when = f" (results out {self.release_at})" if self.release_at else ""
            return f"{what} {HELD_LABEL.lower()}{when}"
        return f"{what} {self.status.lower()}"


@dataclass
class Candidate:
    """One firm or insurance applicant awaiting a results-day decision."""

    choice_id: int
    application_id: int
    student_id: str
    student_name: str
    course_name: str
    course_code: str | None
    final_decision: str | None      # 'Firm' / 'Insurance'
    condition: str | None           # what we asked for, as written
    required_profile: list[str] | None
    achieved: dict[str, str] = field(default_factory=dict)  # subject -> grade
    verdict: str = PENDING
    reason: str = ""
    conditions: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    results_available: bool = True
    #: Relied-on results still under embargo — act on nothing until empty.
    embargoed: list[dict[str, Any]] = field(default_factory=list)
    release_at: str | None = None
    hold: Hold | None = None

    @property
    def achieved_profile(self) -> list[str]:
        return [g for g in self.achieved.values() if g]

    @property
    def is_firm(self) -> bool:
        return self.final_decision == "Firm"

    @property
    def is_embargoed(self) -> bool:
        return bool(self.embargoed)

    @property
    def achieved_label(self) -> str:
        if not self.results_available:
            return "Results unavailable"
        if not self.results:
            return "—"
        parts = []
        for r in sorted(self.results, key=lambda r: str(r.get("subject") or "")):
            mark = "" if _oc.is_released(r) else " (embargoed)"
            q = r.get("qualification_type")
            parts.append(f"{r.get('subject')} {r.get('grade')}"
                         + (f" [{q}]" if q and q != "A Level" else "") + mark)
        return ", ".join(parts)

    @property
    def conditions_label(self) -> str:
        return "; ".join(_oc.describe(c) for c in self.conditions) or "—"

    @property
    def status_label(self) -> str:
        """What the board shows beside the verdict."""
        if self.hold is not None and self.hold.status == "Held":
            return self.hold.label
        if self.is_embargoed:
            when = f" ({self.release_at})" if self.release_at else ""
            return f"Results embargoed{when}"
        return ""


def _terms_for(choice_id: int):
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            offer_terms as _terms,
        )
        return _terms, _terms.get_terms(choice_id)
    except Exception:
        logger.debug("Could not read issued terms for choice #%s", choice_id,
                     exc_info=True)
        return None, None


def _condition_for(choice_id: int, summary: str | None) -> tuple[str | None, list[dict]]:
    """``(condition as written, conditions to check)`` for one offer.

    The structured rows an officer entered win; then the ``grade_requirement``
    written to be checked; then the one-line summary on the choice.
    """
    terms_mod, issued = _terms_for(choice_id)
    written = None
    if issued is not None and (issued.grade_requirement or "").strip():
        written = issued.grade_requirement
    written = written or summary
    if terms_mod is not None:
        conds = terms_mod.effective_conditions(issued, summary)
    else:
        conds = _oc.conditions_from_text(written) if written else []
    return written, conds


def _judge(candidate: Candidate) -> None:
    """Fill in *candidate*'s verdict, reason and embargo state."""
    if not candidate.results_available:
        candidate.verdict = PENDING
        return
    if not candidate.conditions:
        candidate.verdict = REVIEW
        candidate.reason = "No condition recorded on this offer."
        return
    ev = _oc.evaluate(candidate.conditions, candidate.results)
    candidate.verdict = ev.verdict
    candidate.reason = ev.reason
    candidate.embargoed = ev.unreleased
    candidate.release_at = ev.release_at


def _build_candidate(a, cycle_year: int | None) -> Candidate:
    written, conds = _condition_for(a.choice_id, a.offer_terms)
    candidate = Candidate(
        choice_id=a.choice_id,
        application_id=a.application_id,
        student_id=a.student_id,
        student_name=a.student_name,
        course_name=a.course_name,
        course_code=a.course_code,
        final_decision=a.final_decision,
        condition=written,
        required_profile=parse_grade_profile(written),
        conditions=conds,
    )
    try:
        candidate.results = _results_for(a.student_id, a.entry_year or cycle_year)
    except ResultsUnavailable as exc:
        candidate.results_available = False
        candidate.reason = f"Results unavailable: {exc}."
    candidate.achieved = {str(r.get("subject") or ""): str(r.get("grade") or "")
                          for r in candidate.results if r.get("grade")}
    _judge(candidate)
    return candidate


def _candidates(*, cycle_year=None, university_name=None,
                include_insurance=True) -> list[Candidate]:
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    applicants = _ucas.list_applicants(
        university_name=university_name,
        decision_status="Conditional Offer",
        cycle_year=cycle_year,
    )
    wanted = {"Firm"} | ({"Insurance"} if include_insurance else set())
    out = [_build_candidate(a, cycle_year) for a in applicants
           if a.final_decision in wanted]
    held = {h.sf_choice_id: h for h in list_holds(status="Held")}
    for c in out:
        c.hold = held.get(c.choice_id)
    return out


def board(
    *,
    cycle_year: int | None = None,
    university_name: str | None = None,
    include_insurance: bool = True,
    apply_released: bool = True,
    acting_user: str | None = None,
) -> list[Candidate]:
    """Every applicant holding a conditional offer from us, with a verdict.

    Opening the board first applies any held action whose results have
    since been published (``apply_released=False`` to only look). Firm
    choices first, then insurance; within each, the ones needing a
    decision before the ones that do not.
    """
    if apply_released:
        try:
            apply_released_holds(
                released_by=acting_user or "auto (results board)",
                cycle_year=cycle_year, university_name=university_name)
        except Exception:
            logger.exception("Could not apply released results-day holds")
    out = _candidates(cycle_year=cycle_year, university_name=university_name,
                      include_insurance=include_insurance)
    order = {MET: 0, MISSED: 1, REVIEW: 2, PENDING: 3}
    out.sort(key=lambda c: (0 if c.is_firm else 1,
                            order.get(c.verdict, 9),
                            c.student_name))
    logger.info("Results-day board: %d candidate(s)", len(out))
    return out


def _candidate_for(choice_id: int) -> Candidate | None:
    for c in _candidates():
        if c.choice_id == choice_id:
            return c
    return None


# ── Holds ──────────────────────────────────────────────────────────

_HOLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_results_holds (
    hold_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sf_choice_id   INTEGER NOT NULL,
    sf_student_id  TEXT,
    action         TEXT NOT NULL CHECK (action IN ('confirm', 'decline')),
    automatic      INTEGER NOT NULL DEFAULT 0,
    verdict        TEXT,
    reason         TEXT,
    note           TEXT,
    status         TEXT NOT NULL DEFAULT 'Held' CHECK (status IN
                       ('Held', 'Applied', 'Lapsed', 'Cancelled', 'Failed')),
    release_at     TEXT,
    held_by        TEXT,
    held_at        TEXT NOT NULL DEFAULT (datetime('now')),
    released_by    TEXT,
    released_at    TEXT,
    outcome        TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ucas_results_hold_open
    ON ucas_results_holds(sf_choice_id) WHERE status = 'Held';
CREATE INDEX IF NOT EXISTS idx_ucas_results_holds_status
    ON ucas_results_holds(status, held_at);
"""

_HOLDS_READY = False


def _init_holds() -> None:
    global _HOLDS_READY
    if _HOLDS_READY:
        return
    conn = get_connection()
    try:
        conn.executescript(_HOLD_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    _HOLDS_READY = True


def _hold(r) -> Hold:
    return Hold(
        hold_id=r["hold_id"], sf_choice_id=r["sf_choice_id"],
        sf_student_id=r["sf_student_id"], action=r["action"],
        automatic=bool(r["automatic"]), verdict=r["verdict"],
        reason=r["reason"], note=r["note"], status=r["status"],
        release_at=r["release_at"], held_by=r["held_by"],
        held_at=r["held_at"], released_by=r["released_by"],
        released_at=r["released_at"], outcome=r["outcome"])


def list_holds(*, status: str | None = None,
               choice_id: int | None = None) -> list[Hold]:
    """Held (and past) results-day actions, newest first."""
    _init_holds()
    clauses, args = [], []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if choice_id is not None:
        clauses.append("sf_choice_id = ?")
        args.append(int(choice_id))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = get_connection()
    try:
        # db-audit: ignore[DBW001] - fixed clause list
        rows = conn.execute(
            f"SELECT * FROM ucas_results_holds {where} "  # nosec B608
            "ORDER BY held_at DESC, hold_id DESC", args).fetchall()
    finally:
        conn.close()
    return [_hold(r) for r in rows]


def _place_hold(candidate: Candidate, action: str, *, held_by: str | None,
                note: str | None, automatic: bool) -> Hold:
    """Record that *action* waits for results; one open hold per choice
    (a second request replaces the first, keeping who asked last)."""
    _init_holds()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE ucas_results_holds SET status = 'Cancelled', "
            "released_by = ?, released_at = datetime('now'), "
            "outcome = 'Replaced by a later request' "
            "WHERE sf_choice_id = ? AND status = 'Held'",
            (held_by, candidate.choice_id))
        cur = conn.execute(
            """INSERT INTO ucas_results_holds
                   (sf_choice_id, sf_student_id, action, automatic, verdict,
                    reason, note, release_at, held_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (candidate.choice_id, candidate.student_id, action,
             1 if automatic else 0, candidate.verdict, candidate.reason,
             note, candidate.release_at, held_by or "unknown"))
        conn.commit()
        row = conn.execute("SELECT * FROM ucas_results_holds WHERE hold_id = ?",
                           (cur.lastrowid,)).fetchone()
    finally:
        conn.close()
    hold = _hold(row)
    logger.info("Results-day %s for choice #%d held until results publication "
                "(%s, by %s)", action, candidate.choice_id,
                candidate.release_at or "release time unknown", hold.held_by)
    return hold


def _close_hold(hold_id: int, status: str, *, released_by: str | None,
                outcome: str | None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE ucas_results_holds SET status = ?, released_by = ?, "
            "released_at = datetime('now'), outcome = ? "
            "WHERE hold_id = ? AND status = 'Held'",
            (status, released_by or "unknown", outcome, hold_id))
        conn.commit()
    finally:
        conn.close()


def cancel_hold(hold_id: int, *, cancelled_by: str | None = None,
                reason: str | None = None) -> bool:
    """Withdraw a held action before it is applied."""
    before = [h for h in list_holds(status="Held") if h.hold_id == hold_id]
    if not before:
        return False
    _close_hold(hold_id, "Cancelled", released_by=cancelled_by,
                outcome=reason or "Cancelled by an officer")
    return True


def _apply_hold(hold: Hold, candidate: Candidate | None,
                released_by: str) -> str:
    """Apply one held action whose results are out. Returns its new status."""
    if candidate is None:
        _close_hold(hold.hold_id, "Lapsed", released_by=released_by,
                    outcome="The offer is no longer a conditional firm/"
                            "insurance offer — decided elsewhere.")
        return "Lapsed"
    if hold.automatic and hold.action == "confirm" and candidate.verdict != MET:
        # Held because the grades met the condition; the published grades
        # (a late amendment, a remark) no longer do. Back to a person.
        _close_hold(hold.hold_id, "Lapsed", released_by=released_by,
                    outcome=f"On publication the verdict is {candidate.verdict}: "
                            f"{candidate.reason}")
        return "Lapsed"
    try:
        if hold.action == "confirm":
            _do_confirm(hold.sf_choice_id, decided_by=hold.held_by,
                        note=hold.note or candidate.reason)
        else:
            _do_decline(hold.sf_choice_id, decided_by=hold.held_by,
                        reason=hold.note)
    except Exception as exc:
        logger.exception("Could not apply held %s for choice #%d",
                         hold.action, hold.sf_choice_id)
        _close_hold(hold.hold_id, "Failed", released_by=released_by,
                    outcome=str(exc))
        return "Failed"
    _close_hold(hold.hold_id, "Applied", released_by=released_by,
                outcome=f"Applied on publication ({candidate.verdict}).")
    return "Applied"


def apply_released_holds(*, released_by: str = "auto (results-day job)",
                         cycle_year: int | None = None,
                         university_name: str | None = None) -> dict[str, int]:
    """Apply every held action whose relied-on results are now published.

    Holds whose results are still embargoed are left as they are. Returns
    counts by outcome (``Applied`` / ``Lapsed`` / ``Failed`` / ``waiting``).
    """
    held = list_holds(status="Held")
    counts = {"Applied": 0, "Lapsed": 0, "Failed": 0, "waiting": 0}
    if not held:
        return counts
    by_choice = {c.choice_id: c for c in _candidates(
        cycle_year=cycle_year, university_name=university_name)}
    for hold in held:
        candidate = by_choice.get(hold.sf_choice_id)
        if candidate is not None and (candidate.is_embargoed
                                      or not candidate.results_available):
            counts["waiting"] += 1
            continue
        if candidate is None and (cycle_year is not None
                                  or university_name is not None):
            # Outside the cycle this run looked at — not ours to lapse.
            counts["waiting"] += 1
            continue
        counts[_apply_hold(hold, candidate, released_by)] += 1
    if counts["Applied"] or counts["Lapsed"] or counts["Failed"]:
        logger.info("Results-day holds applied: %s", counts)
    return counts


def release_held(hold_ids: list[int] | None = None, *,
                 released_by: str | None = None) -> dict[str, int]:
    """The "Release held confirmations" action.

    Applies the chosen held actions (all of them when *hold_ids* is None)
    whose results are published. The embargo itself is never overridden:
    a hold whose results are still embargoed stays held and is counted as
    ``waiting``.
    """
    wanted = set(hold_ids) if hold_ids else None
    held = [h for h in list_holds(status="Held")
            if wanted is None or h.hold_id in wanted]
    counts = {"Applied": 0, "Lapsed": 0, "Failed": 0, "waiting": 0}
    if not held:
        return counts
    by_choice = {c.choice_id: c for c in _candidates()}
    for hold in held:
        candidate = by_choice.get(hold.sf_choice_id)
        if candidate is not None and (candidate.is_embargoed
                                      or not candidate.results_available):
            counts["waiting"] += 1
            continue
        counts[_apply_hold(hold, candidate, released_by or "unknown")] += 1
    return counts


# ── Decisions ──────────────────────────────────────────────────────

def _do_confirm(choice_id: int, *, decided_by: str | None, note: str | None):
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    out = _ucas.record_decision(
        choice_id,
        "Unconditional Offer",
        offer_terms="Confirmed on results day — conditions met",
        notes=note,
        issued_by=decided_by,
    )
    # Settle the application (Confirmed is what the handover reads as the
    # record of results day). ``ucas.confirm_place`` is the one door for
    # that: it checks the choice is ours and Firm, e-mails the outcome and
    # closes the college login. An insurance place or an already-settled
    # application is left as the decision above made it.
    try:
        _ucas.confirm_place(choice_id, issued_by=decided_by)
    except _ucas.UcasError as exc:
        logger.warning("Choice #%d made unconditional but the application "
                       "was not settled: %s", choice_id, exc)
    logger.info("Confirmed place for UCAS choice #%d (by %s)",
                choice_id, decided_by or "—")
    return out


def _do_decline(choice_id: int, *, decided_by: str | None, reason: str | None):
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    out = _ucas.record_decision(
        choice_id,
        "Rejected",
        notes=(reason or "Conditions of the offer were not met."),
        issued_by=decided_by,
    )
    logger.info("Declined UCAS choice #%d on results (by %s)",
                choice_id, decided_by or "—")
    return out


def _embargo_check(choice_id: int) -> Candidate | None:
    """The candidate when its relied-on results are still embargoed (or
    cannot be read to tell), else ``None``."""
    candidate = _candidate_for(choice_id)
    if candidate is None:
        return None
    if candidate.is_embargoed or not candidate.results_available:
        return candidate
    return None


def confirm_place(choice_id: int, *, decided_by: str | None = None,
                  note: str | None = None):
    """Confirm an applicant's place — the promise the offer email made.

    If a result the verdict relies on is still embargoed, nothing is
    recorded or e-mailed: the confirmation is held and a :class:`Hold` is
    returned; it is applied once the results are published. Otherwise the
    decision is recorded (attributed, audited, e-mailed) and the refreshed
    choice returned.
    """
    waiting = _embargo_check(choice_id)
    if waiting is not None:
        return _place_hold(waiting, "confirm", held_by=decided_by,
                           note=note, automatic=False)
    return _do_confirm(choice_id, decided_by=decided_by, note=note)


def decline_place(choice_id: int, *, decided_by: str | None = None,
                  reason: str | None = None):
    """Turn down an applicant who missed their conditions.

    An explicit call rather than something ``auto_confirm`` does: near
    misses get taken anyway every year. Held, like a confirmation, while a
    relied-on result is embargoed — a rejection e-mail before results day
    would tell the applicant their grades.
    """
    waiting = _embargo_check(choice_id)
    if waiting is not None:
        return _place_hold(waiting, "decline", held_by=decided_by,
                           note=reason, automatic=False)
    return _do_decline(choice_id, decided_by=decided_by, reason=reason)


def auto_confirm(
    *,
    cycle_year: int | None = None,
    university_name: str | None = None,
    decided_by: str | None = None,
    dry_run: bool = True,
) -> list[Candidate]:
    """Confirm every firm applicant whose condition is met in full.

    Defaults to a dry run. Only :data:`MET` firm candidates are touched.
    One whose results are still embargoed is held rather than confirmed
    (its :attr:`Candidate.hold` is set) and confirmed on publication if the
    published grades still meet the condition.

    Returns the candidates confirmed or held (or that would have been).
    """
    candidates = [c for c in board(cycle_year=cycle_year,
                                   university_name=university_name,
                                   apply_released=not dry_run,
                                   acting_user=decided_by)
                  if c.is_firm and c.verdict == MET]
    if dry_run:
        logger.info("auto_confirm dry run: %d place(s) would be confirmed "
                    "(%d after results publication)", len(candidates),
                    sum(1 for c in candidates if c.is_embargoed))
        return candidates

    done: list[Candidate] = []
    for candidate in candidates:
        try:
            if candidate.is_embargoed:
                if candidate.hold is None:
                    candidate.hold = _place_hold(
                        candidate, "confirm", held_by=decided_by or "auto",
                        note=candidate.reason, automatic=True)
            else:
                _do_confirm(candidate.choice_id, decided_by=decided_by,
                            note=candidate.reason)
            done.append(candidate)
        except Exception:
            # One applicant's email bouncing must not stop the rest of
            # results day.
            logger.exception(
                "Could not confirm UCAS choice #%d", candidate.choice_id)
    logger.info("auto_confirm: %d of %d place(s) confirmed or held",
                len(done), len(candidates))
    return done

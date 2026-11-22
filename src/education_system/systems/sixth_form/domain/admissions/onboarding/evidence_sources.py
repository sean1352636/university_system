"""Record-backed onboarding tasks: the evidence rules and the resync.

:mod:`onboarding` asks a rule, registered here per task key, whether the
record that proves a task exists before letting it be ticked without
written evidence. Each rule returns ``(ok, ref, message)``:

* ``(True, ref, "")`` — the record is on file; *ref* is kept on the task
  (``evidence_ref``), e.g. ``"idcard:SF26-0012"``;
* ``(False, None, message)`` — it is not, and *message* says what to do;
* ``(None, None, "")`` — this source cannot tell (module not in use, the
  data cannot be read, or the record proves only part of the task): the
  task ticks freely.

Where a module is the college's own record of the thing (ID cards,
tutor groups, class groups / timetable, the learner's login, the student
record, bursary applications) a missing record is ``False``. Where it may
not be in use (lockers before any bank exists, the library, SEND) only a
found record counts, otherwise the rule cannot tell.

Rules are matched to task keys by wording (:func:`rule_for`), registered
for every task in :data:`onboarding.TEMPLATES` on import; a key nobody
registered falls back to the same matching (the registry is a
:class:`_MatchedRules`), so a task added by hand under a new name is
checked too.

:func:`resync` / :func:`resync_all` tick open tasks whose record now
exists, through :func:`onboarding.set_item_status` (rules and history
apply), and re-open a task ticked from one of these records when the
record has gone. Tasks evidenced by hand (written evidence, N/A) are
never touched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)

logger = logging.getLogger(__name__)

Result = tuple["bool | None", "str | None", str]
Rule = Callable[[str, Any], Result]

_CANT_TELL: Result = (None, None, "")

#: ``evidence_ref`` prefixes written by the rules in this module (the
#: resync re-opens only tasks ticked from these).
REF_PREFIXES: tuple[str, ...] = (
    "login:", "tutorgroup:", "timetable:", "classgroups:", "idcard:",
    "library:", "textbooks:", "locker:", "student:", "contact:",
    "medical:", "send:", "bursary:")


def _missing(item: Any, what: str) -> Result:
    return (False, None, f"'{item.task_name}': {what}. Record it, or say "
                         "where the evidence is.")


def _year_of(item: Any) -> str | None:
    c = ob.get_checklist(item.checklist_id)
    return c.academic_year if c else None


def _student(sid: str) -> Any:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return _students.get_student(sid)


# ── IT account (the learner's sixth form login, read-only) ──────────

def login_state(sid: str) -> str | None:
    """"Active" / "Disabled" / "No sixth form access" / "None" (no login),
    or None when the login database cannot be read. Read-only."""
    try:
        from education_system.platform.identity.auth.db import (
            connect as _auth_connect,
        )
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        conn = _auth_connect()
        try:
            u = conn.execute("SELECT id, is_active FROM users "
                             "WHERE username = ?", (sid,)).fetchone()
            if u is None:
                return "None"
            has = conn.execute(
                "SELECT 1 FROM user_systems WHERE user_id = ? AND "
                "system_key = ?", (u["id"], _students.AUTH_SYSTEM_KEY)
            ).fetchone()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — unreadable: the rule can't tell
        logger.debug("login of %s not readable", sid, exc_info=True)
        return None
    if not u["is_active"]:
        return "Disabled"
    return "Active" if has else "No sixth form access"


def it_account_rule(sid: str, item: Any) -> Result:
    state = login_state(sid)
    if state is None:
        return _CANT_TELL
    if state == "Active":
        return True, f"login:{sid}", ""
    if state == "None":
        return _missing(item, f"{sid} has no sign-in account")
    return _missing(item, f"{sid}'s sign-in account is {state.lower()}")


def logon_tested_rule(sid: str, item: Any) -> Result:
    """Testing a logon needs the account first; the test itself is the
    member of staff's word."""
    state = login_state(sid)
    if state in ("None", "Disabled", "No sixth form access"):
        return _missing(item, "the learner's sign-in account is not set up "
                              f"({state.lower()})")
    return _CANT_TELL


# ── Tutor group / class groups / timetable ──────────────────────────

def _tutor_groups():
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups as _tg,
    )
    return _tg


def tutor_group_rule(sid: str, item: Any) -> Result:
    tg = _tutor_groups()
    g = tg.group_for_student(sid)
    if g is not None:
        return True, f"tutorgroup:{g.name}", ""
    if not tg.list_groups():
        return _CANT_TELL
    return _missing(item, "the learner is not in a tutor group")


def meet_tutor_rule(sid: str, item: Any) -> Result:
    """Meeting the tutor needs a tutor group first."""
    tg = _tutor_groups()
    if tg.group_for_student(sid) is None and tg.list_groups():
        return _missing(item, "the learner is not in a tutor group yet — "
                              "assign one first")
    return _CANT_TELL


def _class_groups(sid: str) -> list[Any]:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    return _cg.groups_for_student(sid)


def class_groups_rule(sid: str, item: Any) -> Result:
    groups = _class_groups(sid)
    if groups:
        return True, f"classgroups:{len(groups)}", ""
    return _missing(item, "the learner is in no class groups")


def timetable_rule(sid: str, item: Any) -> Result:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolment_checks as _checks,
    )
    if not _class_groups(sid):
        return _missing(item, "the learner is in no class groups, so has "
                              "no timetable")
    slots = _checks.learner_timetable(sid)
    if not slots:
        return _missing(item, "the learner's class groups have no "
                              "timetable slots")
    return True, f"timetable:{len(slots)} slots", ""


# ── ID card ─────────────────────────────────────────────────────────

def _card(sid: str) -> Any:
    from education_system.systems.sixth_form.domains.operations.domain.id_cards import (
        id_cards as _cards,
    )
    return _cards, _cards.card_for("Student", sid)


def id_card_rule(sid: str, item: Any) -> Result:
    cards, card = _card(sid)
    if card is None:
        return _missing(item, "the learner has no active ID card")
    if "print" in item.key.lower() and card.print_status != cards.PRINTED:
        return _missing(item, f"card {card.card_number} is "
                              f"{card.print_status.lower()}")
    return True, f"idcard:{card.card_number}", ""


# ── Library / textbooks / locker ────────────────────────────────────

def _loans(sid: str) -> list[Any]:
    from education_system.systems.sixth_form.domain.academics.library import (
        library as _lib,
    )
    return _lib.list_loans(student_id=sid)


def library_rule(sid: str, item: Any) -> Result:
    """The library lends against the student record (there is no
    separate account), so a loan shows the learner is using it; no loan
    proves nothing."""
    loans = _loans(sid)
    if loans:
        return True, f"library:loan {loans[0].loan_id}", ""
    return _CANT_TELL


def textbooks_rule(sid: str, item: Any) -> Result:
    from education_system.systems.sixth_form.domain.academics.library import (
        library as _lib,
    )
    books = [lo for lo in _loans(sid) if lo.status == "Active"
             and getattr(_lib.get_book(lo.book_id), "item_type", None)
             == "Textbook"]
    if books:
        return True, f"textbooks:{len(books)} on loan", ""
    return _CANT_TELL


def locker_rule(sid: str, item: Any) -> Result:
    from education_system.systems.sixth_form.domains.operations.domain.lockers import (
        lockers as _lk,
    )
    a = _lk.locker_for_student(sid)
    if a is not None:
        return True, f"locker:{a.allocation_id}", ""
    if not _lk.list_banks(active_only=True):
        return _CANT_TELL
    return _missing(item, "no locker is allocated to the learner")


# ── Student record: address and contacts ────────────────────────────

def address_rule(sid: str, item: Any) -> Result:
    s = _student(sid)
    if s is None:
        return _CANT_TELL
    if (s.address or "").strip() and (s.postcode or "").strip():
        return True, "student:address", ""
    return _missing(item, "the student record has no home address and "
                          "postcode")


def proof_of_address_rule(sid: str, item: Any) -> Result:
    """Proof is a document seen by staff; the address must be on the
    record first."""
    ok, _ref, msg = address_rule(sid, item)
    return (False, None, msg) if ok is False else _CANT_TELL


def _contacts(sid: str) -> list[Any]:
    from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
        parent_contacts as _pc,
    )
    return _pc.contacts_for_student(sid)


def emergency_contact_rule(sid: str, item: Any) -> Result:
    s = _student(sid)
    if s is not None and (s.emergency_contact_name or "").strip() and \
            (s.emergency_contact_phone or "").strip():
        return True, "student:emergency contact", ""
    for c in _contacts(sid):
        if c.is_emergency_contact and (c.primary_phone or c.secondary_phone):
            return True, f"contact:{c.contact_id}", ""
    return _missing(item, "no emergency contact with a phone number is on "
                          "the record")


def parent_contact_rule(sid: str, item: Any) -> Result:
    for c in _contacts(sid):
        if c.primary_phone or c.secondary_phone or c.email:
            return True, f"contact:{c.contact_id}", ""
    return _missing(item, "no parent / carer contact with a phone or "
                          "e-mail is on the record")


def contact_details_rule(sid: str, item: Any) -> Result:
    s = _student(sid)
    if s is None:
        return _CANT_TELL
    if (s.phone or s.personal_email) and (s.address or "").strip():
        return True, "student:contact details", ""
    return _missing(item, "the student record needs a phone or personal "
                          "e-mail and a home address")


# ── Medical / SEND ──────────────────────────────────────────────────

def medical_rule(sid: str, item: Any) -> Result:
    from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
        medical_records as _med,
    )
    try:
        prof = _med.get_profile(sid)
    except PermissionError:
        return _CANT_TELL
    if prof is not None:
        return True, "medical:profile", ""
    return _missing(item, "no medical profile is recorded for the learner")


def send_rule(sid: str, item: Any) -> Result:
    """A SEND entry shows the information was recorded; no entry may mean
    the learner has no SEND need, so it proves nothing."""
    from education_system.systems.sixth_form.domain.pastoral.send import (
        send as _send,
    )
    try:
        entries = _send.entries_for_student(sid)
    except PermissionError:
        return _CANT_TELL
    if entries:
        return True, f"send:{entries[0].entry_id}", ""
    return _CANT_TELL


# ── Bursary ─────────────────────────────────────────────────────────

def _applications(sid: str, item: Any) -> list[Any]:
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _br,
    )
    year = _year_of(item)
    return [a for a in _br.list_applications(student_id=sid)
            if a.status not in ("Cancelled", "Withdrawn")
            and (not year or a.academic_year in (None, year))]


def bursary_applied_rule(sid: str, item: Any) -> Result:
    apps = _applications(sid, item)
    if apps:
        return True, f"bursary:{apps[0].application_id}", ""
    return _missing(item, "no bursary application is on file for this "
                          "year (mark it N/A if the learner is not "
                          "applying)")


def bursary_reviewed_rule(sid: str, item: Any) -> Result:
    apps = _applications(sid, item)
    if not apps:
        return _missing(item, "no bursary application is on file for this "
                              "year")
    decided = [a for a in apps if a.status not in
               ("Draft", "Submitted", "Awaiting Evidence", "Under Review")]
    if decided:
        return True, f"bursary:{decided[0].application_id}", ""
    return _missing(item, f"bursary application #{apps[0].application_id} "
                          f"is still {apps[0].status.lower()}")


# ── Matching task keys to rules ─────────────────────────────────────

#: (all words that must appear in the lower-cased key, words that must
#: not, rule). First match wins.
_MATCHERS: tuple[tuple[tuple[str, ...], tuple[str, ...], Rule], ...] = (
    (("logon",), (), logon_tested_rule),
    (("log on",), (), logon_tested_rule),
    (("library",), (), library_rule),
    (("textbook",), (), textbooks_rule),
    (("locker",), (), locker_rule),
    (("id card",), (), id_card_rule),
    (("tutor group",), (), tutor_group_rule),
    (("tutor",), ("group",), meet_tutor_rule),
    (("timetable",), (), timetable_rule),
    (("class group",), (), class_groups_rule),
    (("emergency contact",), (), emergency_contact_rule),
    (("parent", "contact"), ("consent",), parent_contact_rule),
    (("contact details",), (), contact_details_rule),
    (("proof of address",), (), proof_of_address_rule),
    (("address",), (), address_rule),
    (("medical",), ("consent",), medical_rule),
    (("send",), (), send_rule),
    (("bursary", "review"), (), bursary_reviewed_rule),
    (("bursary",), (), bursary_applied_rule),
    (("account",), ("library", "acceptable"), it_account_rule),
)


def rule_for(key: str) -> Rule | None:
    """The record rule for a task key, or None (consent and ID tasks have
    their own rules in :mod:`onboarding`)."""
    if not key or key in ob.CONSENT_ITEMS or key in ob.ID_ITEMS:
        return None
    low = key.lower()
    for need, avoid, rule in _MATCHERS:
        if need == ("send",):
            words = set(low.replace("/", " ").split())
            if "send" not in words:
                continue
        elif not all(w in low for w in need):
            continue
        if any(w in low for w in avoid):
            continue
        return rule
    return None


class _MatchedRules(dict):
    """The onboarding rule registry, falling back to :func:`rule_for` for
    a key nobody registered — so a task added by hand under a new name
    ("Tutor group assigned") is checked against its record too."""

    def get(self, key, default=None):
        if key in self:
            return self[key]
        rule = rule_for(key) if isinstance(key, str) else None
        return rule if rule is not None else default


def _install_matcher() -> None:
    if not isinstance(ob.EVIDENCE_RULES, _MatchedRules):
        ob.EVIDENCE_RULES = _MatchedRules(ob.EVIDENCE_RULES)


def register_keys(keys: Iterable[str]) -> list[str]:
    """Register the matching rule for each key that has one (keeps any
    rule already registered for it). Returns the keys registered."""
    out = []
    for key in keys:
        if key in ob.EVIDENCE_RULES:
            continue
        rule = rule_for(key)
        if rule is not None:
            ob.register_evidence_rule(key, rule)
            out.append(key)
    return out


def _register_builtin() -> None:
    _install_matcher()
    register_keys({t for tasks in ob.TEMPLATES.values()
                   for t, _c, _r in tasks})
    try:
        from education_system.systems.sixth_form.domain.admissions.onboarding import (
            consent_followups as _cf,
            induction as _ind,
        )
        _cf.register_rules()
        _ind.register_rules()
    except Exception:  # noqa: BLE001 — the other rules still apply
        logger.exception("Onboarding follow-up / induction rules not "
                         "registered")


_register_builtin()


# ── Resync ──────────────────────────────────────────────────────────

@dataclass
class ResyncResult:
    checklists: int = 0
    ticked: list[str] = field(default_factory=list)
    reopened: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.checklists} checklist(s) checked: "
                f"{len(self.ticked)} task(s) ticked from records, "
                f"{len(self.reopened)} re-opened (record gone)"
                + (f", {len(self.errors)} error(s)" if self.errors else ""))


def _record_ticked(item: Any) -> bool:
    return (item.evidence_ref or "").startswith(REF_PREFIXES)


def resync(checklist_id: int, *, _result: ResyncResult | None = None
           ) -> ResyncResult:
    """Tick the open tasks on one checklist whose record now exists, and
    re-open those ticked from a record that has gone. Hand-evidenced
    tasks (written evidence, N/A) and consent / ID tasks (kept in line by
    their own modules) are left alone."""
    ob._require_writer("updating onboarding tasks from records")
    res = _result or ResyncResult()
    c = ob.get_checklist(checklist_id)
    if c is None:
        raise ob.ValidationError(f"No checklist #{checklist_id}")
    if c.is_archived or c.status == "Cancelled":
        return res
    res.checklists += 1
    for item in ob.list_items(checklist_id=checklist_id):
        rule = ob.EVIDENCE_RULES.get(item.key)
        if rule is None or ob.is_consent_item(item) or item.key in ob.ID_ITEMS:
            continue
        label = f"{c.student_id}: {item.task_name}"
        try:
            if item.is_done:
                if item.status != "Done" or not _record_ticked(item):
                    continue
                ok, _ref, msg = rule(c.student_id, item)
                if ok is False:
                    ob.set_item_status(item.item_id, "Pending")
                    note = f"Re-opened by record check: {msg}"
                    ob.update_item(item.item_id, {"notes": (
                        f"{item.notes}\n{note}" if item.notes else note)})
                    res.reopened.append(label)
                continue
            if item.evidence or item.awaiting_second_check:
                continue
            ok, _ref, _msg = rule(c.student_id, item)
            if ok:
                ob.set_item_status(item.item_id, "Done",
                                   completed_by="record check")
                res.ticked.append(label)
        except Exception as exc:  # noqa: BLE001 — one task never stops the rest
            logger.exception("Resync of onboarding task #%s", item.item_id)
            res.errors.append(f"{label}: {exc}")
    return res


def resync_all(*, academic_year: str | None = None) -> ResyncResult:
    """:func:`resync` over every open checklist (optionally one year)."""
    ob._require_writer("updating onboarding tasks from records")
    res = ResyncResult()
    for c in ob.list_checklists(open_only=True, academic_year=academic_year):
        try:
            resync(c.checklist_id, _result=res)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Resync of checklist #%s", c.checklist_id)
            res.errors.append(f"checklist #{c.checklist_id}: {exc}")
    return res

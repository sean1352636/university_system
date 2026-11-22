"""Onboarding workflow — choosing a learner's template, owners and role
queues, bulk actions, and Year 13 re-onboarding.

Everything here goes through the foundation functions in
:mod:`onboarding` (``open_enrolment_checklist``, ``set_item_status``,
``update_item``), so the evidence / N/A / completion rules and the
history (``onboarding_history``) always apply.

* :func:`choose_template` picks the base template and any add-ons from
  the learner's real records: the enrolment (year group, start date
  against the first teaching term), the enrolment identity check and the
  admissions identity check (right to study / visa), nationality, the
  SEND register, care records and the admissions application flags.
* :func:`open_for_learner` opens (or reuses) the year's checklist from
  that choice and adds the add-ons.
* :func:`my_queue` lists open tasks for a member of staff (assigned to
  them, or unassigned in a queue their job puts them in) or for a role.
* ``bulk_*`` act on many tasks / learners and report per item.
* :func:`reonboard_cohort` opens a short "Year 13 return" checklist for
  learners back for Year 13.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)

logger = logging.getLogger(__name__)

ValidationError = ob.ValidationError

#: A start this many days after the first teaching term began counts as a
#: mid-year join (the first fortnight is the normal enrolment window).
MID_YEAR_GRACE_DAYS = 14

#: Nationalities that never need a visa to study (anything else, with no
#: right-to-study outcome recorded yet, is treated as international).
_NO_VISA_NATIONALITIES = frozenset({
    "british", "uk", "united kingdom", "gb", "great britain", "english",
    "scottish", "welsh", "northern irish", "irish", "ireland",
    "british citizen", "uk national"})
_VISA_RIGHT = "Yes - visa (check expiry)"


# ── Choosing a template ───────────────────────────────────────────

@dataclass
class TemplateChoice:
    template: str
    learner_type: str
    addons: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    #: Signals that could not be read (and so were not used).
    not_checked: list[str] = field(default_factory=list)
    #: Add-on task key -> why it does not apply (set to N/A on opening).
    not_applicable: dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return " + ".join([self.learner_type, *self.addon_types])

    @property
    def addon_types(self) -> list[str]:
        out = []
        for name in self.addons:
            t = tpl.get_template(name)
            out.append(t.learner_type if t and t.learner_type else name)
        return out


def _enrolments():
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments,
    )
    return enrolments


def _resolve_enrolment(student_id: str, enrolment: Any) -> Any:
    enr = _enrolments()
    if enrolment is None:
        live = [e for e in enr.list_enrolments(student_id=student_id)
                if e.is_live]
        return live[0] if live else None
    if isinstance(enrolment, int | str):
        e = enr.get_enrolment(int(enrolment))
        if e is None:
            raise ValidationError(f"No enrolment #{enrolment}")
        return e
    return enrolment


def _applicant_for(student_id: str, notes: list[str]) -> Any:
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            admissions, conversion,
        )
        rec = conversion.conversion_for_student(student_id)
        return admissions.get_applicant(rec.applicant_id) if rec else None
    except Exception as e:  # noqa: BLE001 — a signal, not a requirement
        notes.append(f"admissions application not read ({e})")
        return None


def _first_term_start(year: str, notes: list[str]) -> str:
    """The first teaching term's start (academic-year register), else the
    register's year start, else 1 September (the note says which)."""
    fallback = f"{year[:4]}-09-01"
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (
            academic_year as ay,
        )
        y = ay.get_year_by_name(year)
        if y is None:
            notes.append(f"mid-year: {year} is not in the academic-year "
                         f"register (term start taken as {fallback})")
            return fallback
        starts = sorted(t.start_date for t in ay.list_terms(year_id=y.year_id)
                        if t.start_date and getattr(t, "is_teaching", True))
        if starts:
            return starts[0]
        start = max(y.start_date or fallback, fallback)
        notes.append(f"mid-year: no terms set up for {year} ({start} used)")
        return start
    except Exception as e:  # noqa: BLE001
        notes.append(f"mid-year: term dates not read ({e}; {fallback} used)")
        return fallback


def _international(student_id: str, student: Any, applicant: Any,
                   reasons: list[str], notes: list[str]) -> bool:
    rights: list[tuple[str, str | None, str | None]] = []
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            identity_checks as idc,
        )
        c = idc.get_check(student_id)
        if c is not None and idc.can_see_immigration():
            rights.append(("enrolment ID check", c.right_to_study,
                           c.visa_type))
        elif c is not None and (c.right_to_study or c.visa_type):
            notes.append("right to study: restricted for this user")
    except Exception as e:  # noqa: BLE001
        notes.append(f"enrolment ID check not read ({e})")
    if applicant is not None:
        try:
            from education_system.systems.sixth_form.domain.admissions import (
                applicant_details,
            )
            rec = applicant_details.get_identity(applicant.applicant_id)
            if rec is not None:
                rights.append(("admissions ID check", rec.right_to_study,
                               rec.visa_type))
        except Exception as e:  # noqa: BLE001
            notes.append(f"admissions ID check not read ({e})")
    for source, right, visa in rights:
        if right == _VISA_RIGHT or (visa or "").strip():
            reasons.append(f"international: {source} records a visa")
            return True
    if any((r or "").startswith("Yes") for _s, r, _v in rights):
        return False                    # settled / citizen: no visa needed
    nationality = ((getattr(student, "nationality", None) or "")
                   or (getattr(applicant, "nationality", None) or "")).strip()
    if nationality and nationality.lower() not in _NO_VISA_NATIONALITIES:
        reasons.append(f"international: nationality {nationality} and no "
                       "right to study confirmed yet")
        return True
    return False


def _send_level(student_id: str, applicant: Any, reasons: list[str],
                notes: list[str]) -> str | None:
    """'EHCP', 'SEN' or None."""
    level = None
    try:
        from education_system.systems.sixth_form.domain.pastoral.send import (
            send,
        )
        for e in send.entries_for_student(student_id):
            if e.status in ("Exited", "Archived") or e.register_status in (
                    "Exited", "Monitoring"):
                continue
            if e.register_status == "EHCP":
                reasons.append("SEND: EHCP on the SEND register")
                return "EHCP"
            level = "SEN"
            reasons.append(f"SEND: {e.register_status} on the SEND register")
    except Exception as e:  # noqa: BLE001
        notes.append(f"SEND register not read ({e})")
    if applicant is not None and applicant.ehcp:
        reasons.append("SEND: EHCP declared on the application")
        return "EHCP"
    if level is None and applicant is not None and applicant.lldd:
        reasons.append("SEND: learning difficulty / disability declared on "
                       "the application")
        level = "SEN"
    return level


def _care(student_id: str, applicant: Any, reasons: list[str],
          notes: list[str]) -> tuple[bool, bool]:
    """(looked after, care leaver)."""
    lac = leaver = False
    try:
        from education_system.systems.sixth_form.domain.pastoral.wellbeing import (
            wellbeing,
        )
        for r in wellbeing.list_care_records(student_id=student_id,
                                             active_only=True):
            if r.care_status.startswith("Care Leaver"):
                leaver = True
            else:
                lac = True
        if lac or leaver:
            reasons.append("care: active care record")
    except Exception as e:  # noqa: BLE001 — pastoral-only records
        notes.append(f"care records not read ({type(e).__name__})")
    if applicant is not None and (applicant.looked_after
                                  or applicant.care_leaver):
        lac = lac or bool(applicant.looked_after)
        leaver = leaver or bool(applicant.care_leaver)
        reasons.append("care: flagged on the application")
    return lac, leaver


def _template_for(learner_type: str, fallback: str, choice: TemplateChoice
                  ) -> str:
    t = tpl.for_learner_type(learner_type)
    if t is not None and t.kind == "base":
        return t.name
    if tpl.exists(fallback):
        return fallback
    choice.not_checked.append(f"no active template for {learner_type}; "
                              f"using {ob.DEFAULT_TEMPLATE}")
    return ob.DEFAULT_TEMPLATE


def choose_template(student_id: str, *, enrolment: Any = None,
                    applicant: Any = None) -> TemplateChoice:
    """Pick the template (and add-ons) for a learner from their records.

    Base, in order: Year 13 with a Year 12 here → Year 13 return; a visa
    (or a non-UK/Irish nationality with no right to study yet) →
    international; Year 13 with no Year 12 here → Year 13 transfer-in; a
    start more than :data:`MID_YEAR_GRACE_DAYS` after the first teaching
    term began → mid-year joiner; else Year 12 new starter. Add-ons:
    SEND / EHCP (SEND register or the application), looked-after / care
    leaver (care records or the application). ``enrolment`` (an
    Enrolment or id; default the learner's live one) and ``applicant``
    (default: the application they were converted from) can be given.
    """
    tpl.init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    student = students.get_student(student_id)
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    choice = TemplateChoice(template=ob.DEFAULT_TEMPLATE,
                            learner_type=tpl.YEAR12)
    reasons, notes = choice.reasons, choice.not_checked
    e = _resolve_enrolment(student_id, enrolment)
    if e is None:
        notes.append("no live enrolment (year group and start date unknown)")
    if applicant is None:
        applicant = _applicant_for(student_id, notes)

    def pick(ltype: str, fallback: str) -> None:
        choice.learner_type = ltype
        choice.template = _template_for(ltype, fallback, choice)

    prior_y12 = False
    if e is not None and e.year_group == 13:
        prior_y12 = any(
            x.year_group == 12 and x.academic_year < e.academic_year
            and x.status != "Withdrawn"
            for x in _enrolments().list_enrolments(student_id=student_id))
    if prior_y12:
        reasons.append(f"Year 13 in {e.academic_year} after Year 12 here")
        pick(tpl.YEAR13_RETURN, tpl.YEAR13_RETURN_TEMPLATE)
    elif _international(student_id, student, applicant, reasons, notes):
        pick(tpl.INTERNATIONAL, tpl.INTERNATIONAL_TEMPLATE)
    elif e is not None and e.year_group == 13:
        reasons.append(f"Year 13 in {e.academic_year} with no Year 12 here")
        pick(tpl.YEAR13_TRANSFER, tpl.YEAR13_TRANSFER_TEMPLATE)
    else:
        start = (e.start_date if e is not None else None)
        term = _first_term_start(e.academic_year, notes) if e else None
        if start and term and _dt.date.fromisoformat(start) > (
                _dt.date.fromisoformat(term)
                + _dt.timedelta(days=MID_YEAR_GRACE_DAYS)):
            reasons.append(f"starts {start}, after the first term began "
                           f"({term})")
            pick(tpl.MID_YEAR, tpl.MID_YEAR_TEMPLATE)
        else:
            pick(tpl.YEAR12, ob.DEFAULT_TEMPLATE)
    if choice.learner_type == tpl.YEAR13_RETURN:
        return choice                    # add-ons were applied in Year 12
    send_level = _send_level(student_id, applicant, reasons, notes)
    if send_level:
        addon = tpl.for_learner_type(tpl.SEND)
        if addon is not None:
            choice.addons.append(addon.name)
            if send_level != "EHCP":
                choice.not_applicable[tpl.EHCP_REVIEW_KEY] = (
                    "No EHCP: SEN support only")
    lac, leaver = _care(student_id, applicant, reasons, notes)
    if lac or leaver:
        addon = tpl.for_learner_type(tpl.CARE)
        if addon is not None:
            choice.addons.append(addon.name)
            if leaver and not lac:
                choice.not_applicable[tpl.PEP_KEY] = (
                    "Care leaver, not looked after: no PEP (personal "
                    "adviser instead)")
    return choice


@dataclass
class OpenResult:
    checklist: Any
    choice: TemplateChoice
    added: dict[str, list[str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def open_for_learner(student_id: str, *, enrolment: Any = None,
                     applicant: Any = None, template: str | None = None,
                     extra_tasks: list[tuple[str, str, bool]] | None = None,
                     due_date: str | None = None, notes: str | None = None,
                     assigned_to: str | None = None,
                     academic_year: str | None = None) -> OpenResult:
    """Open (or reuse) the learner's checklist for the enrolment's year
    from :func:`choose_template` (or ``template``), then add the add-ons
    and mark add-on tasks that do not apply as N/A (with the reason).
    ``academic_year`` is used only when the learner has no enrolment."""
    ob._require_writer("opening enrolment checklists")
    choice = choose_template(student_id, enrolment=enrolment,
                             applicant=applicant)
    if template:
        choice.template = template
        choice.reasons.append(f"template {template} chosen by the caller")
    e = _resolve_enrolment(student_id, enrolment)
    chk = ob.open_enrolment_checklist(
        student_id, template=choice.template, extra_tasks=extra_tasks,
        due_date=due_date, notes=notes, assigned_to=assigned_to,
        academic_year=e.academic_year if e is not None else academic_year,
        enrolment_id=e.enrolment_id if e is not None else None,
        learner_type=choice.label)
    result = OpenResult(checklist=chk, choice=choice)
    for name in choice.addons:
        try:
            result.added[name] = tpl.apply_template(chk.checklist_id, name)
        except ValidationError as ex:
            result.problems.append(f"{name}: {ex}")
    if choice.not_applicable:
        for item in ob.list_items(checklist_id=chk.checklist_id):
            why = choice.not_applicable.get(item.key)
            if why and item.status == "Pending":
                try:
                    ob.set_item_status(item.item_id, "N/A", reason=why)
                except ValidationError as ex:
                    result.problems.append(f"{item.task_name}: {ex}")
    out = ob.get_checklist(chk.checklist_id)
    result.checklist = out or chk
    return result


# ── Owners, staff and queues ──────────────────────────────────────

#: Staff job role -> the owner-role queues it works.
STAFF_ROLE_QUEUES: dict[str, tuple[str, ...]] = {
    "Administrator": ("Admissions",), "Receptionist": ("Admissions",),
    "Head of Sixth Form": ("Admissions", "Pastoral"),
    "IT Support": ("IT",), "Pastoral Manager": ("Pastoral",),
    "Counsellor": ("Pastoral",), "Head of Year": ("Pastoral",),
    "Tutor": ("Tutor",), "Finance Officer": ("Finance",),
    "Exams Officer": ("Exams",), "Librarian": ("Library",),
    "SENCO": ("SEND",), "Safeguarding Lead (DSL)": ("Safeguarding",),
    "Deputy DSL": ("Safeguarding",),
}


@dataclass
class StaffMember:
    staff_id: str
    name: str
    job_role: str
    username: str | None
    email: str | None
    is_tutor: bool = False
    is_dsl: bool = False

    @property
    def queues(self) -> tuple[str, ...]:
        q = list(STAFF_ROLE_QUEUES.get(self.job_role, ()))
        if self.is_tutor and "Tutor" not in q:
            q.append("Tutor")
        if self.is_dsl and "Safeguarding" not in q:
            q.append("Safeguarding")
        return tuple(q)

    @property
    def ids(self) -> set[str]:
        """Values an item's ``assigned_to`` may hold for this person."""
        return {v.lower() for v in (self.staff_id, self.username, self.email)
                if v}


def find_staff(value: str) -> StaffMember | None:
    """An active member of staff by staff id, login username or e-mail."""
    v = (value or "").strip().lower()
    if not v:
        return None
    from education_system.systems.sixth_form.domain.staff import staff
    for s in staff.list_staff(active_only=True):
        username = staff.login_username(s.staff_id)
        if v in {x.lower() for x in (s.staff_id, s.email, username) if x}:
            return StaffMember(
                staff_id=s.staff_id, name=f"{s.first_name} {s.last_name}",
                job_role=s.role, username=username, email=s.email,
                is_tutor=bool(s.is_tutor), is_dsl=bool(s.is_dsl))
    return None


#: "Not given" (``None`` clears an assignee / owner).
_UNSET: Any = object()


def _owner_role(value: str | None) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    match = next((o for o in tpl.OWNER_ROLES if o.lower() == v.lower()), None)
    if match is None:
        raise ValidationError("Owner must be one of: "
                              + ", ".join(tpl.OWNER_ROLES))
    return match


def assign_item(item_id: int, *, assignee: Any = _UNSET,
                owner_role: Any = _UNSET) -> Any:
    """Set a task's owner role and/or assignee (an active member of staff,
    stored by staff id; ``None`` clears). Through ``update_item``."""
    payload: dict[str, Any] = {}
    if owner_role is not _UNSET:
        payload["owner_role"] = _owner_role(owner_role)
    if assignee is not _UNSET:
        if assignee in (None, ""):
            payload["assigned_to"] = None
        else:
            who = find_staff(str(assignee))
            if who is None:
                raise ValidationError(
                    f"{assignee!r} is not an active member of staff (staff "
                    "id, login or e-mail)")
            payload["assigned_to"] = who.staff_id
    if not payload:
        raise ValidationError("Give an assignee or an owner role")
    return ob.update_item(item_id, payload)


@dataclass
class QueueRow:
    item: Any
    checklist_id: int
    student_id: str
    student_name: str
    academic_year: str | None
    why: str                       # "assigned" or the queue name

    @property
    def overdue(self) -> bool:
        return bool(self.item.due_date
                    and self.item.due_date < _dt.date.today().isoformat())


def _tutor_students(member: StaffMember) -> set[str]:
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as tg,
        )
        names = {member.staff_id.lower(), member.name.lower(),
                 *(x.lower() for x in (member.username,) if x)}
        out: set[str] = set()
        for g in tg.list_groups():
            if {(g.tutor or "").lower(), (g.co_tutor or "").lower()} & names:
                out.update(tg.list_members(g.tutor_group_id))
        return out
    except Exception:  # noqa: BLE001
        logger.debug("tutor groups not read", exc_info=True)
        return set()


def my_queue(who: str, *, academic_year: str | None = None,
             overdue_only: bool = False) -> list[QueueRow]:
    """Open tasks (not Done / N/A) on open checklists for ``who``:

    * an owner role (``"IT"``, ``"Finance"`` …) — every task in that queue;
    * a member of staff (staff id, login or e-mail) — tasks assigned to
      them, plus unassigned tasks in the queues their job works (a
      tutor's Tutor queue is limited to their tutor groups' learners).

    Sensitive tasks are masked for readers without the rights.
    """
    ob.init_db()
    w = (who or "").strip()
    role = next((o for o in tpl.OWNER_ROLES if o.lower() == w.lower()), None)
    member = None if role else find_staff(w)
    if role is None and member is None:
        raise ValidationError(f"{who!r} is neither an owner role "
                              f"({', '.join(tpl.OWNER_ROLES)}) nor an "
                              "active member of staff")
    clauses = ["c.archived_at IS NULL",
               "c.status IN ('Not Started', 'In Progress', 'On Hold')",
               "i.status NOT IN ('Done', 'N/A')"]
    args: list[Any] = []
    if academic_year:
        clauses.append("c.academic_year = ?")
        args.append(academic_year)
    with ob._connect() as conn:
        rows = conn.execute(
            "SELECT i.*, c.student_id AS c_student, c.academic_year AS c_year "
            "FROM onboarding_items i JOIN onboarding_checklists c "
            "ON c.checklist_id = i.checklist_id WHERE "
            + " AND ".join(clauses)
            + " ORDER BY COALESCE(i.due_date, '9999'), i.item_id",
            args).fetchall()
        names = ob._names_for(conn, {r["c_student"] for r in rows})
    tutees = (_tutor_students(member)
              if member is not None and "Tutor" in member.queues else set())
    out: list[QueueRow] = []
    for r in rows:
        owner = (r["owner_role"] or "").lower()
        assigned = (r["assigned_to"] or "").lower()
        if role is not None:
            if owner != role.lower():
                continue
            why = role
        else:
            assert member is not None
            if assigned:
                if assigned not in member.ids:
                    continue
                why = "assigned"
            else:
                queue = next((q for q in member.queues
                              if q.lower() == owner), None)
                if queue is None or (queue == "Tutor"
                                     and r["c_student"] not in tutees):
                    continue
                why = queue
        item = ob._row_item(r)
        out.append(QueueRow(item=item, checklist_id=r["checklist_id"],
                            student_id=r["c_student"],
                            student_name=names.get(r["c_student"], ""),
                            academic_year=r["c_year"], why=why))
    if overdue_only:
        out = [q for q in out if q.overdue]
    by_student: dict[str, list[Any]] = {}
    for q in out:
        if q.item.sensitive:
            by_student.setdefault(q.student_id, []).append(q.item)
    for sid, items in by_student.items():
        ob._visible_items(items, sid)
    return out


# ── Bulk actions ──────────────────────────────────────────────────

@dataclass
class BulkResult:
    done: list[int] = field(default_factory=list)
    failed: list[tuple[int, str]] = field(default_factory=list)

    def lines(self) -> list[str]:
        return ([f"{len(self.done)} task(s) updated"]
                + [f"#{i}: {msg}" for i, msg in self.failed])


def bulk_set_status(item_ids: list[int], status: str, *,
                    reason: str | None = None, evidence: str | None = None,
                    completed_by: str | None = None) -> BulkResult:
    """``set_item_status`` on each task; one refused task does not stop
    the rest (each refusal is reported with its reason)."""
    ob._require_writer("changing onboarding tasks")
    result = BulkResult()
    for item_id in dict.fromkeys(item_ids):
        try:
            ob.set_item_status(int(item_id), status, reason=reason,
                               evidence=evidence, completed_by=completed_by)
            result.done.append(int(item_id))
        except (ValidationError, ValueError, TypeError) as e:
            result.failed.append((item_id, str(e)))
    return result


def bulk_assign(item_ids: list[int], *, assignee: Any = _UNSET,
                owner_role: Any = _UNSET) -> BulkResult:
    """:func:`assign_item` on each task (the assignee is checked once)."""
    ob._require_writer("changing onboarding tasks")
    if assignee not in (_UNSET, None, "") and find_staff(str(assignee)) is None:
        raise ValidationError(f"{assignee!r} is not an active member of "
                              "staff (staff id, login or e-mail)")
    if owner_role is not _UNSET:
        _owner_role(owner_role)
    result = BulkResult()
    for item_id in dict.fromkeys(item_ids):
        try:
            assign_item(int(item_id), assignee=assignee,
                        owner_role=owner_role)
            result.done.append(int(item_id))
        except (ValidationError, ValueError, TypeError) as e:
            result.failed.append((item_id, str(e)))
    return result


@dataclass
class CohortLine:
    student_id: str
    result: str                     # opened / reused / skipped / failed
    checklist_id: int | None = None
    template: str | None = None
    detail: str = ""

    def line(self) -> str:
        return (f"{self.student_id}: {self.result}"
                + (f" #{self.checklist_id}" if self.checklist_id else "")
                + (f" ({self.template})" if self.template else "")
                + (f" — {self.detail}" if self.detail else ""))


def _year_lists(student_id: str, year: str) -> list[Any]:
    return [c for c in ob.list_checklists(student_id=student_id,
                                          academic_year=year)]


def bulk_open_for_cohort(academic_year: str, *, year_group: int | None = None,
                         tutor_group: str | None = None,
                         template: str | None = None) -> list[CohortLine]:
    """Open the year's checklist for every live enrolment in
    ``academic_year`` (optionally one year group / tutor group), from
    ``template`` or each learner's :func:`choose_template` choice. A
    learner who already has a checklist for that year is skipped (so a
    re-run is safe); each learner gets a line."""
    ob._require_writer("opening enrolment checklists")
    if template and not tpl.exists(template):
        raise ValidationError(f"Unknown template {template!r}")
    enr = _enrolments().list_enrolments(academic_year=academic_year,
                                        year_group=year_group)
    lines: list[CohortLine] = []
    for e in enr:
        if not e.is_live:
            continue
        if tutor_group and (e.tutor_group or "").lower() != tutor_group.lower():
            continue
        have = _year_lists(e.student_id, academic_year)
        if have:
            c = have[0]
            lines.append(CohortLine(e.student_id, "skipped", c.checklist_id,
                                    c.template_name,
                                    f"already has a {c.status} checklist "
                                    f"for {academic_year}"))
            continue
        try:
            res = open_for_learner(e.student_id, enrolment=e,
                                   template=template)
            lines.append(CohortLine(
                e.student_id, "opened", res.checklist.checklist_id,
                res.checklist.template_name,
                "; ".join([res.choice.label, *res.problems])))
        except Exception as ex:  # noqa: BLE001 — reported per learner
            lines.append(CohortLine(e.student_id, "failed", detail=str(ex)))
    return lines


def reonboard_cohort(from_year: str, to_year: str) -> list[CohortLine]:
    """Open a "Year 13 return" checklist in ``to_year`` for each learner
    with a live Year 13 enrolment in ``to_year`` who was in Year 12 here
    in ``from_year``. Idempotent: a learner who already has a checklist
    for ``to_year`` (any status) is skipped."""
    ob._require_writer("opening enrolment checklists")
    enr = _enrolments()
    y12 = {e.student_id for e in enr.list_enrolments(
        academic_year=from_year, year_group=12)}
    t = tpl.for_learner_type(tpl.YEAR13_RETURN)
    name = t.name if t is not None and t.kind == "base" else None
    if name is None:
        raise ValidationError("No active Year 13 return template")
    lines: list[CohortLine] = []
    for e in enr.list_enrolments(academic_year=to_year, year_group=13):
        if not e.is_live:
            continue
        if e.student_id not in y12:
            lines.append(CohortLine(e.student_id, "skipped",
                                    detail=f"not in Year 12 here in "
                                           f"{from_year} (a transfer-in)"))
            continue
        have = _year_lists(e.student_id, to_year)
        if have:
            c = have[0]
            lines.append(CohortLine(e.student_id, "skipped", c.checklist_id,
                                    c.template_name,
                                    f"already has a {c.status} checklist "
                                    f"for {to_year}"))
            continue
        try:
            chk = ob.open_enrolment_checklist(
                e.student_id, template=name, academic_year=to_year,
                enrolment_id=e.enrolment_id, learner_type=tpl.YEAR13_RETURN,
                notes=f"Year 13 return ({from_year} → {to_year})")
            lines.append(CohortLine(e.student_id, "opened", chk.checklist_id,
                                    name))
        except Exception as ex:  # noqa: BLE001 — reported per learner
            lines.append(CohortLine(e.student_id, "failed", detail=str(ex)))
    return lines

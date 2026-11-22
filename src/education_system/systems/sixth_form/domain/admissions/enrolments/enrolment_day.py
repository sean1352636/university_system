"""Enrolment day: one status board per learner, the confirmation
document and the ID-card details.

:func:`learner_status` pulls together, read-only, everything that has
to be done before a learner is ready to start: the enrolment itself, the
ID check and right to study, a photo, the key onboarding items (ID card,
IT account, timetable), the learner agreement and parent/guardian
acknowledgement (:mod:`agreements`), consents, class-group placement,
condition-of-funding gaps (when that module is installed) and the
fee/bursary position. Each item is done / not done (or information
only); the learner is **Ready** when every counted item is done.

:func:`confirmation_text` renders the enrolment confirmation / learner
agreement as plain text for the screen to print or turn into a PDF. Its
"college expectations" section comes from a staff-editable template kept
in ``enrolment_document_templates`` (every save is a new version).
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import logging
import textwrap
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    agreements as _agreements,
    enrolment_checks as _checks,
    enrolments as _enrolments,
)

logger = logging.getLogger(__name__)

ValidationError = _enrolments.ValidationError

READY, OUTSTANDING = "Ready", "Outstanding"

#: Board items fed from the onboarding checklist: label -> task names
#: (from the onboarding templates) that count.
ONBOARDING_ITEMS: dict[str, tuple[str, ...]] = {
    "ID card issued": ("Student ID card issued", "ID card issued"),
    "IT account set up": ("Email / network account created",
                          "Account & email account created",
                          "Account created"),
    "Timetable given": ("Timetable confirmed",),
}

#: The template the confirmation's expectations section comes from.
EXPECTATIONS_TEMPLATE = "college_expectations"
#: Used until staff save their own wording.
DEFAULT_EXPECTATIONS = """\
As a learner at the college I will:
- attend every timetabled lesson, tutorial and exam, on time, and tell
  the college the same day if I cannot attend;
- complete independent study and hand work in by the deadlines set;
- treat everyone in the college community with respect and follow the
  college's behaviour, safeguarding and IT acceptable-use policies;
- carry my ID card while on site;
- keep my contact details up to date and read college messages.

The college will:
- teach and support my programme of study and tell me how I am doing;
- give me a personal tutor and access to careers, wellbeing and
  learning support;
- keep my information safe and use it only as set out in its privacy
  notice."""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolment_document_templates (
    template_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    body         TEXT NOT NULL,
    saved_by     TEXT,
    saved_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_enrol_doc_tpl_name
    ON enrolment_document_templates(name);
"""

_READY_PATHS: set[str] = set()


def _init() -> None:
    key = str(_enrolments.DB_PATH)
    if key in _READY_PATHS:
        return
    _enrolments.init_db()
    conn = _enrolments._connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    _READY_PATHS.add(key)


@contextlib.contextmanager
def _db() -> Iterator[Any]:
    _init()
    conn = _enrolments._connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ── Templates ───────────────────────────────────────────────────────

def get_template(name: str = EXPECTATIONS_TEMPLATE) -> str:
    """The latest saved wording (the built-in default until saved)."""
    with _db() as conn:
        r = conn.execute(
            "SELECT body FROM enrolment_document_templates WHERE name = ? "
            "ORDER BY template_id DESC LIMIT 1", (name,)).fetchone()
    if r is not None:
        return r["body"]
    if name == EXPECTATIONS_TEMPLATE:
        return DEFAULT_EXPECTATIONS
    raise ValidationError(f"No template called {name!r}")


def save_template(body: str, name: str = EXPECTATIONS_TEMPLATE) -> str:
    """Save new wording (``admissions`` or ``students.manage``). Earlier
    versions are kept (:func:`template_versions`)."""
    _enrolments._require_writer("editing enrolment documents")
    text = (body or "").strip()
    if not text:
        raise ValidationError("The template cannot be empty")
    if len(text) > 20000:
        raise ValidationError("The template is too long (20,000 characters "
                              "at most)")
    with _db() as conn:
        conn.execute(
            "INSERT INTO enrolment_document_templates (name, body, saved_by) "
            "VALUES (?, ?, ?)", (name, text, _enrolments._actor()))
    return text


def template_versions(name: str = EXPECTATIONS_TEMPLATE
                      ) -> list[dict[str, Any]]:
    with _db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM enrolment_document_templates WHERE name = ? "
            "ORDER BY template_id DESC", (name,)).fetchall()]


# ── The board ───────────────────────────────────────────────────────

@dataclass
class StatusItem:
    name: str
    #: True / False; None = information only (not counted).
    done: bool | None
    detail: str = ""


@dataclass
class LearnerStatus:
    student_id: str
    name: str
    academic_year: str
    enrolment_id: int | None
    year_group: int | None
    tutor_group: str | None
    items: list[StatusItem] = field(default_factory=list)

    @property
    def outstanding(self) -> list[StatusItem]:
        return [i for i in self.items if i.done is False]

    @property
    def overall(self) -> str:
        return READY if self.enrolment_id and not self.outstanding \
            else OUTSTANDING

    @property
    def done_count(self) -> tuple[int, int]:
        counted = [i for i in self.items if i.done is not None]
        return sum(1 for i in counted if i.done), len(counted)


def _student(student_id: str) -> Any:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return _students.get_student(student_id)


def _safe(items: list[StatusItem], name: str, fn: Any, *args: Any) -> None:
    try:
        items.extend(fn(*args))
    except Exception as exc:  # noqa: BLE001 — one area never hides the rest
        logger.exception("Enrolment-day item %s", name)
        items.append(StatusItem(name, False, f"Could not check: {exc}"))


def _enrolment_items(e: _enrolments.Enrolment) -> list[StatusItem]:
    ok = e.is_live and e.status == "Enrolled"
    return [StatusItem("Enrolment", ok,
                       f"{e.status}, Year {e.year_group}"
                       + (f", started {e.start_date}" if e.start_date else "")
                       + (" (archived)" if e.is_archived else ""))]


def _identity_items(student_id: str) -> list[StatusItem]:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        course_changes as _cc,
        identity_checks as _idc,
    )
    s = _idc.check_status(student_id,
                          within_days=_cc.get_setting(_cc.VISA_WARNING_DAYS))
    rts_detail = {"confirmed": "Confirmed", "unknown": "Not confirmed",
                  "no": "Recorded as no right to study",
                  "restricted": "Needs checking"}[s.right_to_study]
    if s.visa:
        rts_detail += f"; visa {s.visa}" + (f" ({s.visa_expiry})"
                                            if s.visa_expiry else "")
    return [
        StatusItem("ID check", s.id_checked,
                   "Recorded" if s.id_checked else "Not recorded"),
        StatusItem("Right to study",
                   s.right_to_study == "confirmed" and s.visa != "expired",
                   rts_detail),
        StatusItem("Photo on file", s.has_photo,
                   "On file" if s.has_photo else "No photo"),
    ]


def _open_checklist_items(student_id: str) -> tuple[Any, list[Any]]:
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding as _ob,
    )
    lists = _ob.list_checklists(student_id=student_id, open_only=True) or \
        _ob.list_checklists(student_id=student_id)
    if not lists:
        return None, []
    chk = lists[0]
    return chk, _ob.list_items(checklist_id=chk.checklist_id)


def _onboarding_items(student_id: str) -> list[StatusItem]:
    chk, items = _open_checklist_items(student_id)
    if chk is None:
        return [StatusItem("Onboarding checklist", False, "Not opened")]
    out: list[StatusItem] = []
    required = [i for i in items if i.required]
    done = sum(1 for i in required if i.is_done)
    if not required:
        # An empty list (or one with no required task) proves nothing.
        out.append(StatusItem("Onboarding checklist", False,
                              f"{chk.status}: no required tasks on the "
                              "checklist"))
    else:
        out.append(StatusItem("Onboarding checklist",
                              done == len(required),
                              f"{chk.status}: {done}/{len(required)} "
                              "required item(s) done"))
    by_name = {i.key: i for i in items}
    for label, names in ONBOARDING_ITEMS.items():
        hit = next((by_name[n] for n in names if n in by_name), None)
        if label == "ID card issued":
            card = _active_card(student_id)
            if card is not None:
                out.append(StatusItem(label, True,
                                      f"Card {card.card_number} "
                                      f"({card.print_status})"))
                continue
        if hit is None:
            out.append(StatusItem(label, None, "Not on the checklist"))
        else:
            out.append(StatusItem(label, hit.is_done,
                                  hit.status + (f" {hit.completed_on}"
                                                if hit.completed_on else "")))
    return out


def _active_card(student_id: str) -> Any:
    try:
        from education_system.systems.sixth_form.domains.operations.domain.id_cards import (
            id_cards as _cards,
        )
        card = _cards.card_for("Student", student_id)
        return card if card is not None and card.status == _cards.ACTIVE \
            else None
    except Exception:  # noqa: BLE001 — the checklist item still counts
        logger.debug("ID card not read for %s", student_id, exc_info=True)
        return None


def _agreement_items(e: _enrolments.Enrolment) -> list[StatusItem]:
    st = _agreements.state(e.enrolment_id)
    out = [StatusItem("Learner agreement", st.learner is not None,
                      (f"Signed {st.learner.signed_on} ({st.learner.method})"
                       if st.learner else "Not signed"))]
    if st.parent_needed:
        p = st.parent
        out.append(StatusItem(
            "Parent/guardian acknowledgement", p is not None,
            (f"{p.signed_name} ({p.relationship}), {p.signed_on}"
             if p else "Not recorded")))
    else:
        out.append(StatusItem("Parent/guardian acknowledgement", None,
                              "Not needed (18 or over)"))
    return out


def _consent_items(student_id: str) -> list[StatusItem]:
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding as _ob,
    )
    out = []
    for task in _ob.CONSENT_ITEMS:
        state, _c = _ob.consent_state(student_id, task)
        out.append(StatusItem(f"Consent: {_ob.CONSENT_ITEMS[task][0]}",
                              state in ("Granted", "Refused"), state))
    return out


def _class_group_items(e: _enrolments.Enrolment) -> list[StatusItem]:
    gaps = [w for w in _checks._subject_warnings(e)
            if w.kind in ("class group missing", "class group full",
                          "enrolment")]
    if gaps:
        return [StatusItem("Class groups placed", False,
                           "; ".join(w.message for w in gaps))]
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    names = [g.group_name for g in _cg.groups_for_student(e.student_id)]
    return [StatusItem("Class groups placed", True, ", ".join(names))]


def _funding_items(e: _enrolments.Enrolment) -> list[StatusItem]:
    gaps = _checks.funding_gaps(e.enrolment_id)
    if gaps is None:
        return []
    return [StatusItem("Condition of funding", not gaps,
                       "; ".join(gaps) if gaps else "No gaps")]


def _money_items(e: _enrolments.Enrolment) -> list[StatusItem]:
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    see = _enrolments.can_write() or _guard.can(access.FINANCE)
    out: list[StatusItem] = []
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            funding as _funding,
        )
        due = _funding.fee_due(e.enrolment_id)
        if due.fee_paying:
            out.append(StatusItem(
                "Tuition fee raised", due.to_raise <= 0 and not due.problems,
                "; ".join(due.problems) if due.problems else
                (f"£{due.to_raise:.2f} still to raise" if due.to_raise > 0
                 else "Raised") if see else
                ("Needs attention" if due.problems or due.to_raise > 0
                 else "Raised")))
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 — fees optional on the board
        logger.debug("fee due not read", exc_info=True)
    try:
        from education_system.systems.sixth_form.domains.finance.domain.fees import (
            fees as _fees,
        )
        bal = _fees.student_balance(e.student_id)
        out.append(StatusItem(
            "Fees", None,
            (f"£{bal:.2f} outstanding" if bal else "Nothing outstanding")
            if see else ("Balance outstanding" if bal else "Nothing outstanding")))
    except Exception:  # noqa: BLE001 — finance optional on the board
        logger.debug("fees not read", exc_info=True)
    try:
        from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
            bursaries as _br,
        )
        apps = [a for a in _br.list_applications(student_id=e.student_id)
                if a.academic_year in (None, e.academic_year)]
        if apps:
            out.append(StatusItem("Bursary", None, "; ".join(
                f"{a.bursary_type}: {a.status}"
                + (f" £{a.amount_awarded:.2f}" if see and a.amount_awarded
                   else "") for a in apps)))
        else:
            out.append(StatusItem("Bursary", None, "No application"))
    except Exception:  # noqa: BLE001
        logger.debug("bursaries not read", exc_info=True)
    return out


def learner_status(student_id: str, academic_year: str | None = None
                   ) -> LearnerStatus:
    """The enrolment-day board for one learner (default: current year).
    Read-only; an area that cannot be read shows as not done with the
    reason, rather than raising."""
    year = academic_year or _enrolments.current_academic_year()
    s = _student(student_id)
    if s is None:
        raise ValidationError(f"No student with id {student_id}")
    e = _checks._enrolment_for(student_id, year)
    st = LearnerStatus(student_id, s.full_name, year,
                       e.enrolment_id if e else None,
                       e.year_group if e else None,
                       e.tutor_group if e else None)
    if e is None:
        st.items.append(StatusItem("Enrolment", False,
                                   f"No enrolment in {year}"))
        return st
    _safe(st.items, "Enrolment", _enrolment_items, e)
    _safe(st.items, "Identity", _identity_items, student_id)
    _safe(st.items, "Onboarding", _onboarding_items, student_id)
    _safe(st.items, "Agreements", _agreement_items, e)
    _safe(st.items, "Consents", _consent_items, student_id)
    _safe(st.items, "Class groups", _class_group_items, e)
    _safe(st.items, "Condition of funding", _funding_items, e)
    _safe(st.items, "Fees and bursary", _money_items, e)
    return st


def cohort_board(academic_year: str | None = None,
                 year_group: int | None = None) -> list[LearnerStatus]:
    """:func:`learner_status` for every live enrolment in the year,
    outstanding learners first."""
    year = academic_year or _enrolments.current_academic_year()
    rows = []
    for e in _enrolments.list_enrolments(academic_year=year,
                                         year_group=year_group):
        if not e.is_live:
            continue
        try:
            rows.append(learner_status(e.student_id, year))
        except Exception as exc:  # noqa: BLE001 — one learner never hides the rest
            logger.exception("Board row for %s", e.student_id)
            rows.append(LearnerStatus(
                e.student_id, e.student_id, year, e.enrolment_id,
                e.year_group, e.tutor_group,
                [StatusItem("Board", False, f"Could not build: {exc}")]))
    return sorted(rows, key=lambda r: (r.overall == READY, r.year_group or 0,
                                       r.name))


# ── Confirmation document ───────────────────────────────────────────

def _wrap(text: str, width: int = 76) -> list[str]:
    out = []
    for para in text.splitlines():
        out += textwrap.wrap(para, width, subsequent_indent="  "
                             if para.startswith("- ") else "") or [""]
    return out


def confirmation_text(enrolment_id: int, *, width: int = 76) -> str:
    """The enrolment confirmation and learner agreement for one
    enrolment, as plain text."""
    e = _enrolments.get_enrolment(int(enrolment_id))
    if e is None:
        raise ValidationError(f"No enrolment #{enrolment_id}")
    s = _student(e.student_id)
    if s is None:
        raise ValidationError(f"No student with id {e.student_id}")
    first, last = _enrolments.academic_year_dates(e.academic_year)
    rule = "=" * width
    lines = [rule, "ENROLMENT CONFIRMATION AND LEARNER AGREEMENT".center(width),
             f"Academic year {e.academic_year}".center(width), rule, ""]
    lines += [f"Learner:          {s.full_name}",
              f"Student ID:       {s.student_id}"]
    if getattr(s, "uln", None):
        lines.append(f"ULN:              {s.uln}")
    if getattr(s, "date_of_birth", None):
        lines.append(f"Date of birth:    {s.date_of_birth}")
    lines += [f"Year group:       Year {e.year_group}",
              f"Tutor group:      {e.tutor_group or 'To be confirmed'}",
              f"Start date:       {e.start_date or first}",
              f"Enrolment status: {e.status}", ""]

    lines += ["PROGRAMME OF STUDY", "-" * width]
    aims = _enrolments.aims_for_enrolment(e)
    if not aims:
        lines.append("No learning aims recorded yet.")
    for a in sorted(aims, key=lambda a: (a.display_order, a.aim_id)):
        board = f", {a.awarding_body}" if a.awarding_body else ""
        code = f" [{a.aim_code}]" if a.aim_code else ""
        end = f", planned to {a.planned_end_date}" if a.planned_end_date else ""
        lines.append(f"- {a.qualification_type} {a.subject}{board}{code}"
                     f" (from {a.start_date}{end})")
    lines.append("")

    lines += ["TIMETABLE SUMMARY", "-" * width]
    try:
        slots = _checks.learner_timetable(e.student_id)
    except Exception:  # noqa: BLE001 — the document still prints
        logger.exception("Timetable for confirmation %s", e.student_id)
        slots = []
    if not slots:
        lines.append("Your timetable will be given to you on your first day.")
    for t in slots:
        where = f", room {t.room}" if t.room else ""
        who = f", {t.teacher}" if t.teacher else ""
        lines.append(f"{t.day:<10} P{t.period} {t.start}-{t.end}  "
                     f"{t.group_name}{where}{who}")
    lines.append("")

    lines += ["COLLEGE EXPECTATIONS", "-" * width]
    lines += _wrap(get_template(), width)
    lines.append("")

    lines += ["SIGNATURES", "-" * width]
    st = _agreements.state(e.enrolment_id)
    sig = "_" * 34
    lines += ["Learner", f"Signed: {sig}   Date: ____________",
              f"Name:   {s.full_name}"]
    if st.learner:
        lines.append(f"(Recorded: signed {st.learner.signed_on}, "
                     f"{st.learner.method.lower()})")
    lines.append("")
    if st.parent_needed:
        lines += ["Parent / guardian", f"Signed: {sig}   Date: ____________",
                  "Name:   __________________________   Relationship: "
                  "______________"]
        if st.parent:
            lines.append(f"(Recorded: {st.parent.signed_name}, "
                         f"{st.parent.relationship}, {st.parent.signed_on})")
        lines.append("")
    lines += ["For the college", f"Signed: {sig}   Date: ____________", "",
              f"Valid for the {e.academic_year} academic year "
              f"({first} to {last}). Generated "
              f"{_dt.date.today().isoformat()}.", rule]
    return "\n".join(lines)


# ── ID card ─────────────────────────────────────────────────────────

@dataclass
class IdCardData:
    student_id: str
    name: str
    preferred_name: str | None
    photo_path: str | None
    academic_year: str | None
    year_group: int | None
    tutor_group: str | None
    valid_until: str | None
    card_number: str | None


def id_card_data(student_id: str) -> IdCardData:
    """What goes on the learner's ID card; valid until the end of their
    current enrolment's academic year."""
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks as _idc,
    )
    s = _student(student_id)
    if s is None:
        raise ValidationError(f"No student with id {student_id}")
    e = _enrolments.current_enrolment(student_id)
    c = _idc._raw_check(student_id)
    card = _active_card(student_id)
    return IdCardData(
        student_id=s.student_id, name=s.full_name,
        preferred_name=getattr(s, "preferred_name", None),
        photo_path=c.photo_path if c is not None and c.has_photo else None,
        academic_year=e.academic_year if e else None,
        year_group=e.year_group if e else None,
        tutor_group=e.tutor_group if e else None,
        valid_until=(_enrolments.academic_year_dates(e.academic_year)[1]
                     if e else None),
        card_number=card.card_number if card is not None else None)

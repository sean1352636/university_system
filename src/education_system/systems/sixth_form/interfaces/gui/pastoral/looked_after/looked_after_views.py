"""Tkinter window: Looked-After Children & Care Leavers register.

Tabs: Care Register (with care file, PEP reviews and agreed actions,
leaver plans per record), PEP Due, PEP Actions, Care-Leaver Plans,
Bursary Gaps, Designated Teacher and Summary. Every data call goes
through ``looked_after`` (PASTORAL + sensitive-access log).
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.looked_after import (
    looked_after as data,
)
from education_system.systems.sixth_form.domain.pastoral.wellbeing import (
    wellbeing as _wb,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._pastoral_ui import (
    ReportTab, counts_block, make_window, staff_col, swap_cols,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form, open_records_window,
)
from education_system.systems.sixth_form.interfaces.gui.progression._record_tabs import (
    show_text,
)

logger = logging.getLogger(__name__)

_TAGS = {"overdue": ("#ffd1d1", "#8c0d0d"), "soon": ("#fff7e6", "#7a5800"),
         "done": ("#eeeeee", "#555555")}


def _care_form_cols() -> list[Col]:
    cols = [c for c in _wb.CARE_SPEC.cols if c.name != "designated_teacher"]
    i = next(n for n, c in enumerate(cols) if c.name == "virtual_school_email")
    cols.insert(i + 1, staff_col("designated_teacher_id",
                                 "Designated teacher (blank = current)"))
    return cols


def _action_form_cols() -> list[Col]:
    return list(data.PEP_ACTION_SPEC.cols)


# ── Per-record actions ──────────────────────────────────────────────

def _care_file(tab: RecordTab, rec: Any) -> None:
    show_text(tab.frame, f"Care file — {rec.student_id}",
              data.care_file_text(rec.record_id))


def _pep_reviews(tab: RecordTab, rec: Any) -> None:
    open_records_window(
        tab.frame, f"PEP reviews — care record #{rec.record_id} "
        f"({rec.student_id})", _wb.PEP_SPEC, tab_title="PEP Reviews",
        load=lambda _f: _wb.list_pep_reviews(rec.record_id),
        create=data.record_pep_review, update=_wb.update_pep_review,
        delete=_wb.delete_pep_review,
        new_defaults=lambda _t: {"record_id": rec.record_id},
        actions=(("Add agreed action", _add_action_for_review, True),))


def _add_action_for_review(tab: RecordTab, review: Any) -> None:
    ask_form(tab.frame, f"Action agreed at PEP review #{review.review_id}",
             _action_form_cols(),
             initial={"record_id": review.record_id,
                      "review_id": review.review_id},
             on_save=data.add_pep_action)


def _record_pep(tab: RecordTab, rec: Any) -> None:
    ask_form(tab.frame, f"Record PEP review — {rec.student_id}",
             _wb.PEP_SPEC.cols, initial={"record_id": rec.record_id},
             on_save=data.record_pep_review,
             intro=("The record's last / next PEP dates move forward when "
                    "this is the latest review. Add the agreed actions from "
                    "PEP Reviews… → Add agreed action, or the PEP Actions "
                    "tab."))


def _record_actions(tab: RecordTab, rec: Any) -> None:
    open_records_window(
        tab.frame, f"PEP actions — care record #{rec.record_id} "
        f"({rec.student_id})", data.PEP_ACTION_SPEC, tab_title="PEP Actions",
        load=lambda _f: data.list_pep_actions(record_id=rec.record_id),
        create=data.add_pep_action, update=data.update_pep_action,
        delete=data.delete_pep_action,
        new_defaults=lambda _t: {"record_id": rec.record_id},
        row_tag=_action_tag, tag_colours=_TAGS)


def _leaver_plans(tab: RecordTab, rec: Any) -> None:
    open_records_window(
        tab.frame, f"Care-leaver plans — care record #{rec.record_id} "
        f"({rec.student_id})", data.LEAVER_PLAN_SPEC,
        tab_title="Care-Leaver Plans",
        load=lambda _f: data.list_leaver_plans(record_id=rec.record_id),
        create=data.create_leaver_plan, update=data.update_leaver_plan,
        delete=data.delete_leaver_plan,
        new_defaults=lambda _t: {"record_id": rec.record_id})


def _bursaries(tab: RecordTab, rec: Any) -> None:
    rows = data.bursary_applications_for(rec.student_id)
    cat = data.bursary_category_for(rec.care_status)
    lines = [f"16-19 bursary applications for {rec.student_id}", "",
             f"Expected vulnerable category: {cat or 'not a defined vulnerable group'}",
             ""]
    lines += [f"  #{b.application_id}  {b.academic_year or '—':<8} "
              f"{b.bursary_type:<24} {b.category or '':<30} {b.status:<14}"
              + (f" £{b.amount_awarded:,.2f}" if b.amount_awarded else "")
              for b in rows] or ["  (none — raise one in Bursaries)"]
    show_text(tab.frame, "Care bursary applications", "\n".join(lines))


def _action_tag(a: Any) -> str | None:
    if a.overdue:
        return "overdue"
    return "done" if a.status != data.OPEN else None


def _complete_action(tab: RecordTab, a: Any) -> None:
    ask_form(tab.frame, f"Close PEP action #{a.action_id}",
             (Col("status", "Outcome", "choice", required=True,
                  choices=tuple(s for s in data.PEP_ACTION_STATUSES
                                if s != data.OPEN), default="Completed"),
              Col("on", "On", "date", default=today),
              Col("outcome", "Notes", "multiline")),
             on_save=lambda v: data.complete_pep_action(
                 a.action_id, status=v["status"], on=v["on"] or None,
                 outcome=v["outcome"]))


# ── Window ──────────────────────────────────────────────────────────

def open_looked_after_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Looked-After Children & Care Leavers")

    RecordTab(
        nb, "Care Register", _wb.CARE_SPEC,
        load=lambda f: data.list_care_records(
            student_id=f.get("student_id") or None,
            care_status=f.get("care_status") or None,
            active_only=bool(f.get("active")),
            pep_overdue_only=bool(f.get("pep_overdue"))),
        create=data.create_care_record, update=data.update_care_record,
        delete=data.delete_care_record,
        form_cols=_care_form_cols(),
        filters=(Col("student_id", "Student", "student"),
                 Col("care_status", "Status", "choice",
                     choices=data.CARE_STATUSES),
                 Col("active", "Current only", "bool", default=True),
                 Col("pep_overdue", "PEP overdue", "bool")),
        actions=(("Care File…", _care_file, True),
                 ("Record PEP Review", _record_pep, True),
                 ("PEP Reviews…", _pep_reviews, True),
                 ("PEP Actions…", _record_actions, True),
                 ("Leaver Plans…", _leaver_plans, True),
                 ("Bursary…", _bursaries, True)),
        row_tag=lambda r: "overdue" if r.pep_overdue else None,
        tag_colours=_TAGS,
        intro=("Looked-after (LAC), previously looked-after (PLAC) and "
               "care-leaver records. A new LAC/PLAC record with no "
               "designated teacher gets the current appointee. Records "
               "with PEP actions or a leaver plan cannot be deleted — set "
               "an end date. Red = PEP review overdue."))

    RecordTab(
        nb, "PEP Due", None,
        load=lambda f: data.pep_due_list(
            within_days=int(f.get("days") or data.DEFAULT_DUE_SOON_DAYS)),
        columns=(("Care #", lambda r: r.record_id, 60),
                 ("Student", lambda r: r.student_id, 90),
                 ("Name", lambda r: r.student_name, 170),
                 ("State", lambda r: r.state, 120),
                 ("Days over (+)", lambda r: r.days, 90),
                 ("Next PEP", lambda r: r.next_pep_due, 95),
                 ("Last PEP", lambda r: r.last_pep_on, 95),
                 ("Status", lambda r: r.care_status, 140),
                 ("LA", lambda r: r.local_authority, 110),
                 ("Virtual school", lambda r: r.virtual_school_contact, 140),
                 ("Designated teacher", lambda r: r.designated_teacher, 140),
                 ("Open actions", lambda r: r.open_actions, 80),
                 ("Overdue actions", lambda r: r.overdue_actions, 90)),
        filters=(Col("days", "Due within days", "int",
                     default=str(data.DEFAULT_DUE_SOON_DAYS)),),
        row_id=lambda r: r.record_id,
        row_tag=lambda r: "soon" if r.state == "Due soon" else "overdue",
        tag_colours=_TAGS,
        intro=("PEP reviews overdue or due soon, and current looked-after "
               "learners with no PEP recorded at all."))

    RecordTab(
        nb, "PEP Actions", data.PEP_ACTION_SPEC,
        load=lambda f: data.list_pep_actions(
            student_id=f.get("student_id") or None,
            open_only=bool(f.get("open")),
            overdue_only=bool(f.get("overdue"))),
        create=data.add_pep_action, update=data.update_pep_action,
        delete=data.delete_pep_action,
        filters=(Col("student_id", "Student", "student"),
                 Col("open", "Open only", "bool", default=True),
                 Col("overdue", "Overdue only", "bool")),
        actions=(("Close Action", _complete_action, True),),
        row_tag=_action_tag, tag_colours=_TAGS,
        intro="Actions agreed at PEP reviews. Red = past its due date.")

    RecordTab(
        nb, "Care-Leaver Plans", data.LEAVER_PLAN_SPEC,
        load=lambda f: data.list_leaver_plans(
            student_id=f.get("student_id") or None,
            active_only=bool(f.get("active")),
            review_overdue_only=bool(f.get("overdue"))),
        create=data.create_leaver_plan, update=data.update_leaver_plan,
        delete=data.delete_leaver_plan,
        filters=(Col("student_id", "Student", "student"),
                 Col("active", "Active only", "bool", default=True),
                 Col("overdue", "Review overdue", "bool")),
        row_tag=lambda r: "overdue" if r.review_overdue else None,
        tag_colours=_TAGS,
        intro=("Support plans for care leavers (and looked-after learners "
               "approaching leaving care). A blank bursary application # "
               "links the learner's latest application filed under a care "
               "category in Bursaries."))

    RecordTab(
        nb, "Bursary Gaps", None,
        load=lambda _f: data.bursary_gaps(),
        columns=(("Care #", lambda r: r.record_id, 60),
                 ("Student", lambda r: r.student_id, 90),
                 ("Name", lambda r: r.student_name, 170),
                 ("Care status", lambda r: r.care_status, 170),
                 ("Bursary category", lambda r: r.expected_category, 200),
                 ("Applications", lambda r: len(r.applications), 90),
                 ("Note", lambda r: r.note, 320)),
        row_id=lambda r: r.record_id,
        intro=("Current looked-after children and care leavers with no "
               "active or approved 16-19 vulnerable bursary application. "
               "Raise the application in Finance → Bursaries."))

    RecordTab(
        nb, "Designated Teacher", data.APPOINTMENT_SPEC,
        load=lambda _f: data.list_appointments(),
        create=lambda v: data.appoint_designated_teacher(
            v["staff_id"], start_date=v.get("start_date") or None,
            notes=v.get("notes")),
        update=data.update_appointment, delete=data.delete_appointment,
        form_cols=swap_cols(data.APPOINTMENT_SPEC.cols, {
            "staff_id": staff_col("staff_id", "Designated teacher",
                                  required=True)}),
        row_tag=lambda r: None if r.current else "done",
        tag_colours=_TAGS,
        intro=("The statutory designated teacher for looked-after and "
               "previously looked-after learners. A new appointment ends "
               "the previous one the day before."))

    def render(_f: dict[str, str]) -> list[str]:
        s = data.summary()
        lines = ["Looked-after children & care leavers", "",
                 f"  Designated teacher:        {s.designated_teacher or '(none appointed)'}",
                 f"  PEP reviews overdue:       {s.peps_overdue}",
                 f"  LAC with no PEP recorded:  {s.no_pep}",
                 f"  PEP actions open:          {s.actions_open}"
                 f" ({s.actions_overdue} overdue)",
                 f"  Care-leaver plans active:  {s.leaver_plans_active}"
                 f" ({s.leaver_reviews_overdue} review overdue)",
                 f"  Without a vulnerable bursary application: "
                 f"{s.bursary_gaps}", ""]
        lines += counts_block("Current records by status", s.by_status)
        lines += counts_block("By local authority", s.by_local_authority)
        return lines

    ReportTab(nb, "Summary", render)

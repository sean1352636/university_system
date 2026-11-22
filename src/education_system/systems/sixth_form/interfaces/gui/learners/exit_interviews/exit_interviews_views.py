"""Tkinter window: Exit Interviews (early withdrawals / retention).

Tabs: Interviews (all, full CRUD), Pending, and Withdrawal Reasons (the
summary report). Withdrawals made through the student directory open a
pending interview automatically.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.sixth_form.domain.learners.exit_interviews import (
    exit_interviews as data,
)
from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.interfaces.gui.pastoral._pastoral_ui import (
    ReportTab, make_window, staff_col, swap_cols,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form,
)

_TAGS = {"pending": ("#fff7e6", "#7a5800"), "done": ("#e6f7e6", "#0d6b2a")}

_INTRO = ("Other reasons and 'would have helped' take comma-separated "
          "choices. Reasons: " + ", ".join(data.REASONS)
          + ". Would have helped: " + ", ".join(data.HELP_OPTIONS) + ".")


def _form_cols() -> list[Col]:
    return swap_cols(data.SPEC.cols, {
        "interviewer_staff_id": staff_col("interviewer_staff_id",
                                          "Interviewer (staff)")})


def _tag(r: Any) -> str | None:
    if r.status == data.PENDING:
        return "pending"
    return "done" if r.status == data.COMPLETED else None


def _start(tab: RecordTab, _row: Any) -> None:
    ask_form(tab.frame, "Start exit interview from a withdrawal",
             (Col("student_id", "Student", "student", required=True),
              Col("date", "Withdrew on", "date", default=today),
              Col("reason", "Reason given")),
             on_save=lambda v: data.start_from_withdrawal(
                 v["student_id"], withdrawal_date=v["date"] or None,
                 reason=v["reason"]),
             intro=("For a withdrawal recorded before exit interviews "
                    "existed. New withdrawals open one automatically."))


def _complete(tab: RecordTab, r: Any) -> None:
    names = ("status", "primary_reason", "other_reasons", "reason_detail",
             "destination", "destination_detail", "what_could_have_helped",
             "help_categories", "retainable", "interviewer_staff_id",
             "interview_date", "method", "notes")
    cols = [c for c in _form_cols() if c.name in names]
    initial = {n: getattr(r, n) for n in names}
    initial["status"] = data.COMPLETED
    initial["interview_date"] = r.interview_date or today()
    ask_form(tab.frame, f"Exit interview — {r.student_id}", cols,
             initial=initial, editing=True,
             on_save=lambda v: data.update_interview(r.interview_id, v),
             intro=_INTRO)


def open_exit_interviews_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Exit Interviews")

    common = dict(create=data.create_interview, update=data.update_interview,
                  delete=data.delete_interview, form_cols=_form_cols(),
                  row_tag=_tag, tag_colours=_TAGS)
    RecordTab(
        nb, "Interviews", data.SPEC,
        load=lambda f: data.list_interviews(
            student_id=f.get("student_id") or None,
            status=f.get("status") or None,
            primary_reason=f.get("reason") or None,
            date_from=f.get("from") or None, date_to=f.get("to") or None),
        filters=(Col("student_id", "Student", "student"),
                 Col("status", "Status", "choice", choices=data.STATUSES),
                 Col("reason", "Main reason", "choice",
                     choices=data.REASONS),
                 Col("from", "Withdrew from", "date"),
                 Col("to", "to", "date")),
        actions=(("Record Interview…", _complete, True),
                 ("Start from Withdrawal…", _start, False)),
        intro=_INTRO, **common)

    RecordTab(
        nb, "Pending", data.SPEC,
        load=lambda _f: data.pending_interviews(),
        columns=(("#", lambda r: r.interview_id, 50),
                 ("Student", lambda r: r.student_id, 90),
                 ("Withdrew", lambda r: r.withdrawal_date, 95),
                 ("Days ago", data.days_since_withdrawal, 70),
                 ("Year", lambda r: r.year_group, 50),
                 ("Tutor group", lambda r: r.tutor_group, 90),
                 ("Reason given", lambda r: r.withdrawal_reason, 380)),
        actions=(("Record Interview…", _complete, True),),
        intro="Withdrawals still waiting for an exit interview.",
        **common)

    def render(f: dict[str, str]) -> list[str]:
        if f.get("year"):
            return data.reasons_summary(academic_year=f["year"]).lines()
        return data.reasons_summary(date_from=f.get("from") or None,
                                    date_to=f.get("to") or None).lines()

    ReportTab(nb, "Withdrawal Reasons", render,
              filters=(("year", "Academic year", data.current_academic_year()),
                       ("from", "or from", ""), ("to", "to", "")))

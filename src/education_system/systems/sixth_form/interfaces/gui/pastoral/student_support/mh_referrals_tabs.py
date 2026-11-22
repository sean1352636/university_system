"""Mental-health referral tabs (CAMHS, GP, counselling, Kooth ...).

Shown in both the Student Support and the Wellbeing windows. Data calls
go through ``student_support`` which enforces PASTORAL, tutor scoping
and the sensitive-access log.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.student_support import (
    student_support as data,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form, spec_columns,
)

_TAGS = {"urgent": ("#ffd1d1", "#8c0d0d"), "waiting": ("#fff0d6", "#7a5800")}


def _tag(r: Any) -> str | None:
    if r.is_open and r.urgency in ("Urgent", "Emergency"):
        return "urgent"
    if r.status in data.MH_WAITING_STATUSES:
        return "waiting"
    return None


def _set_status(tab: RecordTab, r: Any) -> None:
    ask_form(tab.frame, f"Referral #{r.referral_id} — status",
             (Col("status", "New status", "choice", required=True,
                  choices=data.MH_STATUSES),
              Col("on", "Date", "date", default=today)),
             initial={"status": r.status},
             on_save=lambda v: data.set_mh_status(r.referral_id, v["status"],
                                                  on=v["on"]))


def _outcome(tab: RecordTab, r: Any) -> None:
    ask_form(tab.frame, f"Referral #{r.referral_id} — outcome",
             (Col("outcome", "Outcome", "multiline", required=True),
              Col("follow_up_date", "Follow-up date", "date"),
              Col("follow_up_by", "Follow-up by"),
              Col("close", "Close the referral", "bool")),
             initial={"outcome": r.outcome,
                      "follow_up_date": r.follow_up_date,
                      "follow_up_by": r.follow_up_by},
             on_save=lambda v: data.record_mh_outcome(
                 r.referral_id, outcome=v["outcome"],
                 follow_up_date=v["follow_up_date"],
                 follow_up_by=v["follow_up_by"], close=v["close"]))


def add_mh_referral_tabs(nb: ttk.Notebook) -> None:
    data.init_db()
    RecordTab(
        nb, "Mental Health Referrals", data.MH_SPEC,
        load=lambda f: data.list_mh_referrals(
            student_id=f.get("student_id") or None,
            service=f.get("service") or None,
            status=f.get("status") or None,
            open_only=bool(f.get("open"))),
        create=data.create_mh_referral,
        update=data.update_mh_referral,
        delete=data.delete_mh_referral,
        filters=(Col("student_id", "Student", "student"),
                 Col("service", "Service", "choice",
                     choices=data.MH_SERVICES),
                 Col("status", "Status", "choice", choices=data.MH_STATUSES),
                 Col("open", "Open only", "bool", default=True)),
        actions=(("Change Status", _set_status, True),
                 ("Record Outcome", _outcome, True)),
        row_tag=_tag, tag_colours=_TAGS)

    RecordTab(
        nb, "MH Waiting / Follow-ups", data.MH_SPEC,
        load=lambda f: (data.mh_follow_ups_due(
            within_days=int(f.get("days") or 7))
            if f.get("follow_ups") else data.mh_waiting_list()),
        update=data.update_mh_referral,
        columns=[*spec_columns(data.MH_SPEC)[:3],
                 ("Days waiting", lambda r: r.days_waiting, 90),
                 *spec_columns(data.MH_SPEC)[3:]],
        filters=(Col("follow_ups", "Show follow-ups due instead", "bool"),
                 Col("days", "within days", "int")),
        actions=(("Change Status", _set_status, True),
                 ("Record Outcome", _outcome, True)),
        row_tag=_tag, tag_colours=_TAGS,
        intro="Students referred but not yet seen, longest wait first.")

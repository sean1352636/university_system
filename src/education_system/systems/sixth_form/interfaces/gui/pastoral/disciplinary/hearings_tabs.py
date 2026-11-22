"""Disciplinary tabs: appeal hearings / governor panels / IRPs, and the
statutory notifications for suspensions and exclusions."""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.disciplinary import (
    disciplinary as data,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form, spec_columns,
)

_AMBER = {"todo": ("#fff0d6", "#7a5800")}


def _outcome(tab: RecordTab, h: Any) -> None:
    ask_form(tab.frame, f"{h.stage} #{h.hearing_id} — outcome",
             (Col("outcome", "Outcome", "choice", required=True,
                  choices=tuple(o for o in data.HEARING_OUTCOMES
                                if o != "Pending")),
              Col("hearing_date", "Hearing date", "date"),
              Col("panel_members", "Panel members", "multiline"),
              Col("reasons", "Reasons", "multiline"),
              Col("decision_date", "Decision date", "date")),
             initial={"hearing_date": h.hearing_date,
                      "panel_members": h.panel_members,
                      "reasons": h.outcome_reasons,
                      "decision_date": h.decision_date},
             on_save=lambda v: data.record_hearing_outcome(
                 h.hearing_id, outcome=v["outcome"],
                 panel_members=v["panel_members"],
                 hearing_date=v["hearing_date"], reasons=v["reasons"],
                 decision_date=v["decision_date"]),
             intro=("'Sanction upheld' sets the case to Appeal Upheld; "
                    "'Sanction overturned' / 'Reinstated' to Appeal "
                    "Overturned. The outcome is added to the case."))


def _letter(tab: RecordTab, h: Any) -> None:
    ask_form(tab.frame, f"Decision letter — {h.stage} #{h.hearing_id}",
             (Col("sent_on", "Sent on", "date", default=today),
              Col("sent_by", "Sent by")),
             on_save=lambda v: data.mark_letter_sent(
                 h.hearing_id, sent_on=v["sent_on"],
                 sent_by=v["sent_by"] or None))


def _notify(tab: RecordTab, g: Any) -> None:
    party = g.missing[0] if g.missing else "Local Authority"
    ntype = ("Permanent Exclusion" if g.case.case_type
             == "Permanent Exclusion" else "Suspension")
    ask_form(tab.frame, f"Notification — case #{g.case.case_id}",
             data.NOTIFICATION_SPEC.cols,
             initial={"case_id": g.case.case_id, "notified_party": party,
                      "notification_type": ntype,
                      "days_excluded": g.case.sanction_days},
             on_save=data.record_notification)


def add_hearing_tabs(nb: ttk.Notebook) -> None:
    data.init_db()
    RecordTab(
        nb, "Hearings & Panels", data.HEARING_SPEC,
        load=lambda f: data.list_hearings(
            stage=f.get("stage") or None,
            pending_only=bool(f.get("pending")),
            letters_outstanding=bool(f.get("letters"))),
        create=data.schedule_hearing, update=data.update_hearing,
        delete=data.delete_hearing,
        columns=[*spec_columns(data.HEARING_SPEC)[:1],
                 ("Case", lambda h: h.case_id, 50),
                 ("Student", lambda h: h.student_id, 90),
                 *spec_columns(data.HEARING_SPEC)[1:]],
        filters=(Col("stage", "Stage", "choice",
                     choices=data.HEARING_STAGES),
                 Col("pending", "Pending only", "bool"),
                 Col("letters", "Letter not sent", "bool")),
        actions=(("Record Outcome", _outcome, True),
                 ("Letter Sent", _letter, True)),
        row_tag=lambda h: "todo" if (h.outcome == "Pending"
                                     or h.letter_outstanding) else None,
        tag_colours=_AMBER,
        intro=("Governor panels and independent review panels are only "
               "for suspensions / exclusions. Scheduling a hearing moves "
               "the case to Appealed."))
    RecordTab(
        nb, "Statutory Notifications", data.NOTIFICATION_SPEC,
        load=lambda f: data.list_notifications(
            case_id=int(f["case_id"]) if f.get("case_id") else None),
        create=data.record_notification, update=data.update_notification,
        delete=data.delete_notification,
        columns=[*spec_columns(data.NOTIFICATION_SPEC)[:1],
                 ("Case", lambda n: n.case_id, 50),
                 ("Student", lambda n: n.student_id, 90),
                 *spec_columns(data.NOTIFICATION_SPEC)[1:]],
        filters=(Col("case_id", "Case #", "int"),))
    RecordTab(
        nb, "Notifications Outstanding", None,
        load=lambda _f: data.notifications_outstanding(),
        columns=(("Case", lambda g: g.case.case_id, 60),
                 ("Student", lambda g: g.case.student_id, 90),
                 ("Type", lambda g: g.case.case_type, 150),
                 ("Sanction", lambda g: g.case.sanction_start, 95),
                 ("Days", lambda g: g.case.sanction_days, 50),
                 ("Governors by", lambda g: g.governor_deadline, 100),
                 ("Still to notify", lambda g: ", ".join(g.missing), 380)),
        actions=(("Record Notification", _notify, True),),
        row_id=lambda g: g.case.case_id,
        intro=("Suspensions / exclusions with a sanction issued: the LA "
               "and parents must be told, the virtual school head too for "
               "a looked-after child, and governors where the panel must "
               "meet (within 15 school days)."))

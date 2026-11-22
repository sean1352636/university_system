"""CLI for appeal hearings / governor panels / IRPs and statutory
notifications of suspensions and exclusions."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.disciplinary import (
    disciplinary as data,
)
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui


def _pick_hearing(rows=None):
    rows = data.list_hearings() if rows is None else rows
    ui.print_rows(rows, ui.spec_columns(data.HEARING_SPEC))
    return ui.pick_row(rows, lambda h: h.hearing_id, "hearing")


def outcome() -> None:
    h = _pick_hearing(data.list_hearings(pending_only=True))
    v = ui.prompt_fields((
        Col("outcome", "Outcome", "choice", required=True,
            choices=tuple(o for o in data.HEARING_OUTCOMES
                          if o != "Pending")),
        Col("hearing_date", "Hearing date", "date"),
        Col("panel_members", "Panel members", "multiline"),
        Col("reasons", "Reasons", "multiline"),
        Col("decision_date", "Decision date", "date")),
        initial={"hearing_date": h.hearing_date,
                 "panel_members": h.panel_members})
    data.record_hearing_outcome(h.hearing_id, outcome=v["outcome"],
                                panel_members=v["panel_members"],
                                hearing_date=v["hearing_date"],
                                reasons=v["reasons"],
                                decision_date=v["decision_date"])
    print("\n  ✓ Outcome recorded and added to the case.")
    ui.pause()


def letter() -> None:
    h = _pick_hearing(data.list_hearings(letters_outstanding=True))
    v = ui.prompt_fields((Col("sent_on", "Sent on", "date", default=today),
                          Col("sent_by", "Sent by")))
    data.mark_letter_sent(h.hearing_id, sent_on=v["sent_on"],
                          sent_by=v["sent_by"] or None)
    print("\n  ✓ Letter recorded.")
    ui.pause()


def outstanding() -> None:
    ui.print_rows(data.notifications_outstanding(), (
        ("Case", lambda g: g.case.case_id, 5),
        ("Student", lambda g: g.case.student_id, 9),
        ("Type", lambda g: g.case.case_type, 21),
        ("Governors by", lambda g: g.governor_deadline, 12),
        ("Still to notify", lambda g: ", ".join(g.missing), 44)),
        empty="(no notifications outstanding)")
    ui.pause()


def run() -> None:
    ui.run_menu("Appeals, Panels & Notifications", [
        ("── Hearings ──", None),
        *ui.crud_items("hearing", data.HEARING_SPEC, load=data.list_hearings,
                       create=data.schedule_hearing,
                       update=data.update_hearing,
                       delete=data.delete_hearing),
        ("Record hearing outcome", outcome),
        ("Record decision letter sent", letter),
        ("── Statutory notifications ──", None),
        *ui.crud_items("notification", data.NOTIFICATION_SPEC,
                       load=data.list_notifications,
                       create=data.record_notification,
                       update=data.update_notification,
                       delete=data.delete_notification),
        ("Notifications outstanding", outstanding),
    ])

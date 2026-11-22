"""CLI for external mental-health referrals (CAMHS, GP, Kooth ...)."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.student_support import (
    student_support as data,
)
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui


def _cols():
    base = ui.spec_columns(data.MH_SPEC)
    return [*base[:3], ("Waiting", lambda r: r.days_waiting, 7), *base[3:]]


def _pick(rows=None):
    rows = data.list_mh_referrals() if rows is None else rows
    ui.print_rows(rows, _cols())
    return ui.pick_row(rows, lambda r: r.referral_id, "referral")


def waiting() -> None:
    ui.print_rows(data.mh_waiting_list(), _cols(),
                  empty="(nobody waiting)")
    ui.pause()


def follow_ups() -> None:
    days = ui.ask("Within how many days", default="7")
    ui.print_rows(data.mh_follow_ups_due(within_days=int(days or 7)),
                  _cols(), empty="(no follow-ups due)")
    ui.pause()


def change_status() -> None:
    r = _pick(data.list_mh_referrals(open_only=True))
    v = ui.prompt_fields((Col("status", "New status", "choice",
                              required=True, choices=data.MH_STATUSES),
                          Col("on", "Date", "date", default=today)))
    data.set_mh_status(r.referral_id, v["status"], on=v["on"])
    print("\n  ✓ Status updated.")
    ui.pause()


def outcome() -> None:
    r = _pick()
    v = ui.prompt_fields((Col("outcome", "Outcome", "multiline",
                              required=True),
                          Col("follow_up_date", "Follow-up date", "date"),
                          Col("follow_up_by", "Follow-up by"),
                          Col("close", "Close the referral", "bool")))
    data.record_mh_outcome(r.referral_id, outcome=v["outcome"],
                           follow_up_date=v["follow_up_date"],
                           follow_up_by=v["follow_up_by"], close=v["close"])
    print("\n  ✓ Outcome recorded.")
    ui.pause()


def run() -> None:
    ui.run_menu("Mental Health Referrals", [
        *ui.crud_items("referral", data.MH_SPEC,
                       load=data.list_mh_referrals,
                       create=data.create_mh_referral,
                       update=data.update_mh_referral,
                       delete=data.delete_mh_referral, columns=_cols()),
        ("Waiting list (not yet seen)", waiting),
        ("Follow-ups due", follow_ups),
        ("Change status", change_status),
        ("Record outcome / follow-up", outcome),
    ])

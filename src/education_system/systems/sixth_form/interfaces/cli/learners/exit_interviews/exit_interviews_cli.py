"""CLI: Exit interviews for early withdrawals."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.learners.exit_interviews import (
    exit_interviews as data,
)
from education_system.systems.sixth_form.domain.pastoral._records import today
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui

_COLS = (
    ("#", lambda r: r.interview_id, 5),
    ("Student", lambda r: r.student_id, 9),
    ("Withdrew", lambda r: r.withdrawal_date, 10),
    ("Yr", lambda r: r.year_group, 3),
    ("Status", lambda r: r.status, 11),
    ("Main reason", lambda r: r.primary_reason, 22),
    ("Destination", lambda r: r.destination, 16),
    ("Kept?", lambda r: r.retainable, 8),
)


def pending() -> None:
    ui.print_rows(data.pending_interviews(), (
        *_COLS[:4],
        ("Days", data.days_since_withdrawal, 5),
        ("Reason given", lambda r: r.withdrawal_reason, 36),
    ), empty="(no interviews pending)")
    ui.pause()


def record_interview() -> None:
    rows = data.pending_interviews() or data.list_interviews()
    ui.print_rows(rows, _COLS)
    r = ui.pick_row(rows, lambda x: x.interview_id, "interview")
    print(f"\n  Reason given at withdrawal: {r.withdrawal_reason or '—'}")
    v = {"status": ui.pick_from("Status", list(data.STATUSES),
                                default=data.COMPLETED)}
    if v["status"] == data.COMPLETED:
        v["primary_reason"] = ui.pick_from("Main reason", list(data.REASONS),
                                           default=r.primary_reason)
        others = [o for o in data.REASONS if o != v["primary_reason"]]
        picks = ui.ask("Other reasons — numbers from the list above, "
                       "comma-separated (blank = none)")
        v["other_reasons"] = ", ".join(
            data.REASONS[int(p) - 1] for p in picks.split(",")
            if p.strip().isdigit() and 1 <= int(p) <= len(data.REASONS)
            and data.REASONS[int(p) - 1] in others)
        v["reason_detail"] = ui.ask_multiline("In their words",
                                              default=r.reason_detail or "")
        v["destination"] = ui.pick_from("Destination",
                                        list(data.DESTINATIONS),
                                        default=r.destination)
        v["destination_detail"] = ui.ask("Provider / employer",
                                         default=r.destination_detail or "")
        v["what_could_have_helped"] = ui.ask_multiline(
            "What could have helped", default=r.what_could_have_helped or "")
        print("\n  Would have helped:")
        for i, h in enumerate(data.HELP_OPTIONS, 1):
            print(f"    {i:>2}) {h}")
        picks = ui.ask("Numbers, comma-separated (blank = none)")
        v["help_categories"] = ", ".join(
            data.HELP_OPTIONS[int(p) - 1] for p in picks.split(",")
            if p.strip().isdigit() and 1 <= int(p) <= len(data.HELP_OPTIONS))
        v["retainable"] = ui.pick_from("Could we have kept them?",
                                       list(data.RETAINABLE),
                                       default=r.retainable, allow_blank=True)
        v["method"] = ui.pick_from("Method", list(data.METHODS),
                                   default=r.method or "In person")
    v["interviewer_staff_id"] = ui.ask("Interviewer staff id (blank = none)",
                                       default=r.interviewer_staff_id or "")
    v["interview_date"] = ui.ask("Interview date",
                                 default=r.interview_date or today())
    v["notes"] = ui.ask_multiline("Notes", default=r.notes or "")
    data.update_interview(r.interview_id, v)
    print("\n  ✓ Saved.")
    ui.pause()


def start_from_withdrawal() -> None:
    sid = ui.pick_student()
    r = data.start_from_withdrawal(
        sid, withdrawal_date=ui.ask("Withdrew on", default=today()),
        reason=ui.ask("Reason given"))
    print(f"\n  ✓ Exit interview #{r.interview_id} ({r.status}).")
    ui.pause()


def summary() -> None:
    year = ui.ask("Academic year (blank = enter dates)",
                  default=data.current_academic_year())
    if year:
        s = data.reasons_summary(academic_year=year)
    else:
        s = data.reasons_summary(date_from=ui.ask("From") or None,
                                 date_to=ui.ask("To") or None)
    print()
    print("\n".join(s.lines()))
    ui.pause()


def run() -> None:
    ui.run_menu("Exit Interviews", [
        ("Pending interviews", pending),
        ("Record an interview", record_interview),
        ("Start one for an earlier withdrawal", start_from_withdrawal),
        ("── All interviews ──", None),
        *ui.crud_items("exit interview", data.SPEC,
                       load=lambda: data.list_interviews(), columns=_COLS,
                       create=data.create_interview,
                       update=data.update_interview,
                       delete=data.delete_interview),
        ("── Report ──", None),
        ("Withdrawal reasons summary", summary),
    ])


def exit_interviews_menu() -> None:
    """Entry point for the main CLI menu."""
    run()

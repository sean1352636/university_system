"""CLI for EHCP detail on the SEND register: LA / caseworker, annual
review history, reviews due, LA decisions and high-needs funding."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.send import send as data
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui

_ENTRY_COLS = (
    ("Entry", lambda e: e.entry_id, 5),
    ("Student", lambda e: e.student_id, 9),
    ("EHCP ref", lambda e: e.ehcp_reference, 12),
    ("LA", lambda e: e.local_authority, 14),
    ("Caseworker", lambda e: e.la_caseworker, 16),
    ("Last review", lambda e: e.last_review_on, 11),
    ("Next review", lambda e: e.next_review_due, 11),
)


def _pick_ehcp():
    rows = data.list_entries(register_status="EHCP", open_only=True)
    ui.print_rows(rows, _ENTRY_COLS, empty="(no open EHCP entries)")
    return ui.pick_row(rows, lambda e: e.entry_id, "SEND entry")


def list_plans() -> None:
    ui.print_rows(data.list_entries(register_status="EHCP", open_only=True),
                  _ENTRY_COLS, empty="(no open EHCP entries)")
    ui.pause()


def set_la() -> None:
    e = _pick_ehcp()
    v = ui.prompt_fields((Col("local_authority", "Local authority"),
                          Col("caseworker", "Named LA caseworker"),
                          Col("caseworker_email", "Caseworker e-mail"),
                          Col("caseworker_phone", "Caseworker phone")),
                         initial={"local_authority": e.local_authority,
                                  "caseworker": e.la_caseworker,
                                  "caseworker_email": e.la_caseworker_email,
                                  "caseworker_phone": e.la_caseworker_phone})
    data.set_la_details(e.entry_id, **v)
    print("\n  ✓ Saved.")
    ui.pause()


def reviews_for_plan() -> None:
    e = _pick_ehcp()
    ui.run_menu(f"EHCP reviews — {e.student_id}", ui.crud_items(
        "review", data.EHCP_REVIEW_SPEC,
        load=lambda: data.list_ehcp_reviews(entry_id=e.entry_id),
        create=data.record_ehcp_review, update=data.update_ehcp_review,
        delete=data.delete_ehcp_review,
        new_initial=lambda: {"entry_id": e.entry_id,
                             "local_authority": e.local_authority}))


def reviews_due() -> None:
    days = ui.ask("Due within how many days", default="30")
    rows = data.ehcp_reviews_due(within_days=int(days or 30))
    ui.print_rows(rows, (
        ("Entry", lambda r: r.entry.entry_id, 5),
        ("Student", lambda r: r.entry.student_id, 9),
        ("LA", lambda r: r.entry.local_authority, 12),
        ("Last annual", lambda r: r.last_annual_review, 11),
        ("Due", lambda r: r.due_on, 10),
        ("Overdue", lambda r: r.overdue, 7),
        ("Why", lambda r: r.reason, 32)), empty="(nothing due)")
    ui.pause()


def pending_decisions() -> None:
    rows = data.list_ehcp_reviews(decision_pending=True)
    ui.print_rows(rows, (
        ("#", lambda r: r.review_id, 5),
        ("Student", lambda r: r.student_id, 9),
        ("Review", lambda r: r.review_date, 10),
        ("Recommend", lambda r: r.recommendation, 18),
        ("Report sent", lambda r: r.report_sent_to_la_on, 11),
        ("Report late", lambda r: r.report_overdue, 11),
        ("Decision late", lambda r: r.decision_overdue, 13)),
        empty="(no decisions pending)")
    ui.pause()


def la_decision() -> None:
    rows = data.list_ehcp_reviews(decision_pending=True)
    ui.print_rows(rows, ui.spec_columns(data.EHCP_REVIEW_SPEC))
    r = ui.pick_row(rows, lambda x: x.review_id, "review")
    v = ui.prompt_fields((Col("decision", "Decision", "choice",
                              required=True, choices=data.LA_DECISIONS),
                          Col("decision_date", "Decision date", "date",
                              default=today),
                          Col("notes", "Notes", "multiline")))
    data.record_la_decision(r.review_id, decision=v["decision"],
                            decision_date=v["decision_date"],
                            notes=v["notes"])
    print("\n  ✓ Decision recorded.")
    ui.pause()


def funding() -> None:
    e = _pick_ehcp()
    cols = [*ui.spec_columns(data.HN_FUNDING_SPEC),
            ("Total £", lambda r: r.total, 10)]
    ui.run_menu(f"High-needs funding — {e.student_id}", ui.crud_items(
        "funding record", data.HN_FUNDING_SPEC,
        load=lambda: data.list_hn_funding(entry_id=e.entry_id),
        create=data.create_hn_funding, update=data.update_hn_funding,
        delete=data.delete_hn_funding, columns=cols,
        new_initial=lambda: {"entry_id": e.entry_id,
                             "local_authority": e.local_authority}))


def sync_accessibility() -> None:
    n = data.sync_all_accessibility_profiles()
    print(f"\n  ✓ {n} accessibility profile(s) updated from the register.")
    ui.pause()


def run() -> None:
    ui.run_menu("EHCP", [
        ("Open EHCP plans", list_plans),
        ("Set LA / named caseworker", set_la),
        ("Annual reviews for a plan", reviews_for_plan),
        ("Reviews due / overdue", reviews_due),
        ("LA decisions pending", pending_decisions),
        ("Record LA decision", la_decision),
        ("High-needs funding for a plan", funding),
        ("Sync accessibility profiles from register", sync_accessibility),
    ])

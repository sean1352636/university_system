"""CLI: Young Carers support records."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.young_carers import (
    young_carers as data,
)
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui


def _pick(active_only: bool = True):
    rows = data.list_young_carers(active_only=active_only)
    ui.print_rows(rows, ui.spec_columns(data.SPEC))
    return ui.pick_row(rows, lambda r: r.carer_id, "young carer record")


def review() -> None:
    rec = _pick()
    v = ui.prompt_fields((Col("reviewed_on", "Reviewed on", "date",
                              default=today),
                          Col("next_review_due", "Next review due", "date"),
                          Col("notes", "Review notes", "multiline")))
    data.review_young_carer(rec.carer_id, reviewed_on=v["reviewed_on"] or None,
                            next_review_due=v["next_review_due"] or None,
                            notes=v["notes"])
    print("\n  ✓ Review recorded.")
    ui.pause()


def end_record() -> None:
    rec = _pick()
    out = data.end_young_carer(
        rec.carer_id, on=ui.ask("End date", default=today()),
        reason=ui.ask_multiline("Reason"))
    print(f"\n  ✓ Ended {out.end_date}; flag and exemption ended with it.")
    ui.pause()


def overdue() -> None:
    ui.print_rows(data.list_young_carers(review_overdue_only=True),
                  ui.spec_columns(data.SPEC), empty="(no reviews overdue)")
    ui.pause()


def no_consent() -> None:
    ui.print_rows(data.list_young_carers(active_only=True,
                                         no_consent_only=True),
                  ui.spec_columns(data.SPEC),
                  empty="(every current young carer has consented)")
    ui.pause()


def unlinked() -> None:
    ui.print_rows(data.exemptions_without_record(), (
        ("Exempt#", lambda r: r.exemption_id, 7),
        ("Student", lambda r: r.student_id, 9),
        ("Name", lambda r: r.student_name, 20),
        ("From", lambda r: r.start_date, 10),
        ("To", lambda r: r.end_date, 10),
        ("Detail", lambda r: r.detail, 36),
    ), empty="(none)")
    ui.pause()


def sync() -> None:
    flags, n = data.sync_all()
    print(f"\n  ✓ Checked {n} record(s); {flags} flag change(s).")
    ui.pause()


def summary() -> None:
    s = data.summary()
    print("\n═══ Young carers ═══")
    print(f"  Current:                   {s.active}")
    print(f"  Reviews overdue / 30 days: {s.reviews_overdue} / "
          f"{s.reviews_due_30}")
    print(f"  No consent to share:       {s.no_consent}")
    print(f"  No needs assessment:       {s.no_assessment}")
    print(f"  Bursary attendance exempt: {s.exempt}")
    print(f"  Exemptions without record: {s.unlinked_exemptions}")
    for k, n in s.by_impact.items():
        print(f"    Impact {k:<20} {n}")
    ui.pause()


def run() -> None:
    ui.run_menu("Young Carers", [
        *ui.crud_items("young carer record", data.SPEC,
                       load=lambda: data.list_young_carers(active_only=True),
                       create=data.create_young_carer,
                       update=data.update_young_carer,
                       delete=data.delete_young_carer),
        ("Record review", review),
        ("End a record (no longer caring)", end_record),
        ("── Lists ──", None),
        ("Reviews overdue", overdue),
        ("No consent to share", no_consent),
        ("Young-carer exemptions without a record", unlinked),
        ("Re-sync flags & exemptions", sync),
        ("Summary", summary),
    ])


def young_carers_menu() -> None:
    """Entry point for the main CLI menu."""
    run()

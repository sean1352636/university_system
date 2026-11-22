"""CLI for vulnerable groups: care records (LAC / PLAC / care leavers)
with PEP reviews, young carers, and the vulnerable-groups register."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.wellbeing import wellbeing as data
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui


def _pick_care_record():
    rows = data.list_care_records()
    ui.print_rows(rows, ui.spec_columns(data.CARE_SPEC))
    return ui.pick_row(rows, lambda r: r.record_id, "care record")


def pep_reviews() -> None:
    rec = _pick_care_record()
    ui.run_menu(f"PEP reviews — care record #{rec.record_id}", ui.crud_items(
        "PEP review", data.PEP_SPEC,
        load=lambda: data.list_pep_reviews(rec.record_id),
        create=data.record_pep_review, update=data.update_pep_review,
        delete=data.delete_pep_review,
        new_initial=lambda: {"record_id": rec.record_id}))


def pep_overdue() -> None:
    ui.print_rows(data.list_care_records(pep_overdue_only=True),
                  ui.spec_columns(data.CARE_SPEC),
                  empty="(no PEPs overdue)")
    ui.pause()


def review_carer() -> None:
    rows = data.list_young_carers(active_only=True)
    ui.print_rows(rows, ui.spec_columns(data.YOUNG_CARER_SPEC))
    rec = ui.pick_row(rows, lambda r: r.carer_id, "young carer record")
    v = ui.prompt_fields((Col("reviewed_on", "Reviewed on", "date",
                              default=today),
                          Col("next_review_due", "Next review due", "date"),
                          Col("notes", "Review notes", "multiline")))
    data.review_young_carer(rec.carer_id, reviewed_on=v["reviewed_on"],
                            next_review_due=v["next_review_due"],
                            notes=v["notes"])
    print("\n  ✓ Review recorded.")
    ui.pause()


def register() -> None:
    rows = data.vulnerable_groups_register()
    ui.print_rows(rows, (
        ("Student", lambda r: r.student_id, 9),
        ("Name", lambda r: r.student_name, 20),
        ("Groups", lambda r: ", ".join(r.groups), 30),
        ("LA", lambda r: r.local_authority, 12),
        ("Next PEP", lambda r: r.next_pep_due
         + (" !" if r.pep_overdue else "") if r.next_pep_due else None, 12),
        ("Cares for", lambda r: r.cares_for, 14),
        ("SEND", lambda r: r.send_status, 11),
        ("Bursary", lambda r: r.bursary_eligible, 7),
    ), empty="(nobody on the register)")
    ui.pause()


def sync_flags() -> None:
    n = data.sync_vulnerable_flags()
    print(f"\n  ✓ Flags re-derived from the records: {n} change(s).")
    ui.pause()


def run() -> None:
    ui.run_menu("Vulnerable Groups", [
        ("── Care records (LAC / care leavers) ──", None),
        *ui.crud_items("care record", data.CARE_SPEC,
                       load=data.list_care_records,
                       create=data.create_care_record,
                       update=data.update_care_record,
                       delete=data.delete_care_record),
        ("PEP reviews for a record", pep_reviews),
        ("PEPs overdue", pep_overdue),
        ("── Young carers ──", None),
        *ui.crud_items("young carer record", data.YOUNG_CARER_SPEC,
                       load=data.list_young_carers,
                       create=data.create_young_carer,
                       update=data.update_young_carer,
                       delete=data.delete_young_carer),
        ("Record young carer review", review_carer),
        ("── Register ──", None),
        ("Vulnerable groups register", register),
        ("Re-derive flags from records", sync_flags),
    ])

"""CLI for individual healthcare plans, the medication administration
log and medication stock (MEDICAL capability, audited)."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
    medical_records as data,
)
from education_system.systems.sixth_form.interfaces.cli.pastoral import _records_cli as ui


def _pick_plan():
    rows = data.list_healthcare_plans(include_archived=False)
    ui.print_rows(rows, ui.spec_columns(data.PLAN_SPEC))
    return ui.pick_row(rows, lambda p: p.plan_id, "plan")


def review_plan() -> None:
    p = _pick_plan()
    v = ui.prompt_fields((Col("reviewed_on", "Reviewed on", "date",
                              default=today),
                          Col("next_review", "Next review", "date",
                              required=True),
                          Col("notes", "Review notes", "multiline")))
    data.review_healthcare_plan(p.plan_id, reviewed_on=v["reviewed_on"],
                                next_review=v["next_review"],
                                notes=v["notes"])
    print("\n  ✓ Review recorded.")
    ui.pause()


def sign_off() -> None:
    p = _pick_plan()
    who = ui.pick_from("Who is signing", ["parent", "clinician"])
    v = ui.prompt_fields((Col("name", "Name", required=True),
                          Col("role", "Role (clinician only)"),
                          Col("signed_on", "Signed on", "date",
                              default=today)))
    data.sign_off_healthcare_plan(p.plan_id, who=who, name=v["name"],
                                  role=v["role"], signed_on=v["signed_on"])
    print("\n  ✓ Sign-off recorded.")
    ui.pause()


def attention() -> None:
    rows = data.plans_needing_attention(within_days=30)
    ui.print_rows(rows, (
        ("Plan", lambda a: a.plan.plan_id or "—", 5),
        ("Student", lambda a: a.plan.student_id, 9),
        ("Name", lambda a: a.student_name, 18),
        ("Condition", lambda a: a.plan.condition_name, 16),
        ("Review", lambda a: a.plan.review_date, 10),
        ("Problems", lambda a: "; ".join(a.problems), 48)),
        empty="(every plan is reviewed and signed off)")
    ui.pause()


def receive_stock() -> None:
    rows = data.list_stock()
    ui.print_rows(rows, ui.spec_columns(data.STOCK_SPEC))
    s = ui.pick_row(rows, lambda x: x.stock_id, "stock line")
    v = ui.prompt_fields((Col("quantity", "Quantity received", "int",
                              required=True),
                          Col("expiry_date", "Expiry of new supply",
                              "date")))
    data.receive_stock(s.medication_id, v["quantity"],
                       expiry_date=v["expiry_date"] or None)
    print("\n  ✓ Stock updated.")
    ui.pause()


def low_stock() -> None:
    rows = [s for s in data.list_stock() if s.low or s.expired] + \
        [s for s in data.list_stock(expiring_within_days=30)
         if not (s.low or s.expired)]
    ui.print_rows(rows, [*ui.spec_columns(data.STOCK_SPEC),
                         ("Low", lambda s: s.low, 4),
                         ("Expired", lambda s: s.expired, 7)],
                  empty="(no low, expired or expiring stock)")
    ui.pause()


def run() -> None:
    ui.run_menu("Healthcare Plans & Medication Log", [
        ("── Individual healthcare plans ──", None),
        *ui.crud_items("plan", data.PLAN_SPEC,
                       load=data.list_healthcare_plans,
                       create=data.create_healthcare_plan,
                       update=data.update_healthcare_plan,
                       delete=data.delete_healthcare_plan),
        ("Record plan review", review_plan),
        ("Parent / clinician sign-off", sign_off),
        ("Plans needing attention (overdue / unsigned)", attention),
        ("── Medication administration log ──", None),
        *ui.crud_items("administration", data.ADMIN_SPEC,
                       load=data.list_administrations,
                       create=data.record_administration,
                       update=data.update_administration,
                       delete=data.delete_administration),
        ("── Medication stock ──", None),
        *ui.crud_items("stock line", data.STOCK_SPEC,
                       load=data.list_stock, create=data.save_stock,
                       update=data.update_stock, delete=data.delete_stock),
        ("Receive stock", receive_stock),
        ("Low / expired / expiring stock", low_stock),
    ])

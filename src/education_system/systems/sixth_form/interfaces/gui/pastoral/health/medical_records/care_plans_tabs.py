"""Healthcare-plan, medication-log and stock tabs for Medical Records.

Used in the main Medical Records window (all students) and in the
per-student detail window (``student_id`` fixed). MEDICAL capability
and the sensitive-access log are enforced by the data layer.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
    medical_records as data,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form, spec_columns,
)

_RED = {"alert": ("#ffd1d1", "#8c0d0d")}


def _review(tab: RecordTab, plan: Any) -> None:
    ask_form(tab.frame, f"Review healthcare plan #{plan.plan_id}",
             (Col("reviewed_on", "Reviewed on", "date", default=today),
              Col("next_review", "Next review", "date", required=True),
              Col("notes", "Review notes", "multiline")),
             on_save=lambda v: data.review_healthcare_plan(
                 plan.plan_id, reviewed_on=v["reviewed_on"],
                 next_review=v["next_review"], notes=v["notes"]))


def _sign(who: str):
    def handler(tab: RecordTab, plan: Any) -> None:
        cols = [Col("name", "Name", required=True),
                Col("signed_on", "Signed on", "date", default=today)]
        if who == "clinician":
            cols.insert(1, Col("role", "Role (GP, nurse specialist …)"))
        ask_form(tab.frame, f"{who.title()} sign-off — plan #{plan.plan_id}",
                 cols, on_save=lambda v: data.sign_off_healthcare_plan(
                     plan.plan_id, who=who, name=v["name"],
                     role=v.get("role"), signed_on=v["signed_on"]))
    return handler


def _receive(tab: RecordTab, s: Any) -> None:
    ask_form(tab.frame, f"Receive stock — medication #{s.medication_id}",
             (Col("quantity", "Quantity received", "int", required=True),
              Col("expiry_date", "Expiry of new supply", "date")),
             on_save=lambda v: data.receive_stock(
                 s.medication_id, v["quantity"],
                 expiry_date=v["expiry_date"] or None))


def add_care_plan_tabs(nb: ttk.Notebook, *, student_id: str | None = None
                       ) -> None:
    """Add the tabs. With *student_id*, every tab is scoped to it."""
    data.init_db()
    fixed = {"student_id": student_id} if student_id else {}
    sfilter = () if student_id else (Col("student_id", "Student",
                                         "student"),)

    def sid(f: dict[str, Any]) -> str | None:
        return student_id or f.get("student_id") or None

    RecordTab(
        nb, "Healthcare Plans", data.PLAN_SPEC,
        load=lambda f: data.list_healthcare_plans(
            student_id=sid(f), status=f.get("status") or None,
            include_archived=not f.get("hide_archived")),
        create=data.create_healthcare_plan,
        update=data.update_healthcare_plan,
        delete=data.delete_healthcare_plan,
        filters=(*sfilter,
                 Col("status", "Status", "choice", choices=data.PLAN_STATUSES),
                 Col("hide_archived", "Hide archived", "bool", default=True)),
        actions=(("Record Review", _review, True),
                 ("Parent Sign-off", _sign("parent"), True),
                 ("Clinician Sign-off", _sign("clinician"), True)),
        new_defaults=lambda _t: dict(fixed),
        row_tag=lambda p: "alert" if p.review_overdue else None,
        tag_colours=_RED)

    if not student_id:
        RecordTab(
            nb, "Plans Needing Attention", None,
            load=lambda f: data.plans_needing_attention(
                within_days=int(f.get("days") or 0)),
            columns=(("Plan", lambda a: a.plan.plan_id or "—", 60),
                     ("Student", lambda a: a.plan.student_id, 90),
                     ("Name", lambda a: a.student_name, 170),
                     ("Condition", lambda a: a.plan.condition_name, 170),
                     ("Status", lambda a: a.plan.status, 90),
                     ("Review date", lambda a: a.plan.review_date, 95),
                     ("Problems", lambda a: "; ".join(a.problems), 420)),
            filters=(Col("days", "Include reviews due within days", "int"),),
            row_id=lambda a: a.plan.plan_id,
            intro=("Overdue reviews, missing parent / clinician sign-off, "
                   "and severe conditions with no plan (Plan '—')."))

    RecordTab(
        nb, "Medication Log", data.ADMIN_SPEC,
        load=lambda f: data.list_administrations(
            student_id=sid(f), date_from=f.get("date_from") or None,
            date_to=f.get("date_to") or None),
        create=data.record_administration,
        update=data.update_administration,
        delete=data.delete_administration,
        columns=[*spec_columns(data.ADMIN_SPEC),
                 ("Stock after", lambda a: a.stock_after, 80)],
        filters=(*sfilter, Col("date_from", "From"), Col("date_to", "To")),
        new_defaults=lambda _t: dict(fixed),
        intro=("Link the medication # from the student's record to "
               "decrement stock. Deleting an entry returns its quantity "
               "to stock."))

    RecordTab(
        nb, "Medication Stock", data.STOCK_SPEC,
        load=lambda f: data.list_stock(
            student_id=sid(f), low_only=bool(f.get("low")),
            expiring_within_days=(int(f["expiring"])
                                  if f.get("expiring") else None)),
        create=data.save_stock,
        update=data.update_stock,
        delete=data.delete_stock,
        columns=[("#", lambda s: s.stock_id, 50),
                 ("Student", lambda s: s.student_id, 90),
                 *spec_columns(data.STOCK_SPEC)[1:],
                 ("Low", lambda s: s.low, 50),
                 ("Expired", lambda s: s.expired, 60)],
        filters=(*sfilter, Col("low", "Low stock", "bool"),
                 Col("expiring", "Expiring within days", "int")),
        actions=(("Receive Stock", _receive, True),),
        row_tag=lambda s: "alert" if (s.low or s.expired) else None,
        tag_colours=_RED)

"""Vulnerable-groups tabs for the Wellbeing window.

* Care Records — looked-after children, previously looked-after and
  care leavers (LA, virtual school, social worker, PEP dates, designated
  teacher, 16-19 bursary eligibility), with PEP reviews per record.
* Young Carers — who they care for, support plan, reviews.
* Vulnerable Groups — the register across care, young carers, SEND
  and register-type flags; flags are re-derived from the records.

All data calls go through ``wellbeing`` which enforces the PASTORAL
capability and writes the sensitive-access log.
"""

from __future__ import annotations

from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.wellbeing import wellbeing as data
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form, open_records_window,
)

_OVERDUE = {"overdue": ("#ffd1d1", "#8c0d0d")}


def add_vulnerable_groups_tabs(nb: ttk.Notebook) -> None:
    CareRecordsTab(nb)
    YoungCarersTab(nb)
    RegisterTab(nb)


def _pep_window(tab: RecordTab, rec: Any) -> None:
    open_records_window(
        tab.frame, f"PEP reviews — care record #{rec.record_id} "
        f"({rec.student_id})", data.PEP_SPEC,
        tab_title="PEP Reviews",
        load=lambda _f: data.list_pep_reviews(rec.record_id),
        create=data.record_pep_review,
        update=data.update_pep_review,
        delete=data.delete_pep_review,
        new_defaults=lambda _t: {"record_id": rec.record_id})


def _record_pep(tab: RecordTab, rec: Any) -> None:
    ask_form(tab.frame, f"Record PEP review — {rec.student_id}",
             data.PEP_SPEC.cols, initial={"record_id": rec.record_id},
             on_save=data.record_pep_review,
             intro=("The care record's last / next PEP dates move forward "
                    "when this is the latest review."))


class CareRecordsTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "Care Records", data.CARE_SPEC,
            load=lambda f: data.list_care_records(
                student_id=f.get("student_id") or None,
                care_status=f.get("care_status") or None,
                active_only=bool(f.get("active")),
                pep_overdue_only=bool(f.get("pep_overdue"))),
            create=data.create_care_record,
            update=data.update_care_record,
            delete=data.delete_care_record,
            filters=(Col("student_id", "Student", "student"),
                     Col("care_status", "Status", "choice",
                         choices=data.CARE_STATUSES),
                     Col("active", "Current only", "bool", default=True),
                     Col("pep_overdue", "PEP overdue", "bool")),
            actions=(("PEP Reviews…", _pep_window, True),
                     ("Record PEP Review", _record_pep, True)),
            row_tag=lambda r: "overdue" if r.pep_overdue else None,
            tag_colours=_OVERDUE,
            intro=("Looked-after, previously looked-after and care-leaver "
                   "records. Defined vulnerable groups are marked 16-19 "
                   "bursary eligible automatically. Saving updates the "
                   "matching wellbeing flag."))


def _review_carer(tab: RecordTab, rec: Any) -> None:
    ask_form(tab.frame, f"Review young carer support — {rec.student_id}",
             (Col("reviewed_on", "Reviewed on", "date",
                  default=today),
              Col("next_review_due", "Next review due", "date"),
              Col("notes", "Review notes", "multiline")),
             on_save=lambda v: data.review_young_carer(
                 rec.carer_id, reviewed_on=v["reviewed_on"],
                 next_review_due=v["next_review_due"], notes=v["notes"]))


class YoungCarersTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "Young Carers", data.YOUNG_CARER_SPEC,
            load=lambda f: data.list_young_carers(
                student_id=f.get("student_id") or None,
                active_only=bool(f.get("active")),
                review_overdue_only=bool(f.get("overdue"))),
            create=data.create_young_carer,
            update=data.update_young_carer,
            delete=data.delete_young_carer,
            filters=(Col("student_id", "Student", "student"),
                     Col("active", "Current only", "bool", default=True),
                     Col("overdue", "Review overdue", "bool")),
            actions=(("Record Review", _review_carer, True),),
            row_tag=lambda r: "overdue" if r.review_overdue else None,
            tag_colours=_OVERDUE)


def _sync(tab: RecordTab, _row: Any) -> None:
    n = data.sync_vulnerable_flags()
    messagebox.showinfo("Vulnerable Groups",
                        f"Flags re-derived from the records: {n} change(s).",
                        parent=tab.frame)


class RegisterTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        groups = sorted({*data._CARE_FLAG.values(), "Young Carer",
                         *data.REGISTER_FLAG_TYPES})
        super().__init__(
            nb, "Vulnerable Groups", None,
            load=lambda f: data.vulnerable_groups_register(
                group=f.get("group") or None),
            columns=(
                ("Student", lambda r: r.student_id, 90),
                ("Name", lambda r: r.student_name, 170),
                ("Groups", lambda r: ", ".join(r.groups), 260),
                ("Care status", lambda r: r.care_status, 150),
                ("LA", lambda r: r.local_authority, 110),
                ("Designated teacher", lambda r: r.designated_teacher, 130),
                ("Next PEP", lambda r: r.next_pep_due, 95),
                ("Cares for", lambda r: r.cares_for, 120),
                ("Carer review", lambda r: r.young_carer_review_due, 95),
                ("SEND", lambda r: r.send_status, 100),
                ("Bursary", lambda r: r.bursary_eligible, 60),
                ("Flag without record",
                 lambda r: ", ".join(r.flags_without_record), 150),
            ),
            filters=(Col("group", "Group", "choice", choices=tuple(groups)),),
            actions=(("Sync Flags from Records", _sync, False),),
            row_id=lambda r: r.student_id,
            row_tag=lambda r: "overdue" if (
                r.pep_overdue or r.young_carer_review_overdue) else None,
            tag_colours=_OVERDUE,
            intro=("Red rows have a PEP or young-carer review overdue. "
                   "'Flag without record' = a hand-made flag with no "
                   "structured record behind it yet."))

"""EHCP tabs for the SEND Register window.

* EHCP Plans — open EHCP entries with LA / caseworker, review dates;
  record an annual review, see its history and funding.
* EHCP Reviews — every review, LA decision and report deadlines.
* Reviews Due — annual reviews overdue or due soon.
* High-Needs Funding — element 2 / 3 per academic year (recorded here;
  the funding itself is Finance's).

SEND capability is enforced by the data layer.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.send import send as data
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form, open_records_window, spec_columns,
)

_RED = {"overdue": ("#ffd1d1", "#8c0d0d")}


def add_ehcp_tabs(nb: ttk.Notebook) -> None:
    EHCPPlansTab(nb)
    RecordTab(
        nb, "EHCP Reviews", data.EHCP_REVIEW_SPEC,
        load=lambda f: data.list_ehcp_reviews(
            student_id=f.get("student_id") or None,
            decision_pending=bool(f.get("pending"))),
        create=data.record_ehcp_review,
        update=data.update_ehcp_review,
        delete=data.delete_ehcp_review,
        filters=(Col("student_id", "Student", "student"),
                 Col("pending", "LA decision pending", "bool")),
        columns=[*spec_columns(data.EHCP_REVIEW_SPEC)[:1],
                 ("Entry", lambda r: r.entry_id, 50),
                 ("Student", lambda r: r.student_id, 90),
                 *spec_columns(data.EHCP_REVIEW_SPEC)[1:],
                 ("Report late", lambda r: r.report_overdue, 80),
                 ("Decision late", lambda r: r.decision_overdue, 90)],
        actions=(("Record LA Decision", _la_decision, True),),
        row_tag=lambda r: "overdue" if (r.report_overdue
                                        or r.decision_overdue) else None,
        tag_colours=_RED,
        intro=("Report to the LA within 2 weeks of the meeting; the LA "
               "decides within 4 weeks. Red rows have missed one."))
    RecordTab(
        nb, "EHCP Reviews Due", None,
        load=lambda f: data.ehcp_reviews_due(
            within_days=int(f.get("days") or 30)),
        columns=(("Entry", lambda r: r.entry.entry_id, 60),
                 ("Student", lambda r: r.entry.student_id, 90),
                 ("EHCP ref", lambda r: r.entry.ehcp_reference, 110),
                 ("LA", lambda r: r.entry.local_authority, 120),
                 ("Caseworker", lambda r: r.entry.la_caseworker, 130),
                 ("Last annual review", lambda r: r.last_annual_review, 120),
                 ("Due", lambda r: r.due_on, 95),
                 ("Overdue", lambda r: r.overdue, 70),
                 ("Why", lambda r: r.reason, 240)),
        filters=(Col("days", "Due within days", "int"),),
        actions=(("Record Review", lambda t, r: _record_review(t, r.entry),
                  True),),
        row_id=lambda r: r.entry.entry_id,
        row_tag=lambda r: "overdue" if r.overdue else None,
        tag_colours=_RED)
    RecordTab(
        nb, "High-Needs Funding", data.HN_FUNDING_SPEC,
        load=lambda f: data.list_hn_funding(
            student_id=f.get("student_id") or None,
            academic_year=f.get("academic_year") or None),
        create=data.create_hn_funding,
        update=data.update_hn_funding,
        delete=data.delete_hn_funding,
        columns=[*spec_columns(data.HN_FUNDING_SPEC)[:1],
                 ("Entry", lambda r: r.entry_id, 50),
                 ("Student", lambda r: r.student_id, 90),
                 *spec_columns(data.HN_FUNDING_SPEC)[1:],
                 ("Total (£)", lambda r: r.total, 90)],
        filters=(Col("student_id", "Student", "student"),
                 Col("academic_year", "Year (YYYY/YY)")))


def _record_review(tab: RecordTab, entry: Any) -> None:
    ask_form(tab.frame, f"EHCP review — {entry.student_id}",
             data.EHCP_REVIEW_SPEC.cols,
             initial={"entry_id": entry.entry_id,
                      "local_authority": entry.local_authority},
             on_save=data.record_ehcp_review,
             intro=("An annual review with no next date gets one 12 months "
                    "on. The register's last / next review dates follow "
                    "the latest review."))


def _la_decision(tab: RecordTab, r: Any) -> None:
    ask_form(tab.frame, f"LA decision — review #{r.review_id}",
             (Col("decision", "Decision", "choice", required=True,
                  choices=data.LA_DECISIONS),
              Col("decision_date", "Decision date", "date", default=today),
              Col("notes", "Notes", "multiline")),
             initial={"decision": r.la_decision},
             on_save=lambda v: data.record_la_decision(
                 r.review_id, decision=v["decision"],
                 decision_date=v["decision_date"], notes=v["notes"]))


def _la_details(tab: RecordTab, e: Any) -> None:
    ask_form(tab.frame, f"Local authority — entry #{e.entry_id}",
             (Col("local_authority", "Local authority"),
              Col("caseworker", "Named LA caseworker"),
              Col("caseworker_email", "Caseworker e-mail"),
              Col("caseworker_phone", "Caseworker phone")),
             initial={"local_authority": e.local_authority,
                      "caseworker": e.la_caseworker,
                      "caseworker_email": e.la_caseworker_email,
                      "caseworker_phone": e.la_caseworker_phone},
             on_save=lambda v: data.set_la_details(e.entry_id, **v))


def _history(tab: RecordTab, e: Any) -> None:
    open_records_window(
        tab.frame, f"EHCP reviews — {e.student_id} (entry #{e.entry_id})",
        data.EHCP_REVIEW_SPEC, tab_title="Reviews",
        load=lambda _f: data.list_ehcp_reviews(entry_id=e.entry_id),
        create=data.record_ehcp_review, update=data.update_ehcp_review,
        delete=data.delete_ehcp_review,
        new_defaults=lambda _t: {"entry_id": e.entry_id,
                                 "local_authority": e.local_authority})


def _funding(tab: RecordTab, e: Any) -> None:
    open_records_window(
        tab.frame, f"High-needs funding — {e.student_id}",
        data.HN_FUNDING_SPEC, tab_title="Funding",
        load=lambda _f: data.list_hn_funding(entry_id=e.entry_id),
        create=data.create_hn_funding, update=data.update_hn_funding,
        delete=data.delete_hn_funding,
        columns=[*spec_columns(data.HN_FUNDING_SPEC),
                 ("Total (£)", lambda r: r.total, 90)],
        new_defaults=lambda _t: {"entry_id": e.entry_id,
                                 "local_authority": e.local_authority})


class EHCPPlansTab(RecordTab):
    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(
            nb, "EHCP Plans", None,
            load=lambda f: data.list_entries(register_status="EHCP",
                                             open_only=True),
            columns=(("Entry", lambda e: e.entry_id, 60),
                     ("Student", lambda e: e.student_id, 90),
                     ("Name", lambda e: self.names.get(e.student_id, "?"),
                      170),
                     ("EHCP ref", lambda e: e.ehcp_reference, 110),
                     ("Issued", lambda e: e.ehcp_issued_on, 95),
                     ("LA", lambda e: e.local_authority, 120),
                     ("Caseworker", lambda e: e.la_caseworker, 140),
                     ("Last review", lambda e: e.last_review_on, 95),
                     ("Next review", lambda e: e.next_review_due, 95),
                     ("SENCo", lambda e: e.senco, 120)),
            actions=(("Set LA / Caseworker", _la_details, True),
                     ("Record Review", _record_review, True),
                     ("Review History…", _history, True),
                     ("Funding…", _funding, True)),
            row_id=lambda e: e.entry_id,
            row_tag=lambda e: "overdue" if e.review_overdue else None,
            tag_colours=_RED)

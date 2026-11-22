"""Tkinter window: Young Carers.

Tabs: Young Carers (support records with review / end actions),
Exemptions Without a Record, and Summary. Every data call goes through
``young_carers`` (PASTORAL + sensitive-access log). Saving a record
re-derives the wellbeing "Young Carer" flag and the bursary attendance
exemption.
"""

from __future__ import annotations

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.young_carers import (
    young_carers as data,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._pastoral_ui import (
    ReportTab, counts_block, make_window,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form,
)

_TAGS = {"overdue": ("#ffd1d1", "#8c0d0d"), "ended": ("#eeeeee", "#555555")}


def _tag(r: Any) -> str | None:
    if not r.active:
        return "ended"
    return "overdue" if r.review_overdue else None


def _review(tab: RecordTab, rec: Any) -> None:
    ask_form(tab.frame, f"Review young carer support — {rec.student_id}",
             (Col("reviewed_on", "Reviewed on", "date", default=today),
              Col("next_review_due", "Next review due", "date"),
              Col("notes", "Review notes", "multiline")),
             on_save=lambda v: data.review_young_carer(
                 rec.carer_id, reviewed_on=v["reviewed_on"] or None,
                 next_review_due=v["next_review_due"] or None,
                 notes=v["notes"]))


def _end(tab: RecordTab, rec: Any) -> None:
    ask_form(tab.frame, f"No longer a young carer — {rec.student_id}",
             (Col("on", "End date", "date", default=today),
              Col("reason", "Reason", "multiline")),
             on_save=lambda v: data.end_young_carer(
                 rec.carer_id, on=v["on"] or None, reason=v["reason"]),
             intro=("Ends the record; the wellbeing flag and any bursary "
                    "attendance exemption end with it (kept as history)."))


def _sync(tab: RecordTab, _row: Any) -> None:
    flags, n = data.sync_all()
    messagebox.showinfo("Young Carers",
                        f"Checked {n} record(s); {flags} flag change(s).",
                        parent=tab.frame)


def open_young_carers_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Young Carers")

    RecordTab(
        nb, "Young Carers", data.SPEC,
        load=lambda f: data.list_young_carers(
            student_id=f.get("student_id") or None,
            active_only=bool(f.get("active")),
            review_overdue_only=bool(f.get("overdue")),
            no_consent_only=bool(f.get("no_consent"))),
        create=data.create_young_carer, update=data.update_young_carer,
        delete=data.delete_young_carer,
        filters=(Col("student_id", "Student", "student"),
                 Col("active", "Current only", "bool", default=True),
                 Col("overdue", "Review overdue", "bool"),
                 Col("no_consent", "No consent to share", "bool")),
        actions=(("Record Review", _review, True),
                 ("End Record", _end, True),
                 ("Re-sync Flags & Exemptions", _sync, False)),
        row_tag=_tag, tag_colours=_TAGS,
        intro=("Support record per young carer. 'Exempt from bursary "
               "attendance condition' keeps a matching 'Young carer' "
               "exemption in the bursary attendance scheme. Without "
               "consent to share, teaching staff only see that pastoral "
               "support is in place. Red = review overdue."))

    RecordTab(
        nb, "Exemptions Without a Record", None,
        load=lambda _f: data.exemptions_without_record(),
        columns=(("Exemption #", lambda r: r.exemption_id, 90),
                 ("Student", lambda r: r.student_id, 90),
                 ("Name", lambda r: r.student_name, 170),
                 ("From", lambda r: r.start_date, 95),
                 ("To", lambda r: r.end_date, 95),
                 ("Detail", lambda r: r.detail, 360)),
        row_id=lambda r: r.exemption_id,
        intro=("Open 'Young carer' bursary attendance exemptions that no "
               "support record owns. Create the support record (ticking "
               "the exemption box) and it adopts the exemption."))

    def render(_f: dict[str, str]) -> list[str]:
        s = data.summary()
        lines = ["Young carers", "",
                 f"  Current young carers:          {s.active}",
                 f"  Reviews overdue:               {s.reviews_overdue}",
                 f"  Reviews due in 30 days:        {s.reviews_due_30}",
                 f"  No consent to share:           {s.no_consent}",
                 f"  No needs assessment recorded:  {s.no_assessment}",
                 f"  Bursary attendance exemption:  {s.exempt}",
                 f"  Exemptions without a record:   {s.unlinked_exemptions}",
                 f"  Caring hours / week (total):   {s.hours_total}", ""]
        lines += counts_block("Impact", s.by_impact)
        lines += counts_block("Cared-for person's need", s.by_need)
        return lines

    ReportTab(nb, "Summary", render)

"""GUI tabs for destinations the university itself confirmed — added to
the KS5 Destinations window after the sustained-destination tabs.

* **Confirmed vs self-reported** — the leavers' cohort, each learner's
  LEAVING destination and whether it is confirmed by the institution
  (the university reported the enrolment) or self-reported (any other
  source), plus what the university has reported since.
* **University updates** — every enrolment / progression / withdrawal the
  university has sent, and what was done with it.
"""

from __future__ import annotations

import datetime as _dt
import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.progression.destinations import (
    university_confirmations as data,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)

_BASIS_TAGS = {data.BASIS_CONFIRMED: "good", data.BASIS_SELF: "warn",
               data.BASIS_NONE: "bad"}


def _default_year() -> int:
    # The most recent summer's leavers: they are the cohort the university
    # is reporting on during the current academic year.
    today = _dt.date.today()
    return today.year if today.month >= 8 else today.year - 1


def _year(f) -> int:
    raw = f.get("year") or ""
    if not raw.isdigit():
        raise ValueError("Leaver year must be a year, e.g. 2026")
    return int(raw)


def add_tabs(nb: ttk.Notebook) -> None:
    rt.notebook_tab(nb, "Confirmed vs self-reported", _cohort)
    rt.notebook_tab(nb, "University updates", _updates)


def _cohort(parent: ttk.Frame) -> None:
    def load(f):
        rows = [r.as_row() for r in data.cohort(_year(f))]
        basis = f.get("basis") or ""
        return [r for r in rows if not basis or r["basis"] == basis]

    def summary(table):
        year = _year(table.filters())
        counts = data.cohort_summary(year)
        total = counts.get("Leavers", 0)
        lines = [f"Leavers of {year}: {total}", ""]
        for k in (data.BASIS_CONFIRMED, data.BASIS_SELF, data.BASIS_NONE):
            pct = f" ({round(100 * counts[k] / total)}%)" if total else ""
            lines.append(f"  {k:<44} {counts[k]:>4}{pct}")
        lines.append("")
        for k in ("Needs review (differs from university)",
                  "Sustained (university reports progression)",
                  "Withdrew (university reports)"):
            lines.append(f"  {k:<44} {counts[k]:>4}")
        rt.show_text(table.parent, "Confirmed vs self-reported", "\n".join(lines))

    def history(table):
        row = table.require()
        confs = data.confirmations_for(row["student_id"])
        if not confs:
            rt.info(table.parent, "University updates",
                    f"The university has not reported on {row['student_name']}.")
            return
        lines = [f"{row['student_name']} — {row['destination']}", ""]
        for c in confs:
            extra = ""
            if c["event_type"] == "withdrawn":
                extra = f"  (reason: {data.REASON_LABELS.get(c['reason_category'] or '', '—')})"
            lines.append(f"  {c['event_date'] or '?'}  {c['outcome']}{extra}")
            lines.append(f"      {c['applied'] or ''}"
                         f"{'; ' + str(c['months_recorded']) + ' HE month(s) recorded' if c['months_recorded'] else ''}"
                         f"{'  — DIFFERS from recorded destination' if c['conflict'] else ''}")
        rt.show_text(table.parent, "University updates", "\n".join(lines))

    rt.RecordTable(
        parent,
        (("student_name", "Student", 170), ("student_id", "ID", 80),
         ("destination_type", "Type", 120), ("destination", "Destination", 260),
         ("recorded_via", "Recorded via", 200), ("basis", "Basis", 160),
         ("university_status", "University reports", 170), ("conflict", "", 60)),
        load, key="student_id",
        filters=[("year", "Leaver year", "text", (), _default_year()),
                 ("basis", "Basis", "choice",
                  (data.BASIS_CONFIRMED, data.BASIS_SELF, data.BASIS_NONE))],
        note=("Confirmed by institution = the university reported the learner enrolled "
              "(through the cross-system link). Self-reported = recorded from any other "
              "source (learner, parent, survey, UCAS Track…). A destination entered by "
              "hand is never overwritten; when the university's report differs it is "
              "marked 'Review' and a note is added to the record."),
        tags=lambda r: "bad" if r["conflict"] else _BASIS_TAGS.get(r["basis"]),
        actions=[("University updates", history), ("Summary", summary)],
        on_open=history)


def _updates(parent: ttk.Frame) -> None:
    types = ("enrolled", "progressed", "withdrawn")

    def load(f):
        return data.list_confirmations(event_type=f.get("type") or None,
                                       student_id=rt.student_id_of(f.get("student") or "")
                                       or None)

    rt.RecordTable(
        parent,
        (("event_date", "Date", 90), ("student_name", "Student", 160),
         ("student_id", "ID", 80), ("outcome", "Outcome", 170),
         ("institution", "Institution", 180), ("course", "Course", 180),
         ("reason", "Reason category", 110), ("applied", "Applied", 200),
         ("months_recorded", "HE months", 70)),
        load, key="confirmation_id",
        filters=[("type", "Type", "choice", types),
                 ("student", "Student", "choice", rt.student_choices)],
        note=("Reports received from the university. Only a reason category is ever "
              "sent for a withdrawal — never the reason itself."),
        tags=lambda r: "bad" if r.get("conflict") else (
            "warn" if r["event_type"] == "withdrawn" else "good"))


__all__ = ["add_tabs"]

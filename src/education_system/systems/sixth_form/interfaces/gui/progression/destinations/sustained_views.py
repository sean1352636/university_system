"""GUI tabs for month-by-month activity, sustained destinations and the
NCCIS-style export — added to the KS5 Destinations window after Records /
Missing / Summary.
"""

from __future__ import annotations

import datetime as _dt
import logging
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog

from education_system.systems.sixth_form.domain.progression.destinations import (
    sustained as data,
)
from education_system.systems.sixth_form.domain.progression.destinations.destinations import (
    DESTINATION_TYPES,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)

_TAGS = {"Not sustained": "bad", "No activity recorded": "warn",
         "Window not yet complete": "muted"}


def _default_year() -> int:
    today = _dt.date.today()
    # The most recent cohort whose window (to March) has closed.
    return today.year - 1 if today.month >= 4 else today.year - 2


def _year(f) -> int:
    raw = f.get("year") or ""
    if not raw.isdigit():
        raise ValueError("Leaver year must be a year, e.g. 2025")
    return int(raw)


def add_tabs(nb: ttk.Notebook) -> None:
    rt.notebook_tab(nb, "Sustained", _sustained)
    rt.notebook_tab(nb, "Monthly activity", _activity)
    rt.notebook_tab(nb, "NCCIS export", _export)


def _sustained(parent: ttk.Frame) -> None:
    def load(f):
        return [r.as_row() for r in data.cohort_sustained(_year(f))]

    def detail(table):
        row = table.require()
        r = data.sustained_status(row["student_id"],
                                  year_left=_year(table.filters()))
        lines = [f"{r.student_name} — left {r.leaver_year}: {r.status}", r.detail, ""]
        for m in r.window:
            lines.append(f"  {m}: {', '.join(r.by_month.get(m, [])) or '—'}")
        rt.show_text(table.parent, "Sustained destination", "\n".join(lines))

    def summary(table):
        year = _year(table.filters())
        counts = data.cohort_summary(year)
        total = sum(counts.values())
        lines = [f"Leavers of {year}: {total}", ""]
        lines += [f"  {k:<46} {v:>4}" for k, v in counts.items()]
        sustained = sum(v for k, v in counts.items() if k.startswith("Sustained"))
        if total:
            lines += ["", f"  Sustained overall: {sustained}/{total} "
                          f"({round(100 * sustained / total)}%)"]
        rt.show_text(table.parent, "Sustained destinations summary", "\n".join(lines))

    def set_leaver(table):
        row = table.require()
        rt.form_dialog(table.parent, f"Leaver details — {row['student_name']}",
                       (("leaver_year", "Leaver year (summer left)", "number"),
                        ("leaving_date", "Leaving date", "date"),
                        ("notes", "Notes", "text")),
                       {"leaver_year": row["leaver_year"] if row["leaver_year"] != "—" else ""},
                       lambda v: data.set_leaver(row["student_id"], v["leaver_year"],
                                                 leaving_date=v["leaving_date"] or None,
                                                 notes=v["notes"]),
                       table.refresh)

    rt.RecordTable(
        parent,
        (("student_name", "Student", 180), ("student_id", "ID", 80),
         ("leaver_year", "Left", 60), ("months", "Window months", 100),
         ("status", "Status", 280), ("detail", "Detail", 320)),
        load, key="student_id",
        filters=[("year", "Leaver year", "text", (), _default_year())],
        note=("Sustained = in the destination October to March of the year after "
              "leaving (education every month; employment 5 of 6; apprenticeship 6 "
              "consecutive months Aug–Jul; or a mix every month). Leavers come from "
              "the leaver year set here or the last Year 13 enrolment."),
        tags=lambda r: _TAGS.get(r["status"], "good"),
        actions=[("Months", detail), ("Summary", summary), ("Set leaver year…", set_leaver)],
        on_open=detail)


def _activity(parent: ttk.Frame) -> None:
    def load(f):
        sid = rt.student_id_of(f.get("student") or "")
        return data.list_activity(sid) if sid else []

    fields = (("student", "Student", "choice", rt.student_choices),
              ("from_month", "From month (YYYY-MM)", "text"),
              ("to_month", "To month (YYYY-MM, blank = same)", "text"),
              ("activity_type", "Activity", "choice", DESTINATION_TYPES),
              ("provider", "Provider / employer", "text"),
              ("source", "Source", "choice", data.ACTIVITY_SOURCES),
              ("notes", "Notes", "text"))

    def add(table):
        def save(v):
            sid = rt.student_id_of(v.pop("student"))
            data.record_activity_range(sid, v["from_month"], v["to_month"] or v["from_month"],
                                       v["activity_type"], provider=v["provider"],
                                       source=v["source"] or None, notes=v["notes"])
        rt.form_dialog(table.parent, "Record monthly activity", fields,
                       {"student": table.filters().get("student") or ""}, save, table.refresh)

    def delete(table):
        row = table.require()
        if rt.confirm(table.parent, "Delete", f"Delete {row['month']} {row['activity_type']}?"):
            data.delete_activity(row["activity_id"])
            table.refresh()

    rt.RecordTable(
        parent,
        (("month", "Month", 80), ("activity_type", "Activity", 160),
         ("provider", "Provider / employer", 220), ("source", "Source", 160),
         ("notes", "Notes", 260)),
        load, key="activity_id",
        filters=[("student", "Student", "choice", rt.student_choices)],
        note="Pick a learner and press Refresh. A range records the same activity each month.",
        actions=[("Record…", add), ("Delete", delete)])


def _export(parent: ttk.Frame) -> None:
    def load(f):
        return [{"name": l["name"], "columns": len(l["columns"]),
                 "delimiter": "tab" if l["delimiter"] == "\t" else l["delimiter"],
                 "codes": len(l["code_map"]), "notes": l["notes"] or ""}
                for l in data.list_layouts()]

    def export(table):
        row = table.require()
        rt.form_dialog(
            table.parent, f"Export — {row['name']}",
            (("year", "Leaver year", "number"),), {"year": _default_year()},
            lambda v: _save_export(table, row["name"], v["year"]),
            intro=("The exact NCCIS file specification is set by your local authority — "
                   "check the layout against it before sending."))

    def _layout_fields(layout=None):
        layout = layout or {}
        return (
            ("name", "Layout name", "text" if not layout else "readonly"),
            ("columns", "Columns (Header=field, one per line)", "longtext"),
            ("delimiter", "Delimiter", "choice", (",", ";", "|", "tab")),
            ("code_map", "Activity codes (Activity=code, one per line)", "multiline"),
            ("notes", "Notes", "text"),
        )

    def _save_layout(v, name=None):
        code_map = {}
        for line in (v.get("code_map") or "").splitlines():
            if line.strip():
                if "=" not in line:
                    raise ValueError(f"'{line}' should be Activity=code")
                k, c = (p.strip() for p in line.split("=", 1))
                code_map[k] = c
        data.save_layout(name or v["name"], data.parse_columns(v["columns"]),
                         delimiter="\t" if v["delimiter"] == "tab" else (v["delimiter"] or ","),
                         code_map=code_map, notes=v["notes"])

    def edit(table):
        row = table.require()
        layout = data.get_layout(row["name"])
        rt.form_dialog(
            table.parent, f"Layout — {row['name']}", _layout_fields(layout),
            {"name": layout["name"],
             "columns": "\n".join(f"{c['header']}={c['field']}" for c in layout["columns"]),
             "delimiter": "tab" if layout["delimiter"] == "\t" else layout["delimiter"],
             "code_map": "\n".join(f"{k}={v}" for k, v in layout["code_map"].items()),
             "notes": layout["notes"]},
            lambda v: _save_layout(v, layout["name"]), table.refresh,
            intro="Fields: " + ", ".join(data.available_fields()))

    def new(table):
        rt.form_dialog(table.parent, "New export layout", _layout_fields(),
                       {"delimiter": ","}, _save_layout, table.refresh,
                       intro="Fields: " + ", ".join(data.available_fields()))

    def delete(table):
        row = table.require()
        if rt.confirm(table.parent, "Delete", f"Delete layout {row['name']}?"):
            data.delete_layout(row["name"])
            table.refresh()

    rt.RecordTable(
        parent,
        (("name", "Layout", 260), ("columns", "Columns", 70), ("delimiter", "Delimiter", 70),
         ("codes", "Codes mapped", 90), ("notes", "Notes", 420)),
        load, key="name",
        note=("NCCIS-style CSV of a leaver cohort. Layouts are configurable because each "
              "local authority's NCCIS import differs — confirm the columns and activity "
              "codes with your LA."),
        actions=[("Export…", export), ("New layout…", new), ("Edit layout…", edit),
                 ("Delete layout", delete)],
        on_open=edit)


def _save_export(table, layout_name: str, year: str) -> None:
    if not str(year).isdigit():
        raise ValueError("Leaver year must be a year")
    path = filedialog.asksaveasfilename(
        parent=table.parent.winfo_toplevel(), defaultextension=".csv",
        initialfile=f"destinations_{year}.csv", filetypes=[("CSV", "*.csv")])
    if not path:
        raise ValueError("No file chosen — nothing exported.")
    n = data.export_to_file(layout_name, int(year), path)
    rt.info(table.parent, "Exported", f"{n} row(s) written to {path}")


__all__ = ["add_tabs"]

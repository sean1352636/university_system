"""CLI flows for monthly activity, sustained destinations and the
NCCIS-style export. Listed in the Destinations menu after its originals.
"""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.sixth_form.domain.progression.destinations import (
    sustained as data,
)
from education_system.systems.sixth_form.domain.progression.destinations.destinations import (
    DESTINATION_TYPES,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

logger = logging.getLogger(__name__)


def _year() -> int:
    today = _dt.date.today()
    default = today.year - 1 if today.month >= 4 else today.year - 2
    return rm.ask_int("Leaver year (summer left)", default=default) or default


def cohort() -> None:
    year = _year()
    rm.print_table([r.as_row() for r in data.cohort_sustained(year)],
                   (("student_id", "ID", 10), ("student_name", "Student", 22),
                    ("months", "Months", 6), ("status", "Status", 42),
                    ("detail", "Detail", 36)))
    counts = data.cohort_summary(year)
    print()
    for k, v in counts.items():
        print(f"  {k:<46} {v:>4}")
    rm.pause()


def one_learner() -> None:
    sid = rm.pick_student()
    r = data.sustained_status(sid)
    print(f"\n  {r.student_name} — left {r.leaver_year or '?'}: {r.status}  {r.detail}")
    for m in r.window:
        print(f"    {m}: {', '.join(r.by_month.get(m, [])) or '—'}")
    rm.pause()


def record_activity() -> None:
    sid = rm.pick_student()
    start = rm.ask("From month (YYYY-MM)", required=True)
    end = rm.ask("To month (YYYY-MM)", default=start)
    activity = rm.choose("Activity", DESTINATION_TYPES)
    n = data.record_activity_range(
        sid, start, end, activity, provider=rm.ask("Provider / employer"),
        source=rm.choose("Source", data.ACTIVITY_SOURCES, allow_blank=True) or None,
        notes=rm.ask("Notes"))
    print(f"  ✓ {n} month(s) recorded.")
    rm.pause()


def list_activity() -> None:
    sid = rm.pick_student()
    rows = data.list_activity(sid)
    rm.print_table(rows, (("activity_id", "#", 5), ("month", "Month", 7),
                          ("activity_type", "Activity", 18), ("provider", "Provider", 24),
                          ("source", "Source", 22)))
    if rows and rm.ask_yes("Delete one?"):
        row = rm.pick_row(rows, "activity_id", "Activity #")
        if row and data.delete_activity(row["activity_id"]):
            print("  ✓ Deleted.")
    rm.pause()


def set_leaver() -> None:
    sid = rm.pick_student()
    data.set_leaver(sid, rm.ask_int("Leaver year", default=data.leaver_year(sid)),
                    leaving_date=rm.ask("Leaving date (YYYY-MM-DD)") or None,
                    notes=rm.ask("Notes"))
    print("  ✓ Saved.")
    rm.pause()


def layouts() -> None:
    rows = data.list_layouts()
    for layout in rows:
        print(f"\n  {layout['name']}  (delimiter {layout['delimiter']!r}, "
              f"{len(layout['code_map'])} activity codes mapped)")
        for c in layout["columns"]:
            print(f"    {c['header']:<26} = {c['field']}")
    print("\n  The NCCIS specification is your local authority's — confirm the layout with them.")
    if rm.ask_yes("Create or replace a layout?"):
        print("  Fields: " + ", ".join(data.available_fields()))
        name = rm.ask("Layout name", required=True)
        cols = data.parse_columns(rm.ask_long("Columns, one 'Header=field' per line"))
        codes = {}
        for line in rm.ask_long("Activity codes, one 'Activity=code' per line (blank = none)"
                                ).splitlines():
            if "=" in line:
                k, v = (p.strip() for p in line.split("=", 1))
                codes[k] = v
        delim = rm.choose("Delimiter", (",", ";", "|", "tab"), default=",")
        data.save_layout(name, cols, delimiter="\t" if delim == "tab" else delim,
                         code_map=codes)
        print("  ✓ Saved.")
    rm.pause()


def export() -> None:
    names = [l["name"] for l in data.list_layouts()]
    name = rm.choose("Layout", names, default=data.DEFAULT_LAYOUT_NAME
                     if data.DEFAULT_LAYOUT_NAME in names else None)
    year = _year()
    path = rm.ask("Save to file path (blank = print here)")
    if path:
        n = data.export_to_file(name, year, path)
        print(f"  ✓ {n} row(s) written to {path}")
    else:
        print()
        print(data.export_csv(name, year))
    rm.pause()


MENU = (
    ("Sustained destinations — cohort", cohort),
    ("Sustained destination — one learner", one_learner),
    ("Record monthly activity", record_activity),
    ("List / delete monthly activity", list_activity),
    ("Set leaver year", set_leaver),
    ("Export layouts (NCCIS-style)", layouts),
    ("Export CSV (NCCIS-style)", export),
)

__all__ = ["MENU"]

"""Tkinter window for fire drills and recurring premises checks
(Health & Safety). Also opened from the Health & Safety window."""

from __future__ import annotations

import datetime as _dt
import logging
from tkinter import ttk

from education_system.systems.sixth_form.domains.operations.domain.health_safety import (
    premises_checks as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    make_window,
)
from education_system.systems.sixth_form.interfaces.gui.progression import (
    _record_tabs as rt,
)

logger = logging.getLogger(__name__)

_DUE_TAG = {data.OVERDUE: "bad", data.NEVER: "bad", data.DUE_SOON: "warn",
            data.OK: "good"}


def _key(label: str) -> str:
    return (label or "").split(" — ")[0].strip()


def _type_choices() -> list[str]:
    return [f"{t.type_id} — {t.name}"
            for t in data.list_check_types(active_only=True)]


def _rollcall_choices() -> list[str]:
    try:
        return [f"{r.drill_id} — {r.kind} {r.date} {r.started_at[-8:-3]} "
                f"({r.state}, {r.expected} expected)"
                for r in data.recent_rollcalls()]
    except Exception:
        logger.exception("Could not list roll calls")
        return []


_DRILL_FIELDS = (
    ("drill_date", "Date", "date"),
    ("drill_time", "Time of alarm (HH:MM)", "text"),
    ("drill_type", "Type", "choice", data.DRILL_TYPES),
    ("scenario", "Scenario / zone / call point", "text"),
    ("evacuation_time", "Building clear in (m:ss)", "text"),
    ("assembly_point", "Assembly point", "text"),
    ("people_evacuated", "People evacuated", "number"),
    ("rollcall_complete", "Roll call completed", "bool"),
    ("rollcall_time", "Roll call took (m:ss)", "text"),
    ("issues_found", "Issues found", "multiline"),
    ("led_by", "Led by", "text"),
    ("notes", "Notes", "text"),
)


def _refuse(parent, title: str, message: str) -> None:
    from education_system.platform.delivery.gui.parented_dialogs import messagebox
    messagebox.showwarning(title, message,
                           parent=getattr(parent, "root", parent))


def open_premises_checks_window(parent=None) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    if not any(p.can(c) for c in (access.OPERATIONS, access.GOVERNANCE,
                                  access.REPORTS)):
        _refuse(parent, "Fire Drills & Premises Checks",
                "Fire and premises records are for site / operations "
                "staff.")
        return
    data.init_db()
    win, nb = make_window(parent, "Fire Drills & Premises Checks")
    tables: list[rt.RecordTable] = []

    def refresh_all() -> None:
        for t in tables:
            t.refresh()

    def record_check(table, type_id=None) -> None:
        types = _type_choices()
        if not types:
            raise ValueError("Set up the check types first (Check types "
                             "tab — 'Add standard UK list').")
        rt.form_dialog(
            table.parent, "Record a premises check",
            (("type", "Check", "choice", types),
             ("checked_on", "Date", "date"),
             ("checked_at", "Time (HH:MM)", "text"),
             ("location", "Where (call point, zone, outlet)", "text"),
             ("result", "Result", "choice", data.RESULTS),
             ("findings", "Findings (required unless a clean pass)",
              "multiline"),
             ("checked_by", "Checked by (blank = you)", "text"),
             ("action", "Follow-up action (optional)", "text"),
             ("action_owner", "Action owner", "text"),
             ("action_due", "Action due", "date")),
            {"type": next((t for t in types if _key(t) == str(type_id)), ""),
             "checked_on": _dt.date.today().isoformat(),
             "result": data.PASS},
            lambda v: data.record_check({**v, "type_id": _key(v["type"])}),
            refresh_all)

    # ── Due register ──
    def register_tab(parent: ttk.Frame) -> None:
        def load(f):
            rows = (data.overdue_checks(include_due_soon=True)
                    if f.get("show") == "Needs doing"
                    else data.check_register())
            return [{"id": d.type_id or 0, "name": d.name,
                     "category": d.category, "freq": d.frequency,
                     "last": d.last_done or "", "result": d.last_result or "",
                     "next": d.next_due or "", "state": d.state,
                     "late": d.days_overdue or ""} for d in rows]

        def record(table):
            row = table.require()
            if not row["id"]:
                log_drill(table)
                return
            record_check(table, row["id"])

        tables.append(rt.RecordTable(
            parent,
            [("name", "Check", 300), ("category", "Category", 150),
             ("freq", "Frequency", 100), ("last", "Last done", 100),
             ("result", "Last result", 120), ("next", "Next due", 100),
             ("state", "State", 100), ("late", "Days overdue", 90)],
            load, key="id",
            filters=(("show", "Show", "choice", ("Needs doing",)),),
            actions=(("Record check / drill", record),),
            tags=lambda r: _DUE_TAG.get(r["state"]), on_open=record,
            note="Every active check with when it is next due. The fire "
                 "evacuation drill is due once a term."))

    # ── Check log ──
    def checks_tab(parent: ttk.Frame) -> None:
        def load(f):
            return [{"id": c.check_id, "date": c.checked_on,
                     "time": c.checked_at or "", "check": c.type_name,
                     "where": c.location or "", "result": c.result,
                     "findings": c.findings or "", "by": c.checked_by or ""}
                    for c in data.list_checks(
                        type_id=int(_key(f["type"])) if f.get("type")
                        else None,
                        result=f.get("result") or None,
                        date_from=f.get("from") or None,
                        date_to=f.get("to") or None)]

        def add_action(table):
            row = table.require()
            _action_dialog(table.parent, {"check_id": row["id"]},
                           refresh_all)

        tables.append(rt.RecordTable(
            parent,
            [("date", "Date", 95), ("time", "Time", 60),
             ("check", "Check", 260), ("where", "Where", 170),
             ("result", "Result", 120), ("findings", "Findings", 300),
             ("by", "Checked by", 130)],
            load, key="id",
            filters=(("type", "Check", "choice", _type_choices),
                     ("result", "Result", "choice", data.RESULTS),
                     ("from", "From", "text"), ("to", "To", "text")),
            actions=(("Record check", record_check),
                     ("Raise action", add_action)),
            tags=lambda r: ("bad" if r["result"] == data.FAIL else
                            "warn" if r["result"] == data.ADVISORY else None)))

    # ── Fire drills ──
    def log_drill(table) -> None:
        rt.form_dialog(table.parent, "Log a fire drill / evacuation",
                       _DRILL_FIELDS + (
                           ("rollcall", "Link roll call (attendance)",
                            "choice", [""] + _rollcall_choices()),),
                       {"drill_date": _dt.date.today().isoformat(),
                        "drill_type": data.DEFAULT_DRILL_TYPE},
                       lambda v: data.log_drill({
                           **v, "rollcall_id": _key(v.pop("rollcall"))
                           or None}),
                       refresh_all)

    def drills_tab(parent: ttk.Frame) -> None:
        def load(f):
            return [{"id": d.drill_id, "date": d.drill_date,
                     "time": d.drill_time or "", "type": d.drill_type,
                     "scenario": d.scenario or "",
                     "evac": d.evacuation_label,
                     "assembly": d.assembly_point or "",
                     "rollcall": ("complete" if d.rollcall_complete
                                  else "incomplete") +
                     (f" ({data.fmt_duration(d.rollcall_seconds)})"
                      if d.rollcall_seconds is not None else "") +
                     (f", {d.rollcall_missing} missing"
                      if d.rollcall_missing else ""),
                     "issues": d.issues_found or ""}
                    for d in data.list_drills(
                        drill_type=f.get("type") or None,
                        date_from=f.get("from") or None,
                        date_to=f.get("to") or None)]

        def edit(table):
            d = data.get_drill(table.require()["id"])
            init = {**vars(d), "evacuation_time": d.evacuation_label,
                    "rollcall_time": data.fmt_duration(d.rollcall_seconds)}
            rt.form_dialog(table.parent, f"Fire drill #{d.drill_id}",
                           _DRILL_FIELDS, init,
                           lambda v: data.update_drill(d.drill_id, v),
                           refresh_all)

        def link(table):
            d = data.get_drill(table.require()["id"])
            rt.form_dialog(table.parent, "Link the attendance roll call",
                           (("rollcall", "Roll call", "choice",
                             _rollcall_choices()),),
                           {}, lambda v: data.link_rollcall(
                               d.drill_id, int(_key(v["rollcall"]))),
                           refresh_all)

        def from_rollcall(table):
            rt.form_dialog(table.parent, "Log a drill from a roll call",
                           (("rollcall", "Roll call", "choice",
                             _rollcall_choices()),
                            ("scenario", "Scenario / zone", "text"),
                            ("issues_found", "Issues found", "multiline")),
                           {}, lambda v: data.log_drill_from_rollcall(
                               int(_key(v["rollcall"])),
                               scenario=v["scenario"],
                               issues_found=v["issues_found"]), refresh_all)

        def add_action(table):
            _action_dialog(table.parent, {"drill_id": table.require()["id"]},
                           refresh_all)

        def report(table):
            f = table.filters()
            r = data.drill_report(date_from=f.get("from") or None,
                                  date_to=f.get("to") or None)
            lines = ["Fire drill report"
                     + (f" {f.get('from') or ''} – {f.get('to') or ''}"
                        if f.get("from") or f.get("to") else ""), "",
                     f"  Drills / alarms logged: {r['drills']}"]
            lines += [f"    {k:<28} {v}" for k, v in r["by_type"].items()]
            lines += ["",
                      f"  Average evacuation:  {r['average_evacuation'] or '—'}",
                      f"  Slowest evacuation:  {r['slowest_evacuation'] or '—'}",
                      f"  Roll calls linked:   {r['rollcalls_linked']}",
                      f"  Roll calls complete: {r['rollcalls_complete']}",
                      f"  Drills with issues:  {r['with_issues']}",
                      f"  Actions raised:      {r['actions']} "
                      f"({r['actions_open']} open)"]
            rt.show_text(table.parent, "Fire drill report", "\n".join(lines))

        tables.append(rt.RecordTable(
            parent,
            [("date", "Date", 95), ("time", "Time", 60),
             ("type", "Type", 150), ("scenario", "Scenario", 180),
             ("evac", "Clear in", 70), ("assembly", "Assembly", 120),
             ("rollcall", "Roll call", 220), ("issues", "Issues", 300)],
            load, key="id",
            filters=(("type", "Type", "choice", data.DRILL_TYPES),
                     ("from", "From", "text"), ("to", "To", "text")),
            actions=(("Log drill", log_drill), ("Edit", edit),
                     ("Link roll call", link),
                     ("Log from roll call", from_rollcall),
                     ("Raise action", add_action), ("Report", report)),
            tags=lambda r: "warn" if r["issues"] else None, on_open=edit))

    # ── Actions ──
    def actions_tab(parent: ttk.Frame) -> None:
        def load(f):
            return [{"id": a.action_id, "source": a.source,
                     "action": a.action, "owner": a.owner or "",
                     "due": a.due_date or "", "status": a.status,
                     "done": a.completed_on or "", "notes": a.notes or "",
                     "_late": a.is_overdue}
                    for a in data.list_actions(
                        open_only=f.get("open") == "Yes")]

        def done(table):
            data.set_action_status(table.require()["id"], data.ACTION_DONE)
            refresh_all()

        def cancel(table):
            row = table.require()
            rt.form_dialog(table.parent, "Cancel action",
                           (("notes", "Why", "text"),), {},
                           lambda v: data.set_action_status(
                               row["id"], data.ACTION_CANCELLED,
                               notes=v["notes"]), refresh_all)

        tables.append(rt.RecordTable(
            parent,
            [("source", "From", 100), ("action", "Action", 340),
             ("owner", "Owner", 140), ("due", "Due", 95),
             ("status", "Status", 90), ("done", "Done on", 95),
             ("notes", "Notes", 240)],
            load, key="id",
            filters=(("open", "Open only", "choice", ("Yes",), "Yes"),),
            actions=(("Mark done", done), ("Cancel", cancel)),
            tags=lambda r: "bad" if r["_late"] else (
                "muted" if r["status"] != data.ACTION_OPEN else None)))

    # ── Check types ──
    def types_tab(parent: ttk.Frame) -> None:
        fields = (("name", "Check", "text"),
                  ("category", "Category", "choice", data.CHECK_CATEGORIES),
                  ("frequency", "Frequency", "choice",
                   list(data.FREQUENCIES)),
                  ("due_soon_days", "Warn 'due soon' (days before)",
                   "number"),
                  ("guidance", "Guidance / standard", "multiline"),
                  ("responsible", "Responsible", "text"),
                  ("active", "Active", "bool"))

        def new(table):
            rt.form_dialog(table.parent, "New check type", fields,
                           {"active": True, "frequency": "Monthly",
                            "category": "General", "due_soon_days": 7},
                           data.create_check_type, refresh_all)

        def edit(table):
            t = data.get_check_type(table.require()["id"])
            rt.form_dialog(table.parent, f"Edit {t.name}", fields, vars(t),
                           lambda v: data.update_check_type(t.type_id, v),
                           refresh_all)

        def install(table):
            if rt.confirm(table.parent, "Standard list",
                          "Add the standard UK premises check list (fire "
                          "alarm weekly, emergency lighting monthly/annual, "
                          "legionella, PAT, EICR, gas…)? Existing checks "
                          "are unchanged and nothing is marked as done."):
                made = data.install_default_check_types()
                rt.info(table.parent, "Standard list",
                        f"Added {len(made)} check type(s).")
                refresh_all()

        tables.append(rt.RecordTable(
            parent,
            [("name", "Check", 300), ("category", "Category", 150),
             ("freq", "Frequency", 100), ("soon", "Warn (days)", 80),
             ("resp", "Responsible", 140), ("guide", "Guidance", 380),
             ("active", "Active", 60)],
            lambda _f: [{"id": t.type_id, "name": t.name,
                         "category": t.category, "freq": t.frequency,
                         "soon": t.due_soon_days,
                         "resp": t.responsible or "",
                         "guide": t.guidance or "", "active": t.active}
                        for t in data.list_check_types()],
            key="id",
            actions=(("New", new), ("Edit", edit),
                     ("Add standard UK list", install)),
            tags=lambda r: None if r["active"] else "muted", on_open=edit))

    rt.notebook_tab(nb, "Due register", register_tab)
    rt.notebook_tab(nb, "Check log", checks_tab)
    rt.notebook_tab(nb, "Fire drills", drills_tab)
    rt.notebook_tab(nb, "Actions", actions_tab)
    rt.notebook_tab(nb, "Check types", types_tab)


def _action_dialog(parent, link: dict, after) -> None:
    rt.form_dialog(parent, "Raise a follow-up action",
                   (("action", "Action", "text"), ("owner", "Owner", "text"),
                    ("due_date", "Due", "date"),
                    ("notes", "Notes", "multiline")),
                   {}, lambda v: data.add_action({**v, **link}), after)

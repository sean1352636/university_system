"""Tkinter window for the staff mandatory-training matrix (HR)."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.sixth_form.domain.staff.mandatory_training import (
    mandatory_training as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    make_window,
)
from education_system.systems.sixth_form.interfaces.gui.progression import (
    _record_tabs as rt,
)

logger = logging.getLogger(__name__)

_STATE_TAG = {data.OVERDUE: "bad", data.MISSING: "bad",
              data.DUE_SOON: "warn", data.DONE: "good"}
_SHORT = {data.DONE: "✓", data.DUE_SOON: "due", data.OVERDUE: "OVERDUE",
          data.MISSING: "missing", data.NOT_REQUIRED: ""}


def _staff_mod():
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    return _staff


def _staff_choices() -> list[str]:
    return [f"{s.staff_id} — {s.full_name} ({s.role})"
            for s in _staff_mod().list_staff(active_only=True)]


def _type_choices() -> list[str]:
    return [f"{t.type_id} — {t.name}" for t in data.list_types(active_only=True)]


def _key(label: str) -> str:
    return (label or "").split(" — ")[0].strip()


def cell_text(c: data.Cell) -> str:
    if c.state == data.NOT_REQUIRED:
        return ""
    if c.state == data.MISSING:
        return "missing"
    if c.state == data.DONE and not c.expires_on:
        return "✓"
    mark = _SHORT[c.state]
    return f"{mark} {c.expires_on}" if c.expires_on else mark


def record_dialog(parent: tk.Misc, after, *, staff_id: str | None = None,
                  type_id: int | None = None) -> None:
    staff = _staff_choices()
    types = _type_choices()
    rt.form_dialog(
        parent, "Record training completed",
        (("staff", "Staff member", "choice", staff),
         ("type", "Training", "choice", types),
         ("completed_on", "Completed on", "date"),
         ("expires_on", "Expires on (blank = from renewal period)", "date"),
         ("provider", "Provider", "text"),
         ("evidence", "Certificate / evidence", "multiline")),
        {"staff": next((s for s in staff if _key(s) == staff_id), ""),
         "type": next((t for t in types if _key(t) == str(type_id)), ""),
         "completed_on": _dt.date.today().isoformat()},
        lambda v: data.record_completion({
            **v, "staff_id": _key(v["staff"]), "type_id": _key(v["type"])}),
        after,
        intro="Prevent training is written to the Prevent register; CPD "
              "activities linked to a training type count automatically.")


def _refuse(parent, title: str, message: str) -> None:
    from education_system.platform.delivery.gui.parented_dialogs import messagebox
    messagebox.showwarning(title, message,
                           parent=getattr(parent, "root", parent))


def open_mandatory_training_window(parent=None) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    if not access.current().can(access.HR):
        _refuse(parent, "Mandatory Training", "The training matrix is for "
                "HR. Your own training is under My area.")
        return
    data.init_db()
    win, nb = make_window(parent, "Mandatory Training")
    tables: list[rt.RecordTable] = []
    matrix_refresh: list = []

    def refresh_all() -> None:
        for t in tables:
            t.refresh()
        for f in matrix_refresh:
            f()

    rt.notebook_tab(nb, "Matrix",
                    lambda p: matrix_refresh.append(_matrix_tab(p, refresh_all)))

    # ── Expiring ──
    def expiring_tab(parent: ttk.Frame) -> None:
        def load(f):
            days = f.get("days") or "30"
            if not days.isdigit():
                raise ValueError("Days must be a whole number")
            today = _dt.date.today()
            return [{"id": f"{c.staff_id}:{c.type_id}",
                     "staff_id": c.staff_id, "type_id": c.type_id,
                     "staff": c.staff_name, "training": c.type_name,
                     "state": c.state, "completed": c.completed_on or "",
                     "expires": c.expires_on or "",
                     "days": "" if c.days_left(today) is None
                     else c.days_left(today),
                     "source": c.latest.source if c.latest else ""}
                    for c in data.expiring(
                        within_days=int(days),
                        include_missing=f.get("missing") == "Yes",
                        department=f.get("dept") or None)]

        def record(table):
            row = table.require()
            record_dialog(table.parent, refresh_all, staff_id=row["staff_id"],
                          type_id=row["type_id"])

        tables.append(rt.RecordTable(
            parent,
            [("staff", "Staff", 180), ("training", "Training", 280),
             ("state", "State", 90), ("completed", "Last done", 100),
             ("expires", "Expires", 100), ("days", "Days left", 80),
             ("source", "Evidence from", 130)],
            load, key="id",
            filters=(("days", "Expiring within (days)", "text", (), "30"),
                     ("missing", "Include never done", "choice", ("Yes",)),
                     ("dept", "Department", "choice",
                      lambda: _staff_mod().DEPARTMENTS)),
            actions=(("Record completion", record),),
            tags=lambda r: _STATE_TAG.get(r["state"]), on_open=record,
            note="Required training that runs out within the window, plus "
                 "anything already overdue."))

    # ── Records ──
    def records_tab(parent: ttk.Frame) -> None:
        names = {}

        def load(f):
            if not names:
                names.update({s.staff_id: s.full_name
                              for s in _staff_mod().list_staff()})
            types = {t.type_id: t.name for t in data.list_types()}
            return [{"id": c.completion_id, "staff_id": c.staff_id,
                     "staff": names.get(c.staff_id, c.staff_id),
                     "training": types.get(c.type_id, c.type_id),
                     "completed": c.completed_on,
                     "expires": c.expires_on or "never",
                     "provider": c.provider or "",
                     "evidence": c.evidence or "",
                     "by": c.recorded_by or "",
                     "archived": (f"{c.archived_reason} ({c.archived_by})"
                                  if c.archived_at else "")}
                    for c in data.list_completions(
                        staff_id=_key(f.get("staff")) or None,
                        type_id=int(_key(f["type"])) if f.get("type")
                        else None,
                        include_archived=f.get("archived") == "Yes")]

        def archive(table):
            row = table.require()
            if row["archived"]:
                raise ValueError("That record is already archived")
            rt.form_dialog(table.parent, "Archive training record",
                           (("reason", "Why (e.g. entered in error)",
                             "text"),),
                           {}, lambda v: data.archive_completion(
                               row["id"], v["reason"]), refresh_all)

        tables.append(rt.RecordTable(
            parent,
            [("id", "#", 50), ("staff", "Staff", 170),
             ("training", "Training", 240), ("completed", "Completed", 95),
             ("expires", "Expires", 95), ("provider", "Provider", 140),
             ("evidence", "Evidence", 200), ("by", "Recorded by", 120),
             ("archived", "Archived", 180)],
            load, key="id",
            filters=(("staff", "Staff", "choice", _staff_choices),
                     ("type", "Training", "choice", _type_choices),
                     ("archived", "Include archived", "choice", ("Yes",))),
            actions=(("Record completion",
                      lambda t: record_dialog(t.parent, refresh_all)),
                     ("Archive", archive)),
            tags=lambda r: "muted" if r["archived"] else None,
            note="Records entered here. CPD attendance on linked activities, "
                 "the Prevent register and HR safeguarding dates also count "
                 "in the matrix."))

    # ── Training types ──
    def types_tab(parent: ttk.Frame) -> None:
        fields = (("code", "Code (e.g. KCSIE)", "text"),
                  ("name", "Name", "text"),
                  ("renewal_months", "Renew every (months, blank = once)",
                   "number"),
                  ("due_soon_days", "Warn 'due soon' (days before)",
                   "number"),
                  ("evidence_source", "Also count", "choice",
                   list(data.EVIDENCE_SOURCES)),
                  ("description", "Description", "multiline"),
                  ("active", "Active", "bool"))

        def load(_f):
            return [{"id": t.type_id, "code": t.code, "name": t.name,
                     "renewal": t.renewal_label,
                     "soon": t.due_soon_days,
                     "source": data.EVIDENCE_SOURCE_LABELS.get(
                         t.evidence_source, t.evidence_source),
                     "who": "; ".join(t.requirements) or "(nobody yet)",
                     "active": t.active} for t in data.list_types()]

        def new(table):
            rt.form_dialog(table.parent, "New training type", fields,
                           {"active": True, "due_soon_days": 60},
                           data.create_type, refresh_all)

        def edit(table):
            t = data.get_type(table.require()["id"])
            rt.form_dialog(table.parent, f"Edit {t.name}", fields, vars(t),
                           lambda v: data.update_type(t.type_id, v),
                           refresh_all)

        def who(table):
            t = data.get_type(table.require()["id"])
            rt.form_dialog(
                table.parent, f"Who needs {t.name}",
                (("targets", "One per line", "longtext"),
                 ("help", "Options", "readonly")),
                {"targets": "\n".join(t.requirements),
                 "help": "All staff · Role: <job role> · Designation: DSL / "
                         "Tutor / Examiner · Staff: <staff id>. Roles: "
                         + ", ".join(_staff_mod().ROLES)},
                lambda v: data.set_requirements(
                    t.type_id, v["targets"].splitlines()), refresh_all)

        def add_person(table):
            t = data.get_type(table.require()["id"])
            rt.form_dialog(table.parent, f"Named person for {t.name}",
                           (("staff", "Staff member", "choice",
                             _staff_choices()),),
                           {}, lambda v: data.add_requirement(
                               t.type_id, f"Staff: {_key(v['staff'])}"),
                           refresh_all)

        def install(table):
            if rt.confirm(table.parent, "Standard list",
                          "Add the standard UK list of training types and "
                          "who needs them? Types you already have are left "
                          "unchanged. Nothing is marked as completed."):
                made = data.install_default_types()
                rt.info(table.parent, "Standard list",
                        f"Added {len(made)} training type(s).")
                refresh_all()

        def delete(table):
            row = table.require()
            if rt.confirm(table.parent, "Delete",
                          f"Delete training type {row['name']}?"):
                data.delete_type(row["id"])
                refresh_all()

        tables.append(rt.RecordTable(
            parent,
            [("code", "Code", 100), ("name", "Name", 260),
             ("renewal", "Renewal", 110), ("soon", "Warn (days)", 80),
             ("source", "Also counts", 170), ("who", "Required by", 380),
             ("active", "Active", 60)],
            load, key="id",
            actions=(("New", new), ("Edit", edit), ("Who needs it", who),
                     ("Add named person", add_person),
                     ("Add standard UK list", install), ("Delete", delete)),
            tags=lambda r: None if r["active"] else "muted", on_open=edit))

    # ── CPD links ──
    def cpd_tab(parent: ttk.Frame) -> None:
        def activities() -> list[str]:
            from education_system.systems.sixth_form.domain.staff.cpd import cpd
            return [f"{a.activity_id} — {a.title} ({a.activity_date})"
                    for a in cpd.list_activities()]

        def link(table):
            rt.form_dialog(table.parent, "Count a CPD activity as training",
                           (("activity", "CPD activity", "choice",
                             activities()),
                            ("type", "Counts as", "choice", _type_choices())),
                           {}, lambda v: data.link_cpd_activity(
                               int(_key(v["activity"])),
                               int(_key(v["type"]))), refresh_all)

        def unlink(table):
            row = table.require()
            if rt.confirm(table.parent, "Unlink",
                          f"Stop counting '{row['activity']}' as "
                          f"{row['type']}?"):
                data.unlink_cpd_activity(row["activity_id"], row["type_id"])
                refresh_all()

        tables.append(rt.RecordTable(
            parent,
            [("activity", "CPD activity", 340), ("date", "Date", 100),
             ("type", "Counts as", 300)],
            lambda _f: [{**r, "id": f"{r['activity_id']}:{r['type_id']}"}
                        for r in data.list_cpd_links()],
            key="id", actions=(("Link activity", link), ("Unlink", unlink)),
            note="Staff whose CPD record on a linked activity is Attended or "
                 "Completed are counted as having done that training on the "
                 "date they attended."))

    # ── Compliance ──
    def compliance_tab(parent: ttk.Frame) -> None:
        def load(f):
            return [{"id": r.type_id, "name": r.name,
                     "required": r.required, "done": r.done,
                     "soon": r.due_soon, "overdue": r.overdue,
                     "missing": r.missing,
                     "pct": "" if r.percent is None else f"{r.percent}%"}
                    for r in data.compliance_by_type(
                        department=f.get("dept") or None)]

        def push(table):
            item = data.update_compliance_register()
            rt.info(table.parent, "Compliance register",
                    f"Compliance item #{item.item_id} '{item.title}' is now "
                    f"{item.status}.")

        tables.append(rt.RecordTable(
            parent,
            [("name", "Training", 300), ("required", "Staff needing it", 110),
             ("done", "In date", 80), ("soon", "Due soon", 80),
             ("overdue", "Overdue", 80), ("missing", "Never done", 90),
             ("pct", "% in date", 80)],
            load, key="id",
            filters=(("dept", "Department", "choice",
                      lambda: _staff_mod().DEPARTMENTS),),
            actions=(("Update compliance register", push),),
            tags=lambda r: "bad" if r["overdue"] or r["missing"] else "good"))

    rt.notebook_tab(nb, "Expiring", expiring_tab)
    rt.notebook_tab(nb, "Records", records_tab)
    rt.notebook_tab(nb, "Training types", types_tab)
    rt.notebook_tab(nb, "CPD links", cpd_tab)
    rt.notebook_tab(nb, "Compliance", compliance_tab)


def _matrix_tab(parent: ttk.Frame, refresh_all):
    """Staff × training grid; returns its refresh function."""
    staff_mod = _staff_mod()
    fbar = ttk.Frame(parent)
    fbar.pack(fill="x", pady=(0, 4))
    dept = tk.StringVar()
    role = tk.StringVar()
    ttk.Label(fbar, text="Department:").pack(side="left")
    ttk.Combobox(fbar, textvariable=dept, state="readonly", width=18,
                 values=("",) + staff_mod.DEPARTMENTS).pack(side="left",
                                                            padx=(4, 10))
    ttk.Label(fbar, text="Job role:").pack(side="left")
    ttk.Combobox(fbar, textvariable=role, state="readonly", width=22,
                 values=("",) + staff_mod.ROLES).pack(side="left",
                                                      padx=(4, 10))
    abar = ttk.Frame(parent)
    abar.pack(fill="x", pady=(0, 4))
    ttk.Label(parent, text="✓ in date · due <expiry> = renew soon · OVERDUE "
              "· missing = never done · blank = not required. Double-click "
              "a cell for its evidence.", foreground="#555").pack(anchor="w")
    status = ttk.Label(parent, text="", foreground="#555")
    status.pack(side="bottom", anchor="w")
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, show="headings", height=18)
    xs = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
    ys = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
    xs.pack(side="bottom", fill="x")
    ys.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    for tag, colour in (("bad", "#a33"), ("warn", "#7a5800"),
                        ("good", "#0d6b2a")):
        tree.tag_configure(tag, foreground=colour)
    state: dict = {"types": [], "rows": {}}

    def refresh() -> None:
        try:
            types, rows = data.matrix(department=dept.get() or None,
                                      role=role.get() or None)
        except (ValueError, PermissionError) as exc:
            status.configure(text=str(exc), foreground="#a33")
            return
        state["types"] = types
        cols = ["staff", "role"] + [f"t{t.type_id}" for t in types]
        tree.configure(columns=cols)
        tree.heading("staff", text="Staff")
        tree.column("staff", width=170, anchor="w", stretch=False)
        tree.heading("role", text="Job role")
        tree.column("role", width=130, anchor="w", stretch=False)
        for t in types:
            tree.heading(f"t{t.type_id}", text=t.code)
            tree.column(f"t{t.type_id}", width=118, anchor="w",
                        stretch=False)
        tree.delete(*tree.get_children())
        state["rows"].clear()
        roles = {s.staff_id: s.role for s in staff_mod.list_staff()}
        gaps = 0
        for row in rows:
            if not row:
                continue
            sid = row[0].staff_id
            worst = ("bad" if any(c.required and c.state in (
                data.OVERDUE, data.MISSING) for c in row)
                else "warn" if any(c.required and c.state == data.DUE_SOON
                                   for c in row) else "good")
            gaps += worst == "bad"
            state["rows"][sid] = {c.type_id: c for c in row}
            tree.insert("", "end", iid=sid, tags=(worst,),
                        values=[row[0].staff_name, roles.get(sid, "")]
                        + [cell_text(c) for c in row])
        status.configure(text=f"{len(rows)} staff × {len(types)} trainings; "
                              f"{gaps} with gaps", foreground="#555")

    def clicked_cell(event=None):
        sid = tree.focus()
        if not sid:
            raise ValueError("Select a member of staff first.")
        type_id = None
        if event is not None:
            col = tree.identify_column(event.x)
            idx = int(col.lstrip("#") or 0) - 3
            if 0 <= idx < len(state["types"]):
                type_id = state["types"][idx].type_id
        return sid, type_id

    def evidence(event=None) -> None:
        try:
            sid, type_id = clicked_cell(event)
        except ValueError as exc:
            rt.warn(parent, "Training", str(exc))
            return
        cells = state["rows"].get(sid, {})
        if type_id is None:
            lines = []
            for c in cells.values():
                if c.required or c.latest:
                    lines.append(f"{c.type_name:<48} {c.state or 'n/a':<9} "
                                 f"{c.completed_on or '':<11} "
                                 f"{c.expires_on or ''}")
            rt.show_text(parent, "Training status", "\n".join(lines))
            return
        c = cells.get(type_id)
        ev = data.evidence_for(sid, type_id)
        lines = [f"{c.staff_name if c else sid} — "
                 f"{c.type_name if c else type_id}",
                 f"State: {c.state if c and c.state else 'not required'}", ""]
        lines += [f"{e.completed_on}  expires {e.expires_on or 'never'}  "
                  f"[{e.source}]  {e.provider or ''}  {e.evidence or ''}"
                  for e in ev] or ["No evidence recorded."]
        rt.show_text(parent, "Training evidence", "\n".join(lines))

    def record() -> None:
        sid = tree.focus() or None
        record_dialog(parent, refresh_all, staff_id=sid)

    ttk.Button(fbar, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(abar, text="Record completion", command=record).pack(
        side="left", padx=(0, 4))
    ttk.Button(abar, text="Status for selected", command=evidence).pack(
        side="left", padx=(0, 4))
    tree.bind("<Double-1>", evidence)
    refresh()
    return refresh

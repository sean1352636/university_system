"""Form Groups screens: the forms list (old Year filter / New / Edit / Delete /
Refresh kept) and one page per form. Rules live in :mod:`modules.curriculum.domain.form_groups`."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import FORM_GROUP_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)


_problems = W.problems


def _tree(parent, columns, height: int = 10, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select, stretch={"name", "tutor", "notes"})


def _cap(s: FG.FormStats) -> str:
    if s.capacity is None:
        return "—"
    if s.over_capacity:
        return f"{s.capacity} ({-s.spaces} over)"  # type: ignore[operator]
    return f"{s.capacity} ({s.spaces} free)"


def _plural(n: int, word: str = "pupil") -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


# ── List ─────────────────────────────────────────────────────────────

def draw_form_groups(parent: ttk.Frame, *, principal: Principal,
                     open_form: Callable[[int], None], state: dict | None = None) -> None:
    state = state if state is not None else {}
    editor = principal.role in FORM_GROUP_EDITORS
    activity_log.record("form_group.list")
    ttk.Label(parent, text="Form Groups", font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, text="Pupil numbers are counted live from pupil records. Double-click a "
                           "form to open it.", foreground="#666").pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year filter:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value=state.get("year", "All"))
    ttk.Combobox(bar, textvariable=year_var, values=["All", *map(str, P.YEAR_GROUPS)],
                 state="readonly", width=5).pack(side="left", padx=(0, 10))
    archived_var = tk.BooleanVar(value=state.get("archived", False))
    ttk.Checkbutton(bar, text="Show archived", variable=archived_var).pack(side="left",
                                                                          padx=(0, 10))
    warn = ttk.Frame(parent)
    warn.pack(fill="x")
    tree = _tree(parent, (("yr", "Year", 50), ("name", "Form", 70), ("tutor", "Form tutor", 160),
                          ("co", "Co-tutor", 120), ("room", "Room", 60), ("roll", "Pupils", 55),
                          ("fm", "F / M", 60), ("cap", "Capacity", 100), ("sen", "SEN", 45),
                          ("fsm", "FSM", 45), ("eal", "EAL", 45), ("status", "Status", 70)),
                 height=16)
    tree.tag_configure("over", foreground="#a00")
    tree.tag_configure("archived", foreground="#888")
    count = ttk.Label(parent, foreground="#666")
    count.pack(anchor="w", pady=(4, 0))

    def selected() -> FG.FormGroup | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Form Groups", "Select a form first.", parent=parent)
            return None
        return FG.get(int(sel[0]))

    def refresh(*_a) -> None:
        state.update(year=year_var.get(), archived=archived_var.get())
        year = None if year_var.get() == "All" else int(year_var.get())
        tree.delete(*tree.get_children())
        try:
            forms = FG.list_forms(year, include_archived=archived_var.get())
            st = FG.stats(year)
        except Exception:
            logger.exception("Form groups list failed")
            count.configure(text="Couldn't read form groups - see the log.")
            return
        for f in forms:
            s = st.get(f.form_id, FG.FormStats(capacity=f.capacity))
            live = f.is_active
            tree.insert("", "end", iid=str(f.form_id), tags=(
                "archived" if not live else "over" if s.over_capacity else "",), values=(
                f.year_group, f.name, f.tutor_name or "", f.co_tutor_name or "", f.room or "",
                s.on_roll if live else "", f"{s.female} / {s.male}" if live else "",
                _cap(s) if live else "", s.sen if live else "", s.fsm if live else "",
                s.eal if live else "", "Open" if live else "Archived"))
        total = sum(s.on_roll for s in st.values())
        count.configure(text=f"{len(forms)} form(s) · {_plural(total)} in forms")
        _draw_warnings(warn, year, principal, refresh)

    def new() -> None:
        form_dialog(parent, principal, None, refresh,
                    year=None if year_var.get() == "All" else int(year_var.get()))

    def edit() -> None:
        f = selected()
        if f:
            form_dialog(parent, principal, f, refresh)

    def delete() -> None:
        f = selected()
        if not f:
            return
        if not messagebox.askyesno("Delete", f"Delete form {f.label}?\n\nUse this for a form "
                                   "set up by mistake. To close a form that has been used, "
                                   "Archive it instead.", parent=parent):
            return
        try:
            FG.delete(f.form_id, actor=principal)
        except (FG.ValidationError, FG.PermissionDenied) as e:
            messagebox.showerror("Delete", _problems(e), parent=parent)
            return
        refresh()

    def archive_restore() -> None:
        f = selected()
        if not f:
            return
        try:
            if f.is_active:
                if not messagebox.askyesno("Archive", f"Archive {f.label}? It stays in the "
                                           "list under Show archived.", parent=parent):
                    return
                FG.archive(f.form_id, actor=principal)
            else:
                FG.restore(f.form_id, actor=principal)
        except (FG.ValidationError, FG.PermissionDenied) as e:
            messagebox.showerror("Archive", _problems(e), parent=parent)
            return
        refresh()

    def open_selected(_e=None) -> None:
        sel = tree.selection()
        if sel:
            open_form(int(sel[0]))

    state_kw = {} if editor else {"state": "disabled"}
    ttk.Button(bar, text="New", command=new, **state_kw).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit", command=edit, **state_kw).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete", command=delete, **state_kw).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="left", padx=2)
    ttk.Button(bar, text="Open", command=open_selected).pack(side="left", padx=(12, 2))
    ttk.Button(bar, text="Archive / Restore", command=archive_restore, **state_kw).pack(
        side="left", padx=2)
    tree.bind("<Double-1>", open_selected)
    year_var.trace_add("write", refresh)
    archived_var.trace_add("write", refresh)
    refresh()


def _draw_warnings(box: ttk.Frame, year: int | None, principal: Principal,
                   refresh: Callable[[], None]) -> None:
    for w in box.winfo_children():
        w.destroy()
    editor = principal.role in FORM_GROUP_EDITORS
    missing = [m for m in FG.not_set_up() if year is None or m[0] == year]
    if missing:
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(0, 4))
        ttk.Label(row, text="Not set up: " + ", ".join(
            f"{name} (Y{y}, {_plural(n)})" for y, name, n in missing[:10])
                  + (" …" if len(missing) > 10 else "")
                  + " - pupils have these forms but there's no form record.",
                  foreground="#a60", wraplength=900, justify="left").pack(side="left")
        if editor:
            def set_up() -> None:
                made = FG.set_up_missing(actor=principal)
                messagebox.showinfo("Form Groups", f"{len(made)} form(s) set up. Add their "
                                    "tutors with Edit.", parent=box)
                refresh()

            ttk.Button(row, text="Set these up", command=set_up).pack(side="right")
    loose = {}
    for p in FG.without_form(year):
        loose[p.year_group] = loose.get(p.year_group, 0) + 1
    if loose:
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(0, 4))
        ttk.Label(row, text="No form: " + ", ".join(
            f"Year {y}: {_plural(n)}" for y, n in sorted(loose.items())),
                  foreground="#a60").pack(side="left")
        if editor:
            for y in sorted(loose):
                ttk.Button(row, text=f"Place Year {y}…", command=lambda y=y: distribute_dialog(
                    box, principal, y, refresh)).pack(side="right", padx=2)


# ── One form ─────────────────────────────────────────────────────────

def draw_form(parent: ttk.Frame, form_id: int, *, principal: Principal,
              open_pupil: Callable[[int], None], on_back: Callable[[], None],
              on_changed: Callable[[], None]) -> None:
    try:
        f = FG.get(form_id)
    except FG.NotFound:
        ttk.Label(parent, text="That form no longer exists.").pack(anchor="w")
        ttk.Button(parent, text="← Form Groups", command=on_back).pack(anchor="w")
        return
    activity_log.record("form_group.view", target=f"FG{form_id}")
    editor = principal.role in FORM_GROUP_EDITORS and f.is_active
    pupils = FG.members(f) if f.is_active else []
    s = FG.stats(f.year_group).get(f.form_id, FG.FormStats(capacity=f.capacity))

    head = ttk.Frame(parent)
    head.pack(fill="x")
    ttk.Button(head, text="← Form Groups", command=on_back).pack(side="left")
    ttk.Label(head, text=f"  Form {f.name}", font=("", 16, "bold")).pack(side="left")
    ttk.Label(head, text=f"  Year {f.year_group}" + ("" if f.is_active else " · archived"),
              foreground="#555").pack(side="left", pady=(4, 0))
    if editor:
        ttk.Button(head, text="Edit", command=lambda: form_dialog(
            parent, principal, FG.get(form_id), on_changed)).pack(side="right")

    tiles = ttk.Frame(parent)
    tiles.pack(fill="x", pady=(8, 0))
    for i, (label, value, hint) in enumerate((
            ("Pupils", str(s.on_roll), f"{s.female} F · {s.male} M"
                                       + (f" · {s.other} other" if s.other else "")),
            ("Capacity", _cap(s), "set with Edit"),
            ("SEN / EHCP", str(s.sen), "K or E"),
            ("FSM · EAL", f"{s.fsm} · {s.eal}", "free school meals · EAL"))):
        tiles.columnconfigure(i, weight=1, uniform="t")
        box = ttk.LabelFrame(tiles, padding=8)
        box.grid(row=0, column=i, sticky="nsew", padx=4)
        ttk.Label(box, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(box, text=value, font=("", 16, "bold"),
                  foreground="#a00" if label == "Capacity" and s.over_capacity else "").pack(
            anchor="w")
        ttk.Label(box, text=hint, foreground="#888", font=("", 9)).pack(anchor="w")

    team = ttk.LabelFrame(parent, text="Form team", padding=8)
    team.pack(fill="x", pady=(8, 0))
    for k in ("tutor_name", "tutor_email", "co_tutor_name", "room", "notes"):
        ttk.Label(team, text=f"{FG.FIELD_LABELS[k]}: {getattr(f, k) or '—'}", wraplength=900,
                  justify="left").pack(anchor="w")

    box = ttk.LabelFrame(parent, text="Pupils", padding=8)
    box.pack(fill="both", expand=True, pady=(8, 0))
    tree = _tree(box, (("adm", "Adm. no", 90), ("name", "Pupil", 220), ("g", "Gender", 70),
                       ("dob", "Born", 90), ("sen", "SEN", 45), ("fsm", "FSM", 45),
                       ("eal", "EAL", 45)), height=12, select="extended")
    for p in pupils:
        tree.insert("", "end", iid=str(p.pupil_id), values=(
            p.admission_no, p.display_name, p.gender, p.date_of_birth, p.sen_status,
            "Y" if p.fsm_eligible else "", "Y" if p.eal else ""))
    if not pupils:
        ttk.Label(box, text="No pupils in this form.", foreground="#888").pack(anchor="w")

    def chosen() -> list[int]:
        ids = [int(i) for i in tree.selection()]
        if not ids:
            messagebox.showinfo("Form", "Select pupils first (Ctrl/Shift-click for several).",
                                parent=parent)
        return ids

    tree.bind("<Double-1>", lambda _e: tree.selection() and open_pupil(
        int(tree.selection()[0])))
    pb = ttk.Frame(box)
    pb.pack(fill="x", pady=(6, 0))
    ttk.Button(pb, text="Open pupil", command=lambda: tree.selection() and open_pupil(
        int(tree.selection()[0]))).pack(side="left")
    if editor:
        def take_out() -> None:
            ids = chosen()
            if ids and messagebox.askyesno("Remove", f"Take {_plural(len(ids))} out of "
                                           f"{f.name}? They'll have no form.", parent=parent):
                FG.remove(ids, form_id, actor=principal)
                on_changed()

        ttk.Button(pb, text="Add pupils…", command=lambda: add_dialog(
            parent, principal, f, on_changed)).pack(side="left", padx=6)
        ttk.Button(pb, text="Move to another form…", command=lambda: (
            ids := chosen()) and move_dialog(parent, principal, f, ids, on_changed)).pack(
            side="left")
        ttk.Button(pb, text="Remove from form", command=take_out).pack(side="left", padx=6)

    def export() -> None:
        path = filedialog.asksaveasfilename(parent=parent, defaultextension=".csv",
                                            initialfile=f"form_{f.name.replace(' ', '_')}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        needs = principal.can_edit_pupils and messagebox.askyesno(
            "Export", "Include SEN, FSM and EAL columns?\n\nOnly do this if whoever gets "
            "the file needs them.", parent=parent)
        try:
            n = FG.export_class_list(form_id, path, actor=principal, include_needs=needs)
        except (FG.PermissionDenied, OSError) as e:
            messagebox.showerror("Export", str(e), parent=parent)
            return
        messagebox.showinfo("Export", f"{_plural(n)} written to {path}.", parent=parent)

    ttk.Button(pb, text="Export class list…", command=export).pack(side="left")
    if principal.can_email_bulk and pupils:
        def email() -> None:
            from education_system.systems.secondary.modules.communication.gui import email_views
            ids = [int(i) for i in tree.selection()] or [p.pupil_id for p in pupils]
            email_views.open_compose(parent, principal=principal, on_sent=lambda _m: None,
                                     pupil_ids=ids)

        ttk.Button(pb, text="E-mail parents…", command=email).pack(side="left", padx=6)
    hist = FG.history(form_id)[:4]
    if hist:
        ttk.Label(parent, text="Recent changes: " + "; ".join(
            f"{h['at'][:16]} {h['actor']} {describe(h)}" for h in hist),
                  foreground="#888", wraplength=1000, justify="left").pack(anchor="w",
                                                                          pady=(6, 0))


def describe(h: dict) -> str:
    d, a = h["detail"], h["action"]
    if a == "update":
        return "changed " + ", ".join(FG.FIELD_LABELS.get(k, k).lower() for k in d)
    if a in {"assign", "remove"}:
        return f"{'added' if a == 'assign' else 'removed'} {_plural(d.get('pupils', 0))}"
    if a == "rollover":
        return f"year-end rollover {d.get('year', '')}" + (" (archived)" if d.get("archived")
                                                          else "")
    return {"create": "set up the form", "archive": "archived", "restore": "restored",
            "delete": "deleted"}.get(a, a)


# ── Dialogs ──────────────────────────────────────────────────────────

def _dialog(owner, title: str) -> tuple[tk.Toplevel, ttk.Frame]:
    return W.dialog(owner, title, resizable=False, padding=14)


def form_dialog(owner, principal: Principal, f: FG.FormGroup | None,
                after: Callable[[], None], *, year: int | None = None) -> None:
    if principal.role not in FORM_GROUP_EDITORS:
        messagebox.showinfo("Form Groups", "Your account can view form groups but not change "
                            "them.", parent=owner)
        return
    if f is not None and not f.is_active:
        messagebox.showinfo("Edit", "Archived forms can't be changed - Restore it first.",
                            parent=owner)
        return
    win, frm = _dialog(owner, f"Edit form {f.label}" if f else "New form group")
    w: dict = {}
    r = 0
    ttk.Label(frm, text="Year group *:").grid(row=r, column=0, sticky="w", pady=2, padx=(0, 8))
    yr = ttk.Combobox(frm, values=[str(y) for y in P.YEAR_GROUPS], state="readonly", width=5)
    yr.set(str(f.year_group) if f else str(year) if year else "")
    yr.grid(row=r, column=1, sticky="w", pady=2)
    w["year_group"] = yr
    for key, width, hint in (("name", 12, "e.g. 7K - up to 10 characters"),
                             ("tutor_name", 34, ""), ("tutor_email", 34, ""),
                             ("co_tutor_name", 34, ""), ("room", 12, ""),
                             ("capacity", 6, "blank = no limit")):
        r += 1
        ttk.Label(frm, text=FG.FIELD_LABELS[key] + (" *" if key == "name" else "") + ":").grid(
            row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        e = ttk.Entry(frm, width=width)
        v = getattr(f, key) if f else None
        e.insert(0, "" if v is None else str(v))
        e.grid(row=r, column=1, sticky="w", pady=2)
        if hint:
            ttk.Label(frm, text=hint, foreground="#888").grid(row=r, column=2, sticky="w",
                                                              padx=6)
        w[key] = e
    if f:
        n = len(FG.members(f))
        if n:
            ttk.Label(frm, text=f"{_plural(n)} in this form: renaming renames it on their "
                                "records; the year can't change.", foreground="#888",
                      wraplength=420, justify="left").grid(row=r + 1, column=0, columnspan=3,
                                                           sticky="w")
            yr.configure(state="disabled")
    r += 2
    ttk.Label(frm, text="Notes:").grid(row=r, column=0, sticky="nw", pady=2)
    notes = tk.Text(frm, width=44, height=4, wrap="word")
    notes.insert("1.0", (f.notes if f else None) or "")
    notes.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
    error = tk.StringVar()
    ttk.Label(frm, textvariable=error, foreground="#a00", wraplength=440, justify="left").grid(
        row=r + 1, column=0, columnspan=3, sticky="w")

    def save() -> None:
        data = {k: e.get() for k, e in w.items()}
        data["notes"] = notes.get("1.0", "end").strip()
        try:
            if f is None:
                FG.create(data, actor=principal)
            else:
                if str(yr.cget("state")) == "disabled":
                    data.pop("year_group")
                _g, _c, renamed = FG.update(f.form_id, data, actor=principal)
                if renamed:
                    messagebox.showinfo("Saved", f"Form renamed on {renamed} pupil "
                                        "record(s).", parent=win)
        except FG.ValidationError as e:
            error.set(_problems(e))
            return
        except FG.PermissionDenied as e:
            messagebox.showerror("Form Groups", str(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=r + 2, column=0, columnspan=3, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def _report(owner, title: str, done: int, refused: list[tuple[str, str]]) -> None:
    messagebox.showinfo(title, f"{_plural(done)} done."
                        + ("\n\nNot done:\n" + "\n".join(f"• {a}: {w}" for a, w in refused[:15])
                           if refused else ""), parent=owner)


def _assign(win, owner, principal, ids, form, after) -> None:
    try:
        try:
            done, refused = FG.assign(ids, form.form_id, actor=principal)
        except FG.ValidationError as e:
            full = form.capacity is not None and any("room for" in p for p in e.problems)
            if not full:
                raise
            if not messagebox.askyesno("Over capacity", _problems(e)
                                       + "\n\nGo over capacity anyway?", parent=win):
                return
            done, refused = FG.assign(ids, form.form_id, actor=principal,
                                      allow_over_capacity=True)
    except (FG.ValidationError, FG.PermissionDenied) as e:
        messagebox.showerror("Form", _problems(e), parent=win)
        return
    win.destroy()
    _report(owner, "Form", len(done), refused)
    after()


def add_dialog(owner, principal: Principal, f: FG.FormGroup, after: Callable[[], None]) -> None:
    """Pick pupils from the same year (those with no form first) to put in *f*."""
    win, frm = _dialog(owner, f"Add pupils to {f.name}")
    win.resizable(True, True)
    ttk.Label(frm, text=f"Year {f.year_group} pupils not in {f.name}. Ctrl/Shift-click to "
                        "choose several.").pack(anchor="w")
    only_loose = tk.BooleanVar(value=True)
    ttk.Checkbutton(frm, text="Only pupils with no form", variable=only_loose).pack(
        anchor="w", pady=(4, 4))
    tree = _tree(frm, (("adm", "Adm. no", 90), ("name", "Pupil", 200), ("form", "Form now", 80),
                       ("g", "Gender", 70)), height=14, select="extended")

    def fill(*_a) -> None:
        tree.delete(*tree.get_children())
        for p in P.list_pupils(year_group=f.year_group):
            if (p.form_group or "").upper() == f.name or (only_loose.get() and p.form_group):
                continue
            tree.insert("", "end", iid=str(p.pupil_id), values=(
                p.admission_no, p.display_name, p.form_group or "—", p.gender))

    only_loose.trace_add("write", fill)
    fill()
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Add to form", command=lambda: tree.selection() and _assign(
        win, owner, principal, [int(i) for i in tree.selection()], f, after)).pack(
        side="right", padx=(0, 6))


def move_dialog(owner, principal: Principal, f: FG.FormGroup, pupil_ids: list[int],
                after: Callable[[], None]) -> None:
    others = [o for o in FG.list_forms(f.year_group) if o.form_id != f.form_id]
    if not others:
        messagebox.showinfo("Move", f"Year {f.year_group} has no other form. Set one up "
                            "first.", parent=owner)
        return
    st = FG.stats(f.year_group)
    win, frm = _dialog(owner, "Move to another form")
    ttk.Label(frm, text=f"Move {_plural(len(pupil_ids))} from {f.name} to:").grid(
        row=0, column=0, sticky="w")
    labels = {f"{o.name} - {st[o.form_id].on_roll} pupils, {_cap(st[o.form_id])}": o
              for o in others}
    to = ttk.Combobox(frm, values=list(labels), state="readonly", width=34)
    to.grid(row=1, column=0, sticky="w", pady=(6, 0))
    bar = ttk.Frame(frm)
    bar.grid(row=2, column=0, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Move", command=lambda: to.get() and _assign(
        win, owner, principal, pupil_ids, labels[to.get()], after)).pack(side="right",
                                                                         padx=(0, 6))


def distribute_dialog(owner, principal: Principal, year: int,
                      after: Callable[[], None]) -> None:
    plan, unplaced = FG.plan_distribution(year)
    if not plan and not unplaced:
        messagebox.showinfo("Place pupils", f"Every Year {year} pupil has a form.", parent=owner)
        return
    if not FG.list_forms(year):
        messagebox.showinfo("Place pupils", f"Year {year} has no forms set up yet.",
                            parent=owner)
        return
    win, frm = _dialog(owner, f"Place Year {year} pupils in forms")
    win.resizable(True, True)
    ttk.Label(frm, text="Suggested forms for pupils with none - keeps forms even in size and "
                        "in girls and boys, within capacity. Nothing changes until you press "
                        "Place.", wraplength=520, justify="left").pack(anchor="w")
    tree = _tree(frm, (("adm", "Adm. no", 90), ("name", "Pupil", 200), ("g", "Gender", 70),
                       ("form", "Form", 70)), height=14)
    for p, form in plan:
        tree.insert("", "end", values=(p.admission_no, p.display_name, p.gender, form.name))
    for p in unplaced:
        tree.insert("", "end", values=(p.admission_no, p.display_name, p.gender,
                                       "no room"), tags=("bad",))
    tree.tag_configure("bad", foreground="#a00")

    def go() -> None:
        try:
            done, refused = FG.apply_distribution(plan, actor=principal)
        except (FG.ValidationError, FG.PermissionDenied) as e:
            messagebox.showerror("Place pupils", _problems(e), parent=win)
            return
        win.destroy()
        _report(owner, "Place pupils", done, refused)
        after()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Label(bar, text=f"{_plural(len(plan))} to place"
                        + (f", {len(unplaced)} with no room" if unplaced else ""),
              foreground="#666").pack(side="left")
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Place", command=go,
               state="normal" if plan else "disabled").pack(side="right", padx=(0, 6))

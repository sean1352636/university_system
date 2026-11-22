"""Year Groups screens: the Years 7-11 list (old Edit / Clear / Refresh kept)
and one page per year group. Rules live in :mod:`modules.curriculum.domain.year_groups`."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import YEAR_GROUP_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)


_problems = W.problems



def _gender_split(pr, sep: str, *, labels: bool = False) -> str:
    """Girls / boys, plus the other gender options when there are any."""
    f, m = pr.by_gender.get("Female", 0), pr.by_gender.get("Male", 0)
    other = pr.on_roll - f - m
    parts = [f"{f} F", f"{m} M"] if labels else [str(f), str(m)]
    if other:
        parts.append(f"{other} other")
    return sep.join(parts)

def _tree(parent, columns, height: int = 10, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select, stretch={"name", "hoy", "notes"})


def _capacity_text(pr: YG.Profile) -> str:
    if pr.capacity is None:
        return "—"
    if pr.over_capacity:
        return f"{pr.capacity} ({-pr.spaces} over)"  # type: ignore[operator]
    return f"{pr.capacity} ({pr.spaces} free)"


# ── List ─────────────────────────────────────────────────────────────

def draw_year_groups(parent: ttk.Frame, *, principal: Principal,
                     open_year: Callable[[int], None]) -> None:
    activity_log.record("year_group.list")
    ttk.Label(parent, text="Year Groups", font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, text="Numbers are worked out live from pupil records. Double-click a "
                           "year to open it.", foreground="#666").pack(anchor="w", pady=(0, 6))
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    tree = _tree(parent, (("yr", "Year", 70), ("ks", "Key stage", 70), ("hoy", "Head of year", 170),
                          ("roll", "On roll", 65), ("fm", "F / M", 70), ("forms", "Forms", 55),
                          ("cap", "Capacity", 110), ("needs", "SEN K/E · FSM · EAL", 150),
                          ("ooy", "Out of year", 80), ("notes", "Notes", 200)), height=7)
    tree.tag_configure("over", foreground="#a00")
    total = ttk.Label(parent, foreground="#555")
    total.pack(anchor="w", pady=(6, 0))
    editor = principal.role in YEAR_GROUP_EDITORS

    def refresh() -> None:
        keep = tree.selection()
        tree.delete(*tree.get_children())
        rows = YG.overview()
        for g, pr in rows:
            tree.insert("", "end", iid=str(g.year_group), tags=("over",) if pr.over_capacity
                        else (), values=(
                g.label, g.key_stage, g.head_of_year or "—", pr.on_roll,
                _gender_split(pr, " / "),
                len(pr.forms), _capacity_text(pr),
                f"{pr.sen_support}/{pr.ehcp} · {pr.fsm} · {pr.eal}", len(pr.out_of_year),
                (g.notes or "").replace("\n", " ")[:80]))
        if keep and tree.exists(keep[0]):
            tree.selection_set(keep)
        total.configure(text=f"{sum(pr.on_roll for _g, pr in rows)} pupils on roll in "
                             "Years 7-11")

    def selected() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Year Groups", "Select a year group first.", parent=parent)
            return None
        return int(sel[0])

    def edit() -> None:
        y = selected()
        if y:
            edit_dialog(parent, principal, YG.get(y), refresh)

    def do_clear() -> None:
        y = selected()
        if y and messagebox.askyesno("Clear", f"Clear Year {y}'s head of year, capacity and "
                                     "notes? Pupils aren't affected.", parent=parent):
            try:
                YG.clear(y, actor=principal)
            except (YG.ValidationError, YG.PermissionDenied) as e:
                messagebox.showerror("Clear", _problems(e), parent=parent)
            refresh()

    def open_selected(_e=None) -> None:
        y = selected()
        if y:
            open_year(y)

    tree.bind("<Double-1>", open_selected)
    ttk.Button(bar, text="Open", command=open_selected).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Edit", command=edit,
               state="normal" if editor else "disabled").pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Clear", command=do_clear,
               state="normal" if editor else "disabled").pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="right")
    refresh()


# ── One year group ───────────────────────────────────────────────────

def draw_year(parent: ttk.Frame, year: int, *, principal: Principal,
              open_pupil: Callable[[int], None], on_back: Callable[[], None],
              on_changed: Callable[[], None]) -> None:
    g, pr = YG.get(year), YG.profile(year)
    activity_log.record("year_group.view", target=f"Y{year}")
    editor = principal.role in YEAR_GROUP_EDITORS
    head = ttk.Frame(parent)
    head.pack(fill="x")
    ttk.Button(head, text="← Year Groups", command=on_back).pack(side="left")
    ttk.Label(head, text=f"  {g.label}", font=("", 16, "bold")).pack(side="left")
    ttk.Label(head, text=f"  {g.key_stage}", foreground="#555").pack(side="left", pady=(4, 0))
    if editor:
        def do_clear() -> None:
            if messagebox.askyesno("Clear", f"Clear {g.label}'s settings?", parent=parent):
                YG.clear(year, actor=principal)
                on_changed()

        ttk.Button(head, text="Clear", command=do_clear).pack(side="right")
        ttk.Button(head, text="Edit", command=lambda: edit_dialog(
            parent, principal, YG.get(year), on_changed)).pack(side="right", padx=6)

    tiles = ttk.Frame(parent)
    tiles.pack(fill="x", pady=(8, 0))
    for i, (label, value, hint) in enumerate((
            ("On roll", str(pr.on_roll), _gender_split(pr, " · ", labels=True)),
            ("Capacity", _capacity_text(pr), "set with Edit"),
            ("This year", f"+{pr.joined_this_year} / -{pr.left_this_year}", "joined / left"),
            ("Out of year group", str(len(pr.out_of_year)), "age doesn't fit the year"))):
        tiles.columnconfigure(i, weight=1, uniform="t")
        box = ttk.LabelFrame(tiles, padding=8)
        box.grid(row=0, column=i, sticky="nsew", padx=4)
        ttk.Label(box, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(box, text=value, font=("", 16, "bold"),
                  foreground="#a00" if label == "Capacity" and pr.over_capacity else "").pack(
            anchor="w")
        ttk.Label(box, text=hint, foreground="#888", font=("", 9)).pack(anchor="w")

    mid = ttk.Frame(parent)
    mid.pack(fill="x", pady=(8, 0))
    for c in range(3):
        mid.columnconfigure(c, weight=1, uniform="m")
    team = ttk.LabelFrame(mid, text="Year team", padding=8)
    team.grid(row=0, column=0, sticky="nsew", padx=4)
    for k in ("head_of_year", "head_of_year_email", "assistant_head", "notes"):
        ttk.Label(team, text=f"{YG.FIELD_LABELS[k]}: {getattr(g, k) or '—'}", wraplength=300,
                  justify="left").pack(anchor="w")
    forms = ttk.LabelFrame(mid, text="Forms", padding=8)
    forms.grid(row=0, column=1, sticky="nsew", padx=4)
    for f, n in pr.forms.items():
        ttk.Label(forms, text=f"{f:<6} {n} pupil{'s' if n != 1 else ''}").pack(anchor="w")
    if pr.no_form:
        ttk.Label(forms, text=f"No form: {pr.no_form}", foreground="#a60").pack(anchor="w")
    if not pr.forms and not pr.no_form:
        ttk.Label(forms, text="No pupils.", foreground="#888").pack(anchor="w")
    needs = ttk.LabelFrame(mid, text="Needs", padding=8)
    needs.grid(row=0, column=2, sticky="nsew", padx=4)
    for label, n in (("SEN support (K)", pr.sen_support), ("EHC plan (E)", pr.ehcp),
                     ("Free school meals", pr.fsm), ("EAL", pr.eal)):
        pct = f" ({n * 100 // pr.on_roll}%)" if pr.on_roll else ""
        ttk.Label(needs, text=f"{label}: {n}{pct}").pack(anchor="w")

    if pr.out_of_year:
        ooy = ttk.LabelFrame(parent, text="Taught out of year group", padding=8)
        ooy.pack(fill="x", pady=(8, 0))
        ttk.Label(ooy, text="; ".join(f"{p.display_name} ({p.admission_no}) - age fits Year "
                                      f"{exp}" for p, exp in pr.out_of_year[:12])
                  + (" …" if len(pr.out_of_year) > 12 else ""), foreground="#a60",
                  wraplength=1000, justify="left").pack(anchor="w")

    pupils_box = ttk.LabelFrame(parent, text="Pupils", padding=8)
    pupils_box.pack(fill="both", expand=True, pady=(8, 0))
    sbar = ttk.Frame(pupils_box)
    sbar.pack(fill="x", pady=(0, 4))
    form_var, search_var = tk.StringVar(value="All"), tk.StringVar()
    ttk.Label(sbar, text="Form:").pack(side="left")
    ttk.Combobox(sbar, textvariable=form_var, values=["All", *pr.forms], state="readonly",
                 width=8).pack(side="left", padx=(2, 10))
    ttk.Label(sbar, text="Search:").pack(side="left")
    ttk.Entry(sbar, textvariable=search_var, width=20).pack(side="left", padx=2)
    count = ttk.Label(sbar, foreground="#666")
    count.pack(side="right")
    tree = _tree(pupils_box, (("adm", "Adm. no", 90), ("name", "Pupil", 200), ("form", "Form", 60),
                              ("g", "Gender", 65), ("dob", "Born", 90), ("sen", "SEN", 45),
                              ("fsm", "FSM", 45), ("eal", "EAL", 45)), height=10,
                 select="extended")

    def fill(*_a) -> None:
        tree.delete(*tree.get_children())
        rows = P.list_pupils(year_group=year, search=search_var.get().strip() or None,
                             form_group=None if form_var.get() == "All" else form_var.get())
        for p in rows:
            tree.insert("", "end", iid=str(p.pupil_id), values=(
                p.admission_no, p.display_name, p.form_group or "", p.gender, p.date_of_birth,
                p.sen_status, "Y" if p.fsm_eligible else "", "Y" if p.eal else ""))
        count.configure(text=f"{len(rows)} shown")

    form_var.trace_add("write", fill)
    search_var.trace_add("write", fill)
    tree.bind("<Double-1>", lambda _e: tree.selection() and open_pupil(
        int(tree.selection()[0])))
    fill()
    pb = ttk.Frame(pupils_box)
    pb.pack(fill="x", pady=(6, 0))
    ttk.Button(pb, text="Open pupil", command=lambda: tree.selection() and open_pupil(
        int(tree.selection()[0]))).pack(side="left")
    if editor:
        ttk.Button(pb, text="Move to another year…", command=lambda: move_dialog(
            parent, principal, year, [int(i) for i in tree.selection()], on_changed)).pack(
            side="left", padx=6)
    if principal.can_email_bulk:
        def email() -> None:
            from education_system.systems.secondary.modules.communication.gui import email_views
            ids = [int(i) for i in tree.selection()] or [
                p.pupil_id for p in P.list_pupils(year_group=year)]
            if not ids:
                messagebox.showinfo("E-mail", "No pupils in this year.", parent=parent)
                return
            email_views.open_compose(parent, principal=principal, on_sent=lambda _m: None,
                                     pupil_ids=ids)

        ttk.Button(pb, text="E-mail parents…", command=email).pack(side="left")
    hist = YG.history(year)[:4]
    if hist:
        ttk.Label(parent, text="Recent changes: " + "; ".join(
            f"{h['at'][:16]} {h['actor']} {_describe(h)}" for h in hist),
                  foreground="#888", wraplength=1000, justify="left").pack(anchor="w",
                                                                          pady=(6, 0))


def _describe(h: dict) -> str:
    d = h["detail"]
    if h["action"] == "update":
        return "changed " + ", ".join(YG.FIELD_LABELS.get(k, k).lower() for k in d)
    if h["action"] == "clear":
        return "cleared the settings"
    return f"moved {d.get('moved_in', '?')} pupil(s) in"


# ── Dialogs ──────────────────────────────────────────────────────────

def edit_dialog(owner, principal: Principal, g: YG.YearGroup,
                after: Callable[[], None]) -> None:
    if principal.role not in YEAR_GROUP_EDITORS:
        messagebox.showinfo("Edit", "Your account can view year groups but not change them.",
                            parent=owner)
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Edit {g.label}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    w: dict = {}
    for r, (key, width) in enumerate((("head_of_year", 34), ("head_of_year_email", 34),
                                      ("assistant_head", 34), ("capacity", 8))):
        ttk.Label(frm, text=YG.FIELD_LABELS[key] + ":").grid(row=r, column=0, sticky="w",
                                                             pady=2, padx=(0, 8))
        e = ttk.Entry(frm, width=width)
        v = getattr(g, key)
        e.insert(0, "" if v is None else str(v))
        e.grid(row=r, column=1, sticky="w", pady=2)
        w[key] = e
    pr = YG.profile(g.year_group)
    ttk.Label(frm, text=f"{pr.on_roll} on roll now", foreground="#888").grid(
        row=3, column=2, sticky="w", padx=6)
    ttk.Label(frm, text="Notes:").grid(row=4, column=0, sticky="nw", pady=2)
    notes = tk.Text(frm, width=44, height=5, wrap="word")
    notes.insert("1.0", g.notes or "")
    notes.grid(row=4, column=1, columnspan=2, sticky="w", pady=2)
    error = tk.StringVar()
    ttk.Label(frm, textvariable=error, foreground="#a00", wraplength=420, justify="left").grid(
        row=5, column=0, columnspan=3, sticky="w")

    def save() -> None:
        data = {k: e.get() for k, e in w.items()}
        data["notes"] = notes.get("1.0", "end").strip()
        try:
            YG.update(g.year_group, data, actor=principal)
        except YG.ValidationError as e:
            error.set(_problems(e))
            return
        except YG.PermissionDenied as e:
            messagebox.showerror("Edit", str(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=3, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def move_dialog(owner, principal: Principal, year: int, pupil_ids: list[int],
                after: Callable[[], None]) -> None:
    if not pupil_ids:
        messagebox.showinfo("Move", "Select the pupils to move first (Ctrl/Shift-click for "
                            "several).", parent=owner)
        return
    pupils = [p for p in (P.get_pupil(i) for i in pupil_ids) if p]
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Move to another year group")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    names = ", ".join(p.display_name for p in pupils[:8]) + (" …" if len(pupils) > 8 else "")
    ttk.Label(frm, text=f"Move {len(pupils)} pupil{'s' if len(pupils) != 1 else ''} from Year "
                        f"{year}: {names}", wraplength=440, justify="left").grid(
        row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text="To year group:").grid(row=1, column=0, sticky="w", pady=(10, 2))
    to = ttk.Combobox(frm, values=[str(y) for y in P.YEAR_GROUPS if y != year],
                      state="readonly", width=5)
    to.grid(row=1, column=1, sticky="w", pady=(10, 2))
    note = ttk.Label(frm, foreground="#a60", wraplength=440, justify="left")
    note.grid(row=2, column=0, columnspan=2, sticky="w")

    def preview(_e=None) -> None:
        if not to.get():
            return
        new = int(to.get())
        clears = sum(1 for p in pupils if p.form_group and
                     YG.form_after_move(p.form_group, year, new) is None)
        misfit = sum(1 for p in pupils if P.expected_year_group(p.date_of_birth) != new)
        note.configure(text=(f"{clears} form(s) named after Year {year} will be cleared - "
                             "set new forms afterwards. " if clears else "")
                       + (f"{misfit} pupil(s) will be outside their age-expected year."
                          if misfit else ""))

    to.bind("<<ComboboxSelected>>", preview)

    def go() -> None:
        if not to.get():
            return
        try:
            moved, refused = YG.move_pupils([p.pupil_id for p in pupils], int(to.get()),
                                            actor=principal)
        except (YG.ValidationError, YG.PermissionDenied) as e:
            messagebox.showerror("Move", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Move", f"{len(moved)} moved to Year {to.get()}."
                            + ("\n\nNot moved:\n" + "\n".join(f"• {a}: {w}" for a, w in refused)
                               if refused else ""), parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Move", command=go).pack(side="right", padx=(0, 6))

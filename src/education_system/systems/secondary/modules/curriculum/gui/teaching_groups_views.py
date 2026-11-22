"""Teaching Groups screens: the list for an academic year and one page per
group. Rules live in :mod:`modules.curriculum.domain.teaching_groups`."""

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
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import TEACHING_GROUP_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = "All"


_problems = W.problems


def _plural(n: int, word: str = "pupil") -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


def _tree(parent, columns, height: int = 10, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"name", "subject", "teacher"})


def _size(i: TG.GroupInfo) -> str:
    if i.group.capacity is None:
        return str(i.pupils)
    return f"{i.pupils} / {i.group.capacity}"


def describe(h: dict) -> str:
    a, d = h["action"], h["detail"]
    if a == "update":
        return "changed " + ", ".join(TG.FIELD_LABELS.get(k, k).lower() for k in d)
    if a in {"add", "remove", "move_in", "move_out"}:
        verb = {"add": "added", "remove": "removed", "move_in": "moved in",
                "move_out": "moved out"}[a]
        return f"{verb} {_plural(d.get('pupils', 0))}"
    return {"create": "set up the group", "archive": "archived", "restore": "restored",
            "delete": "deleted"}.get(a, a)


# ── List ─────────────────────────────────────────────────────────────

def draw_teaching_groups(parent: ttk.Frame, *, principal: Principal,
                         open_group: Callable[[int], None], state: dict | None = None) -> None:
    state = state if state is not None else {}
    editor = principal.role in TEACHING_GROUP_EDITORS
    activity_log.record("teaching_group.list")
    ttk.Label(parent, text="Teaching Groups", font=("", 16, "bold")).pack(anchor="w")
    ttk.Label(parent, text="The classes pupils are taught each subject in. Double-click a "
                           "group to open it.", foreground="#666").pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 4))
    years = TG.academic_years()
    year_var = tk.StringVar(value=state.get("year", TG.current_year()))
    if year_var.get() not in years:
        year_var.set(TG.current_year())
    yg_var = tk.StringVar(value=state.get("yg", ALL))
    subjects = {s.label: s for s in S.list_subjects(active_only=False)}
    subj_var = tk.StringVar(value=state.get("subject", ALL))
    if subj_var.get() != ALL and subj_var.get() not in subjects:
        subj_var.set(ALL)
    mine_var = tk.BooleanVar(value=state.get("mine", False))
    arch_var = tk.BooleanVar(value=state.get("archived", False))
    ttk.Label(bar, text="Academic year:").pack(side="left", padx=(0, 4))
    ttk.Combobox(bar, textvariable=year_var, values=years, state="readonly", width=8).pack(
        side="left", padx=(0, 8))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    ttk.Combobox(bar, textvariable=yg_var, values=[ALL, *map(str, P.YEAR_GROUPS)],
                 state="readonly", width=4).pack(side="left", padx=(0, 8))
    ttk.Label(bar, text="Subject:").pack(side="left", padx=(0, 4))
    ttk.Combobox(bar, textvariable=subj_var, values=[ALL, *subjects], state="readonly",
                 width=26).pack(side="left", padx=(0, 8))
    ttk.Checkbutton(bar, text="My groups", variable=mine_var).pack(side="left", padx=(0, 8))
    ttk.Checkbutton(bar, text="Show archived", variable=arch_var).pack(side="left")

    btns = ttk.Frame(parent)
    btns.pack(fill="x", pady=(0, 6))
    warn = ttk.Frame(parent)
    warn.pack(fill="x")
    tree = _tree(parent, (("code", "Group", 110), ("subject", "Subject", 190), ("yr", "Year", 45),
                          ("kind", "Kind", 70), ("teacher", "Teacher", 160), ("room", "Room", 60),
                          ("size", "Pupils", 65), ("lessons", "Lessons/wk", 75),
                          ("status", "Status", 70)), height=16)
    tree.tag_configure("archived", foreground="#888")
    tree.tag_configure("over", foreground="#a00")
    count = ttk.Label(parent, foreground="#666")
    count.pack(anchor="w", pady=(4, 0))

    def current_only() -> bool:
        return year_var.get() == TG.current_year()

    def refresh(*_a) -> None:
        state.update(year=year_var.get(), yg=yg_var.get(), subject=subj_var.get(),
                     mine=mine_var.get(), archived=arch_var.get())
        tree.delete(*tree.get_children())
        try:
            groups = TG.list_groups(
                academic_year=year_var.get(),
                year_group=None if yg_var.get() == ALL else int(yg_var.get()),
                subject_id=subjects[subj_var.get()].subject_id if subj_var.get() != ALL else None,
                teacher=principal.username if mine_var.get() else None,
                include_archived=arch_var.get())
            rows = TG.info(groups)
        except Exception:
            logger.exception("Teaching groups list failed")
            count.configure(text="Couldn't read teaching groups - see the log.")
            return
        for i in rows:
            g = i.group
            tag = "archived" if not g.is_active else "over" if (i.spaces or 0) < 0 else ""
            tree.insert("", "end", iid=str(g.group_id), tags=(tag,), values=(
                g.code, i.subject.label, g.year_group, g.kind_label, g.teacher_name or "",
                g.room or "", _size(i) if g.is_active else "", i.lessons or "",
                "Open" if g.is_active else "Archived"))
        count.configure(text=f"{len(rows)} group(s) · {sum(i.pupils for i in rows)} places"
                        + ("" if current_only() else " · a past year: read-only"))
        for w in warn.winfo_children():
            w.destroy()
        if current_only():
            gaps = TG.coverage()
            if gaps:
                row = ttk.Frame(warn)
                row.pack(fill="x", pady=(0, 4))
                ttk.Label(row, text="No group yet: " + "; ".join(
                    f"{s.code} Y{y} ({len(ps)})" for s, y, ps in gaps[:8])
                          + (" …" if len(gaps) > 8 else "") + " - core subjects.",
                          foreground="#a60", wraplength=900, justify="left").pack(side="left")
                ttk.Button(row, text="Details…", command=lambda: coverage_dialog(
                    parent, gaps)).pack(side="right")

    def selected() -> TG.TeachingGroup | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Teaching Groups", "Select a group first.", parent=parent)
            return None
        return TG.get(int(sel[0]))

    def run(fn, title: str) -> None:
        try:
            fn()
        except (TG.ValidationError, TG.PermissionDenied) as e:
            messagebox.showerror(title, _problems(e), parent=parent)
            return
        refresh()

    def edit() -> None:
        g = selected()
        if g:
            group_dialog(parent, principal, g, refresh)

    def delete() -> None:
        g = selected()
        if g and messagebox.askyesno("Delete", f"Delete {g.code}?\n\nFor a group set up by "
                                     "mistake. A group that has had pupils is archived "
                                     "instead.", parent=parent):
            run(lambda: TG.delete(g.group_id, actor=principal), "Delete")

    def archive() -> None:
        g = selected()
        if not g:
            return
        if g.is_active:
            n = len(TG.members(g.group_id))
            if messagebox.askyesno("Archive", f"Archive {g.code}?"
                                   + (f"\n\nIts {_plural(n)} come out of it so they can join "
                                      "another group; the history keeps the list." if n else ""),
                                   parent=parent):
                run(lambda: TG.archive(g.group_id, actor=principal), "Archive")
        else:
            run(lambda: TG.restore(g.group_id, actor=principal), "Restore")

    def open_selected(_e=None) -> None:
        sel = tree.selection()
        if sel:
            open_group(int(sel[0]))

    kw = {} if editor else {"state": "disabled"}
    ttk.Button(btns, text="New", command=lambda: group_dialog(parent, principal, None, refresh),
               **kw).pack(side="left", padx=2)
    ttk.Button(btns, text="Edit", command=edit, **kw).pack(side="left", padx=2)
    ttk.Button(btns, text="Delete", command=delete, **kw).pack(side="left", padx=2)
    ttk.Button(btns, text="Archive / Restore", command=archive, **kw).pack(side="left", padx=2)
    ttk.Button(btns, text="Refresh", command=refresh).pack(side="left", padx=2)
    ttk.Button(btns, text="Open", command=open_selected).pack(side="left", padx=(12, 2))
    ttk.Button(btns, text="Create from forms…", command=lambda: from_forms_dialog(
        parent, principal, refresh), **kw).pack(side="left", padx=(12, 2))
    tree.bind("<Double-1>", open_selected)
    for v in (year_var, yg_var, subj_var, mine_var, arch_var):
        v.trace_add("write", refresh)
    refresh()


# ── One group ────────────────────────────────────────────────────────

def draw_group(parent: ttk.Frame, group_id: int, *, principal: Principal,
               open_pupil: Callable[[int], None], on_back: Callable[[], None],
               on_changed: Callable[[], None]) -> None:
    try:
        g = TG.get(group_id)
    except TG.NotFound:
        ttk.Label(parent, text="That group no longer exists.").pack(anchor="w")
        ttk.Button(parent, text="← Teaching Groups", command=on_back).pack(anchor="w")
        return
    activity_log.record("teaching_group.view", target=f"TG{group_id}")
    info = TG.info([g])[0]
    editor = principal.role in TEACHING_GROUP_EDITORS and g.is_active and g.is_current
    pupils = TG.members(group_id)

    head = ttk.Frame(parent)
    head.pack(fill="x")
    ttk.Button(head, text="← Teaching Groups", command=on_back).pack(side="left")
    ttk.Label(head, text=f"  {g.code}", font=("", 16, "bold")).pack(side="left")
    ttk.Label(head, text=f"  {info.subject.name} · Year {g.year_group} · {g.kind_label} · "
                         f"{g.academic_year}" + ("" if g.is_active else " · archived"),
              foreground="#555").pack(side="left", pady=(4, 0))
    if editor:
        ttk.Button(head, text="Edit", command=lambda: group_dialog(
            parent, principal, TG.get(group_id), on_changed)).pack(side="right")

    details = ttk.LabelFrame(parent, text="Group", padding=8)
    details.pack(fill="x", pady=(8, 0))
    for line in (
            f"Teacher: {g.teacher_name or '—'}"
            + (f" ({g.teacher_email})" if g.teacher_email else "")
            + (f" · login {g.teacher_username}" if g.teacher_username else "")
            + (f" · second teacher {g.second_teacher}" if g.second_teacher else ""),
            f"Room: {g.room or '—'} · Pupils: {_size(info)} · Lessons per week: "
            f"{info.lessons or '—'}" + ("" if g.lessons_per_week else " (curriculum plan)"),
            f"Notes: {g.notes}" if g.notes else ""):
        if line:
            ttk.Label(details, text=line, wraplength=1000, justify="left").pack(anchor="w")
    if not g.is_current:
        ttk.Label(details, text=f"This group is from {g.academic_year} and can't be changed.",
                  foreground="#888").pack(anchor="w")
    moved = TG.wrong_year(group_id) if g.is_active else []
    if moved:
        ttk.Label(details, text="Now in a different year: " + ", ".join(
            f"{p.display_name} (Y{p.year_group})" for p in moved) + " - remove them, or move "
            "them to a group for their year.", foreground="#a60", wraplength=1000,
                  justify="left").pack(anchor="w")

    box = ttk.LabelFrame(parent, text="Pupils", padding=8)
    box.pack(fill="both", expand=True, pady=(8, 0))
    tree = _tree(box, (("adm", "Adm. no", 90), ("name", "Pupil", 220), ("form", "Form", 70),
                       ("g", "Gender", 70), ("sen", "SEN", 45), ("fsm", "FSM", 45),
                       ("eal", "EAL", 45)), height=12, select="extended")
    for p in pupils:
        tree.insert("", "end", iid=str(p.pupil_id), values=(
            p.admission_no, p.display_name, p.form_group or "", p.gender, p.sen_status,
            "Y" if p.fsm_eligible else "", "Y" if p.eal else ""))
    if not pupils:
        ttk.Label(box, text="No pupils in this group yet.", foreground="#888").pack(anchor="w")

    def chosen() -> list[int]:
        ids = [int(i) for i in tree.selection()]
        if not ids:
            messagebox.showinfo("Group", "Select pupils first (Ctrl/Shift-click for several).",
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
                                           f"{g.code}?", parent=parent):
                TG.remove_pupils(ids, group_id, actor=principal)
                on_changed()

        ttk.Button(pb, text="Add pupils…", command=lambda: add_dialog(
            parent, principal, g, on_changed)).pack(side="left", padx=6)
        ttk.Button(pb, text="Add a form…", command=lambda: add_form_dialog(
            parent, principal, g, on_changed)).pack(side="left")
        ttk.Button(pb, text="Move to another group…", command=lambda: (
            ids := chosen()) and move_dialog(parent, principal, g, ids, on_changed)).pack(
            side="left", padx=6)
        ttk.Button(pb, text="Remove from group", command=take_out).pack(side="left")

    def export() -> None:
        path = filedialog.asksaveasfilename(
            parent=parent, defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="group_" + "".join(c if c.isalnum() else "_" for c in g.code) + ".csv")
        if not path:
            return
        needs = principal.can_edit_pupils and messagebox.askyesno(
            "Export", "Include SEN, FSM and EAL columns?\n\nOnly do this if whoever gets the "
            "file needs them.", parent=parent)
        try:
            n = TG.export_class_list(group_id, path, actor=principal, include_needs=needs)
        except (TG.PermissionDenied, OSError) as e:
            messagebox.showerror("Export", str(e), parent=parent)
            return
        messagebox.showinfo("Export", f"{_plural(n)} written to {path}.", parent=parent)

    ttk.Button(pb, text="Export class list…", command=export).pack(side="left", padx=6)
    if principal.can_email_bulk and pupils:
        def email() -> None:
            from education_system.systems.secondary.modules.communication.gui import email_views
            ids = [int(i) for i in tree.selection()] or [p.pupil_id for p in pupils]
            email_views.open_compose(parent, principal=principal, on_sent=lambda _m: None,
                                     pupil_ids=ids)

        ttk.Button(pb, text="E-mail parents…", command=email).pack(side="left")
    hist = TG.history(group_id)[:4]
    if hist:
        ttk.Label(parent, text="Recent changes: " + "; ".join(
            f"{h['at'][:16]} {h['actor']} {describe(h)}" for h in hist),
                  foreground="#888", wraplength=1000, justify="left").pack(anchor="w",
                                                                          pady=(6, 0))


# ── Dialogs ──────────────────────────────────────────────────────────

def _dialog(owner, title: str, resizable: bool = False) -> tuple[tk.Toplevel, ttk.Frame]:
    return W.dialog(owner, title, resizable=resizable, padding=14)


def _teacher_label(t: dict) -> str:
    return f"{t['display_name']} ({t['username']})"


def group_dialog(owner, principal: Principal, g: TG.TeachingGroup | None,
                 after: Callable[[], None]) -> None:
    if principal.role not in TEACHING_GROUP_EDITORS:
        messagebox.showinfo("Teaching Groups", "Your account can view teaching groups but not "
                            "change them.", parent=owner)
        return
    if g is not None and (not g.is_current or not g.is_active):
        messagebox.showinfo("Edit", "Only this year's open groups can be changed.", parent=owner)
        return
    win, frm = _dialog(owner, f"Edit {g.code}" if g else "New teaching group")
    has_pupils = bool(g and TG.members(g.group_id, include_left=True))
    subjects = {s.label: s for s in S.list_subjects()}
    if g and g.subject_id not in {s.subject_id for s in subjects.values()}:
        cur = S.get(g.subject_id)
        subjects[cur.label] = cur
    teachers = {_teacher_label(t): t for t in TG.teacher_choices()}
    w: dict[str, object] = {}
    r = 0

    def label(text: str, hint: str = "") -> None:
        ttk.Label(frm, text=text + ":").grid(row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        if hint:
            ttk.Label(frm, text=hint, foreground="#888").grid(row=r, column=2, sticky="w",
                                                              padx=6)

    def entry(key: str, width: int, hint: str = "") -> ttk.Entry:
        nonlocal r
        label(TG.FIELD_LABELS[key] + (" *" if key == "code" else ""), hint)
        e = ttk.Entry(frm, width=width)
        v = getattr(g, key) if g else None
        e.insert(0, "" if v is None else str(v))
        e.grid(row=r, column=1, sticky="w", pady=2)
        w[key] = e
        r += 1
        return e

    entry("code", 16, "e.g. 8x/Ma1")
    label("Subject *")
    subj_cb = ttk.Combobox(frm, values=list(subjects), state="readonly", width=32)
    subj_cb.set(next((k for k, s in subjects.items() if g and s.subject_id == g.subject_id), ""))
    subj_cb.grid(row=r, column=1, sticky="w", pady=2)
    r += 1
    label("Year group *")
    yr_cb = ttk.Combobox(frm, values=[str(y) for y in P.YEAR_GROUPS], state="readonly", width=5)
    yr_cb.set(str(g.year_group) if g else "")
    yr_cb.grid(row=r, column=1, sticky="w", pady=2)
    r += 1
    if has_pupils:
        subj_cb.configure(state="disabled")
        yr_cb.configure(state="disabled")
        ttk.Label(frm, text="Has pupils: subject and year are fixed.", foreground="#888").grid(
            row=r - 1, column=2, sticky="w", padx=6)
    label("Kind")
    kind_row = ttk.Frame(frm)
    kind_row.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
    kind_cb = ttk.Combobox(kind_row, values=list(TG.KINDS), state="readonly", width=8)
    kind_cb.set(g.kind if g else "Mixed")
    kind_cb.pack(side="left")
    ttk.Label(kind_row, text="  Set:").pack(side="left")
    set_e = ttk.Entry(kind_row, width=4)
    set_e.insert(0, str(g.set_number) if g and g.set_number else "")
    set_e.pack(side="left")
    r += 1

    def sync_kind(_e=None) -> None:
        set_e.configure(state="normal" if kind_cb.get() == "Set" else "disabled")

    kind_cb.bind("<<ComboboxSelected>>", sync_kind)
    sync_kind()
    label("Teacher's login", "fills in name and e-mail")
    login_cb = ttk.Combobox(frm, values=["", *teachers], state="readonly", width=32)
    login_cb.set(next((k for k, t in teachers.items() if g and g.teacher_username
                       and t["username"].lower() == g.teacher_username.lower()), ""))
    login_cb.grid(row=r, column=1, sticky="w", pady=2)
    r += 1
    name_e = entry("teacher_name", 32)
    email_e = entry("teacher_email", 32)

    def on_login(_e=None) -> None:
        t = teachers.get(login_cb.get())
        if t:
            name_e.delete(0, "end")
            name_e.insert(0, t["display_name"])
            email_e.delete(0, "end")
            email_e.insert(0, t["email"] or "")

    login_cb.bind("<<ComboboxSelected>>", on_login)
    entry("second_teacher", 32)
    entry("room", 10)
    entry("capacity", 5, "blank = no limit")
    entry("lessons_per_week", 5, "blank = from the curriculum plan")
    label("Notes")
    notes = tk.Text(frm, width=44, height=3, wrap="word")
    notes.insert("1.0", (g.notes if g else None) or "")
    notes.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
    r += 1
    error = tk.StringVar()
    ttk.Label(frm, textvariable=error, foreground="#a00", wraplength=460, justify="left").grid(
        row=r, column=0, columnspan=3, sticky="w")

    def save() -> None:
        data = {k: e.get() for k, e in w.items()}  # type: ignore[attr-defined]
        data["notes"] = notes.get("1.0", "end").strip()
        data["kind"] = kind_cb.get()
        data["set_number"] = set_e.get() if kind_cb.get() == "Set" else ""
        t = teachers.get(login_cb.get())
        data["teacher_username"] = t["username"] if t else ""
        if not has_pupils:
            s = subjects.get(subj_cb.get())
            data["subject_id"] = s.subject_id if s else None
            data["year_group"] = yr_cb.get()
        try:
            if g is None:
                TG.create(data, actor=principal)
            else:
                TG.update(g.group_id, data, actor=principal)
        except TG.ValidationError as e:
            error.set(_problems(e))
            return
        except TG.PermissionDenied as e:
            messagebox.showerror("Teaching Groups", str(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=r + 1, column=0, columnspan=3, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def _report(owner, title: str, done: int, refused: list[tuple[str, str]]) -> None:
    messagebox.showinfo(title, f"{_plural(done)} added."
                        + ("\n\nNot added:\n" + "\n".join(f"• {a}: {w}" for a, w in refused[:15])
                           + (" …" if len(refused) > 15 else "") if refused else ""),
                        parent=owner)


def _add(win, owner, principal, ids, g, after, *, move: bool) -> None:
    try:
        try:
            done, refused = TG.add_pupils(ids, g.group_id, actor=principal, move=move)
        except TG.ValidationError as e:
            if g.capacity is None or not any("room for" in p for p in e.problems):
                raise
            if not messagebox.askyesno("Over capacity", _problems(e)
                                       + "\n\nGo over capacity anyway?", parent=win):
                return
            done, refused = TG.add_pupils(ids, g.group_id, actor=principal, move=move,
                                          allow_over_capacity=True)
    except (TG.ValidationError, TG.PermissionDenied) as e:
        messagebox.showerror("Group", _problems(e), parent=win)
        return
    win.destroy()
    _report(owner, "Group", len(done), refused)
    after()


def add_dialog(owner, principal: Principal, g: TG.TeachingGroup,
               after: Callable[[], None]) -> None:
    win, frm = _dialog(owner, f"Add pupils to {g.code}", resizable=True)
    ttk.Label(frm, text=f"Year {g.year_group} pupils not in {g.code}. Ctrl/Shift-click to "
                        "choose several.").pack(anchor="w")
    grouped = tk.BooleanVar(value=False)
    ttk.Checkbutton(frm, text="Also show pupils already in another group for this subject "
                              "(they'll be moved)", variable=grouped).pack(anchor="w", pady=4)
    form_var = tk.StringVar(value=ALL)
    fr = ttk.Frame(frm)
    fr.pack(fill="x", pady=(0, 4))
    ttk.Label(fr, text="Form:").pack(side="left")
    ttk.Combobox(fr, textvariable=form_var, values=[ALL, *FG.names_for_year(g.year_group)],
                 state="readonly", width=8).pack(side="left", padx=4)
    tree = _tree(frm, (("adm", "Adm. no", 90), ("name", "Pupil", 200), ("form", "Form", 70),
                       ("g", "Gender", 70), ("now", "Group now", 100)), height=14,
                 select="extended")

    def fill(*_a) -> None:
        tree.delete(*tree.get_children())
        for p, other in TG.candidates(g.group_id, include_grouped=grouped.get()):
            if form_var.get() != ALL and (p.form_group or "") != form_var.get():
                continue
            tree.insert("", "end", iid=str(p.pupil_id), values=(
                p.admission_no, p.display_name, p.form_group or "", p.gender, other or "—"))

    grouped.trace_add("write", fill)
    form_var.trace_add("write", fill)
    fill()
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Add to group", command=lambda: tree.selection() and _add(
        win, owner, principal, [int(i) for i in tree.selection()], g, after,
        move=grouped.get())).pack(side="right", padx=(0, 6))


def add_form_dialog(owner, principal: Principal, g: TG.TeachingGroup,
                    after: Callable[[], None]) -> None:
    forms = {f.name: f for f in FG.list_forms(g.year_group)}
    if not forms:
        messagebox.showinfo("Add a form", f"Year {g.year_group} has no forms set up.",
                            parent=owner)
        return
    win, frm = _dialog(owner, f"Add a form to {g.code}")
    ttk.Label(frm, text="Form:").grid(row=0, column=0, sticky="w")
    cb = ttk.Combobox(frm, values=list(forms), state="readonly", width=10)
    cb.grid(row=0, column=1, sticky="w", padx=6)
    move = tk.BooleanVar(value=False)
    ttk.Checkbutton(frm, text="Move pupils already in another group for this subject",
                    variable=move).grid(row=1, column=0, columnspan=2, sticky="w", pady=6)

    def go() -> None:
        f = forms.get(cb.get())
        if f:
            _add(win, owner, principal, [p.pupil_id for p in FG.members(f)], g, after,
                 move=move.get())

    bar = ttk.Frame(frm)
    bar.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Add", command=go).pack(side="right", padx=(0, 6))


def move_dialog(owner, principal: Principal, g: TG.TeachingGroup, pupil_ids: list[int],
                after: Callable[[], None]) -> None:
    others = [i for i in TG.info(TG.list_groups(year_group=g.year_group,
                                                subject_id=g.subject_id))
              if i.group.group_id != g.group_id]
    if not others:
        messagebox.showinfo("Move", f"There's no other {S.get(g.subject_id).code} group in "
                            f"Year {g.year_group}.", parent=owner)
        return
    win, frm = _dialog(owner, "Move to another group")
    ttk.Label(frm, text=f"Move {_plural(len(pupil_ids))} from {g.code} to:").grid(
        row=0, column=0, sticky="w")
    labels = {f"{i.group.code} - {i.group.teacher_name or 'no teacher'}, {_size(i)}": i.group
              for i in others}
    to = ttk.Combobox(frm, values=list(labels), state="readonly", width=40)
    to.grid(row=1, column=0, sticky="w", pady=(6, 0))
    bar = ttk.Frame(frm)
    bar.grid(row=2, column=0, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Move", command=lambda: to.get() and _add(
        win, owner, principal, pupil_ids, labels[to.get()], after, move=True)).pack(
        side="right", padx=(0, 6))


def from_forms_dialog(owner, principal: Principal, after: Callable[[], None]) -> None:
    subjects = {s.label: s for s in S.list_subjects()}
    if not subjects:
        messagebox.showinfo("Create from forms", "Add subjects first (Subjects).", parent=owner)
        return
    win, frm = _dialog(owner, "Create groups from forms")
    ttk.Label(frm, text="Makes one group per form in the year, coded <form>/<subject code>, "
                        "with the form's pupils - for subjects taught in form groups.",
              wraplength=420, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text="Subject:").grid(row=1, column=0, sticky="w", pady=(8, 2))
    subj = ttk.Combobox(frm, values=list(subjects), state="readonly", width=32)
    subj.grid(row=1, column=1, sticky="w", pady=(8, 2))
    ttk.Label(frm, text="Year group:").grid(row=2, column=0, sticky="w")
    yr = ttk.Combobox(frm, state="readonly", width=5)
    yr.grid(row=2, column=1, sticky="w")
    note = ttk.Label(frm, foreground="#666", wraplength=420, justify="left")
    note.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def on_subject(_e=None) -> None:
        s = subjects.get(subj.get())
        yr.configure(values=[str(y) for y in (s.years if s else ())])
        yr.set("")
        note.configure(text="")

    def on_year(_e=None) -> None:
        s = subjects.get(subj.get())
        if s and yr.get():
            forms = FG.names_for_year(int(yr.get()))
            note.configure(text=("Will make: " + ", ".join(f"{f}/{s.code}" for f in forms))
                           if forms else f"Year {yr.get()} has no forms set up.")

    subj.bind("<<ComboboxSelected>>", on_subject)
    yr.bind("<<ComboboxSelected>>", on_year)

    def go() -> None:
        s = subjects.get(subj.get())
        if not s or not yr.get():
            return
        try:
            made, notes = TG.create_from_forms(s.subject_id, int(yr.get()), actor=principal)
        except (TG.ValidationError, TG.PermissionDenied) as e:
            messagebox.showerror("Create from forms", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Create from forms", f"{len(made)} group(s) made."
                            + ("\n\n" + "\n".join(notes) if notes else ""), parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Create", command=go).pack(side="right", padx=(0, 6))


def coverage_dialog(owner, gaps) -> None:
    win, frm = _dialog(owner, "Core subjects: pupils with no group", resizable=True)
    tree = _tree(frm, (("subject", "Subject", 180), ("yr", "Year", 50), ("n", "Pupils", 60),
                       ("name", "Who", 420)), height=14)
    for s, y, ps in gaps:
        tree.insert("", "end", values=(s.label, y, len(ps), ", ".join(
            f"{p.display_name} ({p.form_group or 'no form'})" for p in ps[:12])
            + (" …" if len(ps) > 12 else "")))
    ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(8, 0))

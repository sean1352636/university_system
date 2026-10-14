"""GUI tabs for attendance mark codes, authorisation and audit.

Three panels, mounted as extra tabs on the Attendance screen:

* **Codes & reasons** — the statutory vocabulary, the college's editable
  absence-reason list, and how the marks in a window break down across
  them.
* **Authorisation** — the queue of absences nobody has decided about,
  with authorise / withdraw to hand, plus the off-site placement
  register.
* **Audit** — the amendment trail and the voided rows, which are the two
  things a governor asks for.

Like :mod:`attendance_register_views`, this module does not import
:mod:`attendance_views`; the import graph stays one-way.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date, timedelta as _timedelta
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as data,
    attendance_audit as audit,
    attendance_authorisation as authz,
    attendance_codes as codes,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as cg_data,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as course_data,
)

logger = logging.getLogger(__name__)

_WINDOW_DAYS: int = 28


def _today() -> str:
    return _date.today().isoformat()


def _window_start() -> str:
    return (_date.today() - _timedelta(days=_WINDOW_DAYS)).isoformat()


def _actor(gui) -> str | None:
    auth = getattr(gui, "auth", None)
    return ((getattr(auth, "current_user", None) or {}).get("username")
            if auth else None)


def _group_choices() -> tuple[list[str], dict[str, int]]:
    groups = cg_data.list_groups()
    courses = {c.course_id: c for c in course_data.list_courses()}
    labels = [
        f"#{g.group_id} {g.group_name} "
        f"({courses[g.course_id].course_code if g.course_id in courses else '?'})"
        for g in groups
    ]
    return labels, {label: g.group_id for label, g in zip(labels, groups)}


def _date_bar(parent) -> tuple[ttk.Frame, tk.StringVar, tk.StringVar]:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    from_var = tk.StringVar(value=_window_start())
    to_var = tk.StringVar(value=_today())
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(
        side="left", padx=(4, 12))
    return bar, from_var, to_var


def _tree(parent, columns: list[tuple[str, str, int]],
          height: int = 12) -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c[0] for c in columns],
                        show="headings", height=height)
    for key, text, width in columns:
        tree.heading(key, text=text)
        tree.column(key, width=width, anchor="w")
    scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


def _selected_id(tree: ttk.Treeview, parent) -> int | None:
    selection = tree.selection()
    if not selection:
        messagebox.showinfo("Nothing selected", "Pick a row first.",
                            parent=parent)
        return None
    try:
        return int(tree.item(selection[0], "values")[0])
    except (ValueError, IndexError):
        return None


# ── Codes & reasons tab ─────────────────────────────────────────────

def build_codes_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)

    reference = ttk.Frame(inner, padding=8)
    reasons = ttk.Frame(inner, padding=8)
    breakdown = ttk.Frame(inner, padding=8)
    inner.add(reference, text="Mark codes")
    inner.add(reasons, text="Absence reasons")
    inner.add(breakdown, text="Breakdown")

    _build_code_reference(reference)
    _build_reasons(gui, reasons)
    _build_breakdown(breakdown)


def _build_code_reference(parent: ttk.Frame) -> None:
    ttk.Label(
        parent,
        text=("The statutory vocabulary. What matters for every "
              "calculation is the meaning, not the letter: Present and "
              "Approved both count as attending, and 'Not counted' codes "
              "leave the denominator rather than counting as absence."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    tree = _tree(parent, [
        ("code", "Code", 60),
        ("label", "Label", 280),
        ("meaning", "Counts as", 120),
        ("status", "Status", 100),
        ("description", "Notes", 360),
    ], height=18)
    for mark in codes.MARK_CODES:
        tree.insert("", "end", values=(mark.code, mark.label, mark.meaning,
                                       mark.status, mark.description))


def _build_reasons(gui, parent: ttk.Frame) -> None:
    ttk.Label(
        parent,
        text=("The college's own list. A code says how an absence "
              "counts; a reason says what happened. Reasons are archived "
              "rather than deleted, so historic rows keep pointing at "
              "something meaningful."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    show_archived = tk.BooleanVar(value=False)
    ttk.Checkbutton(parent, text="Include archived",
                    variable=show_archived).pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("id", "ID", 50),
        ("name", "Name", 220),
        ("category", "Category", 120),
        ("code", "Default code", 100),
        ("evidence", "Evidence", 90),
        ("used", "In use", 70),
        ("state", "State", 90),
    ])
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(8, 0))

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for reason in codes.list_reasons(active_only=not show_archived.get()):
            tree.insert("", "end", values=(
                reason.reason_id, reason.name, reason.category,
                reason.default_code or "—",
                "yes" if reason.requires_evidence else "no",
                codes.reason_usage(reason.reason_id),
                "active" if reason.active else "archived"))

    def add() -> None:
        name = simpledialog.askstring(
            "New reason", "Reason name:", parent=gui.root)
        if not name:
            return
        category = simpledialog.askstring(
            "New reason",
            "Category (" + " / ".join(codes.REASON_CATEGORIES) + "):",
            initialvalue=codes.DEFAULT_REASON_CATEGORY, parent=gui.root)
        code = simpledialog.askstring(
            "New reason", "Default mark code (blank for none):",
            parent=gui.root)
        try:
            codes.create_reason({
                "name": name,
                "category": (category or codes.DEFAULT_REASON_CATEGORY),
                "default_code": (code or "").strip() or None,
            })
        except ValidationError as e:
            messagebox.showerror("Invalid reason", str(e), parent=gui.root)
            return
        refresh()

    def archive() -> None:
        reason_id = _selected_id(tree, gui.root)
        if reason_id is None:
            return
        used = codes.reason_usage(reason_id)
        note = (f"\n\n{used} live row(s) use it. They keep it."
                if used else "")
        if not messagebox.askyesno(
                "Archive reason",
                f"Hide reason #{reason_id} from the pickers?{note}",
                parent=gui.root):
            return
        try:
            codes.archive_reason(reason_id)
        except ValidationError as e:
            messagebox.showerror("Could not archive", str(e), parent=gui.root)
            return
        refresh()

    def restore() -> None:
        reason_id = _selected_id(tree, gui.root)
        if reason_id is None:
            return
        try:
            codes.restore_reason(reason_id)
        except ValidationError as e:
            messagebox.showerror("Could not restore", str(e), parent=gui.root)
            return
        refresh()

    ttk.Button(actions, text="Add", command=add).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Archive", command=archive).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Restore", command=restore).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Refresh", command=refresh).pack(side="left")
    show_archived.trace_add("write", lambda *_: refresh())
    refresh()


def _build_breakdown(parent: ttk.Frame) -> None:
    bar, from_var, to_var = _date_bar(parent)
    group_labels, group_by_label = _group_choices()
    group_var = tk.StringVar(value="(all)")
    ttk.Label(bar, text="Group:").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var,
                 values=["(all)", *group_labels], state="readonly",
                 width=30).pack(side="left", padx=(4, 8))

    tree = _tree(parent, [
        ("code", "Code", 60),
        ("label", "Label", 300),
        ("meaning", "Counts as", 130),
        ("count", "Marks", 80),
        ("share", "Share", 80),
    ])
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(6, 0))

    def refresh() -> None:
        tree.delete(*tree.get_children())
        group_id = group_by_label.get(group_var.get())
        try:
            rows = codes.code_breakdown(
                group_id=group_id,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None)
        except ValidationError as e:
            summary.config(text=str(e), foreground="#a33")
            return
        total = sum(r.count for r in rows)
        for row in rows:
            share = (100.0 * row.count / total) if total else 0.0
            tree.insert("", "end", values=(
                row.code or "—", row.label, row.meaning, row.count,
                f"{share:.1f}%"))
        meanings = codes.meaning_breakdown(
            group_id=group_id,
            date_from=from_var.get().strip() or None,
            date_to=to_var.get().strip() or None)
        attending = meanings[codes.PRESENT] + meanings[codes.APPROVED]
        possible = total - meanings[codes.NOT_COUNTED]
        pct = f"{100.0 * attending / possible:.1f}%" if possible else "—"
        uncoded = codes.uncoded_count(
            date_from=from_var.get().strip() or None,
            date_to=to_var.get().strip() or None)
        summary.config(
            text=(f"{total} mark(s) · attending {attending}/{possible} "
                  f"= {pct}" +
                  (f" · {uncoded} row(s) still uncoded" if uncoded else "")),
            foreground="#555")

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    refresh()


# ── Authorisation tab ───────────────────────────────────────────────

def build_authorisation_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    queue = ttk.Frame(inner, padding=8)
    offsite = ttk.Frame(inner, padding=8)
    inner.add(queue, text="Decision queue")
    inner.add(offsite, text="Off-site register")
    _build_queue(gui, queue)
    _build_offsite(gui, offsite)


def _build_queue(gui, parent: ttk.Frame) -> None:
    bar, from_var, to_var = _date_bar(parent)
    stale_only = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text=f"Waiting {authz.STALE_AFTER_DAYS}+ days",
                    variable=stale_only).pack(side="left", padx=(4, 8))

    ttk.Label(
        parent,
        text=("Absences nobody has decided about — sitting on N, or on a "
              "bare Absent status from before codes existed. An absence "
              "already coded O has been decided (the answer was no), so "
              "it is not here."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("id", "Rec", 60),
        ("date", "Date", 100),
        ("student", "Student", 200),
        ("code", "Code", 60),
        ("waiting", "Waiting", 80),
        ("reason", "Reason", 220),
    ])
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(6, 4))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w")

    def refresh() -> None:
        tree.delete(*tree.get_children())
        try:
            rows = authz.pending(
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
                stale_only=stale_only.get())
        except ValidationError as e:
            summary.config(text=str(e), foreground="#a33")
            return
        for row in rows:
            tree.insert("", "end", values=(
                row.record_id, row.record.date, row.student_name,
                row.record.code or "—",
                f"{row.days_waiting}d" + (" !" if row.stale else ""),
                row.reason_name or ""))
        stale = sum(1 for r in rows if r.stale)
        summary.config(
            text=(f"{len(rows)} awaiting a decision"
                  + (f", {stale} for {authz.STALE_AFTER_DAYS}+ days"
                     if stale else "")),
            foreground="#a33" if stale else "#555")

    def authorise() -> None:
        record_id = _selected_id(tree, gui.root)
        if record_id is None:
            return
        reasons = codes.list_reasons()
        names = [r.name for r in reasons]
        chosen = simpledialog.askstring(
            "Authorise",
            "Absence reason (one of: " + ", ".join(names[:8]) + " …):",
            parent=gui.root)
        reason = next((r for r in reasons
                       if r.name.lower() == (chosen or "").strip().lower()),
                      None)
        note = simpledialog.askstring(
            "Authorise", "Grounds / note (optional):", parent=gui.root)
        who = _actor(gui) or simpledialog.askstring(
            "Authorise", "Authorised by:", parent=gui.root)
        if not who:
            return
        try:
            authz.authorise(record_id, authorised_by=who,
                            reason_id=reason.reason_id if reason else None,
                            note=note or None)
        except ValidationError as e:
            messagebox.showerror("Could not authorise", str(e),
                                 parent=gui.root)
            return
        refresh()

    def refuse() -> None:
        record_id = _selected_id(tree, gui.root)
        if record_id is None:
            return
        if not messagebox.askyesno(
                "Record as unauthorised",
                f"Code record #{record_id} as O (unauthorised absence)?",
                parent=gui.root):
            return
        try:
            data.update_record(
                record_id, {"code": "O", "status": "Absent"},
                actor=_actor(gui), reason="Absence not authorised")
        except ValidationError as e:
            messagebox.showerror("Could not update", str(e), parent=gui.root)
            return
        refresh()

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(actions, text="Authorise", command=authorise).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Mark unauthorised", command=refuse).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Refresh", command=refresh).pack(side="left")
    stale_only.trace_add("write", lambda *_: refresh())
    refresh()


def _build_offsite(gui, parent: ttk.Frame) -> None:
    bar, from_var, to_var = _date_bar(parent)
    ttk.Label(
        parent,
        text=("Learners who were elsewhere but still in education. "
              "Approved-activity codes count as attending, so a placement "
              "does not dent a learner's percentage — which is the whole "
              "point of recording it properly."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("id", "Rec", 60),
        ("date", "Date", 100),
        ("student", "Student", 200),
        ("code", "Code", 60),
        ("location", "Location", 300),
    ])
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(6, 4))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w")

    def refresh() -> None:
        tree.delete(*tree.get_children())
        try:
            rows = authz.list_offsite(
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None)
        except ValidationError as e:
            summary.config(text=str(e), foreground="#a33")
            return
        for row in rows:
            tree.insert("", "end", values=(
                row.record.record_id, row.record.date, row.student_name,
                row.code, row.location))
        breakdown = authz.offsite_breakdown(
            date_from=from_var.get().strip() or None,
            date_to=to_var.get().strip() or None)
        summary.config(text=(f"{len(rows)} placement mark(s) · " +
                             ", ".join(f"{k} ({v})"
                                       for k, v in breakdown.items())),
                       foreground="#555")

    def add() -> None:
        raw = simpledialog.askstring(
            "Mark off site", "Record ID:", parent=gui.root)
        if not raw or not raw.strip().isdigit():
            return
        location = simpledialog.askstring(
            "Mark off site",
            "Location / employer (e.g. " + ", ".join(
                authz.OFFSITE_KINDS[:3]) + "):", parent=gui.root)
        if not location:
            return
        try:
            authz.set_offsite(int(raw.strip()), location=location,
                              actor=_actor(gui))
        except ValidationError as e:
            messagebox.showerror("Could not mark off site", str(e),
                                 parent=gui.root)
            return
        refresh()

    def clear() -> None:
        record_id = _selected_id(tree, gui.root)
        if record_id is None:
            return
        try:
            authz.clear_offsite(record_id, actor=_actor(gui))
        except ValidationError as e:
            messagebox.showerror("Could not clear", str(e), parent=gui.root)
            return
        refresh()

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(actions, text="Mark off site", command=add).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Clear placement", command=clear).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Refresh", command=refresh).pack(side="left")
    refresh()


# ── Audit tab ───────────────────────────────────────────────────────

def build_audit_tab(gui, parent: ttk.Frame) -> None:
    inner = ttk.Notebook(parent)
    inner.pack(fill="both", expand=True)
    trail = ttk.Frame(inner, padding=8)
    voided = ttk.Frame(inner, padding=8)
    inner.add(trail, text="Amendment trail")
    inner.add(voided, text="Voided records")
    _build_trail(gui, trail)
    _build_voided(gui, voided)


def _build_trail(gui, parent: ttk.Frame) -> None:
    bar, from_var, to_var = _date_bar(parent)
    student_var = tk.StringVar(value="")
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Entry(bar, textvariable=student_var, width=14).pack(
        side="left", padx=(4, 12))

    ttk.Label(
        parent,
        text=("Append-only, and deliberately not the undo buffer: undo "
              "is a short stack a teacher pops, this is a record nobody "
              "can. Dates filter on the lesson being amended, not on "
              "when somebody amended it."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("when", "Amended at", 150),
        ("action", "Action", 100),
        ("student", "Student", 110),
        ("date", "Lesson date", 100),
        ("change", "Change", 300),
        ("who", "By", 110),
        ("reason", "Reason", 220),
    ])
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(6, 0))

    def refresh() -> None:
        tree.delete(*tree.get_children())
        try:
            rows = audit.list_amendments(
                student_id=student_var.get().strip() or None,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
                limit=300)
        except ValidationError as e:
            summary.config(text=str(e), foreground="#a33")
            return
        for entry in rows:
            change = (f"{entry.field}: {entry.old_value or '—'} → "
                      f"{entry.new_value or '—'}") if entry.field else "—"
            tree.insert("", "end", values=(
                entry.amended_at or "", entry.action, entry.student_id,
                entry.date, change, entry.amended_by or "—",
                entry.reason or ""))
        counts = audit.amendment_summary(
            date_from=from_var.get().strip() or None,
            date_to=to_var.get().strip() or None)
        summary.config(text=(f"{len(rows)} shown · " + ", ".join(
            f"{k} {v}" for k, v in counts.items() if v)), foreground="#555")

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    refresh()


def _build_voided(gui, parent: ttk.Frame) -> None:
    bar, from_var, to_var = _date_bar(parent)
    ttk.Label(
        parent,
        text=("Voided rows are kept but count for nothing — the fact that "
              "somebody once recorded a mark is part of the story. Purge "
              "only under a retention policy; it is the one thing here "
              "that cannot be undone."),
        foreground="#666", wraplength=780, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    tree = _tree(parent, [
        ("id", "Rec", 60),
        ("date", "Date", 100),
        ("student", "Student", 120),
        ("was", "Was", 110),
        ("by", "Voided by", 120),
        ("reason", "Reason", 320),
    ])
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(6, 4))
    actions = ttk.Frame(parent)
    actions.pack(anchor="w")

    def refresh() -> None:
        tree.delete(*tree.get_children())
        try:
            rows = audit.list_voided(
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None)
        except ValidationError as e:
            summary.config(text=str(e), foreground="#a33")
            return
        for record in rows:
            tree.insert("", "end", values=(
                record.record_id, record.date, record.student_id,
                f"{record.status} [{record.code or '—'}]",
                record.voided_by or "—", record.void_reason or ""))
        summary.config(text=f"{len(rows)} voided row(s)", foreground="#555")

    def void() -> None:
        raw = simpledialog.askstring("Void a record", "Record ID:",
                                     parent=gui.root)
        if not raw or not raw.strip().isdigit():
            return
        reason = simpledialog.askstring(
            "Void a record", "Why is this being voided?", parent=gui.root)
        if not reason:
            messagebox.showinfo(
                "Reason required",
                "A void needs a reason — an unexplained one is "
                "indistinguishable from a cover-up.", parent=gui.root)
            return
        try:
            audit.void_record(int(raw.strip()), reason=reason,
                              actor=_actor(gui))
        except ValidationError as e:
            messagebox.showerror("Could not void", str(e), parent=gui.root)
            return
        refresh()

    def restore() -> None:
        record_id = _selected_id(tree, gui.root)
        if record_id is None:
            return
        try:
            audit.restore_record(record_id, actor=_actor(gui))
        except ValidationError as e:
            messagebox.showerror("Could not restore", str(e), parent=gui.root)
            return
        refresh()

    def purge() -> None:
        before = simpledialog.askstring(
            "Purge voided records",
            "Delete voided rows dated before (YYYY-MM-DD):", parent=gui.root)
        if not before:
            return
        try:
            preview = audit.purge_voided(before_date=before, dry_run=True)
        except ValidationError as e:
            messagebox.showerror("Invalid date", str(e), parent=gui.root)
            return
        if not preview.purged:
            messagebox.showinfo("Nothing to purge",
                                f"No voided rows before {before}.",
                                parent=gui.root)
            return
        if not messagebox.askyesno(
                "Purge voided records",
                f"Permanently delete {preview.purged} voided row(s) dated "
                f"before {before}?\n\nThis cannot be undone. The amendment "
                f"trail will keep a note that each one existed.",
                default="no", parent=gui.root):
            return
        audit.purge_voided(before_date=before, actor=_actor(gui))
        refresh()

    ttk.Button(bar, text="Show", command=refresh).pack(side="left")
    ttk.Button(actions, text="Void a record", command=void).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Restore", command=restore).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Purge…", command=purge).pack(
        side="left", padx=(0, 6))
    ttk.Button(actions, text="Refresh", command=refresh).pack(side="left")
    refresh()

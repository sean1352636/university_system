"""GUI panels for Sixth Form University Visits.

Four tabs:

* Directory  — filterable list of visits.
* Editor     — add / edit form with the full field set.
* Attendees  — pick a visit, manage the per-student attendee list.
* Summary    — counts by status / type / year group, plus upcoming alerts.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk

from education_system.sixthform_system.modules.domain.progression.university_visits import university_visits as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.progression.university_visits.university_visits import (
    DEFAULT_TRANSPORT,
    DEFAULT_VISIT_STATUS,
    DEFAULT_VISIT_TYPE,
    DEFAULT_YEAR_GROUP,
    TRANSPORT_MODES,
    UniversityVisit,
    VISIT_STATUSES,
    VISIT_TYPES,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


# ── Top-level tabbed view ───────────────────────────────────────────

_active_window: tk.Toplevel | None = None


def open_directory(gui) -> None:
    """Open the University Visits view in its own Toplevel window."""
    global _active_window
    # If already open, just raise it to the front instead of stacking copies.
    if _active_window is not None and _active_window.winfo_exists():
        try:
            _active_window.deiconify()
            _active_window.lift()
            _active_window.focus_force()
            return
        except tk.TclError:
            _active_window = None

    win = tk.Toplevel(gui.root)
    win.title("University Visits")
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    # Fit the screen with a small margin; cap to the project convention.
    w = min(1400, sw - 60)
    h = min(900,  sh - 100)  # leave room for taskbar / window decorations
    win.minsize(min(1200, w), min(800, h))
    win.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")

    def _on_close() -> None:
        global _active_window
        _active_window = None
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", _on_close)
    _active_window = win

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)
    _heading(frame, "University Visits")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    editor_tab = ttk.Frame(nb, padding=8)
    att_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(editor_tab,  text="Editor")
    nb.add(att_tab,     text="Attendees")
    nb.add(summary_tab, text="Summary")

    _build_directory_tab(gui, dir_tab)
    _build_editor_tab(gui, editor_tab)
    _build_attendees_tab(gui, att_tab)
    _build_summary_tab(gui, summary_tab)

    try:
        win.lift()
        win.focus_force()
    except tk.TclError:
        pass


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    uni_var = tk.StringVar()
    type_var = tk.StringVar()
    year_var = tk.StringVar()
    status_var = tk.StringVar()
    df_var = tk.StringVar()
    dt_var = tk.StringVar()

    ttk.Label(filt, text="University:").pack(side="left")
    ttk.Entry(filt, textvariable=uni_var, width=18
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Type:").pack(side="left")
    ttk.Combobox(filt, textvariable=type_var,
                 values=["", *VISIT_TYPES], state="readonly", width=18
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Year:").pack(side="left")
    ttk.Combobox(filt, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly", width=10
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *VISIT_STATUSES], state="readonly", width=12
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="From:").pack(side="left")
    ttk.Entry(filt, textvariable=df_var, width=12
              ).pack(side="left", padx=(4, 8))
    ttk.Label(filt, text="To:").pack(side="left")
    ttk.Entry(filt, textvariable=dt_var, width=12
              ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(parent)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        try:
            rows = data.list_visits_with_detail(
                university_like=uni_var.get().strip() or None,
                visit_type=type_var.get().strip() or None,
                year_group=year_var.get().strip() or None,
                status=status_var.get().strip() or None,
                date_from=df_var.get().strip() or None,
                date_to=dt_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("visit_id", "date", "university", "type",
                "year_group", "status", "attendees", "capacity")
        headings = {
            "visit_id":   ("#",          50),
            "date":       ("Date",       90),
            "university": ("University", 220),
            "type":       ("Type",       150),
            "year_group": ("Year",        80),
            "status":     ("Status",     100),
            "attendees":  ("Att.",        50),
            "capacity":   ("Cap.",        50),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                           command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for r in rows:
            v = r.visit
            tree.insert("", "end", iid=str(v.visit_id), values=(
                v.visit_id, v.visit_date, v.university_name,
                v.visit_type, v.year_group, v.status,
                r.attendee_count,
                "—" if v.capacity is None else v.capacity,
            ))
        summary.configure(text=f"{len(rows)} visit(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            vid = _selected()
            if vid is None:
                messagebox.showinfo("No selection",
                                    "Pick a visit first.",
                                    parent=gui.root)
            return vid

        def _edit() -> None:
            vid = _require()
            if vid is None:
                return
            open_editor(gui, visit_id=vid, on_saved=refresh)

        def _delete() -> None:
            vid = _require()
            if vid is None:
                return
            v = data.get_visit(vid)
            if v is None:
                return
            if not messagebox.askyesno(
                "Delete visit",
                f"Delete visit #{vid} ({v.university_name} — "
                f"{v.visit_date})?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_visit(vid)
            except Exception as e:
                logger.exception("delete_visit crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Open in editor",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_editor(gui, visit_id=None,
                                               on_saved=refresh)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"University visits: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (uni_var.set(""), type_var.set(""),
                                year_var.set(""), status_var.set(""),
                                df_var.set(""), dt_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Editor tab ─────────────────────────────────────────────────────

def _build_editor_tab(gui, parent: ttk.Frame) -> None:
    ttk.Label(
        parent,
        text=("Editing now opens in a separate window. "
              "Use Directory → New or Open in editor."),
        foreground="#555",
    ).pack(anchor="w", pady=8)
    ttk.Button(parent, text="New University Visit",
               command=lambda: open_editor(gui, visit_id=None)
               ).pack(anchor="w")


def open_editor(gui, *, visit_id: int | None,
                on_saved=None) -> None:
    """Open the visit editor in its own Toplevel window.

    ``on_saved`` is invoked after a successful save (e.g. to refresh
    the directory listing in the underlying notebook).
    """
    win = tk.Toplevel(gui.root)
    win.title(f"University Visit #{visit_id}"
              if visit_id else "New University Visit")
    win.transient(gui.root)

    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w = min(1100, sw - 80)
    h = min(780,  sh - 120)
    win.minsize(min(900, w), min(560, h))
    win.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")
    try:
        win.lift()
        win.focus_force()
    except tk.TclError:
        pass

    container = ttk.Frame(win, padding=12)
    container.pack(fill="both", expand=True)
    _heading(container,
             f"University Visit #{visit_id}"
             if visit_id else "New University Visit")
    _render_editor(gui, container, visit_id, window=win,
                   on_saved=on_saved)


def _render_editor(gui, parent: ttk.Frame, visit_id: int | None,
                   *, window=None, on_saved=None) -> None:
    existing = data.get_visit(visit_id) if visit_id else None

    # Action buttons at the top so they're always visible without scrolling.
    btns = ttk.Frame(parent)
    btns.pack(anchor="w", pady=(0, 8))

    form = ttk.Frame(parent)
    form.pack(anchor="w", fill="x", pady=(0, 8))
    form.columnconfigure(1, weight=1, minsize=320)

    uni_var = tk.StringVar(value=existing.university_name if existing else "")
    type_var = tk.StringVar(
        value=existing.visit_type if existing else DEFAULT_VISIT_TYPE)
    date_var = tk.StringVar(
        value=(existing.visit_date if existing
               else _date.today().isoformat()))
    dep_var = tk.StringVar(
        value=(existing.departure_time or "") if existing else "")
    ret_var = tk.StringVar(
        value=(existing.return_time or "") if existing else "")
    loc_var = tk.StringVar(
        value=(existing.location or "") if existing else "")
    year_var = tk.StringVar(
        value=existing.year_group if existing else DEFAULT_YEAR_GROUP)
    org_var = tk.StringVar(
        value=(existing.organiser_staff_id or "") if existing else "")
    tr_var = tk.StringVar(
        value=existing.transport if existing else DEFAULT_TRANSPORT)
    cost_var = tk.StringVar(
        value=(f"{existing.cost_per_student:.2f}" if existing else "0.00"))
    cap_var = tk.StringVar(
        value=(str(existing.capacity) if existing and existing.capacity
               else ""))
    status_var = tk.StringVar(
        value=existing.status if existing else DEFAULT_VISIT_STATUS)

    notes_text = tk.Text(form, height=3, width=60)
    if existing and existing.notes:
        notes_text.insert("1.0", existing.notes)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=2)
        widget.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "University *",
        ttk.Entry(form, textvariable=uni_var, width=42))
    row(1, "Visit type",
        ttk.Combobox(form, textvariable=type_var, values=list(VISIT_TYPES),
                     state="readonly", width=24))
    row(2, "Visit date * (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=date_var, width=14))
    row(3, "Departure time (HH:MM)",
        ttk.Entry(form, textvariable=dep_var, width=8))
    row(4, "Return time (HH:MM)",
        ttk.Entry(form, textvariable=ret_var, width=8))
    row(5, "Pick-up location",
        ttk.Entry(form, textvariable=loc_var, width=32))
    row(6, "Year group",
        ttk.Combobox(form, textvariable=year_var, values=list(YEAR_GROUPS),
                     state="readonly", width=12))
    row(7, "Organiser (staff ID)",
        ttk.Entry(form, textvariable=org_var, width=14))
    row(8, "Transport",
        ttk.Combobox(form, textvariable=tr_var,
                     values=list(TRANSPORT_MODES),
                     state="readonly", width=20))
    row(9, "Cost per student (£)",
        ttk.Entry(form, textvariable=cost_var, width=10))
    row(10, "Capacity",
        ttk.Entry(form, textvariable=cap_var, width=8))
    row(11, "Status",
        ttk.Combobox(form, textvariable=status_var,
                     values=list(VISIT_STATUSES),
                     state="readonly", width=14))
    row(12, "Notes", notes_text)

    def _save() -> None:
        payload = {
            "university_name":    uni_var.get(),
            "visit_type":         type_var.get(),
            "visit_date":         date_var.get(),
            "departure_time":     dep_var.get(),
            "return_time":        ret_var.get(),
            "location":           loc_var.get(),
            "year_group":         year_var.get(),
            "organiser_staff_id": org_var.get(),
            "transport":          tr_var.get(),
            "cost_per_student":   cost_var.get(),
            "capacity":           cap_var.get(),
            "status":             status_var.get(),
            "notes":              notes_text.get("1.0", "end").strip(),
        }
        try:
            if existing:
                data.update_visit(existing.visit_id, payload)
                vid = existing.visit_id
                msg = f"Updated visit #{vid}."
            else:
                v = data.create_visit(payload)
                vid = v.visit_id
                msg = f"Created visit #{vid}."
        except ValidationError as e:
            messagebox.showerror("Validation error", str(e),
                                 parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_visit crashed")
            messagebox.showerror("Error", f"Could not save: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set(msg)
        if on_saved is not None:
            try:
                on_saved()
            except Exception:
                logger.exception("on_saved callback crashed")
        if window is not None:
            window.destroy()

    ttk.Button(btns, text="Save", command=_save
               ).pack(side="left", padx=(0, 6))
    ttk.Button(btns, text="Cancel",
               command=(window.destroy if window is not None
                        else lambda: open_directory(gui))
               ).pack(side="left")

    if existing is not None:
        def _push() -> None:
            from education_system.sixthform_system.modules.domain.progression.university_visits import crm_link
            try:
                result = crm_link.push_visit_to_university_crm(
                    existing.visit_id)
            except crm_link.CrmLinkError as e:
                messagebox.showerror(
                    "Push failed",
                    f"Could not reach the university system:\n\n{e}",
                    parent=window or gui.root)
                return
            except Exception as e:
                logger.exception("CRM push crashed")
                messagebox.showerror(
                    "Push failed",
                    f"Unexpected error: {e}",
                    parent=window or gui.root)
                return
            skipped = (f"\n  Skipped: {len(result.skipped)}"
                       if result.skipped else "")
            messagebox.showinfo(
                "Pushed to university CRM",
                f"Tour #{result.campus_tour_id} synced.\n\n"
                f"  Prospects created : {result.prospects_created}\n"
                f"  Prospects reused  : {result.prospects_reused}\n"
                f"  Registrations new : {result.registrations_created}"
                f"{skipped}",
                parent=window or gui.root)
            gui.status_var.set(
                f"Pushed visit #{existing.visit_id} → campus_tour "
                f"#{result.campus_tour_id}")

        ttk.Button(btns, text="Push to University CRM", command=_push
                   ).pack(side="left", padx=(18, 0))
        if existing.campus_tour_id:
            ttk.Label(btns,
                      text=f"Linked: campus_tour #{existing.campus_tour_id}",
                      foreground="#555"
                      ).pack(side="left", padx=(12, 0))


# ─── Attendees tab ──────────────────────────────────────────────────

def _build_attendees_tab(gui, parent: ttk.Frame) -> None:
    visits = data.list_visits()
    if not visits:
        ttk.Label(parent,
                  text=("No university visits yet. "
                        "Add one in the Editor tab first."),
                  foreground="#555").pack(anchor="w", pady=8)
        return

    top = ttk.Frame(parent)
    top.pack(anchor="w", fill="x", pady=(0, 8))
    ttk.Label(top, text="Visit:").pack(side="left")

    labels = [f"#{v.visit_id} — {v.visit_date} {v.university_name}"
              for v in visits]
    label_to_id = {lbl: v.visit_id for lbl, v in zip(labels, visits)}
    pick_var = tk.StringVar(value=labels[0])
    ttk.Combobox(top, textvariable=pick_var, values=labels,
                 state="readonly", width=50
                 ).pack(side="left", padx=(4, 12))

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)

    def _refresh(*_a) -> None:
        for w in body.winfo_children():
            w.destroy()
        vid = label_to_id[pick_var.get()]
        v = data.get_visit(vid)
        if v is None:
            return
        attendees = data.list_attendees(vid)

        info = ttk.Frame(body)
        info.pack(anchor="w", fill="x", pady=(0, 8))
        cap_text = f"  Capacity: {v.capacity}" if v.capacity else ""
        ttk.Label(info,
                  text=f"  {len(attendees)} attendee(s){cap_text}",
                  foreground="#555").pack(side="left")

        cols = ("attendee_id", "student", "attended", "notes")
        tree = ttk.Treeview(body, columns=cols, show="headings", height=12)
        tree.heading("attendee_id", text="#")
        tree.heading("student",     text="Student")
        tree.heading("attended",    text="Attended")
        tree.heading("notes",       text="Notes")
        tree.column("attendee_id", width=50, anchor="w")
        tree.column("student",     width=120, anchor="w")
        tree.column("attended",    width=80,  anchor="center")
        tree.column("notes",       width=400, anchor="w")
        tree.pack(side="top", fill="both", expand=True)

        for a in attendees:
            tree.insert("", "end", iid=str(a.attendee_id), values=(
                a.attendee_id, a.student_id,
                "Yes" if a.attended else "No",
                a.notes or "",
            ))

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        actions = ttk.Frame(body)
        actions.pack(anchor="w", pady=(8, 0))

        def _add() -> None:
            students = student_data.list_students()
            if not students:
                messagebox.showinfo("No students",
                                    "There are no students to add.",
                                    parent=gui.root)
                return
            dlg = tk.Toplevel(gui.root)
            dlg.title("Add Attendee")
            dlg.transient(gui.root)
            dlg.grab_set()
            ttk.Label(dlg, text="Student:").grid(
                row=0, column=0, padx=8, pady=8, sticky="e")
            opts = [f"{s.student_id} — {s.full_name}" for s in students]
            opt_map = {opt: s.student_id for opt, s in zip(opts, students)}
            sv = tk.StringVar(value=opts[0])
            ttk.Combobox(dlg, textvariable=sv, values=opts,
                         state="readonly", width=38
                         ).grid(row=0, column=1, padx=8, pady=8, sticky="w")
            ttk.Label(dlg, text="Notes:").grid(
                row=1, column=0, padx=8, pady=4, sticky="e")
            nv = tk.StringVar()
            ttk.Entry(dlg, textvariable=nv, width=40
                      ).grid(row=1, column=1, padx=8, pady=4, sticky="w")

            def _ok() -> None:
                try:
                    data.add_attendee(vid, opt_map[sv.get()],
                                      notes=nv.get() or None)
                except ValidationError as e:
                    messagebox.showerror("Validation error", str(e),
                                         parent=dlg)
                    return
                dlg.destroy()
                _refresh()

            btn_row = ttk.Frame(dlg)
            btn_row.grid(row=2, column=0, columnspan=2, pady=8)
            ttk.Button(btn_row, text="Add", command=_ok
                       ).pack(side="left", padx=4)
            ttk.Button(btn_row, text="Cancel", command=dlg.destroy
                       ).pack(side="left", padx=4)

        def _toggle() -> None:
            aid = _selected()
            if aid is None:
                messagebox.showinfo("No selection",
                                    "Pick an attendee first.",
                                    parent=gui.root)
                return
            target = next((a for a in attendees if a.attendee_id == aid), None)
            if target is None:
                return
            data.set_attendance(aid, not target.attended)
            _refresh()

        def _remove() -> None:
            aid = _selected()
            if aid is None:
                messagebox.showinfo("No selection",
                                    "Pick an attendee first.",
                                    parent=gui.root)
                return
            if not messagebox.askyesno(
                "Remove attendee",
                f"Remove attendee #{aid} from visit #{vid}?",
                parent=gui.root,
            ):
                return
            data.remove_attendee(aid)
            _refresh()

        ttk.Button(actions, text="Add attendee", command=_add
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Toggle attended", command=_toggle
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Remove", command=_remove
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Refresh", command=_refresh
                   ).pack(side="left", padx=(12, 0))

    pick_var.trace_add("write", _refresh)
    _refresh()


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    window_var = tk.StringVar(value="30")

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 8))
    ttk.Label(bar, text="Upcoming window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=window_var, width=6
              ).pack(side="left", padx=(4, 12))

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)

    def _refresh() -> None:
        for w in body.winfo_children():
            w.destroy()
        try:
            window = int(window_var.get() or "30")
        except ValueError:
            window = 30
        s = data.summary(upcoming_window_days=window)

        head = ttk.Frame(body)
        head.pack(anchor="w", fill="x", pady=(0, 8))
        for label, value in [
            ("Total visits",      s.total_visits),
            ("Total attendees",   s.total_attendees),
            ("Students attended", s.students_attended),
            (f"Upcoming ({window}d)",  s.upcoming_visits),
        ]:
            cell = ttk.Frame(head, padding=8)
            cell.pack(side="left", padx=(0, 12))
            ttk.Label(cell, text=label, foreground="#555"
                      ).pack(anchor="w")
            ttk.Label(cell, text=str(value),
                      font=("", 14, "bold")).pack(anchor="w")

        def _table(title: str, counts: dict, keys) -> None:
            box = ttk.LabelFrame(body, text=title, padding=8)
            box.pack(anchor="w", fill="x", pady=(0, 8))
            for i, k in enumerate(keys):
                ttk.Label(box, text=k).grid(
                    row=i, column=0, sticky="w", padx=(0, 16))
                ttk.Label(box, text=str(counts.get(k, 0))).grid(
                    row=i, column=1, sticky="w")

        _table("By status", s.by_status, list(VISIT_STATUSES))
        _table("By type",   s.by_type,   list(VISIT_TYPES))
        _table("By year group", s.by_year_group, list(YEAR_GROUPS))

    ttk.Button(bar, text="Refresh", command=_refresh
               ).pack(side="left")
    _refresh()

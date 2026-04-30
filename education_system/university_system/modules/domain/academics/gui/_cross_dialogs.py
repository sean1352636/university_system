"""Reusable Tk dialogs for the cross-GUI services.

Each helper renders one of the views in ``_cross_services.py`` so a
caller can wire a button without rebuilding the dialog every time.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.academics.gui._cross_services import (
    find_conflicts_for_module,
    find_conflicts_for_course,
    instructor_workload,
    list_instructors,
    at_risk_students_unified,
    module_timeline,
)


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------

def show_conflicts_dialog(parent: tk.Misc, *,
                          module_code: str | None = None,
                          course_code: str | None = None,
                          title: str | None = None) -> None:
    """Render the conflict report scoped to a module or course."""
    if module_code:
        rows = find_conflicts_for_module(module_code)
        scope = f"module {module_code}"
    elif course_code:
        rows = find_conflicts_for_course(course_code)
        scope = f"course {course_code}"
    else:
        messagebox.showinfo("Conflicts", "No module or course supplied.")
        return

    win = tk.Toplevel(parent)
    win.title(title or f"Schedule conflicts — {scope}")
    win.geometry("760x420")
    ttk.Label(
        win,
        text=f"Conflicts touching {scope}",
        font=("Helvetica", 12, "bold"),
    ).pack(anchor="w", padx=15, pady=(15, 5))

    if not rows:
        ttk.Label(
            win, text="No conflicts detected.",
            foreground="#27ae60",
        ).pack(padx=15, pady=20)
    else:
        cols = ("type", "severity", "description")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, w in zip(cols, (140, 90, 480)):
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=w, anchor="w")
        for r in rows:
            tree.insert("", "end", values=(
                r.get("type", ""), r.get("severity", ""), r.get("description", ""),
            ))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))


# ---------------------------------------------------------------------------
# Instructor workload
# ---------------------------------------------------------------------------

def show_instructor_workload_dialog(parent: tk.Misc,
                                    instructor_id: int | None = None) -> None:
    """Workload-for-instructor dialog — picker on top, details below."""
    win = tk.Toplevel(parent)
    win.title("Instructor Workload")
    win.geometry("780x540")

    top = ttk.Frame(win, padding=(15, 15, 15, 5))
    top.pack(fill="x")
    ttk.Label(top, text="Instructor:").pack(side="left")
    var = tk.StringVar()
    rows = list_instructors()
    items = {r["label"]: r["id"] for r in rows}
    combo = ttk.Combobox(top, textvariable=var, values=list(items),
                         state="readonly", width=55)
    combo.pack(side="left", padx=(8, 0))
    if rows:
        combo.current(0)

    body = ttk.Frame(win, padding=15)
    body.pack(fill="both", expand=True)
    summary_var = tk.StringVar(value="Pick an instructor to view workload.")
    ttk.Label(body, textvariable=summary_var, font=("Helvetica", 11)).pack(
        anchor="w", pady=(0, 8))

    notebook = ttk.Notebook(body)
    notebook.pack(fill="both", expand=True)

    slots_tab = ttk.Frame(notebook)
    notebook.add(slots_tab, text="Teaching slots")
    slots_cols = ("module_code", "day_of_week", "start_time", "end_time", "room")
    slots_tree = ttk.Treeview(slots_tab, columns=slots_cols, show="headings")
    for c, w in zip(slots_cols, (110, 110, 90, 90, 200)):
        slots_tree.heading(c, text=c.replace("_", " ").title())
        slots_tree.column(c, width=w, anchor="w")
    slots_tree.pack(fill="both", expand=True)

    panels_tab = ttk.Frame(notebook)
    notebook.add(panels_tab, text="Examiner panels")
    panel_cols = ("exam_id", "module_code", "role")
    panels_tree = ttk.Treeview(panels_tab, columns=panel_cols, show="headings")
    for c, w in zip(panel_cols, (90, 130, 160)):
        panels_tree.heading(c, text=c.replace("_", " ").title())
        panels_tree.column(c, width=w, anchor="w")
    panels_tree.pack(fill="both", expand=True)

    def reload(*_):
        instr_id = items.get(var.get())
        if not instr_id:
            return
        data = instructor_workload(instructor_id=int(instr_id))
        info = data["instructor"]
        totals = data["totals"]
        summary_var.set(
            f"{info['name']}  ·  {info['department'] or '—'}  ·  "
            f"{totals['teaching_hours_per_week']}h/week across "
            f"{totals['slot_count']} slots in {totals['modules']} modules  ·  "
            f"{totals['exam_panels']} exam panel(s)  ·  "
            f"{data['recent_grades']} grades entered (30d)"
        )
        for tree in (slots_tree, panels_tree):
            for i in tree.get_children():
                tree.delete(i)
        for s in data["teaching_slots"]:
            slots_tree.insert("", "end", values=tuple(s.get(c, "") for c in slots_cols))
        for p in data["examiner_assignments"]:
            panels_tree.insert("", "end", values=tuple(p.get(c, "") for c in panel_cols))

    combo.bind("<<ComboboxSelected>>", reload)
    if instructor_id is not None:
        for label, iid in items.items():
            if int(iid) == int(instructor_id):
                var.set(label)
                break
    reload()
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))


# ---------------------------------------------------------------------------
# Unified at-risk list (Grade Tracking → Exam Scheduler)
# ---------------------------------------------------------------------------

def show_at_risk_dialog(parent: tk.Misc, *,
                        module_code: str | None = None,
                        threshold: int = 30) -> None:
    rows = at_risk_students_unified(module_code=module_code, threshold=threshold)
    win = tk.Toplevel(parent)
    title = "At-risk (unified)" + (f" — {module_code}" if module_code else "")
    win.title(title)
    win.geometry("820x420")
    ttk.Label(
        win,
        text=f"Students flagged ≥ {threshold} risk score "
             f"by Grade Tracking{' for ' + module_code if module_code else ''}",
        font=("Helvetica", 11, "bold"),
    ).pack(anchor="w", padx=15, pady=(15, 5))
    if not rows:
        ttk.Label(
            win, text="No students currently flagged at this threshold.",
            foreground="#27ae60",
        ).pack(padx=15, pady=20)
    else:
        cols = ("student_id", "name", "course", "risk_score", "severity",
                "detected_at", "notes")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, w in zip(cols, (90, 180, 80, 90, 80, 150, 200)):
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=w, anchor="w")
        for r in rows:
            tree.insert("", "end", values=tuple(str(r.get(c, "")) for c in cols))
        tree.pack(fill="both", expand=True, padx=10, pady=10)
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))


# ---------------------------------------------------------------------------
# Module timeline
# ---------------------------------------------------------------------------

def show_module_timeline_dialog(parent: tk.Misc, module_code: str) -> None:
    rows = module_timeline(module_code)
    win = tk.Toplevel(parent)
    win.title(f"Module timeline — {module_code}")
    win.geometry("820x500")
    ttk.Label(
        win,
        text=f"All scheduled events for {module_code}",
        font=("Helvetica", 12, "bold"),
    ).pack(anchor="w", padx=15, pady=(15, 5))

    if not rows:
        ttk.Label(
            win, text="No events recorded for this module.",
            foreground="#7f8c8d",
        ).pack(padx=15, pady=20)
    else:
        cols = ("kind", "date", "label", "detail")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, w in zip(cols, (90, 110, 280, 320)):
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=w, anchor="w")
        for r in rows:
            tree.insert("", "end", values=tuple(r.get(c, "") for c in cols))
        tree.pack(fill="both", expand=True, padx=10, pady=10)
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))


class ModuleTimelinePanel(ttk.Frame):
    """Embeddable inline panel showing the timeline for one module.

    Use as a child widget anywhere a host GUI wants to show "what's
    happening for this module" without popping a dialog. Call
    :meth:`set_module` to retarget; refreshes auto-subscribe to the
    relevant bus events when the host root is provided.
    """

    def __init__(self, master: tk.Misc, module_code: str | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._module_code: str | None = None

        self._heading_var = tk.StringVar(value="Module timeline")
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("kind", "date", "label", "detail")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (80, 100, 240, 280)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._empty_var = tk.StringVar(value="")
        self._empty_label = ttk.Label(
            self, textvariable=self._empty_var, foreground="#7f8c8d",
        )
        self._empty_label.pack(anchor="w", padx=10)

        if listen_to_events:
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    subscribe_tk,
                    EVENT_MODULE_SCHEDULE_CHANGED,
                    EVENT_EXAM_CHANGED,
                    EVENT_ASSESSMENT_CHANGED,
                    EVENT_ASSIGNMENT_CHANGED,
                )

                def _on_change(**_payload):
                    if self._module_code:
                        self.refresh()

                for evt in (EVENT_MODULE_SCHEDULE_CHANGED, EVENT_EXAM_CHANGED,
                            EVENT_ASSESSMENT_CHANGED, EVENT_ASSIGNMENT_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                pass

        if module_code:
            self.set_module(module_code)

    def set_module(self, module_code: str) -> None:
        self._module_code = module_code or None
        self._heading_var.set(
            f"Module timeline — {module_code}" if module_code
            else "Module timeline"
        )
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._module_code:
            self._empty_var.set("No module selected.")
            return
        rows = module_timeline(self._module_code)
        if not rows:
            self._empty_var.set("No events recorded for this module.")
            return
        self._empty_var.set("")
        cols = ("kind", "date", "label", "detail")
        for r in rows:
            self._tree.insert("", "end", values=tuple(r.get(c, "") for c in cols))


class StudentFinancePanel(ttk.Frame):
    """Inline summary of a student's balance + active holds.

    Embed in the enrolment dialog (Course/Module GUI), the resit
    confirmation (Exam GUI), or the library checkout screen so the
    operator sees money state without context-switching.

    Auto-refreshes on ``finance.charge.raised`` and ``finance.hold.changed``.
    """

    def __init__(self, master: tk.Misc, student_id: str | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._student_id: str | None = None

        self._heading_var = tk.StringVar(value="Finance: —")
        self._balance_var = tk.StringVar(value="Balance: —")
        self._hold_var = tk.StringVar(value="Holds: —")

        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))
        ttk.Label(self, textvariable=self._balance_var).pack(anchor="w", padx=10)
        self._hold_label = ttk.Label(self, textvariable=self._hold_var)
        self._hold_label.pack(anchor="w", padx=10, pady=(0, 6))

        cols = ("source", "reason", "amount")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=4)
        for c, w in zip(cols, (110, 320, 90)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="x", expand=False, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    subscribe_tk, EVENT_CHARGE_RAISED, EVENT_HOLD_CHANGED,
                )

                def _on_change(**payload):
                    if (self._student_id and
                            str(payload.get("student_id") or "") in ("", str(self._student_id))):
                        self.refresh()

                for evt in (EVENT_CHARGE_RAISED, EVENT_HOLD_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                pass

        if student_id:
            self.set_student(student_id)

    def set_student(self, student_id: str) -> None:
        self._student_id = str(student_id) if student_id else None
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._student_id:
            self._heading_var.set("Finance: —")
            self._balance_var.set("Balance: —")
            self._hold_var.set("Holds: —")
            return
        self._heading_var.set(f"Finance — student {self._student_id}")

        try:
            from education_system.university_system.modules.services.finance_bus import (
                student_balance, list_active_holds,
            )
            balance = student_balance(self._student_id)
            holds = list_active_holds(self._student_id)
        except Exception:
            balance, holds = 0.0, []

        self._balance_var.set(f"Balance: £{balance:,.2f}")
        if holds:
            self._hold_var.set(f"⚠ {len(holds)} active hold(s)")
            self._hold_label.configure(foreground="#c0392b")
        else:
            self._hold_var.set("✓ No active holds")
            self._hold_label.configure(foreground="#27ae60")

        for h in holds:
            self._tree.insert("", "end", values=(
                h.get("source", ""), h.get("reason", ""),
                f"£{float(h.get('amount') or 0):,.2f}",
            ))


class ResourceAvailabilityPanel(ttk.Frame):
    """Shows library availability for a textbook ISBN or a module's reading list.

    Pass ``isbn=`` for a single title, or ``module_code=`` to walk the
    module's textbook list. Auto-refreshes on ``library.loan.changed``
    and ``library.reading_list.changed``.
    """

    def __init__(self, master: tk.Misc, *,
                 isbn: str | None = None,
                 module_code: str | None = None,
                 listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._isbn: str | None = None
        self._module_code: str | None = None

        self._heading_var = tk.StringVar(value="Library availability")
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("title", "author", "on_loan", "available")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (260, 160, 80, 80)):
            self._tree.heading(c, text=c.replace("_", " ").capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._empty_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self._empty_var, foreground="#7f8c8d",
        ).pack(anchor="w", padx=10)

        if listen_to_events:
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    subscribe_tk, EVENT_LOAN_CHANGED, EVENT_READING_LIST_CHANGED,
                )

                def _on_change(**_payload):
                    if self._isbn or self._module_code:
                        self.refresh()

                for evt in (EVENT_LOAN_CHANGED, EVENT_READING_LIST_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                pass

        if isbn or module_code:
            self.set_target(isbn=isbn, module_code=module_code)

    def set_target(self, *, isbn: str | None = None,
                   module_code: str | None = None) -> None:
        self._isbn = isbn or None
        self._module_code = module_code or None
        if self._isbn:
            self._heading_var.set(f"Library availability — ISBN {self._isbn}")
        elif self._module_code:
            self._heading_var.set(
                f"Library availability — reading list for {self._module_code}"
            )
        else:
            self._heading_var.set("Library availability")
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._empty_var.set("")

        rows: list[tuple[str, str, int, int]] = []
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                if self._module_code:
                    books = conn.execute(
                        "SELECT isbn, title, author FROM textbooks "
                        "WHERE module_code = ? ORDER BY required DESC, title",
                        (self._module_code,),
                    ).fetchall()
                elif self._isbn:
                    books = conn.execute(
                        "SELECT isbn, title, author FROM textbooks "
                        "WHERE isbn = ? LIMIT 1",
                        (self._isbn,),
                    ).fetchall()
                else:
                    books = []

                for b in books:
                    isbn = b["isbn"]
                    on_loan_row = conn.execute(
                        "SELECT COUNT(*) FROM book_loans bl "
                        "JOIN books bk ON bl.book_id = bk.book_id "
                        "WHERE bk.isbn = ? AND bl.return_date IS NULL",
                        (isbn,),
                    ).fetchone() if isbn else None
                    on_loan = int(on_loan_row[0] or 0) if on_loan_row else 0
                    total_row = conn.execute(
                        "SELECT COUNT(*) FROM books WHERE isbn = ?",
                        (isbn,),
                    ).fetchone() if isbn else None
                    total = int(total_row[0] or 0) if total_row else 0
                    rows.append((
                        b["title"] or "—",
                        b["author"] or "—",
                        on_loan,
                        max(0, total - on_loan),
                    ))
        except Exception as exc:
            self._empty_var.set(f"(unavailable: {exc})")
            return

        if not rows:
            self._empty_var.set("No reading-list titles found.")
            return
        for title, author, on_loan, available in rows:
            self._tree.insert("", "end", values=(title, author, on_loan, available))


class ResearchOutputPanel(ttk.Frame):
    """Recent publications for an instructor or for a module's PI.

    Embed in the Course/Module detail page so a student sees the
    research-led context, or in the Library to inform journal
    subscription decisions.
    """

    def __init__(self, master: tk.Misc, *,
                 instructor_id: int | str | None = None,
                 module_code: str | None = None,
                 limit: int = 10) -> None:
        super().__init__(master)
        self._instructor_id = instructor_id
        self._module_code = module_code
        self._limit = limit

        self._heading_var = tk.StringVar(value="Recent research outputs")
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("year", "title", "venue")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (60, 360, 200)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._empty_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self._empty_var, foreground="#7f8c8d",
        ).pack(anchor="w", padx=10)

        if instructor_id or module_code:
            self.refresh()

    def set_target(self, *, instructor_id: int | str | None = None,
                   module_code: str | None = None) -> None:
        self._instructor_id = instructor_id
        self._module_code = module_code
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._empty_var.set("")

        instr = self._instructor_id
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                # Resolve instructor from module if needed.
                if instr is None and self._module_code:
                    row = conn.execute(
                        "SELECT instructor_id FROM module_schedule "
                        "WHERE module_code = ? "
                        "  AND instructor_id IS NOT NULL "
                        "ORDER BY rowid DESC LIMIT 1",
                        (self._module_code,),
                    ).fetchone()
                    if row:
                        instr = row[0]

                if instr is None:
                    self._empty_var.set("No instructor / module supplied.")
                    return

                self._heading_var.set(f"Recent research — instructor {instr}")
                rows = conn.execute(
                    "SELECT publication_date, title, "
                    "       COALESCE(journal_name, conference_name, '') AS venue "
                    "FROM research_publications rp "
                    "JOIN research_projects pr ON rp.project_id = pr.project_id "
                    "WHERE pr.principal_investigator_id = ? "
                    "ORDER BY publication_date DESC LIMIT ?",
                    (instr, self._limit),
                ).fetchall()
        except Exception as exc:
            self._empty_var.set(f"(unavailable: {exc})")
            return

        if not rows:
            self._empty_var.set("No publications recorded.")
            return
        for r in rows:
            year = (r["publication_date"] or "")[:4]
            self._tree.insert("", "end", values=(
                year, r["title"] or "—", r["venue"] or "",
            ))


_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
_DEFAULT_TIME_SLOTS = (
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00",
)


class WeeklyGridPanel(ttk.Frame):
    """Embeddable weekly timetable grid.

    Single read-side widget for *every* timetable surface — the
    Student Timetable, the per-module detail in Module Scheduling,
    the per-course detail in Course Management, and the per-instructor
    drill-down. The host picks a ``scope`` and the panel queries the
    right slice; the rendering and refresh wiring is identical.

    Scopes:
      * ``scope='module'``     + ``scope_id='CS101'``
      * ``scope='course'``     + ``scope_id='CS-BSC'``
      * ``scope='instructor'`` + ``scope_id=42``
      * ``scope='student'``    + ``scope_id='S12345'``

    Auto-refreshes on ``module.schedule.changed`` / ``exam.changed`` /
    ``enrolment.changed`` / ``calendar.changed`` / ``term.changed``.

    Cells are click-aware: clicking publishes a soft
    ``selection.changed`` so sibling GUIs can highlight the row.
    Cells with an unresolved schedule conflict get a red ribbon.
    Exams are overlaid in orange so you can see lectures + exams in
    a single view.
    """

    _LECTURE_BG = "#d4edda"
    _LECTURE_FG = "#155724"
    _EXAM_BG = "#fde2c4"
    _EXAM_FG = "#7a3e00"
    _CONFLICT_BORDER = "#c0392b"
    _EMPTY_BG = "#ffffff"

    def __init__(self, master: tk.Misc, *,
                 scope: str = "module",
                 scope_id: Any = None,
                 listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._scope = scope
        self._scope_id = scope_id
        self._cells: dict[tuple[int, int], tk.Frame] = {}
        self._heading_var = tk.StringVar(value="Weekly timetable")

        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self._grid_frame = ttk.Frame(self)
        self._grid_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_grid()

        self._status_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self._status_var, foreground="#7f8c8d",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        if listen_to_events:
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    subscribe_tk,
                    EVENT_MODULE_SCHEDULE_CHANGED,
                    EVENT_EXAM_CHANGED,
                    EVENT_ENROLMENT_CHANGED,
                    EVENT_CALENDAR_CHANGED,
                    EVENT_TERM_CHANGED,
                )

                def _on_change(**_payload):
                    if self._scope_id is not None:
                        self.refresh()

                for evt in (EVENT_MODULE_SCHEDULE_CHANGED, EVENT_EXAM_CHANGED,
                            EVENT_ENROLMENT_CHANGED, EVENT_CALENDAR_CHANGED,
                            EVENT_TERM_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                pass

        if scope_id is not None:
            self.refresh()

    # ------------------------------------------------------------------ #

    def _build_grid(self) -> None:
        # Top-left corner.
        tk.Label(
            self._grid_frame, text="Time", width=8,
            font=("Helvetica", 9, "bold"), bg="#4a90e2", fg="white",
            relief="ridge",
        ).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        # Day headers.
        for c, day in enumerate(_WEEKDAYS, start=1):
            tk.Label(
                self._grid_frame, text=day[:3], width=14,
                font=("Helvetica", 9, "bold"), bg="#4a90e2", fg="white",
                relief="ridge",
            ).grid(row=0, column=c, sticky="nsew", padx=1, pady=1)
        # Time rows.
        for r, slot in enumerate(_DEFAULT_TIME_SLOTS, start=1):
            tk.Label(
                self._grid_frame, text=slot, width=8,
                font=("Helvetica", 9, "bold"), bg="#e8f4f8",
                relief="ridge",
            ).grid(row=r, column=0, sticky="nsew", padx=1, pady=1)
            for c in range(1, len(_WEEKDAYS) + 1):
                cell = tk.Frame(
                    self._grid_frame, bg=self._EMPTY_BG,
                    relief="ridge", borderwidth=1,
                    width=140, height=60,
                )
                cell.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                cell.grid_propagate(False)
                self._cells[(c - 1, r - 1)] = cell

        for c in range(len(_WEEKDAYS) + 1):
            self._grid_frame.columnconfigure(c, weight=1)

    def set_target(self, *, scope: str, scope_id: Any) -> None:
        self._scope = scope
        self._scope_id = scope_id
        self.refresh()

    def refresh(self) -> None:
        self._clear_cells()
        if self._scope_id is None:
            self._heading_var.set("Weekly timetable")
            self._status_var.set("No target selected.")
            return
        self._heading_var.set(
            f"Weekly timetable — {self._scope}: {self._scope_id}"
        )

        try:
            lecture_rows, exam_rows = self._load_rows()
        except Exception as exc:
            self._status_var.set(f"(load failed: {exc})")
            return

        if not lecture_rows and not exam_rows:
            self._status_var.set("No scheduled sessions.")
            return
        self._status_var.set(
            f"{len(lecture_rows)} lecture slots · {len(exam_rows)} exam(s)"
        )

        # Conflict overlay — set of module codes that appear in
        # unresolved conflicts. Cell ribbons are rendered for these.
        try:
            from education_system.university_system.modules.domain.academics.gui._cross_services import (
                _all_conflicts,
            )
            conflict_codes = set()
            for c in _all_conflicts():
                desc = (c.get("description") or "").lower()
                for code in {r["module_code"].lower() for r in lecture_rows
                             if r.get("module_code")}:
                    if code in desc:
                        conflict_codes.add(code)
        except Exception:
            conflict_codes = set()

        for row in lecture_rows:
            self._draw_cell(row, kind="lecture", conflict_codes=conflict_codes)
        for row in exam_rows:
            self._draw_cell(row, kind="exam", conflict_codes=conflict_codes)

    # ------------------------------------------------------------------ #

    def _load_rows(self) -> tuple[list[dict], list[dict]]:
        from education_system.university_system.infrastructure.database.db import get_connection
        lecture_rows: list[dict] = []
        exam_rows: list[dict] = []
        with get_connection() as conn:
            modules = self._modules_in_scope(conn)
            if not modules:
                return [], []
            placeholders = ",".join("?" for _ in modules)

            for r in conn.execute(
                f"""
                SELECT ms.id, ms.module_code, ms.day_of_week,
                       ms.start_time, ms.end_time,
                       COALESCE(ms.session_type, 'lecture') AS session_type,
                       COALESCE(r.building || ' ' || r.room_number, '') AS room
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                WHERE ms.module_code IN ({placeholders})
                ORDER BY ms.day_of_week, ms.start_time
                """,
                modules,
            ).fetchall():
                lecture_rows.append(dict(r))

            try:
                for r in conn.execute(
                    f"""
                    SELECT id, module_code, date, start_time, end_time, room
                    FROM exams WHERE module_code IN ({placeholders})
                    ORDER BY date, start_time
                    """,
                    modules,
                ).fetchall():
                    exam_rows.append(dict(r))
            except Exception:
                pass
        return lecture_rows, exam_rows

    def _modules_in_scope(self, conn) -> list[str]:
        sid = self._scope_id
        if self._scope == "module":
            return [str(sid)]
        if self._scope == "course":
            try:
                rows = conn.execute(
                    "SELECT module_code FROM modules WHERE course = ?",
                    (str(sid),),
                ).fetchall()
                return [r[0] for r in rows]
            except Exception:
                return []
        if self._scope == "instructor":
            try:
                rows = conn.execute(
                    "SELECT DISTINCT module_code FROM module_schedule "
                    "WHERE instructor_id = ?",
                    (sid,),
                ).fetchall()
                return [r[0] for r in rows]
            except Exception:
                return []
        if self._scope == "student":
            try:
                rows = conn.execute(
                    "SELECT module_code FROM student_modules "
                    "WHERE student_id = ? AND LOWER(status) = 'enrolled'",
                    (str(sid),),
                ).fetchall()
                return [r[0] for r in rows]
            except Exception:
                return []
        return []

    # ------------------------------------------------------------------ #

    def _clear_cells(self) -> None:
        for cell in self._cells.values():
            cell.configure(bg=self._EMPTY_BG, highlightthickness=0)
            for child in cell.winfo_children():
                child.destroy()

    def _slot_index(self, t: str) -> int | None:
        if not t or len(t) < 5:
            return None
        head = t[:5]
        try:
            return _DEFAULT_TIME_SLOTS.index(head)
        except ValueError:
            # Map to the nearest hour bucket.
            try:
                hour = int(t[:2])
                for i, slot in enumerate(_DEFAULT_TIME_SLOTS):
                    if int(slot[:2]) == hour:
                        return i
            except Exception:
                return None
        return None

    def _day_index(self, day: str) -> int | None:
        if not day:
            return None
        for i, d in enumerate(_WEEKDAYS):
            if day.strip().lower().startswith(d[:3].lower()):
                return i
        return None

    def _draw_cell(self, row: dict, *, kind: str,
                   conflict_codes: set[str]) -> None:
        if kind == "lecture":
            d_idx = self._day_index(row.get("day_of_week", ""))
        else:
            try:
                from datetime import datetime as _dt
                day_name = _dt.strptime(
                    (row.get("date") or "")[:10], "%Y-%m-%d"
                ).strftime("%A")
                d_idx = self._day_index(day_name)
            except Exception:
                d_idx = None
        s_idx = self._slot_index(row.get("start_time") or "")
        if d_idx is None or s_idx is None:
            return
        cell = self._cells.get((d_idx, s_idx))
        if cell is None:
            return

        bg, fg = (self._LECTURE_BG, self._LECTURE_FG) if kind == "lecture" \
            else (self._EXAM_BG, self._EXAM_FG)
        cell.configure(bg=bg)
        if (row.get("module_code") or "").lower() in conflict_codes:
            cell.configure(highlightthickness=2,
                           highlightbackground=self._CONFLICT_BORDER)

        prefix = "EXAM " if kind == "exam" else ""
        label = tk.Label(
            cell,
            text=f"{prefix}{row.get('module_code', '')}\n{row.get('room') or ''}",
            bg=bg, fg=fg, font=("Helvetica", 8, "bold"),
            wraplength=130, anchor="center", justify="center",
        )
        label.pack(fill="both", expand=True, padx=2, pady=2)

        # Click → soft selection broadcast.
        module_code = row.get("module_code")
        kind_local = kind

        def _on_click(_event=None, mc=module_code, k=kind_local):
            try:
                from education_system.university_system.modules.services.academic_state import (
                    set_current_selection,
                )
                set_current_selection(module_code=mc, source=f"timetable_{k}")
            except Exception:
                pass

        for w in (cell, label):
            w.bind("<Button-1>", _on_click)


class StaffWorkloadPanel(ttk.Frame):
    """Inline summary of one staff member's teaching load.

    Wraps the existing ``instructor_workload`` cross-service so HR
    can drop it into the staff detail page, and Module Scheduling
    can drop it into the instructor-edit dialog. Auto-refreshes on
    ``hr.staff_availability.changed`` / ``module.schedule.changed``.
    """

    def __init__(self, master: tk.Misc,
                 instructor_id: int | str | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._instructor_id: int | str | None = None

        self._heading_var = tk.StringVar(value="Staff workload")
        self._totals_var = tk.StringVar(value="—")
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))
        ttk.Label(self, textvariable=self._totals_var).pack(
            anchor="w", padx=10, pady=(0, 4),
        )

        cols = ("module", "day", "time", "room")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (90, 90, 110, 130)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    subscribe_tk,
                    EVENT_STAFF_AVAILABILITY_CHANGED,
                    EVENT_MODULE_SCHEDULE_CHANGED,
                )

                def _on_change(**_payload):
                    if self._instructor_id is not None:
                        self.refresh()

                for evt in (EVENT_STAFF_AVAILABILITY_CHANGED,
                            EVENT_MODULE_SCHEDULE_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                pass

        if instructor_id is not None:
            self.set_instructor(instructor_id)

    def set_instructor(self, instructor_id: int | str) -> None:
        self._instructor_id = instructor_id
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if self._instructor_id is None:
            self._heading_var.set("Staff workload")
            self._totals_var.set("—")
            return
        try:
            from education_system.university_system.modules.domain.academics.gui._cross_services import (
                instructor_workload,
            )
            data = instructor_workload(instructor_id=int(self._instructor_id))
        except Exception:
            data = None
        if not data:
            self._totals_var.set("(unavailable)")
            return
        info = data.get("instructor", {})
        totals = data.get("totals", {})
        self._heading_var.set(
            f"Staff workload — {info.get('name') or self._instructor_id}"
        )
        self._totals_var.set(
            f"{totals.get('teaching_hours_per_week', 0):.1f} h/wk · "
            f"{totals.get('slot_count', 0)} slots · "
            f"{totals.get('modules', 0)} modules · "
            f"{totals.get('exam_panels', 0)} exam panels"
        )
        for s in data.get("teaching_slots", []):
            self._tree.insert("", "end", values=(
                s.get("module_code") or "",
                s.get("day_of_week") or "",
                f"{s.get('start_time') or ''}–{s.get('end_time') or ''}",
                s.get("room") or "",
            ))


class AcademicPeriodPanel(ttk.Frame):
    """Compact strip showing the current term + calendar context.

    Embed at the top of every scheduling GUI so the operator sees
    "Term: Spring 2026 · Week 7 · Exam window opens 12 May" without
    scrolling to find it. Refreshes on ``calendar.changed`` and
    ``term.changed``.
    """

    def __init__(self, master: tk.Misc, *,
                 listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._line_var = tk.StringVar(value="—")
        self._lbl = ttk.Label(
            self, textvariable=self._line_var,
            font=("Helvetica", 10, "bold"),
            foreground="#2c3e50",
        )
        self._lbl.pack(anchor="w", padx=8, pady=4)

        if listen_to_events:
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    subscribe_tk, EVENT_CALENDAR_CHANGED, EVENT_TERM_CHANGED,
                )
                subscribe_tk(EVENT_CALENDAR_CHANGED, self, lambda **_: self.refresh())
                subscribe_tk(EVENT_TERM_CHANGED, self, lambda **_: self.refresh())
            except Exception:
                pass

        self.refresh()

    def refresh(self) -> None:
        bits: list[str] = []
        try:
            from education_system.university_system.modules.services.academic_state import (
                get_current_term,
            )
            term = get_current_term()
            if term is not None:
                bits.append(f"Term: {term.label()}")
        except Exception:
            pass

        try:
            from education_system.university_system.modules.domain.academics.gui._cross_services import (
                current_period, is_holiday,
            )
            from datetime import date as _date
            today = _date.today().isoformat()
            term_p = current_period("term", on_date=today)
            if term_p:
                # Compute a rough week-of-term number for the operator.
                start = (term_p.get("date_start") or "")[:10]
                if start:
                    try:
                        delta = (_date.fromisoformat(today)
                                 - _date.fromisoformat(start)).days
                        bits.append(f"Week {max(1, delta // 7 + 1)}")
                    except Exception:
                        pass
            if is_holiday(today):
                bits.append("⚠ holiday today")
            exam_p = current_period("exam_window", on_date=today)
            if exam_p:
                bits.append(f"exam window open (until {exam_p.get('date_end','')})")
            else:
                # Look ahead 60 days for the next exam window.
                try:
                    from datetime import timedelta as _td
                    for ahead in range(1, 61):
                        d = (_date.fromisoformat(today)
                             + _td(days=ahead)).isoformat()
                        nxt = current_period("exam_window", on_date=d)
                        if nxt:
                            bits.append(f"exam window opens {nxt.get('date_start','')}")
                            break
                except Exception:
                    pass
        except Exception:
            pass

        self._line_var.set(" · ".join(bits) if bits
                            else "No active term / period set")


class StaffCertificationsPanel(ttk.Frame):
    """Inline view of one staff member's certifications + expiry warnings.

    Pulls from ``cert_bus.list_certifications_for`` and tints rows
    that have expired or expire within 30 days. Auto-refreshes on
    ``hr.certification.changed``.
    """

    _EXPIRED_FG = "#c0392b"
    _SOON_FG = "#d97706"

    def __init__(self, master: tk.Misc,
                 staff_id: str | int | None = None,
                 *, listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._staff_id: str | None = None

        self._heading_var = tk.StringVar(value="Certifications")
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("kind", "issued", "expires", "issuer")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (160, 110, 110, 160)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.tag_configure("expired", foreground=self._EXPIRED_FG)
        self._tree.tag_configure("soon", foreground=self._SOON_FG)
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        if listen_to_events:
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    subscribe_tk, EVENT_CERT_CHANGED,
                )
                subscribe_tk(EVENT_CERT_CHANGED, self,
                             lambda **_: self.refresh())
            except Exception:
                pass

        if staff_id is not None:
            self.set_staff(staff_id)

    def set_staff(self, staff_id: str | int) -> None:
        self._staff_id = str(staff_id)
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._staff_id:
            self._heading_var.set("Certifications")
            return
        self._heading_var.set(f"Certifications — staff {self._staff_id}")

        try:
            from datetime import date as _date, timedelta as _td
            from education_system.university_system.modules.services.cert_bus import (
                list_certifications_for,
            )
            today = _date.today()
            soon = today + _td(days=30)
            for c in list_certifications_for(self._staff_id):
                expires = c.get("expires_on") or ""
                tag = ()
                if expires:
                    try:
                        d = _date.fromisoformat(expires[:10])
                        if d < today:
                            tag = ("expired",)
                        elif d <= soon:
                            tag = ("soon",)
                    except Exception:
                        pass
                self._tree.insert("", "end", values=(
                    c.get("kind") or "",
                    c.get("issued_on") or "",
                    expires,
                    c.get("issuer") or "",
                ), tags=tag)
        except Exception:
            pass


class IncidentEvidencePanel(ttk.Frame):
    """Show DM-linked documents for a Health & Safety / First Aid incident.

    Reads through ``document_bus.get_documents_for(domain, incident_id)``
    so both H&S and First Aid views see the same evidence pack.
    Refreshes on ``dm.document.changed``.
    """

    def __init__(self, master: tk.Misc, *,
                 incident_id: int | str | None = None,
                 domain: str = "incident",
                 listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._incident_id: str | None = None
        self._domain = domain

        self._heading_var = tk.StringVar(value="Incident evidence")
        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        cols = ("name", "type", "uploaded", "uploaded_by")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=5)
        for c, w in zip(cols, (240, 120, 110, 120)):
            self._tree.heading(c, text=c.replace("_", " ").capitalize())
            self._tree.column(c, width=w, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._empty_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self._empty_var, foreground="#7f8c8d",
        ).pack(anchor="w", padx=10)

        if listen_to_events:
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    subscribe_tk, EVENT_DOCUMENT_CHANGED,
                )

                def _on_change(**payload):
                    if (str(payload.get("ref_id") or "") in
                            ("", str(self._incident_id or ""))
                            or payload.get("domain") == self._domain):
                        self.refresh()

                subscribe_tk(EVENT_DOCUMENT_CHANGED, self, _on_change)
            except Exception:
                pass

        if incident_id is not None:
            self.set_incident(incident_id, domain=domain)

    def set_incident(self, incident_id: int | str, *,
                     domain: str | None = None) -> None:
        self._incident_id = str(incident_id)
        if domain:
            self._domain = domain
        self.refresh()

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._empty_var.set("")
        if not self._incident_id:
            self._heading_var.set("Incident evidence")
            return
        self._heading_var.set(
            f"Incident evidence — {self._domain} #{self._incident_id}"
        )

        try:
            from education_system.university_system.modules.services.document_bus import (
                get_documents_for,
            )
            docs = get_documents_for(self._domain, self._incident_id)
        except Exception as exc:
            self._empty_var.set(f"(unavailable: {exc})")
            return

        if not docs:
            self._empty_var.set("No evidence linked yet.")
            return
        for d in docs:
            self._tree.insert("", "end", values=(
                d.get("document_name") or "",
                d.get("document_type") or "",
                (d.get("upload_date") or "")[:10],
                d.get("uploaded_by") or "",
            ))


__all__ = [
    "show_conflicts_dialog",
    "show_instructor_workload_dialog",
    "show_at_risk_dialog",
    "show_module_timeline_dialog",
    "ModuleTimelinePanel",
    "StudentFinancePanel",
    "ResourceAvailabilityPanel",
    "ResearchOutputPanel",
    "WeeklyGridPanel",
    "StaffWorkloadPanel",
    "AcademicPeriodPanel",
    "StaffCertificationsPanel",
    "IncidentEvidencePanel",
]

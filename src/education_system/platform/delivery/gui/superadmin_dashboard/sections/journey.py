"""Student Journey section and cohort flow.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CARD_BG,
    CONTENT_BG,
    DEFAULT_SYSTEM_COLOR,
    SYSTEM_COLORS,
    SYSTEM_LABELS,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class JourneyMixin:
    # ------------------------------------------------------------------
    # Section: Student Journey (Feature 9)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Cohort flow (aggregate progression funnel)
    # ------------------------------------------------------------------

    def _build_cohort_flow(self, parent):
        """Render the cross-system progression funnel and drop-off analysis."""
        tk.Label(
            parent, text="Cohort Flow",
            font=("Segoe UI", 15, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(4, 2))
        tk.Label(
            parent,
            text="Progression funnel and drop-off: Primary → Secondary → "
                 "College → University.",
            font=("Segoe UI", 9), bg=CONTENT_BG, fg=TEXT_MUTED,
        ).pack(anchor=tk.W, padx=24, pady=(0, 8))

        svc = self._get_journey_service()
        data = None
        if svc:
            try:
                data = svc.get_cohort_flow()
            except Exception:
                data = None

        if not data or not data.get("total_journeys"):
            tk.Label(
                parent, text="No cross-system journey records yet.",
                font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
            ).pack(anchor=tk.W, padx=24, pady=(0, 6))
            return

        # Year filter + summary line.
        controls = tk.Frame(parent, bg=CONTENT_BG)
        controls.pack(fill=tk.X, padx=24, pady=(0, 6))
        tk.Label(
            controls, text="Cohort year:", font=("Segoe UI", 9),
            bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(side=tk.LEFT, padx=(0, 6))

        year_var = tk.StringVar(value="All")
        years = ["All"] + list(data.get("available_years", []))
        body = tk.Frame(parent, bg=CONTENT_BG)

        def _on_year(*_args):
            sel = year_var.get()
            current = data
            try:
                current = svc.get_cohort_flow(year=None if sel == "All" else sel)
            except Exception:
                pass
            for w in body.winfo_children():
                w.destroy()
            self._render_cohort_body(body, current)

        option = tk.OptionMenu(controls, year_var, *years, command=_on_year)
        option.configure(font=("Segoe UI", 9), bg=CARD_BG, relief=tk.FLAT, cursor="hand2")
        option.pack(side=tk.LEFT)

        body.pack(fill=tk.X)
        self._render_cohort_body(body, data)

    def _render_cohort_body(self, body, data):
        # --- Stage funnel (proportional bars) ---
        card = tk.Frame(body, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(fill=tk.X, padx=24, pady=(2, 8))
        tk.Label(
            card, text=f"Stage Funnel  ({data.get('total_journeys', 0)} journeys)",
            font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=12, pady=(8, 4))

        stages = data.get("stage_presence", [])
        max_count = max([s["count"] for s in stages] + [1])
        for s in stages:
            row = tk.Frame(card, bg=CARD_BG)
            row.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(
                row, text=s["label"], font=("Segoe UI", 9), bg=CARD_BG,
                fg=TEXT_DARK, width=18, anchor=tk.W,
            ).pack(side=tk.LEFT)
            bar_wrap = tk.Frame(row, bg="#ecf0f1", width=360, height=18)
            bar_wrap.pack(side=tk.LEFT, padx=(0, 8))
            bar_wrap.pack_propagate(False)
            width = max(2, int(360 * s["count"] / max_count))
            tk.Frame(
                bar_wrap, bg=SYSTEM_COLORS.get(s["system"], "#3498db"),
                width=width, height=18,
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=str(s["count"]), font=("Segoe UI", 9, "bold"),
                bg=CARD_BG, fg=TEXT_DARK,
            ).pack(side=tk.LEFT)
        tk.Frame(card, bg=CARD_BG, height=6).pack()

        # --- Continuation & drop-off between adjacent stages ---
        card2 = tk.Frame(body, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card2.pack(fill=tk.X, padx=24, pady=(0, 8))
        tk.Label(
            card2, text="Continuation & Drop-off",
            font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=12, pady=(8, 4))

        for c in data.get("continuation", []):
            row = tk.Frame(card2, bg=CARD_BG)
            row.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(
                row, text=f"{c['from_label']} → {c['to_label']}",
                font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_DARK,
                width=32, anchor=tk.W,
            ).pack(side=tk.LEFT)
            rate = c["rate"]
            rate_color = "#27ae60" if rate >= 75 else (
                "#e67e22" if rate >= 50 else "#e74c3c")
            tk.Label(
                row,
                text=f"{c['continued']}/{c['from_count']} continued ({rate}%)",
                font=("Segoe UI", 9, "bold"), bg=CARD_BG, fg=rate_color,
            ).pack(side=tk.LEFT)
            if c["dropped"]:
                tk.Label(
                    row, text=f"   {c['dropped']} dropped",
                    font=("Segoe UI", 9), bg=CARD_BG, fg="#e74c3c",
                ).pack(side=tk.LEFT)
        tk.Frame(card2, bg=CARD_BG, height=6).pack()

        # --- Recorded transitions (explicit moves logged in the registry) ---
        trans = data.get("transitions", [])
        if trans:
            card3 = tk.Frame(body, bg=CARD_BG, relief=tk.RAISED, bd=1)
            card3.pack(fill=tk.X, padx=24, pady=(0, 8))
            tk.Label(
                card3, text="Recorded Transitions  (click a row to see who moved)",
                font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
            ).pack(anchor=tk.W, padx=12, pady=(8, 4))
            year = data.get("year")
            for t in trans:
                self._build_transition_row(card3, t, year)
            tk.Frame(card3, bg=CARD_BG, height=6).pack()

    def _build_transition_row(self, parent, t, year):
        """One clickable transition edge that expands to list the students."""
        row = tk.Frame(parent, bg=CARD_BG, cursor="hand2")
        row.pack(fill=tk.X, padx=12, pady=1)
        caret = tk.Label(
            row, text="▶", font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED, width=2,
        )
        caret.pack(side=tk.LEFT)
        tk.Label(
            row, text=f"{t['from_label']} → {t['to_label']}",
            font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_DARK, width=30, anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Label(
            row, text=str(t["count"]), font=("Segoe UI", 9, "bold"),
            bg=CARD_BG, fg=TEXT_DARK,
        ).pack(side=tk.LEFT)

        detail = tk.Frame(parent, bg="#f7f9f9")

        def _toggle(_e=None):
            if detail.winfo_ismapped():
                detail.pack_forget()
                caret.config(text="▶")
                return
            for w in detail.winfo_children():
                w.destroy()
            self._populate_transition_students(detail, t, year)
            detail.pack(fill=tk.X, padx=12, pady=(0, 4), after=row)
            caret.config(text="▼")

        for widget in (row, caret, *row.winfo_children()):
            widget.bind("<Button-1>", _toggle)

    def _populate_transition_students(self, container, t, year):
        svc = self._get_journey_service()
        students = []
        if svc:
            try:
                students = svc.get_transition_students(
                    from_system=t.get("from_system"),
                    to_system=t.get("to_system"),
                    year=year,
                )
            except Exception:
                students = []

        if not students:
            tk.Label(
                container, text="No student detail recorded for this move.",
                font=("Segoe UI", 8), bg="#f7f9f9", fg=TEXT_MUTED,
            ).pack(anchor=tk.W, padx=24, pady=2)
            return

        for s in students:
            parts = [s["name"]]
            if s.get("occurred_at"):
                parts.append(str(s["occurred_at"])[:10])
            if s.get("reason"):
                parts.append(s["reason"])
            tk.Label(
                container, text="• " + "  —  ".join(parts),
                font=("Segoe UI", 9), bg="#f7f9f9", fg=TEXT_DARK, anchor=tk.W,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, padx=24, pady=1)

    def _build_journey(self):
        _, frame = self._make_scrollable(self._content_frame)

        tk.Label(
            frame, text="Student Journey Timeline",
            font=("Segoe UI", 18, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        tk.Label(
            frame,
            text="Visualise a student's path across every system — Playgroup, "
                 "Nursery, Primary, Secondary, Sixth Form, College (FE), "
                 "Apprenticeships, Higher Apprenticeships and University.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 12))

        # Cohort-level progression funnel (aggregate across all students).
        self._build_cohort_flow(frame)

        # Divider before the single-student lookup.
        tk.Frame(frame, bg="#d5dbdb", height=1).pack(fill=tk.X, padx=24, pady=(8, 12))
        tk.Label(
            frame, text="Look Up an Individual Student",
            font=("Segoe UI", 15, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(0, 8))

        # Search bar
        search_bar = tk.Frame(frame, bg=CONTENT_BG)
        search_bar.pack(fill=tk.X, padx=24, pady=(0, 12))

        search_var = tk.StringVar()
        tk.Entry(
            search_bar, textvariable=search_var, font=("Segoe UI", 12), width=30,
        ).pack(side=tk.LEFT, padx=(0, 8), ipady=4)

        timeline_frame = tk.Frame(frame, bg=CONTENT_BG)
        timeline_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))

        status_label = tk.Label(
            timeline_frame, text="Enter a student name or ID and click Search.",
            font=("Segoe UI", 10), bg=CONTENT_BG, fg=TEXT_MUTED,
        )
        status_label.pack(pady=8, anchor=tk.W)

        def _search_journey(*_args):
            query = search_var.get().strip()
            if not query or len(query) < 2:
                return
            # Clear previous timeline
            for w in timeline_frame.winfo_children():
                if w is not status_label:
                    w.destroy()
            status_label.config(text="Searching...")

            journey_svc = self._get_journey_service()
            if not journey_svc:
                status_label.config(text="Journey service unavailable.")
                return

            try:
                results = journey_svc.search_student(query)
            except Exception as exc:
                status_label.config(text=f"Search error: {exc}")
                return

            if not results:
                status_label.config(text="No students found.")
                return

            # Use first result to get full journey
            first = results[0]
            student_id = first.get("student_id", first.get("id", ""))
            system = first.get("system", "")

            try:
                journey = journey_svc.get_journey(student_id, system)
            except Exception:
                journey = None

            if not journey or not journey.get("stages"):
                status_label.config(
                    text=f"Found {first.get('name', '')} in {SYSTEM_LABELS.get(system, system)}, "
                         f"but no cross-system journey data available."
                )
                # Show a single stage card anyway
                self._draw_journey_card(
                    timeline_frame, system,
                    {"name": first.get("name", ""), "status": first.get("status", ""), "id": student_id},
                    is_last=True,
                )
                return

            stages = journey.get("stages", [])
            moves = journey.get("transitions", [])
            status_label.config(
                text=f"Journey for: {journey.get('name', first.get('name', ''))}  —  "
                     f"appears in {len(stages)} system(s) (by name); "
                     f"{len(moves)} recorded move(s)"
            )

            tk.Label(
                timeline_frame, text="Appears In (matched by name)",
                font=("Segoe UI", 11, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
            ).pack(anchor=tk.W, pady=(4, 4))
            for i, stage in enumerate(stages):
                sys_key = stage.get("system", "")
                self._draw_journey_card(timeline_frame, sys_key, stage, is_last=(i == len(stages) - 1))

            # Authoritative recorded moves from the cross-system registry.
            # Distinct from the name-matched stages above, which is why the
            # counts can differ.
            tk.Label(
                timeline_frame, text=f"Recorded Moves ({len(moves)})",
                font=("Segoe UI", 11, "bold"), bg=CONTENT_BG, fg=TEXT_DARK,
            ).pack(anchor=tk.W, pady=(12, 4))
            if moves:
                for m in moves:
                    line = f"  • {m['from_label']} → {m['to_label']}"
                    if m.get("occurred_at"):
                        line += f"   ({str(m['occurred_at'])[:10]})"
                    tk.Label(
                        timeline_frame, text=line, font=("Segoe UI", 9),
                        bg=CONTENT_BG, fg=TEXT_DARK, anchor=tk.W, justify=tk.LEFT,
                    ).pack(anchor=tk.W)
            else:
                tk.Label(
                    timeline_frame,
                    text="  No moves recorded in the registry for this student.",
                    font=("Segoe UI", 9), bg=CONTENT_BG, fg=TEXT_MUTED,
                ).pack(anchor=tk.W)

        tk.Button(
            search_bar, text="Search", font=("Segoe UI", 11), bg="#3498db", fg=TEXT_LIGHT,
            relief=tk.FLAT, cursor="hand2", padx=16, command=_search_journey,
        ).pack(side=tk.LEFT)

        search_bar.winfo_children()[0].bind("<Return>", _search_journey)

    def _draw_journey_card(self, parent, sys_key, stage, is_last=False):
        """Draw a single journey stage card with a connecting line."""
        color = SYSTEM_COLORS.get(sys_key, DEFAULT_SYSTEM_COLOR)
        label = SYSTEM_LABELS.get(sys_key, sys_key.title())

        wrapper = tk.Frame(parent, bg=CONTENT_BG)
        wrapper.pack(fill=tk.X, pady=(0, 0))

        # Timeline dot and connector
        dot_frame = tk.Frame(wrapper, bg=CONTENT_BG, width=40)
        dot_frame.pack(side=tk.LEFT, fill=tk.Y)
        dot_frame.pack_propagate(False)

        dot_canvas = tk.Canvas(dot_frame, width=40, height=80, bg=CONTENT_BG, highlightthickness=0)
        dot_canvas.pack(fill=tk.BOTH, expand=True)
        dot_canvas.create_oval(12, 8, 28, 24, fill=color, outline=color)
        if not is_last:
            dot_canvas.create_line(20, 24, 20, 80, fill="#bdc3c7", width=2)

        # Card content
        card = tk.Frame(wrapper, bg=CARD_BG, relief=tk.RAISED, bd=1)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), pady=4)

        accent = tk.Frame(card, bg=color, height=4)
        accent.pack(fill=tk.X, side=tk.TOP)

        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill=tk.X, padx=12, pady=8)

        tk.Label(
            body, text=label, font=("Segoe UI", 11, "bold"), bg=CARD_BG, fg=TEXT_DARK,
        ).pack(anchor=tk.W)

        info_parts = []
        if stage.get("name"):
            info_parts.append(f"Name: {stage['name']}")
        if stage.get("id") or stage.get("student_id"):
            info_parts.append(f"ID: {stage.get('student_id', stage.get('id', ''))}")
        if stage.get("status"):
            info_parts.append(f"Status: {stage['status']}")
        if stage.get("enrollment_date") or stage.get("enrolled_date"):
            dt = stage.get("enrollment_date") or stage.get("enrolled_date", "")
            info_parts.append(f"Enrolled: {str(dt)[:10]}")
        if stage.get("year_group"):
            info_parts.append(f"Year: {stage['year_group']}")

        if info_parts:
            tk.Label(
                body, text="  |  ".join(info_parts),
                font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_MUTED, wraplength=600, justify=tk.LEFT,
            ).pack(anchor=tk.W, pady=(2, 0))

        # Academic history
        for hist in stage.get("academic_history", []):
            tk.Label(
                body, text=f"  - {hist}",
                font=("Segoe UI", 8), bg=CARD_BG, fg=TEXT_MUTED,
            ).pack(anchor=tk.W)

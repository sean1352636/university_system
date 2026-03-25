"""Cross-system student journey dashboard GUI.

Provides a tkinter Frame that can be embedded in any system's sidebar to
display a student's full educational journey across primary, secondary,
college, and university systems.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.cross_system.journey_service import JourneyService

# Display names and colours for each system stage
SYSTEM_INFO = {
    "primary": {"label": "Primary School", "colour": "#27ae60", "icon": "1"},
    "secondary": {"label": "Secondary School", "colour": "#2980b9", "icon": "2"},
    "college": {"label": "Sixth Form College", "colour": "#8e44ad", "icon": "3"},
    "university": {"label": "University", "colour": "#c0392b", "icon": "4"},
}

STAGE_ORDER = ["primary", "secondary", "college", "university"]


class JourneyDashboardFrame(tk.Frame):
    """Shows a student's full educational journey across all 4 systems."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._service = JourneyService()
        self._auth = auth
        self._search_results = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header bar (dark blue, matching other modules)
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Student Journey Dashboard",
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Search bar
        search_frame = tk.Frame(self, bg="#ecf0f1", pady=8)
        search_frame.pack(fill="x", padx=15)

        tk.Label(
            search_frame,
            text="Student name:",
            bg="#ecf0f1",
            font=("Helvetica", 10),
        ).pack(side="left", padx=(0, 5))

        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        search_entry.pack(side="left", padx=(0, 5))
        search_entry.bind("<Return>", lambda e: self._search())

        ttk.Button(search_frame, text="Search", command=self._search).pack(
            side="left", padx=4
        )
        ttk.Button(search_frame, text="Clear", command=self._clear).pack(
            side="left", padx=4
        )

        self._status_var = tk.StringVar(value="")
        tk.Label(
            search_frame,
            textvariable=self._status_var,
            bg="#ecf0f1",
            font=("Helvetica", 9, "italic"),
            fg="#7f8c8d",
        ).pack(side="right", padx=10)

        # --- Results Treeview ---
        results_label = tk.Label(
            self,
            text="Search Results",
            bg="#ecf0f1",
            font=("Helvetica", 10, "bold"),
            anchor="w",
        )
        results_label.pack(fill="x", padx=15, pady=(5, 0))

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="x", padx=15, pady=(0, 5))

        columns = ("system", "student_id", "name", "year_group", "status")
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse", height=6
        )
        for col, heading, width in [
            ("system", "System", 120),
            ("student_id", "Student ID", 100),
            ("name", "Name", 200),
            ("year_group", "Year/Group", 100),
            ("status", "Status", 90),
        ]:
            self._tree.heading(col, text=heading)
            anchor = "center" if col in ("status", "year_group") else "w"
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="x", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # --- Journey timeline area (scrollable) ---
        timeline_label = tk.Label(
            self,
            text="Educational Journey",
            bg="#ecf0f1",
            font=("Helvetica", 10, "bold"),
            anchor="w",
        )
        timeline_label.pack(fill="x", padx=15, pady=(5, 0))

        timeline_outer = tk.Frame(self, bg="#ecf0f1")
        timeline_outer.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self._timeline_canvas = tk.Canvas(timeline_outer, bg="#ecf0f1", highlightthickness=0)
        timeline_vsb = ttk.Scrollbar(
            timeline_outer, orient="vertical", command=self._timeline_canvas.yview
        )
        self._timeline_canvas.configure(yscrollcommand=timeline_vsb.set)
        timeline_vsb.pack(side="right", fill="y")
        self._timeline_canvas.pack(side="left", fill="both", expand=True)

        self._timeline_frame = tk.Frame(self._timeline_canvas, bg="#ecf0f1")
        self._timeline_window = self._timeline_canvas.create_window(
            (0, 0), window=self._timeline_frame, anchor="nw"
        )

        self._timeline_frame.bind("<Configure>", self._on_timeline_configure)
        self._timeline_canvas.bind("<Configure>", self._on_canvas_configure)

        # Placeholder
        self._placeholder = tk.Label(
            self._timeline_frame,
            text="Search for a student and select a result to view their journey.",
            bg="#ecf0f1",
            fg="#95a5a6",
            font=("Helvetica", 10, "italic"),
            pady=30,
        )
        self._placeholder.pack(fill="x")

    # ------------------------------------------------------------------
    # Canvas / scroll helpers
    # ------------------------------------------------------------------

    def _on_timeline_configure(self, event):
        self._timeline_canvas.configure(scrollregion=self._timeline_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._timeline_canvas.itemconfig(self._timeline_window, width=event.width)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _search(self):
        query = self._search_var.get().strip()
        if not query:
            messagebox.showwarning("Search", "Please enter a student name.", parent=self)
            return

        self._tree.delete(*self._tree.get_children())
        self._search_results = []
        self._clear_timeline()

        try:
            results = self._service.search_student(query)
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        if not results:
            self._status_var.set("No students found.")
            return

        self._search_results = results
        self._status_var.set(f"{len(results)} result(s) found")

        for idx, r in enumerate(results):
            sys_label = SYSTEM_INFO.get(r["system"], {}).get("label", r["system"])
            self._tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    sys_label,
                    r.get("student_id", ""),
                    r.get("name", ""),
                    r.get("year_group", ""),
                    r.get("status", ""),
                ),
            )

    def _clear(self):
        self._search_var.set("")
        self._tree.delete(*self._tree.get_children())
        self._search_results = []
        self._status_var.set("")
        self._clear_timeline()

    # ------------------------------------------------------------------
    # Selection / journey display
    # ------------------------------------------------------------------

    def _on_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._search_results):
            return
        result = self._search_results[idx]

        try:
            journey = self._service.get_journey(
                student_id=result.get("student_id") or result.get("id"),
                system=result["system"],
            )
            # If nothing came back from ID-based search, try name
            if not journey:
                journey = self._service.get_journey(student_name=result.get("name"))
        except Exception as exc:
            self._status_var.set(f"Error loading journey: {exc}")
            return

        if journey:
            self._show_journey(journey)
        else:
            self._clear_timeline()
            tk.Label(
                self._timeline_frame,
                text="No journey data found for this student.",
                bg="#ecf0f1",
                fg="#95a5a6",
                font=("Helvetica", 10, "italic"),
                pady=20,
            ).pack(fill="x")

    def _clear_timeline(self):
        for widget in self._timeline_frame.winfo_children():
            widget.destroy()

    def _show_journey(self, journey):
        """Display journey stages as a vertical timeline."""
        self._clear_timeline()

        for idx, stage in enumerate(journey):
            sys_key = stage.get("system", "")
            info = SYSTEM_INFO.get(sys_key, {"label": sys_key, "colour": "#7f8c8d", "icon": "?"})
            is_last = idx == len(journey) - 1

            # Container for this stage
            stage_frame = tk.Frame(self._timeline_frame, bg="#ecf0f1")
            stage_frame.pack(fill="x", padx=5, pady=0)

            # Left column: timeline connector
            left = tk.Frame(stage_frame, bg="#ecf0f1", width=50)
            left.pack(side="left", fill="y", anchor="n")
            left.pack_propagate(False)

            # Circle indicator
            circle = tk.Label(
                left,
                text=info["icon"],
                bg=info["colour"],
                fg="white",
                font=("Helvetica", 12, "bold"),
                width=3,
                height=1,
                relief="raised",
                bd=1,
            )
            circle.pack(pady=(8, 0))

            # Vertical connector line (except for last)
            if not is_last:
                connector = tk.Frame(left, bg=info["colour"], width=3, height=30)
                connector.pack(expand=True, fill="y")

            # Right column: stage info card
            card = tk.LabelFrame(
                stage_frame,
                text=f"  {info['label']}  ",
                bg="white",
                fg=info["colour"],
                font=("Helvetica", 11, "bold"),
                padx=12,
                pady=8,
                relief="groove",
                bd=1,
            )
            card.pack(side="left", fill="x", expand=True, padx=(5, 0), pady=5)

            # Student info grid inside the card
            row = 0
            fields = [
                ("Student ID", stage.get("student_id", "")),
                ("Name", stage.get("name", "")),
                ("Date of Birth", stage.get("dob", "")),
                ("Year / Group", stage.get("year_group", "")),
                ("Status", stage.get("status", "")),
                ("Enrolled", stage.get("enrolled_date", "")),
            ]
            for label_text, value in fields:
                if not value:
                    continue
                tk.Label(
                    card,
                    text=f"{label_text}:",
                    bg="white",
                    font=("Helvetica", 9, "bold"),
                    anchor="w",
                ).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=1)
                tk.Label(
                    card,
                    text=str(value),
                    bg="white",
                    font=("Helvetica", 9),
                    anchor="w",
                ).grid(row=row, column=1, sticky="w", pady=1)
                row += 1

            # Academic history expandable section
            history = stage.get("academic_history", [])
            if history:
                hist_btn_var = tk.BooleanVar(value=False)
                hist_frame = tk.Frame(card, bg="white")
                hist_frame.grid(row=row, column=0, columnspan=2, sticky="we", pady=(5, 0))

                def _toggle_history(frame=hist_frame, var=hist_btn_var, data=history):
                    self._toggle_history_section(frame, var, data)

                hist_btn = ttk.Button(
                    hist_frame,
                    text=f"Academic History ({len(history)} record(s))",
                    command=_toggle_history,
                )
                hist_btn.pack(anchor="w")

        # Scroll to top
        self._timeline_canvas.yview_moveto(0)

    # ------------------------------------------------------------------
    # Academic history expansion
    # ------------------------------------------------------------------

    @staticmethod
    def _toggle_history_section(parent_frame, var, records):
        """Toggle an expandable academic history section."""
        tag = "_history_content"
        existing = [w for w in parent_frame.winfo_children() if getattr(w, "_tag", None) == tag]

        if existing:
            for w in existing:
                w.destroy()
            var.set(False)
            return

        var.set(True)
        content = tk.Frame(parent_frame, bg="#f9f9f9", bd=1, relief="sunken", padx=6, pady=4)
        content._tag = tag
        content.pack(fill="x", pady=(4, 0))

        for rec in records[:20]:  # cap display at 20 records
            line_parts = []
            for key in ("source_system", "academic_year", "subject", "subject_code",
                        "grade", "score", "level", "outcome", "assessment_type"):
                val = rec.get(key)
                if val is not None and str(val).strip():
                    line_parts.append(f"{key}: {val}")
            if not line_parts:
                # Fallback: show all keys
                line_parts = [f"{k}: {v}" for k, v in rec.items() if v is not None and str(v).strip()]

            text = "  |  ".join(line_parts) if line_parts else "(no detail)"
            tk.Label(
                content,
                text=text,
                bg="#f9f9f9",
                font=("Helvetica", 8),
                anchor="w",
                wraplength=500,
                justify="left",
            ).pack(fill="x", pady=1)

        if len(records) > 20:
            tk.Label(
                content,
                text=f"... and {len(records) - 20} more record(s)",
                bg="#f9f9f9",
                font=("Helvetica", 8, "italic"),
                fg="#95a5a6",
                anchor="w",
            ).pack(fill="x")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when the module is shown in the sidebar."""
        pass

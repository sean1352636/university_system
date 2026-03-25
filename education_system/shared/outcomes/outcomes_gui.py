"""Student outcome tracking GUI.

Provides a tkinter Frame showing what happened to students after they
left each education system, including their performance in the
destination system.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.outcomes.outcomes_service import (
    OutcomesService,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
)


class OutcomeTrackingFrame(tk.Frame):
    """Frame for tracking student outcomes across education systems."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._service = OutcomesService()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header bar
        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Student Outcome Tracking",
            font=("Helvetica", 15, "bold"),
            bg="#1a5276",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Controls bar
        controls = tk.Frame(self, bg="#ecf0f1", pady=8)
        controls.pack(fill="x", padx=15)

        tk.Label(
            controls, text="Source System:", bg="#ecf0f1",
            font=("Helvetica", 10),
        ).pack(side="left", padx=(0, 5))

        self._system_var = tk.StringVar(value="primary")
        system_values = [f"{k} - {SYSTEM_LABELS[k]}" for k in SYSTEM_ORDER]
        self._system_combo = ttk.Combobox(
            controls, textvariable=self._system_var,
            values=system_values, state="readonly", width=30,
        )
        self._system_combo.set(system_values[0])
        self._system_combo.pack(side="left", padx=(0, 10))
        self._system_combo.bind("<<ComboboxSelected>>", lambda e: self._load_outcomes())

        ttk.Button(controls, text="Load Outcomes", command=self._load_outcomes).pack(
            side="left", padx=4
        )
        ttk.Button(controls, text="Refresh", command=self.refresh).pack(
            side="left", padx=4
        )

        # Stats bar
        self._stats_frame = tk.Frame(self, bg="#ecf0f1")
        self._stats_frame.pack(fill="x", padx=15, pady=(5, 0))

        self._stats_vars = {}
        for key, label, colour in [
            ("total_left", "Total Left", "#2980b9"),
            ("progressed", "Progressed", "#27ae60"),
            ("progression_rate", "Progression Rate", "#8e44ad"),
            ("avg_grade", "Avg Grade (Dest)", "#e67e22"),
        ]:
            card = tk.Frame(self._stats_frame, bg="white", bd=1, relief="groove",
                            padx=12, pady=6)
            card.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(card, text=label, font=("Helvetica", 8), bg="white",
                     fg="#7f8c8d").pack(anchor="w")
            var = tk.StringVar(value="--")
            self._stats_vars[key] = var
            tk.Label(card, textvariable=var, font=("Helvetica", 16, "bold"),
                     bg="white", fg=colour).pack(anchor="w")

        # Main treeview
        tree_label = tk.Label(
            self, text="Student Outcomes", bg="#ecf0f1",
            font=("Helvetica", 10, "bold"), anchor="w",
        )
        tree_label.pack(fill="x", padx=15, pady=(10, 2))

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("name", "destination", "status", "grade_avg", "transfer_date")
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings",
            selectmode="browse",
        )
        for col, heading, width in [
            ("name", "Student Name", 200),
            ("destination", "Destination System", 160),
            ("status", "Current Status", 120),
            ("grade_avg", "Grade Average", 110),
            ("transfer_date", "Transfer Date", 120),
        ]:
            self._tree.heading(col, text=heading)
            anchor = "center" if col in ("status", "grade_avg", "transfer_date") else "w"
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _get_selected_system(self):
        """Extract the system key from the combo selection."""
        val = self._system_combo.get()
        if " - " in val:
            return val.split(" - ")[0].strip()
        return val.strip()

    def _load_outcomes(self):
        """Load outcomes for the selected source system."""
        system = self._get_selected_system()
        if system not in SYSTEM_ORDER:
            messagebox.showwarning("Selection", "Please select a valid system.", parent=self)
            return

        self._tree.delete(*self._tree.get_children())

        try:
            outcomes = self._service.get_outcomes_for_system(system)
            stats = self._service.get_progression_stats(system)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load outcomes:\n{exc}", parent=self)
            return

        # Update stats cards
        self._stats_vars["total_left"].set(str(stats["total_left"]))
        self._stats_vars["progressed"].set(str(stats["progressed_count"]))
        self._stats_vars["progression_rate"].set(f"{stats['progression_rate']}%")
        avg_grade = stats.get("avg_grade_at_destination")
        self._stats_vars["avg_grade"].set(
            f"{avg_grade:.1f}" if avg_grade is not None else "N/A"
        )

        # Populate tree
        if not outcomes:
            self._tree.insert("", "end", values=(
                "No outcome data found", "", "", "", "",
            ))
            return

        for o in outcomes:
            dest_label = SYSTEM_LABELS.get(o.get("destination_system", ""),
                                            o.get("destination_system", ""))
            grade_str = f"{o['grade_average']:.1f}" if o.get("grade_average") is not None else "N/A"
            self._tree.insert("", "end", values=(
                o.get("student_name", ""),
                dest_label,
                o.get("destination_status", ""),
                grade_str,
                o.get("transfer_date", ""),
            ))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload outcome data for the currently selected system."""
        self._load_outcomes()

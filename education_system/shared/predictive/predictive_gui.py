"""Predictive alerts GUI.

Provides a tkinter Frame that lists at-risk students based on
cross-system analysis, with filtering by risk level and detail views.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.predictive.predictive_service import (
    PredictiveService,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
)


RISK_COLOURS = {
    "High": "#e74c3c",
    "Medium": "#f39c12",
    "Low": "#27ae60",
}


class PredictiveAlertsFrame(tk.Frame):
    """Frame displaying predictive at-risk student alerts."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._service = PredictiveService()
        self._all_alerts = []
        self._build_ui()
        self.after_idle(self._apply_eqa_context)

    def _apply_eqa_context(self):
        """#1 — Honour an EQA drill-through (set on ``self.eqa_context``
        by the receiver bridge). Prefilters by metric / threshold when
        the matching widgets exist; silently no-ops otherwise."""
        ctx = getattr(self, "eqa_context", None)
        if not ctx:
            return
        try:
            metric = ctx.get("metric")
            if metric:
                for attr in ("_metric_var", "_filter_metric_var",
                             "_category_var"):
                    var = getattr(self, attr, None)
                    if var is not None:
                        try:
                            var.set(metric)
                            break
                        except Exception:
                            pass
            thr = ctx.get("threshold_pct")
            if thr is not None:
                for attr in ("_threshold_var", "_min_score_var"):
                    var = getattr(self, attr, None)
                    if var is not None:
                        try:
                            var.set(thr)
                            break
                        except Exception:
                            pass
            for fn in ("_apply_filters", "refresh", "_refresh"):
                m = getattr(self, fn, None)
                if callable(m):
                    m()
                    break
        except Exception:
            pass

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
            text="Predictive At-Risk Alerts",
            font=("Helvetica", 15, "bold"),
            bg="#1a5276",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Controls bar
        controls = tk.Frame(self, bg="#ecf0f1", pady=8)
        controls.pack(fill="x", padx=15)

        tk.Label(
            controls, text="System:", bg="#ecf0f1",
            font=("Helvetica", 10),
        ).pack(side="left", padx=(0, 5))

        system_values = [f"{k} - {SYSTEM_LABELS[k]}" for k in SYSTEM_ORDER]
        self._system_var = tk.StringVar()
        self._system_combo = ttk.Combobox(
            controls, textvariable=self._system_var,
            values=system_values, state="readonly", width=28,
        )
        self._system_combo.set(system_values[1] if len(system_values) > 1 else system_values[0])
        self._system_combo.pack(side="left", padx=(0, 10))

        ttk.Button(controls, text="Scan", command=self._scan).pack(side="left", padx=4)

        # Filter by risk level
        tk.Label(
            controls, text="Filter:", bg="#ecf0f1",
            font=("Helvetica", 10),
        ).pack(side="left", padx=(20, 5))

        self._filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(
            controls, textvariable=self._filter_var,
            values=["All", "High", "Medium", "Low"],
            state="readonly", width=10,
        )
        filter_combo.pack(side="left", padx=(0, 5))
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        # Alert count
        self._count_var = tk.StringVar(value="")
        tk.Label(
            controls, textvariable=self._count_var, bg="#ecf0f1",
            font=("Helvetica", 10, "bold"), fg="#e74c3c",
        ).pack(side="right", padx=10)

        # Main content area: left = treeview, right = detail panel
        content = tk.PanedWindow(self, orient="horizontal", sashwidth=4, bg="#bdc3c7")
        content.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Left: alerts treeview
        left_frame = tk.Frame(content)
        content.add(left_frame, width=500)

        columns = ("name", "risk_level", "score", "key_factors")
        self._tree = ttk.Treeview(
            left_frame, columns=columns, show="headings",
            selectmode="browse",
        )
        for col, heading, width in [
            ("name", "Student Name", 180),
            ("risk_level", "Risk Level", 80),
            ("score", "Score", 60),
            ("key_factors", "Key Factors", 250),
        ]:
            self._tree.heading(col, text=heading)
            anchor = "center" if col in ("risk_level", "score") else "w"
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Configure tag colours for risk levels
        self._tree.tag_configure("High", foreground="#e74c3c")
        self._tree.tag_configure("Medium", foreground="#f39c12")
        self._tree.tag_configure("Low", foreground="#27ae60")

        # Right: detail panel
        right_frame = tk.Frame(content, bg="#ecf0f1")
        content.add(right_frame, width=350)

        detail_label = tk.Label(
            right_frame, text="Student Detail", bg="#ecf0f1",
            font=("Helvetica", 11, "bold"), anchor="w",
        )
        detail_label.pack(fill="x", padx=10, pady=(10, 5))

        # Detail content (scrollable text)
        detail_container = tk.Frame(right_frame, bg="#ecf0f1")
        detail_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._detail_text = tk.Text(
            detail_container, wrap="word", font=("Helvetica", 10),
            bg="white", relief="groove", bd=1, padx=8, pady=8,
            state="disabled",
        )
        detail_vsb = ttk.Scrollbar(
            detail_container, orient="vertical", command=self._detail_text.yview
        )
        self._detail_text.configure(yscrollcommand=detail_vsb.set)
        self._detail_text.pack(side="left", fill="both", expand=True)
        detail_vsb.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _get_selected_system(self):
        """Extract the system key from the combo selection."""
        val = self._system_combo.get()
        if " - " in val:
            return val.split(" - ")[0].strip()
        return val.strip()

    def _scan(self):
        """Scan for at-risk students in the selected system."""
        system = self._get_selected_system()
        if system not in SYSTEM_ORDER:
            messagebox.showwarning("Selection", "Please select a valid system.", parent=self)
            return

        try:
            self._all_alerts = self._service.get_at_risk_students(system)
        except Exception as exc:
            messagebox.showerror("Error", f"Scan failed:\n{exc}", parent=self)
            self._all_alerts = []

        self._apply_filter()

    def _apply_filter(self):
        """Apply the risk level filter to the treeview."""
        self._tree.delete(*self._tree.get_children())
        self._clear_detail()

        level_filter = self._filter_var.get()
        filtered = self._all_alerts
        if level_filter != "All":
            filtered = [a for a in self._all_alerts if a["risk_level"] == level_filter]

        high_count = sum(1 for a in self._all_alerts if a["risk_level"] == "High")
        med_count = sum(1 for a in self._all_alerts if a["risk_level"] == "Medium")
        self._count_var.set(
            f"{len(self._all_alerts)} alert(s)  |  {high_count} High  {med_count} Medium"
        )

        if not filtered:
            self._tree.insert("", "end", values=(
                "No at-risk students found", "", "", "",
            ))
            return

        for idx, alert in enumerate(filtered):
            factors_str = "; ".join(alert.get("risk_factors", [])[:2])
            if len(alert.get("risk_factors", [])) > 2:
                factors_str += " ..."

            self._tree.insert(
                "", "end", iid=str(idx),
                values=(
                    alert.get("student_name", ""),
                    alert.get("risk_level", ""),
                    alert.get("risk_score", 0),
                    factors_str,
                ),
                tags=(alert.get("risk_level", ""),),
            )

    def _on_select(self, event):
        """Show detail for the selected student."""
        sel = self._tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except (ValueError, IndexError):
            return

        level_filter = self._filter_var.get()
        filtered = self._all_alerts
        if level_filter != "All":
            filtered = [a for a in self._all_alerts if a["risk_level"] == level_filter]

        if idx < 0 or idx >= len(filtered):
            return

        alert = filtered[idx]
        self._show_detail(alert)

    def _clear_detail(self):
        self._detail_text.config(state="normal")
        self._detail_text.delete("1.0", "end")
        self._detail_text.config(state="disabled")

    def _show_detail(self, alert):
        """Display detailed info for an at-risk student."""
        self._detail_text.config(state="normal")
        self._detail_text.delete("1.0", "end")

        lines = []
        lines.append(f"Student: {alert.get('student_name', 'Unknown')}")
        lines.append(f"Student ID: {alert.get('student_id', '')}")
        lines.append(f"System: {SYSTEM_LABELS.get(alert.get('system', ''), alert.get('system', ''))}")
        lines.append(f"Previous System: {SYSTEM_LABELS.get(alert.get('previous_system', ''), alert.get('previous_system', ''))}")
        lines.append("")
        lines.append(f"Risk Level: {alert.get('risk_level', 'Unknown')}")
        lines.append(f"Risk Score: {alert.get('risk_score', 0)} / 100")
        lines.append("")

        att = alert.get("attendance_pct")
        lines.append(f"Attendance: {att:.1f}%" if att is not None else "Attendance: N/A")
        grade = alert.get("grade_average")
        lines.append(f"Grade Average: {grade:.1f}" if grade is not None else "Grade Average: N/A")
        lines.append("")

        lines.append("Risk Factors:")
        for factor in alert.get("risk_factors", []):
            lines.append(f"  - {factor}")

        if not alert.get("risk_factors"):
            lines.append("  (none identified)")

        self._detail_text.insert("end", "\n".join(lines))
        self._detail_text.config(state="disabled")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def refresh(self):
        """Re-scan for at-risk students."""
        self._scan()

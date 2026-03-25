"""Reverse Lookup GUI frame.

Provides a tkinter Frame for finding where transferred students ended up
in destination education systems.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.reverse_lookup.reverse_lookup_service import (
    ReverseLookupService,
    SYSTEM_LABELS,
)

SOURCE_SYSTEMS = ["primary", "secondary", "college"]


class ReverseLookupFrame(tk.Frame):
    """GUI for tracking transferred students across education systems."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._service = ReverseLookupService()
        self._transferred = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Reverse Lookup - Transfer Tracking",
            font=("Helvetica", 15, "bold"),
            bg="#1a5276",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Controls bar
        ctrl = tk.Frame(self, bg="#ecf0f1", pady=8)
        ctrl.pack(fill="x", padx=15)

        tk.Label(ctrl, text="Source System:", bg="#ecf0f1", font=("Helvetica", 10)).pack(
            side="left", padx=(0, 5)
        )
        self._source_var = tk.StringVar(value=SYSTEM_LABELS[SOURCE_SYSTEMS[0]])
        src_combo = ttk.Combobox(
            ctrl,
            textvariable=self._source_var,
            values=[SYSTEM_LABELS[s] for s in SOURCE_SYSTEMS],
            state="readonly",
            width=20,
        )
        src_combo.current(0)
        src_combo.pack(side="left", padx=(0, 10))

        ttk.Button(ctrl, text="Load Transferred", command=self._load_transferred).pack(
            side="left", padx=4
        )
        ttk.Button(ctrl, text="Destination Summary", command=self._show_summary).pack(
            side="left", padx=4
        )

        self._status_var = tk.StringVar(value="")
        tk.Label(
            ctrl,
            textvariable=self._status_var,
            bg="#ecf0f1",
            font=("Helvetica", 9, "italic"),
            fg="#7f8c8d",
        ).pack(side="right", padx=10)

        # Transferred students Treeview
        tk.Label(
            self, text="Transferred Students", bg="#ecf0f1",
            font=("Helvetica", 10, "bold"), anchor="w"
        ).pack(fill="x", padx=15, pady=(5, 0))

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="x", padx=15, pady=(0, 5))

        columns = ("student_id", "name", "year_group", "status")
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse", height=10
        )
        for col, heading, width in [
            ("student_id", "Student ID", 120),
            ("name", "Name", 220),
            ("year_group", "Year Group", 100),
            ("status", "Status", 100),
        ]:
            self._tree.heading(col, text=heading)
            anchor = "center" if col in ("status", "year_group") else "w"
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="x", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail panel
        tk.Label(
            self, text="Destination Details", bg="#ecf0f1",
            font=("Helvetica", 10, "bold"), anchor="w"
        ).pack(fill="x", padx=15, pady=(5, 0))

        detail_outer = tk.Frame(self, bg="#ecf0f1")
        detail_outer.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self._detail_text = tk.Text(
            detail_outer, wrap="word", font=("Courier", 9), state="disabled", height=12
        )
        detail_vsb = ttk.Scrollbar(detail_outer, orient="vertical", command=self._detail_text.yview)
        self._detail_text.configure(yscrollcommand=detail_vsb.set)
        self._detail_text.pack(side="left", fill="both", expand=True)
        detail_vsb.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # Source system management
    # ------------------------------------------------------------------

    def _get_source_key(self):
        label = self._source_var.get()
        for key, lbl in SYSTEM_LABELS.items():
            if lbl == label:
                return key
        return SOURCE_SYSTEMS[0]

    # ------------------------------------------------------------------
    # Load transferred students
    # ------------------------------------------------------------------

    def _load_transferred(self):
        source = self._get_source_key()
        self._tree.delete(*self._tree.get_children())
        self._transferred = []
        self._clear_detail()

        try:
            self._transferred = self._service.find_transferred_students(source)
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        if not self._transferred:
            self._status_var.set("No transferred students found.")
            return

        self._status_var.set(f"{len(self._transferred)} transferred student(s)")

        for idx, stu in enumerate(self._transferred):
            self._tree.insert(
                "", "end", iid=str(idx),
                values=(
                    stu.get("student_id", ""),
                    stu.get("name", ""),
                    stu.get("year_group", ""),
                    stu.get("status", ""),
                ),
            )

    # ------------------------------------------------------------------
    # Selection - look up destination
    # ------------------------------------------------------------------

    def _on_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return

        idx = int(sel[0])
        if idx < 0 or idx >= len(self._transferred):
            return

        student = self._transferred[idx]
        source = self._get_source_key()

        self._status_var.set("Looking up destination...")
        self.update_idletasks()

        try:
            dest = self._service.find_destination(student["name"], source)
        except Exception as exc:
            self._show_detail_text(f"Error: {exc}")
            self._status_var.set("Lookup failed.")
            return

        if not dest:
            self._show_detail_text(
                f"Student: {student.get('name', '?')}\n"
                f"Source:  {SYSTEM_LABELS.get(source, source)}\n\n"
                f"Destination: NOT FOUND\n"
                f"This student was not found in any destination system."
            )
            self._status_var.set("Destination not found.")
            return

        lines = [
            f"Student: {student.get('name', '?')}",
            f"Source System: {SYSTEM_LABELS.get(source, source)}",
            f"Source ID: {student.get('student_id', '?')}",
            "",
            f"--- Destination ---",
            f"System: {SYSTEM_LABELS.get(dest['dest_system'], dest['dest_system'])}",
            f"Student ID: {dest.get('student_id', 'N/A')}",
            f"Name: {dest.get('name', 'N/A')}",
            f"Status: {dest.get('status', 'N/A')}",
            f"Year/Group: {dest.get('year_group', 'N/A')}",
        ]

        if dest.get("previous_system_id"):
            lines.append(f"Previous System ID: {dest['previous_system_id']}")

        grades = dest.get("grades_summary", [])
        if grades:
            lines.append("")
            lines.append(f"--- Recent Grades ({len(grades)} record(s)) ---")
            for g in grades:
                lines.append(f"  {g}")

        self._show_detail_text("\n".join(lines))
        self._status_var.set(f"Found in {SYSTEM_LABELS.get(dest['dest_system'], dest['dest_system'])}")

    # ------------------------------------------------------------------
    # Destination summary
    # ------------------------------------------------------------------

    def _show_summary(self):
        source = self._get_source_key()
        self._status_var.set("Computing summary (may take a moment)...")
        self.update_idletasks()

        try:
            summary = self._service.get_destination_summary(source)
        except Exception as exc:
            self._show_detail_text(f"Error: {exc}")
            self._status_var.set("Summary failed.")
            return

        total = summary.pop("_total_transferred", 0)
        lines = [
            f"Destination Summary for {SYSTEM_LABELS.get(source, source)}",
            f"Total Transferred Students: {total}",
            "",
            f"{'Destination':<30} {'Count':>6}",
            "-" * 38,
        ]
        for dest_label, count in sorted(summary.items()):
            lines.append(f"{dest_label:<30} {count:>6}")

        self._show_detail_text("\n".join(lines))
        self._status_var.set("Summary complete.")

    # ------------------------------------------------------------------
    # Detail panel helpers
    # ------------------------------------------------------------------

    def _clear_detail(self):
        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        self._detail_text.configure(state="disabled")

    def _show_detail_text(self, text):
        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        self._detail_text.insert("1.0", text)
        self._detail_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when the module is shown in the sidebar."""
        pass

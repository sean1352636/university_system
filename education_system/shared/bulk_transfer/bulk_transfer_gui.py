"""Bulk Transfer GUI frame.

Provides a tkinter Frame for selecting and transferring batches of students
between education systems.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.bulk_transfer.bulk_transfer_service import (
    BulkTransferService,
    DESTINATION_MAP,
)

SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}

SOURCE_SYSTEMS = ["primary", "secondary", "college"]


class BulkTransferFrame(tk.Frame):
    """GUI for bulk student transfers between education systems."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._service = BulkTransferService()
        self._eligible = []  # list of student dicts
        self._checked = {}   # iid -> BooleanVar
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
            text="Bulk Student Transfer",
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
        self._source_var = tk.StringVar(value=SOURCE_SYSTEMS[0])
        src_combo = ttk.Combobox(
            ctrl,
            textvariable=self._source_var,
            values=[SYSTEM_LABELS[s] for s in SOURCE_SYSTEMS],
            state="readonly",
            width=20,
        )
        src_combo.current(0)
        src_combo.pack(side="left", padx=(0, 10))
        src_combo.bind("<<ComboboxSelected>>", self._on_source_change)

        ttk.Button(ctrl, text="Load Eligible", command=self._load_eligible).pack(
            side="left", padx=4
        )

        self._dest_var = tk.StringVar(value="")
        tk.Label(
            ctrl,
            textvariable=self._dest_var,
            bg="#ecf0f1",
            font=("Helvetica", 10, "italic"),
            fg="#2c3e50",
        ).pack(side="left", padx=15)

        self._status_var = tk.StringVar(value="")
        tk.Label(
            ctrl,
            textvariable=self._status_var,
            bg="#ecf0f1",
            font=("Helvetica", 9, "italic"),
            fg="#7f8c8d",
        ).pack(side="right", padx=10)

        self._update_dest_label()

        # Selection buttons
        btn_bar = tk.Frame(self, bg="#ecf0f1")
        btn_bar.pack(fill="x", padx=15)
        ttk.Button(btn_bar, text="Select All", command=self._select_all).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Deselect All", command=self._deselect_all).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Transfer Selected", command=self._transfer_selected).pack(
            side="right", padx=4
        )

        # Treeview with checkbox column
        tree_frame = tk.Frame(self, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(5, 5))

        columns = ("selected", "student_id", "name", "year_group", "status")
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse", height=15
        )
        for col, heading, width, anchor in [
            ("selected", "Sel", 40, "center"),
            ("student_id", "Student ID", 120, "w"),
            ("name", "Name", 220, "w"),
            ("year_group", "Year Group", 100, "center"),
            ("status", "Status", 100, "center"),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Click on row toggles selection
        self._tree.bind("<ButtonRelease-1>", self._on_row_click)

        # Results summary area
        results_label = tk.Label(
            self, text="Transfer Results", bg="#ecf0f1", font=("Helvetica", 10, "bold"), anchor="w"
        )
        results_label.pack(fill="x", padx=15, pady=(5, 0))

        self._results_text = tk.Text(
            self, height=6, wrap="word", state="disabled", font=("Courier", 9)
        )
        self._results_text.pack(fill="x", padx=15, pady=(0, 10))

    # ------------------------------------------------------------------
    # Source / destination management
    # ------------------------------------------------------------------

    def _get_source_key(self):
        """Map the combo display text back to a system key."""
        label = self._source_var.get()
        for key, lbl in SYSTEM_LABELS.items():
            if lbl == label:
                return key
        return SOURCE_SYSTEMS[0]

    def _on_source_change(self, event=None):
        self._update_dest_label()
        self._clear_tree()

    def _update_dest_label(self):
        source = self._get_source_key()
        dest = DESTINATION_MAP.get(source, "")
        if dest:
            self._dest_var.set(f"Destination: {SYSTEM_LABELS.get(dest, dest)}")
        else:
            self._dest_var.set("No destination available")

    # ------------------------------------------------------------------
    # Load eligible students
    # ------------------------------------------------------------------

    def _load_eligible(self):
        source = self._get_source_key()
        self._clear_tree()

        try:
            self._eligible = self._service.get_eligible_students(source)
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        if not self._eligible:
            self._status_var.set("No eligible students found.")
            return

        self._status_var.set(f"{len(self._eligible)} eligible student(s)")

        for idx, stu in enumerate(self._eligible):
            iid = str(idx)
            self._checked[iid] = False
            self._tree.insert(
                "", "end", iid=iid,
                values=(
                    "[ ]",
                    stu.get("student_id", ""),
                    stu.get("name", ""),
                    stu.get("year_group", ""),
                    stu.get("status", ""),
                ),
            )

    def _clear_tree(self):
        self._tree.delete(*self._tree.get_children())
        self._eligible = []
        self._checked = {}
        self._status_var.set("")

    # ------------------------------------------------------------------
    # Selection management
    # ------------------------------------------------------------------

    def _on_row_click(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        self._toggle_check(iid)

    def _toggle_check(self, iid):
        current = self._checked.get(iid, False)
        self._checked[iid] = not current
        marker = "[X]" if not current else "[ ]"
        values = list(self._tree.item(iid, "values"))
        values[0] = marker
        self._tree.item(iid, values=values)

    def _select_all(self):
        for iid in self._tree.get_children():
            self._checked[iid] = True
            values = list(self._tree.item(iid, "values"))
            values[0] = "[X]"
            self._tree.item(iid, values=values)

    def _deselect_all(self):
        for iid in self._tree.get_children():
            self._checked[iid] = False
            values = list(self._tree.item(iid, "values"))
            values[0] = "[ ]"
            self._tree.item(iid, values=values)

    # ------------------------------------------------------------------
    # Transfer execution
    # ------------------------------------------------------------------

    def _transfer_selected(self):
        selected_ids = []
        for iid, checked in self._checked.items():
            if checked:
                idx = int(iid)
                if 0 <= idx < len(self._eligible):
                    selected_ids.append(self._eligible[idx]["student_id"])

        if not selected_ids:
            messagebox.showwarning("Transfer", "No students selected.", parent=self)
            return

        source = self._get_source_key()
        dest = DESTINATION_MAP.get(source)
        if not dest:
            messagebox.showerror("Transfer", "No valid destination system.", parent=self)
            return

        confirm = messagebox.askyesno(
            "Confirm Transfer",
            f"Transfer {len(selected_ids)} student(s) from "
            f"{SYSTEM_LABELS.get(source, source)} to "
            f"{SYSTEM_LABELS.get(dest, dest)}?\n\n"
            "This will mark them as Transferred in the source system.",
            parent=self,
        )
        if not confirm:
            return

        self._status_var.set("Transferring...")
        self.update_idletasks()

        try:
            results = self._service.transfer_batch(source, dest, selected_ids)
        except Exception as exc:
            messagebox.showerror("Transfer Error", str(exc), parent=self)
            self._status_var.set("Transfer failed.")
            return

        self._show_results(results)
        self._status_var.set(
            f"Done: {results['transferred']} transferred, {results['failed']} failed"
        )

        # Reload the list to reflect updated statuses
        self._load_eligible()

    def _show_results(self, results):
        self._results_text.configure(state="normal")
        self._results_text.delete("1.0", "end")

        lines = [
            f"Transfer from {results.get('source_system', '?')} "
            f"to {results.get('dest_system', '?')}",
            f"Timestamp: {results.get('timestamp', '')}",
            f"Transferred: {results.get('transferred', 0)}",
            f"Failed:      {results.get('failed', 0)}",
            "",
        ]
        for d in results.get("details", []):
            sid = d.get("student_id", "?")
            name = d.get("name", "")
            if d.get("success"):
                lines.append(f"  OK   {sid}  {name}")
            else:
                lines.append(f"  FAIL {sid}  {name}  ({d.get('error', 'unknown')})")

        self._results_text.insert("1.0", "\n".join(lines))
        self._results_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when the module is shown in the sidebar."""
        pass

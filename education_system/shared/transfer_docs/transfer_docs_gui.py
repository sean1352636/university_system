"""Transfer Documents GUI frame.

Provides a tkinter Frame for searching students, generating transition
reports, and saving them to file.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.shared.transfer_docs.transfer_docs_service import (
    TransferDocsService,
    SYSTEM_LABELS,
)


class TransferDocumentsFrame(tk.Frame):
    """GUI for generating student transfer / transition documents."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._service = TransferDocsService()
        self._search_results = []
        self._current_report = ""
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
            text="Transfer Documents",
            font=("Helvetica", 15, "bold"),
            bg="#1a5276",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Search bar
        search_frame = tk.Frame(self, bg="#ecf0f1", pady=8)
        search_frame.pack(fill="x", padx=15)

        tk.Label(
            search_frame, text="Student name:", bg="#ecf0f1", font=("Helvetica", 10)
        ).pack(side="left", padx=(0, 5))

        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        search_entry.pack(side="left", padx=(0, 5))
        search_entry.bind("<Return>", lambda e: self._search())

        ttk.Button(search_frame, text="Search", command=self._search).pack(side="left", padx=4)

        self._status_var = tk.StringVar(value="")
        tk.Label(
            search_frame,
            textvariable=self._status_var,
            bg="#ecf0f1",
            font=("Helvetica", 9, "italic"),
            fg="#7f8c8d",
        ).pack(side="right", padx=10)

        # Search results Treeview
        tk.Label(
            self, text="Search Results", bg="#ecf0f1", font=("Helvetica", 10, "bold"), anchor="w"
        ).pack(fill="x", padx=15, pady=(5, 0))

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="x", padx=15, pady=(0, 5))

        columns = ("system", "student_id", "name", "year_group", "status")
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse", height=6
        )
        for col, heading, width in [
            ("system", "System", 130),
            ("student_id", "Student ID", 110),
            ("name", "Name", 200),
            ("year_group", "Year Group", 90),
            ("status", "Status", 90),
        ]:
            self._tree.heading(col, text=heading)
            anchor = "center" if col in ("status", "year_group") else "w"
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="x", expand=True)
        vsb.pack(side="right", fill="y")

        # Action buttons
        btn_frame = tk.Frame(self, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=15, pady=4)
        ttk.Button(btn_frame, text="Generate Report", command=self._generate_report).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="Save to File", command=self._save_report).pack(
            side="left", padx=4
        )

        # Report text area
        tk.Label(
            self, text="Report Preview", bg="#ecf0f1", font=("Helvetica", 10, "bold"), anchor="w"
        ).pack(fill="x", padx=15, pady=(5, 0))

        text_frame = tk.Frame(self)
        text_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self._report_text = tk.Text(
            text_frame, wrap="word", font=("Courier", 9), state="disabled"
        )
        text_vsb = ttk.Scrollbar(text_frame, orient="vertical", command=self._report_text.yview)
        self._report_text.configure(yscrollcommand=text_vsb.set)
        self._report_text.pack(side="left", fill="both", expand=True)
        text_vsb.pack(side="right", fill="y")

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

        try:
            results = self._service.search_students(query)
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        if not results:
            self._status_var.set("No students found.")
            return

        self._search_results = results
        self._status_var.set(f"{len(results)} result(s)")

        for idx, r in enumerate(results):
            sys_label = SYSTEM_LABELS.get(r["system"], r["system"])
            self._tree.insert(
                "", "end", iid=str(idx),
                values=(
                    sys_label,
                    r.get("student_id", ""),
                    r.get("name", ""),
                    r.get("year_group", ""),
                    r.get("status", ""),
                ),
            )

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _generate_report(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Report", "Select a student from the results first.", parent=self)
            return

        idx = int(sel[0])
        if idx < 0 or idx >= len(self._search_results):
            return

        student = self._search_results[idx]
        self._status_var.set("Generating report...")
        self.update_idletasks()

        try:
            report = self._service.generate_report(
                student_name=student.get("name", ""),
                source_system=student["system"],
                student_id=student.get("student_id", ""),
            )
        except Exception as exc:
            messagebox.showerror("Report Error", str(exc), parent=self)
            self._status_var.set("Report generation failed.")
            return

        self._current_report = report
        self._report_text.configure(state="normal")
        self._report_text.delete("1.0", "end")
        self._report_text.insert("1.0", report)
        self._report_text.configure(state="disabled")
        self._status_var.set("Report generated.")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save_report(self):
        if not self._current_report:
            messagebox.showwarning("Save", "Generate a report first.", parent=self)
            return

        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Save Transition Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not filepath:
            return

        try:
            saved = self._service.save_report(self._current_report, filepath)
            messagebox.showinfo("Saved", f"Report saved to:\n{saved}", parent=self)
            self._status_var.set(f"Saved: {saved}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc), parent=self)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when the module is shown in the sidebar."""
        pass

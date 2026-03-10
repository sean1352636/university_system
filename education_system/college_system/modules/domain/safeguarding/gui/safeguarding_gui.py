"""Safeguarding GUI for managing concerns and referrals."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.safeguarding.services.safeguarding_service import SafeguardingService


class SafeguardingFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SafeguardingService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#c0392b", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Safeguarding", font=("Helvetica", 14, "bold"),
                 bg="#c0392b", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Report tab
        self._report_tab = tk.Frame(self._nb)
        self._nb.add(self._report_tab, text="Report Concern")
        self._build_report_tab()

        # Log tab
        self._log_tab = tk.Frame(self._nb)
        self._nb.add(self._log_tab, text="Concerns Log")
        self._build_log_tab()

    def _build_report_tab(self):
        form = tk.Frame(self._report_tab, padx=20, pady=20)
        form.pack(fill="both", expand=True)

        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Category*:", "category")]:
            tk.Label(form, text=label).grid(row=row, column=0, sticky="e", padx=5, pady=5)
            e = tk.Entry(form, width=30)
            e.grid(row=row, column=1, sticky="w", padx=5, pady=5)
            fields[key] = e
            row += 1

        tk.Label(form, text="Severity:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self._severity_var = tk.StringVar(value="low")
        ttk.Combobox(form, textvariable=self._severity_var,
                      values=["low", "medium", "high", "critical"],
                      state="readonly", width=27).grid(row=row, column=1, sticky="w", padx=5, pady=5)
        row += 1

        tk.Label(form, text="Description*:").grid(row=row, column=0, sticky="ne", padx=5, pady=5)
        desc_text = tk.Text(form, width=40, height=6)
        desc_text.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        fields["description"] = desc_text
        row += 1

        tk.Label(form, text="Immediate Action:").grid(row=row, column=0, sticky="ne", padx=5, pady=5)
        action_text = tk.Text(form, width=40, height=3)
        action_text.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        fields["immediate_action"] = action_text
        row += 1

        self._report_fields = fields

        def submit():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else 1
                self._svc.report_concern(
                    student_id=int(fields["student_id"].get().strip()),
                    reported_by=user_id,
                    category=fields["category"].get().strip(),
                    description=desc_text.get("1.0", "end").strip(),
                    severity=self._severity_var.get(),
                    immediate_action=action_text.get("1.0", "end").strip() or None)
                messagebox.showinfo("Success", "Concern reported")
                for w in [fields["student_id"], fields["category"]]:
                    w.delete(0, "end")
                desc_text.delete("1.0", "end")
                action_text.delete("1.0", "end")
                self._load_concerns()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(form, text="Submit Concern", command=submit).grid(row=row, column=0, columnspan=2, pady=15)

    def _build_log_tab(self):
        toolbar = tk.Frame(self._log_tab)
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Status:").pack(side="left", padx=5)
        self._log_status_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._log_status_var,
                      values=["All", "open", "investigating", "referred", "resolved", "closed"],
                      state="readonly", width=15).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Filter", command=self._load_concerns).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Update Selected", command=self._update_concern).pack(side="right", padx=5)

        cols = ("id", "student", "category", "severity", "status", "date")
        self._log_tree = ttk.Treeview(self._log_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 120, 80, 100, 120)):
            self._log_tree.heading(c, text=c.title())
            self._log_tree.column(c, width=w)
        self._log_tree.pack(fill="both", expand=True, padx=5, pady=5)

        self._detail_text = tk.Text(self._log_tab, height=6, state="disabled")
        self._detail_text.pack(fill="x", padx=5, pady=5)
        self._log_tree.bind("<<TreeviewSelect>>", self._on_concern_select)

    def _load_concerns(self):
        for item in self._log_tree.get_children():
            self._log_tree.delete(item)
        try:
            status = self._log_status_var.get()
            concerns = self._svc.list_concerns(
                status=None if status == "All" else status)
            for c in concerns:
                name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or str(c.get("student_id", ""))
                self._log_tree.insert("", "end", iid=str(c["id"]), values=(
                    c["id"], name, c.get("category", ""),
                    c.get("severity", ""), c.get("status", ""),
                    c.get("reported_date", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_concern_select(self, _event=None):
        sel = self._log_tree.selection()
        if not sel:
            return
        try:
            concern = self._svc.get_concern(int(sel[0]))
            self._detail_text.configure(state="normal")
            self._detail_text.delete("1.0", "end")
            self._detail_text.insert("end", f"Description: {concern.get('description', '')}\n")
            self._detail_text.insert("end", f"Immediate Action: {concern.get('immediate_action', '')}\n")
            self._detail_text.insert("end", f"Outcome: {concern.get('outcome', '')}\n")
            self._detail_text.insert("end", f"Notes: {concern.get('notes', '')}")
            self._detail_text.configure(state="disabled")
        except Exception:
            pass

    def _update_concern(self):
        sel = self._log_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a concern")
            return
        concern_id = int(sel[0])
        win = tk.Toplevel(self)
        win.title("Update Concern")
        win.geometry("400x300")
        row = 0
        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        status_var = tk.StringVar(value="investigating")
        ttk.Combobox(win, textvariable=status_var,
                      values=["open", "investigating", "referred", "resolved", "closed"],
                      state="readonly", width=20).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        tk.Label(win, text="Outcome:").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        outcome = tk.Text(win, width=30, height=3)
        outcome.grid(row=row, column=1, padx=10, pady=5)
        row += 1
        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        notes = tk.Text(win, width=30, height=3)
        notes.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                kwargs = {"status": status_var.get()}
                o = outcome.get("1.0", "end").strip()
                n = notes.get("1.0", "end").strip()
                if o:
                    kwargs["outcome"] = o
                if n:
                    kwargs["notes"] = n
                self._svc.update_concern(concern_id, **kwargs)
                win.destroy()
                self._load_concerns()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def refresh(self):
        self._load_concerns()

"""Behaviour GUI for managing conduct records."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.behaviour.services.behaviour_service import BehaviourService


class BehaviourFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = BehaviourService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Behaviour & Conduct", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Record tab
        self._record_tab = tk.Frame(self._nb)
        self._nb.add(self._record_tab, text="Record Incident")
        self._build_record_tab()

        # Log tab
        self._log_tab = tk.Frame(self._nb)
        self._nb.add(self._log_tab, text="Behaviour Log")
        self._build_log_tab()

    def _build_record_tab(self):
        form = tk.Frame(self._record_tab, padx=20, pady=20)
        form.pack(fill="both", expand=True)

        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Location:", "location")]:
            tk.Label(form, text=label).grid(row=row, column=0, sticky="e", padx=5, pady=5)
            e = tk.Entry(form, width=30)
            e.grid(row=row, column=1, sticky="w", padx=5, pady=5)
            fields[key] = e
            row += 1

        tk.Label(form, text="Incident Type:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self._type_var = tk.StringVar(value="negative")
        ttk.Combobox(form, textvariable=self._type_var,
                      values=["positive", "negative", "bullying", "disruption", "absence"],
                      state="readonly", width=27).grid(row=row, column=1, sticky="w", padx=5, pady=5)
        row += 1

        tk.Label(form, text="Severity:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self._sev_var = tk.StringVar(value="minor")
        ttk.Combobox(form, textvariable=self._sev_var,
                      values=["minor", "moderate", "major", "critical"],
                      state="readonly", width=27).grid(row=row, column=1, sticky="w", padx=5, pady=5)
        row += 1

        tk.Label(form, text="Description*:").grid(row=row, column=0, sticky="ne", padx=5, pady=5)
        desc_text = tk.Text(form, width=40, height=5)
        desc_text.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        fields["description"] = desc_text
        row += 1

        self._beh_fields = fields

        def submit():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else 1
                self._svc.record_incident(
                    student_id=int(fields["student_id"].get().strip()),
                    reported_by=user_id,
                    incident_type=self._type_var.get(),
                    description=desc_text.get("1.0", "end").strip(),
                    severity=self._sev_var.get(),
                    location=fields["location"].get().strip() or None)
                messagebox.showinfo("Success", "Incident recorded")
                fields["student_id"].delete(0, "end")
                fields["location"].delete(0, "end")
                desc_text.delete("1.0", "end")
                self._load_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(form, text="Submit", command=submit).grid(row=row, column=0, columnspan=2, pady=15)

    def _build_log_tab(self):
        toolbar = tk.Frame(self._log_tab)
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Type:").pack(side="left", padx=5)
        self._filter_type = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._filter_type,
                      values=["All", "positive", "negative", "bullying", "disruption", "absence"],
                      state="readonly", width=15).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Filter", command=self._load_records).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Update Selected", command=self._update_record).pack(side="right", padx=5)

        cols = ("id", "student", "type", "severity", "date", "resolved")
        self._beh_tree = ttk.Treeview(self._log_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 80, 120, 80)):
            self._beh_tree.heading(c, text=c.title())
            self._beh_tree.column(c, width=w)
        self._beh_tree.pack(fill="both", expand=True, padx=5, pady=5)

        self._beh_detail = tk.Text(self._log_tab, height=4, state="disabled")
        self._beh_detail.pack(fill="x", padx=5, pady=5)
        self._beh_tree.bind("<<TreeviewSelect>>", self._on_record_select)

    def _load_records(self):
        for item in self._beh_tree.get_children():
            self._beh_tree.delete(item)
        try:
            ft = self._filter_type.get()
            records = self._svc.list_records(
                incident_type=None if ft == "All" else ft)
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._beh_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"], name, r.get("incident_type", ""),
                    r.get("severity", ""), r.get("incident_date", ""),
                    "Yes" if r.get("resolved") else "No"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_record_select(self, _event=None):
        sel = self._beh_tree.selection()
        if not sel:
            return
        try:
            rec = self._svc.get_record(int(sel[0]))
            self._beh_detail.configure(state="normal")
            self._beh_detail.delete("1.0", "end")
            self._beh_detail.insert("end", f"Description: {rec.get('description', '')}\n")
            self._beh_detail.insert("end", f"Action Taken: {rec.get('action_taken', '')}\n")
            self._beh_detail.insert("end", f"Notes: {rec.get('notes', '')}")
            self._beh_detail.configure(state="disabled")
        except Exception:
            pass

    def _update_record(self):
        sel = self._beh_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a record")
            return
        record_id = int(sel[0])
        win = tk.Toplevel(self)
        win.title("Update Record")
        win.geometry("400x250")
        tk.Label(win, text="Action Taken:").grid(row=0, column=0, padx=10, pady=5, sticky="ne")
        action = tk.Text(win, width=30, height=3)
        action.grid(row=0, column=1, padx=10, pady=5)
        tk.Label(win, text="Notes:").grid(row=1, column=0, padx=10, pady=5, sticky="ne")
        notes = tk.Text(win, width=30, height=3)
        notes.grid(row=1, column=1, padx=10, pady=5)
        resolved_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Resolved", variable=resolved_var).grid(row=2, column=1, sticky="w", padx=10)

        def save():
            try:
                kwargs = {}
                a = action.get("1.0", "end").strip()
                n = notes.get("1.0", "end").strip()
                if a:
                    kwargs["action_taken"] = a
                if n:
                    kwargs["notes"] = n
                kwargs["resolved"] = 1 if resolved_var.get() else 0
                self._svc.update_record(record_id, **kwargs)
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=3, column=0, columnspan=2, pady=15)

    def refresh(self):
        self._load_records()

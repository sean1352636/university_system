"""GDPR Data Subject Request GUI.

Provides a tkinter Frame with tabs for searching student data across
systems, generating SAR reports, anonymising records, and reviewing
data retention.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.shared.gdpr.gdpr_service import GDPRService, SYSTEM_LABELS

HEADER_BG = "#1a5276"
HEADER_FG = "white"
BG = "#ecf0f1"

SYSTEM_KEYS = ["primary", "secondary", "sixth_form", "university"]


class GDPRComplianceFrame(tk.Frame):
    """GDPR compliance frame with search, export, anonymisation, retention tabs."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = GDPRService()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg=BG)

        # Header
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="GDPR Compliance",
            font=("Helvetica", 15, "bold"), bg=HEADER_BG, fg=HEADER_FG,
        ).pack(side="left", padx=20, pady=10)
        ttk.Button(header, text="Refresh", command=self.refresh).pack(
            side="right", padx=20, pady=10)

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_search_tab()
        self._build_export_tab()
        self._build_anonymise_tab()
        self._build_retention_tab()

    # ---- Search tab ----

    def _build_search_tab(self):
        frame = tk.Frame(self._nb, bg=BG)
        self._nb.add(frame, text="Search")

        # Search fields
        search_frame = tk.Frame(frame, bg=BG, pady=8)
        search_frame.pack(fill="x", padx=10)

        tk.Label(search_frame, text="Name:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 5))
        self._search_name_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self._search_name_var,
                  width=20).pack(side="left", padx=5)

        tk.Label(search_frame, text="Email:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(15, 5))
        self._search_email_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self._search_email_var,
                  width=20).pack(side="left", padx=5)

        tk.Label(search_frame, text="DOB:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(15, 5))
        self._search_dob_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self._search_dob_var,
                  width=12).pack(side="left", padx=5)

        ttk.Button(search_frame, text="Search",
                   command=self._do_search).pack(side="left", padx=15)

        # Results treeview
        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("system", "student_id", "name", "email", "dob", "status")
        self._search_tree = ttk.Treeview(tree_frame, columns=columns,
                                         show="headings", selectmode="browse")
        for col, heading, width in [
            ("system", "System", 130),
            ("student_id", "Student ID", 100),
            ("name", "Name", 180),
            ("email", "Email", 180),
            ("dob", "DOB", 100),
            ("status", "Status", 80),
        ]:
            self._search_tree.heading(col, text=heading)
            self._search_tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._search_tree.yview)
        self._search_tree.configure(yscrollcommand=vsb.set)
        self._search_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _do_search(self):
        self._search_tree.delete(*self._search_tree.get_children())
        name = self._search_name_var.get().strip() or None
        email = self._search_email_var.get().strip() or None
        dob = self._search_dob_var.get().strip() or None

        if not name and not email and not dob:
            messagebox.showwarning("Validation",
                                   "Enter at least one search criterion.",
                                   parent=self)
            return

        try:
            results = self._svc.search_all_systems(name=name, email=email, dob=dob)
            if not results:
                messagebox.showinfo("No Results",
                                    "No matching records found across any system.",
                                    parent=self)
                return
            for r in results:
                self._search_tree.insert("", "end", values=(
                    r["system_label"],
                    r["student_id"],
                    r["name"],
                    r["email"],
                    r["dob"],
                    r["status"],
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}", parent=self)

    # ---- Data Export tab ----

    def _build_export_tab(self):
        frame = tk.Frame(self._nb, bg=BG)
        self._nb.add(frame, text="Data Export")

        # Student name input
        input_frame = tk.Frame(frame, bg=BG, pady=8)
        input_frame.pack(fill="x", padx=10)

        tk.Label(input_frame, text="Student Name:", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 5))
        self._export_name_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self._export_name_var,
                  width=30).pack(side="left", padx=5)
        ttk.Button(input_frame, text="Generate SAR Report",
                   command=self._generate_sar).pack(side="left", padx=15)
        ttk.Button(input_frame, text="Save Report",
                   command=self._save_report).pack(side="left", padx=5)

        # Report text area
        text_frame = tk.Frame(frame)
        text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._report_text = tk.Text(text_frame, font=("Courier", 9),
                                    wrap="word", state="disabled")
        vsb = ttk.Scrollbar(text_frame, orient="vertical",
                            command=self._report_text.yview)
        self._report_text.configure(yscrollcommand=vsb.set)
        self._report_text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _generate_sar(self):
        name = self._export_name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Enter a student name.",
                                   parent=self)
            return

        try:
            report = self._svc.generate_sar_report(name)
            self._report_text.config(state="normal")
            self._report_text.delete("1.0", "end")
            self._report_text.insert("end", report)
            self._report_text.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", f"Report generation failed: {e}",
                                 parent=self)

    def _save_report(self):
        content = self._report_text.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("No Report",
                                   "Generate a report first.", parent=self)
            return

        filepath = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save SAR Report",
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Saved", f"Report saved to:\n{filepath}",
                                    parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}",
                                     parent=self)

    # ---- Anonymisation tab ----

    def _build_anonymise_tab(self):
        frame = tk.Frame(self._nb, bg=BG)
        self._nb.add(frame, text="Anonymisation")

        # Warning banner
        warn = tk.Frame(frame, bg="#e74c3c", height=40)
        warn.pack(fill="x")
        warn.pack_propagate(False)
        tk.Label(
            warn,
            text="WARNING: Anonymisation is IRREVERSIBLE. All PII will be permanently replaced.",
            bg="#e74c3c", fg="white", font=("Helvetica", 10, "bold"),
        ).pack(pady=10)

        input_frame = tk.Frame(frame, bg=BG, pady=15)
        input_frame.pack(fill="x", padx=20)

        tk.Label(input_frame, text="Student Name:", bg=BG,
                 font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=5)
        self._anon_name_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self._anon_name_var,
                  width=30).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(input_frame, text="System:", bg=BG,
                 font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky="w", padx=5, pady=5)
        self._anon_system_var = tk.StringVar(value=SYSTEM_KEYS[0])
        ttk.Combobox(input_frame, textvariable=self._anon_system_var,
                     values=SYSTEM_KEYS, state="readonly", width=27).grid(
            row=1, column=1, padx=5, pady=5)

        ttk.Button(input_frame, text="Anonymise",
                   command=self._do_anonymise).grid(
            row=2, column=0, columnspan=2, pady=20)

        # Result label
        self._anon_result_var = tk.StringVar()
        tk.Label(frame, textvariable=self._anon_result_var, bg=BG,
                 font=("Helvetica", 10), wraplength=500).pack(padx=20, pady=10)

    def _do_anonymise(self):
        name = self._anon_name_var.get().strip()
        system = self._anon_system_var.get()
        if not name:
            messagebox.showwarning("Validation", "Enter a student name.",
                                   parent=self)
            return

        # Strong confirmation: user must type the student name
        dlg = tk.Toplevel(self)
        dlg.title("Confirm Anonymisation")
        dlg.geometry("400x200")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        tk.Label(
            dlg, text=f"This will PERMANENTLY anonymise all data for\n"
                      f"'{name}' in {SYSTEM_LABELS.get(system, system)}.\n\n"
                      f"Type the student's name to confirm:",
            font=("Helvetica", 10), wraplength=350, justify="center",
        ).pack(pady=15)

        confirm_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=confirm_var, width=30).pack(pady=5)

        def _confirm():
            if confirm_var.get().strip() == name:
                dlg.destroy()
                try:
                    count = self._svc.anonymise_student(name, system)
                    self._anon_result_var.set(
                        f"Successfully anonymised {count} record(s) for "
                        f"'{name}' in {SYSTEM_LABELS.get(system, system)}."
                    )
                    messagebox.showinfo("Anonymised",
                                        f"{count} record(s) anonymised.",
                                        parent=self)
                except Exception as e:
                    self._anon_result_var.set(f"Error: {e}")
                    messagebox.showerror("Error", str(e), parent=self)
            else:
                messagebox.showwarning(
                    "Mismatch",
                    "The name you typed does not match. Anonymisation cancelled.",
                    parent=dlg,
                )

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Confirm", command=_confirm).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(
            side="left", padx=5)

    # ---- Retention tab ----

    def _build_retention_tab(self):
        frame = tk.Frame(self._nb, bg=BG)
        self._nb.add(frame, text="Retention")

        toolbar = tk.Frame(frame, bg=BG, pady=8)
        toolbar.pack(fill="x", padx=10)

        tk.Label(toolbar, text="Retention Period (years):", bg=BG,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 5))
        self._retention_years_var = tk.StringVar(value="6")
        ttk.Spinbox(toolbar, from_=1, to=25, width=5,
                    textvariable=self._retention_years_var).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Check Retention",
                   command=self._refresh_retention).pack(side="left", padx=15)

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("system", "student_id", "name", "oldest_date", "age_years")
        self._retention_tree = ttk.Treeview(tree_frame, columns=columns,
                                            show="headings", selectmode="browse")
        for col, heading, width in [
            ("system", "System", 130),
            ("student_id", "Student ID", 100),
            ("name", "Name", 180),
            ("oldest_date", "Oldest Date", 110),
            ("age_years", "Age (years)", 90),
        ]:
            self._retention_tree.heading(col, text=heading)
            self._retention_tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._retention_tree.yview)
        self._retention_tree.configure(yscrollcommand=vsb.set)
        self._retention_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _refresh_retention(self):
        self._retention_tree.delete(*self._retention_tree.get_children())
        try:
            years = int(self._retention_years_var.get())
        except ValueError:
            years = 6

        try:
            records = self._svc.get_data_retention_report(retention_years=years)
            for r in records:
                self._retention_tree.insert("", "end", values=(
                    r["system_label"],
                    r["student_id"],
                    r["name"],
                    r["oldest_date"],
                    r["age_years"],
                ))
            if not records:
                messagebox.showinfo("No Records",
                                    f"No records older than {years} years found.",
                                    parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Retention check failed: {e}",
                                 parent=self)

    # ------------------------------------------------------------------
    # Public refresh
    # ------------------------------------------------------------------

    def refresh(self):
        """Refresh retention tab (other tabs require user input)."""
        self._refresh_retention()

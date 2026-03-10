"""Bursary GUI for managing bursary records and meal eligibility."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.bursary.services.bursary_service import BursaryService


class BursaryFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = BursaryService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Bursary & Free Meals", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._bursary_tab = tk.Frame(self._nb)
        self._nb.add(self._bursary_tab, text="Bursary Records")
        self._build_bursary_tab()

        self._meals_tab = tk.Frame(self._nb)
        self._nb.add(self._meals_tab, text="Free Meals")
        self._build_meals_tab()

    def _build_bursary_tab(self):
        toolbar = tk.Frame(self._bursary_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_bursaries).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Bursary", command=self._new_bursary).pack(side="right", padx=5)

        cols = ("id", "student", "type", "amount", "status", "evidence", "frequency")
        self._bur_tree = ttk.Treeview(self._bursary_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 100, 80, 80, 80, 80)):
            self._bur_tree.heading(c, text=c.title())
            self._bur_tree.column(c, width=w)
        self._bur_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_meals_tab(self):
        toolbar = tk.Frame(self._meals_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_meals).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Set Eligibility", command=self._set_eligibility).pack(side="right", padx=5)

        cols = ("id", "student", "eligible", "evidence_type", "verified_date")
        self._meal_tree = ttk.Treeview(self._meals_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 150, 70, 120, 120)):
            self._meal_tree.heading(c, text=c.replace("_", " ").title())
            self._meal_tree.column(c, width=w)
        self._meal_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_bursaries(self):
        for item in self._bur_tree.get_children():
            self._bur_tree.delete(item)
        try:
            records = self._svc.list_bursaries()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._bur_tree.insert("", "end", values=(
                    r["id"], name, r.get("bursary_type", ""),
                    f"\u00a3{r.get('amount', 0):.2f}", r.get("status", ""),
                    "Yes" if r.get("evidence_provided") else "No",
                    r.get("payment_frequency", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_meals(self):
        for item in self._meal_tree.get_children():
            self._meal_tree.delete(item)
        try:
            records = self._svc.list_meal_eligible()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._meal_tree.insert("", "end", values=(
                    r["id"], name, "Yes" if r.get("eligible") else "No",
                    r.get("evidence_type", ""), r.get("updated_at", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_bursary(self):
        win = tk.Toplevel(self)
        win.title("New Bursary Record")
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Amount:", "amount")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_var = tk.StringVar(value="discretionary")
        ttk.Combobox(win, textvariable=type_var,
                      values=["vulnerable", "discretionary", "free_meals", "other"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        tk.Label(win, text="Frequency:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        freq_var = tk.StringVar(value="termly")
        ttk.Combobox(win, textvariable=freq_var,
                      values=["weekly", "monthly", "termly", "annual"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        ev_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Evidence Provided", variable=ev_var).grid(
            row=row, column=1, sticky="w", padx=10)
        row += 1

        def save():
            try:
                amt = fields["amount"].get().strip()
                self._svc.create_bursary(
                    student_id=int(fields["student_id"].get().strip()),
                    bursary_type=type_var.get(),
                    amount=float(amt) if amt else 0.0,
                    evidence_provided=1 if ev_var.get() else 0,
                    payment_frequency=freq_var.get())
                messagebox.showinfo("Success", "Bursary record created")
                win.destroy()
                self._load_bursaries()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _set_eligibility(self):
        win = tk.Toplevel(self)
        win.title("Set Meal Eligibility")
        win.geometry("350x200")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Evidence Type:", "evidence_type")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        elig_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="Eligible", variable=elig_var).grid(
            row=row, column=1, sticky="w", padx=10)
        row += 1

        def save():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else None
                self._svc.set_meal_eligibility(
                    student_id=int(fields["student_id"].get().strip()),
                    eligible=1 if elig_var.get() else 0,
                    evidence_type=fields["evidence_type"].get().strip() or None,
                    verified_by=user_id)
                messagebox.showinfo("Success", "Eligibility updated")
                win.destroy()
                self._load_meals()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def refresh(self):
        self._load_bursaries()
        self._load_meals()

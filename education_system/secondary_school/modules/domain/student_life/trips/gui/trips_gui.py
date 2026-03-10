"""Trips & Visits GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.trips.services.trips_service import (
    TripsService, TRIP_STATUSES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class TripsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = TripsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Trips & Visits", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="New Trip", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Students", command=self._on_view_students).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Add Student", command=self._on_add_student).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Risk Assessment Done", command=self._on_risk).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("title", "destination", "date", "year", "lead", "max", "cost", "risk", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("title", "Title", 150), ("destination", "Destination", 110),
                           ("date", "Date", 80), ("year", "Year", 40), ("lead", "Lead", 90),
                           ("max", "Max", 35), ("cost", "Cost", 50),
                           ("risk", "Risk", 40), ("status", "Status", 70)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        try:
            trips = self._svc.list_trips()
            for t in trips:
                self._tree.insert("", "end", iid=t["id"], values=(
                    t["title"], t.get("destination") or "", t["date"],
                    t.get("year_group") or "", t.get("lead_teacher") or "",
                    t.get("max_students") or "", f"£{t['cost_per_student']:.2f}" if t.get("cost_per_student") else "",
                    "Yes" if t["risk_assessment_done"] else "No", t["status"]))
            self._status_var.set(f"{len(trips)} trip(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Trip")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Title", "title", ""), ("Destination", "destination", ""),
                  ("Date (YYYY-MM-DD)", "date", ""), ("Return Date", "return_date", ""),
                  ("Departure Time", "departure_time", ""), ("Return Time", "return_time", ""),
                  ("Year Group", "year_group", ""), ("Lead Teacher", "lead_teacher", ""),
                  ("Max Students", "max_students", ""), ("Cost Per Student (£)", "cost", "0"),
                  ("Transport", "transport", "")]
        for row, (l, k, d) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            t = vars_["title"].get().strip()
            d = vars_["date"].get().strip()
            if not t or not d:
                messagebox.showwarning("Validation", "Title and date required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Create", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            cost = float(d["cost"]) if d["cost"] else 0.0
        except ValueError:
            cost = 0.0
        try:
            max_s = int(d["max_students"]) if d["max_students"] else None
        except ValueError:
            max_s = None
        try:
            self._svc.create_trip(d["title"], d["date"], d["destination"] or None,
                                  d["return_date"] or None, d["departure_time"] or None,
                                  d["return_time"] or None, d["year_group"] or None,
                                  d["lead_teacher"] or None, max_s, cost,
                                  d["transport"] or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_view_students(self):
        sel = self._tree.selection()
        if not sel:
            return
        trip_id = int(sel[0])
        students = self._svc.list_trip_students(trip_id)
        dlg = tk.Toplevel(self)
        dlg.title(f"Trip Students ({len(students)})")
        dlg.geometry("600x350")
        cols = ("student", "year", "consent", "paid", "medical")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("student", "Student", 150), ("year", "Year", 50),
                           ("consent", "Consent", 60), ("paid", "Paid", 50), ("medical", "Medical Notes", 200)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in students:
            tree.insert("", "end", iid=s["id"], values=(
                f"{s['first_name']} {s['last_name']}", s.get("year_group") or "",
                "Yes" if s["consent_received"] else "No",
                "Yes" if s["paid"] else "No", s.get("medical_notes") or ""))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        def mark_consent():
            s = tree.selection()
            if s:
                self._svc.update_consent(int(s[0]))
                for item in tree.get_children():
                    tree.delete(item)
                for st in self._svc.list_trip_students(trip_id):
                    tree.insert("", "end", iid=st["id"], values=(
                        f"{st['first_name']} {st['last_name']}", st.get("year_group") or "",
                        "Yes" if st["consent_received"] else "No",
                        "Yes" if st["paid"] else "No", st.get("medical_notes") or ""))

        def mark_paid():
            s = tree.selection()
            if s:
                self._svc.update_payment(int(s[0]))
                for item in tree.get_children():
                    tree.delete(item)
                for st in self._svc.list_trip_students(trip_id):
                    tree.insert("", "end", iid=st["id"], values=(
                        f"{st['first_name']} {st['last_name']}", st.get("year_group") or "",
                        "Yes" if st["consent_received"] else "No",
                        "Yes" if st["paid"] else "No", st.get("medical_notes") or ""))

        ttk.Button(btn_frame, text="Mark Consent", command=mark_consent).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Mark Paid", command=mark_paid).pack(side="left", padx=4)

    def _on_add_student(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a trip first.")
            return
        trip_id = int(sel[0])
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Student to Trip")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=0, column=1, **pad)
        ec_var = tk.StringVar()
        tk.Label(c, text="Emergency Contact", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=ec_var, width=20).grid(row=1, column=1, **pad)
        ep_var = tk.StringVar()
        tk.Label(c, text="Emergency Phone", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=ep_var, width=20).grid(row=2, column=1, **pad)
        result = [None]
        def save():
            sv = stu_var.get()
            if not sv:
                messagebox.showwarning("Validation", "Select a student.")
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"student_id": spk, "ec": ec_var.get().strip() or None, "ep": ep_var.get().strip() or None}
            dlg.destroy()
        ttk.Button(c, text="Add", command=save).grid(row=3, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.add_student(trip_id, d["student_id"], d["ec"], d["ep"])
            messagebox.showinfo("Success", "Student added to trip.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_risk(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.mark_risk_assessment(int(sel[0]))
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this trip and all student registrations?"):
            self._svc.delete_trip(int(sel[0]))
            self._load()

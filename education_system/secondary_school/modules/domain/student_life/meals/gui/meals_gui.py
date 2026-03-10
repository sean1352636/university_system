"""School Meals GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.meals.services.meals_service import (
    MealsService, MEAL_PREFERENCES, MEAL_TYPES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class MealsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = MealsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="School Meals", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        # --- Registrations tab ---
        reg_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(reg_tab, text="Registrations")
        rt = tk.Frame(reg_tab, bg=MAIN_BG, pady=8)
        rt.pack(fill="x", padx=10)
        ttk.Button(rt, text="Register Student", command=self._on_register).pack(side="left", padx=4)
        ttk.Button(rt, text="Delete", command=self._on_delete_reg).pack(side="left", padx=4)
        self._fsm_var = tk.BooleanVar()
        ttk.Checkbutton(rt, text="FSM Only", variable=self._fsm_var,
                        command=self._load_registrations).pack(side="left", padx=10)

        rf = tk.Frame(reg_tab)
        rf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("student", "year", "preference", "fsm", "dietary", "allergies")
        self._reg_tree = ttk.Treeview(rf, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 130), ("year", "Year", 40),
                           ("preference", "Preference", 90), ("fsm", "FSM", 40),
                           ("dietary", "Dietary Reqs", 130), ("allergies", "Allergies", 130)]:
            self._reg_tree.heading(col, text=h)
            self._reg_tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(rf, orient="vertical", command=self._reg_tree.yview)
        self._reg_tree.configure(yscrollcommand=vsb.set)
        self._reg_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- Bookings tab ---
        book_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(book_tab, text="Bookings")
        bt = tk.Frame(book_tab, bg=MAIN_BG, pady=8)
        bt.pack(fill="x", padx=10)
        ttk.Button(bt, text="Book Meal", command=self._on_book).pack(side="left", padx=4)
        ttk.Button(bt, text="Cancel Booking", command=self._on_cancel_booking).pack(side="left", padx=4)

        bf = tk.Frame(book_tab)
        bf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        bcols = ("date", "student", "type", "choice", "status")
        self._book_tree = ttk.Treeview(bf, columns=bcols, show="headings", selectmode="browse")
        for col, h, w in [("date", "Date", 90), ("student", "Student", 140),
                           ("type", "Type", 70), ("choice", "Choice", 120), ("status", "Status", 70)]:
            self._book_tree.heading(col, text=h)
            self._book_tree.column(col, width=w, anchor="center")
        bvsb = ttk.Scrollbar(bf, orient="vertical", command=self._book_tree.yview)
        self._book_tree.configure(yscrollcommand=bvsb.set)
        self._book_tree.pack(side="left", fill="both", expand=True)
        bvsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_registrations()
        self._load_bookings()

    def _load_registrations(self):
        self._reg_tree.delete(*self._reg_tree.get_children())
        try:
            regs = self._svc.list_registrations(fsm_only=self._fsm_var.get())
            for r in regs:
                self._reg_tree.insert("", "end", iid=r["id"], values=(
                    f"{r['first_name']} {r['last_name']}", r.get("year_group") or "",
                    r["meal_preference"], "Yes" if r["free_school_meals"] else "No",
                    r.get("dietary_requirements") or "", r.get("allergies") or ""))
            fsm = self._svc.fsm_count()
            self._status_var.set(f"{len(regs)} registration(s) | FSM: {fsm}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_bookings(self):
        self._book_tree.delete(*self._book_tree.get_children())
        try:
            bookings = self._svc.list_bookings()
            for b in bookings:
                self._book_tree.insert("", "end", iid=b["id"], values=(
                    b["date"], f"{b['first_name']} {b['last_name']}",
                    b["meal_type"], b.get("menu_choice") or "", b["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_register(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Register for Meals")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=0, column=1, **pad)
        pref_var = tk.StringVar(value="standard")
        tk.Label(c, text="Preference", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=pref_var, values=list(MEAL_PREFERENCES), state="readonly", width=20).grid(row=1, column=1, **pad)
        diet_var = tk.StringVar()
        tk.Label(c, text="Dietary Reqs", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=diet_var, width=25).grid(row=2, column=1, **pad)
        allergy_var = tk.StringVar()
        tk.Label(c, text="Allergies", font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=allergy_var, width=25).grid(row=3, column=1, **pad)
        fsm_var = tk.BooleanVar()
        ttk.Checkbutton(c, text="Free School Meals", variable=fsm_var).grid(row=4, column=1, sticky="w", **pad)
        result = [None]
        def save():
            sv = stu_var.get()
            if not sv:
                messagebox.showwarning("Validation", "Select a student.")
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"student_id": spk, "fsm": fsm_var.get(), "pref": pref_var.get(),
                         "dietary": diet_var.get().strip() or None, "allergies": allergy_var.get().strip() or None}
            dlg.destroy()
        ttk.Button(c, text="Register", command=save).grid(row=5, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.register_student(d["student_id"], d["fsm"], d["dietary"], d["allergies"], d["pref"])
            self._load_registrations()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete_reg(self):
        sel = self._reg_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Remove this meal registration?"):
            self._svc.delete_registration(int(sel[0]))
            self._load_registrations()

    def _on_book(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Book Meal")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=0, column=1, **pad)
        date_var = tk.StringVar()
        tk.Label(c, text="Date (YYYY-MM-DD)", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=date_var, width=15).grid(row=1, column=1, sticky="w", **pad)
        type_var = tk.StringVar(value="lunch")
        tk.Label(c, text="Meal Type", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=type_var, values=list(MEAL_TYPES), state="readonly", width=12).grid(row=2, column=1, sticky="w", **pad)
        choice_var = tk.StringVar()
        tk.Label(c, text="Menu Choice", font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=choice_var, width=20).grid(row=3, column=1, **pad)
        result = [None]
        def save():
            sv = stu_var.get()
            dt = date_var.get().strip()
            if not sv or not dt:
                messagebox.showwarning("Validation", "Student and date required.")
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"student_id": spk, "date": dt, "type": type_var.get(),
                         "choice": choice_var.get().strip() or None}
            dlg.destroy()
        ttk.Button(c, text="Book", command=save).grid(row=4, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.book_meal(d["student_id"], d["date"], d["type"], d["choice"])
            self._load_bookings()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_cancel_booking(self):
        sel = self._book_tree.selection()
        if not sel:
            return
        self._svc.cancel_booking(int(sel[0]))
        self._load_bookings()

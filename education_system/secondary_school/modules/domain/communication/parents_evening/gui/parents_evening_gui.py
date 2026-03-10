"""Parents evening GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.communication.parents_evening.services.parents_evening_service import ParentsEveningService
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.core.exceptions import ParentsEveningError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class ParentsEveningFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._svc = ParentsEveningService(db_path)
        self._stu_svc = StudentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Parents Evening", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Create Event", command=self._on_create).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Book Slot", command=self._on_book).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Slots", command=self._on_view_slots).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Event", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("title", "year", "date", "start", "end", "slot_mins", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("title", "Title", 180), ("year", "Year", 40), ("date", "Date", 85),
                           ("start", "Start", 55), ("end", "End", 55), ("slot_mins", "Slot (min)", 60),
                           ("status", "Status", 60)]:
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
            events = self._svc.list_events()
            for e in events:
                self._tree.insert("", "end", iid=e["id"], values=(
                    e["title"], e.get("year_group") or "All", e["date"],
                    e["start_time"], e["end_time"], e["slot_duration_minutes"], e["status"]))
            self._status_var.set(f"{len(events)} event(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_create(self):
        dlg = tk.Toplevel(self)
        dlg.title("Create Parents Evening")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        for row, (l, k, d) in enumerate([("Title", "title", ""), ("Year Group", "year_group", ""),
                                           ("Date (YYYY-MM-DD)", "date", ""), ("Start Time", "start_time", "16:00"),
                                           ("End Time", "end_time", "19:00"), ("Slot Duration (mins)", "slot_mins", "5")]):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            if not vars_["title"].get().strip() or not vars_["date"].get().strip():
                messagebox.showwarning("Validation", "Title and date required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).grid(row=6, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            sm = int(d["slot_mins"]) if d["slot_mins"] else 5
        except ValueError:
            sm = 5
        try:
            self._svc.create_event(d["title"], d["date"], d["year_group"] or None,
                                   d["start_time"] or "16:00", d["end_time"] or "19:00", sm)
            messagebox.showinfo("Success", "Parents evening created.")
            self._load()
        except ParentsEveningError as e:
            messagebox.showerror("Error", str(e))

    def _on_book(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an event first.")
            return
        event_id = int(sel[0])
        students = self._stu_svc.list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Book Slot")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        for row, (l, k, d, vals) in enumerate([
            ("Student", "student", "", stu_names), ("Teacher", "teacher", "", None),
            ("Time Slot (HH:MM)", "time_slot", "", None), ("Parent Name", "parent_name", "", None)]):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=28).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=30).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            sv = vars_["student"].get()
            t = vars_["teacher"].get().strip()
            ts = vars_["time_slot"].get().strip()
            if not sv or not t or not ts:
                messagebox.showwarning("Validation", "Student, teacher and time slot required.")
                return
            sid = sv.split(" - ")[0]
            stu_pk = next((s["id"] for s in students if s["student_id"] == sid), None)
            result[0] = {"event_id": event_id, "teacher": t, "student_id": stu_pk,
                         "time_slot": ts, "parent_name": vars_["parent_name"].get().strip() or None}
            dlg.destroy()
        ttk.Button(c, text="Book", command=save).grid(row=4, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        try:
            self._svc.book_slot(**result[0])
            messagebox.showinfo("Booked", "Slot booked.")
        except ParentsEveningError as e:
            messagebox.showerror("Error", str(e))

    def _on_view_slots(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an event.")
            return
        slots = self._svc.list_slots(int(sel[0]))
        dlg = tk.Toplevel(self)
        dlg.title("Booked Slots")
        dlg.geometry("550x350")
        cols = ("time", "teacher", "student", "parent")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("time", "Time", 60), ("teacher", "Teacher", 120),
                           ("student", "Student", 150), ("parent", "Parent", 120)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in slots:
            tree.insert("", "end", values=(s["time_slot"], s["teacher"],
                        f"{s['first_name']} {s['last_name']}", s.get("parent_name") or ""))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this event and all its bookings?"):
            self._svc.delete_event(int(sel[0]))
            self._load()

"""School Transport GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.transport.services.transport_service import (
    TransportService, VEHICLE_TYPES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class TransportFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = TransportService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="School Transport", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="New Route", command=self._on_add_route).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Stops", command=self._on_view_stops).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Add Stop", command=self._on_add_stop).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Students", command=self._on_view_students).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Assign Student", command=self._on_assign).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Route", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("route", "operator", "vehicle", "capacity", "students", "driver", "depart", "return")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("route", "Route", 120), ("operator", "Operator", 90),
                           ("vehicle", "Vehicle", 60), ("capacity", "Cap", 35),
                           ("students", "Students", 55), ("driver", "Driver", 90),
                           ("depart", "Depart", 55), ("return", "Return", 55)]:
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
            routes = self._svc.list_routes()
            for r in routes:
                cnt = self._svc.student_count(r["id"])
                self._tree.insert("", "end", iid=r["id"], values=(
                    r["route_name"], r.get("operator") or "", r.get("vehicle_type") or "",
                    r.get("capacity") or "", cnt, r.get("driver_name") or "",
                    r.get("departure_time") or "", r.get("return_time") or ""))
            self._status_var.set(f"{len(routes)} route(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add_route(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Route")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Route Name", "name", "", None), ("Operator", "operator", "", None),
                  ("Vehicle Type", "vehicle", "bus", list(VEHICLE_TYPES)),
                  ("Capacity", "capacity", "", None), ("Driver Name", "driver", "", None),
                  ("Driver Phone", "phone", "", None),
                  ("Departure Time", "depart", "", None), ("Return Time", "return", "", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=15).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=20).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            n = vars_["name"].get().strip()
            if not n:
                messagebox.showwarning("Validation", "Route name required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Create", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            cap = int(d["capacity"]) if d["capacity"] else None
        except ValueError:
            cap = None
        try:
            self._svc.create_route(d["name"], d.get("operator") or None,
                                   d.get("vehicle") or "bus", cap,
                                   d.get("driver") or None, d.get("phone") or None,
                                   d.get("depart") or None, d.get("return") or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_view_stops(self):
        sel = self._tree.selection()
        if not sel:
            return
        stops = self._svc.list_stops(int(sel[0]))
        dlg = tk.Toplevel(self)
        dlg.title(f"Stops ({len(stops)})")
        dlg.geometry("400x250")
        cols = ("stop", "pickup", "dropoff")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("stop", "Stop", 180), ("pickup", "Pickup", 70), ("dropoff", "Drop-off", 70)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in stops:
            tree.insert("", "end", values=(s["stop_name"], s.get("pickup_time") or "", s.get("dropoff_time") or ""))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_add_stop(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a route first.")
            return
        route_id = int(sel[0])
        dlg = tk.Toplevel(self)
        dlg.title("Add Stop")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        name_var = tk.StringVar()
        pk_var = tk.StringVar()
        do_var = tk.StringVar()
        tk.Label(c, text="Stop Name", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=name_var, width=20).grid(row=0, column=1, **pad)
        tk.Label(c, text="Pickup Time", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=pk_var, width=10).grid(row=1, column=1, sticky="w", **pad)
        tk.Label(c, text="Drop-off Time", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=do_var, width=10).grid(row=2, column=1, sticky="w", **pad)
        result = [None]
        def save():
            n = name_var.get().strip()
            if not n:
                return
            result[0] = {"name": n, "pk": pk_var.get().strip() or None, "do": do_var.get().strip() or None}
            dlg.destroy()
        ttk.Button(c, text="Add", command=save).grid(row=3, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0]:
            try:
                self._svc.add_stop(route_id, result[0]["name"], result[0]["pk"], result[0]["do"])
                messagebox.showinfo("Success", "Stop added.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_view_students(self):
        sel = self._tree.selection()
        if not sel:
            return
        students = self._svc.list_route_students(int(sel[0]))
        dlg = tk.Toplevel(self)
        dlg.title(f"Students ({len(students)})")
        dlg.geometry("450x300")
        cols = ("student", "year", "stop")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("student", "Student", 160), ("year", "Year", 50), ("stop", "Stop", 150)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in students:
            tree.insert("", "end", values=(
                f"{s['first_name']} {s['last_name']}", s.get("year_group") or "",
                s.get("stop_name") or ""))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_assign(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a route first.")
            return
        route_id = int(sel[0])
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Assign Student")
        dlg.resizable(False, False)
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).pack(pady=5)
        result = [None]
        def save():
            sv = stu_var.get()
            if not sv:
                return
            sid_str = sv.split(" - ")[0]
            result[0] = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            dlg.destroy()
        ttk.Button(c, text="Assign", command=save).pack(pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        try:
            self._svc.assign_student(route_id, result[0])
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this route, stops and student assignments?"):
            self._svc.delete_route(int(sel[0]))
            self._load()

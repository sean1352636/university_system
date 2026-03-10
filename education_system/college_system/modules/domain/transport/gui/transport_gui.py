"""Transport GUI for managing student transport records."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.transport.services.transport_service import TransportService


class TransportFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = TransportService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Transport", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=5)
        tk.Label(toolbar, text="Type:").pack(side="left", padx=5)
        self._type_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._type_var,
                      values=["All", "bus", "train", "taxi", "walking", "cycling", "car"],
                      state="readonly", width=12).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Filter", command=self._load_records).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Record", command=self._new_record).pack(side="right", padx=5)

        cols = ("id", "student", "type", "route", "pickup", "pass_no", "cost", "funded", "status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 120, 70, 100, 100, 80, 60, 50, 70)):
            self._tree.heading(c, text=c.replace("_", " ").title())
            self._tree.column(c, width=w)
        self._tree.pack(fill="both", expand=True, padx=10, pady=5)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Edit", command=self._edit_record).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete", command=self._delete_record).pack(side="left", padx=5)

    def _load_records(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            t = self._type_var.get()
            records = self._svc.list_records(transport_type=None if t == "All" else t)
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"], name, r.get("transport_type", ""), r.get("route", ""),
                    r.get("pickup_point", ""), r.get("pass_number", ""),
                    f"\u00a3{r.get('cost', 0) or 0:.2f}",
                    "Yes" if r.get("funded") else "No", r.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_record(self):
        win = tk.Toplevel(self)
        win.title("New Transport Record")
        win.geometry("400x350")
        fields = {}
        row = 0
        for label, key in [("Student ID*:", "student_id"), ("Route:", "route"),
                           ("Pickup Point:", "pickup_point"), ("Pass Number:", "pass_number"),
                           ("Cost:", "cost")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_var = tk.StringVar(value="bus")
        ttk.Combobox(win, textvariable=type_var,
                      values=["bus", "train", "taxi", "walking", "cycling", "car"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1
        funded_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Funded", variable=funded_var).grid(
            row=row, column=1, sticky="w", padx=10)
        row += 1

        def save():
            try:
                cost = fields["cost"].get().strip()
                self._svc.create_record(
                    student_id=int(fields["student_id"].get().strip()),
                    transport_type=type_var.get(),
                    route=fields["route"].get().strip() or None,
                    pickup_point=fields["pickup_point"].get().strip() or None,
                    pass_number=fields["pass_number"].get().strip() or None,
                    cost=float(cost) if cost else None,
                    funded=1 if funded_var.get() else 0)
                messagebox.showinfo("Success", "Record created")
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _edit_record(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a record")
            return
        record_id = int(sel[0])
        try:
            rec = self._svc.get_record(record_id)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        win = tk.Toplevel(self)
        win.title("Edit Transport Record")
        win.geometry("400x250")
        fields = {}
        row = 0
        for label, key in [("Route:", "route"), ("Pickup Point:", "pickup_point"),
                           ("Pass Number:", "pass_number")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.insert(0, rec.get(key, "") or "")
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        status_var = tk.StringVar(value=rec.get("status", "active"))
        ttk.Combobox(win, textvariable=status_var,
                      values=["active", "suspended", "cancelled"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                self._svc.update_record(record_id,
                    route=fields["route"].get().strip() or None,
                    pickup_point=fields["pickup_point"].get().strip() or None,
                    pass_number=fields["pass_number"].get().strip() or None,
                    status=status_var.get())
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _delete_record(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a record")
            return
        if messagebox.askyesno("Confirm", "Delete this transport record?"):
            try:
                self._svc.delete_record(int(sel[0]))
                self._load_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load_records()

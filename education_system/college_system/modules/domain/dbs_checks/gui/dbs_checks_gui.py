"""DBS Checks GUI frame for managing DBS/disclosure checks."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.dbs_checks.services.dbs_checks_service import DBSCheckService

CHECK_TYPES = ["enhanced", "standard", "basic", "enhanced_barred"]
STATUSES = ["valid", "expired", "pending", "revoked"]


class DBSCheckFrame(tk.Frame):
    """DBS Checks management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DBSCheckService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="DBS Checks",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._checks_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._checks_tab, text="All Checks")
        self._build_checks_tab()

        self._expiring_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._expiring_tab, text="Expiring Soon")
        self._build_expiring_tab()

        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text="Statistics")
        self._build_stats_tab()

    # ---- Checks Tab ----

    def _build_checks_tab(self):
        toolbar = tk.Frame(self._checks_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Search:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._search = tk.Entry(toolbar, width=14)
        self._search.pack(side="left", padx=2)
        self._search.bind("<Return>", lambda e: self._load_checks())

        tk.Label(toolbar, text="Status:", bg="#ecf0f1").pack(side="left", padx=(8, 2))
        self._filter_status = ttk.Combobox(toolbar, width=10, state="readonly",
                                            values=[""] + STATUSES)
        self._filter_status.set("")
        self._filter_status.pack(side="left", padx=2)

        tk.Label(toolbar, text="Type:", bg="#ecf0f1").pack(side="left", padx=(8, 2))
        self._filter_type = ttk.Combobox(toolbar, width=12, state="readonly",
                                          values=[""] + CHECK_TYPES)
        self._filter_type.set("")
        self._filter_type.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Search", command=self._load_checks).pack(side="left", padx=5)

        btn_frame = tk.Frame(self._checks_tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text="Refresh", command=self._load_checks).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="New Check", command=self._new_check).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="View", command=self._view_check).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._edit_check).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_check).pack(side="right", padx=2)

        cols = ("id", "person", "type", "cert_no", "issue", "expiry",
                "update_svc", "status")
        self._tree = ttk.Treeview(self._checks_tab, columns=cols,
                                   show="headings", height=16)
        for c, w, label in [
            ("id", 40, "ID"), ("person", 160, "Person"),
            ("type", 100, "Type"), ("cert_no", 120, "Certificate #"),
            ("issue", 90, "Issue Date"), ("expiry", 90, "Expiry Date"),
            ("update_svc", 70, "Update"), ("status", 70, "Status"),
        ]:
            self._tree.heading(c, text=label)
            self._tree.column(c, width=w,
                               anchor="center" if w < 100 else "w")
        self._tree.bind("<Double-1>", lambda e: self._view_check())

        vsb = ttk.Scrollbar(self._checks_tab, orient="vertical",
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True,
                         padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _person_label(self, r):
        if r.get("volunteer_name"):
            return f"Vol: {r['volunteer_name']}"
        if r.get("staff_id"):
            return f"Staff #{r['staff_id']}"
        if r.get("governor_id"):
            return f"Governor #{r['governor_id']}"
        return "Unknown"

    def _load_checks(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            search = self._search.get().strip() or None
            status = self._filter_status.get().strip() or None
            ctype = self._filter_type.get().strip() or None
            records = self._svc.list_checks(
                search=search, status=status, check_type=ctype)
            for r in records:
                self._tree.insert("", "end", iid=r["id"], values=(
                    r["id"], self._person_label(r),
                    r.get("check_type", ""), r.get("certificate_number", ""),
                    r.get("issue_date", ""), r.get("expiry_date", ""),
                    "Yes" if r.get("update_service") else "No",
                    r.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a check first.")
            return None
        return int(sel[0])

    def _new_check(self):
        win = tk.Toplevel(self)
        win.title("New DBS Check")
        win.geometry("460x500")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Staff ID:", "staff_id"), ("Governor ID:", "governor_id"),
            ("Volunteer Name:", "volunteer_name"),
            ("Certificate Number:", "certificate_number"),
            ("Issue Date (YYYY-MM-DD):", "issue_date"),
            ("Expiry Date (YYYY-MM-DD):", "expiry_date"),
            ("Update Service ID:", "update_service_id"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text="Check Type:").grid(row=row, column=0, padx=10,
                                                pady=4, sticky="e")
        type_cb = ttk.Combobox(win, width=25, state="readonly",
                                values=CHECK_TYPES)
        type_cb.set("enhanced")
        type_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        update_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="On DBS Update Service",
                         variable=update_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        barred_var = tk.BooleanVar()
        ttk.Checkbutton(win, text="Barred List Checked",
                         variable=barred_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        children_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="Children's Workforce",
                         variable=children_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10,
                                           pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=28, height=3)
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            sid = fields["staff_id"].get().strip()
            gid = fields["governor_id"].get().strip()
            vname = fields["volunteer_name"].get().strip()
            if not sid and not gid and not vname:
                messagebox.showwarning("Validation",
                                        "Specify staff ID, governor ID, or volunteer name.")
                return
            try:
                self._svc.create_check(
                    staff_id=int(sid) if sid else None,
                    governor_id=int(gid) if gid else None,
                    volunteer_name=vname or None,
                    check_type=type_cb.get(),
                    certificate_number=fields["certificate_number"].get().strip() or None,
                    issue_date=fields["issue_date"].get().strip() or None,
                    expiry_date=fields["expiry_date"].get().strip() or None,
                    update_service=1 if update_var.get() else 0,
                    update_service_id=fields["update_service_id"].get().strip() or None,
                    barred_list_checked=1 if barred_var.get() else 0,
                    children_workforce=1 if children_var.get() else 0,
                    notes=notes_txt.get("1.0", "end-1c").strip() or None)
                messagebox.showinfo("Success", "DBS check recorded.")
                win.destroy()
                self._load_checks()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _view_check(self):
        cid = self._selected_id()
        if not cid:
            return
        rec = self._svc.get_check(cid)
        if not rec:
            messagebox.showwarning("Not Found", "Check not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"DBS Check #{cid}")
        win.geometry("420x420")
        win.resizable(False, False)

        display = [
            ("ID", rec.get("id")),
            ("Person", self._person_label(rec)),
            ("Check Type", rec.get("check_type")),
            ("Certificate #", rec.get("certificate_number")),
            ("Issue Date", rec.get("issue_date")),
            ("Expiry Date", rec.get("expiry_date")),
            ("Update Service", "Yes" if rec.get("update_service") else "No"),
            ("Update Service ID", rec.get("update_service_id")),
            ("Barred List Checked", "Yes" if rec.get("barred_list_checked") else "No"),
            ("Children's Workforce", "Yes" if rec.get("children_workforce") else "No"),
            ("Status", rec.get("status")),
            ("Notes", rec.get("notes")),
            ("Created", rec.get("created_at")),
            ("Updated", rec.get("updated_at")),
        ]

        frame = tk.Frame(win, padx=15, pady=10)
        frame.pack(fill="both", expand=True)
        for i, (lbl, val) in enumerate(display):
            tk.Label(frame, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, sticky="ne",
                                       padx=(0, 8), pady=2)
            tk.Label(frame, text=str(val or ""), anchor="w",
                     wraplength=260).grid(row=i, column=1, sticky="w", pady=2)

    def _edit_check(self):
        cid = self._selected_id()
        if not cid:
            return
        rec = self._svc.get_check(cid)
        if not rec:
            messagebox.showwarning("Not Found", "Check not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Edit DBS Check #{cid}")
        win.geometry("460x520")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Staff ID:", "staff_id"), ("Governor ID:", "governor_id"),
            ("Volunteer Name:", "volunteer_name"),
            ("Certificate Number:", "certificate_number"),
            ("Issue Date:", "issue_date"), ("Expiry Date:", "expiry_date"),
            ("Update Service ID:", "update_service_id"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=28)
            e.insert(0, str(rec.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text="Check Type:").grid(row=row, column=0, padx=10,
                                                pady=4, sticky="e")
        type_cb = ttk.Combobox(win, width=25, state="readonly",
                                values=CHECK_TYPES)
        type_cb.set(rec.get("check_type", "enhanced"))
        type_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
        status_cb = ttk.Combobox(win, width=25, state="readonly",
                                  values=STATUSES)
        status_cb.set(rec.get("status", "valid"))
        status_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        update_var = tk.BooleanVar(value=bool(rec.get("update_service")))
        ttk.Checkbutton(win, text="On DBS Update Service",
                         variable=update_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        barred_var = tk.BooleanVar(value=bool(rec.get("barred_list_checked")))
        ttk.Checkbutton(win, text="Barred List Checked",
                         variable=barred_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        children_var = tk.BooleanVar(value=bool(rec.get("children_workforce")))
        ttk.Checkbutton(win, text="Children's Workforce",
                         variable=children_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10,
                                           pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=28, height=3)
        notes_txt.insert("1.0", rec.get("notes", "") or "")
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                sid = fields["staff_id"].get().strip()
                gid = fields["governor_id"].get().strip()
                self._svc.update_check(
                    cid,
                    staff_id=int(sid) if sid else None,
                    governor_id=int(gid) if gid else None,
                    volunteer_name=fields["volunteer_name"].get().strip() or None,
                    check_type=type_cb.get(),
                    status=status_cb.get(),
                    certificate_number=fields["certificate_number"].get().strip() or None,
                    issue_date=fields["issue_date"].get().strip() or None,
                    expiry_date=fields["expiry_date"].get().strip() or None,
                    update_service=1 if update_var.get() else 0,
                    update_service_id=fields["update_service_id"].get().strip() or None,
                    barred_list_checked=1 if barred_var.get() else 0,
                    children_workforce=1 if children_var.get() else 0,
                    notes=notes_txt.get("1.0", "end-1c").strip() or None)
                messagebox.showinfo("Success", "DBS check updated.")
                win.destroy()
                self._load_checks()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_check(self):
        cid = self._selected_id()
        if not cid:
            return
        if not messagebox.askyesno("Confirm", f"Delete DBS check #{cid}?"):
            return
        try:
            self._svc.delete_check(cid)
            messagebox.showinfo("Deleted", "DBS check deleted.")
            self._load_checks()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Expiring Tab ----

    def _build_expiring_tab(self):
        toolbar = tk.Frame(self._expiring_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Expiring within (days):",
                 bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._exp_days = ttk.Spinbox(toolbar, from_=30, to=365, width=6)
        self._exp_days.set("90")
        self._exp_days.pack(side="left", padx=2)
        ttk.Button(toolbar, text="Load",
                   command=self._load_expiring).pack(side="left", padx=5)

        cols = ("id", "person", "type", "cert_no", "expiry", "status")
        self._exp_tree = ttk.Treeview(self._expiring_tab, columns=cols,
                                       show="headings", height=18)
        for c, w, label in [
            ("id", 40, "ID"), ("person", 180, "Person"),
            ("type", 100, "Type"), ("cert_no", 130, "Certificate #"),
            ("expiry", 100, "Expiry Date"), ("status", 80, "Status"),
        ]:
            self._exp_tree.heading(c, text=label)
            self._exp_tree.column(c, width=w,
                                   anchor="center" if w < 100 else "w")

        vsb = ttk.Scrollbar(self._expiring_tab, orient="vertical",
                             command=self._exp_tree.yview)
        self._exp_tree.configure(yscrollcommand=vsb.set)
        self._exp_tree.pack(side="left", fill="both", expand=True,
                             padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_expiring(self):
        for item in self._exp_tree.get_children():
            self._exp_tree.delete(item)
        try:
            days = int(self._exp_days.get())
            records = self._svc.get_expiring(days)
            for r in records:
                self._exp_tree.insert("", "end", values=(
                    r["id"], self._person_label(r),
                    r.get("check_type", ""), r.get("certificate_number", ""),
                    r.get("expiry_date", ""), r.get("status", "")))
            if not records:
                messagebox.showinfo("Info", "No checks expiring in that period.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1",
                                      padx=20, pady=20)
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(self._stats_frame, text="Refresh Statistics",
                   command=self._load_stats).pack(anchor="w", pady=(0, 15))

        self._stats_labels = {}
        for key, label in [
            ("total", "Total Checks"),
            ("valid", "Valid"),
            ("expired", "Expired"),
            ("pending", "Pending"),
            ("on_update_service", "On Update Service"),
            ("expiring_90_days", "Expiring within 90 days"),
        ]:
            row_frame = tk.Frame(self._stats_frame, bg="#ecf0f1")
            row_frame.pack(fill="x", pady=3)
            tk.Label(row_frame, text=f"{label}:",
                     font=("Helvetica", 11, "bold"), bg="#ecf0f1",
                     width=24, anchor="e").pack(side="left")
            lbl = tk.Label(row_frame, text="—", font=("Helvetica", 11),
                           bg="#ecf0f1", anchor="w")
            lbl.pack(side="left", padx=(10, 0))
            self._stats_labels[key] = lbl

        tk.Label(self._stats_frame, text="By Type:",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", pady=(15, 5))
        self._type_lbl = tk.Label(self._stats_frame, text="—",
                                   font=("Helvetica", 10), bg="#ecf0f1",
                                   justify="left", anchor="w")
        self._type_lbl.pack(anchor="w", padx=(20, 0))

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            for key, lbl in self._stats_labels.items():
                lbl.config(text=str(stats.get(key, 0)))
            by_type = stats.get("by_type", {})
            if by_type:
                self._type_lbl.config(
                    text="\n".join(f"{k}: {v}" for k, v in by_type.items()))
            else:
                self._type_lbl.config(text="No data")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load_checks()
        self._load_stats()

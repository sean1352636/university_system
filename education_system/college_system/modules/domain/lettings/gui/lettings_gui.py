"""Facility Lettings GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.lettings.services.lettings_service import LettingsService


class LettingsFrame(tk.Frame):
    """Facility Lettings management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = LettingsService(db_path)
        self._build_ui()

    # ── UI construction ─────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("lettings.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_bookings_tab()
        self._build_contracts_tab()
        self._build_stats_tab()

    # ── Bookings tab ────────────────────────────────────────────

    def _build_bookings_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("lettings.bookings"))

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=10, pady=5)

        ttk.Button(toolbar, text=t("common.create"), command=self._new_booking).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.view"), command=self._view_booking).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.edit"), command=self._edit_booking).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("lettings.confirm"), command=self._confirm_booking).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.cancel"), command=self._cancel_booking).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_booking).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_bookings_csv).pack(side="right", padx=2)

        # Filters
        filter_frame = tk.Frame(tab, bg="#ecf0f1")
        filter_frame.pack(fill="x", padx=10, pady=2)

        tk.Label(filter_frame, text=t("lettings.facility") + ":", bg="#ecf0f1").pack(side="left", padx=2)
        self._bk_facility_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._bk_facility_var,
                     values=["All", "Sports Hall", "Main Hall", "Drama Studio",
                             "Conference Room", "Classroom", "IT Suite",
                             "Playing Field", "Other"],
                     state="readonly", width=14).pack(side="left", padx=2)

        tk.Label(filter_frame, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=2)
        self._bk_status_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._bk_status_var,
                     values=["All", "pending", "confirmed", "cancelled"],
                     state="readonly", width=12).pack(side="left", padx=2)

        tk.Label(filter_frame, text=t("lettings.payment") + ":", bg="#ecf0f1").pack(side="left", padx=2)
        self._bk_pay_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._bk_pay_var,
                     values=["All", "unpaid", "paid", "invoiced", "waived"],
                     state="readonly", width=10).pack(side="left", padx=2)

        tk.Label(filter_frame, text=t("common.search") + ":", bg="#ecf0f1").pack(side="left", padx=5)
        self._bk_search_var = tk.StringVar()
        tk.Entry(filter_frame, textvariable=self._bk_search_var, width=18).pack(side="left", padx=2)

        ttk.Button(filter_frame, text=t("common.search"), command=self._load_bookings).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "hirer", "facility", "date", "time", "fee", "payment", "status")
        self._bk_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                     selectmode="browse", height=16)
        headings = (t("common.id"), t("lettings.hirer"), t("lettings.facility"),
                    t("lettings.date"), t("lettings.time"), t("lettings.fee"),
                    t("lettings.payment"), t("common.status"))
        widths = (40, 160, 120, 90, 110, 70, 80, 80)
        for c, h, w in zip(cols, headings, widths):
            self._bk_tree.heading(c, text=h)
            self._bk_tree.column(c, width=w, anchor="center" if w < 100 else "w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._bk_tree.yview)
        self._bk_tree.configure(yscrollcommand=vsb.set)
        self._bk_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 10), pady=5)

    # ── Contracts tab ───────────────────────────────────────────

    def _build_contracts_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("lettings.contracts"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=10, pady=5)

        ttk.Button(toolbar, text=t("common.create"), command=self._new_contract).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.edit"), command=self._edit_contract).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("lettings.sign"), command=self._sign_contract).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.delete"), command=self._delete_contract).pack(side="left", padx=2)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_contracts_csv).pack(side="right", padx=2)

        filter_frame = tk.Frame(tab, bg="#ecf0f1")
        filter_frame.pack(fill="x", padx=10, pady=2)

        tk.Label(filter_frame, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=2)
        self._ct_status_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._ct_status_var,
                     values=["All", "draft", "signed", "expired", "cancelled"],
                     state="readonly", width=12).pack(side="left", padx=2)
        ttk.Button(filter_frame, text=t("common.search"), command=self._load_contracts).pack(side="left", padx=5)

        cols = ("id", "hirer", "organisation", "start", "end", "fee", "signed", "status")
        self._ct_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                     selectmode="browse", height=16)
        headings = (t("common.id"), t("lettings.hirer"), t("lettings.organisation"),
                    t("lettings.start_date"), t("lettings.end_date"),
                    t("lettings.fee"), t("lettings.signed_date"), t("common.status"))
        widths = (40, 160, 140, 90, 90, 80, 90, 80)
        for c, h, w in zip(cols, headings, widths):
            self._ct_tree.heading(c, text=h)
            self._ct_tree.column(c, width=w, anchor="center" if w < 100 else "w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._ct_tree.yview)
        self._ct_tree.configure(yscrollcommand=vsb.set)
        self._ct_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 10), pady=5)

    # ── Statistics tab ──────────────────────────────────────────

    def _build_stats_tab(self):
        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text=t("common.summary"))

        ttk.Button(self._stats_tab, text=t("common.refresh"),
                   command=self._load_stats).pack(pady=10)

        self._stats_text = tk.Text(self._stats_tab, width=60, height=20,
                                   font=("Courier", 11), state="disabled",
                                   bg="white", relief="groove", bd=2)
        self._stats_text.pack(padx=20, pady=5, fill="both", expand=True)

    # ── Data loaders ────────────────────────────────────────────

    def _load_bookings(self):
        for item in self._bk_tree.get_children():
            self._bk_tree.delete(item)
        try:
            fac = self._bk_facility_var.get()
            st = self._bk_status_var.get()
            pay = self._bk_pay_var.get()
            search = self._bk_search_var.get().strip() or None
            bookings = self._svc.list_bookings(
                facility=None if fac == "All" else fac,
                status=None if st == "All" else st,
                payment_status=None if pay == "All" else pay,
                search=search,
            )
            for b in bookings:
                time_str = f"{b.get('start_time', '')}-{b.get('end_time', '')}"
                fee_str = f"{b.get('fee', 0):.2f}" if b.get('fee') else "0.00"
                self._bk_tree.insert("", "end", iid=str(b["id"]), values=(
                    b["id"],
                    b.get("hirer_name", ""),
                    b.get("facility", ""),
                    b.get("booking_date", ""),
                    time_str,
                    fee_str,
                    b.get("payment_status", ""),
                    b.get("status", ""),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_contracts(self):
        for item in self._ct_tree.get_children():
            self._ct_tree.delete(item)
        try:
            st = self._ct_status_var.get()
            contracts = self._svc.list_contracts(
                status=None if st == "All" else st,
            )
            for c in contracts:
                fee_str = f"{c.get('agreed_fee', 0):.2f}" if c.get('agreed_fee') else "0.00"
                self._ct_tree.insert("", "end", iid=str(c["id"]), values=(
                    c["id"],
                    c.get("hirer_name", ""),
                    c.get("organisation", "") or "",
                    c.get("contract_start", "") or "",
                    c.get("contract_end", "") or "",
                    fee_str,
                    c.get("signed_date", "") or "",
                    c.get("status", ""),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            lines = [
                "=" * 45,
                f"  {t('lettings.management').upper()} - {t('common.summary').upper()}",
                "=" * 45,
                "",
                f"  {t('lettings.total_bookings')}:       {stats.get('total_bookings', 0)}",
                "",
                f"  {t('lettings.bookings_by_status')}:",
            ]
            for st, cnt in stats.get("by_status", {}).items():
                lines.append(f"    {st:<18} {cnt}")
            lines += [
                "",
                f"  {t('lettings.total_revenue')}:        {stats.get('total_revenue', 0):,.2f}",
                f"  {t('lettings.pending_payments')}:     {stats.get('pending_payments', 0)}",
                "",
                "-" * 45,
                "",
                f"  {t('lettings.total_contracts')}:      {stats.get('total_contracts', 0)}",
                f"  {t('lettings.active_contracts')}:     {stats.get('active_contracts', 0)}",
                f"  {t('lettings.total_contract_value')}: {stats.get('total_contract_value', 0):,.2f}",
                "",
                "=" * 45,
            ]
            self._stats_text.configure(state="normal")
            self._stats_text.delete("1.0", "end")
            self._stats_text.insert("1.0", "\n".join(lines))
            self._stats_text.configure(state="disabled")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── CSV export ──────────────────────────────────────────

    def _export_bookings_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._bk_tree, "lettings_bookings.csv")

    def _export_contracts_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._ct_tree, "lettings_contracts.csv")

    # ── Booking actions ─────────────────────────────────────────

    def _new_booking(self):
        win = tk.Toplevel(self)
        win.title(t("lettings.new_booking"))
        win.geometry("450x520")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key, default in [
            (t("lettings.hirer") + "*:", "hirer_name", ""),
            (t("lettings.organisation") + ":", "organisation", ""),
            (t("lettings.contact_email") + ":", "contact_email", ""),
            (t("lettings.contact_phone") + ":", "contact_phone", ""),
            (t("lettings.facility") + "*:", "facility", ""),
            (t("lettings.date") + "* (YYYY-MM-DD):", "booking_date", str(date.today())),
            (t("lettings.start_time") + "* (HH:MM):", "start_time", "18:00"),
            (t("lettings.end_time") + "* (HH:MM):", "end_time", "21:00"),
            (t("lettings.purpose") + ":", "purpose", ""),
            (t("lettings.attendee_count") + ":", "attendee_count", "0"),
            (t("lettings.fee") + ":", "fee", "0.00"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=3, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=3)
            if default:
                e.insert(0, default)
            fields[key] = e
            row += 1

        tk.Label(win, text=t("lettings.recurrence") + ":").grid(row=row, column=0, padx=10, pady=3, sticky="e")
        rec_var = tk.StringVar(value="one-off")
        ttk.Combobox(win, textvariable=rec_var,
                     values=["one-off", "weekly", "fortnightly", "monthly"],
                     state="readonly", width=25).grid(row=row, column=1, padx=10, pady=3)
        row += 1

        # Checkboxes
        dbs_var = tk.IntVar()
        tk.Checkbutton(win, text=t("lettings.dbs_required"), variable=dbs_var).grid(
            row=row, column=0, columnspan=2, padx=10, pady=2, sticky="w")
        row += 1

        def save():
            try:
                hirer = fields["hirer_name"].get().strip()
                facility = fields["facility"].get().strip()
                bdate = fields["booking_date"].get().strip()
                stime = fields["start_time"].get().strip()
                etime = fields["end_time"].get().strip()
                if not hirer or not facility or not bdate or not stime or not etime:
                    messagebox.showwarning(t("common.validation"), t("common.field_required"))
                    return
                fee_val = float(fields["fee"].get().strip() or 0)
                att_val = int(fields["attendee_count"].get().strip() or 0)
                self._svc.create_booking(
                    hirer_name=hirer,
                    facility=facility,
                    booking_date=bdate,
                    start_time=stime,
                    end_time=etime,
                    organisation=fields["organisation"].get().strip() or None,
                    contact_email=fields["contact_email"].get().strip() or None,
                    contact_phone=fields["contact_phone"].get().strip() or None,
                    purpose=fields["purpose"].get().strip() or None,
                    attendee_count=att_val,
                    fee=fee_val,
                    recurrence=rec_var.get(),
                    dbs_required=dbs_var.get(),
                )
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_bookings()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15)

    def _view_booking(self):
        sel = self._bk_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        try:
            b = self._svc.get_booking(int(sel[0]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('lettings.booking')} #{b['id']}")
        win.geometry("420x500")
        win.resizable(False, False)

        txt = tk.Text(win, font=("Courier", 10), state="normal", wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)

        display_fields = [
            (t("common.id"), "id"), (t("lettings.hirer"), "hirer_name"),
            (t("lettings.organisation"), "organisation"),
            (t("lettings.contact_email"), "contact_email"),
            (t("lettings.contact_phone"), "contact_phone"),
            (t("lettings.facility"), "facility"), (t("lettings.date"), "booking_date"),
            (t("lettings.start_time"), "start_time"), (t("lettings.end_time"), "end_time"),
            (t("lettings.recurrence"), "recurrence"), (t("lettings.purpose"), "purpose"),
            (t("lettings.attendee_count"), "attendee_count"),
            (t("lettings.dbs_required"), "dbs_required"),
            (t("lettings.dbs_verified"), "dbs_verified"),
            (t("lettings.insurance"), "insurance_verified"),
            (t("lettings.risk_assessment"), "risk_assessment_done"),
            (t("lettings.fee"), "fee"), (t("lettings.payment"), "payment_status"),
            (t("lettings.invoice"), "invoice_number"), (t("common.status"), "status"),
            (t("common.notes"), "notes"), (t("common.created"), "created_at"),
            (t("common.updated"), "updated_at"),
        ]
        for label, key in display_fields:
            val = b.get(key, "")
            txt.insert("end", f"{label:<18}: {val}\n")
        txt.configure(state="disabled")

    def _edit_booking(self):
        sel = self._bk_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        try:
            b = self._svc.get_booking(int(sel[0]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        win = tk.Toplevel(self)
        win.title(t("common.edit") + f" {t('lettings.booking')} #{b['id']}")
        win.geometry("450x560")
        win.resizable(False, False)

        fields = {}
        row = 0
        editable = [
            (t("lettings.hirer") + ":", "hirer_name"),
            (t("lettings.organisation") + ":", "organisation"),
            (t("lettings.contact_email") + ":", "contact_email"),
            (t("lettings.contact_phone") + ":", "contact_phone"),
            (t("lettings.facility") + ":", "facility"),
            (t("lettings.date") + " (YYYY-MM-DD):", "booking_date"),
            (t("lettings.start_time") + ":", "start_time"),
            (t("lettings.end_time") + ":", "end_time"),
            (t("lettings.purpose") + ":", "purpose"),
            (t("lettings.attendee_count") + ":", "attendee_count"),
            (t("lettings.fee") + ":", "fee"),
            (t("lettings.invoice") + ":", "invoice_number"),
            (t("common.notes") + ":", "notes"),
        ]
        for label, key in editable:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=3, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=3)
            val = b.get(key, "") or ""
            e.insert(0, str(val))
            fields[key] = e
            row += 1

        tk.Label(win, text=t("lettings.payment_status") + ":").grid(row=row, column=0, padx=10, pady=3, sticky="e")
        pay_var = tk.StringVar(value=b.get("payment_status", "unpaid"))
        ttk.Combobox(win, textvariable=pay_var,
                     values=["unpaid", "paid", "invoiced", "waived"],
                     state="readonly", width=25).grid(row=row, column=1, padx=10, pady=3)
        row += 1

        # Compliance checkboxes
        dbs_req_var = tk.IntVar(value=b.get("dbs_required", 0))
        dbs_ver_var = tk.IntVar(value=b.get("dbs_verified", 0))
        ins_var = tk.IntVar(value=b.get("insurance_verified", 0))
        risk_var = tk.IntVar(value=b.get("risk_assessment_done", 0))

        chk_frame = tk.Frame(win)
        chk_frame.grid(row=row, column=0, columnspan=2, padx=10, pady=3)
        tk.Checkbutton(chk_frame, text=t("lettings.dbs_required"), variable=dbs_req_var).pack(side="left", padx=5)
        tk.Checkbutton(chk_frame, text=t("lettings.dbs_verified"), variable=dbs_ver_var).pack(side="left", padx=5)
        tk.Checkbutton(chk_frame, text=t("lettings.insurance"), variable=ins_var).pack(side="left", padx=5)
        tk.Checkbutton(chk_frame, text=t("lettings.risk_assessment"), variable=risk_var).pack(side="left", padx=5)
        row += 1

        def save():
            try:
                updates = {}
                for key, entry in fields.items():
                    val = entry.get().strip()
                    if key in ("fee", "attendee_count"):
                        val = float(val) if val else 0
                        if key == "attendee_count":
                            val = int(val)
                    updates[key] = val if val != "" else None
                updates["payment_status"] = pay_var.get()
                updates["dbs_required"] = dbs_req_var.get()
                updates["dbs_verified"] = dbs_ver_var.get()
                updates["insurance_verified"] = ins_var.get()
                updates["risk_assessment_done"] = risk_var.get()
                self._svc.update_booking(b["id"], **updates)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_bookings()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15)

    def _confirm_booking(self):
        sel = self._bk_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if not messagebox.askyesno(t("common.confirm"), t("lettings.confirm_booking")):
            return
        try:
            self._svc.confirm_booking(int(sel[0]))
            messagebox.showinfo(t("common.success"), t("lettings.booking_confirmed"))
            self._load_bookings()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _cancel_booking(self):
        sel = self._bk_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if not messagebox.askyesno(t("common.confirm"), t("lettings.cancel_booking")):
            return
        try:
            self._svc.cancel_booking(int(sel[0]))
            messagebox.showinfo(t("common.success"), t("lettings.booking_cancelled"))
            self._load_bookings()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_booking(self):
        sel = self._bk_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_booking(int(sel[0]))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_bookings()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── Contract actions ────────────────────────────────────────

    def _new_contract(self):
        win = tk.Toplevel(self)
        win.title(t("lettings.new_contract"))
        win.geometry("420x350")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key, default in [
            (t("lettings.hirer") + "*:", "hirer_name", ""),
            (t("lettings.organisation") + ":", "organisation", ""),
            (t("lettings.start_date") + ":", "contract_start", str(date.today())),
            (t("lettings.end_date") + ":", "contract_end", ""),
            (t("lettings.agreed_fee") + ":", "agreed_fee", "0.00"),
            (t("lettings.terms") + ":", "terms", ""),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=5)
            if default:
                e.insert(0, default)
            fields[key] = e
            row += 1

        def save():
            try:
                hirer = fields["hirer_name"].get().strip()
                if not hirer:
                    messagebox.showwarning(t("common.validation"), t("common.field_required"))
                    return
                fee_val = float(fields["agreed_fee"].get().strip() or 0)
                self._svc.create_contract(
                    hirer_name=hirer,
                    organisation=fields["organisation"].get().strip() or None,
                    contract_start=fields["contract_start"].get().strip() or None,
                    contract_end=fields["contract_end"].get().strip() or None,
                    agreed_fee=fee_val,
                    terms=fields["terms"].get().strip() or None,
                )
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_contracts()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15)

    def _edit_contract(self):
        sel = self._ct_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        try:
            c = self._svc.get_contract(int(sel[0]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        win = tk.Toplevel(self)
        win.title(t("common.edit") + f" {t('lettings.contract')} #{c['id']}")
        win.geometry("420x380")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            (t("lettings.hirer") + ":", "hirer_name"),
            (t("lettings.organisation") + ":", "organisation"),
            (t("lettings.start_date") + ":", "contract_start"),
            (t("lettings.end_date") + ":", "contract_end"),
            (t("lettings.agreed_fee") + ":", "agreed_fee"),
            (t("lettings.terms") + ":", "terms"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=5)
            val = c.get(key, "") or ""
            e.insert(0, str(val))
            fields[key] = e
            row += 1

        tk.Label(win, text=t("common.status") + ":").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        st_var = tk.StringVar(value=c.get("status", "draft"))
        ttk.Combobox(win, textvariable=st_var,
                     values=["draft", "signed", "expired", "cancelled"],
                     state="readonly", width=25).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                updates = {}
                for key, entry in fields.items():
                    val = entry.get().strip()
                    if key == "agreed_fee":
                        val = float(val) if val else 0
                    updates[key] = val if val != "" else None
                updates["status"] = st_var.get()
                self._svc.update_contract(c["id"], **updates)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_contracts()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=15)

    def _sign_contract(self):
        sel = self._ct_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if not messagebox.askyesno(t("common.confirm"), t("lettings.confirm_sign")):
            return
        try:
            self._svc.sign_contract(int(sel[0]), signed_date=str(date.today()))
            messagebox.showinfo(t("common.success"), t("lettings.contract_signed"))
            self._load_contracts()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_contract(self):
        sel = self._ct_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("common.select_first"))
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_contract(int(sel[0]))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_contracts()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── Refresh ─────────────────────────────────────────────────

    def refresh(self):
        self._load_bookings()
        self._load_contracts()
        self._load_stats()

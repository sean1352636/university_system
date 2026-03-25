"""Lettings management portal GUI frame."""
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.lettings_portal.services.lettings_portal_service import (
    LettingsPortalService,
)
from education_system.college_system.core.i18n import t


class LettingsPortalFrame(tk.Frame):
    """GUI for lettings management with booking portal and invoicing."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = LettingsPortalService(db_path)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=t("lettings_portal.title", "Lettings Portal"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_hirers_tab()
        self._build_facilities_tab()
        self._build_bookings_tab()
        self._build_invoicing_tab()
        self._build_revenue_tab()

    # -- Hirers Tab --

    def _build_hirers_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("lettings_portal.hirers_tab", "Hirers"))

        form = tk.LabelFrame(tab, text=t("lettings_portal.register_hirer", "Register Hirer"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Organisation", "Contact Name", "Email", "Phone", "Account Type"]
        self._hirer_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=0, column=i * 2, padx=5, pady=5, sticky="e")
            var = tk.StringVar()
            if lbl == "Account Type":
                var.set("occasional")
                widget = ttk.Combobox(form, textvariable=var, values=["regular", "occasional", "community", "commercial"], width=12)
            else:
                widget = tk.Entry(form, textvariable=var, width=16)
            widget.grid(row=0, column=i * 2 + 1, padx=5, pady=5)
            self._hirer_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=1, column=0, columnspan=10, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_hirer).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_hirers).pack(side="left", padx=5)

        cols = ("id", "organisation_name", "contact_name", "contact_email", "contact_phone", "account_type", "discount_rate", "is_active")
        self._hirers_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._hirers_tree.heading(c, text=c.replace("_", " ").title())
            self._hirers_tree.column(c, width=110)
        self._hirers_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_hirer(self):
        try:
            v = self._hirer_vars
            self._svc.register_hirer(
                organisation_name=v["Organisation"].get(),
                contact_name=v["Contact Name"].get(),
                contact_email=v["Email"].get(),
                contact_phone=v["Phone"].get(),
                account_type=v["Account Type"].get(),
            )
            messagebox.showinfo(t("common.success", "Success"), t("lettings_portal.hirer_added", "Hirer registered."))
            self._load_hirers()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_hirers(self):
        for row in self._hirers_tree.get_children():
            self._hirers_tree.delete(row)
        try:
            for h in self._svc.list_hirers(active_only=False):
                self._hirers_tree.insert("", "end", values=(
                    h["id"], h["organisation_name"], h.get("contact_name", ""),
                    h.get("contact_email", ""), h.get("contact_phone", ""),
                    h.get("account_type", ""), h.get("discount_rate", 0),
                    "Yes" if h.get("is_active") else "No",
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Facilities Tab --

    def _build_facilities_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("lettings_portal.facilities_tab", "Facilities"))

        form = tk.LabelFrame(tab, text=t("lettings_portal.add_facility", "Add Facility"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Name", "Type", "Capacity", "Hourly Rate", "Half Day Rate", "Full Day Rate", "Community Rate"]
        self._fac_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            if lbl == "Type":
                widget = ttk.Combobox(form, textvariable=var, values=["hall", "sports_hall", "classroom", "field", "studio", "meeting_room", "other"], width=14)
            else:
                widget = tk.Entry(form, textvariable=var, width=16)
            widget.grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._fac_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_facility).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_facilities).pack(side="left", padx=5)

        cols = ("id", "facility_name", "facility_type", "capacity", "hourly_rate", "half_day_rate", "full_day_rate", "community_rate")
        self._fac_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._fac_tree.heading(c, text=c.replace("_", " ").title())
            self._fac_tree.column(c, width=110)
        self._fac_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_facility(self):
        try:
            v = self._fac_vars
            self._svc.add_facility(
                facility_name=v["Name"].get(),
                facility_type=v["Type"].get(),
                capacity=int(v["Capacity"].get() or 0),
                hourly_rate=float(v["Hourly Rate"].get() or 0),
                half_day_rate=float(v["Half Day Rate"].get() or 0),
                full_day_rate=float(v["Full Day Rate"].get() or 0),
                community_rate=float(v["Community Rate"].get() or 0),
            )
            messagebox.showinfo(t("common.success", "Success"), t("lettings_portal.facility_added", "Facility added."))
            self._load_facilities()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_facilities(self):
        for row in self._fac_tree.get_children():
            self._fac_tree.delete(row)
        try:
            for f in self._svc.list_facilities(active_only=False):
                self._fac_tree.insert("", "end", values=(
                    f["id"], f["facility_name"], f.get("facility_type", ""),
                    f.get("capacity", 0), f.get("hourly_rate", 0),
                    f.get("half_day_rate", 0), f.get("full_day_rate", 0),
                    f.get("community_rate", 0),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Bookings Portal Tab --

    def _build_bookings_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("lettings_portal.bookings_tab", "Bookings Portal"))

        form = tk.LabelFrame(tab, text=t("lettings_portal.new_booking", "New Booking"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Hirer ID", "Facility ID", "Date", "Start Time", "End Time", "Purpose", "Attendees"]
        self._book_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=16).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._book_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("lettings_portal.check_avail", "Check Availability"), command=self._check_avail).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("lettings_portal.book_and_invoice", "Book & Invoice"), command=self._book_and_invoice).pack(side="left", padx=5)

        self._booking_info = tk.Text(tab, height=10, width=60, state="disabled")
        self._booking_info.pack(fill="both", expand=True, padx=10, pady=5)

    def _check_avail(self):
        try:
            v = self._book_vars
            avail = self._svc.check_availability(
                facility_id=int(v["Facility ID"].get()),
                date=v["Date"].get(),
                start_time=v["Start Time"].get(),
                end_time=v["End Time"].get(),
            )
            msg = "Available" if avail else "Not available"
            messagebox.showinfo(t("lettings_portal.availability", "Availability"), msg)
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _book_and_invoice(self):
        try:
            v = self._book_vars
            result = self._svc.create_booking_with_invoice(
                hirer_id=int(v["Hirer ID"].get()),
                facility_id=int(v["Facility ID"].get()),
                booking_date=v["Date"].get(),
                start_time=v["Start Time"].get(),
                end_time=v["End Time"].get(),
                purpose=v["Purpose"].get(),
                attendee_count=int(v["Attendees"].get() or 0),
            )
            self._booking_info.config(state="normal")
            self._booking_info.delete("1.0", "end")
            self._booking_info.insert("end", "Booking Created Successfully\n")
            self._booking_info.insert("end", "=" * 40 + "\n\n")
            for key, val in result.items():
                label = key.replace("_", " ").title()
                self._booking_info.insert("end", f"{label}: {val}\n")
            self._booking_info.config(state="disabled")
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Invoicing Tab --

    def _build_invoicing_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("lettings_portal.invoicing_tab", "Invoicing"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl, text="Hirer ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._inv_hirer_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._inv_hirer_var, width=8).pack(side="left", padx=5)

        tk.Label(ctrl, text="Status:", bg="#ecf0f1").pack(side="left", padx=5)
        self._inv_status_var = tk.StringVar()
        ttk.Combobox(ctrl, textvariable=self._inv_status_var, values=["", "draft", "sent", "paid", "overdue", "cancelled"], width=10).pack(side="left", padx=5)

        tk.Button(ctrl, text=t("common.load", "Load"), command=self._load_lettings_invoices).pack(side="left", padx=5)

        # Payment section
        pay = tk.Frame(tab, bg="#ecf0f1")
        pay.pack(fill="x", padx=10, pady=2)
        tk.Label(pay, text="Invoice ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._pay_inv_var = tk.StringVar()
        tk.Entry(pay, textvariable=self._pay_inv_var, width=8).pack(side="left", padx=5)
        tk.Label(pay, text="Amount:", bg="#ecf0f1").pack(side="left", padx=5)
        self._pay_amount_var = tk.StringVar()
        tk.Entry(pay, textvariable=self._pay_amount_var, width=10).pack(side="left", padx=5)
        tk.Button(pay, text=t("lettings_portal.record_payment", "Record Payment"), command=self._record_payment).pack(side="left", padx=5)

        cols = ("id", "hirer_id", "invoice_number", "invoice_date", "subtotal",
                "vat_amount", "discount_amount", "total_amount", "paid_amount", "status")
        self._linv_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self._linv_tree.heading(c, text=c.replace("_", " ").title())
            self._linv_tree.column(c, width=95)
        self._linv_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _load_lettings_invoices(self):
        for row in self._linv_tree.get_children():
            self._linv_tree.delete(row)
        try:
            hid = self._inv_hirer_var.get()
            status = self._inv_status_var.get()
            for r in self._svc.list_invoices(
                hirer_id=int(hid) if hid else None,
                status=status or None,
            ):
                self._linv_tree.insert("", "end", values=(
                    r["id"], r["hirer_id"], r.get("invoice_number", ""),
                    r.get("invoice_date", ""), r.get("subtotal", 0),
                    r.get("vat_amount", 0), r.get("discount_amount", 0),
                    r.get("total_amount", 0), r.get("paid_amount", 0),
                    r.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _record_payment(self):
        try:
            self._svc.record_payment(
                invoice_id=int(self._pay_inv_var.get()),
                amount=float(self._pay_amount_var.get()),
            )
            messagebox.showinfo(t("common.success", "Success"), t("lettings_portal.payment_recorded", "Payment recorded."))
            self._load_lettings_invoices()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Revenue Reports Tab --

    def _build_revenue_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("lettings_portal.revenue_tab", "Revenue Reports"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl, text="From:", bg="#ecf0f1").pack(side="left", padx=5)
        self._rev_from_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._rev_from_var, width=12).pack(side="left", padx=5)
        tk.Label(ctrl, text="To:", bg="#ecf0f1").pack(side="left", padx=5)
        self._rev_to_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._rev_to_var, width=12).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("lettings_portal.revenue_report", "Revenue Report"), command=self._run_revenue).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("lettings_portal.utilisation_report", "Utilisation Report"), command=self._run_utilisation).pack(side="left", padx=5)

        cols = ("name", "id", "count", "total", "paid", "outstanding")
        self._rev_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._rev_tree.heading(c, text=c.replace("_", " ").title())
            self._rev_tree.column(c, width=130)
        self._rev_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _run_revenue(self):
        for row in self._rev_tree.get_children():
            self._rev_tree.delete(row)
        try:
            data = self._svc.get_revenue_report(
                self._rev_from_var.get(), self._rev_to_var.get(),
            )
            for r in data:
                self._rev_tree.insert("", "end", values=(
                    r.get("organisation_name", ""), r.get("hirer_id", ""),
                    r.get("num_invoices", 0), f"{r.get('total_invoiced', 0):.2f}",
                    f"{r.get('total_paid', 0):.2f}", f"{r.get('outstanding', 0):.2f}",
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _run_utilisation(self):
        for row in self._rev_tree.get_children():
            self._rev_tree.delete(row)
        try:
            data = self._svc.get_utilisation_report(
                self._rev_from_var.get(), self._rev_to_var.get(),
            )
            for r in data:
                self._rev_tree.insert("", "end", values=(
                    r.get("facility_name", ""), r.get("facility_id", ""),
                    r.get("num_bookings", 0), f"{r.get('total_hours', 0):.1f}",
                    r.get("facility_type", ""), "",
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def refresh(self):
        """Refresh all data."""
        self._load_hirers()

"""Supply/cover agency integration GUI frame."""
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.cover_agency.services.cover_agency_service import (
    CoverAgencyService,
)
from education_system.college_system.core.i18n import t


class CoverAgencyFrame(tk.Frame):
    """GUI for managing cover agency requests and invoicing."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CoverAgencyService(db_path)
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
            text=t("cover_agency.title", "Cover Agency Management"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_agencies_tab()
        self._build_requests_tab()
        self._build_invoices_tab()
        self._build_reports_tab()

    # -- Agencies Tab --

    def _build_agencies_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("cover_agency.agencies_tab", "Agencies"))

        form = tk.LabelFrame(tab, text=t("cover_agency.add_agency", "Add Agency"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Agency Name", "Contact Name", "Contact Email", "Contact Phone", "Day Rate", "Rank"]
        self._agency_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 3, column=(i % 3) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=20).grid(row=i // 3, column=(i % 3) * 2 + 1, padx=5, pady=2)
            self._agency_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=6, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_agency).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_agencies).pack(side="left", padx=5)

        cols = ("id", "agency_name", "contact_name", "contact_email", "contact_phone", "day_rate", "preferred_rank", "is_active")
        self._agencies_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._agencies_tree.heading(c, text=c.replace("_", " ").title())
            self._agencies_tree.column(c, width=110)
        self._agencies_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_agency(self):
        try:
            v = self._agency_vars
            self._svc.add_agency(
                agency_name=v["Agency Name"].get(),
                contact_name=v["Contact Name"].get(),
                contact_email=v["Contact Email"].get(),
                contact_phone=v["Contact Phone"].get(),
                day_rate=float(v["Day Rate"].get() or 0),
                preferred_rank=int(v["Rank"].get() or 0),
            )
            messagebox.showinfo(t("common.success", "Success"), t("cover_agency.agency_added", "Agency added."))
            self._load_agencies()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_agencies(self):
        for row in self._agencies_tree.get_children():
            self._agencies_tree.delete(row)
        try:
            for a in self._svc.list_agencies(active_only=False):
                self._agencies_tree.insert("", "end", values=(
                    a["id"], a["agency_name"], a.get("contact_name", ""),
                    a.get("contact_email", ""), a.get("contact_phone", ""),
                    a.get("day_rate", 0), a.get("preferred_rank", 0),
                    "Yes" if a.get("is_active") else "No",
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Cover Requests Tab --

    def _build_requests_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("cover_agency.requests_tab", "Cover Requests"))

        form = tk.LabelFrame(tab, text=t("cover_agency.create_request", "Create Request"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Agency ID", "Date Required", "Subject Area", "Start Time", "End Time", "Year Group", "Special Requirements"]
        self._req_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=16).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._req_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("cover_agency.send_request", "Send Request"), command=self._create_request).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_requests).pack(side="left", padx=5)

        # Response section
        resp = tk.LabelFrame(tab, text=t("cover_agency.update_response", "Update Response"), bg="#ecf0f1")
        resp.pack(fill="x", padx=10, pady=5)

        tk.Label(resp, text="Request ID:", bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        self._resp_id_var = tk.StringVar()
        tk.Entry(resp, textvariable=self._resp_id_var, width=8).grid(row=0, column=1, padx=5, pady=2)

        tk.Label(resp, text="Response:", bg="#ecf0f1").grid(row=0, column=2, padx=5, pady=2, sticky="e")
        self._resp_var = tk.StringVar(value="accepted")
        ttk.Combobox(resp, textvariable=self._resp_var, values=["accepted", "declined", "no_response"], width=12).grid(row=0, column=3, padx=5, pady=2)

        tk.Label(resp, text="Teacher Name:", bg="#ecf0f1").grid(row=0, column=4, padx=5, pady=2, sticky="e")
        self._resp_teacher_var = tk.StringVar()
        tk.Entry(resp, textvariable=self._resp_teacher_var, width=18).grid(row=0, column=5, padx=5, pady=2)

        tk.Button(resp, text=t("common.update", "Update"), command=self._update_response).grid(row=0, column=6, padx=10)
        tk.Button(resp, text=t("cover_agency.cancel_req", "Cancel Request"), command=self._cancel_request).grid(row=0, column=7, padx=5)

        cols = ("id", "agency_id", "subject_area", "date_required", "start_time", "end_time",
                "agency_response", "teacher_name", "status", "day_rate")
        self._req_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self._req_tree.heading(c, text=c.replace("_", " ").title())
            self._req_tree.column(c, width=100)
        self._req_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _create_request(self):
        try:
            v = self._req_vars
            self._svc.create_cover_request(
                agency_id=int(v["Agency ID"].get()),
                date_required=v["Date Required"].get(),
                subject_area=v["Subject Area"].get(),
                start_time=v["Start Time"].get(),
                end_time=v["End Time"].get(),
                year_group=v["Year Group"].get() or None,
                special_requirements=v["Special Requirements"].get() or None,
            )
            messagebox.showinfo(t("common.success", "Success"), t("cover_agency.request_created", "Request created."))
            self._load_requests()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _update_response(self):
        try:
            self._svc.update_request_response(
                request_id=int(self._resp_id_var.get()),
                agency_response=self._resp_var.get(),
                teacher_name=self._resp_teacher_var.get() or None,
            )
            messagebox.showinfo(t("common.success", "Success"), t("cover_agency.response_updated", "Response updated."))
            self._load_requests()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _cancel_request(self):
        try:
            rid = self._resp_id_var.get()
            if not rid:
                return
            self._svc.cancel_request(int(rid))
            messagebox.showinfo(t("common.success", "Success"), t("cover_agency.request_cancelled", "Request cancelled."))
            self._load_requests()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_requests(self):
        for row in self._req_tree.get_children():
            self._req_tree.delete(row)
        try:
            for r in self._svc.list_requests():
                self._req_tree.insert("", "end", values=(
                    r["id"], r["agency_id"], r.get("subject_area", ""),
                    r.get("date_required", ""), r.get("start_time", ""),
                    r.get("end_time", ""), r.get("agency_response", ""),
                    r.get("teacher_name", ""), r.get("status", ""),
                    r.get("day_rate", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Invoice Management Tab --

    def _build_invoices_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("cover_agency.invoices_tab", "Invoice Management"))

        form = tk.LabelFrame(tab, text=t("cover_agency.create_invoice", "Create Invoice"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Agency ID", "Invoice Number", "Invoice Date", "Period Start", "Period End", "Days Covered", "Total Amount"]
        self._inv_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=16).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._inv_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_invoice).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_invoices).pack(side="left", padx=5)

        # Approve section
        approve = tk.Frame(tab, bg="#ecf0f1")
        approve.pack(fill="x", padx=10, pady=2)
        tk.Label(approve, text="Invoice ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._approve_id_var = tk.StringVar()
        tk.Entry(approve, textvariable=self._approve_id_var, width=8).pack(side="left", padx=5)
        tk.Button(approve, text=t("cover_agency.approve", "Approve"), command=self._approve_invoice).pack(side="left", padx=5)

        cols = ("id", "agency_id", "invoice_number", "invoice_date", "period_start",
                "period_end", "days_covered", "total_amount", "status")
        self._inv_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self._inv_tree.heading(c, text=c.replace("_", " ").title())
            self._inv_tree.column(c, width=100)
        self._inv_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_invoice(self):
        try:
            v = self._inv_vars
            self._svc.create_invoice(
                agency_id=int(v["Agency ID"].get()),
                invoice_number=v["Invoice Number"].get(),
                invoice_date=v["Invoice Date"].get(),
                period_start=v["Period Start"].get(),
                period_end=v["Period End"].get(),
                days_covered=int(v["Days Covered"].get() or 0),
                total_amount=float(v["Total Amount"].get() or 0),
            )
            messagebox.showinfo(t("common.success", "Success"), t("cover_agency.invoice_created", "Invoice created."))
            self._load_invoices()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _approve_invoice(self):
        try:
            iid = self._approve_id_var.get()
            if not iid:
                return
            user_id = self._auth.get("user_id", 0) if self._auth else 0
            self._svc.approve_invoice(int(iid), user_id)
            messagebox.showinfo(t("common.success", "Success"), t("cover_agency.invoice_approved", "Invoice approved."))
            self._load_invoices()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_invoices(self):
        for row in self._inv_tree.get_children():
            self._inv_tree.delete(row)
        try:
            for r in self._svc.list_invoices():
                self._inv_tree.insert("", "end", values=(
                    r["id"], r["agency_id"], r.get("invoice_number", ""),
                    r.get("invoice_date", ""), r.get("period_start", ""),
                    r.get("period_end", ""), r.get("days_covered", 0),
                    r.get("total_amount", 0), r.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Spend Reports Tab --

    def _build_reports_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("cover_agency.reports_tab", "Spend Reports"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl, text="From:", bg="#ecf0f1").pack(side="left", padx=5)
        self._report_from_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._report_from_var, width=12).pack(side="left", padx=5)
        tk.Label(ctrl, text="To:", bg="#ecf0f1").pack(side="left", padx=5)
        self._report_to_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._report_to_var, width=12).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("cover_agency.run_report", "Run Report"), command=self._run_report).pack(side="left", padx=5)

        cols = ("agency_name", "agency_id", "requests", "total_spend")
        self._report_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._report_tree.heading(c, text=c.replace("_", " ").title())
            self._report_tree.column(c, width=150)
        self._report_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _run_report(self):
        for row in self._report_tree.get_children():
            self._report_tree.delete(row)
        try:
            data = self._svc.get_cover_spend_report(
                self._report_from_var.get(), self._report_to_var.get(),
            )
            for r in data:
                self._report_tree.insert("", "end", values=(
                    r.get("agency_name", ""), r.get("agency_id", ""),
                    r.get("requests", 0), f"{r.get('total_spend', 0):.2f}",
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def refresh(self):
        """Refresh all data."""
        self._load_agencies()

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from education_system.systems.university.domain.finance.operations_service import (
    FinanceOperationsService,
)


class FinanceOperationsMixin:
    def _ops(self):
        if not hasattr(self, "_ops_service"):
            self._ops_service = FinanceOperationsService()
        return self._ops_service

    def _ops_user(self):
        details = getattr(self.gui, "user_info", {}) or {}
        return str(
            details.get("username")
            or details.get("email")
            or getattr(self.gui, "role", "finance-user")
        )

    def _ops_tab(self, key, title, table, columns, add_action):
        frame = tk.Frame(self.content_frame, bg="white")
        self.tab_frames[key] = frame
        bar = ttk.Frame(frame)
        bar.pack(fill="x", padx=10, pady=10)
        ttk.Label(bar, text=title, font=("Arial", 16, "bold")).pack(side="left")
        ttk.Button(bar, text="Add", command=lambda: self._run_ops_action(add_action, refresh)).pack(
            side="right"
        )
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        [tree.heading(c, text=c.replace("_", " ").title()) for c in columns]
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            tree.delete(*tree.get_children())
            rows = self._ops().list_suppliers() if table == "suppliers" else self._ops().rows(table)
            for r in rows:
                tree.insert("", "end", values=[r.get(c, "") for c in columns])

        refresh()
        return frame, tree, refresh

    def _run_ops_action(self, action, refresh):
        try:
            action(refresh)
        except Exception as error:
            messagebox.showerror("Unable to save", str(error), parent=self.root)

    def create_suppliers_tab(self):
        def add(refresh):
            n = simpledialog.askstring("Supplier", "Name:", parent=self.root)
            e = simpledialog.askstring("Supplier", "Email:", parent=self.root) or ""
            if n:
                self._ops().add_supplier(n, e)
                refresh()

        frame, tree, refresh = self._ops_tab(
            "suppliers",
            "Supplier Management",
            "suppliers",
            ("id", "name", "email", "bank_verified", "risk_rating", "status"),
            add,
        )
        ttk.Button(
            frame, text="Verify bank details", command=lambda: self._supplier_verify(tree, refresh)
        ).pack(pady=4)

    def create_accounts_payable_tab(self):
        def add(refresh):
            s = simpledialog.askinteger("Invoice", "Supplier ID:", parent=self.root)
            n = simpledialog.askstring("Invoice", "Invoice number:", parent=self.root)
            a = simpledialog.askfloat("Invoice", "Net amount:", parent=self.root)
            if s and n and a:
                self._ops().add_invoice(s, n, a)
                refresh()

        frame, tree, refresh = self._ops_tab(
            "accounts_payable",
            "Accounts Payable",
            "finance_ap_invoices",
            (
                "id",
                "invoice_number",
                "supplier_id",
                "net_amount",
                "vat_amount",
                "due_date",
                "status",
            ),
            add,
        )
        ttk.Button(
            frame,
            text="Approve selected invoice",
            command=lambda: self._invoice_approve(tree, refresh),
        ).pack(pady=4)

    def create_purchase_orders_tab(self):
        def add(refresh):
            s = simpledialog.askinteger("Purchase order", "Supplier ID:", parent=self.root)
            d = simpledialog.askstring("Purchase order", "Description:", parent=self.root)
            a = simpledialog.askfloat("Purchase order", "Net amount:", parent=self.root)
            if s and d and a:
                self._ops().create_po(s, d, a)
                refresh()

        frame, tree, refresh = self._ops_tab(
            "purchase_orders",
            "Purchase Orders",
            "finance_purchase_orders",
            ("id", "po_number", "supplier_id", "description", "net_amount", "status"),
            add,
        )
        ttk.Button(
            frame, text="Advance status", command=lambda: self._po_advance(tree, refresh)
        ).pack(pady=4)

    def create_cash_flow_tab(self):
        def add(refresh):
            k = simpledialog.askstring("Cash movement", "Type (inflow/outflow):", parent=self.root)
            c = simpledialog.askstring("Cash movement", "Category:", parent=self.root)
            a = simpledialog.askfloat("Cash movement", "Amount:", parent=self.root)
            if k and a:
                self._ops().record_cash(k, c or "", a)
                refresh()

        frame, tree, refresh = self._ops_tab(
            "cash_flow",
            "Cash Flow Control Centre",
            "finance_cash_movements",
            ("id", "movement_date", "kind", "category", "amount", "status", "description"),
            add,
        )
        summary = ttk.Label(frame, font=("Arial", 11, "bold"))
        summary.pack(pady=4)

        def update():
            s = self._ops().cash_summary()
            summary.config(
                text=f"Position: £{s['balance']:,.2f} | Expected receipts: £{s['expected_in']:,.2f} | Scheduled payments: £{s['expected_out']:,.2f}"
            )

        ttk.Button(frame, text="Refresh cash position", command=update).pack(pady=3)
        update()

    def create_tax_vat_tab(self):
        def add(refresh):
            code = simpledialog.askstring("VAT", "Tax code:", parent=self.root)
            net = simpledialog.askfloat("VAT", "Net amount:", parent=self.root)
            vat = simpledialog.askfloat("VAT", "VAT amount:", parent=self.root)
            direction = simpledialog.askstring("VAT", "Direction (input/output):", parent=self.root)
            if code and net is not None and vat is not None and direction:
                self._ops().record_vat("manual", None, code, net, vat, direction)
                refresh()

        frame, tree, refresh = self._ops_tab(
            "tax_vat",
            "Tax & VAT Management",
            "finance_vat_entries",
            ("id", "tax_date", "source_type", "tax_code", "net_amount", "vat_amount", "direction"),
            add,
        )
        summary = ttk.Label(frame, font=("Arial", 11, "bold"))
        summary.pack(pady=4)

        def update():
            s = self._ops().vat_summary()
            summary.config(
                text=f"Output VAT: £{s['output_vat']:,.2f} | Input VAT: £{s['input_vat']:,.2f} | Net payable: £{s['net_payable']:,.2f}"
            )

        ttk.Button(frame, text="Refresh VAT position", command=update).pack(pady=3)
        update()

    def _selected_id(self, tree):
        selected = tree.selection()
        return int(tree.item(selected[0], "values")[0]) if selected else None

    def _supplier_verify(self, tree, refresh):
        item = self._selected_id(tree)
        if item:
            self._ops().update_supplier_controls(item, bank_verified=True)
            refresh()

    def _invoice_approve(self, tree, refresh):
        item = self._selected_id(tree)
        if item:
            try:
                self._ops().approve_invoice(item)
                refresh()
            except Exception as e:
                messagebox.showerror("Approval blocked", str(e), parent=self.root)

    def _po_advance(self, tree, refresh):
        item = self._selected_id(tree)
        status = simpledialog.askstring(
            "PO status",
            "submitted / approved / ordered / received / closed / cancelled",
            parent=self.root,
        )
        if item and status:
            try:
                self._ops().advance_po(item, status.strip().lower())
                refresh()
            except Exception as e:
                messagebox.showerror("Status update blocked", str(e), parent=self.root)

    def create_fixed_assets_tab(self):
        def add(refresh):
            tag = simpledialog.askstring("Asset", "Asset tag:", parent=self.root)
            if tag is None:
                return
            desc = simpledialog.askstring("Asset", "Description:", parent=self.root)
            if desc is None:
                return
            cost = simpledialog.askfloat("Asset", "Cost:", parent=self.root)
            if cost is None:
                return
            life = simpledialog.askinteger("Asset", "Useful life (years):", parent=self.root)
            if life is None:
                return
            self._ops().add_asset(tag, desc, cost, life)
            refresh()

        self._ops_tab(
            "fixed_assets",
            "Fixed Asset Register",
            "finance_fixed_assets",
            (
                "id",
                "asset_tag",
                "description",
                "cost",
                "acquired_date",
                "useful_life_years",
                "residual_value",
                "location",
                "status",
            ),
            add,
        )

    def create_approval_inbox_tab(self):
        def add(refresh):
            typ = simpledialog.askstring("Approval", "Item type:", parent=self.root)
            entity = simpledialog.askinteger("Approval", "Entity ID:", parent=self.root)
            amount = simpledialog.askfloat("Approval", "Amount:", parent=self.root)
            if typ and entity:
                self._ops().request_approval(typ, entity, amount or 0, self._ops_user())
                refresh()

        frame, tree, refresh = self._ops_tab(
            "approval_inbox",
            "Finance Approval Inbox",
            "finance_approval_items",
            (
                "id",
                "item_type",
                "entity_id",
                "amount",
                "requested_by",
                "status",
                "decision_by",
                "decision_at",
            ),
            add,
        )
        for text, decision in (("Approve", "approved"), ("Reject", "rejected")):
            ttk.Button(
                frame, text=text, command=lambda d=decision: self._approval_decide(tree, refresh, d)
            ).pack(side="left", padx=5, pady=4)

    def _approval_decide(self, tree, refresh, decision):
        item = self._selected_id(tree)
        if item:
            self._ops().decide_approval(item, decision, self._ops_user())
            refresh()

    def create_fraud_investigations_tab(self):
        def add(refresh):
            payment = simpledialog.askinteger("Fraud case", "Payment ID:", parent=self.root)
            score = simpledialog.askfloat("Fraud case", "Risk score 0-1:", parent=self.root)
            reason = simpledialog.askstring("Fraud case", "Reason:", parent=self.root)
            if payment and score is not None:
                self._ops().create_fraud_case(payment, score, reason or "")
                refresh()

        frame, tree, refresh = self._ops_tab(
            "fraud_investigations",
            "Fraud Investigations",
            "finance_fraud_cases",
            (
                "id",
                "payment_id",
                "risk_score",
                "reason",
                "status",
                "assigned_to",
                "decision",
                "created_at",
            ),
            add,
        )
        for text, decision in (
            ("Confirm fraud", "confirmed"),
            ("False positive", "false_positive"),
            ("Escalate", "escalated"),
        ):
            ttk.Button(
                frame, text=text, command=lambda d=decision: self._fraud_decide(tree, refresh, d)
            ).pack(side="left", padx=4, pady=4)

    def _fraud_decide(self, tree, refresh, decision):
        item = self._selected_id(tree)
        if item:
            self._ops().decide_fraud_case(item, decision, self._ops_user())
            refresh()

    def create_close_checklist_tab(self):
        def add(refresh):
            period = simpledialog.askstring(
                "Close checklist", "Period (e.g. 2026-08):", parent=self.root
            )
            if period:
                self._ops().seed_close_checklist(period, "finance-team")
                refresh()

        frame, tree, refresh = self._ops_tab(
            "close_checklist",
            "Month-End Close Checklist",
            "finance_close_tasks",
            ("id", "period_label", "task_name", "owner", "status", "evidence"),
            add,
        )
        ttk.Button(
            frame,
            text="Complete selected task",
            command=lambda: self._close_complete(tree, refresh),
        ).pack(pady=4)

    def _close_complete(self, tree, refresh):
        item = self._selected_id(tree)
        evidence = simpledialog.askstring("Close evidence", "Evidence/reference:", parent=self.root)
        if item and evidence:
            try:
                self._ops().complete_close_task(item, evidence)
                refresh()
            except Exception as e:
                messagebox.showerror("Cannot complete", str(e), parent=self.root)

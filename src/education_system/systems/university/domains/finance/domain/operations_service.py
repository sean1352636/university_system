"""Operational finance workflows: suppliers, purchasing, AP, cash and VAT."""

from datetime import date

from education_system.systems.university.infrastructure.database.db import get_connection

SCHEMA = """
CREATE TABLE IF NOT EXISTS finance_suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    bank_verified INTEGER DEFAULT 0,
    risk_rating TEXT DEFAULT 'low',
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS finance_purchase_orders (
    id INTEGER PRIMARY KEY,
    po_number TEXT UNIQUE NOT NULL,
    supplier_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    net_amount REAL NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES finance_suppliers(id)
);

CREATE TABLE IF NOT EXISTS finance_ap_invoices (
    id INTEGER PRIMARY KEY,
    invoice_number TEXT NOT NULL,
    supplier_id INTEGER NOT NULL,
    po_id INTEGER,
    net_amount REAL NOT NULL,
    vat_amount REAL DEFAULT 0,
    due_date TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (supplier_id, invoice_number),
    FOREIGN KEY (supplier_id) REFERENCES finance_suppliers(id)
);

CREATE TABLE IF NOT EXISTS finance_cash_movements (
    id INTEGER PRIMARY KEY,
    movement_date TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('inflow', 'outflow')),
    category TEXT,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'forecast',
    description TEXT
);

CREATE TABLE IF NOT EXISTS finance_vat_entries (
    id INTEGER PRIMARY KEY,
    tax_date TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id INTEGER,
    tax_code TEXT NOT NULL,
    net_amount REAL NOT NULL,
    vat_amount REAL NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('input', 'output'))
);

CREATE TABLE IF NOT EXISTS finance_fixed_assets (
    id INTEGER PRIMARY KEY,
    asset_tag TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    cost REAL NOT NULL,
    acquired_date TEXT NOT NULL,
    useful_life_years INTEGER NOT NULL,
    residual_value REAL DEFAULT 0,
    location TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS finance_approval_items (
    id INTEGER PRIMARY KEY,
    item_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    amount REAL,
    requested_by TEXT,
    status TEXT DEFAULT 'pending',
    decision_by TEXT,
    decision_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS finance_fraud_cases (
    id INTEGER PRIMARY KEY,
    payment_id INTEGER,
    risk_score REAL NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'open',
    assigned_to TEXT,
    decision TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finance_close_tasks (
    id INTEGER PRIMARY KEY,
    period_label TEXT NOT NULL,
    task_name TEXT NOT NULL,
    owner TEXT,
    status TEXT DEFAULT 'pending',
    evidence TEXT,
    UNIQUE (period_label, task_name)
);
"""

PURCHASE_ORDER_STATUSES = {
    "submitted",
    "approved",
    "ordered",
    "received",
    "closed",
    "cancelled",
}

READABLE_TABLES = {
    "finance_purchase_orders",
    "finance_ap_invoices",
    "finance_cash_movements",
    "finance_vat_entries",
    "finance_fixed_assets",
    "finance_approval_items",
    "finance_fraud_cases",
    "finance_close_tasks",
}

CLOSE_CHECKLIST_TASKS = (
    "Complete bank reconciliation",
    "Review suspense accounts",
    "Post depreciation",
    "Review VAT control",
    "Approve journals",
    "Lock reporting period",
)


class FinanceOperationsService:
    def __init__(self, connection_factory=get_connection):
        self.connect = connection_factory
        self.init_schema()

    def init_schema(self):
        with self.connect() as c:
            c.executescript(SCHEMA)

    def add_supplier(self, name, email="", risk="low"):
        if not name.strip():
            raise ValueError("Supplier name is required")
        with self.connect() as c:
            return c.execute(
                "INSERT INTO finance_suppliers(name,email,risk_rating) VALUES(?,?,?)",
                (name.strip(), email.strip(), risk),
            ).lastrowid

    def list_suppliers(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM finance_suppliers ORDER BY name")]

    def update_supplier_controls(self, supplier_id, bank_verified=None, status=None, risk=None):
        fields = []
        values = []
        for name, value in (
            ("bank_verified", bank_verified),
            ("status", status),
            ("risk_rating", risk),
        ):
            if value is not None:
                fields.append(name + "=?")
                values.append(int(value) if name == "bank_verified" else value)
        if fields:
            with self.connect() as c:
                c.execute(
                    "UPDATE finance_suppliers SET " + ",".join(fields) + " WHERE id=?",
                    values + [supplier_id],
                )

    def create_po(self, supplier_id, description, net_amount):
        if not str(description).strip():
            raise ValueError("Description is required")
        if float(net_amount) <= 0:
            raise ValueError("Amount must be positive")
        with self.connect() as c:
            # Serialize number allocation across connections.  MAX(id)+1 is
            # otherwise vulnerable to two concurrent purchase orders choosing
            # the same human-readable number.
            c.execute("BEGIN IMMEDIATE")
            if not c.execute("SELECT 1 FROM finance_suppliers WHERE id=?", (supplier_id,)).fetchone():
                raise ValueError("Supplier not found")
            n = c.execute("SELECT COALESCE(MAX(id),0)+1 FROM finance_purchase_orders").fetchone()[0]
            number = f"PO-{date.today().year}-{n:05d}"
            return c.execute(
                "INSERT INTO finance_purchase_orders(po_number,supplier_id,description,net_amount) VALUES(?,?,?,?)",
                (number, supplier_id, description, float(net_amount)),
            ).lastrowid

    def add_invoice(self, supplier_id, invoice_number, net, vat=0, due_date=None, po_id=None):
        if float(net) <= 0 or float(vat) < 0:
            raise ValueError("Invoice net amount must be positive and VAT cannot be negative")
        with self.connect() as c:
            supplier = c.execute("SELECT 1 FROM finance_suppliers WHERE id=?", (supplier_id,)).fetchone()
            if not supplier:
                raise ValueError("Supplier not found")
            if po_id is not None:
                po = c.execute("SELECT supplier_id FROM finance_purchase_orders WHERE id=?", (po_id,)).fetchone()
                if not po or po[0] != supplier_id:
                    raise ValueError("Purchase order does not belong to supplier")
            return c.execute(
                "INSERT INTO finance_ap_invoices(invoice_number,supplier_id,po_id,net_amount,vat_amount,due_date) VALUES(?,?,?,?,?,?)",
                (invoice_number, supplier_id, po_id, float(net), float(vat), due_date),
            ).lastrowid

    def advance_po(self, po_id, status):
        if status not in PURCHASE_ORDER_STATUSES:
            raise ValueError("Invalid PO status")
        with self.connect() as c:
            c.execute("UPDATE finance_purchase_orders SET status=? WHERE id=?", (status, po_id))

    def approve_invoice(self, invoice_id):
        with self.connect() as c:
            inv = c.execute(
                "SELECT po_id,net_amount FROM finance_ap_invoices WHERE id=?", (invoice_id,)
            ).fetchone()
            if not inv:
                raise ValueError("Invoice not found")
            if inv[0]:
                po = c.execute(
                    "SELECT net_amount,status FROM finance_purchase_orders WHERE id=?", (inv[0],)
                ).fetchone()
                if (
                    not po
                    or po[1] not in {"received", "closed"}
                    or abs(float(po[0]) - float(inv[1])) > 0.01
                ):
                    raise ValueError("Three-way match failed")
            c.execute("UPDATE finance_ap_invoices SET status='approved' WHERE id=?", (invoice_id,))

    def record_cash(
        self, kind, category, amount, movement_date=None, status="forecast", description=""
    ):
        if kind not in {"inflow", "outflow"}:
            raise ValueError("Invalid cash movement kind")
        if float(amount) <= 0:
            raise ValueError("Cash amount must be positive")
        with self.connect() as c:
            return c.execute(
                "INSERT INTO finance_cash_movements(movement_date,kind,category,amount,status,description) VALUES(?,?,?,?,?,?)",
                (
                    movement_date or date.today().isoformat(),
                    kind,
                    category,
                    float(amount),
                    status,
                    description,
                ),
            ).lastrowid

    def record_vat(self, source_type, source_id, tax_code, net, vat, direction, tax_date=None):
        if float(net) <= 0 or float(vat) < 0:
            raise ValueError("VAT net amount must be positive and VAT cannot be negative")
        if direction not in {"input", "output"}:
            raise ValueError("Invalid VAT direction")
        with self.connect() as c:
            return c.execute(
                "INSERT INTO finance_vat_entries(tax_date,source_type,source_id,tax_code,net_amount,vat_amount,direction) VALUES(?,?,?,?,?,?,?)",
                (
                    tax_date or date.today().isoformat(),
                    source_type,
                    source_id,
                    tax_code,
                    float(net),
                    float(vat),
                    direction,
                ),
            ).lastrowid

    def rows(self, table):
        if table not in READABLE_TABLES:
            raise ValueError("Invalid table")
        with self.connect() as c:
            # db-audit: ignore[DBW001] - statement builds SQL without splicing a value
            return [dict(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 500")]

    def cash_summary(self):
        with self.connect() as c:
            r = c.execute(
                "SELECT COALESCE(SUM(CASE WHEN kind='inflow' THEN amount ELSE -amount END),0) balance, COALESCE(SUM(CASE WHEN status='forecast' AND kind='inflow' THEN amount ELSE 0 END),0) expected_in, COALESCE(SUM(CASE WHEN status='forecast' AND kind='outflow' THEN amount ELSE 0 END),0) expected_out FROM finance_cash_movements"
            ).fetchone()
            return dict(r)

    def vat_summary(self):
        with self.connect() as c:
            r = c.execute(
                "SELECT COALESCE(SUM(CASE WHEN direction='output' THEN vat_amount ELSE 0 END),0) output_vat, COALESCE(SUM(CASE WHEN direction='input' THEN vat_amount ELSE 0 END),0) input_vat FROM finance_vat_entries"
            ).fetchone()
            d = dict(r)
            d["net_payable"] = d["output_vat"] - d["input_vat"]
            return d

    def add_asset(self, tag, description, cost, life, acquired=None, residual=0, location=""):
        if not tag.strip() or not description.strip():
            raise ValueError("Asset tag and description are required")
        if float(cost) <= 0 or int(life) <= 0:
            raise ValueError("Cost and useful life must be positive")
        if float(residual) < 0 or float(residual) > float(cost):
            raise ValueError("Residual value must be between zero and cost")
        with self.connect() as c:
            return c.execute(
                "INSERT INTO finance_fixed_assets(asset_tag,description,cost,acquired_date,useful_life_years,residual_value,location) VALUES(?,?,?,?,?,?,?)",
                (
                    tag,
                    description,
                    float(cost),
                    acquired or date.today().isoformat(),
                    int(life),
                    float(residual),
                    location,
                ),
            ).lastrowid

    def asset_book_value(self, asset_id, as_of=None):
        with self.connect() as c:
            r = c.execute(
                "SELECT cost,acquired_date,useful_life_years,residual_value FROM finance_fixed_assets WHERE id=?",
                (asset_id,),
            ).fetchone()
        if not r:
            raise ValueError("Asset not found")
        years = max(0, ((as_of or date.today()) - date.fromisoformat(r[1])).days / 365.25)
        annual = (r[0] - r[3]) / r[2]
        return max(r[3], r[0] - annual * years)

    def request_approval(self, item_type, entity_id, amount, requested_by):
        with self.connect() as c:
            return c.execute(
                "INSERT INTO finance_approval_items(item_type,entity_id,amount,requested_by) VALUES(?,?,?,?)",
                (item_type, entity_id, amount, requested_by),
            ).lastrowid

    def decide_approval(self, item_id, decision, user, notes=""):
        if decision not in {"approved", "rejected"}:
            raise ValueError("Invalid decision")
        with self.connect() as c:
            current = c.execute("SELECT status FROM finance_approval_items WHERE id=?", (item_id,)).fetchone()
            if not current:
                raise ValueError("Approval item not found")
            if current[0] != "pending":
                raise ValueError("Approval item has already been decided")
            c.execute(
                "UPDATE finance_approval_items SET status=?,decision_by=?,decision_at=CURRENT_TIMESTAMP,notes=? WHERE id=? AND status='pending'",
                (decision, user, notes, item_id),
            )

    def create_fraud_case(self, payment_id, risk_score, reason):
        score = float(risk_score)
        if score < 0 or score > 1:
            raise ValueError("Risk score must be between 0 and 1")
        with self.connect() as c:
            return c.execute(
                "INSERT INTO finance_fraud_cases(payment_id,risk_score,reason) VALUES(?,?,?)",
                (payment_id, score, reason),
            ).lastrowid

    def decide_fraud_case(self, case_id, decision, user):
        with self.connect() as c:
            c.execute(
                "UPDATE finance_fraud_cases SET status='closed',decision=?,assigned_to=? WHERE id=?",
                (decision, user, case_id),
            )

    def reassign_fraud_case(self, case_id, assignee):
        if not str(assignee).strip():
            raise ValueError("Assignee is required")
        with self.connect() as c:
            updated = c.execute(
                "UPDATE finance_fraud_cases SET assigned_to=? WHERE id=? AND status='open'",
                (assignee, case_id),
            ).rowcount
            if not updated:
                raise ValueError("Fraud case is missing or not open")

    def reopen_fraud_case(self, case_id):
        with self.connect() as c:
            updated = c.execute(
                "UPDATE finance_fraud_cases SET status='open',decision=NULL WHERE id=? AND status='closed'",
                (case_id,),
            ).rowcount
            if not updated:
                raise ValueError("Only a closed fraud case can be reopened")

    def seed_close_checklist(self, period, owner=""):
        with self.connect() as c:
            for task in CLOSE_CHECKLIST_TASKS:
                c.execute(
                    "INSERT OR IGNORE INTO finance_close_tasks(period_label,task_name,owner) VALUES(?,?,?)",
                    (period, task, owner),
                )

    def complete_close_task(self, task_id, evidence):
        if not evidence.strip():
            raise ValueError("Evidence is required")
        with self.connect() as c:
            task = c.execute(
                "SELECT period_label, task_name, status FROM finance_close_tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not task:
                raise ValueError("Close task not found")
            if task[2] == "complete":
                raise ValueError("Close task is already complete")
            previous = c.execute(
                "SELECT 1 FROM finance_close_tasks WHERE period_label=? AND id<? AND status!='complete'",
                (task[0], task_id),
            ).fetchone()
            if previous:
                raise ValueError("Close tasks must be completed in order")
            c.execute(
                "UPDATE finance_close_tasks SET status='complete',evidence=? WHERE id=?",
                (evidence, task_id),
            )

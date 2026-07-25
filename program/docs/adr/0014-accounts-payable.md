# 0014 — Accounts Payable & Vendor Master

**Date:** 2026-05-08
**Status:** Proposed

---

## Context

Item #3 from the finance-system Tier-1 gap survey (2026-05-07).

The platform tracks the **revenue side** of finance well — student
tuition, commerce sales, refunds, payroll runs (since 8.117.117) — but
has no consolidated story for paying suppliers. The picture is more
nuanced than "AP doesn't exist":

**What exists (scattered):**

- **Generic `purchase_orders` table** with all the right columns
  (`vendor`, `supplier_id`, `tax_amount`, `shipping_cost`,
  `approved_by`, `expected_delivery`, etc.) — 0 rows. Created but
  never wired to any UI or service.
- **`PurchaseOrdersGUI` in restaurant management** — full ~1000-line
  workflow for restaurant-specific inventory POs. Working.
- **Per-subsystem supplier tables** — `restaurant_suppliers`,
  `cafe_suppliers`, `grocery_suppliers`, `butcher_supplier_orders`,
  `eco_suppliers` (student union). Each silo manages its own.
- **`expense_categories.gl_code TEXT`** — vestigial; flagged in
  earlier audits as a column with no validation, no chart link, no
  posting logic.
- **HR payroll** (now GL-hooked in 8.117.117) is technically a form of
  AP but is structurally different enough to keep separate.

**What's missing:**

- No **vendor master** — no single table anyone can join through; each
  commerce silo defines its own suppliers, with no de-duplication
- No **consolidated AP officer view** — an AP officer can't see "all
  unpaid bills" across departments
- No **purchase-order workflow at the institution level** — utilities,
  IT, professional services, building maintenance all have no home
- No **three-way match** (PO → goods receipt → invoice → payment)
- No **payment runs** (batch outgoing-payments via Bacs file or SEPA)
- No **GL postings for purchase commitments or supplier invoices**

**Cash-basis vs. accrual tension** — ADR 0013 chose cash basis for the
GL. AP is fundamentally an accrual concept: you recognise the
liability when the supplier invoice arrives, before paying it. Under
strict cash basis, the 2100 Accounts Payable account in the chart
would never carry a balance. This ADR confronts that head-on.

### Alternatives considered

1. **Stay on cash basis with no AP module.** Suppliers are paid; the
   GL records the cash-out at payment time. Simple but loses
   commitment-tracking, ageing-payables reports, and the ability to
   run statutory accounts. Acceptable only for very small organisations.
2. **External AP package** (Xero, NetSuite, SAP). Push purchases out
   to a third-party system. Multi-system integration cost; loses
   per-subsystem context (which department raised the PO, which
   project it's for). Not chosen.
3. **Modified cash basis with AP as an opt-in layer.** Routine
   below-threshold purchases stay cash-basis (post directly to expense
   on payment); larger invoices use full AP recognition (Dr Expense /
   Cr AP on receipt; Dr AP / Cr Cash on payment). Chosen approach
   below — pragmatic compromise that doesn't force a full accrual
   migration.
4. **Build full accrual AP** to FRS 102 standard. Right answer
   long-term but ~6 weeks of engineering plus accountancy sign-off on
   recognition policies. Out of scope for v1; should be revisited
   alongside ADR 0017 (fixed assets) since both push toward accrual.

## Decision

We will build a **modified cash basis** AP module, scoped to
institution-level procurement. Each commerce subsystem keeps its own
operational PO/supplier flow (restaurant inventory, cafe stock, etc.);
those are tactical and don't need to merge into central AP. The
central module handles utilities, IT, professional services, building
maintenance, capital purchases, and any other supplier paid via
finance department rather than a department's local procurement card.

### 1. Schema

Eight new tables:

```sql
CREATE TABLE vendors (
    vendor_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_code        TEXT    UNIQUE NOT NULL,        -- e.g. 'V-2026-0042'
    name               TEXT    NOT NULL,
    legal_name         TEXT,
    company_number     TEXT,                            -- UK Companies House
    vat_number         TEXT,
    contact_email      TEXT,
    contact_phone      TEXT,
    address            TEXT,
    payment_terms_days INTEGER NOT NULL DEFAULT 30,    -- net days
    bank_sort_code     TEXT,
    bank_account       TEXT,                            -- for Bacs payment runs
    default_expense_account TEXT,                       -- e.g. '5400' Other Op Ex
    is_active          INTEGER NOT NULL DEFAULT 1,
    notes              TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    created_by         TEXT
);

CREATE TABLE ap_purchase_orders (
    po_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number          TEXT    UNIQUE NOT NULL,        -- e.g. 'PO-2026-0042'
    vendor_id          INTEGER NOT NULL REFERENCES vendors(vendor_id),
    order_date         TEXT    NOT NULL,
    expected_delivery  TEXT,
    department         TEXT,
    project_code       TEXT,                            -- optional, for cost-centre reporting
    status             TEXT    NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','approved','partially_received',
                                            'received','invoiced','closed','cancelled')),
    total_net          REAL    NOT NULL DEFAULT 0,
    total_vat          REAL    NOT NULL DEFAULT 0,
    total_gross        REAL    NOT NULL DEFAULT 0,
    raised_by          TEXT,
    approved_by        TEXT,
    approved_at        TEXT,
    notes              TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE ap_purchase_order_lines (
    po_line_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id              INTEGER NOT NULL REFERENCES ap_purchase_orders(po_id) ON DELETE CASCADE,
    line_no            INTEGER NOT NULL,
    description        TEXT    NOT NULL,
    quantity           REAL    NOT NULL,
    unit_price_net     REAL    NOT NULL,
    vat_rate           TEXT    NOT NULL DEFAULT 'standard',
    line_net           REAL    NOT NULL,
    line_vat           REAL    NOT NULL DEFAULT 0,
    line_gross         REAL    NOT NULL,
    expense_account_code TEXT,                          -- defaults from vendor or category
    UNIQUE (po_id, line_no)
);

CREATE TABLE ap_goods_receipts (
    gr_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id              INTEGER NOT NULL REFERENCES ap_purchase_orders(po_id),
    received_date      TEXT    NOT NULL,
    received_by        TEXT,
    notes              TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE ap_goods_receipt_lines (
    gr_line_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    gr_id              INTEGER NOT NULL REFERENCES ap_goods_receipts(gr_id) ON DELETE CASCADE,
    po_line_id         INTEGER NOT NULL REFERENCES ap_purchase_order_lines(po_line_id),
    qty_received       REAL    NOT NULL
);

CREATE TABLE ap_supplier_invoices (
    invoice_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_internal_no TEXT   UNIQUE NOT NULL,        -- e.g. 'AP-2026-0042'
    vendor_id          INTEGER NOT NULL REFERENCES vendors(vendor_id),
    vendor_invoice_no  TEXT    NOT NULL,                -- the supplier's invoice number
    invoice_date       TEXT    NOT NULL,
    due_date           TEXT    NOT NULL,
    po_id              INTEGER REFERENCES ap_purchase_orders(po_id),
    total_net          REAL    NOT NULL,
    total_vat          REAL    NOT NULL DEFAULT 0,
    total_gross        REAL    NOT NULL,
    amount_paid        REAL    NOT NULL DEFAULT 0,
    status             TEXT    NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','matched','approved','paid','cancelled','disputed')),
    received_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    received_by        TEXT,
    matched_at         TEXT,
    matched_by         TEXT,
    notes              TEXT,
    UNIQUE (vendor_id, vendor_invoice_no)
);

CREATE TABLE ap_supplier_invoice_lines (
    invoice_line_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id         INTEGER NOT NULL REFERENCES ap_supplier_invoices(invoice_id) ON DELETE CASCADE,
    line_no            INTEGER NOT NULL,
    po_line_id         INTEGER REFERENCES ap_purchase_order_lines(po_line_id),
    description        TEXT,
    quantity           REAL,
    line_net           REAL    NOT NULL,
    vat_rate           TEXT    NOT NULL DEFAULT 'standard',
    line_vat           REAL    NOT NULL DEFAULT 0,
    line_gross         REAL    NOT NULL,
    expense_account_code TEXT  NOT NULL,
    UNIQUE (invoice_id, line_no)
);

CREATE TABLE ap_payment_runs (
    payment_run_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date           TEXT    NOT NULL,
    bank_account       TEXT    NOT NULL,                -- which bank account is paying
    total_amount       REAL    NOT NULL DEFAULT 0,
    invoice_count      INTEGER NOT NULL DEFAULT 0,
    status             TEXT    NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','approved','generated','paid','cancelled')),
    bacs_file_path     TEXT,                            -- if Bacs file generated
    generated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    generated_by       TEXT,
    approved_by        TEXT,
    approved_at        TEXT
);

CREATE TABLE ap_payment_run_lines (
    payment_line_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_run_id     INTEGER NOT NULL REFERENCES ap_payment_runs(payment_run_id) ON DELETE CASCADE,
    invoice_id         INTEGER NOT NULL REFERENCES ap_supplier_invoices(invoice_id),
    amount             REAL    NOT NULL,
    UNIQUE (payment_run_id, invoice_id)
);
```

### 2. Three-way match

The integrity check at invoice-approval time:

```
For each invoice line that references a PO line:
    Σ qty_received (across goods_receipts for that po_line)  >=  invoice_line.quantity
    AND invoice_line.line_net is within tolerance of (po_line.unit_price_net × invoice_line.quantity)
```

Tolerance is configurable (default ±2% or £5 per line, whichever is
larger — handles rounding and small price variances). A failed match
puts the invoice in `disputed` status and surfaces in an exception
queue for the AP officer.

Lines without a `po_id` (one-off invoices, recurring services without
a PO — utilities, professional fees) skip the match check and go
straight to `matched` status on receipt.

### 3. Posting (modified cash basis)

The boundary between cash-basis posting and accrual posting is the
**capitalisation threshold**, defined per vendor or per expense
category (default £500, same as ADR 0017).

**Below threshold (or `vendor.payment_terms_days = 0` — paid
immediately):**

```
On payment:
  Dr  <expense_account_code>    line_net
  Dr  1300 VAT Input             line_vat
  Cr  1010 Cash                  line_gross
```

No AP recognition. Supplier invoice still recorded for audit but
doesn't post on receipt — only on payment.

**Above threshold (the AP path):**

```
On supplier invoice approval (after 3-way match):
  Dr  <expense_account_code>    line_net
  Dr  1300 VAT Input             line_vat
  Cr  2100 Accounts Payable      line_gross

On payment (via payment run):
  Dr  2100 Accounts Payable      paid_amount
  Cr  1010 Cash                  paid_amount
```

The trial balance shows AP balance = unpaid approved invoices.

**Goods received not invoiced (GRNI)** — only applies if the
institution adopts full accrual later. v1 doesn't post on goods
receipt; the GR table is a record of physical receipt for the 3-way
match only.

### 4. AP-side input VAT

ADR 0015 (VAT) covers the output side; the AP ADR is where input VAT
gets posted. Each invoice line's `vat_rate` and `line_vat` flow
straight to account 1300 VAT Input. The partial-exemption percentage
(if any — see ADR 0015) is applied at quarterly return time, not at
posting time, so input VAT is initially recognised in full.

If the institution becomes partially exempt, a year-end adjustment
journal moves the irrecoverable proportion from 1300 VAT Input to
the relevant expense account.

### 5. Payment runs

A payment run aggregates approved unpaid invoices into a single batch:

1. Operator creates a draft run, adds invoices (or auto-selects all
   invoices due in the next N days)
2. Run is approved by a different user (segregation of duties)
3. On approval, the run generates either:
   - A Bacs file (UK direct credit format) for upload to the bank
   - A list of payments to be made manually
4. When the bank confirms execution, the run is marked `paid`, which
   posts one journal per invoice (Dr 2100 / Cr 1010) and updates
   `invoice.amount_paid` and `invoice.status`.

Bacs file generation is an optional v2 feature; v1 produces a printable
list and assumes the operator records payments manually.

### 6. UI

A **🧾 Accounts Payable** parent tab with sub-views:

- **Vendors** — vendor master CRUD; per-vendor view shows recent
  invoices, total spend YTD, ageing of open invoices
- **Purchase Orders** — list / create / approve / receive POs;
  3-way-match status indicators
- **Supplier Invoices** — receive invoice, attach to PO (or stand-alone),
  match, approve, view ageing
- **Payment Runs** — create draft, add invoices, approve, generate
  Bacs/list
- **AP Aging Report** — 30/60/90 day buckets per vendor

### 7. Migration & coexistence

The existing per-subsystem supplier tables (restaurant_suppliers, etc.)
are **not** migrated into the central vendor master. Those are tactical
operational records for inventory replenishment and stay where they
are; central AP is for institutional procurement.

If finance later wants a single supplier list, a **vendor merge tool**
can be built that pulls distinct supplier names from each subsystem
table, presents them to finance for de-duplication, and creates
central vendor records. Out of scope for v1.

The empty `purchase_orders` table from the existing schema is
**deprecated** in favour of `ap_purchase_orders` (clearer naming,
proper FK design). The old table can be dropped once verified empty
in production.

## Consequences

### Positive

- AP officer has a single view of all unpaid invoices and their ageing
- 3-way match catches receiving / pricing errors before payment goes
  out the door
- Supplier-level analytics (top spend, payment-on-time rate, payment
  terms compliance)
- Foundation for vendor-direct integrations later (PO submission via
  email/EDI)
- Capital purchases can be hooked to fixed-asset register (ADR 0017):
  paying an invoice marked "capital" creates a `fixed_assets` entry
  automatically

### Negative / trade-offs

- **Build cost.** Schema + 3-way match + posting + UI: ~6 weeks for
  one engineer. Bigger than payroll/GL because of the 3-way match
  complexity and the segregation-of-duties requirement on payment runs.
- **Modified cash basis is a hybrid.** Some auditors prefer "accrual
  or nothing"; the threshold-based split needs to be explainable in
  the year-end audit working papers.
- **Two parallel supplier registers** (central + per-subsystem) is a
  recognised compromise but creates de-duplication pain if a vendor
  appears in both
- **Bacs file format**: BACSTEL-IP / Bacstel is the standard but
  needs bank-side setup. v1 output format may need iteration.
- **Cross-subsystem visibility loss**: a department that has its own
  supplier system (restaurant) won't have spend visible in the central
  AP officer view. Acceptable trade-off for v1.

### Neutral

- The seeded chart already has 2100 Accounts Payable; no chart
  changes required for AP itself (VAT and category-specific expense
  accounts handled separately)
- Existing payroll AP-side recognition (Cr 2100 for deductions in
  8.117.117) remains, since deductions are payable to HMRC/pension —
  the new module just adds non-payroll AP rows alongside them

---

### Open questions to resolve before implementation

1. **Capitalisation threshold** for the cash-vs-accrual posting
   split: institution-wide or per-category? Default £500 — finance to
   confirm.
2. **Three-way match tolerance**: ±2% or £5 per line is a reasonable
   starting point; finance may want stricter (large capital purchases)
   or looser (high-volume utilities).
3. **Payment run approval workflow**: who approves? Often two-tier
   (AP officer creates, Finance Director approves above £X). Schema
   needs a `second_approval_required_above` threshold if so.
4. **Bacs file format**: BACSTEL-IP, BACS Direct Credit Standard, or
   bank-specific CSV? Each bank's format differs.
5. **Multi-currency vendors** (foreign suppliers): depends on ADR 0016
   being in place. Until then, AP is GBP-only.
6. **VAT on imports / reverse charge** (services from non-UK
   suppliers): UK reverse-charge rules require accounting for output
   AND input VAT on the same import. Out of scope v1.
7. **Vendor de-duplication**: do we run a merge tool against the
   per-subsystem supplier tables? When?
8. **Supplier statements reconciliation**: monthly statement-vs-invoice
   reconciliation is standard practice. v1 doesn't include it.
9. **Recurring invoices** (utilities, software subscriptions) —
   supported as one-off invoices in v1, or as a separate template
   pattern with auto-generation?
10. **Construction-in-progress / capital projects** integration with
    ADR 0017 fixed assets — how do staged payments to a contractor
    accumulate into a final asset?

These should be answered with finance staff (and external auditor)
before implementation begins; the ADR can be amended once they're
settled.

### Estimated build cost

Schema + vendor master CRUD: ~1 week.
PO workflow + GR + 3-way match: ~2 weeks.
Supplier invoice receipt + matching + approval: ~1 week.
Payment runs + GL posting hooks: ~1 week.
UI (5 sub-tabs) + tests + documentation: ~1 week.
**Total: ~6 weeks** for one engineer. The longest of the deferred
finance ADRs because of the workflow complexity.

---

*Related: ADR 0013 (General Ledger — AP recognition stretches the
cash-basis decision), ADR 0015 (VAT — input VAT posts via this
module), ADR 0017 (Fixed Assets — capital purchases acquired via AP),
ADR 0016 (Multi-currency — non-GBP supplier invoices).*

# 0013 — Add a General Ledger to the Finance Subsystem

**Date:** 2026-05-08
**Status:** Proposed

---

## Context

The university Finance subsystem (`education_system/university_system/modules/domain/finance/`)
today tracks money as a set of siloed operational tables:

- `payments` — student fee receipts, club payments, top-ups (heterogeneous, with `source_type` discriminator)
- `student_fees` + `payment_allocations` — what students owe, what got applied
- `unified_refunds` — refunds across departments
- `late_fees`, `student_credits`, `financial_aid`, `collection_cases`, `budget_plans`, etc.

Each table is queried directly by the relevant tab in the Finance GUI. Reports are produced by
ad-hoc SQL aggregations over these tables (`report_manager.py`, `dashboard.py`).

This works for day-to-day operations but cannot answer accounting questions:

- **Trial balance / balance sheet / P&L** — there is no accounts structure. Revenue, refunds, AR,
  cash, deferred income are not modelled as accounts you can sum.
- **Cash vs. accrual** — revenue is recognised implicitly when a payment is recorded; tuition
  paid in advance for a future term is not deferred. There is no concept of accrual.
- **Audit trail at the accounting level** — `unified_refunds.processed_by` and friends record
  who clicked what, but there is no immutable double-entry record showing what hit which account.
- **Period close** — no concept of "August is closed, no more entries". A user could amend a
  three-year-old refund and the dashboard totals would silently change.
- **External reporting** — OfS financial returns, statutory accounts, and external auditors all
  expect double-entry records. Producing those from operational tables is fragile and
  unrepeatable.

The platform now serves multiple subsystems (university, sixth form, secondary, primary), each
with its own commerce, accommodation, and refund flows. Continuing without a ledger means each
subsystem accretes its own ad-hoc reporting SQL, drifting further from a single source of
financial truth.

### Alternatives considered

1. **Continue with operational-tables-only reporting.** Keep using direct aggregations.
   *Rejected* — does not solve trial-balance, accrual, or period-close, and the drift compounds.
2. **Buy / integrate an external accounting package** (Xero, NetSuite, SAP) and push events out.
   *Deferred* — viable long-term, but out of scope for this codebase. An internal ledger can later
   become the producer of journals into an external system without rework.
3. **Build the ledger inside this codebase.** Add a chart of accounts, journal entries, posting
   rules from existing operational events, and standard reports. *Chosen approach below.*

## Decision

We will add an internal general ledger to the Finance subsystem. The ledger sits alongside the
operational tables and is fed by **posting rules** that translate each operational event into
balanced double-entry journal lines.

### 1. Schema (additive — no changes to existing operational tables)

Four new tables in the existing finance database:

```sql
-- Chart of accounts. Hierarchical via parent_account_id; type drives sign conventions
-- and where the account appears in standard reports.
CREATE TABLE gl_accounts (
    account_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    account_code      TEXT    NOT NULL UNIQUE,        -- e.g. '1100', '4000-TUI'
    account_name      TEXT    NOT NULL,
    account_type      TEXT    NOT NULL,               -- 'asset' | 'liability' | 'equity' | 'revenue' | 'expense'
    parent_account_id INTEGER REFERENCES gl_accounts(account_id),
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Accounting periods. Posting is rejected when target period is closed.
CREATE TABLE gl_periods (
    period_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    fiscal_year INTEGER NOT NULL,
    period_no   INTEGER NOT NULL,                     -- 1..12 calendar month within fiscal year
    start_date  TEXT    NOT NULL,
    end_date    TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'open',      -- 'open' | 'closed' | 'locked'
    closed_at   TEXT,
    closed_by   TEXT,
    UNIQUE (fiscal_year, period_no)
);

-- Journal header. One per economic event. Source identifies the operational origin.
CREATE TABLE gl_journals (
    journal_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_date    TEXT    NOT NULL,                  -- effective accounting date
    period_id       INTEGER NOT NULL REFERENCES gl_periods(period_id),
    description     TEXT    NOT NULL,
    source_type     TEXT    NOT NULL,                  -- 'payment' | 'refund' | 'fee_assignment' | 'manual' | ...
    source_id       INTEGER,                           -- FK into the originating table (e.g. payments.payment_id)
    posted_by       TEXT    NOT NULL,
    posted_at       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reversed_by_id  INTEGER REFERENCES gl_journals(journal_id),  -- if this journal was reversed, points at reversal
    is_reversal_of  INTEGER REFERENCES gl_journals(journal_id),  -- if this journal IS a reversal, points at original
    UNIQUE (source_type, source_id)                    -- idempotency: one journal per source event
);

-- Journal lines. Each journal must have ≥2 lines and SUM(debit) = SUM(credit).
CREATE TABLE gl_journal_lines (
    line_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_id  INTEGER NOT NULL REFERENCES gl_journals(journal_id),
    account_id  INTEGER NOT NULL REFERENCES gl_accounts(account_id),
    debit       DECIMAL(12,2) NOT NULL DEFAULT 0,
    credit      DECIMAL(12,2) NOT NULL DEFAULT 0,
    memo        TEXT,
    CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);
CREATE INDEX idx_gl_lines_journal ON gl_journal_lines(journal_id);
CREATE INDEX idx_gl_lines_account ON gl_journal_lines(account_id);
```

Balance enforcement and "≥2 lines" are application-level invariants enforced by the posting
service (SQLite cannot easily express SUM-equality constraints).

### 2. Posting service

A single service module — `modules/domain/finance/ledger/posting.py` — exposes one public
function per operational event type:

```python
def post_payment(payment_id: int) -> int:        # returns journal_id
def post_refund(refund_id: int) -> int:
def post_fee_assignment(student_fee_id: int) -> int:
def post_aid_disbursement(aid_id: int) -> int:
def post_late_fee(late_fee_id: int) -> int:
def reverse_journal(journal_id: int, reason: str) -> int:
```

Each function:
1. Reads the operational row.
2. Looks up the relevant accounts via mapping rules (see §3).
3. Builds a balanced journal in a single transaction.
4. Returns the new `journal_id`.
5. Is idempotent — re-running for the same source returns the existing `journal_id` (uses the
   `UNIQUE (source_type, source_id)` index).

### 3. Posting rules — the mapping that operational columns become accounts

The trickiest part is deciding what gets debited/credited. Initial mapping:

| Event                        | Debit                       | Credit                      |
|------------------------------|-----------------------------|-----------------------------|
| Fee assigned (`student_fees`)| AR — Students (1100)        | Tuition Revenue (4000)      |
| Payment received             | Cash / Bank (1000)          | AR — Students (1100)        |
| Refund processed             | Tuition Revenue (4000)      | Cash / Bank (1000)          |
| Aid disbursed                | Aid Expense (5200)          | AR — Students (1100)        |
| Late fee assessed            | AR — Students (1100)        | Late Fee Income (4100)      |
| Write-off                    | Bad Debt Expense (5300)     | AR — Students (1100)        |

Mappings are config-driven (a `gl_posting_rules` config or simple Python module), not hardcoded
inside `post_payment` etc., so finance staff can adjust without code changes.

Source-type variants matter: a `payments` row with `source_type='club'` should credit Club
Revenue (4200), not Tuition Revenue. The mapping table keys on `(event, source_type, ...)`.

### 4. Period management

- `period_id` is computed at posting time from `journal_date`.
- If the target period's status is `closed`, posting fails with an explicit error and the user is
  prompted to either change the journal date or have an admin reopen the period.
- A `gl_close_period(period_id)` operation flips status to `closed`. Admins with the right role
  can reopen with audit. `locked` is a stronger close (e.g. after year-end audit) that no role
  can reopen — only superseding journals.
- "Closed" prevents posting *into* the period; it does not prevent posting *as of* a later date
  with reference to the closed period (e.g. an adjusting journal in the next open period).

### 5. UI surface (Finance GUI)

Five new tabs (admin/staff only), as a first cut:

- **Chart of Accounts** — view tree, add/edit/deactivate.
- **Journals** — list view of `gl_journals` with drill-down to lines; filter by date, source,
  account; reverse a journal (creates a paired reversal journal, never edits the original).
- **Trial Balance** — debit/credit totals per account over a date range.
- **P&L / Balance Sheet** — standard reports built from `gl_accounts.account_type`.
- **Period Close** — list periods, close/reopen with audit.

These replace nothing in the existing GUI. The operational tabs (Payments, Fees, Refunds, etc.)
continue to work as today. Posting hooks attach to the existing record actions so a posted
operational event also produces a journal.

### 6. Backfill

Existing rows in `payments`, `student_fees`, `unified_refunds`, etc. need to be backfilled into
the GL when the feature is first deployed. Migration script:

1. Create the four new tables and seed `gl_accounts` from the standard chart.
2. Create periods covering the historical date range.
3. Iterate every operational row and call the relevant `post_*` function.
4. Reconcile: SUM of operational table totals should equal SUM of corresponding account balances.
   Any divergence is logged for manual review before backfill is marked complete.

The backfill is idempotent (the `UNIQUE (source_type, source_id)` constraint), so it can be
re-run safely.

### 7. Testing

- Unit tests on each `post_*` function: assert balanced journal, correct accounts, correct
  amounts.
- Property test: for any operational event, calling its post function twice produces exactly
  one journal.
- Integration test: seed a known set of operational rows, run backfill, assert trial-balance
  totals match operational aggregates.
- Period-close test: close a period, assert posting into it fails; reopen, assert it succeeds.

## Consequences

### Positive

- Auditable double-entry record of every economic event.
- Trial balance, P&L, and balance sheet become trivial queries instead of fragile aggregations.
- Period close prevents silent drift in historical reports.
- Future external accounting integration (Xero etc.) can read from `gl_journals` directly — the
  hard work is already done.
- Multi-currency, accrual basis, and deferred-income recognition can be added later within the
  same model without re-architecting.

### Negative / trade-offs

- **Build cost** — schema, posting service, mapping rules, UI, backfill, tests. Realistically
  3–5 weeks for one engineer, longer if posting rules need finance-staff sign-off.
- **Discipline cost** — every new operational event type that affects money must add a posting
  rule. Forgetting one means the GL silently understates that flow. CI test that asserts every
  `payments.source_type` value has a mapping is the mitigation.
- **Backfill risk** — historical rows may have inconsistencies (e.g. refunds without a matching
  payment). Backfill must report these rather than silently fudge them.
- **Operational coupling** — the operational tables become the system of record for the *event*,
  but the GL becomes the system of record for the *accounting*. Disagreements between them
  become a class of bug to investigate.

### Neutral

- The existing operational tabs and reports continue working unchanged during and after rollout.
- Subsystems other than the university (sixth form, secondary, primary) can adopt the same
  ledger design later — the schema is subsystem-agnostic.

---

### Open questions to resolve before implementation

1. **Account codes** — adopt a standard chart (e.g. UK SORP for HE) or design our own?
2. **Cash vs. accrual** — accept cash basis as v1, or build accrual from day one (deferred
   tuition, prepayments)? Cash is faster but means a v2 migration.
3. **Multi-entity** — is this one ledger for the whole institution, or do subsystems (and
   subsidiary trading companies, e.g. catering) have separate ledgers consolidated at the top?
4. **VAT** — ADR 0014 (proposed) covers VAT separately; the GL design assumes VAT is tracked
   on a dedicated account (e.g. 2200 — VAT Output, 1300 — VAT Input) and posted alongside
   revenue/expense by the same posting rules.
5. **Year-end close vs. month-end close** — both? Just year-end initially?

These should be answered with finance staff before implementation begins; the ADR can be
amended once they're settled.

---

*Related: ADR 0006 (domain-driven module structure) — the GL lives inside the existing
`finance` domain, not as a separate top-level module.*

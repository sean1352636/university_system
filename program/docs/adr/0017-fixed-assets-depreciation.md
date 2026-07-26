# 0017 — Fixed Assets & Depreciation

**Date:** 2026-05-08
**Status:** Proposed

---

## Context

Item #15 from the finance-system gap survey (2026-05-07).

A university typically has the largest single category of fixed assets
of any service organisation: buildings (residences, academic blocks,
libraries), vehicles, IT infrastructure (servers, classroom AV,
laboratory equipment), furniture, and plant. Capital expenditure is
required by accounting standards (FRS 102 / SORP for HE) to be
**capitalised** (recorded as a fixed asset) and **depreciated** over
its useful economic life — not expensed in the year of acquisition.

The platform has nothing for this today:

- **No asset register.** No `fixed_assets` table, no acquisition cost
  tracking, no useful-life data, no location/custodian.
- **No depreciation calculation.** Even if assets were tracked, there's
  no monthly or annual depreciation run.
- **No GL postings for depreciation.** The seeded chart has `5xxx`
  expense accounts (5000 Staff Costs, 5100 Premises, etc.) but no
  dedicated `Depreciation Expense` account, and no
  `Accumulated Depreciation` contra-asset accounts.
- **`expense_categories.gl_code TEXT`** is vestigial — flagged in
  earlier audits as a column with no validation, no chart link, no
  posting logic. It hints someone considered fixed-asset categorisation
  but never followed through.
- **`equipment_rentals` table exists** in commerce/campus but only for
  short-term hire (rental income), not for capitalised university-owned
  equipment.

For an institution of any size, this is an audit blocker. Statutory
accounts cannot be produced from a system that expenses every capital
purchase in-period and has no reconciled fixed-asset note.

### Alternatives considered

1. **Spreadsheet-based register.** Many small organisations run their
   asset register in Excel and feed totals into the GL via manual
   journals. Acceptable up to a certain size but loses the per-asset
   audit trail (location, condition, custodian) and disconnects from
   the operational system that records the original purchase.
2. **External fixed-asset module.** Standalone packages exist (e.g.
   Sage Fixed Assets, Real Asset Management). Out of scope — adds an
   integration dependency and licensing cost for a problem that's
   well-bounded.
3. **Build the fixed-asset module in this codebase.** Chosen approach.

## Decision

We will add a fixed-asset register and depreciation-run service to the
finance domain, with GL postings hooked the same way payroll and
payments are. Scope is intentionally focused on the **operational
mechanics** (registry, depreciation calculation, disposal). The
**accountancy decisions** (useful-life tables, capitalisation
threshold, depreciation method per category) live in a configuration
table that finance staff can edit without code changes.

### 1. Schema

Three new tables:

```sql
CREATE TABLE fixed_assets (
    asset_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_code            TEXT    UNIQUE NOT NULL,        -- e.g. 'IT-2026-0042'
    name                  TEXT    NOT NULL,
    description           TEXT,
    category              TEXT    NOT NULL,               -- FK to fixed_asset_categories
    acquisition_date      TEXT    NOT NULL,
    acquisition_cost      REAL    NOT NULL,
    salvage_value         REAL    NOT NULL DEFAULT 0,     -- residual value at end of life
    useful_life_months    INTEGER NOT NULL,               -- straight-line denominator
    depreciation_method   TEXT    NOT NULL DEFAULT 'straight_line'
                            CHECK (depreciation_method IN ('straight_line','reducing_balance','none')),
    reducing_balance_rate REAL,                            -- only for reducing_balance
    location              TEXT,
    custodian             TEXT,                            -- staff_id / department
    status                TEXT    NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','disposed','impaired','retired')),
    disposed_date         TEXT,
    disposal_proceeds     REAL,                            -- cash received on disposal
    asset_account_code    TEXT    NOT NULL DEFAULT '1500', -- e.g. 1510 Buildings, 1520 Vehicles
    accumulated_depreciation_account_code TEXT NOT NULL DEFAULT '1600',
    notes                 TEXT,
    created_at            TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT
);

CREATE TABLE fixed_asset_categories (
    category              TEXT PRIMARY KEY,           -- e.g. 'IT_Equipment'
    display_name          TEXT NOT NULL,
    default_useful_life_months INTEGER NOT NULL,
    default_depreciation_method TEXT NOT NULL,
    asset_account_code    TEXT NOT NULL,              -- 1510, 1520, 1530, …
    accumulated_depreciation_account_code TEXT NOT NULL,
    capitalisation_threshold REAL NOT NULL DEFAULT 500.00
);

CREATE TABLE depreciation_runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    period_end    TEXT NOT NULL,                     -- last day of the period being depreciated
    generated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    generated_by  TEXT,
    journal_id    INTEGER REFERENCES gl_journals(journal_id),
    total_depreciation REAL NOT NULL DEFAULT 0,
    asset_count   INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'completed',
    UNIQUE (period_end)                              -- one run per period_end
);

CREATE TABLE depreciation_lines (
    line_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id               INTEGER NOT NULL REFERENCES depreciation_runs(run_id) ON DELETE CASCADE,
    asset_id             INTEGER NOT NULL REFERENCES fixed_assets(asset_id),
    depreciation_amount  REAL    NOT NULL,
    accumulated_to_date  REAL    NOT NULL,
    nbv                  REAL    NOT NULL              -- net book value after this run
);
```

### 2. Chart of accounts additions

Extends the seeded SORP chart. Conventional UK ranges:

```
1500–1599  Property, Plant & Equipment (cost)
  1510  Buildings
  1520  Plant & Machinery
  1530  IT Equipment
  1540  Furniture & Fittings
  1550  Vehicles
  1590  Capital Work in Progress

1600–1699  Accumulated Depreciation (contra-asset, credit balance)
  1610  Accumulated Depreciation — Buildings
  1620  Accumulated Depreciation — Plant & Machinery
  1630  Accumulated Depreciation — IT Equipment
  1640  Accumulated Depreciation — Furniture & Fittings
  1650  Accumulated Depreciation — Vehicles

5500  Depreciation Expense  (P&L)

4500  Gain on Disposal of Fixed Assets   (other income)
5550  Loss on Disposal of Fixed Assets   (operating expense)
```

The `1600` series are **contra-asset** accounts: they sit on the asset
side of the chart but normally carry a credit balance. Net Book Value
(NBV) on the balance sheet is `cost (1500-) − accumulated depreciation
(1600-)`.

### 3. Depreciation methods

**Straight-line** (default, covers ~90% of assets):

```
monthly_depreciation = (acquisition_cost − salvage_value) / useful_life_months
```

Stops when accumulated depreciation reaches `cost − salvage`. The asset
remains on the register at salvage value until disposed.

**Reducing balance**:

```
monthly_rate = (1 − (salvage / cost)^(1 / useful_life_months))
monthly_depreciation = NBV × monthly_rate
```

Stops when NBV reaches salvage. Used for assets that lose value faster
in early years (vehicles, some IT).

**None**: configured for assets that don't depreciate (land, art).
Skipped by the run.

### 4. Posting

**Acquisition** (when an asset is added to the register):

```
Dr  1530 IT Equipment           cost
Cr  2100 Accounts Payable       cost          (or 1010 Cash if paid immediately)
```

This depends on Accounts Payable existing (ADR 0014 prerequisite). For
v1, if AP isn't available, post directly against Cash 1010.

**Monthly depreciation** (one journal per run, with one debit and one
credit pair per asset category):

```
Dr  5500 Depreciation Expense   sum_for_period
Cr  1610 Acc. Dep. — Buildings  buildings_share
Cr  1630 Acc. Dep. — IT Equip.  it_share
Cr  1640 Acc. Dep. — Furniture  furniture_share
Cr  1650 Acc. Dep. — Vehicles   vehicles_share
```

The debit aggregates so the trial balance shows a single Depreciation
Expense line. Per-asset detail lives in `depreciation_lines`.

**Disposal**:

```
Dr  1010 Cash                                            disposal_proceeds
Dr  1610 Acc. Dep. — (category)                          accumulated_to_date  -- clear it
Cr  1530 (category cost account)                         acquisition_cost     -- clear it
Dr/Cr  4500 / 5550  Gain or Loss on Disposal             plug to balance
```

The plug is `proceeds − NBV`: positive → gain (Cr 4500), negative →
loss (Dr 5550).

### 5. Service surface

```python
# Module: education_system/.../modules/domain/finance/fixed_assets/

def init_fixed_assets()                                     # idempotent schema + chart
def register_asset(...) -> int                              # → asset_id, posts acquisition journal
def run_depreciation(period_end, generated_by) -> dict      # → run_id + summary
def dispose_asset(asset_id, disposed_date, proceeds, by)    # posts disposal journal
def asset_register(category=None, status='active') -> list  # report
def nbv_at(period_end, asset_id=None) -> dict | float       # NBV report
```

Idempotency: depreciation runs `UNIQUE(period_end)` so re-running for
the same period returns the existing run without duplicating journals.
Asset register is keyed on `asset_code` (UNIQUE) so re-importing
historical data won't create duplicates.

### 6. UI

A new **🏭 Fixed Assets** tab (admin/staff) with three sub-views:

- **Register** — list of assets, filterable by category and status.
  Add / edit / dispose actions. Per-row drilldown shows acquisition
  details, current NBV, depreciation history.
- **Depreciation runs** — list of runs with totals, link to the GL
  journal. Run-now button (typically monthly).
- **Asset categories** — config view: per-category default useful
  life, depreciation method, asset / accumulated-depreciation account
  codes, capitalisation threshold.

### 7. Capitalisation threshold

Per-category configurable. Items below the threshold are expensed
(post directly to a 5xxx expense account on acquisition) instead of
being capitalised. Implementation: `register_asset` checks
`category.capitalisation_threshold` against `acquisition_cost`; below
threshold, the function posts an expense journal and does NOT insert
into `fixed_assets`. This keeps the asset register noise-free.

### 8. Migration & backfill

Existing operational data has no fixed-asset content (verified — no
asset/equipment/depreciation tables outside the few rental-related
ones in commerce/campus). On adoption:

1. Run `init_fixed_assets()` to create schema + chart + default
   categories.
2. Finance staff manually load the historical asset register from
   whatever spreadsheet they're currently using. Each `register_asset`
   call for a historical asset should pass `acquisition_date` in the
   past — the function must accept this and create the journal in the
   correct historical period (which raises `PeriodClosedError` if
   that period is now closed; admin reopens, posts, and re-closes).
3. Optionally, run `backfill_depreciation(from_date, to_date)` to
   produce one journal per period from the asset's acquisition to the
   current month. This brings accumulated depreciation up-to-date in
   one operation.

## Consequences

### Positive

- Statutory accounts become possible (depreciation note, NBV by
  category, additions/disposals reconciliation)
- Net Book Value visible on the balance sheet without spreadsheet
  cross-referencing
- Disposal gain/loss flows to P&L automatically (manual journals at
  year-end go away)
- Audit trail per asset (custodian, location, condition over time)
- Foundation for capital project / construction-in-progress
  accounting later (assets-under-construction sit in `1590` and
  transfer to a category account on commissioning)

### Negative / trade-offs

- **Build cost.** Schema + register + depreciation runs + disposal
  posting + UI: realistically 3–4 weeks for one engineer.
- **Accountancy decisions before code.** Useful-life tables and
  category boundaries need finance-staff input. The defaults below are
  defensible starting points, not authoritative.
- **Historical data load.** Onboarding an existing register is the
  hardest part — typically painful no matter what tool you adopt.
  Documenting the spreadsheet → CSV → `register_asset` import path
  carefully is part of the rollout.
- **Compounds with closed-period work.** If finance staff are still
  registering historical assets after period close has been adopted
  (ADR 0010 / 8.117.110), they'll hit `PeriodClosedError` regularly
  and need admin reopens. Tolerable but adds friction.
- **Component depreciation not supported.** Some assets (e.g. a
  building with a roof on a different useful life from the structure)
  technically need to be split into components and depreciated
  separately. v1 uses a single-component approximation.

### Neutral

- Existing operational paths (payments, refunds, fees, payroll) are
  untouched. Fixed assets is purely additive.
- Lease accounting (right-of-use assets per IFRS 16) is **not**
  covered by this ADR — it's a separate problem with its own
  recognition rules. UK FRS 102 has a different lease treatment from
  IFRS 16; the choice depends on which framework the institution
  reports under.

---

### Default category seed

```
('Buildings',          'Buildings',           50*12, 'straight_line', '1510','1610',  500.00)
('Plant_Machinery',    'Plant & Machinery',   10*12, 'straight_line', '1520','1620',  500.00)
('IT_Equipment',       'IT Equipment',         3*12, 'straight_line', '1530','1630',  500.00)
('Furniture',          'Furniture & Fittings',10*12, 'straight_line', '1540','1640',  500.00)
('Vehicles',           'Vehicles',             5*12, 'reducing_balance', '1550','1650', 500.00)
('Land',               'Land (no depreciation)', 0,  'none',          '1500','1600',  500.00)
```

`500.00` capitalisation threshold is a common starting point; finance
may adjust upward (e.g. £1000 for IT) or by category.

### Open questions to resolve before implementation

1. **Reporting framework**: FRS 102, FRS 105, or IFRS? Lease treatment
   and revaluation policy differ. Most UK universities are on FRS 102
   with the SORP for HE.
2. **Depreciation frequency**: monthly journals (matches GL period
   close) or annual? Monthly is more accurate; annual is operationally
   simpler. Pick one.
3. **Capitalisation threshold**: institution-wide or per-category?
   Schema supports per-category; finance picks.
4. **Revaluation upwards**: not in v1, but a possible future need
   (FRS 102 allows it for Property).
5. **Capital projects / construction-in-progress**: should there be a
   `capital_projects` table feeding into `1590` Capital WIP, with
   transfer to a category account on commissioning? Out of scope here
   but worth scoping if the institution undertakes building works.
6. **Component depreciation**: supported or not? FRS 102 requires it
   for assets where components have materially different useful lives.
   v1 says no; v2 may need to.
7. **Government grants** that fund asset acquisitions may need to be
   amortised through the P&L over the asset's life (FRS 102 Section
   24). This is a posting-rules decision, not a schema decision.

These should be answered with finance staff (and external auditor)
before implementation begins; the ADR can be amended once they're
settled.

### Estimated build cost

Schema + categories + register CRUD: ~1 week.
Depreciation calculator + run + GL posting hooks: ~1 week.
Disposal flow + GUI tab: ~1 week.
Backfill helper + tests + documentation: ~1 week.
**Total: ~4 weeks** for one engineer, assuming open questions are
answered up front and the historical data load is reasonably clean.

---

*Related: ADR 0013 (General Ledger), ADR 0014 (Accounts Payable —
acquisition postings need AP if not paid in cash), ADR 0010 (period
close — historical asset registration interacts with closed periods).*

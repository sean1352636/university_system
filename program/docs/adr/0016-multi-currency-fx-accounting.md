# 0016 — Multi-Currency & FX Accounting

**Date:** 2026-05-08
**Status:** Proposed

---

## Context

Item #14 from the finance-system gap survey (2026-05-07).

The platform records every monetary amount as a plain `DECIMAL`/`REAL`
with no currency dimension. UI strings hardcode `f"£{amount:.2f}"`
across the codebase. The General Ledger added in ADR 0013 sums every
journal line in implicit GBP. There is no FX gain/loss account in the
seeded chart, no exchange-rate table, and no revaluation function.

This works while every transaction is GBP, but the platform already
has data points that aren't:

- `payments.currency` exists with `DEFAULT 'GBP'` — almost always GBP,
  but rows do exist where a writer set a different code (none in dev,
  but the column is part of the contract)
- International student tuition is sometimes paid in the student's
  home currency (USD/EUR/CNY most commonly) before being converted to
  GBP at the receiving bank
- Research grants from non-UK funders arrive in foreign currency
- Conference income from overseas attendees is sometimes invoiced and
  paid in EUR or USD
- Some commerce subsystems (e.g. cinema, charity shop) accept card
  payments where the customer's billing currency may not be GBP — the
  acquirer settles in GBP after FX

If any of these flows produce a non-GBP transaction, the GL silently
posts the foreign-currency amount as if it were GBP, and the trial
balance lies. We need to make the currency dimension explicit before
that becomes a real audit issue.

### Alternatives considered

1. **Pretend everything is GBP.** Only acceptable if foreign-currency
   activity is genuinely zero. Most institutions cross that threshold
   without noticing.
2. **External FX engine.** Push every transaction through a third-party
   service that handles rate-fetch, conversion, and revaluation.
   Out of scope — adds an integration dependency for a problem that's
   well-understood and small in scale at the volumes UK universities
   typically transact.
3. **Build the FX layer in this codebase.** Chosen approach below.

## Decision

We will add an FX layer to the GL and operational tables. The base
(functional and presentation) currency is **GBP**. Multi-base operation
(separate functional and reporting currencies) is explicitly out of
scope; UK institutions don't need it.

### 1. Schema changes (additive, nullable defaults)

Three new columns on every monetary operational table:

```sql
ALTER TABLE payments         ADD COLUMN currency      TEXT;        -- already present
ALTER TABLE payments         ADD COLUMN fx_rate       REAL;        -- transaction-currency → base
ALTER TABLE payments         ADD COLUMN base_amount   REAL;        -- amount × fx_rate, denormalised

ALTER TABLE unified_refunds  ADD COLUMN currency      TEXT;
ALTER TABLE unified_refunds  ADD COLUMN fx_rate       REAL;
ALTER TABLE unified_refunds  ADD COLUMN base_amount   REAL;

ALTER TABLE student_fees     ADD COLUMN currency      TEXT;
ALTER TABLE student_fees     ADD COLUMN fx_rate       REAL;
ALTER TABLE student_fees     ADD COLUMN base_amount   REAL;
```

NULL means "GBP at parity" (`fx_rate=1.0`, `base_amount=amount`). The
posting service treats NULL like that on read — no migration of
existing rows required, identical behaviour to today.

Two new tables:

```sql
CREATE TABLE fx_rates (
    rate_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    currency    TEXT    NOT NULL,            -- ISO 4217 code, e.g. 'USD'
    rate_date   TEXT    NOT NULL,            -- date the rate was effective
    rate_to_base REAL   NOT NULL,            -- 1 unit of `currency` = rate_to_base GBP
    source      TEXT    NOT NULL,            -- 'manual' | 'hmrc' | 'ecb' | 'card_acquirer'
    notes       TEXT,
    UNIQUE (currency, rate_date, source)
);

-- For revaluation runs (period-end FX revaluation of open AR / AP / cash)
CREATE TABLE fx_revaluation_runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    period_end    TEXT NOT NULL,
    generated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    generated_by  TEXT,
    total_gain    REAL,
    total_loss    REAL,
    journal_id    INTEGER REFERENCES gl_journals(journal_id),
    status        TEXT NOT NULL DEFAULT 'completed'
);
```

### 2. Chart-of-accounts additions

Three new accounts seeded by `init_ledger()`:

```
4400  FX Gain (revenue side)              -- realised + unrealised FX gains
5400  FX Loss (already exists; expense)   -- realised + unrealised FX losses
1050  Cash — USD bank account             -- if held; pattern repeats per currency
1051  Cash — EUR bank account             -- ...
```

The base currency cash account remains `1010 Bank — Operating Account`.
Per-currency cash accounts are added on demand when a non-GBP bank
account is opened.

### 3. Posting changes

`_post_journal` already accepts a list of lines. Each line gains a
`currency`, `fx_rate`, and `base_amount` field with sensible defaults
(GBP at parity). The line's `debit`/`credit` is the transaction-currency
amount; `base_amount` is what gets summed in the trial balance.

```sql
ALTER TABLE gl_journal_lines ADD COLUMN currency    TEXT;
ALTER TABLE gl_journal_lines ADD COLUMN fx_rate     REAL;
ALTER TABLE gl_journal_lines ADD COLUMN base_amount REAL;
```

`trial_balance` (and every report) sums `base_amount` instead of
`debit`/`credit` directly. NULL `base_amount` falls back to
`COALESCE(base_amount, debit - credit)` for backward compatibility
with existing journals.

The balance check that `Σdebit_base = Σcredit_base` per journal
remains the source-of-truth invariant. Journals with mixed-currency
lines are allowed (a USD payment received into a GBP bank produces a
USD-credited line and a GBP-debited line; FX gain/loss is the
balancing line).

### 4. Rate-fetch strategy

Three sources, in priority order:

1. **Explicit on the row.** If a writer sets `fx_rate` directly,
   that's used.
2. **`fx_rates` lookup** by `(currency, journal_date)`. If multiple
   rows exist for the same date (different sources), prefer
   `card_acquirer` > `hmrc` > `ecb` > `manual` (acquirer rates are
   what actually settled; HMRC publishes monthly rates for VAT use;
   ECB is fallback).
3. **Last known rate** if the date is missing — emit a warning and
   use the most recent rate before `journal_date`.

If no rate is found, the post fails with `FXRateNotFoundError` rather
than silently posting at parity. This is a blocking error: cash basis
posting can't proceed without a defensible rate.

### 5. Revaluation

At period close, run `revalue_fx_balances(period_end)`:

1. Find every account holding a non-base balance (any account where the
   sum of journal lines in foreign currency is non-zero).
2. For each: compute the closing-rate value vs. the historical-cost
   value already posted.
3. Difference goes to FX Gain (4400) or FX Loss (5400) with a single
   revaluation journal, tagged `source_type='fx_revaluation'`.
4. Record the run in `fx_revaluation_runs` with the journal_id.

This is run once per period, idempotent on `(period_end, source_type)`.

### 6. UI

A new **💱 Currency** tab (or extension of the existing one) gives
finance staff:

- View / edit the `fx_rates` table (manual rate entry)
- Trigger period-end revaluation
- View the revaluation history
- See trial-balance sub-totals broken out by currency for the
  open balances (sanity check before close)

The existing per-transaction VAT split (ADR 0015) and GL posting (ADR
0013) work unchanged — they sum on `base_amount`.

### 7. Migration & backfill

Existing rows: NULL `currency`/`fx_rate`/`base_amount` is the same as
GBP-at-parity. No migration required for read paths.

Optional one-shot: a `backfill_base_amount()` script populates
`base_amount = amount` for every NULL row. Useful for clean reporting
queries that don't want the COALESCE branch. Idempotent.

## Consequences

### Positive

- Trial balance is reliably in base currency regardless of writer behaviour
- FX gain/loss is visible as an explicit P&L line, not a silent error
- Period-end revaluation is a deliberate operation finance staff
  perform, not an emergent property
- Per-currency reporting is possible without restructuring (filter
  journal lines by `currency`)
- Schema is additive; existing code continues to work

### Negative / trade-offs

- **Discipline cost.** Every new INSERT into `payments` /
  `unified_refunds` / `student_fees` must populate the three new
  columns or accept GBP-at-parity defaults. CI test that asserts every
  writer sets currency explicitly when amount is non-trivial.
- **Rate management.** Someone has to keep `fx_rates` populated. For an
  institution that takes one or two non-GBP transactions per quarter,
  manual entry is fine; for higher volumes, an API-fetch script is
  needed (out of scope here).
- **VAT subtlety.** UK VAT must always be reported in GBP using the
  HMRC-published monthly rate, regardless of the actual rate at which
  cash converted. Either ADR 0015 (VAT) handles this with a separate
  `vat_base_amount` column or the VAT split is computed using a
  different rate from the cash split. This is a real complication —
  flagged for ADR 0015 to resolve.
- **Bank rec gets harder.** Bank lines from a foreign-currency account
  will arrive in that currency; the matcher (added in 8.117.119)
  needs to convert to base before comparing amounts, OR maintain a
  per-bank-account currency dimension.

### Neutral

- The seeded chart already has `1300 VAT Input` / `2200 VAT Output`;
  the FX accounts add to but don't change that
- Existing GBP-only trial balance keeps working through the COALESCE
  fallback

---

### Open questions to resolve before implementation

1. **Acquirer rate or HMRC rate** for routine commerce transactions?
   Card acquirer rates are tighter; HMRC monthly rates simplify VAT
   reporting. Picking one as default avoids per-transaction confusion.
2. **Held bank accounts.** Does the institution actually hold non-GBP
   bank accounts? If not, the per-currency cash-account pattern is
   premature; revaluation only applies to open AR balances.
3. **Translation gain vs. transaction gain.** Distinguishing the two in
   reporting is an accountancy decision (some institutions report them
   together; some separately).
4. **Frequency of revaluation.** Monthly (matches GL period close) or
   only year-end? Monthly is more accurate but adds a step to month-end
   close.
5. **Rounding policy.** ROUND_HALF_EVEN is standard for accounting. The
   posting service uses `Decimal.quantize(0.01)` already — confirm this
   stays consistent for FX-converted amounts (potential off-by-1p on
   reciprocal calculations).

These should be answered with finance staff before implementation
begins; the ADR can be amended once they're settled.

### Estimated build cost

Schema + posting changes + tests: ~1 week.
Revaluation function + UI for rate management: ~1 week.
Migration of existing FX-touching writers (e.g. unifying `payments.currency`
treatment, fixing hardcoded "£" UI strings): ~1 week, mechanical.
**Total: ~3 weeks** for one engineer, assuming open questions are
answered up front.

---

*Related: ADR 0013 (General Ledger), ADR 0015 (VAT — has a dependency
on the rate-source decision here).*

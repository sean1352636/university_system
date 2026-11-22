"""General Ledger — double-entry accounting layer over the operational finance tables.

See docs/adr/0013-general-ledger.md for design rationale.

Public surface:
    init_ledger()             — create schema, seed default entity + chart, init periods
    post_payment(payment_id)  — post a payments row to the ledger (idempotent)
    post_refund(refund_id)    — post a unified_refunds row to the ledger (idempotent)
    post_fee_assignment(fee_id)
    backfill()                — replay all unposted operational events into the ledger
    trial_balance(start_date, end_date, entity_id=None)
    close_period(period_id, closed_by)
    lock_period(period_id, locked_by)
    reopen_period(period_id)  — reverses 'closed' only; 'locked' cannot be reopened
    open_fiscal_year(fy, opened_by) — open a year's 12 periods (the current and next
                                year also open on their own when something posts)
"""

from education_system.systems.university.domains.finance.domain.ledger.schema import init_ledger
from education_system.systems.university.domains.finance.domain.ledger.posting import (
    post_payment, post_refund, post_fee_assignment, post_payroll_run,
    backfill, JournalUnbalancedError, PeriodClosedError, AccountNotFoundError,
)
from education_system.systems.university.domains.finance.domain.ledger.periods import (
    close_period, lock_period, reopen_period, list_periods, open_fiscal_year,
)
from education_system.systems.university.domains.finance.domain.ledger.reports import trial_balance
from education_system.systems.university.domains.finance.domain.ledger.hooks import (
    notify_ledger, LEDGER_HOOK_FAILURES,
)

__all__ = [
    'init_ledger',
    'post_payment', 'post_refund', 'post_fee_assignment', 'post_payroll_run', 'backfill',
    'close_period', 'lock_period', 'reopen_period', 'list_periods', 'open_fiscal_year',
    'trial_balance',
    'notify_ledger', 'LEDGER_HOOK_FAILURES',
    'JournalUnbalancedError', 'PeriodClosedError', 'AccountNotFoundError',
]

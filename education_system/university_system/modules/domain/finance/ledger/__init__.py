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
"""

from education_system.university_system.modules.domain.finance.ledger.schema import init_ledger
from education_system.university_system.modules.domain.finance.ledger.posting import (
    post_payment, post_refund, post_fee_assignment, post_payroll_run,
    backfill, JournalUnbalancedError, PeriodClosedError, AccountNotFoundError,
)
from education_system.university_system.modules.domain.finance.ledger.periods import (
    close_period, lock_period, reopen_period, list_periods,
)
from education_system.university_system.modules.domain.finance.ledger.reports import trial_balance
from education_system.university_system.modules.domain.finance.ledger.hooks import (
    notify_ledger, LEDGER_HOOK_FAILURES,
)

__all__ = [
    'init_ledger',
    'post_payment', 'post_refund', 'post_fee_assignment', 'post_payroll_run', 'backfill',
    'close_period', 'lock_period', 'reopen_period', 'list_periods',
    'trial_balance',
    'notify_ledger', 'LEDGER_HOOK_FAILURES',
    'JournalUnbalancedError', 'PeriodClosedError', 'AccountNotFoundError',
]

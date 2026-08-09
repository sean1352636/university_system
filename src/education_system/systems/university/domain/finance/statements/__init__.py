"""Periodic student statement runs.

A statement run produces one snapshot row per student showing AR position as
of a chosen period_end date, plus in-period charges and payments. This is
the batch counterpart to InvoiceManager.gui_generate_invoice (which
produces a single on-demand invoice for one student).

Public surface:
    init_statements()                     — create schema (idempotent)
    run_statements_batch(period_end, ...) — generate one row per active student
    list_runs()                            — recent runs
    list_statements(run_id, only_with_balance=False)
    get_statement(run_id, student_id)
"""

from education_system.systems.university.domain.finance.statements.schema import init_statements
from education_system.systems.university.domain.finance.statements.service import (
    run_statements_batch, list_runs, list_statements, get_statement,
)

__all__ = [
    'init_statements',
    'run_statements_batch', 'list_runs', 'list_statements', 'get_statement',
]

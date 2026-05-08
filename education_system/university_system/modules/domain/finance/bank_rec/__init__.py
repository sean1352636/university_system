"""Bank reconciliation — import a bank statement, auto-match lines against
payments / unified_refunds, and surface unmatched lines as an exception queue.

Public surface:
    init_bank_rec()                   — create schema (idempotent)
    import_csv(path, account_name, ...) — import a statement file
    auto_match_statement(statement_id) — run auto-matcher; returns counts
    manual_match(line_id, ..., by)    — operator-confirmed match
    unmatch(line_id)                   — reset a line to 'unmatched'
    discard(line_id, reason, by)       — flag as not relevant (e.g. fee)
    list_statements()                  — list of statements
    list_lines(statement_id, status_filter=None)
"""

from education_system.university_system.modules.domain.finance.bank_rec.schema import init_bank_rec
from education_system.university_system.modules.domain.finance.bank_rec.service import (
    import_csv, auto_match_statement, manual_match, unmatch, discard,
    list_statements, list_lines,
)

__all__ = [
    'init_bank_rec',
    'import_csv', 'auto_match_statement', 'manual_match', 'unmatch', 'discard',
    'list_statements', 'list_lines',
]

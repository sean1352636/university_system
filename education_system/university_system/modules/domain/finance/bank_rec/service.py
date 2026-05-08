"""Bank reconciliation service.

Auto-matching is intentionally simple — exact amount match within a small
date window. False positives are surfaced as `matched_auto` (distinct from
`matched_manual`) so an operator can review and override. The matcher does
NOT post anything to the GL — bank-rec is about confirming the bank's view
agrees with the operational tables, not about creating new journal entries.
"""

import csv
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import get_connection


# Match window: days either side of a statement-line date that we'll search
# for a candidate payment/refund. 3 days handles weekend bank-clearing
# without being so wide it produces ambiguous matches on common amounts.
_DEFAULT_MATCH_WINDOW_DAYS = 3


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_csv(path, account_name, imported_by='admin',
               period_start=None, period_end=None,
               opening_balance=None, closing_balance=None):
    """Import a bank statement CSV.

    Expected columns (case-insensitive, header row required):
        date         — ISO 8601 (YYYY-MM-DD); other formats accepted via dateutil.parser fallback
        amount       — signed decimal; positive = credit (money in), negative = debit (money out)
        description  — free text
        reference    — optional payment reference / counterparty
    Other columns are ignored.

    Returns dict {statement_id, lines_imported, errors}.
    """
    summary = {'statement_id': None, 'lines_imported': 0, 'errors': []}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bank_statements (account_name, period_start, period_end, "
            "opening_balance, closing_balance, imported_by, source_file) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (account_name, period_start, period_end, opening_balance, closing_balance,
             imported_by, str(path)),
        )
        statement_id = cur.lastrowid
        summary['statement_id'] = statement_id

        with open(path, newline='', encoding='utf-8-sig') as fh:
            reader = csv.DictReader(fh)
            # Normalise header keys
            field_map = {k.strip().lower(): k for k in (reader.fieldnames or [])}
            need = ['date', 'amount']
            for n in need:
                if n not in field_map:
                    summary['errors'].append(f"missing required column: {n}")
                    conn.rollback()
                    return summary

            line_no = 0
            for row in reader:
                line_no += 1
                try:
                    txn_date = _parse_date(row[field_map['date']])
                    amount = _parse_amount(row[field_map['amount']])
                    description = (row.get(field_map.get('description', ''), '') or '').strip()
                    reference = (row.get(field_map.get('reference', ''), '') or '').strip()
                except Exception as e:
                    summary['errors'].append(f"line {line_no}: {e}")
                    continue
                cur.execute(
                    "INSERT INTO bank_statement_lines "
                    "(statement_id, line_no, txn_date, amount, description, reference) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (statement_id, line_no, txn_date, amount, description, reference),
                )
                summary['lines_imported'] += 1

        conn.commit()
    except Exception as e:
        summary['errors'].append(f"import failed: {e}")
        conn.rollback()
    finally:
        conn.close()
    return summary


def _parse_date(s):
    """Accept ISO YYYY-MM-DD; fall back to a few common UK formats."""
    s = str(s).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%d-%m-%Y', '%d %b %Y'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date format: {s!r}")


def _parse_amount(s):
    """Accept '12.50', '-12.50', '£12.50', '1,234.56' etc."""
    s = str(s).strip().replace('£', '').replace(',', '').replace(' ', '')
    if not s:
        raise ValueError("empty amount")
    return float(s)


# ---------------------------------------------------------------------------
# Auto-match
# ---------------------------------------------------------------------------

def auto_match_statement(statement_id, window_days=_DEFAULT_MATCH_WINDOW_DAYS):
    """Run the auto-matcher over all unmatched lines in a statement.

    For each line:
      - amount > 0  → credit (money in)  → look for a payment with the same amount
                      whose payment_date is within ±window_days
      - amount < 0  → debit  (money out) → look for a unified_refunds row with the
                      same magnitude within ±window_days

    A match is recorded only when exactly ONE candidate is found (to avoid
    false positives on common amounts). Reference text is used as a tiebreaker
    when multiple candidates exist.

    Returns dict {scanned, matched, ambiguous, errors}.
    """
    summary = {'scanned': 0, 'matched': 0, 'ambiguous': 0, 'errors': []}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT line_id, txn_date, amount, reference "
            "FROM bank_statement_lines "
            "WHERE statement_id = ? AND status = 'unmatched'",
            (statement_id,),
        )
        lines = cur.fetchall()
        for line in lines:
            line_id, txn_date, amount, reference = line[0], line[1], float(line[2]), line[3] or ''
            summary['scanned'] += 1

            # Date window
            try:
                centre = datetime.strptime(txn_date, '%Y-%m-%d').date()
            except ValueError:
                summary['errors'].append((line_id, f"bad txn_date: {txn_date}"))
                continue
            from_date = (centre - timedelta(days=window_days)).isoformat()
            to_date   = (centre + timedelta(days=window_days)).isoformat()

            try:
                if amount > 0:
                    candidates = _candidate_payments(cur, amount, from_date, to_date)
                    # Payment candidate columns: (id, date, transaction_id,
                    # payment_reference, notes) — search reference across all
                    # three text fields when tie-breaking.
                    chosen = _pick_best(candidates, reference, search_idxs=(2, 3, 4))
                    if chosen is not None:
                        cur.execute(
                            "UPDATE bank_statement_lines SET status='matched_auto', "
                            "matched_payment_id=?, matched_at=datetime('now'), matched_by='auto' "
                            "WHERE line_id=?",
                            (chosen[0], line_id),
                        )
                        summary['matched'] += 1
                    elif candidates:
                        summary['ambiguous'] += 1
                elif amount < 0:
                    magnitude = -amount
                    candidates = _candidate_refunds(cur, magnitude, from_date, to_date)
                    # Refund candidate columns: (id, date, refund_reference, notes).
                    chosen = _pick_best(candidates, reference, search_idxs=(2, 3))
                    if chosen is not None:
                        cur.execute(
                            "UPDATE bank_statement_lines SET status='matched_auto', "
                            "matched_refund_id=?, matched_at=datetime('now'), matched_by='auto' "
                            "WHERE line_id=?",
                            (chosen[0], line_id),
                        )
                        summary['matched'] += 1
                    elif candidates:
                        summary['ambiguous'] += 1
                else:
                    # Zero-amount lines (rare) — skip
                    continue
            except Exception as e:
                summary['errors'].append((line_id, str(e)))
        conn.commit()
    finally:
        conn.close()
    return summary


def _candidate_payments(cur, amount, from_date, to_date):
    """Return [(payment_id, payment_date, transaction_id, payment_reference, notes), ...]
    for payments matching amount within the date window and not already matched."""
    cur.execute(
        """SELECT p.payment_id, p.payment_date,
                  COALESCE(p.transaction_id, ''),
                  COALESCE(p.payment_reference, ''),
                  COALESCE(p.notes, '')
           FROM payments p
           LEFT JOIN bank_statement_lines bsl ON bsl.matched_payment_id = p.payment_id
           WHERE ABS(p.amount - ?) < 0.005
             AND substr(p.payment_date, 1, 10) BETWEEN ? AND ?
             AND COALESCE(p.status, 'completed') = 'completed'
             AND bsl.line_id IS NULL
           ORDER BY p.payment_date""",
        (amount, from_date, to_date),
    )
    return cur.fetchall()


def _candidate_refunds(cur, magnitude, from_date, to_date):
    """Return [(refund_id, refund_date, refund_reference, notes), ...] for
    refunds matching magnitude within the date window and not already matched."""
    cur.execute(
        """SELECT r.refund_id, r.refund_date,
                  COALESCE(r.refund_reference, ''),
                  COALESCE(r.notes, '')
           FROM unified_refunds r
           LEFT JOIN bank_statement_lines bsl ON bsl.matched_refund_id = r.refund_id
           WHERE ABS(r.amount - ?) < 0.005
             AND substr(r.refund_date, 1, 10) BETWEEN ? AND ?
             AND COALESCE(r.status, 'pending') IN ('processed','completed')
             AND bsl.line_id IS NULL
           ORDER BY r.refund_date""",
        (magnitude, from_date, to_date),
    )
    return cur.fetchall()


def _pick_best(candidates, reference, search_idxs=(2,)):
    """Single-candidate → match. Multi-candidate → only match if exactly one
    candidate has the bank line's reference appearing in any of its
    `search_idxs` fields. Otherwise leave for manual review (returns None)."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if reference:
        ref_lc = reference.strip().lower()
        if not ref_lc:
            return None
        scored = []
        for c in candidates:
            haystacks = [str(c[i] or '').lower() for i in search_idxs]
            if any(ref_lc in h for h in haystacks):
                scored.append(c)
        if len(scored) == 1:
            return scored[0]
    return None


# ---------------------------------------------------------------------------
# Manual operations
# ---------------------------------------------------------------------------

def manual_match(line_id, *, payment_id=None, refund_id=None, by='admin'):
    """Operator-confirmed match. Exactly one of payment_id or refund_id."""
    if (payment_id is None) == (refund_id is None):
        raise ValueError("exactly one of payment_id or refund_id must be provided")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE bank_statement_lines SET status='matched_manual', "
            "matched_payment_id=?, matched_refund_id=?, matched_at=datetime('now'), matched_by=? "
            "WHERE line_id=?",
            (payment_id, refund_id, by, line_id),
        )
        conn.commit()
    finally:
        conn.close()


def unmatch(line_id):
    """Reset a line to 'unmatched'. Used to undo a wrong auto- or manual-match."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE bank_statement_lines SET status='unmatched', "
            "matched_payment_id=NULL, matched_refund_id=NULL, "
            "matched_at=NULL, matched_by=NULL "
            "WHERE line_id=?",
            (line_id,),
        )
        conn.commit()
    finally:
        conn.close()


def discard(line_id, reason='', by='admin'):
    """Mark a line as not relevant to the operational tables (bank fees,
    interest, etc.). Excluded from the unmatched-exception queue."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE bank_statement_lines SET status='discarded', "
            "matched_at=datetime('now'), matched_by=?, notes=? "
            "WHERE line_id=?",
            (by, reason or None, line_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def list_statements():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT s.statement_id, s.account_name, s.period_start, s.period_end,
                      s.imported_at, s.imported_by, s.source_file,
                      (SELECT COUNT(*) FROM bank_statement_lines WHERE statement_id = s.statement_id) AS lines,
                      (SELECT COUNT(*) FROM bank_statement_lines WHERE statement_id = s.statement_id AND status='unmatched') AS unmatched
               FROM bank_statements s
               ORDER BY s.statement_id DESC"""
        )
        return [
            {
                'statement_id': r[0], 'account_name': r[1],
                'period_start': r[2], 'period_end': r[3],
                'imported_at': r[4], 'imported_by': r[5],
                'source_file': r[6],
                'lines': r[7], 'unmatched': r[8],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def list_lines(statement_id, status_filter=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        params = [statement_id]
        sql = ("SELECT line_id, line_no, txn_date, amount, description, reference, "
               "status, matched_payment_id, matched_refund_id, matched_by "
               "FROM bank_statement_lines WHERE statement_id = ?")
        if status_filter and status_filter != 'all':
            sql += " AND status = ?"
            params.append(status_filter)
        sql += " ORDER BY line_no"
        cur.execute(sql, params)
        return [
            {
                'line_id': r[0], 'line_no': r[1], 'txn_date': r[2], 'amount': r[3],
                'description': r[4], 'reference': r[5], 'status': r[6],
                'matched_payment_id': r[7], 'matched_refund_id': r[8],
                'matched_by': r[9],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()

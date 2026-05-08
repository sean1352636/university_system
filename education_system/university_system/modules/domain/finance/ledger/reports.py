"""GL reports — trial balance for now; P&L and Balance Sheet are derivable extensions."""

from education_system.university_system.infrastructure.database.db import get_connection


def trial_balance(start_date=None, end_date=None, entity_id=None):
    """Return list of dicts: per-account debit/credit totals over the period.

    Each row:
        {
            'account_code': '1010',
            'account_name': 'Bank — Operating Account',
            'account_type': 'asset',
            'debit_total': 12345.00,
            'credit_total': 0.00,
            'balance':  12345.00,   # debit-positive for assets/expenses, credit-positive for others
        }

    The trial balance includes only accounts with non-zero activity in the
    range. Sum(debit_total) and sum(credit_total) across all rows must be
    equal — useful as a self-check.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        params = []
        where = []
        if start_date:
            where.append("j.journal_date >= ?")
            params.append(start_date)
        if end_date:
            where.append("j.journal_date <= ?")
            params.append(end_date)
        if entity_id is not None:
            where.append("j.entity_id = ?")
            params.append(entity_id)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
            SELECT a.account_code, a.account_name, a.account_type,
                   COALESCE(SUM(l.debit), 0)  AS debit_total,
                   COALESCE(SUM(l.credit), 0) AS credit_total
            FROM gl_accounts a
            LEFT JOIN gl_journal_lines l ON l.account_id = a.account_id
            LEFT JOIN gl_journals j      ON j.journal_id = l.journal_id
            {where_sql}
            GROUP BY a.account_id
            HAVING (COALESCE(SUM(l.debit), 0) + COALESCE(SUM(l.credit), 0)) > 0
            ORDER BY a.account_code
        """
        cur.execute(sql, params)
        rows = []
        for code, name, atype, dr, cr in cur.fetchall():
            dr = float(dr or 0)
            cr = float(cr or 0)
            # Balance: debit-positive for asset/expense, credit-positive for the rest
            if atype in ('asset', 'expense'):
                balance = dr - cr
            else:
                balance = cr - dr
            rows.append({
                'account_code': code,
                'account_name': name,
                'account_type': atype,
                'debit_total': dr,
                'credit_total': cr,
                'balance': balance,
            })
        return rows
    finally:
        conn.close()


def journals_list(start_date=None, end_date=None, entity_id=None, source_type=None, limit=500):
    """Return list of (journal_id, journal_date, period_id, description, source_type,
    source_id, entity_id, posted_by, debit_total) for browsing."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        params = []
        where = []
        if start_date:
            where.append("j.journal_date >= ?")
            params.append(start_date)
        if end_date:
            where.append("j.journal_date <= ?")
            params.append(end_date)
        if entity_id is not None:
            where.append("j.entity_id = ?")
            params.append(entity_id)
        if source_type:
            where.append("j.source_type = ?")
            params.append(source_type)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        sql = f"""
            SELECT j.journal_id, j.journal_date, j.period_id, j.description,
                   j.source_type, j.source_id, j.entity_id, j.posted_by,
                   COALESCE((SELECT SUM(debit) FROM gl_journal_lines WHERE journal_id = j.journal_id), 0) AS debit_total
            FROM gl_journals j
            {where_sql}
            ORDER BY j.journal_id DESC
            LIMIT ?
        """
        params.append(int(limit))
        cur.execute(sql, params)
        return [
            {
                'journal_id': r[0], 'journal_date': r[1], 'period_id': r[2],
                'description': r[3], 'source_type': r[4], 'source_id': r[5],
                'entity_id': r[6], 'posted_by': r[7], 'amount': float(r[8] or 0),
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def journal_lines(journal_id):
    """Return the lines of a single journal joined with account info."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT l.line_id, a.account_code, a.account_name,
                      l.debit, l.credit, l.memo
               FROM gl_journal_lines l
               JOIN gl_accounts a ON a.account_id = l.account_id
               WHERE l.journal_id = ?
               ORDER BY l.line_id""",
            (journal_id,),
        )
        return [
            {
                'line_id': r[0], 'account_code': r[1], 'account_name': r[2],
                'debit': float(r[3] or 0), 'credit': float(r[4] or 0), 'memo': r[5],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()

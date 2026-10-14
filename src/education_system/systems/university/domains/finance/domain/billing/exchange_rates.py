"""Exchange-rate table — list, add, edit, delete, refresh, convert.

Non-interactive counterpart to ``billing.fee_structure.update_exchange_rates``
and ``currency_conversion_tool``. The Finance GUI Currency tab, the Finance
settings Currency panel and the Finance CLI Currency menu all call these.
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)

CURRENCIES = ('GBP', 'USD', 'EUR', 'CAD', 'AUD', 'JPY', 'CHF')
RATE_SOURCES = ('manual', 'api', 'bank')

#: Stand-in for a live rate feed; the same figures the GUI's refresh loads.
SAMPLE_RATES = {'USD': 1.27, 'EUR': 1.17, 'CAD': 1.71, 'AUD': 1.91, 'JPY': 188.50, 'CHF': 1.14}

_DATE_FMT = '%Y-%m-%d'
_TS_FMT = '%Y-%m-%d %H:%M:%S'

_SELECT = '''
SELECT rate_id, from_currency, to_currency, exchange_rate, rate_date, source, created_at
FROM exchange_rates
'''


def _normalise_currency(code, label):
    code = (code or '').strip().upper()
    if code not in CURRENCIES:
        raise ValueError(f"{label} must be one of: {', '.join(CURRENCIES)}")
    return code


def _validate_rate(rate):
    rate = float(rate)
    if rate <= 0:
        raise ValueError("Exchange rate must be greater than zero")
    return rate


def base_currency():
    """The configured base currency (``GBP`` when unset)."""
    conn = get_connection()
    try:
        row = conn.execute('SELECT base_currency FROM currency_settings LIMIT 1').fetchone()
        return (row[0] if row and row[0] else 'GBP').upper()
    finally:
        conn.close()


def list_exchange_rates(limit=500):
    """Rates newest first, then by currency pair."""
    conn = get_connection()
    try:
        rows = conn.execute(
            _SELECT + ' ORDER BY rate_date DESC, from_currency, to_currency LIMIT ?',
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_exchange_rate(rate_id):
    """One rate row as a dict, or ``None``."""
    conn = get_connection()
    try:
        row = conn.execute(_SELECT + ' WHERE rate_id = ?', (rate_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_exchange_rate(from_currency, to_currency, rate, source='manual', rate_date=None):
    """Insert a rate row and return its id. Raises ValueError on bad input."""
    from_currency = _normalise_currency(from_currency, "From currency")
    to_currency = _normalise_currency(to_currency, "To currency")
    if from_currency == to_currency:
        raise ValueError("From and to currencies must differ")
    rate = _validate_rate(rate)
    if source not in RATE_SOURCES:
        raise ValueError(f"Source must be one of: {', '.join(RATE_SOURCES)}")
    if rate_date:
        try:
            datetime.strptime(rate_date, _DATE_FMT)
        except ValueError:
            raise ValueError("Rate date must be in YYYY-MM-DD form") from None
    else:
        rate_date = datetime.now().strftime(_DATE_FMT)

    with transaction() as conn:
        cursor = conn.execute('''
        INSERT INTO exchange_rates
        (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (from_currency, to_currency, rate, rate_date, source,
              datetime.now().strftime(_TS_FMT)))
        return cursor.lastrowid


def update_exchange_rate(rate_id, rate=None, source=None, rate_date=None):
    """Change a rate's value, source or date; returns the updated row.

    ``None`` leaves a field alone. Raises ValueError for a missing row or bad
    input.
    """
    if get_exchange_rate(rate_id) is None:
        raise ValueError(f"Exchange rate {rate_id} not found")
    sets, params = [], []
    if rate is not None:
        sets.append('exchange_rate = ?')
        params.append(_validate_rate(rate))
    if source is not None:
        if source not in RATE_SOURCES:
            raise ValueError(f"Source must be one of: {', '.join(RATE_SOURCES)}")
        sets.append('source = ?')
        params.append(source)
    if rate_date is not None:
        try:
            datetime.strptime(rate_date, _DATE_FMT)
        except ValueError:
            raise ValueError("Rate date must be in YYYY-MM-DD form") from None
        sets.append('rate_date = ?')
        params.append(rate_date)
    if sets:
        sets.append('created_at = ?')
        params.append(datetime.now().strftime(_TS_FMT))
        params.append(rate_id)
        with transaction() as conn:
            conn.execute(f"UPDATE exchange_rates SET {', '.join(sets)} WHERE rate_id = ?", params)
    return get_exchange_rate(rate_id)


def delete_exchange_rate(rate_id):
    """Delete a rate row; returns it. Raises ValueError when missing."""
    row = get_exchange_rate(rate_id)
    if row is None:
        raise ValueError(f"Exchange rate {rate_id} not found")
    with transaction() as conn:
        conn.execute('DELETE FROM exchange_rates WHERE rate_id = ?', (rate_id,))
    return row


def refresh_sample_rates(base=None, rates=None):
    """Load today's rates from the base currency (the GUI's "Update Exchange Rates").

    Today's row for each pair is updated in place when it exists, otherwise
    inserted, so refreshing twice in a day does not duplicate rows.
    Returns ``{'base', 'updated', 'pairs'}``.
    """
    base = _normalise_currency(base or base_currency(), "Base currency")
    rates = rates or SAMPLE_RATES
    today = datetime.now().strftime(_DATE_FMT)
    now = datetime.now().strftime(_TS_FMT)
    pairs = []
    with transaction() as conn:
        for currency, rate in rates.items():
            if currency == base:
                continue
            existing = conn.execute('''
            SELECT rate_id FROM exchange_rates
            WHERE from_currency = ? AND to_currency = ? AND rate_date = ?
            ''', (base, currency, today)).fetchone()
            if existing:
                conn.execute('''
                UPDATE exchange_rates SET exchange_rate = ?, source = 'api', created_at = ?
                WHERE rate_id = ?
                ''', (rate, now, existing[0]))
            else:
                conn.execute('''
                INSERT INTO exchange_rates
                (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
                VALUES (?, ?, ?, ?, 'api', ?)
                ''', (base, currency, rate, today, now))
            pairs.append((base, currency, rate))
        conn.execute(
            'UPDATE currency_settings SET last_rate_update = ?, updated_at = ?', (now, now)
        )
    return {'base': base, 'updated': len(pairs), 'pairs': pairs}


def latest_rate(from_currency, to_currency):
    """Most recent rate for a pair, inverting the reverse pair if needed.

    Returns ``(rate, inverted)`` or ``None`` when neither direction exists.
    """
    from_currency = (from_currency or '').upper()
    to_currency = (to_currency or '').upper()
    if from_currency == to_currency:
        return 1.0, False
    conn = get_connection()
    try:
        for a, b, inverted in ((from_currency, to_currency, False),
                               (to_currency, from_currency, True)):
            row = conn.execute('''
            SELECT exchange_rate FROM exchange_rates
            WHERE from_currency = ? AND to_currency = ?
            ORDER BY rate_date DESC, created_at DESC
            LIMIT 1
            ''', (a, b)).fetchone()
            if row and row[0]:
                rate = float(row[0])
                return (1 / rate if inverted else rate), inverted
    finally:
        conn.close()
    return None


def convert_amount(amount, from_currency, to_currency):
    """Convert ``amount``; returns ``(converted, rate)``.

    Raises ValueError for a non-positive amount and LookupError when no rate
    exists in either direction (unlike ``fee_structure.convert_currency``,
    which silently returns the input).
    """
    amount = float(amount)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")
    found = latest_rate(from_currency, to_currency)
    if found is None:
        raise LookupError(f"No exchange rate found for {from_currency}/{to_currency}")
    rate, _inverted = found
    return amount * rate, rate

"""
Multi-Currency — interactive CLI.

Wired to ``billing.exchange_rates`` (list / add / edit / delete / refresh /
convert), which reads/writes ``exchange_rates`` and ``currency_settings`` in
the shared ``student_records.db`` — the same tables the Currency tab and the
settings Currency panel of the Finance GUI use.

Covers: list the exchange-rate table, add a rate, edit a rate, delete a rate,
refresh today's rates from the base currency, convert an amount, and show
the base currency.
"""

from __future__ import annotations

import logging

from education_system.systems.university.domains.finance.domain.billing.exchange_rates import (
    CURRENCIES,
    RATE_SOURCES,
    add_exchange_rate,
    base_currency,
    convert_amount,
    delete_exchange_rate,
    get_exchange_rate,
    list_exchange_rates,
    refresh_sample_rates,
    update_exchange_rate,
)
from education_system.systems.university.domains.finance.interfaces.cli.common import (
    fail,
    ok,
    print_table,
    prompt_bool,
    prompt_choice,
    prompt_date,
    prompt_float,
    prompt_int,
    require_permission,
    run_menu,
    t,
)

logger = logging.getLogger(__name__)


def _rate_rows(rates):
    return [[r['rate_id'], r['from_currency'], r['to_currency'],
             f"{float(r['exchange_rate'] or 0):.4f}", r['rate_date'], r['source'],
             (r['created_at'] or '')[:16]] for r in rates]


_HEADERS = ['ID', 'From', 'To', 'Rate', 'Date', 'Source', 'Recorded']


def _list_rates() -> None:
    rates = list_exchange_rates(limit=500)
    print_table(_HEADERS, _rate_rows(rates), empty=t('currency.no_rates', "No exchange rates recorded."))


def _show_base() -> None:
    print('\n' + t('currency.base', "Base currency: {base}", base=base_currency()))
    print(t('currency.supported', "Supported currencies: {codes}", codes=', '.join(CURRENCIES)))


def _add_rate() -> None:
    from_currency = prompt_choice(t('currency.from', "From currency"), CURRENCIES, default=base_currency())
    to_currency = prompt_choice(t('currency.to', "To currency"), CURRENCIES)
    if not to_currency:
        fail(t('currency.to_required', "A target currency is required."))
        return
    rate = prompt_float(t('currency.rate', "Exchange rate (1 {a} = ? {b})", a=from_currency, b=to_currency),
                        allow_blank=False, minimum=0.000001)
    source = prompt_choice(t('currency.source', "Source"), RATE_SOURCES, default='manual')
    rate_date = prompt_date(t('currency.rate_date', "Rate date (blank = today)"), allow_blank=True)
    rate_id = add_exchange_rate(from_currency, to_currency, rate, source, rate_date)
    ok(t('currency.added', "Rate {rate_id} added: 1 {a} = {rate:.4f} {b}.",
         rate_id=rate_id, a=from_currency, rate=rate, b=to_currency))


def _edit_rate() -> None:
    rate_id = prompt_int(t('currency.rate_id', "Rate id"), allow_blank=False)
    current = get_exchange_rate(rate_id)
    if current is None:
        fail(t('currency.not_found', "Exchange rate {rate_id} not found.", rate_id=rate_id))
        return
    print(f"\n#{rate_id}: 1 {current['from_currency']} = {float(current['exchange_rate']):.4f} "
          f"{current['to_currency']} ({current['source']}, {current['rate_date']})")
    print(t('currency.blank_keeps', "Leave a field blank to keep its current value."))
    rate = prompt_float(t('currency.new_rate', "New rate"), minimum=0.000001)
    source = prompt_choice(t('currency.source', "Source"), RATE_SOURCES)
    rate_date = prompt_date(t('currency.rate_date', "Rate date"), allow_blank=True)
    if rate is None and source is None and rate_date is None:
        print(t('currency.nothing_changed', "Nothing changed."))
        return
    updated = update_exchange_rate(rate_id, rate=rate, source=source, rate_date=rate_date)
    ok(t('currency.updated', "Rate {rate_id} is now 1 {a} = {rate:.4f} {b} ({source}, {date}).",
         rate_id=rate_id, a=updated['from_currency'], rate=float(updated['exchange_rate']),
         b=updated['to_currency'], source=updated['source'], date=updated['rate_date']))


def _delete_rate() -> None:
    rate_id = prompt_int(t('currency.rate_id', "Rate id"), allow_blank=False)
    current = get_exchange_rate(rate_id)
    if current is None:
        fail(t('currency.not_found', "Exchange rate {rate_id} not found.", rate_id=rate_id))
        return
    print(f"\n#{rate_id}: 1 {current['from_currency']} = {float(current['exchange_rate']):.4f} "
          f"{current['to_currency']} ({current['rate_date']})")
    if not prompt_bool(t('currency.confirm_delete', "Delete this rate?")):
        return
    delete_exchange_rate(rate_id)
    ok(t('currency.deleted', "Rate {rate_id} deleted.", rate_id=rate_id))


def _refresh_rates() -> None:
    base = base_currency()
    if not prompt_bool(t('currency.confirm_refresh', "Refresh today's rates from {base}?", base=base),
                       default=True):
        return
    result = refresh_sample_rates(base)
    print_table(['From', 'To', 'Rate'], [[a, b, f"{rate:.4f}"] for a, b, rate in result['pairs']])
    ok(t('currency.refreshed', "{count} rate(s) refreshed from {base}.",
         count=result['updated'], base=result['base']))


def _convert() -> None:
    amount = prompt_float(t('currency.amount', "Amount"), allow_blank=False, minimum=0.01)
    from_currency = prompt_choice(t('currency.from', "From currency"), CURRENCIES, default=base_currency())
    to_currency = prompt_choice(t('currency.to', "To currency"), CURRENCIES)
    if not to_currency:
        fail(t('currency.to_required', "A target currency is required."))
        return
    converted, rate = convert_amount(amount, from_currency, to_currency)
    print(f"\n{amount:,.2f} {from_currency} = {converted:,.2f} {to_currency}")
    print(t('currency.rate_used', "Rate: 1 {a} = {rate:.4f} {b}", a=from_currency, rate=rate, b=to_currency))


def run_currency_menu(auth) -> None:
    """Run the Multi-Currency CLI loop."""
    if not require_permission(auth):
        return
    run_menu(t('currency.title', "MULTI-CURRENCY"), [
        (t('currency.menu.list', "List exchange rates"), _list_rates),
        (t('currency.menu.add', "Add an exchange rate"), _add_rate),
        (t('currency.menu.edit', "Edit an exchange rate"), _edit_rate),
        (t('currency.menu.delete', "Delete an exchange rate"), _delete_rate),
        (t('currency.menu.refresh', "Refresh today's rates"), _refresh_rates),
        (t('currency.menu.convert', "Convert an amount"), _convert),
        (t('currency.menu.base', "Show base currency"), _show_base),
    ], return_label=t('menu.return_finance', "Return to Finance Menu"))

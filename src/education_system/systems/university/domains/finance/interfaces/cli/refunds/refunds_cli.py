"""
Refunds — interactive CLI.

Wired to ``core.refunds`` (list / filter / approve / reject / status / export)
and the menu-driven ``core.account_management.process_refund`` (raise a refund
request), all of which read/write ``unified_refunds`` in the shared
``student_records.db`` — the same table the Refunds tab, the "View All
Refunds" window and the "Manage Refunds" dialog of the Finance GUI use.

Covers: list refunds by status and/or free-text search, view one, approve or
reject pending refunds, set any status (with optional student email), export
the current filter to CSV, totals by status, and raise a new refund request.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from education_system.systems.university.domains.finance.domain.core.refunds import (
    REFUND_STATUSES,
    export_refunds_csv,
    get_refund,
    list_refunds,
    refund_totals,
    refunds_table_exists,
    send_refund_email,
    set_refund_status,
)
from education_system.systems.university.domains.finance.interfaces.cli.common import (
    bind_legacy_auth,
    current_username,
    fail,
    money,
    ok,
    print_table,
    prompt,
    prompt_bool,
    prompt_choice,
    require_permission,
    run_menu,
    t,
)

logger = logging.getLogger(__name__)

_STATUS_FILTERS = ('all',) + REFUND_STATUSES
_HEADERS = ['ID', 'Reference', 'Source', 'Dept', 'Student', 'Amount', 'Method', 'Date',
            'Ref id', 'Status', 'By']


def _rows(refunds):
    return [[r['refund_id'], r['refund_reference'], r['source_type'], r['department'],
             r['student_id'], money(r['amount']), r['refund_method'], r['refund_date'],
             r['reference_id'], r['status'], r['processed_by']] for r in refunds]


def _ask_filter():
    status = prompt_choice(t('refunds.status_filter', "Status filter"), _STATUS_FILTERS, default='all')
    search = prompt(t('refunds.search', "Search (blank = none)"))
    return status, search or None


def _parse_ids(raw: str):
    ids = []
    for part in raw.replace(',', ' ').split():
        try:
            ids.append(int(part))
        except ValueError:
            raise ValueError(t('refunds.bad_id', "'{part}' is not a refund id.", part=part)) from None
    return ids


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #
def _list_refunds() -> None:
    if not refunds_table_exists():
        fail(t('refunds.no_table', "The unified_refunds table does not exist yet."))
        return
    status, search = _ask_filter()
    refunds = list_refunds(search=search, status=status)
    print_table(_HEADERS, _rows(refunds), empty=t('refunds.none', "No refunds match."))
    count, total = refund_totals(refunds)
    if count:
        print(t('refunds.totals', "{count} refund(s), {total} in total.", count=count, total=money(total)))


def _view_refund() -> None:
    raw = prompt(t('refunds.refund_id', "Refund id"))
    if not raw:
        fail(t('refunds.id_required', "A refund id is required."))
        return
    refund = get_refund(_parse_ids(raw)[0])
    if refund is None:
        fail(t('refunds.not_found', "Refund {refund_id} not found.", refund_id=raw))
        return
    print(f"\n--- {t('refunds.heading', 'Refund')} #{refund['refund_id']} ---")
    for key in ('refund_reference', 'source_type', 'department', 'student_id', 'amount', 'currency',
                'refund_type', 'refund_method', 'reason', 'status', 'requested_by', 'request_date',
                'approved_by', 'approval_date', 'processed_by', 'refund_date', 'reference_id',
                'notes'):
        value = refund.get(key)
        if key == 'amount':
            value = money(value)
        print(f"  {key:<18}: {value if value not in (None, '') else '-'}")


def _totals_by_status() -> None:
    refunds = list_refunds()
    if not refunds:
        print('\n' + t('refunds.none', "No refunds match."))
        return
    buckets = OrderedDict((status, []) for status in REFUND_STATUSES)
    for refund in refunds:
        buckets.setdefault(refund['status'] or 'pending', []).append(refund)
    rows = []
    for status, group in buckets.items():
        if group:
            count, total = refund_totals(group)
            rows.append([status, count, money(total)])
    count, total = refund_totals(refunds)
    rows.append(['TOTAL', count, money(total)])
    print_table(['Status', 'Count', 'Amount'], rows)


# --------------------------------------------------------------------------- #
# Status changes
# --------------------------------------------------------------------------- #
def _decide_pending(auth, new_status: str) -> None:
    pending = list_refunds(status='pending')
    print_table(_HEADERS, _rows(pending), empty=t('refunds.no_pending', "No pending refunds."))
    if not pending:
        return
    raw = prompt(t('refunds.ids_to_change', "Refund id(s) to {verb} (comma-separated)",
                   verb=t(f'refunds.verb_{new_status}', new_status.rstrip('d'))))
    if not raw:
        return
    ids = _parse_ids(raw)
    if not prompt_bool(t('refunds.confirm_change', "Mark {count} refund(s) as {status}?",
                         count=len(ids), status=new_status), default=True):
        return
    result = set_refund_status(ids, new_status, current_username(auth), only_pending=True)
    ok(t('refunds.changed', "{count} refund(s) marked {status}.",
         count=len(result['updated']), status=new_status))
    for refund_id, state in result['skipped']:
        print(t('refunds.skipped', "  Skipped {refund_id} (status: {state}).",
                refund_id=refund_id, state=state))


def _set_status(auth) -> None:
    raw = prompt(t('refunds.refund_id', "Refund id"))
    if not raw:
        fail(t('refunds.id_required', "A refund id is required."))
        return
    refund_id = _parse_ids(raw)[0]
    refund = get_refund(refund_id)
    if refund is None:
        fail(t('refunds.not_found', "Refund {refund_id} not found.", refund_id=refund_id))
        return
    print(f"\n#{refund_id} — {refund['student_id'] or '-'} — {money(refund['amount'])} "
          f"— {t('refunds.status', 'status')} {refund['status']}")
    new_status = prompt_choice(t('refunds.new_status', "New status"), REFUND_STATUSES)
    if not new_status:
        fail(t('refunds.status_required', "A status is required."))
        return
    if new_status == refund['status']:
        print(t('refunds.unchanged', "Refund is already {status}.", status=new_status))
        return
    notify = bool(refund.get('student_id')) and prompt_bool(
        t('refunds.notify', "Email the student about the change?"), default=False)
    set_refund_status(refund_id, new_status, current_username(auth))
    ok(t('refunds.status_set', "Refund {refund_id} is now {status}.", refund_id=refund_id, status=new_status))
    if notify:
        sent = send_refund_email(kind='status_update', student_id=refund['student_id'],
                                 refund_id=refund_id, amount=refund['amount'],
                                 refund_type=refund.get('refund_type') or '',
                                 refund_method=refund.get('refund_method') or '',
                                 status=new_status, reason=refund.get('reason') or '')
        print(t('refunds.email_sent', "Notification email sent.") if sent
              else t('refunds.email_not_sent', "Notification email was not sent."))


# --------------------------------------------------------------------------- #
# Export / create
# --------------------------------------------------------------------------- #
def _export_csv() -> None:
    status, search = _ask_filter()
    refunds = list_refunds(search=search, status=status)
    if not refunds:
        print('\n' + t('refunds.none', "No refunds match."))
        return
    default = f"refunds_export_{datetime.now().strftime('%Y%m%d')}.csv"
    path = Path(prompt(t('refunds.export_path', "Export file"), default)).expanduser()
    if path.exists() and not prompt_bool(t('refunds.overwrite', "{path} exists. Overwrite?", path=path)):
        return
    export_refunds_csv(refunds, path)
    ok(t('refunds.exported', "{count} refund(s) exported to {path}.", count=len(refunds), path=path))


def _raise_refund() -> None:
    from education_system.systems.university.domains.finance.domain.core import account_management
    account_management.process_refund()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_refunds_menu(auth) -> None:
    """Run the Refunds CLI loop."""
    if not require_permission(auth):
        return
    from education_system.systems.university.domains.finance.domain.core import account_management
    bind_legacy_auth(auth, account_management)

    run_menu(t('refunds.title', "REFUNDS"), [
        (t('refunds.menu.list', "List refunds (filter / search)"), _list_refunds),
        (t('refunds.menu.view', "View a refund"), _view_refund),
        (t('refunds.menu.approve', "Approve pending refund(s)"), lambda: _decide_pending(auth, 'approved')),
        (t('refunds.menu.reject', "Reject pending refund(s)"), lambda: _decide_pending(auth, 'rejected')),
        (t('refunds.menu.set_status', "Set a refund's status"), lambda: _set_status(auth)),
        (t('refunds.menu.totals', "Totals by status"), _totals_by_status),
        (t('refunds.menu.export', "Export refunds to CSV"), _export_csv),
        (t('refunds.menu.raise', "Raise a refund request"), _raise_refund),
    ], return_label=t('menu.return_finance', "Return to Finance Menu"))

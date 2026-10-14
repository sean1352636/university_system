"""
Collections Management — interactive CLI.

Wired to the collections domain (``revenue_analytics.collections``,
``collection_case_actions`` and ``agencies``), which read/write the shared
``student_records.db`` — the same database the Collections tab and the
Compliance window of the Finance GUI use. A case opened, noticed, assigned or
resolved here is what the GUI shows, and vice-versa.

Covers: cases (list, view, open, send notice, resolve, update status, assign
to an agency, progress report, overdue accounts), payment arrangements,
agencies (list, add, edit, deactivate/reactivate, remove, performance), automated
workflows (save, run, history), collection reports and the audit log.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics import (
    agencies as agency_domain,
)
from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collection_case_actions import (
    DEFAULT_NOTICE_SUBJECT,
    NOTICE_TYPES,
    SCHEDULE_KINDS,
    active_case_for_student,
    default_notice_message,
    describe_schedule,
    list_audit_entries,
    record_payment_arrangement,
    resolve_case,
    send_case_notice,
)
from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collections import (
    CASE_STATUSES,
    assign_case,
    format_collection_progress,
    get_case,
    list_active_agencies,
    list_cases,
    list_unassigned_cases,
    open_case,
    set_case_status,
    view_student_collection_detail,
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
    prompt_date,
    prompt_float,
    prompt_int,
    prompt_multiline,
    require_permission,
    run_menu,
    t,
)

logger = logging.getLogger(__name__)


def _student_label(row) -> str:
    name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
    return f"{row.get('student_id')} ({name})" if name else str(row.get('student_id'))


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #
def _list_cases() -> None:
    cases = list_cases(limit=500)
    print_table(
        ['Case', 'Student', 'Debt', 'Collected', 'Status', 'Agency', 'Assigned', 'Resolved'],
        [[c['case_id'], _student_label(c), money(c['total_debt']), money(c['amount_collected']),
          c['case_status'], c['agency_name'], (c['assigned_date'] or '')[:10],
          (c['resolution_date'] or '')[:10]] for c in cases],
        empty=t('collections.no_cases', "No collection cases yet."),
    )


def _view_case() -> None:
    case_id = prompt_int(t('collections.case_id', "Case id"), allow_blank=False)
    case = get_case(case_id)
    if case is None:
        fail(t('collections.case_not_found', "Collection case {case_id} not found.", case_id=case_id))
        return
    print(f"\n--- {t('collections.case_heading', 'Collection case')} #{case['case_id']} ---")
    print(f"  {'Student':<16}: {_student_label(case)}")
    print(f"  {'Email':<16}: {case.get('email_address') or '-'}")
    print(f"  {'Status':<16}: {case['case_status']}")
    print(f"  {'Total debt':<16}: {money(case['total_debt'])}")
    print(f"  {'Collected':<16}: {money(case['amount_collected'])}")
    print(f"  {'Agency':<16}: {case.get('agency_name') or '-'}")
    print(f"  {'Assigned':<16}: {case.get('assigned_date') or '-'}")
    print(f"  {'Resolved':<16}: {case.get('resolution_date') or '-'}")
    print(f"  {'Created':<16}: {case.get('created_at') or '-'}")
    print(f"  {'Updated':<16}: {case.get('updated_at') or '-'}")
    print(f"  {'Notes':<16}:")
    for line in (case.get('notes') or '-').splitlines():
        print(f"      {line}")


def _open_case(auth) -> None:
    student_id = prompt(t('collections.student_id', "Student id"))
    if not student_id:
        fail(t('collections.student_required', "Student id is required."))
        return
    total_debt = prompt_float(t('collections.total_debt', "Total debt (£)"), allow_blank=False)
    notes = prompt(t('collections.notes', "Notes"))
    case_id = open_case(student_id, total_debt, notes, created_by=current_username(auth))
    ok(t('collections.case_opened', "Case {case_id} opened for student {student_id} ({debt}).",
         case_id=case_id, student_id=student_id, debt=money(total_debt)))


def _send_notice(auth) -> None:
    case_id = prompt_int(t('collections.case_id', "Case id"), allow_blank=False)
    case = get_case(case_id)
    if case is None:
        fail(t('collections.case_not_found', "Collection case {case_id} not found.", case_id=case_id))
        return
    print(f"\n{_student_label(case)} — {money(case['total_debt'])} "
          f"— {case.get('email_address') or t('collections.no_email', 'no email on file')}")
    notice_type = prompt_choice(t('collections.notice_type', "Notice type"),
                                NOTICE_TYPES, default=NOTICE_TYPES[0])
    subject = prompt(t('collections.subject', "Subject"), DEFAULT_NOTICE_SUBJECT)
    message = default_notice_message(case['total_debt'])
    print('\n' + message + '\n')
    if not prompt_bool(t('collections.use_default_message', "Use this default message?"), default=True):
        message = prompt_multiline(t('collections.message', "Message"))
    if not prompt_bool(t('collections.confirm_send', "Send the notice now?"), default=True):
        print(t('collections.not_sent', "Notice not sent."))
        return
    result = send_case_notice(case_id, notice_type, subject, message, sent_by=current_username(auth))
    ok(t('collections.notice_sent', "{notice_type} sent to {email} for case {case_id}.",
         notice_type=notice_type.replace('_', ' ').title(), email=result['email'], case_id=case_id))


def _resolve_case(auth) -> None:
    case_id = prompt_int(t('collections.case_id', "Case id"), allow_blank=False)
    case = get_case(case_id)
    if case is None:
        fail(t('collections.case_not_found', "Collection case {case_id} not found.", case_id=case_id))
        return
    print(f"\n{_student_label(case)} — {t('collections.debt', 'debt')} {money(case['total_debt'])}"
          f" — {t('collections.status', 'status')} {case['case_status']}")
    amount = prompt_float(t('collections.amount_collected', "Amount collected (£)"),
                          allow_blank=False, minimum=0)
    notes = prompt(t('collections.resolution_notes', "Resolution notes"), 'Resolved')
    notify = prompt_bool(t('collections.email_resolution', "Email the student the outcome?"),
                         default=True)
    result = resolve_case(case_id, amount, notify=notify, notes=notes,
                          updated_by=current_username(auth))
    ok(t('collections.case_resolved', "Case {case_id} resolved; collected {collected}, remaining {remaining}.",
         case_id=case_id, collected=money(result['amount_collected']),
         remaining=money(max(result['remaining'], 0))))
    if notify:
        print(t('collections.email_sent', "Resolution email sent.") if result['emailed']
              else t('collections.email_not_sent', "Resolution email was not sent."))


def _update_status(auth) -> None:
    case_id = prompt_int(t('collections.case_id', "Case id"), allow_blank=False)
    case = get_case(case_id)
    if case is None:
        fail(t('collections.case_not_found', "Collection case {case_id} not found.", case_id=case_id))
        return
    print(f"\n{_student_label(case)} — {t('collections.status', 'status')} {case['case_status']}")
    new_status = prompt_choice(t('collections.new_status', "New status"), CASE_STATUSES)
    if not new_status:
        fail(t('collections.status_required', "A status is required."))
        return
    amount = None
    if new_status in ('resolved', 'closed'):
        amount = prompt_float(t('collections.amount_collected', "Amount collected (£)"),
                              allow_blank=False, minimum=0)
    else:
        amount = prompt_float(t('collections.amount_collected_optional',
                                "Amount collected so far (£, blank = unchanged)"), minimum=0)
    notes = prompt(t('collections.update_notes', "Update notes"))
    result = set_case_status(case_id, new_status, notes, amount, updated_by=current_username(auth))
    ok(t('collections.status_updated', "Case {case_id}: {old} → {new}.",
         case_id=case_id, old=result['old_status'], new=result['new_status']))


def _assign_case(auth) -> None:
    cases = list_unassigned_cases()
    if not cases:
        print('\n' + t('collections.no_unassigned', "No unassigned collection cases."))
        return
    print_table(['Case', 'Student', 'Debt', 'Status'],
                [[c['case_id'], _student_label(c), money(c['total_debt']), c['case_status']]
                 for c in cases])
    agencies = list_active_agencies()
    if not agencies:
        print('\n' + t('collections.no_active_agencies', "No active collection agencies to assign to."))
        return
    print_table(['Agency', 'Name', 'Commission', 'Minimum'],
                [[a['agency_id'], a['agency_name'], f"{float(a['commission_rate'] or 0):.1f}%",
                  money(a['minimum_amount'])] for a in agencies])
    case_id = prompt_int(t('collections.case_id', "Case id"), allow_blank=False)
    agency_id = prompt_int(t('collections.agency_id', "Agency id"), allow_blank=False)
    result = assign_case(case_id, agency_id, assigned_by=current_username(auth))
    ok(t('collections.case_assigned', "Case {case_id} assigned to {agency}.",
         case_id=result['case_id'], agency=result['agency_name']))


def _track_progress() -> None:
    print(format_collection_progress())


def _view_overdue_accounts() -> None:
    from education_system.systems.university.domains.finance.domain.core.analytics import (
        view_overdue_accounts,
    )
    view_overdue_accounts()


def _student_detail() -> None:
    student_id = prompt(t('collections.student_id', "Student id"))
    if not student_id:
        fail(t('collections.student_required', "Student id is required."))
        return
    view_student_collection_detail(student_id)


# --------------------------------------------------------------------------- #
# Payment arrangements
# --------------------------------------------------------------------------- #
def _create_arrangement(auth) -> None:
    student_id = prompt(t('collections.student_id', "Student id"))
    if not student_id:
        fail(t('collections.student_required', "Student id is required."))
        return
    case = active_case_for_student(student_id)
    if case is None:
        fail(t('collections.no_active_case', "No active collection case for student {student_id}.",
               student_id=student_id))
        return
    print(f"\n{t('collections.case_heading', 'Collection case')} #{case['case_id']} — "
          f"{money(case['total_debt'])} — {case['case_status']}")
    amount = prompt_float(t('collections.arrangement_amount', "Arrangement amount (£)"),
                          allow_blank=False, minimum=0.01)
    kind = prompt_choice(t('collections.schedule', "Payment schedule"), SCHEDULE_KINDS, default='single')
    today = datetime.now().strftime('%Y-%m-%d')
    if kind == 'single':
        schedule = describe_schedule(kind, amount, prompt_date(t('collections.payment_date', "Payment date"), today))
    elif kind in ('weekly', 'monthly'):
        periods = prompt_int(t('collections.number_of_payments', "Number of payments"),
                             allow_blank=False, minimum=1)
        schedule = describe_schedule(kind, amount,
                                     prompt_date(t('collections.start_date', "Start date"), today),
                                     periods=periods)
    else:
        schedule = describe_schedule(kind, amount, custom=prompt_multiline(
            t('collections.custom_schedule', "Custom schedule details")))
    terms = prompt(t('collections.terms', "Agreement terms"))
    notify = prompt_bool(t('collections.email_confirmation', "Email the student a confirmation?"),
                         default=True)
    result = record_payment_arrangement(student_id, amount, schedule, terms,
                                        arranged_by=current_username(auth), notify=notify)
    ok(t('collections.arrangement_recorded', "Arrangement recorded on case {case_id}: {schedule}",
         case_id=result['case_id'], schedule=result['schedule_info']))


def _arrangements_menu(auth) -> None:
    run_menu(t('collections.arrangements_title', "PAYMENT ARRANGEMENTS"), [
        (t('collections.menu.create_arrangement', "Create a payment arrangement"),
         lambda: _create_arrangement(auth)),
        (t('collections.menu.student_detail', "View a student's collection detail"), _student_detail),
        (t('collections.menu.track_progress', "Track collection progress"), _track_progress),
    ])


# --------------------------------------------------------------------------- #
# Agencies
# --------------------------------------------------------------------------- #
def _list_agencies() -> None:
    agencies = agency_domain.list_agencies(include_inactive=True)
    print_table(
        ['ID', 'Name', 'Email', 'Phone', 'Commission', 'Minimum', 'Active', 'Open cases'],
        [[a['agency_id'], a['agency_name'], a['contact_email'], a['contact_phone'],
          f"{float(a['commission_rate'] or 0):.1f}%", money(a['minimum_amount']),
          'yes' if a['is_active'] else 'no', agency_domain.count_open_cases(a['agency_id'])]
         for a in agencies],
        empty=t('collections.no_agencies', "No collection agencies yet."),
    )


def _add_agency() -> None:
    name = prompt(t('collections.agency_name', "Agency name"))
    if not name:
        fail(t('collections.agency_name_required', "Agency name is required."))
        return
    email = prompt(t('collections.contact_email', "Contact email"))
    phone = prompt(t('collections.contact_phone', "Contact phone"))
    commission = prompt_float(t('collections.commission', "Commission rate (%)"), default=0.0, minimum=0)
    minimum = prompt_float(t('collections.minimum_amount', "Minimum debt amount (£)"),
                           default=0.0, minimum=0)
    agency_id = agency_domain.create_agency(name, email, phone, commission, minimum)
    ok(t('collections.agency_added', "Agency {agency_id} '{name}' added.", agency_id=agency_id, name=name))


def _edit_agency() -> None:
    agency_id = prompt_int(t('collections.agency_id', "Agency id"), allow_blank=False)
    agency = agency_domain.get_agency(agency_id)
    if agency is None:
        fail(t('collections.agency_not_found', "Collection agency {agency_id} not found.", agency_id=agency_id))
        return
    print('\n' + t('collections.blank_keeps', "Leave a field blank to keep its current value."))
    name = prompt(t('collections.agency_name', "Agency name"), agency['agency_name'])
    email = prompt(t('collections.contact_email', "Contact email"), agency['contact_email'] or '')
    phone = prompt(t('collections.contact_phone', "Contact phone"), agency['contact_phone'] or '')
    commission = prompt_float(t('collections.commission', "Commission rate (%)"),
                              default=float(agency['commission_rate'] or 0), minimum=0)
    minimum = prompt_float(t('collections.minimum_amount', "Minimum debt amount (£)"),
                           default=float(agency['minimum_amount'] or 0), minimum=0)
    agency_domain.update_agency(agency_id, agency_name=name, contact_email=email,
                                contact_phone=phone, commission_rate=commission,
                                minimum_amount=minimum)
    ok(t('collections.agency_updated', "Agency {agency_id} updated.", agency_id=agency_id))


def _toggle_agency() -> None:
    agency_id = prompt_int(t('collections.agency_id', "Agency id"), allow_blank=False)
    agency = agency_domain.get_agency(agency_id)
    if agency is None:
        fail(t('collections.agency_not_found', "Collection agency {agency_id} not found.", agency_id=agency_id))
        return
    activate = not agency['is_active']
    open_cases = agency_domain.count_open_cases(agency_id)
    if not activate and open_cases:
        print(t('collections.agency_has_cases',
                "Warning: '{name}' has {count} open case(s) that will need reassigning.",
                name=agency['agency_name'], count=open_cases))
    verb = t('collections.reactivate', "Reactivate") if activate else t('collections.deactivate', "Deactivate")
    if not prompt_bool(f"{verb} '{agency['agency_name']}'?"):
        return
    agency_domain.set_agency_active(agency_id, activate)
    ok(t('collections.agency_toggled', "Agency '{name}' is now {state}.",
         name=agency['agency_name'],
         state=t('collections.active', 'active') if activate else t('collections.inactive', 'inactive')))


def _remove_agency() -> None:
    agency_id = prompt_int(t('collections.agency_id', "Agency id"), allow_blank=False)
    agency = agency_domain.get_agency(agency_id)
    if agency is None:
        fail(t('collections.agency_not_found', "Collection agency {agency_id} not found.", agency_id=agency_id))
        return
    if not prompt_bool(t('collections.confirm_remove', "Permanently remove '{name}'?",
                         name=agency['agency_name'])):
        return
    agency_domain.delete_agency(agency_id)
    ok(t('collections.agency_removed', "Agency '{name}' removed.", name=agency['agency_name']))


def _agency_performance() -> None:
    from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collection_reports import (
        agency_performance_report,
    )
    agency_performance_report()


def _agencies_menu() -> None:
    run_menu(t('collections.agencies_title', "COLLECTION AGENCIES"), [
        (t('collections.menu.list_agencies', "List agencies"), _list_agencies),
        (t('collections.menu.add_agency', "Add an agency"), _add_agency),
        (t('collections.menu.edit_agency', "Edit an agency"), _edit_agency),
        (t('collections.menu.toggle_agency', "Deactivate / reactivate an agency"), _toggle_agency),
        (t('collections.menu.remove_agency', "Remove an agency (no case history)"), _remove_agency),
        (t('collections.menu.agency_performance', "Agency performance report"), _agency_performance),
    ])


# --------------------------------------------------------------------------- #
# Workflows
# --------------------------------------------------------------------------- #
def _list_workflows() -> None:
    workflows = agency_domain.list_workflows()
    print_table(
        ['ID', 'Name', 'Min debt', 'Remind (d)', 'Escalate (d)', 'Auto-assign', 'Active', 'Last run'],
        [[w['workflow_id'], w['workflow_name'], money(w['minimum_debt']), w['reminder_days'],
          w['escalation_days'], 'yes' if w['auto_assign'] else 'no',
          'yes' if w['is_active'] else 'no', (w['last_run_at'] or '')[:16]] for w in workflows],
        empty=t('collections.no_workflows', "No collection workflows saved yet."),
    )


def _print_run_result(result) -> None:
    ok(t('collections.workflow_ran',
         "Workflow run: created {created}, assigned {assigned}, reminded {reminded}, escalated {escalated}.",
         **result))


def _create_workflow() -> None:
    name = prompt(t('collections.workflow_name', "Workflow name"), "Default overdue workflow")
    minimum_debt = prompt_float(t('collections.minimum_debt', "Minimum overdue debt (£)"),
                                default=100.0, minimum=0)
    reminder_days = prompt_int(t('collections.reminder_days', "Reminder interval (days)"),
                               allow_blank=False, minimum=1)
    escalation_days = prompt_int(t('collections.escalation_days', "Escalate after (days)"),
                                 allow_blank=False, minimum=1)
    auto_assign = prompt_bool(t('collections.auto_assign', "Automatically assign an eligible agency?"))
    workflow_id = agency_domain.save_collection_workflow(
        name, minimum_debt, reminder_days, escalation_days, auto_assign)
    ok(t('collections.workflow_saved', "Workflow saved (ID {workflow_id}).", workflow_id=workflow_id))
    if prompt_bool(t('collections.run_now', "Run it now?")):
        _print_run_result(agency_domain.run_collection_workflow(workflow_id))


def _run_workflow() -> None:
    workflow_id = prompt_int(t('collections.workflow_id', "Workflow id"), allow_blank=False)
    if not prompt_bool(t('collections.confirm_run', "Run workflow {workflow_id} now?",
                         workflow_id=workflow_id), default=True):
        return
    _print_run_result(agency_domain.run_collection_workflow(workflow_id))


def _workflow_history() -> None:
    workflow_id = prompt_int(t('collections.workflow_id', "Workflow id"), allow_blank=False)
    actions = agency_domain.list_workflow_actions(workflow_id, limit=100)
    print_table(['Action', 'Case', 'Type', 'Status', 'Details', 'When'],
                [[a['action_id'], a['case_id'], a['action_type'], a['status'], a['details'],
                  (a['created_at'] or '')[:16]] for a in actions],
                empty=t('collections.no_actions', "This workflow has not recorded any actions."))


def _workflows_menu() -> None:
    run_menu(t('collections.workflows_title', "AUTOMATED COLLECTION WORKFLOWS"), [
        (t('collections.menu.list_workflows', "List workflows"), _list_workflows),
        (t('collections.menu.create_workflow', "Create a workflow"), _create_workflow),
        (t('collections.menu.run_workflow', "Run a workflow"), _run_workflow),
        (t('collections.menu.workflow_history', "Workflow action history"), _workflow_history),
    ])


# --------------------------------------------------------------------------- #
# Reports and audit
# --------------------------------------------------------------------------- #
def _collection_reports() -> None:
    from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collection_reports import (
        generate_collection_reports,
    )
    generate_collection_reports()


def _audit_logs() -> None:
    today = datetime.now()
    start = prompt_date(t('collections.start_date', "Start date"),
                        (today - timedelta(days=30)).strftime('%Y-%m-%d'))
    end = prompt_date(t('collections.end_date', "End date"), today.strftime('%Y-%m-%d'))
    only_collections = prompt_bool(t('collections.only_collections', "Only collection-case entries?"),
                                   default=True)
    entries = list_audit_entries(start, end, 'collection_cases' if only_collections else None)
    print_table(['When', 'User', 'Action', 'Table', 'Record', 'Details'],
                [[(e['timestamp'] or '')[:19], e['user_id'], e['action'], e['table_name'],
                  e['record_id'], e['new_values']] for e in entries],
                max_width=50,
                empty=t('collections.no_audit', "No audit entries in that range."))


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_collections_menu(auth) -> None:
    """Run the Collections Management CLI loop."""
    if not require_permission(auth):
        return
    from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics import (
        app as _legacy_app,
        collections as _legacy_collections,
    )
    bind_legacy_auth(auth, _legacy_app, _legacy_collections)

    run_menu(t('collections.title', "COLLECTIONS MANAGEMENT"), [
        (t('collections.menu.list_cases', "List collection cases"), _list_cases),
        (t('collections.menu.view_case', "View a case"), _view_case),
        (t('collections.menu.overdue', "View overdue accounts"), _view_overdue_accounts),
        (t('collections.menu.open_case', "Create a collection case"), lambda: _open_case(auth)),
        (t('collections.menu.send_notice', "Send a collection notice"), lambda: _send_notice(auth)),
        (t('collections.menu.resolve', "Resolve a case"), lambda: _resolve_case(auth)),
        (t('collections.menu.update_status', "Update a case status"), lambda: _update_status(auth)),
        (t('collections.menu.assign', "Assign a case to an agency"), lambda: _assign_case(auth)),
        (t('collections.menu.track_progress', "Track collection progress"), _track_progress),
        (t('collections.menu.arrangements', "Payment arrangements"), lambda: _arrangements_menu(auth)),
        (t('collections.menu.agencies', "Manage collection agencies"), _agencies_menu),
        (t('collections.menu.workflows', "Automated collection workflows"), _workflows_menu),
        (t('collections.menu.reports', "Collection reports"), _collection_reports),
        (t('collections.menu.audit', "View audit logs"), _audit_logs),
    ], return_label=t('menu.return_finance', "Return to Finance Menu"))

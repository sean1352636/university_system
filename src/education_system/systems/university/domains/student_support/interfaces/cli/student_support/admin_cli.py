"""Student Support CLI for team leads and administrators.

Teams (members, capacity, auto-assign, leads) and the duty rota, and data
protection: the retention policy, subject access exports to a file and
erasure requests under dual control (the deciding administrator re-enters
their password). The domain decides who may do each of these.
"""

from __future__ import annotations

import datetime
import getpass
import json
from pathlib import Path

from education_system.systems.university.domains.student_support.domain.student_support import (
    confidentiality as _tiers,
    gdpr,
    routing,
)
from education_system.systems.university.domains.student_support.interfaces.cli.student_support.common import (
    _t,
    actor,
    ask,
    ask_choice,
    ask_yes,
    call,
    failed,
    heading,
    page_through,
    pause,
    team_text,
    user,
)


# ── teams and the duty rota ──────────────────────────────────────────────


def _pick_team(duty: bool = False):
    teams = routing.teams() + ([{'key': routing.DUTY_TEAM, 'label': 'Duty officers'}] if duty else [])
    team = ask_choice(_t('team', "Team"), teams, label=lambda t: t['label'])
    return team['key'] if team else None


def _members(team) -> None:
    rows = call(lambda: {r['username']: r for r in _capacity_rows(team)})
    names = call(routing.team_members, team)
    if failed(names) or failed(rows):
        return
    leads = routing.team_leads(team) if names else set()
    heading(_t('members_of', "Members of {team}", team=team_text(team)))
    if not names:
        print(_t('no_members', "Nobody yet."))
    for name in sorted(names):
        r = rows.get(name) or {}
        cap = f"{r.get('open', '-')}/{r.get('max', '-')}" if r else '-'
        auto = (_t('auto_on', 'auto') if r.get('auto_assign') else _t('auto_off', 'manual')) if r else ''
        print(f"  {name:<18} {cap:<8} {auto:<7}{_t('lead', ' lead') if name in leads else ''}")


def _capacity_rows(team) -> list:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        caseload,
    )
    try:
        return caseload.capacity(actor(), team)
    except PermissionError:
        return []


def _set_member(team) -> None:
    username = ask(_t('member', "Username: "))
    cap = ask(_t('max_open_keep', "Most open tickets at once (Enter to keep / default 10): "))
    auto = ask(_t('auto_assign', "Give them new tickets automatically? (y/n, Enter to keep): ")).lower()
    lead = ask(_t('is_lead', "Team lead? (y/n, Enter to keep): ")).lower()
    result = call(routing.set_member, actor(), team, username,
                  max_concurrent=cap or None,
                  auto_assign=None if not auto else auto.startswith('y'),
                  lead=None if not lead else lead.startswith('y'))
    if not failed(result):
        print(_t('member_saved', "✅ {user} in {team}: up to {max}, {auto}{lead}.",
                 user=result['username'], team=team_text(result['team']), max=result['max'],
                 auto='auto-assign' if result['auto_assign'] else 'manual',
                 lead=', lead' if result['lead'] else ''))


def _remove_member(team) -> None:
    username = ask(_t('member', "Username: "))
    if not username or not ask_yes(_t('remove_confirm', "Take {user} out of {team}",
                                      user=username, team=team_text(team))):
        return
    removed = call(routing.remove_member, actor(), team, username)
    if not failed(removed):
        print(_t('removed', "✅ Removed.") if removed else _t('not_member', "They were not a member."))


def teams_menu() -> None:
    """M: team membership, capacity and the duty rota."""
    while True:
        heading(_t('teams_heading', "👥 TEAMS & DUTY ROTA"))
        print("  1. " + _t('m_list', "Teams and their members"))
        print("  2. " + _t('m_set', "Add a member / change capacity, auto-assign or lead"))
        print("  3. " + _t('m_remove', "Remove a member"))
        print("  4. " + _t('m_duty', "Duty rota (duty officers)"))
        print("  5. " + _t('m_duty_add', "Add a duty officer"))
        print("  6. " + _t('m_duty_remove', "Remove a duty officer"))
        print("  0. " + _t('back', "Back"))
        choice = ask(_t('choice', "Choice: "))
        if choice in ('0', ''):
            return
        if choice == '1':
            for t in routing.teams():
                _members(t['key'])
            pause()
        elif choice in ('2', '3'):
            team = _pick_team(duty=True)
            if team:
                (_set_member if choice == '2' else _remove_member)(team)
        elif choice == '4':
            _members(routing.DUTY_TEAM)
            pause()
        elif choice == '5':
            _set_member(routing.DUTY_TEAM)
        elif choice == '6':
            _remove_member(routing.DUTY_TEAM)
        else:
            print(_t('invalid_choice', "Invalid choice."))


# ── data protection ──────────────────────────────────────────────────────


def _retention() -> None:
    policy = call(gdpr.retention_policy)
    if failed(policy):
        return
    heading(_t('retention_heading', "Retention policy"))
    for tier in _tiers.TIERS:
        years = policy.get(tier)
        text = _t('years', "{n} years after closing", n=years) if years else \
            _t('never', "kept (never removed automatically)")
        print(f"  {_tiers.TIER_LABELS[tier]:<14} {text}")


def _set_retention() -> None:
    _retention()
    standard = ask(_t('std_years', "Standard tickets: keep for how many years? "))
    restricted = ask(_t('res_years', "Restricted tickets: keep for how many years? "))
    if not (standard.isdigit() and restricted.isdigit()):
        print("❌ " + _t('years_number', "Give the years as whole numbers"))
        return
    result = call(gdpr.set_retention, actor(), standard_years=int(standard),
                  restricted_years=int(restricted))
    if not failed(result):
        print(_t('retention_saved', "✅ Retention policy saved."))


def _purge_preview() -> None:
    result = call(gdpr.purge, actor(), dry_run=True)
    if not failed(result):
        due = result.get('due') or []
        print(_t('purge_due', "{n} ticket(s) are past their retention period{ids}.", n=len(due),
                 ids=(": " + ", ".join(f"#{t}" for t in due[:30])) if due else ''))
        print(_t('purge_note', "They are removed by the nightly retention job."))


def _subject_access() -> None:
    student = ask(_t('sar_who', "Student number or username: "))
    if not student:
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    default = f"support_sar_{student}_{stamp}.json"
    path = Path(ask(_t('save_as', "Save as [{name}]: ", name=default), default)).expanduser()
    section = call(gdpr.subject_access_export, actor(), student)
    if failed(section):
        return
    # The file is written once the disclosure has been recorded.
    if failed(call(path.write_text, json.dumps(section, indent=2, default=str), encoding='utf-8')):
        return
    print(_t('sar_done', "✅ {n} ticket(s) written to {path}.", n=len(section['records']), path=path))
    if section.get('for_review'):
        print(_t('sar_review', "⚠ Review before release: {items}",
                 items=", ".join(str(i) for i in section['for_review'][:20])))
    if section.get('withheld'):
        print(_t('sar_withheld', "Withheld: {items}", items=section['withheld']))


def _erasure_list() -> None:
    rows = call(gdpr.erasure_requests, actor())
    if failed(rows):
        return
    page_through(rows, lambda r: (
        f"  #{r['request_id']:<4} {r['status']:<10} {r.get('student_id') or r.get('requester_username') or '':<12} "
        f"case {r.get('case_reference')} — by {r.get('requested_by')}"
        f"{' / decided by ' + r['decided_by'] if r.get('decided_by') else ''}"
        f" — erase {len((r.get('tickets') or {}).get('erase') or [])}, "
        f"keep {len((r.get('tickets') or {}).get('keep') or [])}"),
        title=_t('erasure_requests', "Erasure requests"))


def _erasure_request() -> None:
    student = ask(_t('erase_who', "Student number or username: "))
    reason = ask(_t('erase_reason', "Reason (a sentence): "))
    case = ask(_t('erase_case', "Case reference (optional): ")) or None
    rid = call(gdpr.erase_student, actor(), student, reason, case_reference=case)
    if not failed(rid):
        print(_t('erase_requested', "✅ Request #{id} recorded; another administrator must "
                 "approve it.", id=rid))


def _verify_password(password: str) -> bool:
    from education_system.systems.university.services.student_provisioning import (
        verify_staff_password,
    )
    return verify_staff_password(user().get('username'), password)


def _erasure_decide() -> None:
    rid = ask(_t('request_no', "Request number: "))
    if not rid.isdigit():
        return
    approve = ask(_t('approve_reject', "a approve / r reject: ")).lower()
    if approve not in ('a', 'r'):
        return
    note = ask(_t('note_opt', "Note (optional): "))
    try:
        password = getpass.getpass(_t('reenter', "Re-enter your password: "))
    except EOFError:
        password = ''
    ok = bool(call(_verify_password, password) is True)
    result = call(gdpr.decide_erasure, actor(), int(rid), approve == 'a', reauthenticated=ok,
                  note=note)
    if not failed(result):
        print(_t('decided', "✅ Request #{id} {status}.", id=rid, status=result))


def _erasure_execute() -> None:
    rid = ask(_t('request_no', "Request number: "))
    if not rid.isdigit():
        return
    if ask(_t('erase_confirm', "This permanently removes personal data. Type ERASE to "
              "continue: ")) != 'ERASE':
        print(_t('cancelled', "Cancelled."))
        return
    result = call(gdpr.execute_erasure, actor(), int(rid))
    if not failed(result):
        print(_t('erased', "✅ Erased {e} ticket(s); kept {k} (safeguarding or legal hold); "
                 "{f} file(s) deleted.", e=len(result['erased']), k=len(result['kept']),
                 f=result['files_deleted']))


def _delete_ticket() -> None:
    tid = ask(_t('delete_no', "Ticket number to delete: "))
    if not tid.isdigit():
        return
    reason = ask_choice(_t('delete_reason', "Reason"), list(gdpr.DELETE_REASONS))
    if not reason:
        return
    detail = ask(_t('delete_detail', "Why is it being deleted? ")) if reason == 'other' else ""
    print(_t('delete_warning', "Ticket #{id} and its replies and attachments will be removed for "
             "good. To keep the record, close the ticket instead.", id=tid))
    confirm = ask(_t('delete_confirm', "Type the ticket number again to confirm: "))
    result = call(gdpr.delete_ticket, actor(), int(tid), reason, confirm_ticket_id=confirm,
                  detail=detail)
    if not failed(result):
        print(_t('deleted', "✅ Ticket #{id} deleted ({f} attachment file(s) removed).",
                 id=result['ticket_id'], f=result['files_removed']))


def data_protection_menu() -> None:
    """D: administrators only (the domain checks)."""
    actions = (
        ('1', _t('d_retention', "Retention policy"), _retention),
        ('2', _t('d_set_retention', "Change the retention periods"), _set_retention),
        ('3', _t('d_purge', "Tickets due for removal (preview)"), _purge_preview),
        ('4', _t('d_sar', "Subject access export (to a file)"), _subject_access),
        ('5', _t('d_erasures', "Erasure requests"), _erasure_list),
        ('6', _t('d_erase', "Request erasure of a person's support records"), _erasure_request),
        ('7', _t('d_decide', "Approve or reject an erasure request"), _erasure_decide),
        ('8', _t('d_execute', "Carry out an approved erasure"), _erasure_execute),
        ('9', _t('d_delete', "Delete a ticket permanently (error, duplicate, spam, test)"), _delete_ticket),
    )
    while True:
        heading(_t('dp_heading', "🛡  DATA PROTECTION"))
        for key, label, _fn in actions:
            print(f"  {key}. {label}")
        print("  0. " + _t('back', "Back"))
        choice = ask(_t('choice', "Choice: "))
        if choice in ('0', ''):
            return
        match = next((fn for key, _label, fn in actions if key == choice), None)
        if match:
            match()
        else:
            print(_t('invalid_choice', "Invalid choice."))


__all__ = ['teams_menu', 'data_protection_menu']

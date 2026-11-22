"""Student Support CLI for the staff who work tickets.

Caseload and team queue, working one ticket (status, assignment, escalation,
merge, confidentiality tier, break-glass, "Refer to…", history), the student
360, the service report, bulk changes and exports. Every action calls the
support domain, which decides who may do it; a refusal is printed and the
menu carries on.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
from pathlib import Path
from typing import Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    caseload,
    collaboration,
    confidentiality as _tiers,
    history360,
    referrals,
    routing,
    schema,
    service,
)
from education_system.systems.university.domains.student_support.domain.student_support.config import (
    SUPPORT_CATEGORIES,
    TICKET_PRIORITIES,
)
from education_system.systems.university.domains.student_support.interfaces.cli.student_support.common import (
    _t,
    actor,
    ask,
    ask_choice,
    ask_text,
    ask_ticket_id,
    ask_yes,
    call,
    failed,
    heading,
    numbers,
    page_through,
    pause,
    show_crisis,
    status_text,
    team_text,
    tier_badge,
)
from education_system.systems.university.domains.student_support.interfaces.cli.student_support.tickets_cli import (
    all_tickets,
    reply,
    view_ticket,
)


# ── caseload ─────────────────────────────────────────────────────────────


def _case_row(c: dict) -> str:
    if c.get('breached'):
        due = _t('breached', "BREACHED")
    elif c.get('hours_left') is not None:
        due = _t('hours_left', "{h}h left", h=c['hours_left'])
    else:
        due = '-'
    return (f"  #{c['ticket_id']:<6} {due:<11} {c.get('status_label') or '':<19} "
            f"{str(c.get('priority') or ''):<8} {c.get('team_label') or '':<22} "
            f"{tier_badge(c.get('confidentiality'))} {str(c.get('subject') or '')[:44]}")


def _ask_team(prompt: str, allow_none: bool = True) -> Optional[str]:
    teams = routing.teams() + [{'key': routing.DUTY_TEAM, 'label': 'Duty officers'}]
    team = ask_choice(prompt + (_t('enter_all', " (Enter for all)") if allow_none else ''),
                      teams, label=lambda t: t['label'], allow_none=allow_none)
    return team['key'] if team else None


def caseload_menu() -> None:
    """C: my caseload, team queue, take, reassign, capacity."""
    while True:
        heading(_t('caseload_heading', "📋 CASELOAD & QUEUE"))
        print("  1. " + _t('c_mine', "My caseload (most urgent first)"))
        print("  2. " + _t('c_queue', "Team queue (unassigned)"))
        print("  3. " + _t('c_take', "Take a ticket from the queue"))
        print("  4. " + _t('c_reassign', "Reassign a ticket (with a reason)"))
        print("  5. " + _t('c_capacity', "Team capacity"))
        print("  6. " + _t('c_set_capacity', "Set an adviser's capacity"))
        print("  0. " + _t('back', "Back"))
        choice = ask(_t('choice', "Choice: "))
        if choice in ('0', ''):
            return
        action = {'1': _my_caseload, '2': _team_queue, '3': _take, '4': _reassign,
                  '5': _capacity, '6': _set_capacity}.get(choice)
        if action:
            action()
        else:
            print(_t('invalid_choice', "Invalid choice."))


def _my_caseload() -> None:
    rows = call(caseload.my_caseload, actor())
    if not failed(rows):
        page_through(rows, _case_row, title=_t('my_caseload', "My caseload"),
                     pick=work_ticket, key=lambda c: c['ticket_id'])


def _team_queue() -> None:
    team = _ask_team(_t('which_team', "Team"))
    rows = call(caseload.team_queue, actor(), team)
    if not failed(rows):
        page_through(rows, _case_row, title=_t('team_queue', "Team queue"),
                     pick=lambda c: _take(c['ticket_id']), key=lambda c: c['ticket_id'])


def _take(ticket_id: Optional[int] = None) -> None:
    if ticket_id is None:
        ticket_id = ask_ticket_id(_t('take_which', "Ticket to take: "))
        if ticket_id is None:
            return
    result = call(caseload.take, actor(), ticket_id)
    if not failed(result):
        print(_t('taken', "✅ Ticket #{id} is now yours ({status}).", id=ticket_id,
                 status=status_text(result['status'])))


def _reassign(ticket_id: Optional[int] = None) -> None:
    if ticket_id is None:
        ticket_id = ask_ticket_id()
        if ticket_id is None:
            return
    to = ask(_t('reassign_to', "Hand over to (username): "))
    reason = ask(_t('reassign_reason', "Reason for the handover: "))
    force = ask_yes(_t('reassign_force', "Override team membership / capacity (leads and admins)"))
    result = call(caseload.reassign, actor(), ticket_id, to, reason, force=force)
    if not failed(result):
        print(_t('reassigned', "✅ Ticket #{id} handed from {old} to {new}.", id=ticket_id,
                 old=result['old'] or '-', new=result['new']))


def _capacity() -> None:
    team = _ask_team(_t('which_team', "Team"))
    rows = call(caseload.capacity, actor(), team)
    if failed(rows):
        return
    page_through(rows, lambda r: (
        f"  {r['username']:<16} {r['team_label']:<24} {r['open']:>3}/{r['max']:<3} "
        f"{_t('auto_on', 'auto') if r['auto_assign'] else _t('auto_off', 'manual'):<7}"
        f"{_t('lead', ' lead') if r['lead'] else ''}"), title=_t('capacity', "Capacity"))


def _set_capacity() -> None:
    team = _ask_team(_t('which_team', "Team"), allow_none=False)
    if not team:
        return
    username = ask(_t('adviser', "Adviser (username): "))
    cap = ask(_t('max_open', "Most open tickets at once: "))
    auto = ask(_t('auto_assign', "Give them new tickets automatically? (y/n, Enter to keep): ")).lower()
    result = call(caseload.set_capacity, actor(), username, cap, team,
                  auto_assign=None if not auto else auto.startswith('y'))
    if not failed(result):
        print(_t('capacity_saved', "✅ {user} in {team}: up to {max} tickets.",
                 user=result['username'], team=team_text(result['team']), max=result['max']))


# ── working one ticket ───────────────────────────────────────────────────


def work_menu() -> None:
    """W: pick a ticket (by number or from the list), then work it."""
    print("  1. " + _t('w_number', "Enter a ticket number"))
    print("  2. " + _t('w_list', "Choose from the ticket list"))
    choice = ask(_t('choice', "Choice [1]: "), '1')
    if choice == '2':
        all_tickets(open_ticket=work_ticket)
        return
    tid = ask_ticket_id()
    if tid is not None:
        work_ticket(tid)


def work_ticket(ticket_id) -> None:
    if isinstance(ticket_id, dict):
        ticket_id = ticket_id['ticket_id']
    actions = (
        ('1', _t('a_view', "View"), lambda: view_ticket(ticket_id)),
        ('2', _t('a_reply', "Reply to the student"), lambda: reply(ticket_id, internal=False)),
        ('3', _t('a_note', "Internal note"), lambda: reply(ticket_id, internal=True)),
        ('4', _t('a_status', "Set status"), lambda: _set_status(ticket_id)),
        ('5', _t('a_assign', "Assign / unassign"), lambda: _assign(ticket_id)),
        ('6', _t('a_reassign', "Reassign with a reason"), lambda: _reassign(ticket_id)),
        ('7', _t('a_escalate', "Escalate"), lambda: _escalate(ticket_id)),
        ('8', _t('a_merge', "Merge duplicates into this ticket"), lambda: _merge(ticket_id)),
        ('9', _t('a_tier', "Set confidentiality tier"), lambda: _set_tier(ticket_id)),
        ('10', _t('a_break_glass', "Break-glass access (emergency)"), lambda: _break_glass(ticket_id)),
        ('11', _t('a_refer', "Refer to…"), lambda: refer_menu(ticket_id)),
        ('12', _t('a_history', "History"), lambda: _history(ticket_id)),
        ('13', _t('a_360', "Student 360 for the requester"), lambda: _ticket_360(ticket_id)),
        ('14', _t('a_edit', "Edit title / description"), lambda: _edit(ticket_id)),
        ('15', _t('a_move_team', "Move to another team"), lambda: _move_team(ticket_id)),
        ('16', _t('a_link', "Link to another ticket"), lambda: _link(ticket_id)),
        ('17', _t('a_links', "Linked tickets (view / unlink)"),
         lambda: _collab_menus().unlink_menu(actor(), ticket_id)),
        ('18', _t('a_time', "Log time"), lambda: _log_time(ticket_id)),
        ('19', _t('a_time_list', "Time logged (view / remove)"),
         lambda: _collab_menus().time_menu(actor(), ticket_id)),
        ('20', _t('a_followers', "Followers"),
         lambda: _collab_menus().followers_menu(actor(), ticket_id)),
        ('21', _t('a_incident', "Add to a major incident"),
         lambda: _collab_menus().incident_for_ticket(actor(), ticket_id)),
    )
    while True:
        heading(_t('work_heading', "🛠  TICKET #{id}", id=ticket_id))
        for key, label, _fn in actions:
            print(f"  {key:>2}. {label}")
        print("   0. " + _t('back', "Back"))
        choice = ask(_t('choice', "Choice: "))
        if choice in ('0', ''):
            return
        match = next((fn for key, _label, fn in actions if key == choice), None)
        if match:
            match()
        else:
            print(_t('invalid_choice', "Invalid choice."))


def _collab_menus():
    from education_system.systems.university.domains.student_support.domain.helpdesk import (
        collab_menus,
    )
    return collab_menus


def _link(ticket_id) -> None:
    other = ask(_t('link_other', "Link to ticket number: ")).lstrip('#')
    if not other:
        return
    kinds = list(collaboration.LINK_LABELS)
    for i, kind in enumerate(kinds, 1):
        print(f"  {i}. {collaboration.LINK_LABELS[kind]}")
    choice = ask(_t('link_kind', "Kind of link [1]: ")) or '1'
    kind = kinds[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= len(kinds) else None
    if kind is None:
        print(_t('invalid_choice', "Invalid choice."))
        return
    if not failed(call(collaboration.link_tickets, actor(), ticket_id, other, kind)):
        print(_t('linked', "✅ Linked."))


def _log_time(ticket_id) -> None:
    minutes = ask(_t('time_minutes', "Minutes spent: "))
    if not minutes.isdigit():
        print(_t('time_bad', "❌ Enter a whole number of minutes."))
        return
    note = ask(_t('time_note', "What was done (optional): "))
    billable = ask(_t('time_billable', "Billable? (y/N): ")).lower().startswith('y')
    result = call(collaboration.log_time, actor(), ticket_id, int(minutes), note,
                  billable=billable)
    if not failed(result):
        print(_t('time_logged', "✅ Logged. Total on this ticket: {h:.2f} hours.",
                 h=result['total_minutes'] / 60))


def _set_status(ticket_id) -> None:
    status = ask_choice(_t('new_status', "New status"), list(schema.STATUSES), label=status_text)
    if not status:
        return
    note = None
    if status in schema.DONE_STATUSES:
        note = ask(_t('resolution_note', "Resolution (shown to the student, optional): ")) or None
    result = call(service.set_status, actor(), ticket_id, status, note=note)
    if not failed(result):
        print(_t('status_set', "✅ {old} → {new}", old=status_text(result['old']),
                 new=status_text(result['new'])))


def _assign(ticket_id) -> None:
    who = ask(_t('assign_to', "Assign to (username; '-' to unassign): "))
    if not who:
        return
    result = call(service.assign, actor(), ticket_id, None if who == '-' else who)
    if not failed(result):
        print(_t('assigned', "✅ Assigned to {who}.", who=result['new'] or _t('nobody', 'nobody')))


def _edit(ticket_id) -> None:
    subject = ask(_t('edit_subject', "New title (Enter to keep): "))
    description = None
    if ask_yes(_t('edit_description_q', "Replace the description")):
        description = ask_text(_t('edit_description', "New description"))
    if not subject and not description:
        return
    reason = ask(_t('edit_reason', "Reason for the edit: "))
    result = call(service.edit_ticket, actor(), ticket_id, subject=subject or None,
                  description=description or None, reason=reason)
    if failed(result):
        return
    show_crisis(result.get('crisis'))
    print(_t('edited', "✅ Edited: {what}.", what=", ".join(result['changed']) or _t('nothing', 'nothing')))


def _move_team(ticket_id) -> None:
    team = _ask_team(_t('move_team', "Move to which team"), allow_none=False)
    if not team:
        return
    reason = ask(_t('move_reason', "Reason for the move: "))
    result = call(service.set_team, actor(), ticket_id, team, reason)
    if failed(result):
        return
    print(_t('moved', "✅ Moved to {team} ({tier}).", team=team_text(result['new']),
             tier=_tiers.TIER_LABELS[result['tier']]))
    if result['unassigned']:
        print(_t('moved_unassigned', "The previous assignee isn't in that team, so the ticket is unassigned."))


def _escalate(ticket_id) -> None:
    reason = ask(_t('escalate_reason', "Why escalate? "))
    if not failed(call(service.escalate, actor(), ticket_id, reason)):
        print(_t('escalated', "✅ Ticket #{id} escalated.", id=ticket_id))


def _merge(ticket_id) -> None:
    raw = ask(_t('merge_ids', "Duplicate ticket numbers to merge in (e.g. 12, 15): "))
    ids = call(numbers, raw)
    if failed(ids):
        return
    reason = ask(_t('merge_reason', "Reason for the merge: "))
    if not ask_yes(_t('merge_confirm', "Merge {ids} into #{id}", ids=raw, id=ticket_id)):
        return
    merged = call(service.merge, actor(), ticket_id, ids, reason)
    if not failed(merged):
        print(_t('merged', "✅ {n} ticket(s) merged into #{id}.", n=merged, id=ticket_id))


def _set_tier(ticket_id) -> None:
    tier = ask_choice(_t('tier', "Confidentiality"), list(_tiers.TIERS),
                      label=lambda t: _tiers.TIER_LABELS[t])
    if not tier:
        return
    reason = ask(_t('tier_reason', "Reason for the change (a sentence): "))
    result = call(_tiers.set_tier, actor(), ticket_id, tier, reason)
    if not failed(result):
        print(_t('tier_set', "✅ {old} → {new}", old=_tiers.TIER_LABELS[result['old']],
                 new=_tiers.TIER_LABELS[result['new']]))


def _break_glass(ticket_id) -> None:
    print(_t('bg_warning', "Break-glass opens a confidential ticket outside your team for "
             "{m} minutes. It is recorded and the administrators are told.",
             m=_tiers.BREAK_GLASS_MINUTES))
    reason = ask(_t('bg_reason', "Explain the emergency (at least 15 characters): "))
    if len(reason) < 15:
        print("❌ " + _t('bg_short', "Explain the emergency (at least a sentence)"))
        return
    if not ask_yes(_t('bg_confirm', "Open ticket #{id} with break-glass access", id=ticket_id)):
        return
    result = call(_tiers.break_glass, actor(), ticket_id, reason)
    if not failed(result):
        print(_t('bg_open', "✅ Open until {at} ({n} notified).", at=result['expires_at'],
                 n=result['notified']))
        view_ticket(ticket_id)


def _history(ticket_id) -> None:
    result = call(service.ticket_history, actor(), ticket_id)
    if failed(result):
        return

    def line(e):
        data = e.get('data') or {}
        if e['type'] == 'response':
            text = str(data.get('response_text') or '')[:70].replace("\n", " ")
            tag = _t('internal', " [INTERNAL NOTE]") if data.get('is_internal') else ''
            return f"  {e['datetime']}  reply  {data.get('responder_username') or ''}{tag}: {text}"
        if e['type'] == 'audit':
            return f"  {e['datetime']}  audit  {data.get('action')} by {data.get('user_id') or ''}"
        if e['type'] == 'attachment':
            return f"  {e['datetime']}  file   {data.get('original_filename')}"
        return f"  {e['datetime']}  raised {data.get('subject') or ''}"
    page_through(result['timeline'], line, title=_t('history', "History of #{id}", id=ticket_id))


def _ticket_360(ticket_id) -> None:
    ticket = call(service.get_ticket, actor(), ticket_id)
    if failed(ticket):
        return
    student = ticket.get('student_id')
    if not student:
        print(_t('no_student', "This ticket was not raised by a student."))
        return
    student_360(student)


# ── Refer to… ────────────────────────────────────────────────────────────


def _referral_fields(kind: str, values: dict, choices: dict) -> Optional[dict]:
    """What the adviser completes or overrides for ``kind``."""
    fields: dict = {}
    if kind == 'hardship':
        funds = choices.get('hardship_funds') or []
        if not funds:
            print(_t('no_funds', "There is no open hardship fund to apply to."))
            return None
        fund = ask_choice(_t('fund', "Fund"), funds, label=lambda f: str(f.get('name')))
        if not fund:
            return None
        fields['fund_id'] = fund.get('fund_id')
        fields['requested_amount'] = ask(_t('amount', "Amount requested (£): "))
        income = ask(_t('income', "Household income (£, optional): "))
        if income:
            fields['household_income'] = income
    elif kind == 'mitigating_circumstances':
        grounds = list(choices.get('mitigating_grounds') or [])
        pos = grounds.index(values.get('grounds')) + 1 if values.get('grounds') in grounds else None
        picked = ask_choice(_t('grounds', "Grounds"), grounds, default=pos)
        if picked:
            fields['grounds'] = picked
        for key, prompt in (('module_code', "Module code (optional): "),
                            ('assessment_ref', "Assessment (optional): "),
                            ('period_start', "Affected from (YYYY-MM-DD, optional): "),
                            ('period_end', "Affected until (YYYY-MM-DD, optional): ")):
            value = ask(_t(f'mc_{key}', prompt))
            if value:
                fields[key] = value
    elif kind == 'accessibility':
        types = list(choices.get('accommodation_types') or [])
        picked = ask_choice(_t('adjustment', "Adjustment type"), types,
                            default=types.index(values.get('accommodation_type')) + 1
                            if values.get('accommodation_type') in types else None)
        if picked:
            fields['accommodation_type'] = picked
    elif kind == 'early_warning':
        assignee = ask(_t('ew_assignee', "Assign the intervention to (username, optional): "))
        if assignee:
            fields['assigned_to'] = assignee
    extra = ask_text(_t('ref_text', "Text for the referral (empty keeps the ticket's text):"))
    if extra:
        fields['description' if kind != 'hardship' else 'circumstances'] = extra
    return fields


def refer_menu(ticket_id) -> None:
    opts = call(referrals.options, actor(), ticket_id)
    if failed(opts):
        return
    heading(_t('refer_heading', "➡  REFER TICKET #{id}", id=ticket_id))
    print(_t('ref_consent', "Sharing consent: {c}", c=opts.get('share_consent') or _t('none', 'none')))
    for r in opts.get('referrals') or []:
        print(_t('ref_existing', "  Already referred: {kind} → {ref} ({status})",
                 kind=referrals.KINDS.get(r['kind'], r['kind']), ref=r.get('target_ref') or '-',
                 status=r.get('status')))
    kinds = list(opts['kinds'].items())

    def label(item):
        _kind, entry = item
        return entry['label'] + ('' if entry['allowed'] else f" — {entry['blocked_reason']}")
    picked = ask_choice(_t('refer_to', "Refer to"), kinds, label=label, allow_none=True)
    if not picked:
        return
    kind, entry = picked
    if not entry['allowed']:
        print("❌ " + str(entry['blocked_reason']))
        return
    print(_t('prefilled', "Pre-filled from the ticket:"))
    for key, value in (entry.get('values') or {}).items():
        print(f"  {key}: {str(value)[:80] if value not in (None, '') else '-'}")
    fields = _referral_fields(kind, entry.get('values') or {}, opts.get('choices') or {})
    if fields is None or not ask_yes(_t('refer_confirm', "Send the {label}", label=entry['label'].lower())):
        return
    result = call(referrals.refer, actor(), ticket_id, kind, **fields)
    if not failed(result):
        print(_t('referred', "✅ Referred: {label} (reference {ref}).", label=entry['label'],
                 ref=result['reference']))


# ── student 360 ──────────────────────────────────────────────────────────


def student_360(student_id: Optional[str] = None) -> None:
    if not student_id:
        student_id = ask(_t('student_number', "Student number: "))
        if not student_id:
            return
    items = call(history360.contacts_for_student, actor(), student_id)
    if failed(items):
        return
    page_through(items, lambda i: (
        f"  {str(i.get('date') or '')[:16]:<17} {i['source']:<25} {str(i.get('status') or ''):<16} "
        f"{i.get('title') or ''}"), title=_t('h360', "Support history for {s}", s=student_id))


# ── reports ──────────────────────────────────────────────────────────────


def _dates():
    today = datetime.date.today()
    start = ask(_t('from', "From (YYYY-MM-DD) [30 days ago]: "),
                (today - datetime.timedelta(days=30)).isoformat())
    end = ask(_t('to', "To (YYYY-MM-DD) [today]: "), today.isoformat())
    return start, end


def service_report_screen() -> None:
    from education_system.systems.university.domains.student_support.domain.student_support.features.reports import (
        service_report,
    )
    start, end = _dates()
    team = _ask_team(_t('report_team', "Team"))
    report = call(service_report, actor(), start, end, team)
    if failed(report):
        return
    heading(_t('report_heading', "📊 SERVICE REPORT {a} to {b}{team}", a=start, b=end,
               team=f" — {team_text(team)}" if team else ''))
    print(_t('r_total', "Tickets raised: {n}", n=report.get('total_tickets', 0)))
    for title, key in (("First response", 'first_response'), ("Resolution", 'resolution')):
        s = report.get(key) or {}
        print(f"{title}: avg {s.get('avg_hours')} h, met {s.get('met')}/{s.get('measured')} "
              f"({s.get('met_pct')}%), breached {s.get('breached')}")
    backlog = report.get('backlog') or {}
    print(_t('r_backlog', "Backlog: {n} open, oldest {d} days", n=backlog.get('open'),
             d=backlog.get('oldest_days')))
    for bucket, count in (backlog.get('by_age') or {}).items():
        print(f"    {bucket:<14} {count}")
    sat = report.get('satisfaction') or {}
    print(_t('r_sat', "Satisfaction: avg {avg} from {n} ratings; surveys {a}/{s} answered",
             avg=sat.get('avg_rating'), n=sat.get('ratings'), a=sat.get('surveys_answered'),
             s=sat.get('surveys_sent')))
    d = report.get('deflection') or {}
    print(_t('r_defl', "Self-help: {v} visits, {x} answered without a ticket ({r}%)",
             v=d.get('visits'), x=d.get('deflected'), r=d.get('deflection_rate')))
    for name, counts in (report.get('volumes') or {}).items():
        print(f"{name.replace('_', ' ').capitalize()}: "
              + ", ".join(f"{k or '-'} {v}" for k, v in list(counts.items())[:10]))
    themes = (report.get('themes') or {}).get('top_keywords') or {}
    if themes:
        print(_t('r_themes', "Themes: ") + ", ".join(f"{k} ({v})" for k, v in themes.items()))
    pause()


def reports_menu(support) -> None:
    """Option 'Generate Reports': the service report, or the older reports."""
    print("  1. " + _t('rep_service', "Service report (SLA, backlog, satisfaction, self-help)"))
    print("  2. " + _t('rep_classic', "Ticket summary / performance / satisfaction / categories"))
    choice = ask(_t('choice', "Choice [1]: "), '1')
    if choice == '1':
        service_report_screen()
    elif choice == '2':
        from education_system.systems.university.domains.student_support.domain.student_support.features.reports import (
            generate_reports_menu,
        )
        call(generate_reports_menu, support)


# ── bulk changes ─────────────────────────────────────────────────────────


def bulk_menu(support=None) -> None:
    heading(_t('bulk_heading', "🔄 BULK CHANGES"))
    raw = ask(_t('bulk_ids', "Ticket numbers (e.g. 12, 15, 18): "))
    ids = call(numbers, raw)
    if failed(ids) or not ids:
        return
    print("  1. " + _t('b_assign', "Assign"))
    print("  2. " + _t('b_status', "Status"))
    print("  3. " + _t('b_priority', "Priority"))
    print("  4. " + _t('b_category', "Category"))
    choice = ask(_t('choice', "Choice: "))
    updates: dict = {}
    if choice == '1':
        updates['assigned_to'] = ask(_t('assign_to', "Assign to (username; '-' to unassign): "))
        if updates['assigned_to'] == '-':
            updates['assigned_to'] = None
    elif choice == '2':
        status = ask_choice(_t('new_status', "New status"), list(schema.STATUSES), label=status_text)
        if status:
            updates['status'] = status
    elif choice == '3':
        priority = ask_choice(_t('priority', "Priority"), TICKET_PRIORITIES)
        if priority:
            updates['priority'] = priority
    elif choice == '4':
        category = ask_choice(_t('category', "Category"), SUPPORT_CATEGORIES)
        if category:
            updates['category'] = category
    if not updates or not ask_yes(_t('bulk_confirm', "Apply to {n} ticket(s)", n=len(ids))):
        return
    count = call(service.bulk_update, actor(), ids, updates)
    if not failed(count):
        print(_t('bulk_done', "✅ {n} of {m} ticket(s) updated (others were not yours to change).",
                 n=count, m=len(ids)))


# ── export ───────────────────────────────────────────────────────────────

_EXPORT_COLUMNS = ('ticket_id', 'subject', 'status_label', 'priority', 'category', 'team',
                   'confidentiality', 'requester_username', 'student_id', 'assigned_to',
                   'created_at', 'first_response_at', 'resolved_at', 'satisfaction_rating',
                   'description')


def _collect(filters: dict, with_replies: bool, limit: int = 5000) -> dict:
    """Tickets (and replies) through the service: only what the signed-in
    person may see, confidential text left as the placeholder."""
    rows, replies, page = [], [], 1
    while len(rows) < limit:
        result = service.list_tickets(actor(), filters, page, 200)
        rows += result['tickets']
        if page >= result['total_pages']:
            break
        page += 1
    if with_replies:
        for t in rows[:limit]:
            try:
                full = service.get_ticket(actor(), t['ticket_id'])
            except PermissionError:
                continue
            for r in full.get('responses') or []:
                replies.append({'ticket_id': t['ticket_id'], 'when': r.get('response_datetime'),
                                'by': r.get('responder_username') or r.get('responder_role'),
                                'internal': int(bool(r.get('is_internal'))),
                                'text': r.get('response_text')})
    return {'tickets': rows[:limit], 'replies': replies}


def _write(path: Path, rows: list, columns, fmt: str) -> None:
    if fmt == 'json':
        path.write_text(json.dumps([{c: r.get(c) for c in columns} for r in rows], indent=2,
                                   default=str), encoding='utf-8')
        return
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(columns), extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding='utf-8')


def export_menu(support=None) -> None:
    heading(_t('export_heading', "📤 EXPORT"))
    print("  1. " + _t('e_tickets', "Tickets"))
    print("  2. " + _t('e_responses', "Tickets with their replies"))
    print("  3. " + _t('e_metrics', "Metrics"))
    print("  4. " + _t('e_filtered', "Filtered tickets"))
    choice = ask(_t('choice', "Choice: "))
    if choice == '3':
        from education_system.systems.university.domains.student_support.domain.student_support.operations.export import (
            export_metrics_menu,
        )
        call(export_metrics_menu, support)
        return
    if choice not in ('1', '2', '4'):
        return
    filters: dict = {}
    start, end = (ask(_t('from_opt', "From (YYYY-MM-DD, optional): ")),
                  ask(_t('to_opt', "To (YYYY-MM-DD, optional): ")))
    if start:
        filters['date_from'] = start
    if end:
        filters['date_to'] = end + ' 23:59:59' if len(end) == 10 else end
    if choice == '4':
        status = ask_choice(_t('status_opt', "Status (Enter for any)"), list(schema.STATUSES),
                            label=status_text, allow_none=True)
        team = _ask_team(_t('team', "Team"))
        priority = ask(_t('priority_opt', "Priority (optional): "))
        filters.update({k: v for k, v in (('status', status), ('team', team),
                                          ('priority', priority)) if v})
    fmt = 'json' if ask(_t('format', "Format: 1 CSV, 2 JSON [1]: "), '1') == '2' else 'csv'
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    default = f"support_tickets_{stamp}.{fmt}"
    path = Path(ask(_t('save_as', "Save as [{name}]: ", name=default), default)).expanduser()
    data = call(_collect, filters, choice == '2')
    if failed(data):
        return
    # The file is written after the reads have finished.
    if failed(call(_write, path, data['tickets'], _EXPORT_COLUMNS, fmt)):
        return
    print(_t('exported', "✅ {n} ticket(s) written to {path}", n=len(data['tickets']), path=path))
    if choice == '2':
        replies_path = path.with_name(path.stem + '_replies' + path.suffix)
        if not failed(call(_write, replies_path, data['replies'],
                           ('ticket_id', 'when', 'by', 'internal', 'text'), fmt)):
            print(_t('exported_replies', "✅ {n} replies written to {path}",
                     n=len(data['replies']), path=replies_path))


__all__ = ['caseload_menu', 'work_menu', 'work_ticket', 'refer_menu', 'student_360',
           'service_report_screen', 'reports_menu', 'bulk_menu', 'export_menu']

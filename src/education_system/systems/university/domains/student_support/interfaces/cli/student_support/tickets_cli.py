"""Student Support CLI: raising, reading and answering tickets.

Everyone uses these screens: the guided new ticket (UK categories, self-help
suggestions before submitting, the sharing-consent question and the crisis
contacts when the text asks for them), the ticket view (tier, team, SLA and
consent shown; internal notes only reach the staff working the ticket — the
service leaves them out for anyone else), replies and the ticket lists.
"""

from __future__ import annotations

import mimetypes
import os
from typing import Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    consent,
    deflection,
    routing,
    schema,
    service,
    sla,
    store,
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
    category_text,
    failed,
    heading,
    is_staff,
    page_through,
    pause,
    service_pages,
    show_crisis,
    status_text,
    team_text,
    ticket_row,
    tier_badge,
)


# ── new ticket ───────────────────────────────────────────────────────────


def _templates() -> list:
    from education_system.systems.university.domains.student_support.domain.student_support.features.templates import (
        get_ticket_templates,
    )
    result = call(get_ticket_templates)
    return [] if failed(result) else list(result or [])


def _pick_template(force: bool) -> Optional[dict]:
    templates = _templates()
    if not templates:
        if force:
            print(_t('no_templates', "There are no ticket templates yet."))
        return None
    print(_t('templates', "\nTicket templates:"))
    if not force:
        print("  0. " + _t('from_scratch', "Start from scratch"))
    return ask_choice(_t('pick_template', "Template"), templates,
                      label=lambda t: f"{t.get('name')} ({category_text(t.get('category'))})",
                      allow_none=True)


def _show_suggestion(item: dict) -> None:
    """The suggestion in full where the knowledge base holds it."""
    print(f"\n📖 {item['title']}")
    body = item.get('snippet') or ''
    if item['source'] == 'kb':
        from education_system.systems.university.domains.student_support.domain.student_support.features.knowledge_base import (
            get_kb_articles,
        )
        articles = call(get_kb_articles)
        if not failed(articles):
            match = next((a for a in articles or [] if str(a.get('article_id')) == str(item['id'])),
                         None)
            if match:
                body = match.get('content') or body
    print(body)


def _deflect(text: str):
    """Show self-help matches for ``text``. Returns ``(visit_id, stop)`` —
    ``stop`` True when the person's question was answered."""
    suggestions = call(deflection.suggest, text)
    if failed(suggestions) or not suggestions:
        return None, False
    visit = call(deflection.start, actor(), text, suggestions)
    visit = None if failed(visit) else visit
    while True:
        heading(_t('suggest_heading', "These articles may answer your question"))
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. {s['title']} — {s['snippet'][:90]}")
        choice = ask(_t('suggest_prompt', "Read one (number), 'd' if this answered your question, "
                        "or Enter to carry on with your ticket: ")).lower()
        if not choice:
            return visit, False
        if choice == 'd':
            return visit, True
        if choice.isdigit() and 1 <= int(choice) <= len(suggestions):
            item = suggestions[int(choice) - 1]
            if visit:
                call(deflection.viewed, actor(), visit, item['key'])
            _show_suggestion(item)


def _read_attachments() -> list:
    files = []
    while ask_yes(_t('add_file', "Add a file")):
        path = ask(_t('file_path', "File path: "))
        if not path or not os.path.isfile(path):
            print(_t('file_missing', "File not found."))
            continue
        data = call(lambda p=path: open(p, 'rb').read())
        if failed(data):
            continue
        files.append({'filename': os.path.basename(path), 'data': data,
                      'mime_type': mimetypes.guess_type(path)[0]})
        print(_t('file_added', "Added {name}", name=os.path.basename(path)))
    return files


def _ask_category(text: str, default=None) -> Optional[str]:
    from education_system.systems.university.domains.student_support.domain.student_support.automation.sentiment_analysis import (
        _suggest_category,
    )
    suggested = routing.uk_category(default) if default else None
    suggested = suggested or call(_suggest_category, text)
    suggested = None if failed(suggested) else suggested
    print(_t('categories', "\nWhat is it about?"))
    pos = SUPPORT_CATEGORIES.index(suggested) + 1 if suggested in SUPPORT_CATEGORIES else None
    return ask_choice(_t('category', "Category"), SUPPORT_CATEGORIES,
                      label=lambda c: c + (_t('suggested', " (suggested)") if c == suggested else ''),
                      default=pos)


def _ask_priority(default='Medium') -> str:
    print(_t('priorities', "\nHow urgent is it?"))
    pos = TICKET_PRIORITIES.index(default) + 1 if default in TICKET_PRIORITIES else 2
    return ask_choice(_t('priority', "Priority"), TICKET_PRIORITIES, default=pos) or default


def _ask_consent(ticket_id) -> None:
    """The sharing question, when the requester has not answered it yet."""
    state = call(consent.consent_state, actor(), ticket_id)
    if failed(state) or not state.get('prompt'):
        return
    print("\n🔒 " + state['question'])
    answer = ask(_t('consent_prompt', "Share with other university services? "
                    "(y = yes, n = no, Enter = decide later): ")).lower()
    if answer in ('y', 'yes', 'n', 'no'):
        result = call(consent.record_share_consent, actor(), ticket_id, answer.startswith('y'))
        if not failed(result):
            print(_t('consent_saved', "Thank you — your answer has been saved ({answer}).",
                     answer=result['new']))
    else:
        print(_t('consent_later', "You can answer later from the ticket."))


def new_ticket(support=None, *, use_template: bool = False) -> None:
    """Raise a ticket: everything is asked first, then the service is called."""
    heading(_t('new_heading', "🎫 NEW SUPPORT TICKET"))
    requester = None
    if is_staff():
        requester = ask(_t('requester', "Raise it for (student number or username; "
                           "Enter for yourself): ")) or None
    template = _pick_template(use_template)
    if use_template and not template:
        return
    t_subject = (template or {}).get('subject_template') or (template or {}).get('title_template')
    t_body = (template or {}).get('message_template') or (template or {}).get('description_template')
    subject = ask(_t('subject', "Subject{hint}: ", hint=f" [{t_subject}]" if t_subject else ''),
                  t_subject or None)
    if not subject:
        print(_t('subject_needed', "A subject is required."))
        return
    if t_body:
        print(_t('template_text', "Template text:\n{text}", text=t_body))
    description = ask_text(_t('describe', "Describe what you need help with"
                              + (" (empty keeps the template text)" if t_body else "") + ":"))
    description = description or t_body or ''
    if not description:
        print(_t('description_needed', "A description is required."))
        return
    visit, answered = (None, False) if requester else _deflect(f"{subject}\n{description}")
    if answered:
        if visit:
            outcome = call(deflection.finish, actor(), visit)
            if not failed(outcome):
                print(_t('deflected', "Glad that helped — no ticket was raised."))
        return
    category = _ask_category(f"{subject} {description}", (template or {}).get('category'))
    if not category:
        return
    priority = _ask_priority((template or {}).get('priority') or 'Medium')
    tags_raw = ask(_t('tags', "Tags (comma-separated, optional): "))
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    attachments = _read_attachments()
    print(_t('review', "\n{subject} — {category}, {priority}", subject=subject,
             category=category, priority=priority))
    if not ask_yes(_t('submit', "Submit this ticket"), default=True):
        if visit:
            call(deflection.finish, actor(), visit)
        print(_t('not_submitted', "Not submitted."))
        return
    template_id = (template or {}).get('template_id')
    result = call(service.submit_ticket, actor(), subject=subject, description=description,
                  category=category, priority=priority, requester=requester,
                  attachments=attachments, tags=tags,
                  template_id=template_id if isinstance(template_id, int) else None)
    if failed(result):
        return
    # The crisis contacts come first, before anything else is printed.
    show_crisis(result.get('crisis'))
    tid = result['ticket_id']
    print(_t('created', "✅ Ticket #{id} raised — {team} {badge}", id=tid,
             team=team_text(result.get('team')), badge=tier_badge(result.get('confidentiality'))))
    if visit:
        call(deflection.finish, actor(), visit, tid)
    if not requester:
        _ask_consent(tid)
    if ask_yes(_t('view_now', "View the ticket now")):
        view_ticket(tid)


# ── one ticket ───────────────────────────────────────────────────────────


def _sla_lines(ticket: dict) -> list:
    if schema.normalize_status(ticket.get('status'), default='open') in schema.DONE_STATUSES \
            and not ticket.get('first_response_at'):
        return []
    with store.reading() as conn:
        state = sla.ticket_sla(conn, ticket)
    lines = [_t('sla_first', "First response due {due}{state}", due=state['first_response_due'],
                state=(" — met" if state['first_response_met'] else " — BREACHED")
                if state['first_response_met'] is not None
                else (" — BREACHED" if state['first_response_breached'] else ''))]
    res_state = ''
    if state['resolution_met'] is not None:
        res_state = " — met" if state['resolution_met'] else " — BREACHED"
    elif state['resolution_breached']:
        res_state = " — BREACHED"
    lines.append(_t('sla_resolution', "Resolution due {due}{state}",
                    due=state['resolution_due'], state=res_state))
    if state['hours_left'] is not None:
        lines.append(_t('sla_left', "Next target in {hours} working hours",
                        hours=state['hours_left']))
    return lines


def _consent_text(ticket: dict) -> str:
    value = ticket.get('share_consent')
    if value == 'granted':
        return _t('consent_granted', "may be shared ({at})", at=ticket.get('share_consent_at'))
    if value == 'declined':
        return _t('consent_declined', "not to be shared ({at})", at=ticket.get('share_consent_at'))
    return _t('consent_none', "not asked / not answered")


def _print_ticket(ticket: dict) -> None:
    badge = tier_badge(ticket.get('confidentiality'))
    heading(f"🎫 #{ticket['ticket_id']} {ticket.get('subject') or ''} {badge}".rstrip())
    rows = [
        (_t('f_status', "Status"), ticket.get('status_label') or status_text(ticket.get('status'))),
        (_t('f_priority', "Priority"), ticket.get('priority')),
        (_t('f_category', "Category"), category_text(ticket.get('category'))),
        (_t('f_team', "Team"), team_text(ticket.get('team'))),
        (_t('f_tier', "Confidentiality"), badge.strip('[]').title() or "Standard"),
        (_t('f_requester', "Requester"), ticket.get('requester_username') or ticket.get('student_id')),
        (_t('f_assigned', "Assigned to"), ticket.get('assigned_to') or _t('unassigned', 'unassigned')),
        (_t('f_consent', "Sharing consent"), _consent_text(ticket)),
        (_t('f_created', "Raised"), ticket.get('created_at')),
    ]
    if ticket.get('resolved_at'):
        rows.append((_t('f_resolved', "Resolved"), ticket['resolved_at']))
    for label, value in rows:
        print(f"  {label + ':':<17} {value if value not in (None, '') else '-'}")
    sla_lines = call(_sla_lines, ticket)
    if not failed(sla_lines):
        for line in sla_lines:
            print(f"  ⏱  {line}")
    if ticket.get('access') == 'break_glass':
        print(_t('bg_note', "  ⚠ Opened with break-glass access — this view is recorded."))
    print("\n" + _t('description', "Description:"))
    print("  " + str(ticket.get('description') or '').replace("\n", "\n  "))
    if ticket.get('resolution'):
        print(_t('resolution', "Resolution: {text}", text=ticket['resolution']))
    for att in ticket.get('attachments') or []:
        hidden = "" if att.get('is_public', 1) else _t('private', " (staff only)")
        print(f"  📎 {att.get('original_filename')}{hidden}")


def _response_line(r: dict) -> str:
    who = r.get('responder_username') or r.get('responder_role') or ''
    tag = _t('internal', " [INTERNAL NOTE]") if r.get('is_internal') else ''
    auto = " 🤖" if r.get('is_auto_generated') else ''
    text = str(r.get('response_text') or '').replace("\n", "\n      ")
    return f"\n  [{r.get('response_datetime')}] {who}{auto}{tag}:\n      {text}"


def view_ticket(ticket_id: Optional[int] = None) -> None:
    """Show one ticket (the service decides what the signed-in person sees)."""
    if ticket_id is None:
        ticket_id = ask_ticket_id()
        if ticket_id is None:
            return
    ticket = call(service.get_ticket, actor(), ticket_id)
    if failed(ticket):
        return
    show_crisis(ticket.get('crisis_support'))
    _print_ticket(ticket)
    responses = ticket.get('responses') or []
    if len(responses) > 20:
        page_through(responses, _response_line, title=_t('conversation', "Conversation"))
    else:
        print("\n" + _t('conversation_n', "Conversation ({n}):", n=len(responses)))
        for r in responses:
            print(_response_line(r))
    if ticket.get('access') == 'owner':
        _ask_consent(ticket['ticket_id'])
        _owner_actions(ticket)
    else:
        pause()


def _owner_actions(ticket: dict) -> None:
    done = schema.normalize_status(ticket.get('status'), default='open') in schema.DONE_STATUSES
    options = _t('owner_actions', "\nr reply") + (_t('owner_rate', ", s rate the help") if done else '')
    choice = ask(options + _t('owner_back', ", Enter to go back: ")).lower()
    if choice == 'r':
        reply(ticket['ticket_id'])
    elif choice == 's' and done:
        rating = ask(_t('rating', "Rating 1-5: "))
        feedback = ask(_t('feedback', "Comments (optional): ")) or None
        if not failed(call(service.rate_ticket, actor(), ticket['ticket_id'], rating, feedback)):
            print(_t('rated', "Thank you for your feedback."))


def reply(ticket_id: Optional[int] = None, *, internal: Optional[bool] = None) -> None:
    """Reply (staff working the ticket may write an internal note instead)."""
    if ticket_id is None:
        ticket_id = ask_ticket_id()
        if ticket_id is None:
            return
    if internal is None:
        internal = is_staff() and ask_yes(_t('as_internal', "Internal note (staff only)"))
    text = ask_text(_t('note_text', "Internal note:") if internal else _t('reply_text', "Your reply:"))
    if not text:
        print(_t('nothing_sent', "Nothing was sent."))
        return
    result = call(service.post_response, actor(), ticket_id, text, internal=internal)
    if failed(result):
        return
    show_crisis(result.get('crisis'))
    print(_t('note_saved', "✅ Internal note added.") if internal else _t('reply_sent', "✅ Reply sent."))


# ── lists ────────────────────────────────────────────────────────────────


def _filters(staff: bool) -> Optional[dict]:
    print(_t('filter_heading', "\nShow:"))
    print("  1. " + _t('flt_active', "Active tickets"))
    print("  2. " + _t('flt_all', "All tickets"))
    print("  3. " + _t('flt_done', "Resolved and closed"))
    print("  4. " + _t('flt_search', "Search subject / description"))
    if staff:
        print("  5. " + _t('flt_status', "By status"))
        print("  6. " + _t('flt_team', "By team"))
        print("  7. " + _t('flt_category', "By category"))
        print("  8. " + _t('flt_assignee', "Assigned to someone"))
        print("  9. " + _t('flt_unassigned', "Unassigned"))
    choice = ask(_t('filter_prompt', "Choice [1]: "), '1')
    if choice == '1':
        return {'active_only': True}
    if choice == '2':
        return {}
    if choice == '3':
        return {'status': list(schema.DONE_STATUSES)}
    if choice == '4':
        return {'search': ask(_t('search_for', "Search for: "))}
    if staff and choice == '5':
        status = ask_choice(_t('status', "Status"), list(schema.STATUSES), label=status_text)
        return {'status': status} if status else None
    if staff and choice == '6':
        team = ask_choice(_t('team', "Team"), routing.teams(), label=lambda t: t['label'])
        return {'team': team['key']} if team else None
    if staff and choice == '7':
        category = ask_choice(_t('category', "Category"), SUPPORT_CATEGORIES)
        return {'category': category} if category else None
    if staff and choice == '8':
        return {'assigned_to': ask(_t('assignee', "Username: ")) or None}
    if staff and choice == '9':
        return {'unassigned': True}
    print(_t('invalid_choice', "Invalid choice."))
    return None


def my_tickets(support=None) -> None:
    filters = _filters(False)
    if filters is None:
        return
    service_pages(lambda page: service.list_my_tickets(actor(), filters, page, 20), ticket_row,
                  title=_t('my_tickets', "My support tickets"),
                  pick=lambda t: view_ticket(t['ticket_id']))


def all_tickets(support=None, open_ticket=None) -> None:
    """Every ticket the signed-in staff member may work (their teams and tiers)."""
    filters = _filters(True)
    if filters is None:
        return
    service_pages(lambda page: service.list_tickets(actor(), filters, page, 20), ticket_row,
                  title=_t('all_tickets', "Support tickets"),
                  pick=lambda t: (open_ticket or view_ticket)(t['ticket_id']))


def tickets_menu() -> None:
    """T: view, reply, consent — for everyone."""
    while True:
        heading(_t('tickets_heading', "🎫 TICKETS"))
        print("  1. " + _t('t_view', "View a ticket"))
        print("  2. " + _t('t_reply', "Reply to a ticket"))
        print("  3. " + _t('t_mine', "My tickets"))
        print("  4. " + _t('t_new', "Raise a new ticket"))
        print("  5. " + _t('t_consent', "Answer or change the sharing question on my ticket"))
        print("  0. " + _t('back', "Back"))
        choice = ask(_t('choice', "Choice: "))
        if choice in ('0', ''):
            return
        if choice == '1':
            view_ticket()
        elif choice == '2':
            reply()
        elif choice == '3':
            my_tickets()
        elif choice == '4':
            new_ticket()
        elif choice == '5':
            _change_consent()
        else:
            print(_t('invalid_choice', "Invalid choice."))


def _change_consent() -> None:
    tid = ask_ticket_id()
    if tid is None:
        return
    state = call(consent.consent_state, actor(), tid)
    if failed(state):
        return
    print("\n🔒 " + state['question'])
    print(_t('consent_now', "Current answer: {value}", value=state['share_consent'] or '-'))
    answer = ask(_t('consent_change', "Share? (y/n, Enter to leave it): ")).lower()
    if answer in ('y', 'yes', 'n', 'no'):
        result = call(consent.record_share_consent, actor(), tid, answer.startswith('y'))
        if not failed(result):
            print(_t('consent_saved', "Thank you — your answer has been saved ({answer}).",
                     answer=result['new']))


__all__ = ['new_ticket', 'view_ticket', 'reply', 'my_tickets', 'all_tickets', 'tickets_menu']

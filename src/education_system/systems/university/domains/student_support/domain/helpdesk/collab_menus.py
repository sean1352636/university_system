"""Text menus for the newer support tools (the Helpdesk CLI's ticket actions
and main menu, and the Student Support CLI, call these).

Everything goes through the support services, which check permission:
followers / links / time (``collaboration``), major incidents and known
issues (``incidents``), support e-mail review (``email_in``) and the
automation settings (``settings``).
"""

from __future__ import annotations

_PKG = "education_system.systems.university.domains.student_support.domain.student_support"


def _mod(name):
    import importlib
    return importlib.import_module(f"{_PKG}.{name}")


def _try(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        print(f"\n{exc}")
        return None


def _ask(prompt) -> str:
    return input(prompt).strip()


def _lines(prompt) -> str:
    print(f"{prompt} (finish with a line containing only 'done'):")
    out = []
    while True:
        line = input()
        if line.strip().lower() == 'done':
            break
        out.append(line)
    return "\n".join(out).strip()


def _choose(options) -> str | None:
    for i, (_key, label) in enumerate(options, 1):
        print(f"{i}. {label}")
    print("0. Back")
    choice = _ask("Choose: ")
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        return options[int(choice) - 1][0]
    return None


# ── one ticket ──────────────────────────────────────────────────────────


def followers_menu(auth, ticket_id) -> None:
    collab = _mod('collaboration')
    me = (_mod('auth').user_of(auth) or {}).get('username')
    while True:
        rows = _try(collab.list_followers, auth, ticket_id)
        if rows is None:
            return
        print(f"\nFollowers of ticket #{ticket_id}: "
              + (", ".join(r['username'] for r in rows) or "none"))
        action = _choose([('follow', "Follow it myself"), ('unfollow', "Stop following it"),
                          ('add', "Add a member of staff"), ('remove', "Remove a follower")])
        if action is None:
            return
        if action == 'follow':
            _try(collab.add_follower, auth, ticket_id, me)
        elif action == 'unfollow':
            _try(collab.remove_follower, auth, ticket_id, me)
        elif action == 'add':
            _try(collab.add_follower, auth, ticket_id, _ask("Username: "))
        elif action == 'remove':
            _try(collab.remove_follower, auth, ticket_id, _ask("Username: "))


def unlink_menu(auth, ticket_id) -> None:
    collab = _mod('collaboration')
    links = _try(collab.list_links, auth, ticket_id)
    if not links:
        print("\nThis ticket has no links.")
        return
    for link in links:
        print(f"  {link['label']} #{link['ticket_id']}")
    other = _ask("Unlink from ticket number (blank to cancel): ").lstrip('#')
    if other:
        removed = _try(collab.unlink_tickets, auth, ticket_id, other)
        if removed is not None:
            print("Link removed." if removed else "Those tickets were not linked.")


def time_menu(auth, ticket_id) -> None:
    collab = _mod('collaboration')
    data = _try(collab.time_entries, auth, ticket_id)
    if data is None:
        return
    for e in data['entries']:
        print(f"  [{e['time_id']}] {e['created_at']} {e['username'] or ''}: "
              f"{e['duration_minutes']} min {'(billable) ' if e['billable'] else ''}"
              f"{e['description'] or ''}")
    print(f"Total: {data['total_minutes'] / 60:.2f} hours")
    entry = _ask("Remove entry number (blank to keep all): ")
    if entry.isdigit():
        total = _try(collab.delete_time_entry, auth, int(entry))
        if total is not None:
            print(f"Removed. Total now {total / 60:.2f} hours.")


def incident_for_ticket(auth, ticket_id) -> None:
    inc = _mod('incidents')
    rows = _try(inc.list_incidents, auth, ['open', 'monitoring'])
    if rows is None:
        return
    for r in rows:
        print(f"  #{r['incident_id']} {r['title']} ({r['status_label']}, {r['tickets']} tickets)")
    choice = _ask("Incident number to add this ticket to, or 'new' to declare one: ").lstrip('#')
    if choice.lower() == 'new':
        _declare(auth, [ticket_id])
    elif choice.isdigit():
        result = _try(inc.attach, auth, int(choice), [ticket_id])
        if result:
            _report_attach(result)


# ── incidents ───────────────────────────────────────────────────────────


def _report_attach(result) -> None:
    print(f"\n{result['attached']} ticket(s) attached.")
    for tid, why in sorted(result['skipped'].items()):
        print(f"  #{tid} not attached: {why}")


def _declare(auth, ticket_ids=()) -> None:
    inc = _mod('incidents')
    title = _ask("Title (everyone sees it): ")
    public = _lines("Public message for affected people")
    desc = _lines("Internal description")
    team = _ask("Team (blank for none, e.g. it_services): ") or None
    severity = _ask("Severity (minor/major/critical) [major]: ") or 'major'
    if not ticket_ids:
        ticket_ids = _ask("Tickets to attach (e.g. 12 15 18, blank for none): ").replace(',', ' ').split()
    result = _try(inc.declare, auth, title, desc, public_message=public, team=team,
                  severity=severity, ticket_ids=ticket_ids)
    if result:
        print(f"\nIncident #{result['incident_id']} declared.")
        if ticket_ids:
            _report_attach(result)


def incidents_menu(auth) -> None:
    inc = _mod('incidents')
    while True:
        rows = _try(inc.list_incidents, auth, ['open', 'monitoring'])
        if rows is None:
            return
        print("\nMAJOR INCIDENTS")
        print("=" * 60)
        for r in rows:
            print(f"  #{r['incident_id']} [{r['status_label']}] {r['title']} — "
                  f"{r['open_tickets']} open of {r['tickets']} tickets")
        if not rows:
            print("  No active incidents.")
        action = _choose([('declare', "Declare an incident"), ('view', "View an incident"),
                          ('attach', "Attach tickets"), ('detach', "Detach a ticket"),
                          ('update', "Post an update to every ticket"),
                          ('monitoring', "Mark as monitoring"), ('reopen', "Mark as open"),
                          ('resolve', "Resolve (resolves every open ticket)"),
                          ('history', "Show resolved incidents")])
        if action is None:
            return
        if action == 'declare':
            _declare(auth)
            continue
        if action == 'history':
            for r in _try(inc.list_incidents, auth, ['resolved']) or []:
                print(f"  #{r['incident_id']} {r['title']} — resolved {r['resolved_at']} "
                      f"by {r['resolved_by']}")
            continue
        iid = _ask("Incident number: ").lstrip('#')
        if not iid.isdigit():
            continue
        iid = int(iid)
        if action == 'view':
            data = _try(inc.get_incident, auth, iid)
            if data:
                print(f"\n#{data['incident_id']} {data['title']} ({data['status_label']})")
                if data.get('public_message'):
                    print(f"Public: {data['public_message']}")
                if data.get('description'):
                    print(f"Internal: {data['description']}")
                for t in data['tickets']:
                    print(f"  #{t['ticket_id']} {t['status']:<20} {t['subject']}")
        elif action == 'attach':
            result = _try(inc.attach, auth, iid,
                          _ask("Ticket numbers: ").replace(',', ' ').split())
            if result:
                _report_attach(result)
        elif action == 'detach':
            tid = _ask("Ticket number: ").lstrip('#')
            if tid.isdigit():
                _try(inc.detach, auth, iid, int(tid))
        elif action == 'update':
            text = _lines("Update (posted on every open ticket)")
            count = _try(inc.post_update, auth, iid, text)
            if count is not None:
                print(f"Update posted to {count} ticket(s).")
        elif action in ('monitoring', 'reopen'):
            _try(inc.set_status, auth, iid, 'monitoring' if action == 'monitoring' else 'open')
        elif action == 'resolve':
            text = _lines("Resolution (sent with every ticket)")
            result = _try(inc.resolve, auth, iid, text)
            if result:
                print(f"{result['resolved']} ticket(s) resolved.")
                if result['skipped']:
                    print("Left open (not yours to work): "
                          + ", ".join(f"#{t}" for t in result['skipped']))


def known_issues_menu(auth) -> None:
    inc = _mod('incidents')
    issues = _try(inc.known_issues, auth)
    if not issues:
        print("\nThere are no known issues right now.")
        return
    print("\nKNOWN ISSUES")
    print("=" * 60)
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue['title']}")
        if issue['public_message']:
            print(f"   {issue['public_message']}")
    choice = _ask("Number of an issue that affects you (blank to go back): ")
    if not choice.isdigit() or not 1 <= int(choice) <= len(issues):
        return
    details = _ask("Anything that will help (optional): ")
    result = _try(inc.report_affected, auth, issues[int(choice) - 1]['incident_id'], details)
    if result:
        if result.get('crisis'):
            print("\n" + result['crisis'].get('message', ''))
        print(f"\nYou already have ticket #{result['ticket_id']} for this issue."
              if result.get('existing') else
              f"\nThanks — your ticket #{result['ticket_id']} has been added to this issue.")


def followed_menu(auth) -> None:
    rows = _try(_mod('collaboration').followed_tickets, auth)
    if rows is None:
        return
    print("\nTICKETS I FOLLOW")
    for t in rows:
        print(f"  #{t['ticket_id']} [{t['status']}] {t['subject']} "
              f"({t['assigned_to'] or 'unassigned'})")
    if not rows:
        print("  None.")


# ── support e-mail and settings ─────────────────────────────────────────


def mail_menu(auth) -> None:
    email_in = _mod('email_in')
    while True:
        rows = _try(email_in.list_quarantine, auth)
        if rows is None:
            return
        print("\nSUPPORT E-MAIL WAITING FOR REVIEW")
        print("=" * 60)
        for r in rows:
            print(f"  [{r['mail_id']}] {r['received_at']} {r['from_address']}: {r['subject']}"
                  f"\n        why: {r['reason']}")
        if not rows:
            print("  Nothing waiting.")
        action = _choose([('read', "Read a message"), ('accept', "Raise a ticket from it"),
                          ('discard', "Discard it"), ('poll', "Check the mailbox now")])
        if action is None:
            return
        if action == 'poll':
            print(_try(email_in.poll))
            continue
        mid = _ask("Message number: ")
        if not mid.isdigit():
            continue
        if action == 'read':
            msg = _try(email_in.read_quarantined, auth, int(mid))
            if msg:
                print(f"\nFrom: {msg['from']}\nSubject: {msg['subject']}\nDate: {msg['date']}")
                if msg['suggested']:
                    print("Accounts with this address: " + ", ".join(msg['suggested']))
                print(f"\n{msg['text']}")
        elif action == 'accept':
            who = _ask("Raise the ticket for (username or student number): ")
            result = _try(email_in.accept_quarantined, auth, int(mid), who)
            if result:
                print(f"Ticket #{result['ticket_id']} raised.")
        elif action == 'discard':
            _try(email_in.discard_quarantined, auth, int(mid), _ask("Why? "))


def automation_menu(auth) -> None:
    settings = _mod('settings')
    values = _try(settings.read, auth)
    if values is None:
        return
    print("\nSUPPORT AUTOMATION SETTINGS")
    for key in settings.DEFAULTS:
        print(f"  {key}: {values[key]}")
    print("Enter new values (blank keeps the current one).")
    changes = {}
    for key in settings.DEFAULTS:
        value = _ask(f"{key} [{values[key]}]: ")
        if value:
            changes[key] = value
    if changes and _try(settings.update, auth, changes) is not None:
        print("Saved.")


__all__ = [
    'followers_menu', 'unlink_menu', 'time_menu', 'incident_for_ticket', 'incidents_menu',
    'known_issues_menu', 'followed_menu', 'mail_menu', 'automation_menu',
]

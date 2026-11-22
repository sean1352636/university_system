"""Shared pieces for the Helpdesk CLI on the one ticket model.

The Helpdesk menus read and change tickets only through the ticket service
(``student_support.service`` / ``helpdesk.tickets.service``), which checks
who may see what, reveals sealed text after the gate and applies tiers,
crisis detection, SLA, routing and e-mail. This module holds what the menus
share on top of that: the signed-in person's local ``users.id`` (resolved by
username — the session's ``id`` is an auth.db id), the crisis contacts
printout, and the tier / crisis / SLA lines of a ticket view.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# The actor automated Helpdesk workflows act as (configured by admins, so
# they act with admin authority; the audit trail names 'system').
SYSTEM_ACTOR = {'username': 'system', 'role': 'admin', 'id': None}


def _username(auth: Any) -> Optional[str]:
    user = auth if isinstance(auth, dict) else getattr(auth, 'current_user', None)
    return (user or {}).get('username') if user else None


def local_user_id(auth: Any) -> Optional[int]:
    """The signed-in person's student_records ``users.id`` (None: no local
    profile). Resolved by username — auth.db ids differ."""
    username = _username(auth)
    if not username:
        return None
    from education_system.systems.university.infrastructure.auth.session_user import (
        resolve_local_identity,
    )
    try:
        return resolve_local_identity(username)[0]
    except Exception:
        logger.debug("Could not resolve %s to a local user", username, exc_info=True)
        return None


def print_crisis(crisis) -> None:
    """Show the crisis contacts at once (``result['crisis']`` from a submit
    or a reply)."""
    if not crisis:
        return
    print("\n" + "!" * 60)
    print(crisis.get('message') or "\n".join(crisis.get('lines') or []))
    print("!" * 60 + "\n")


def tier_badge(ticket) -> str:
    """'[RESTRICTED]' / '[SAFEGUARDING]' for a confidential ticket, else ''."""
    tier = str((ticket or {}).get('confidentiality') or 'standard').lower()
    return '' if tier == 'standard' else f"[{tier.upper()}]"


def status_label(ticket) -> str:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    return (ticket or {}).get('status_label') or schema.status_label((ticket or {}).get('status'))


def sla_label(ticket) -> str:
    """The ticket's SLA standing ('Due in 3.5h', 'Breached', ...)."""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.service import (
        sla_status,
    )
    try:
        return sla_status(ticket)['label']
    except Exception:
        logger.debug("No SLA standing for ticket %s", (ticket or {}).get('ticket_id'), exc_info=True)
        return '-'


def fetch_ticket(auth, ticket_id) -> Optional[dict]:
    """The ticket as ``auth`` may see it, or None after printing why not."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    try:
        return service.get_ticket(auth, ticket_id)
    except (PermissionError, ValueError) as e:
        print(e)
        return None


def read_lines(prompt: str) -> str:
    """Lines typed until 'done' (the CLI's multi-line entry)."""
    print(prompt)
    lines = []
    while True:
        line = input()
        if line.strip().lower() == 'done':
            break
        lines.append(line)
    return "\n".join(lines).strip()


__all__ = ['SYSTEM_ACTOR', 'local_user_id', 'print_crisis', 'tier_badge', 'status_label',
           'sla_label', 'fetch_ticket', 'read_lines']

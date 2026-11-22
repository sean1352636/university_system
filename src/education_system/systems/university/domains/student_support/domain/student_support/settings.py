"""Support automation settings.

Kept in the Helpdesk's ``helpdesk_system_settings`` key/value table (the
Helpdesk Settings dialog already reads and writes it), so there is one place
to change them. Read with :func:`get` / :func:`automation`; only an
administrator changes them (:func:`update`, audited).

* ``auto_close_days`` — a resolved ticket with no reply for this many days is
  closed (``lifecycle``); 0 turns it off.
* ``sla_pause_waiting`` — the resolution clock stops while a ticket waits on
  the student (``sla``).
* ``inbound_enabled`` / ``inbound_mode`` ('folder' or 'imap') /
  ``imap_host`` / ``imap_port`` / ``imap_user`` / ``imap_folder`` /
  ``support_address`` — e-mail into tickets (``email_in``). The mailbox
  password is never stored here: it comes from the ``SUPPORT_IMAP_PASSWORD``
  environment variable or ``var/secrets/support_imap_password``.
"""

from __future__ import annotations

import datetime
from typing import Any

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS helpdesk_system_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT,
    updated_at TEXT
)
'''

DEFAULTS: dict[str, Any] = {
    'auto_close_days': 7,
    'sla_pause_waiting': True,
    'inbound_enabled': False,
    'inbound_mode': 'folder',
    'imap_host': '',
    'imap_port': 993,
    'imap_user': '',
    'imap_folder': 'INBOX',
    'support_address': '',
}
INBOUND_MODES = ('folder', 'imap')
MAX_AUTO_CLOSE_DAYS = 90


def _coerce(key: str, value):
    default = DEFAULTS[key]
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')
    if isinstance(default, int):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default
    return str(value if value is not None else '').strip()


def ensure(conn) -> None:
    conn.execute(TABLE_SQL)


def get(key: str, conn=None):
    """One setting, typed like its default."""
    if key not in DEFAULTS:
        raise KeyError(key)
    return automation(conn)[key]


def automation(conn=None) -> dict:
    """Every automation setting (stored value, else the default)."""
    if conn is None:
        with store.reading() as own:
            return automation(own)
    values = dict(DEFAULTS)
    has = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                       "AND name = 'helpdesk_system_settings'").fetchone()
    if not has:
        return values
    marks = ", ".join("?" * len(DEFAULTS))
    for key, value in conn.execute(
            f"SELECT setting_key, setting_value FROM helpdesk_system_settings "  # nosec B608
            f"WHERE setting_key IN ({marks})", list(DEFAULTS)).fetchall():
        if value is not None:
            values[key] = _coerce(key, value)
    return values


def _validated(changes: dict) -> dict:
    out = {}
    for key, value in (changes or {}).items():
        if key not in DEFAULTS:
            raise ValueError(f"Unknown setting '{key}'")
        value = _coerce(key, value)
        if key == 'auto_close_days' and not 0 <= value <= MAX_AUTO_CLOSE_DAYS:
            raise ValueError(f"Auto-close must be between 0 (off) and {MAX_AUTO_CLOSE_DAYS} days")
        if key == 'imap_port' and not 1 <= value <= 65535:
            raise ValueError("The mailbox port must be between 1 and 65535")
        if key == 'inbound_mode' and value not in INBOUND_MODES:
            raise ValueError("The mailbox mode must be 'folder' or 'imap'")
        if key == 'support_address' and value and '@' not in value:
            raise ValueError("The support address must be an e-mail address")
        out[key] = value
    return out


def read(actor) -> dict:
    """The automation settings for an administrator to review or change."""
    user = _auth.require_auth(actor)
    if not _auth.is_admin(user):
        raise PermissionError("Only an administrator can see the support settings")
    return automation()


def update(actor, changes: dict) -> dict:
    """Change automation settings (administrators only); returns them all."""
    user = _auth.require_auth(actor)
    if not _auth.is_admin(user):
        raise PermissionError("Only an administrator can change the support settings")
    values = _validated(changes)
    if values.get('inbound_enabled') and \
            {**automation(), **values}.get('inbound_mode') == 'imap' and \
            not {**automation(), **values}.get('imap_host'):
        raise ValueError("Give the mailbox server before turning on e-mail into tickets")
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with store.writing() as conn:
        ensure(conn)
        old = automation(conn)
        for key, value in values.items():
            stored = str(value).lower() if isinstance(value, bool) else str(value)
            conn.execute("INSERT OR REPLACE INTO helpdesk_system_settings "
                         "(setting_key, setting_value, updated_at) VALUES (?, ?, ?)",
                         (key, stored, now))
        log_audit('support_settings', resource_type='support_settings', actor=user, conn=conn,
                  old_values={k: old[k] for k in values}, new_values=values)
        return automation(conn)


__all__ = ['DEFAULTS', 'INBOUND_MODES', 'MAX_AUTO_CLOSE_DAYS', 'automation', 'get', 'read', 'update',
           'ensure']

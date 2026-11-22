"""University e-mail delivery: the CLI for the outbox.

Reached from the Communication Hub ("E. E-mail delivery & preferences").
Everyone gets their own e-mail preferences; bulk senders get bulk sending;
e-mail administrators get the rest (status and mode, the outbox, failures,
suppressions, audit, settings, subject access and erasure, delivery and
retention runs). Granting roles and moving the SMTP password out of the
config file are for administrators only.

Rules: ``application/mail/outbox`` and ``email_admin``; delivery:
``infrastructure/email/outbox_delivery``.
"""

from __future__ import annotations

import json
from pathlib import Path

from education_system.systems.university.application.mail import (
    admin as email_admin,
    outbox as email_outbox,
)
from education_system.systems.university.infrastructure.email import outbox_delivery
from education_system.systems.university.infrastructure.email import permissions

# Swappable for scripted runs.
ask = input
say = print

BASE_CATEGORIES = ("all_bulk", "announcements", "news", "events", "alumni", "surveys")


def _conn():
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(None, row_factory=False)


def _run(fn, *args, **kwargs):
    """Run ``fn(conn, ...)`` in one transaction; report refusals."""
    conn = _conn()
    try:
        result = fn(conn, *args, **kwargs)
        conn.commit()
        return result
    except (PermissionError, ValueError) as exc:
        conn.rollback()
        say(f"  {exc}")
        return None
    finally:
        conn.close()


def _do(fn, *args, **kwargs) -> bool:
    """:func:`_run` for actions that return nothing: True when it worked."""
    ok = []
    _run(lambda conn: ok.append(fn(conn, *args, **kwargs)))
    return bool(ok)


def _pause():
    ask("\nPress Enter to continue...")


def _table(rows, columns, widths):
    if not rows:
        say("  (none)")
        return
    say("  " + "".join(f"{c[:w - 1]:<{w}}" for c, w in zip(columns, widths)))
    for row in rows:
        say("  " + "".join(f"{str(row.get(c) if row.get(c) is not None else '')[:w - 1]:<{w}}"
                           for c, w in zip(columns, widths)))


# ── status and mode ─────────────────────────────────────────────────────


def show_status(auth=None):
    st = outbox_delivery.status()
    summary = _run(email_admin.summary) or {}
    say("\n=== E-mail delivery ===")
    say(f"  Mode: {st['mode']}"
        + {"inbox_only": "  (nothing leaves the system; in-app inbox only)",
           "sandbox": f"  (written as .eml files to {st['sandbox_dir']})",
           "live": "  (sent over SMTP to real addresses)"}.get(st["mode"], ""))
    say(f"  Sender: {st['sender'] or '-'}   Server: {st['smtp_server']}")
    say(f"  Live sending ready: {'yes' if st['live_ready'] else 'no'}")
    for problem in st["live_problems"]:
        say(f"    - {problem}")
    if st["password_in_config_file"]:
        say("  WARNING: the SMTP password is stored in plain text in the config file.")
    say(f"  Background worker: {'running' if st['worker_running'] else 'not running'}")
    counts = summary.get("counts") or {}
    say("  Outbox: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "empty"))
    say(f"  Retention: {summary.get('retention_days', '-')} days; "
        f"max attempts {summary.get('max_attempts', '-')}")


def change_mode(auth):
    username, role = permissions.current(auth)
    say("\n  inbox_only – keep everything in the in-app inbox (nothing is sent)")
    say("  sandbox    – write each message to an .eml file (nothing is sent)")
    say("  live       – send over SMTP; REAL people at REAL addresses get the e-mail")
    mode = ask("New mode: ").strip().lower()
    if mode == "live":
        say("\n  Live mode sends queued and future e-mail from "
            f"{outbox_delivery.status()['sender'] or 'the configured sender'} to real addresses.")
        if ask("  Type LIVE to confirm: ").strip() != "LIVE":
            say("  Not changed.")
            return
    if _do(outbox_delivery.set_mode, username, role, mode):
        say(f"  Delivery mode is now {outbox_delivery.delivery_mode()}.")


# ── outbox ──────────────────────────────────────────────────────────────

_COLUMNS = ("message_id", "status", "to_address", "subject", "attempts", "created_at")
_WIDTHS = (8, 11, 30, 34, 5, 20)


def list_outbox(auth, status=None):
    if status is None:
        status = ask("Status (blank = all; queued/sent/failed/bounced/suppressed/stored): ")
    search = ask("Search address or subject (blank = none): ").strip()
    rows = _run(lambda c: email_outbox.messages(c, status=status.strip() or None,
                                                search=search or None, limit=50))
    _table(rows or [], _COLUMNS, _WIDTHS)


def failures(auth):
    for status in ("failed", "bounced"):
        say(f"\n  -- {status} --")
        rows = _run(lambda c, s=status: email_outbox.messages(c, status=s, limit=50))
        _table(rows or [], ("message_id", "to_address", "subject", "last_error"),
               (8, 30, 30, 40))


def message_detail(auth):
    raw = ask("Message id: ").strip()
    if not raw.isdigit():
        return
    msg = _run(email_outbox.message, int(raw))
    if not msg:
        say("  No such message.")
        return
    for key in ("message_id", "status", "mode", "kind", "category", "to_address", "cc",
                "subject", "attempts", "next_attempt_at", "last_error", "created_by",
                "created_at", "sent_at", "bulk_id"):
        say(f"  {key:<16}{msg.get(key) if msg.get(key) is not None else ''}")
    say("  --- body ---")
    say("  (removed by retention)" if msg.get("body_purged") else msg.get("body", "")[:2000])
    say("  --- attempts ---")
    _table(msg.get("attempt_log") or [], ("at", "mode", "outcome", "detail"), (20, 11, 10, 50))


def act_on_message(auth):
    username, role = permissions.current(auth)
    raw = ask("Message id: ").strip()
    if not raw.isdigit():
        return
    what = ask("r = retry, c = cancel, b = record a bounce: ").strip().lower()
    if what == "r":
        done = _do(email_outbox.retry, username, role, int(raw))
    elif what == "c":
        done = _do(email_outbox.cancel, username, role, int(raw))
    elif what == "b":
        detail = ask("Bounce message / reason: ").strip() or "returned"
        hard = ask("Permanent (address no longer works)? (y/n): ").strip().lower() == "y"
        done = _do(email_outbox.record_bounce, username, role, int(raw), detail, hard=hard)
    else:
        return
    if done:
        say("  Done.")


# ── suppressions ────────────────────────────────────────────────────────


def suppressions(auth):
    username, role = permissions.current(auth)
    _table(_run(email_outbox.suppressions) or [],
           ("address", "category", "reason", "added_by", "added_at"), (32, 14, 12, 16, 20))
    what = ask("\na = block an address, u = unblock, Enter = back: ").strip().lower()
    if what == "a":
        address = ask("Address: ").strip()
        if _do(email_outbox.add_suppression, username, role, address,
             ask("Why: ").strip()):
            say("  Saved.")
    elif what == "u":
        address = ask("Address: ").strip()
        category = ask("Category (Enter = * for a block/bounce): ").strip() or "*"
        if _do(email_outbox.remove_suppression, username, role, address, category):
            say("  Saved.")


# ── bulk ────────────────────────────────────────────────────────────────


def send_bulk(auth):
    username, role = permissions.current(auth)
    for key, label in email_admin.AUDIENCES.items():
        say(f"  {key:<11}{label}")
    audience = ask("Audience: ").strip()
    addresses = None
    if audience == "addresses":
        addresses = [a.strip() for a in ask("Addresses (comma separated): ").split(",")]
    category = ask("Category (e.g. announcements, news, events): ").strip() or "announcements"
    kind = "marketing" if ask("Is this marketing? (y/n): ").strip().lower() == "y" else "bulk"
    subject = ask("Subject: ").strip()
    say("Message (finish with a line containing only a full stop):")
    lines = []
    while (line := ask("")) != ".":
        lines.append(line)
    if ask(f"Send to '{audience}'? Unsubscribed people are skipped. (y/n): "
           ).strip().lower() != "y":
        say("  Cancelled.")
        return
    result = _run(email_admin.send_bulk, username, role, audience=audience, subject=subject,
                  body="\n".join(lines), category=category, mode=outbox_delivery.delivery_mode(),
                  kind=kind, addresses=addresses)
    if result:
        outbox_delivery.kick()
        say(f"  Bulk send {result['bulk_id']}: {result['recipients']} recipients, "
            f"{result['queued']} queued, {result['stored']} in-app only, "
            f"{result['suppressed']} skipped.")


def bulk_history(auth):
    _table(_run(email_admin.bulk_sends) or [],
           ("bulk_id", "sent_at", "sent_by", "audience", "category", "subject", "recipients",
            "suppressed"), (6, 20, 12, 11, 14, 28, 6, 6))


# ── administration ──────────────────────────────────────────────────────


def audit(auth):
    _table(_run(email_outbox.recent_audit, 50) or [],
           ("at", "actor", "entity", "entity_id", "action", "detail"), (20, 14, 12, 22, 14, 40))


def roles(auth):
    username, role = permissions.current(auth)
    _table(_run(email_outbox.roles) or [], ("username", "role", "granted_by", "granted_at"),
           (16, 14, 16, 20))
    what = ask("\ng = grant, r = revoke, Enter = back: ").strip().lower()
    if what in ("g", "r"):
        who = ask("Staff username: ").strip()
        which = ask("Role (bulk_sender / email_admin): ").strip()
        fn = email_outbox.grant if what == "g" else email_outbox.revoke
        if _do(fn, username, role, who, which):
            say("  Saved.")


def settings(auth):
    username, role = permissions.current(auth)
    for key in email_outbox.SETTINGS:
        say(f"  {key:<17}{_run(email_outbox.setting, key)}")
    key = ask("Setting to change (Enter = none): ").strip()
    if key:
        if _do(email_outbox.set_setting, username, role, key, ask("New value: ").strip()):
            say("  Saved.")


def export_person(auth):
    username, role = permissions.current(auth)
    address = ask("Address: ").strip()
    data = _run(email_admin.export, username, role, address)
    if data is None:
        return
    target = Path(ask("Save to (path to a .json file): ").strip()).expanduser()
    if not target.name:
        say("  Not saved.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    say(f"  Saved {sum(len(v) for v in data.values() if isinstance(v, list))} records "
        f"to {target}")


def erase_person(auth):
    username, role = permissions.current(auth)
    address = ask("Address whose e-mails to erase: ").strip()
    if ask(f"Type ERASE to delete every e-mail sent to {address}: ").strip() != "ERASE":
        say("  Not erased.")
        return
    done = _run(email_admin.erase, username, role, address)
    if done:
        say("  Erased: " + ", ".join(f"{k} {v}" for k, v in done.items()))


def deliver_now(auth):
    say(f"  {outbox_delivery.deliver_due()}")


def purge_now(auth):
    say(f"  Removed: {outbox_delivery.purge()}")


def move_password(auth):
    _username, role = permissions.current(auth)
    if not email_outbox.is_admin(role):
        say("  Only an administrator can do this.")
        return
    from education_system.platform.integrations.email import config as platform_config
    if not platform_config.password_in_config_file():
        say("  There is no plain-text password in the config file.")
        return
    say("  This moves the SMTP password into the system keyring (or the owner-only file "
        "var/secrets/smtp_password) and removes it from the config file.")
    if ask("  Type MOVE to continue: ").strip() != "MOVE":
        say("  Not moved.")
        return
    where = platform_config.move_password_out_of_config()
    say(f"  Moved to {where}." if where else "  Nothing to move.")


# ── own preferences ─────────────────────────────────────────────────────


def _categories():
    try:
        from education_system.systems.university.services.bus import email_bus
        return BASE_CATEGORIES + tuple(email_bus._TRACKED_EVENTS)
    except Exception:
        return BASE_CATEGORIES


def my_preferences(auth):
    username, _role = permissions.current(auth)
    if not username:
        say("  You must be logged in.")
        return
    prefs = _run(email_outbox.preferences, username) or {}
    cats = _categories()
    say("\n  Bulk and marketing e-mail you receive (transactional mail is always sent):")
    for n, cat in enumerate(cats, 1):
        label = "all bulk & marketing mail" if cat == "all_bulk" else cat
        say(f"  {n:>2}. [{'x' if prefs.get(cat, True) else ' '}] {label}")
    raw = ask("Number to switch on/off (Enter = back): ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(cats):
        cat = cats[int(raw) - 1]
        _run(email_outbox.set_preference, username, cat, not prefs.get(cat, True))
        say(f"  {cat}: {'on' if not prefs.get(cat, True) else 'off'}")


# ── menu ────────────────────────────────────────────────────────────────

# key: (label, handler, who) – who is 'all', 'bulk', 'email_admin' or 'admin'
ITEMS = {
    "1": ("Delivery status", show_status, "email_admin"),
    "2": ("Change delivery mode", change_mode, "email_admin"),
    "3": ("Outbox", list_outbox, "email_admin"),
    "4": ("Failed and bounced", failures, "email_admin"),
    "5": ("Message detail", message_detail, "email_admin"),
    "6": ("Retry / cancel / record bounce", act_on_message, "email_admin"),
    "7": ("Blocked addresses", suppressions, "email_admin"),
    "8": ("Send bulk e-mail", send_bulk, "bulk"),
    "9": ("Bulk send history", bulk_history, "bulk"),
    "10": ("Audit", audit, "email_admin"),
    "11": ("E-mail roles", roles, "admin"),
    "12": ("Settings", settings, "email_admin"),
    "13": ("Export a person's e-mails", export_person, "email_admin"),
    "14": ("Erase a person's e-mails", erase_person, "email_admin"),
    "15": ("Deliver due e-mail now", deliver_now, "email_admin"),
    "16": ("Run retention purge now", purge_now, "email_admin"),
    "17": ("Move SMTP password out of the config file", move_password, "admin"),
    "P": ("My e-mail preferences", my_preferences, "all"),
}


def _allowed(auth, who) -> bool:
    if who == "all":
        return True
    if who == "admin":
        return email_outbox.is_admin(permissions.current(auth)[1])
    if who == "bulk":
        return permissions.can_send_bulk(auth)
    return permissions.is_email_admin(auth)


def run(auth):
    """The e-mail delivery menu, showing only what the user may use."""
    while True:
        visible = {k: v for k, v in ITEMS.items() if _allowed(auth, v[2])}
        say("\n=== E-mail delivery & preferences ===")
        for key, (label, _fn, _who) in visible.items():
            say(f"  {key:>2}. {label}")
        say("   0. Back")
        choice = ask("Choice: ").strip().upper()
        if choice in ("0", ""):
            return
        if choice not in visible:
            say("  Not available.")
            continue
        visible[choice][1](auth)
        _pause()

"""University e-mail administration: bulk sends (who may send to whom,
with an audit), retention of message bodies, and a person's subject-access
export and erasure across the outbox, ``stored_emails`` and ``email_log``.

Bulk sends go through :func:`email_outbox.submit` one recipient at a
time, so suppressions, unsubscribes and preferences apply to each, and
each message carries an unsubscribe footer.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.application.mail import outbox

AUDIENCES = {
    "students": "All students",
    "staff": "All staff",
    "all_users": "Everyone with a university login",
    "addresses": "A list of addresses",
}


def can_send_bulk(conn, username, role, audience) -> bool:
    if outbox.is_admin(role):
        return True
    if audience == "all_users":
        return outbox.holds(conn, username, "email_admin")
    return (outbox.holds(conn, username, "bulk_sender")
            or outbox.holds(conn, username, "email_admin"))


def audience_recipients(conn, audience, addresses=None) -> list[tuple[str, str | None]]:
    """``[(address, username)]`` for an audience, without duplicates."""
    if audience == "addresses":
        found = []
        for raw in addresses or []:
            if not str(raw).strip():
                continue
            address = outbox.valid_address(raw)
            user = conn.execute("SELECT username FROM users WHERE LOWER(email) = LOWER(?) "
                                "LIMIT 1", (address,)).fetchone()
            found.append((address, user[0] if user else None))
    else:
        where = {"students": "LOWER(role) = 'student'",
                 "staff": "LOWER(role) <> 'student'",
                 "all_users": "1 = 1"}.get(audience)
        if where is None:
            raise ValueError(f"Unknown audience {audience!r}")
        found = conn.execute(
            f"SELECT email, username FROM users WHERE {where} "  # nosec B608 - fixed clauses
            "AND email IS NOT NULL AND TRIM(email) <> '' "
            "AND COALESCE(service_account, 0) = 0 ORDER BY username").fetchall()
    seen, result = set(), []
    for address, username in found:
        key = str(address).strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append((str(address).strip(), username))
    return result


def send_bulk(conn, actor, actor_role, *, audience, subject, body, category, mode,
              kind="bulk", addresses=None) -> dict:
    """Queue one message per recipient. Does not commit."""
    outbox.ensure(conn)
    outbox.require(can_send_bulk(conn, actor, actor_role, audience),
                   "You do not have permission to send bulk e-mail to this audience")
    if kind not in ("bulk", "marketing"):
        raise ValueError("A bulk send is bulk or marketing mail")
    category = str(category or "").strip().lower() or "announcements"
    if not str(body or "").strip():
        raise ValueError("The message is empty")
    recipients = audience_recipients(conn, audience, addresses)
    if not recipients:
        raise ValueError("Nobody in that audience has an e-mail address")
    cur = conn.execute("INSERT INTO email_bulk_sends (audience, category, subject, kind, sent_by, "
                       "sent_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (audience, category, subject, kind, actor, outbox.now()))
    bulk_id = cur.lastrowid
    counts = {"queued": 0, "stored": 0, "suppressed": 0}
    for address, username in recipients:
        result = outbox.submit(conn, address, subject, body, mode=mode, kind=kind,
                               category=category, to_ref=username, created_by=actor,
                               bulk_id=bulk_id)
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    conn.execute("UPDATE email_bulk_sends SET recipients = ?, suppressed = ? WHERE bulk_id = ?",
                 (len(recipients), counts["suppressed"], bulk_id))
    outbox.audit(conn, actor, "bulk", bulk_id, "sent",
                 {"audience": audience, "category": category, "subject": subject,
                  "recipients": len(recipients), **counts})
    return {"bulk_id": bulk_id, "recipients": len(recipients), **counts}


def bulk_sends(conn, limit=100) -> list[dict]:
    outbox.ensure(conn)
    cur = conn.execute("SELECT * FROM email_bulk_sends ORDER BY bulk_id DESC LIMIT ?",
                       (int(limit),))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


# ── retention ───────────────────────────────────────────────────────────


def _has(conn, table, column=None) -> bool:
    cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
    return bool(cols) and (column is None or column in cols)


def purge(conn, as_of=None) -> dict:
    """Remove message bodies older than ``retention_days``. Delivery
    records (who, when, status) are kept; suppressions are never purged."""
    outbox.ensure(conn)
    days = outbox.int_setting(conn, "retention_days")
    cutoff = outbox.now((as_of or datetime.now()) - timedelta(days=days))
    done = {"outbox": conn.execute(
        "UPDATE email_outbox SET body = '', cc = NULL, bcc = NULL, attachments = NULL, "
        "body_purged = 1 WHERE body_purged = 0 AND created_at < ? AND status NOT IN "
        "('queued', 'sending')", (cutoff,)).rowcount}
    done["stored_emails"] = conn.execute(
        "DELETE FROM stored_emails WHERE created_date < ?", (cutoff,)
    ).rowcount if _has(conn, "stored_emails") else 0
    if _has(conn, "email_log"):
        bodies = [c for c in ("message", "body", "template_vars") if _has(conn, "email_log", c)]
        sets = ", ".join(f'"{c}" = NULL' for c in bodies)
        done["email_log"] = conn.execute(
            f"UPDATE email_log SET {sets} WHERE sent_date < ? AND "  # nosec B608 - known columns
            f"({' OR '.join(f'{c} IS NOT NULL' for c in bodies)})", (cutoff,)).rowcount
    done["tokens"] = conn.execute("DELETE FROM email_unsubscribe_tokens WHERE created_at < ? "
                                  "AND used_at IS NULL", (cutoff,)).rowcount
    if any(done.values()):
        outbox.audit(conn, "retention", "retention", None, "purged",
                     {"cutoff": cutoff, **done})
    return done


# ── subject access and erasure ──────────────────────────────────────────


def _rows(conn, table, column, address) -> list[dict]:
    if not _has(conn, table, column):
        return []
    cur = conn.execute(f'SELECT * FROM "{table}" WHERE "{column}" = ? '  # nosec B608
                       "COLLATE NOCASE", (address,))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _require_records_access(conn, actor, actor_role) -> None:
    outbox.require(outbox.is_admin(actor_role) or outbox.holds(conn, actor, "email_admin"),
                   "Only an e-mail administrator can do this")


def export(conn, actor, actor_role, address) -> dict:
    """Everything the university holds about e-mail sent to ``address``."""
    _require_records_access(conn, actor, actor_role)
    outbox.ensure(conn)
    address = outbox.valid_address(address)
    data = {
        "address": address,
        "outbox": _rows(conn, "email_outbox", "to_address", address),
        "stored_emails": _rows(conn, "stored_emails", "recipient_email", address),
        "email_log": _rows(conn, "email_log", "recipient", address),
        "suppressions": _rows(conn, "email_suppressions", "address", address),
    }
    outbox.audit(conn, actor, "person", address, "exported",
                 {k: len(v) for k, v in data.items() if isinstance(v, list)})
    return data


def erase(conn, actor, actor_role, address) -> dict:
    """Delete the e-mails sent to ``address``. Suppressions stay, so an
    erased person who asked not to be mailed is still not mailed."""
    _require_records_access(conn, actor, actor_role)
    outbox.ensure(conn)
    address = outbox.valid_address(address)
    done = {"outbox": conn.execute("DELETE FROM email_outbox WHERE to_address = ?",
                                   (address,)).rowcount}
    if _has(conn, "stored_emails"):
        done["stored_emails"] = conn.execute(
            "DELETE FROM stored_emails WHERE recipient_email = ? COLLATE NOCASE",
            (address,)).rowcount
    if _has(conn, "email_log"):
        done["email_log"] = conn.execute(
            "DELETE FROM email_log WHERE recipient = ? COLLATE NOCASE", (address,)).rowcount
    done["tokens"] = conn.execute("DELETE FROM email_unsubscribe_tokens WHERE address = ?",
                                  (address,)).rowcount
    outbox.audit(conn, actor, "person", "(erased)", "erased", done)
    return done


def summary(conn) -> dict:
    outbox.ensure(conn)
    counts = outbox.status_counts(conn)
    return {
        "counts": counts,
        "waiting": counts.get("queued", 0) + counts.get("sending", 0),
        "problems": counts.get("failed", 0) + counts.get("bounced", 0),
        "suppressed_addresses": conn.execute(
            "SELECT COUNT(DISTINCT address) FROM email_suppressions").fetchone()[0],
        "retention_days": outbox.int_setting(conn, "retention_days"),
        "max_attempts": outbox.int_setting(conn, "max_attempts"),
    }

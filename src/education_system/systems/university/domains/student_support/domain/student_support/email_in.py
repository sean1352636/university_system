"""E-mail into support tickets.

The support mailbox is read on a schedule (:func:`poll`, from the support
jobs worker, when the ``inbound_enabled`` setting is on):

* ``folder`` mode reads ``.eml`` files dropped into
  ``paths.UNIVERSITY_SUPPORT_INBOUND_DIR`` (a mail server's delivery folder,
  or files saved by hand);
* ``imap`` mode reads unseen messages from the mailbox in the settings
  (``imap_host`` / ``imap_port`` / ``imap_user`` / ``imap_folder``, over
  TLS). The password is never stored in the database: it comes from the
  ``SUPPORT_IMAP_PASSWORD`` environment variable or
  ``paths.UNIVERSITY_SUPPORT_IMAP_PASSWORD_FILE``.

Each message (:func:`process_message`) is recorded once in
``support_inbound_mail`` (by Message-ID) and then:

* **ignored** — automatic mail (auto-replies, bounces, lists, our own
  address), so two robots never answer each other;
* **quarantined** — the sender failed SPF/DMARC, or the address matches no
  one (or more than one person), or it replies to a ticket the sender did not
  raise, or it comes from staff (staff reply in the Helpdesk, where internal
  notes and confidentiality are handled). Staff review these
  (:func:`list_quarantine`, :func:`read_quarantined`) and either raise a
  ticket for the right person (:func:`accept_quarantined`) or discard it.
  Crisis language in a quarantined message alerts the wellbeing leads and the
  duty officers at once;
* **processed** — a message naming one of the sender's tickets ("ticket #12"
  in the subject, as every support e-mail has) becomes their reply on it (a
  closed ticket gets a new follow-up ticket instead); any other message
  becomes a new ticket from them (channel 'email').

Replies and tickets go through ``service`` as the sender, so crisis
detection, routing, SLAs, sealing and notices are the same as on screen. A
sender whose message used crisis language is e-mailed the crisis contacts
straight away. Quoted earlier messages are stripped; attachments go through
the usual checks (one that is refused is left off and noted).

Raw messages are kept only while they wait in quarantine (deleted when
reviewed, and after :data:`QUARANTINE_DAYS` by :func:`purge_old`).
"""

from __future__ import annotations

import datetime
import hashlib
import html
import logging
import os
import re
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from pathlib import Path
from typing import Iterable, Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    notify,
    safety,
    settings,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

logger = logging.getLogger(__name__)

BATCH = 50
QUARANTINE_DAYS = 30
MAX_ATTACHMENTS = 5
TICKET_REF = re.compile(r'ticket\s*#\s*(\d+)', re.IGNORECASE)
_AUTO_SENDERS = re.compile(r'^(mailer-daemon|postmaster|no-?reply|do-?not-?reply|bounce)',
                           re.IGNORECASE)
_QUOTE_START = (
    re.compile(r'^\s*On .{3,200}wrote:\s*$'),
    re.compile(r'^\s*-{2,}\s*Original Message\s*-{2,}', re.IGNORECASE),
    re.compile(r'^\s*_{10,}\s*$'),
    re.compile(r'^\s*Sent from my ', re.IGNORECASE),
)
# An Outlook-style quoted header block; only after some text of the reply.
_QUOTED_HEADER = re.compile(r'^\s*From:\s.+$')


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _paths():
    import education_system.paths as paths
    return paths


def inbound_dir() -> Path:
    return Path(_paths().UNIVERSITY_SUPPORT_INBOUND_DIR)


def quarantine_dir() -> Path:
    return inbound_dir() / 'quarantine'


# ── reading a message ───────────────────────────────────────────────────


def _parse(raw: bytes):
    return BytesParser(policy=policy.default).parsebytes(raw)


def message_key(msg, raw: bytes) -> str:
    mid = str(msg.get('Message-ID') or '').strip()
    return mid[:500] if mid else 'sha256:' + hashlib.sha256(raw).hexdigest()


def _html_to_text(text: str) -> str:
    text = re.sub(r'(?is)<(script|style).*?</\1>', ' ', text)
    text = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</li>', '\n', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return html.unescape(text)


def body_text(msg) -> str:
    """The message's own text (plain text preferred), without quoted history."""
    part = msg.get_body(preferencelist=('plain', 'html'))
    if part is None:
        return ''
    try:
        text = part.get_content()
    except (LookupError, ValueError):
        text = (part.get_payload(decode=True) or b'').decode('utf-8', 'replace')
    if part.get_content_type() == 'text/html':
        text = _html_to_text(text)
    return strip_quoted(text)


def strip_quoted(text: str) -> str:
    """Cut a reply at the quoted earlier message and drop '>' lines."""
    kept = []
    for line in str(text or '').replace('\r\n', '\n').split('\n'):
        if any(p.match(line) for p in _QUOTE_START):
            break
        if kept and any(k.strip() for k in kept) and _QUOTED_HEADER.match(line):
            break
        if line.rstrip() == '--':          # signature separator
            break
        if line.lstrip().startswith('>'):
            continue
        kept.append(line.rstrip())
    out = '\n'.join(kept).strip()
    return re.sub(r'\n{3,}', '\n\n', out)


def attachments_of(msg) -> list:
    out = []
    for part in msg.iter_attachments():
        name = part.get_filename()
        if not name:
            continue
        data = part.get_payload(decode=True) or b''
        out.append({'filename': os.path.basename(name), 'data': data,
                    'mime_type': part.get_content_type()})
        if len(out) >= MAX_ATTACHMENTS:
            break
    return out


def is_automatic(msg, from_address: str, support_address: str = '') -> Optional[str]:
    """Why this is automatic mail to ignore, or None."""
    auto = str(msg.get('Auto-Submitted') or '').strip().lower()
    if auto and auto != 'no':
        return f"auto-submitted ({auto})"
    if str(msg.get('Precedence') or '').strip().lower() in ('bulk', 'list', 'junk', 'auto_reply'):
        return "bulk or list mail"
    if msg.get('List-Id') or msg.get('List-Unsubscribe'):
        return "mailing list"
    if msg.get('X-Autoreply') or msg.get('X-Autorespond'):
        return "auto-reply"
    if str(msg.get('Content-Type') or '').lower().startswith('multipart/report'):
        return "delivery report"
    local = from_address.split('@', 1)[0]
    if not from_address or _AUTO_SENDERS.match(local):
        return "automatic sender"
    if support_address and from_address == support_address.lower():
        return "our own address"
    return None


def failed_authentication(msg) -> Optional[str]:
    """'spf=fail' / 'dmarc=fail' recorded by the receiving server, if any."""
    for header in msg.get_all('Authentication-Results') or []:
        text = str(header).lower()
        for check in ('dmarc', 'spf'):
            if re.search(rf'\b{check}=(fail|softfail)\b', text):
                return f"{check.upper()} failed"
    return None


# ── who sent it ─────────────────────────────────────────────────────────


def find_people(conn, address: str) -> list:
    """Accounts with this e-mail: ``[{'username', 'role'}]`` (users, then a
    student record's address)."""
    address = str(address or '').strip().lower()
    if not address:
        return []
    found = {}
    for row in conn.execute("SELECT username, role FROM users WHERE lower(email) = ? "
                            "AND COALESCE(is_active, 1) = 1"
                            if 'is_active' in _cols(conn, 'users') else
                            "SELECT username, role FROM users WHERE lower(email) = ?",
                            (address,)).fetchall():
        found[row['username']] = {'username': row['username'], 'role': row['role']}
    if not found and 'students' in _tables(conn):
        for row in conn.execute(
                "SELECT u.username, u.role FROM students s JOIN users u ON u.student_id = s.student_id "
                "WHERE lower(s.email_address) = ?", (address,)).fetchall():
            found[row['username']] = {'username': row['username'], 'role': row['role']}
    return list(found.values())


def _tables(conn) -> set:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _cols(conn, table) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


# ── the log ─────────────────────────────────────────────────────────────


def _seen(conn, key) -> bool:
    return conn.execute("SELECT 1 FROM support_inbound_mail WHERE message_key = ?",
                        (key,)).fetchone() is not None


def _record(key, from_address, subject, status, reason=None, *, ticket_id=None,
            response_id=None, username=None, raw_path=None) -> Optional[int]:
    with store.writing() as conn:
        if _seen(conn, key):
            return None
        cur = conn.execute(
            "INSERT INTO support_inbound_mail (message_key, from_address, subject, received_at, "
            "status, reason, ticket_id, response_id, username, raw_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, from_address, (subject or '')[:300], _now(), status, reason, ticket_id,
             response_id, username, raw_path))
        return cur.lastrowid


def _keep_raw(raw: bytes, key: str) -> str:
    folder = quarantine_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (hashlib.sha256(key.encode()).hexdigest()[:32] + '.eml')
    path.write_bytes(raw)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return str(path)


def _crisis_alert(mail_id, from_address) -> None:
    """Crisis language in a message we could not match: the wellbeing leads
    and duty officers are told now (no text in the notice)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
    )
    with store.reading() as conn:
        names = sorted(set(routing.team_leads(safety.TEAM, conn)) | set(routing.duty_officers(conn)))
    notices = [notify.Notice(name, f"Urgent: unmatched support e-mail #{mail_id}",
                             f"An e-mail to the support mailbox from {from_address} could not be "
                             "matched to a person and used crisis language. Review it now in "
                             f"the support e-mail quarantine (#{mail_id}).", 'inbound_crisis')
               for name in names]
    if not notices:
        logger.error("Unmatched support e-mail #%s used crisis language and nobody is on the "
                     "wellbeing lead or duty rota to tell", mail_id)
        return
    notify.announce(notices)


def _quarantine(raw, key, from_address, subject, reason, text) -> dict:
    crisis = safety.detect(subject, text)
    if crisis:
        reason += "; crisis language"
    mail_id = _record(key, from_address, subject, 'quarantined', reason,
                      raw_path=_keep_raw(raw, key))
    if crisis and mail_id:
        _crisis_alert(mail_id, from_address)
    return {'status': 'quarantined', 'reason': reason, 'mail_id': mail_id}


def _crisis_mail(address, ticket_id, support) -> None:
    """E-mail the crisis contacts to someone who wrote in crisis language."""
    if not support or not address:
        return
    body = ("Thank you for contacting us. If you are in danger or worried about your safety, "
            "please get help now:\n\n" + support.get('message', '') +
            f"\n\nYour message has been passed to our wellbeing team (ticket #{ticket_id}).")
    notify.send_mails([notify._Mail('send_email', address, f"support:{ticket_id}:crisis",
                                    f"Support ticket #{ticket_id}: help is available", body)])


# ── processing ──────────────────────────────────────────────────────────


def _new_ticket(actor, person, subject, text, files, *, follow_up=None):
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    from education_system.systems.university.domains.student_support.domain.student_support.automation.sentiment_analysis import (
        _suggest_category,
    )
    subject = (subject or '').strip() or '(no subject)'
    description = text or '(The e-mail had no text.)'
    if follow_up:
        description = f"Follow-up to closed ticket #{follow_up}.\n\n{description}"
    student = str(person.get('role') or '').lower() == 'student'
    category = (_suggest_category(f"{subject} {description}") or 'General') if student else 'General'
    return service.submit_ticket(
        actor, subject=subject[:service.MAX_SUBJECT], description=description[:service.MAX_DESCRIPTION],
        category=category, priority='Medium' if student else 'medium',
        source='support' if student else 'helpdesk', channel='email', attachments=files)


def _with_files(call, files):
    """Run ``call(files)``; an attachment refused by the checks is left off
    (returns ``(result, note)``)."""
    try:
        return call(files), None
    except ValueError as exc:
        if files and str(exc).startswith('Attachment not accepted'):
            return call([]), str(exc)
        raise


def process_message(raw: bytes) -> dict:
    """Turn one raw e-mail into a reply or a ticket (see the module notes).
    Returns ``{'status', 'reason', 'ticket_id', 'response_id', 'mail_id'}``;
    status 'duplicate' when this message was seen before."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
        service,
    )
    msg = _parse(raw)
    key = message_key(msg, raw)
    from_address = parseaddr(str(msg.get('From') or ''))[1].strip().lower()
    subject = str(msg.get('Subject') or '').strip()
    with store.reading() as conn:
        if _seen(conn, key):
            return {'status': 'duplicate', 'reason': None, 'ticket_id': None,
                    'response_id': None, 'mail_id': None}
        cfg = settings.automation(conn)
    auto = is_automatic(msg, from_address, cfg.get('support_address') or '')
    if auto:
        mail_id = _record(key, from_address, subject, 'ignored', auto)
        return {'status': 'ignored', 'reason': auto, 'ticket_id': None, 'response_id': None,
                'mail_id': mail_id}
    text = body_text(msg)
    failed = failed_authentication(msg)
    if failed:
        return _quarantine(raw, key, from_address, subject, f"sender {failed}", text)
    with store.reading() as conn:
        people = find_people(conn, from_address)
    if not people:
        return _quarantine(raw, key, from_address, subject, "address matches no one", text)
    if len(people) > 1:
        return _quarantine(raw, key, from_address, subject,
                           "address matches more than one person", text)
    person = people[0]
    actor = {'username': person['username'], 'role': str(person['role'] or '').lower()}
    files = attachments_of(msg)
    match = TICKET_REF.search(subject)
    note = None
    try:
        if match:
            tid = int(match.group(1))
            with store.reading() as conn:
                ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                                      (tid,)).fetchone()
                owner = ticket is not None and _auth.owns_ticket(
                    _auth.current_requester(actor, conn), ticket)
            if not owner:
                if ticket is not None and _auth.is_case_worker(actor):
                    reason = (f"staff reply to ticket #{tid} by e-mail (reply in the Helpdesk "
                              "instead)")
                else:
                    reason = f"sender did not raise ticket #{tid}"
                return _quarantine(raw, key, from_address, subject, reason, text)
            if schema.normalize_status(ticket['status'], default='open') == 'closed':
                result, note = _with_files(
                    lambda f: _new_ticket(actor, person, subject, text, f, follow_up=tid), files)
                outcome = {'ticket_id': result['ticket_id'], 'response_id': None}
            else:
                result, note = _with_files(
                    lambda f: service.post_response(actor, tid, text or '(The e-mail had no text.)',
                                                    attachments=f), files)
                outcome = {'ticket_id': tid, 'response_id': result['response_id']}
        else:
            result, note = _with_files(
                lambda f: _new_ticket(actor, person, subject, text, f), files)
            outcome = {'ticket_id': result['ticket_id'], 'response_id': None}
    except (PermissionError, ValueError) as exc:
        return _quarantine(raw, key, from_address, subject, f"not accepted: {exc}", text)
    reason = f"attachment left off: {note}" if note else None
    mail_id = _record(key, from_address, subject, 'processed', reason,
                      ticket_id=outcome['ticket_id'], response_id=outcome['response_id'],
                      username=person['username'])
    if note:
        with store.writing() as conn:
            service._add_auto_note(conn, outcome['ticket_id'],
                                   f"An attachment on the e-mail was not accepted: {note}")
    if result.get('crisis'):
        _crisis_mail(from_address, outcome['ticket_id'], result['crisis'])
    return {'status': 'processed', 'reason': reason, **outcome, 'mail_id': mail_id}


# ── the mailbox ─────────────────────────────────────────────────────────


def _imap_password() -> Optional[str]:
    value = os.environ.get('SUPPORT_IMAP_PASSWORD')
    if value:
        return value
    path = Path(_paths().UNIVERSITY_SUPPORT_IMAP_PASSWORD_FILE)
    try:
        return path.read_text(encoding='utf-8').strip() or None
    except OSError:
        return None


def _poll_folder() -> list:
    folder = inbound_dir()
    if not folder.is_dir():
        return []
    results = []
    for path in sorted(folder.glob('*.eml'))[:BATCH]:
        try:
            raw = path.read_bytes()
        except OSError:
            logger.warning("Could not read %s", path, exc_info=True)
            continue
        try:
            results.append(process_message(raw))
        except Exception:
            logger.exception("Support e-mail %s could not be processed", path.name)
            failed = folder / 'failed'
            failed.mkdir(exist_ok=True)
            path.replace(failed / path.name)
            continue
        path.unlink(missing_ok=True)
    return results


def _poll_imap(cfg) -> list:
    import imaplib
    import ssl
    password = _imap_password()
    if not cfg.get('imap_host') or not cfg.get('imap_user') or not password:
        logger.warning("Support mailbox not read: server, user or password missing")
        return []
    results = []
    with imaplib.IMAP4_SSL(cfg['imap_host'], int(cfg.get('imap_port') or 993),
                           ssl_context=ssl.create_default_context(), timeout=30) as box:
        box.login(cfg['imap_user'], password)
        box.select(cfg.get('imap_folder') or 'INBOX')
        _typ, data = box.search(None, 'UNSEEN')
        for num in (data[0].split() if data and data[0] else [])[:BATCH]:
            _typ, parts = box.fetch(num, '(BODY.PEEK[])')
            raw = next((p[1] for p in parts or [] if isinstance(p, tuple)), None)
            if raw is None:
                continue
            try:
                results.append(process_message(raw))
            except Exception:
                # Left unseen: tried again next time (the log stops a repeat).
                logger.exception("Support e-mail %s could not be processed", num)
                continue
            box.store(num, '+FLAGS', '\\Seen')
    return results


def poll() -> dict:
    """Read the support mailbox once (when e-mail into tickets is on).
    Returns ``{'enabled', 'mode', 'counts'}``."""
    cfg = settings.automation()
    if not cfg['inbound_enabled']:
        return {'enabled': False, 'mode': cfg['inbound_mode'], 'counts': {}}
    results = _poll_imap(cfg) if cfg['inbound_mode'] == 'imap' else _poll_folder()
    counts: dict = {}
    for r in results:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    if results:
        logger.info("Support mailbox read: %s", counts)
    return {'enabled': True, 'mode': cfg['inbound_mode'], 'counts': counts}


# ── quarantine review ───────────────────────────────────────────────────


def _require_reviewer(actor) -> dict:
    user = _auth.require_auth(actor)
    if not _auth.is_support_staff(user):
        raise PermissionError("Only support staff can review support e-mail")
    return user


def list_mail(actor, status='quarantined', limit=200) -> list:
    """The inbound e-mail log (default: what waits for review), newest first."""
    _require_reviewer(actor)
    with store.reading() as conn:
        sql, params = "SELECT mail_id, from_address, subject, received_at, status, reason, " \
                      "ticket_id, username, reviewed_by, reviewed_at FROM support_inbound_mail", []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        return [dict(r) for r in conn.execute(sql + " ORDER BY mail_id DESC LIMIT ?",
                                              params + [int(limit)]).fetchall()]


def list_quarantine(actor) -> list:
    return list_mail(actor, 'quarantined')


def _quarantined(conn, mail_id):
    row = conn.execute("SELECT * FROM support_inbound_mail WHERE mail_id = ?",
                       (int(mail_id),)).fetchone()
    if row is None:
        raise ValueError(f"E-mail #{mail_id} was not found")
    if row['status'] != 'quarantined':
        raise ValueError(f"E-mail #{mail_id} has already been dealt with ({row['status']})")
    return row


def _raw_of(row) -> bytes:
    path = Path(row['raw_path'] or '')
    try:
        path.resolve().relative_to(quarantine_dir().resolve())
    except ValueError:
        raise PermissionError("That message is stored outside the quarantine folder") from None
    if not path.is_file():
        raise FileNotFoundError(f"The message for e-mail #{row['mail_id']} is no longer kept")
    return path.read_bytes()


def read_quarantined(actor, mail_id) -> dict:
    """A quarantined message: ``{'mail_id', 'from', 'to', 'subject', 'date',
    'text', 'attachments', 'reason', 'suggested'}`` (the reading is audited)."""
    user = _require_reviewer(actor)
    with store.reading() as conn:
        row = _quarantined(conn, mail_id)
        msg = _parse(_raw_of(row))
        people = find_people(conn, row['from_address'])
    log_audit('read_inbound_mail', resource_type='support_inbound_mail',
              resource_id=row['mail_id'], actor=user)
    return {'mail_id': row['mail_id'], 'from': str(msg.get('From') or ''),
            'to': ", ".join(a for _n, a in getaddresses(msg.get_all('To') or [])),
            'subject': str(msg.get('Subject') or ''), 'date': str(msg.get('Date') or ''),
            'text': body_text(msg), 'attachments': [a['filename'] for a in attachments_of(msg)],
            'reason': row['reason'], 'suggested': [p['username'] for p in people]}


def _close_review(conn, row, status, user, reason=None, ticket_id=None) -> None:
    path = row['raw_path']
    conn.execute("UPDATE support_inbound_mail SET status = ?, reviewed_by = ?, reviewed_at = ?, "
                 "reason = COALESCE(?, reason), ticket_id = COALESCE(?, ticket_id), "
                 "raw_path = NULL WHERE mail_id = ?",
                 (status, user['username'], _now(), reason, ticket_id, row['mail_id']))
    log_audit(f'{status}_inbound_mail', resource_type='support_inbound_mail',
              resource_id=row['mail_id'], actor=user, conn=conn,
              details={'ticket_id': ticket_id, 'reason': reason})
    if path:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete %s", path, exc_info=True)


def accept_quarantined(actor, mail_id, requester) -> dict:
    """Raise a ticket for ``requester`` (a username or student number) from a
    quarantined message, as the reviewing member of staff. Returns
    :func:`service.submit_ticket`'s result."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    user = _require_reviewer(actor)
    with store.reading() as conn:
        row = _quarantined(conn, mail_id)
        msg = _parse(_raw_of(row))
        username, student_id, _uid = service._resolve_requester(conn, requester)
        account = conn.execute("SELECT role FROM users WHERE username = ?",
                               (username,)).fetchone() if username else None
    student = student_id is not None or (account is not None and account['role'] == 'student')
    subject = str(msg.get('Subject') or '').strip() or '(no subject)'
    text = body_text(msg) or '(The e-mail had no text.)'
    description = f"Received by e-mail from {row['from_address']}.\n\n{text}"
    files = attachments_of(msg)

    def submit(f):
        return service.submit_ticket(
            user, subject=subject[:service.MAX_SUBJECT],
            description=description[:service.MAX_DESCRIPTION], category='General',
            priority='Medium' if student else 'medium',
            source='support' if student else 'helpdesk', channel='email',
            requester=username or student_id, attachments=f)
    result, note = _with_files(submit, files)
    with store.writing() as conn:
        _close_review(conn, _quarantined(conn, mail_id), 'accepted', user,
                      ticket_id=result['ticket_id'])
        if note:
            service._add_auto_note(conn, result['ticket_id'],
                                   f"An attachment on the e-mail was not accepted: {note}")
    return result


def discard_quarantined(actor, mail_id, reason) -> bool:
    """Discard a quarantined message (its stored copy is deleted)."""
    user = _require_reviewer(actor)
    reason = str(reason or '').strip()
    if len(reason) < 3:
        raise ValueError("Say why the e-mail is being discarded")
    with store.writing() as conn:
        _close_review(conn, _quarantined(conn, mail_id), 'discarded', user, reason=reason[:300])
    return True


def purge_old(days: int = QUARANTINE_DAYS, now=None) -> int:
    """Discard quarantined messages older than ``days`` (their stored copies
    deleted); returns how many."""
    now = now or datetime.datetime.now()
    cutoff = (now - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    system = {'username': 'system', 'role': 'system'}
    with store.writing() as conn:
        rows = conn.execute("SELECT * FROM support_inbound_mail WHERE status = 'quarantined' "
                            "AND received_at < ?", (cutoff,)).fetchall()
        for row in rows:
            _close_review(conn, row, 'discarded', system,
                          reason=f"not reviewed within {days} days")
    return len(rows)


__all__ = [
    'TICKET_REF', 'QUARANTINE_DAYS', 'process_message', 'poll', 'body_text', 'strip_quoted',
    'is_automatic', 'failed_authentication', 'find_people', 'list_mail', 'list_quarantine',
    'read_quarantined', 'accept_quarantined', 'discard_quarantined', 'purge_old',
    'inbound_dir', 'quarantine_dir',
]

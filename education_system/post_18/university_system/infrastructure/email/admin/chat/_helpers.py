"""Module-level helpers for the chat package."""

from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


# ---- safety / encryption helpers (module level) -----------------------------

# Default starter wordlist; a deployment-grade list should be loaded from config.
_DEFAULT_FILTER_WORDS = (
    # Mild markers used as a smoke-test wordlist; severity='flag' means the
    # message still goes through but a safeguarding row is recorded.
    ('badword', 'flag'),
    ('killme', 'flag'),
    ('selfharm', 'flag'),
)

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    _FERNET_AVAILABLE = True
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    _FERNET_AVAILABLE = False


def _scan_filter_words(cursor, content):
    """Return (highest_severity, [matched_words]) for a piece of content.
    Severity is 'block' if any matched word is flagged that way, else 'flag'."""
    if not content:
        return None, []
    lowered = content.lower()
    try:
        cursor.execute('SELECT word, severity FROM chat_filter_words')
        rows = list(cursor.fetchall())
    except Exception:
        rows = []
    if not rows:
        rows = [(w, s) for (w, s) in _DEFAULT_FILTER_WORDS]
    matches, severity = [], None
    for word, sev in rows:
        if word and word.lower() in lowered:
            matches.append(word)
            if sev == 'block':
                severity = 'block'
            elif severity is None:
                severity = sev or 'flag'
    return severity, matches


def _ensure_room_key(cursor, room_id, now):
    """Fetch or create a Fernet key for a room. Returns base64 key or None."""
    if not _FERNET_AVAILABLE:
        return None
    cursor.execute('SELECT key_b64 FROM chat_room_keys WHERE room_id = ?', (room_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    new_key = Fernet.generate_key().decode('ascii')
    cursor.execute(
        'INSERT INTO chat_room_keys (room_id, key_b64, created_at) VALUES (?, ?, ?)',
        (room_id, new_key, now),
    )
    return new_key


def _encrypt_with_key(plaintext, key_b64):
    if not _FERNET_AVAILABLE or not key_b64:
        return None
    try:
        token = Fernet(key_b64.encode('ascii')).encrypt(plaintext.encode('utf-8'))
        return 'enc:v1:' + token.decode('ascii')
    except Exception:
        return None


def _decrypt_with_key(ciphertext, key_b64):
    if not ciphertext or not isinstance(ciphertext, str):
        return ciphertext
    if not ciphertext.startswith('enc:v1:'):
        return ciphertext
    if not _FERNET_AVAILABLE or not key_b64:
        return '[encrypted message — key unavailable]'
    try:
        token = ciphertext[len('enc:v1:'):].encode('ascii')
        return Fernet(key_b64.encode('ascii')).decrypt(token).decode('utf-8')
    except (InvalidToken, Exception):
        return '[encrypted message — could not decrypt]'


def _maybe_decrypt(cursor, room_id_for_key_lookup, msg_dict):
    """Decrypt msg_dict['content'] in place when the encrypted flag is on the
    underlying row. Caller passes a cursor so we can fetch the room key once
    per query if needed (cached in a closure-local dict by the caller)."""
    # No-op here — the GUI layer doesn't have direct access; we decrypt in
    # _format_message_row when row data carries an is_encrypted bit. This
    # helper is kept as a placeholder for any future per-row strategies.
    return msg_dict


def _format_message_row(row, full_name):
    """Translate a SELECT row from the canonical chat_messages query into the
    dict shape consumed by the GUI. Row layout (17 cols):

    id, content, sent_at, username, first, last, sender_id,
    edited_at, is_deleted, reply_to_id, pinned_at,
    att_path, att_name, att_mime, att_size,
    reply_content, reply_username, reply_is_deleted
    """
    is_deleted = bool(row[8])
    content = row[1] if not is_deleted else ''
    msg = {
        'id': row[0],
        'content': content,
        'sent_at': row[2],
        'sender': row[3],
        'sender_name': full_name or row[3],
        'sender_id': row[6],
        'edited_at': row[7],
        'is_deleted': is_deleted,
        'reply_to_id': row[9],
        'pinned_at': row[10],
        'attachment_path': row[11],
        'attachment_name': row[12],
        'attachment_mime': row[13],
        'attachment_size': row[14],
    }
    if row[9] and row[15] is not None:
        msg['reply_preview'] = {
            'sender': row[16],
            'content': '' if row[17] else (row[15] or ''),
            'is_deleted': bool(row[17]),
        }
    # Sender role (column 18) is optional — only present in extended queries.
    if len(row) > 18:
        msg['sender_role'] = row[18]
    # Encryption (cols 19/20) — decrypt content lazily for display.
    if len(row) > 20 and row[19]:
        decrypted = _decrypt_with_key(msg.get('content'), row[20])
        if decrypted is not None:
            msg['content'] = decrypted
        msg['is_encrypted'] = True
    return msg



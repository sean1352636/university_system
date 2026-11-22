"""
File attachment handling for Student Support.

Attachments are stored in two steps so no file is written inside a database
transaction: :func:`prepare_attachments` validates the uploads and picks
their paths (before the transaction), :func:`insert_attachment_rows` records
them (inside it) and :func:`write_attachment_files` writes the files once the
transaction has committed, removing the rows of any file that could not be
written.
"""

import datetime
import hashlib
import logging
import os
import secrets
from pathlib import Path

from education_system.systems.university.domains.student_support.domain.student_support.config import (
    FileType, SupportConfig
)
from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod

logger = logging.getLogger(__name__)

config = SupportConfig()


def upload_root() -> Path:
    """Where ticket attachments live (read at call time so it can be repointed)."""
    import education_system.paths as paths
    return Path(paths.UNIVERSITY_UPLOAD_DIR) / 'tickets'


def _validate_file(attachment, cfg=None):
    """None when the upload is acceptable, else the reason it is not."""
    cfg = cfg or config
    name = str(attachment.get('filename') or '').strip()
    data = attachment.get('data')
    if not name or data is None:
        return "an attachment needs a file name and content"
    if len(data) > cfg.max_file_size:
        return (f"'{name}' is larger than the {cfg.max_file_size // (1024 * 1024)} MB limit")
    ext = os.path.splitext(name)[1].lower()
    if ext not in cfg.allowed_file_types:
        return f"'{name}': files of type '{ext or 'none'}' are not accepted"
    return None


def _generate_secure_filename(filename):
    """A stored file name that keeps only the extension of the upload."""
    _name, ext = os.path.splitext(filename)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{timestamp}_{secrets.token_hex(4)}{ext.lower()}"


def _get_file_type(filename):
    """Determine file type from filename"""
    ext = os.path.splitext(filename)[1].lower()

    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
        return FileType.IMAGE.value
    elif ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']:
        return FileType.DOCUMENT.value
    elif ext in ['.mp4', '.avi', '.mov', '.wmv']:
        return FileType.VIDEO.value
    else:
        return FileType.OTHER.value


def prepare_attachments(attachments, cfg=None) -> list:
    """Validate uploads and give each its stored name; ValueError on the first
    unacceptable one. Nothing is written."""
    prepared = []
    for attachment in attachments or []:
        problem = _validate_file(attachment, cfg)
        if problem:
            raise ValueError(f"Attachment not accepted: {problem}")
        data = bytes(attachment['data'])
        prepared.append({
            'original_filename': os.path.basename(str(attachment['filename'])),
            'filename': _generate_secure_filename(str(attachment['filename'])),
            'data': data,
            'size': len(data),
            'mime_type': attachment.get('mime_type'),
            'file_hash': hashlib.sha256(data).hexdigest(),
            'is_public': attachment.get('is_public'),
        })
    return prepared


def insert_attachment_rows(conn, ticket_id, prepared, uploaded_by, *, public=True,
                           reply_id=None) -> list:
    """Record prepared attachments on ``conn``; returns them with their ids and paths."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    folder = upload_root() / str(int(ticket_id))
    for item in prepared:
        item['file_path'] = str(folder / item['filename'])
        is_public = public if item.get('is_public') is None else bool(item['is_public'])
        cur = conn.execute('''
        INSERT INTO ticket_attachments (
            ticket_id, reply_id, filename, original_filename, file_path, file_size,
            file_type, mime_type, file_hash, uploaded_by, is_public, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticket_id, reply_id, item['filename'], item['original_filename'], item['file_path'],
              item['size'], _get_file_type(item['original_filename']), item['mime_type'],
              item['file_hash'], uploaded_by, 1 if is_public else 0, now))
        item['attachment_id'] = cur.lastrowid
    return prepared


def write_attachment_files(prepared) -> list:
    """Write committed attachments to disk. Rows whose file cannot be written
    are deleted again (and any partial file removed); returns those items."""
    failed = []
    for item in prepared:
        path = Path(item['file_path'])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'xb') as f:
                f.write(item['data'])
        except OSError as exc:
            logger.error("Could not save attachment %s for ticket file %s: %s",
                         item.get('attachment_id'), path, exc)
            try:
                if path.exists() and path.stat().st_size != item['size']:
                    path.unlink()
            except OSError:
                pass
            failed.append(item)
    if failed:
        from education_system.systems.university.domains.student_support.domain.student_support import (
            store,
        )
        with store.writing() as conn:
            for item in failed:
                conn.execute("DELETE FROM ticket_attachments WHERE attachment_id = ?",
                             (item['attachment_id'],))
    return failed


def _process_attachments(ticket_id, attachments, cursor):
    """Record attachments on ``cursor``'s transaction and return them; the
    caller writes the files with :func:`write_attachment_files` after commit."""
    user = _auth_mod.user_of()
    prepared = prepare_attachments(attachments)
    return insert_attachment_rows(cursor.connection, ticket_id, prepared,
                                  (user or {}).get('username'))


def _get_attachment_count(ticket_id, cursor, staff=True):
    """Number of attachments on a ticket (``staff=False``: public ones only)."""
    sql = 'SELECT COUNT(*) FROM ticket_attachments WHERE ticket_id = ?'
    if not staff:
        sql += ' AND is_public = 1'
    cursor.execute(sql, (ticket_id,))
    return cursor.fetchone()[0]


def _get_last_response_info(ticket_id, cursor, staff=True):
    """Who answered a ticket last (``staff=False``: ignoring internal notes)."""
    sql = 'SELECT responder_role, response_datetime FROM ticket_responses WHERE ticket_id = ?'
    if not staff:
        sql += ' AND COALESCE(is_internal, 0) = 0'
    cursor.execute(sql + ' ORDER BY response_datetime DESC LIMIT 1', (ticket_id,))
    result = cursor.fetchone()
    if result:
        return {'role': result[0], 'datetime': result[1]}
    return None


def download_attachment_menu(support, attachments):
    """Download attachment menu"""
    try:
        print("\n📎 DOWNLOAD ATTACHMENTS")
        print("="*40)

        print("Available attachments:")
        for i, att in enumerate(attachments, 1):
            size_mb = (att['file_size'] or 0) / (1024 * 1024)
            print(f"{i}. 📄 {att['original_filename']} ({size_mb:.1f}MB)")
            print(f"   📅 Uploaded: {att['created_at']}")
            print(f"   👤 By: {att['uploaded_by']}")

        choice = input(f"\nSelect attachment to download (1-{len(attachments)}): ").strip()

        if not choice.isdigit() or not 1 <= int(choice) <= len(attachments):
            print("❌ Invalid choice.")
            return

        attachment = attachments[int(choice) - 1]
        attachment_id = attachment['attachment_id']

        # Download attachment
        print(f"📥 Downloading {attachment['original_filename']}...")

        file_info = support.download_attachment(attachment_id)

        # Save to current directory
        filename = os.path.basename(file_info['filename'])
        with open(filename, 'wb') as f:
            f.write(file_info['data'])

        print(f"✅ File downloaded as {filename}")

    except Exception as e:
        print(f"❌ Error downloading attachment: {e}")

    input("\nPress Enter to continue...")

"""Schemas + simple CRUD helpers for the four "extras" features that
attach to a housing assignment:

- **Keys**  : link an entry in ``access_cards`` (already owned by
              Facility Management) to a housing assignment, with
              issue/revoke helpers that record who did what.
- **Contracts** : store PDF/scan contract documents per assignment in
              the housing data dir.
- **Checklists** : move-in / move-out hand-over checklist items, each
              with optional photos, attached to a housing inspection.
- **Guests** : visitor / overnight-guest passes per assignment.

All schemas are created lazily so callers don't need a separate
migration step. Helpers log on success and exception so failures don't
silently corrupt state.
"""

from __future__ import annotations

import datetime
import logging
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    get_connection,
)
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation.common import (
    generate_id,
)

logger = logging.getLogger(__name__)


# ── Storage paths ──────────────────────────────────────────────────────

def _housing_data_dir() -> Path:
    try:
        from education_system.university_system.core import paths
        base = Path(getattr(paths, 'DATA_DIR', '.')) / 'housing'
    except Exception:
        base = Path('education_system/university_system/data/housing')
    base.mkdir(parents=True, exist_ok=True)
    return base


def contracts_dir() -> Path:
    p = _housing_data_dir() / 'contracts'
    p.mkdir(parents=True, exist_ok=True)
    return p


def checklist_photos_dir() -> Path:
    p = _housing_data_dir() / 'checklist_photos'
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Schemas ────────────────────────────────────────────────────────────

def init_extras_schemas() -> None:
    """Idempotently create every schema this module owns."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()

            # Contracts — one row per uploaded document.
            cur.execute('''
                CREATE TABLE IF NOT EXISTS housing_contract_documents (
                    doc_id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    notes TEXT,
                    uploaded_by TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    FOREIGN KEY (assignment_id)
                        REFERENCES housing_assignments (assignment_id)
                )
            ''')

            # Move-in / Move-out checklist headers + items + photos.
            cur.execute('''
                CREATE TABLE IF NOT EXISTS housing_checklists (
                    checklist_id TEXT PRIMARY KEY,
                    inspection_id TEXT,
                    assignment_id TEXT NOT NULL,
                    template TEXT NOT NULL,                  -- 'move-in' | 'move-out'
                    completed_by TEXT,
                    completed_at TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (assignment_id)
                        REFERENCES housing_assignments (assignment_id),
                    FOREIGN KEY (inspection_id)
                        REFERENCES housing_inspections (inspection_id)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS housing_checklist_items (
                    item_id TEXT PRIMARY KEY,
                    checklist_id TEXT NOT NULL,
                    area TEXT NOT NULL,                      -- e.g. 'Kitchen', 'Bathroom'
                    description TEXT NOT NULL,
                    condition TEXT,                          -- 'Good' | 'Damaged' | 'Missing'
                    notes TEXT,
                    FOREIGN KEY (checklist_id)
                        REFERENCES housing_checklists (checklist_id)
                            ON DELETE CASCADE
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS housing_checklist_photos (
                    photo_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    caption TEXT,
                    uploaded_at TEXT NOT NULL,
                    FOREIGN KEY (item_id)
                        REFERENCES housing_checklist_items (item_id)
                            ON DELETE CASCADE
                )
            ''')

            # Guest passes — student requests, staff approves.
            cur.execute('''
                CREATE TABLE IF NOT EXISTS housing_guest_passes (
                    pass_id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    guest_name TEXT NOT NULL,
                    guest_relation TEXT,
                    id_type TEXT,
                    id_reference TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    overnight INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'Pending',  -- 'Pending'|'Approved'|'Denied'|'Cancelled'
                    decision_by TEXT,
                    decision_at TEXT,
                    notes TEXT,
                    requested_by TEXT,
                    requested_at TEXT NOT NULL,
                    FOREIGN KEY (assignment_id)
                        REFERENCES housing_assignments (assignment_id)
                )
            ''')

            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to init housing extras schemas")
        raise


# ── Keys / access cards ────────────────────────────────────────────────

DEFAULT_KEY_CARD_TYPE = 'resident'


def _student_for_assignment(cur, assignment_id: str) -> tuple[str, str] | None:
    cur.execute('''
        SELECT a.student_id, s.first_name || ' ' || s.last_name
        FROM housing_assignments a
        LEFT JOIN students s ON s.student_id = a.student_id
        WHERE a.assignment_id = ?
    ''', (assignment_id,))
    row = cur.fetchone()
    return (row[0], row[1] or '') if row else None


def _building_id_for_assignment(cur, assignment_id: str) -> str | None:
    cur.execute('''
        SELECT b.building_id
        FROM housing_assignments a
        JOIN housing_rooms r ON r.room_id = a.room_id
        JOIN housing_buildings b ON b.building_id = r.building_id
        WHERE a.assignment_id = ?
    ''', (assignment_id,))
    row = cur.fetchone()
    return row[0] if row else None


def issue_card(assignment_id: str, *, issued_by: str,
                expiry_date: str | None = None) -> str | None:
    """Issue an active access card linked to the assignment's student.
    Returns the new card number, or None on failure. The Facility
    Management ``access_cards`` table is the source of truth — this
    just inserts a row keyed by ``user_id = student_id`` with the card
    notes referencing the assignment for traceability.
    """
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            who = _student_for_assignment(cur, assignment_id)
            if not who:
                logger.warning("issue_card: unknown assignment %s",
                               assignment_id)
                return None
            student_id, student_name = who
            building_id = _building_id_for_assignment(cur, assignment_id)
            card_number = f"HK-{uuid.uuid4().hex[:10].upper()}"
            now = datetime.datetime.now().isoformat(timespec='seconds')
            cur.execute('''
                INSERT INTO access_cards
                (card_number, user_id, user_name, card_type, access_level,
                 buildings_access, issue_date, expiry_date, status,
                 issued_by, notes, created_at)
                VALUES (?, ?, ?, ?, 'resident', ?, ?, ?, 'active', ?, ?, ?)
            ''', (card_number, student_id, student_name,
                  DEFAULT_KEY_CARD_TYPE,
                  building_id or '',
                  now[:10], expiry_date, issued_by,
                  f"Housing assignment {assignment_id}", now))
            conn.commit()
            logger.info("issue_card: %s issued to %s (assignment %s)",
                        card_number, student_id, assignment_id)
            return card_number
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("issue_card failed for assignment %s", assignment_id)
        return None


def revoke_cards(assignment_id: str, *, reason: str = "Move-out") -> int:
    """Mark every active card whose notes reference this assignment
    as ``revoked``. Returns count revoked."""
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                UPDATE access_cards
                   SET status = 'revoked',
                       notes  = COALESCE(notes, '') || ' | revoked: ' || ?
                 WHERE status = 'active'
                   AND notes LIKE ?
            ''', (reason, f"%{assignment_id}%"))
            n = cur.rowcount
            conn.commit()
            logger.info("revoke_cards: %d card(s) revoked for assignment %s "
                        "(reason=%s)", n, assignment_id, reason)
            return n
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("revoke_cards failed for assignment %s",
                         assignment_id)
        return 0


def list_cards_for_assignment(assignment_id: str) -> list[dict]:
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT card_id, card_number, user_id, user_name,
                       card_type, access_level, buildings_access,
                       issue_date, expiry_date, status, issued_by, notes
                FROM access_cards
                WHERE notes LIKE ?
                ORDER BY created_at DESC
            ''', (f"%{assignment_id}%",)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_cards_for_assignment failed for %s",
                         assignment_id)
        return []


# ── Contracts ──────────────────────────────────────────────────────────

def save_contract_document(assignment_id: str, source_path: str, *,
                            uploaded_by: str,
                            notes: str | None = None) -> str | None:
    init_extras_schemas()
    src = Path(source_path)
    if not src.is_file():
        logger.warning("save_contract_document: source not found %s",
                       source_path)
        return None
    try:
        target_dir = contracts_dir() / assignment_id
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        target = target_dir / f"{stamp}_{src.name}"
        shutil.copy2(src, target)
    except OSError:
        logger.exception("save_contract_document: copy failed")
        return None
    try:
        doc_id = generate_id('DOC')
        now = datetime.datetime.now().isoformat(timespec='seconds')
        conn = get_connection()
        try:
            conn.execute('''
                INSERT INTO housing_contract_documents
                (doc_id, assignment_id, original_filename, stored_path,
                 notes, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (doc_id, assignment_id, src.name, str(target), notes,
                  uploaded_by, now))
            conn.commit()
        finally:
            conn.close()
        logger.info("save_contract_document: %s saved for assignment %s",
                    doc_id, assignment_id)
        return doc_id
    except sqlite3.Error:
        logger.exception("save_contract_document: DB insert failed")
        # Best-effort cleanup of the copied file.
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def list_contract_documents(assignment_id: str) -> list[dict]:
    init_extras_schemas()
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT * FROM housing_contract_documents
                WHERE assignment_id = ?
                ORDER BY uploaded_at DESC
            ''', (assignment_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_contract_documents failed for %s",
                         assignment_id)
        return []


def delete_contract_document(doc_id: str) -> bool:
    init_extras_schemas()
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT stored_path FROM housing_contract_documents "
                "WHERE doc_id = ?", (doc_id,))
            row = cur.fetchone()
            if not row:
                return False
            stored = row[0]
            cur.execute(
                "DELETE FROM housing_contract_documents WHERE doc_id = ?",
                (doc_id,))
            conn.commit()
        finally:
            conn.close()
        try:
            Path(stored).unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not unlink contract file %s", stored)
        logger.info("delete_contract_document: %s deleted", doc_id)
        return True
    except sqlite3.Error:
        logger.exception("delete_contract_document failed for %s", doc_id)
        return False


# ── Checklists ─────────────────────────────────────────────────────────

CHECKLIST_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    'move-in': [
        ("Walls", "Free of marks, holes, or damage"),
        ("Floors", "Clean and undamaged"),
        ("Windows & blinds", "Open/close, no cracks"),
        ("Kitchen", "Appliances, taps, cupboards"),
        ("Bathroom", "Taps, shower, toilet, seals"),
        ("Bed & mattress", "Clean, no stains"),
        ("Desk & chair", "Present and undamaged"),
        ("Wardrobe", "Doors and rails working"),
        ("Lighting", "Bulbs working, switches operate"),
        ("Smoke / heat alarm", "Test, in date"),
        ("Heating / radiators", "Functional"),
        ("Keys / fob issued", "Working, count correct"),
    ],
    'move-out': [
        ("Walls", "Free of new marks, holes, or damage"),
        ("Floors", "Clean, no new stains or burns"),
        ("Windows & blinds", "Working, undamaged"),
        ("Kitchen", "Clean, appliances operational"),
        ("Bathroom", "Clean, no new damage"),
        ("Bed & mattress", "Clean, no new stains"),
        ("Desk & chair", "Returned, undamaged"),
        ("Wardrobe", "Working, contents removed"),
        ("Lighting", "Bulbs working, all returned"),
        ("Smoke / heat alarm", "Test, in date"),
        ("Heating / radiators", "Functional"),
        ("Keys / fob returned", "All returned, count correct"),
        ("Rubbish removed", "All bins emptied, communal areas tidy"),
    ],
}


def create_checklist(assignment_id: str, template: str, *,
                     inspection_id: str | None = None) -> str | None:
    if template not in CHECKLIST_TEMPLATES:
        logger.warning("create_checklist: unknown template %r", template)
        return None
    init_extras_schemas()
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            now = datetime.datetime.now().isoformat(timespec='seconds')
            cl_id = generate_id('CL')
            cur.execute('''
                INSERT INTO housing_checklists
                (checklist_id, inspection_id, assignment_id, template,
                 created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (cl_id, inspection_id, assignment_id, template, now))
            for area, desc in CHECKLIST_TEMPLATES[template]:
                cur.execute('''
                    INSERT INTO housing_checklist_items
                    (item_id, checklist_id, area, description)
                    VALUES (?, ?, ?, ?)
                ''', (generate_id('CLI'), cl_id, area, desc))
            conn.commit()
        finally:
            conn.close()
        logger.info("create_checklist: %s (%s) for assignment %s",
                    cl_id, template, assignment_id)
        return cl_id
    except sqlite3.Error:
        logger.exception("create_checklist failed")
        return None


def list_checklists(assignment_id: str) -> list[dict]:
    init_extras_schemas()
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT * FROM housing_checklists
                WHERE assignment_id = ?
                ORDER BY created_at DESC
            ''', (assignment_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_checklists failed for %s", assignment_id)
        return []


def list_checklist_items(checklist_id: str) -> list[dict]:
    init_extras_schemas()
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT * FROM housing_checklist_items
                WHERE checklist_id = ?
                ORDER BY area, item_id
            ''', (checklist_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_checklist_items failed for %s", checklist_id)
        return []


def update_checklist_item(item_id: str, *, condition: str | None,
                           notes: str | None) -> bool:
    init_extras_schemas()
    try:
        conn = get_connection()
        try:
            conn.execute('''
                UPDATE housing_checklist_items
                   SET condition = ?, notes = ?
                 WHERE item_id = ?
            ''', (condition, notes, item_id))
            conn.commit()
        finally:
            conn.close()
        return True
    except sqlite3.Error:
        logger.exception("update_checklist_item failed for %s", item_id)
        return False


def complete_checklist(checklist_id: str, *, completed_by: str,
                        notes: str | None = None) -> bool:
    init_extras_schemas()
    try:
        conn = get_connection()
        try:
            now = datetime.datetime.now().isoformat(timespec='seconds')
            conn.execute('''
                UPDATE housing_checklists
                   SET completed_by = ?, completed_at = ?, notes = ?
                 WHERE checklist_id = ?
            ''', (completed_by, now, notes, checklist_id))
            conn.commit()
        finally:
            conn.close()
        logger.info("complete_checklist: %s by %s", checklist_id, completed_by)
        return True
    except sqlite3.Error:
        logger.exception("complete_checklist failed for %s", checklist_id)
        return False


def attach_photo(item_id: str, source_path: str, *,
                  caption: str | None = None) -> str | None:
    src = Path(source_path)
    if not src.is_file():
        logger.warning("attach_photo: file not found %s", source_path)
        return None
    init_extras_schemas()
    try:
        target_dir = checklist_photos_dir() / item_id
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        target = target_dir / f"{stamp}_{src.name}"
        shutil.copy2(src, target)
    except OSError:
        logger.exception("attach_photo: copy failed")
        return None
    try:
        pid = generate_id('PH')
        now = datetime.datetime.now().isoformat(timespec='seconds')
        conn = get_connection()
        try:
            conn.execute('''
                INSERT INTO housing_checklist_photos
                (photo_id, item_id, stored_path, caption, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (pid, item_id, str(target), caption, now))
            conn.commit()
        finally:
            conn.close()
        logger.info("attach_photo: %s -> item %s", pid, item_id)
        return pid
    except sqlite3.Error:
        logger.exception("attach_photo: DB insert failed")
        return None


def list_photos(item_id: str) -> list[dict]:
    init_extras_schemas()
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT * FROM housing_checklist_photos
                WHERE item_id = ?
                ORDER BY uploaded_at
            ''', (item_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_photos failed for %s", item_id)
        return []


# ── Guest passes ───────────────────────────────────────────────────────

def request_guest_pass(assignment_id: str, *, guest_name: str,
                        start_date: str, end_date: str,
                        guest_relation: str | None = None,
                        id_type: str | None = None,
                        id_reference: str | None = None,
                        overnight: bool = False,
                        notes: str | None = None,
                        requested_by: str | None = None) -> str | None:
    if not guest_name or not start_date or not end_date:
        logger.warning("request_guest_pass: required field missing")
        return None
    try:
        datetime.date.fromisoformat(start_date)
        datetime.date.fromisoformat(end_date)
    except ValueError:
        logger.warning("request_guest_pass: bad date format")
        return None
    init_extras_schemas()
    try:
        pid = generate_id('GP')
        now = datetime.datetime.now().isoformat(timespec='seconds')
        conn = get_connection()
        try:
            conn.execute('''
                INSERT INTO housing_guest_passes
                (pass_id, assignment_id, guest_name, guest_relation,
                 id_type, id_reference, start_date, end_date,
                 overnight, status, requested_by, requested_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)
            ''', (pid, assignment_id, guest_name.strip(), guest_relation,
                  id_type, id_reference, start_date, end_date,
                  1 if overnight else 0, requested_by, now, notes))
            conn.commit()
        finally:
            conn.close()
        logger.info("request_guest_pass: %s for assignment %s "
                    "(%s, %s..%s)",
                    pid, assignment_id, guest_name, start_date, end_date)
        return pid
    except sqlite3.Error:
        logger.exception("request_guest_pass failed")
        return None


def decide_guest_pass(pass_id: str, *, approved: bool,
                       decision_by: str,
                       notes: str | None = None) -> bool:
    init_extras_schemas()
    new_status = 'Approved' if approved else 'Denied'
    try:
        now = datetime.datetime.now().isoformat(timespec='seconds')
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                UPDATE housing_guest_passes
                   SET status = ?, decision_by = ?, decision_at = ?,
                       notes = COALESCE(?, notes)
                 WHERE pass_id = ? AND status = 'Pending'
            ''', (new_status, decision_by, now, notes, pass_id))
            ok = cur.rowcount > 0
            conn.commit()
        finally:
            conn.close()
        logger.info("decide_guest_pass: %s -> %s by %s",
                    pass_id, new_status, decision_by)
        return ok
    except sqlite3.Error:
        logger.exception("decide_guest_pass failed for %s", pass_id)
        return False


def cancel_guest_pass(pass_id: str, *, by: str) -> bool:
    init_extras_schemas()
    try:
        now = datetime.datetime.now().isoformat(timespec='seconds')
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                UPDATE housing_guest_passes
                   SET status = 'Cancelled', decision_by = ?, decision_at = ?
                 WHERE pass_id = ? AND status IN ('Pending', 'Approved')
            ''', (by, now, pass_id))
            ok = cur.rowcount > 0
            conn.commit()
        finally:
            conn.close()
        return ok
    except sqlite3.Error:
        logger.exception("cancel_guest_pass failed for %s", pass_id)
        return False


def list_guest_passes(*, status: str | None = None,
                       assignment_id: str | None = None) -> list[dict]:
    init_extras_schemas()
    sql = '''
        SELECT gp.*,
               s.first_name || ' ' || s.last_name AS student_name,
               s.student_id, b.building_name, r.room_number
        FROM housing_guest_passes gp
        JOIN housing_assignments a ON a.assignment_id = gp.assignment_id
        JOIN students          s  ON s.student_id   = a.student_id
        JOIN housing_rooms     r  ON r.room_id      = a.room_id
        JOIN housing_buildings b  ON b.building_id  = r.building_id
    '''
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("gp.status = ?")
        args.append(status)
    if assignment_id:
        clauses.append("gp.assignment_id = ?")
        args.append(assignment_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY gp.start_date DESC, gp.requested_at DESC"
    try:
        conn = get_connection()
        try:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_guest_passes failed")
        return []

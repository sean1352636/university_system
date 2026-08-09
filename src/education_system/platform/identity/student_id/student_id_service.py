"""Student ID card generation and management service."""

import sqlite3
import hashlib
import json
import os
from datetime import datetime, timedelta


class StudentIDService:
    def __init__(self, db_path):
        self._db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self, conn):
        conn.execute("""CREATE TABLE IF NOT EXISTS student_id_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            card_number TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            photo_path TEXT,
            qr_data TEXT,
            issue_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        )""")

    def generate_card_number(self):
        raw = f"{datetime.now().isoformat()}{os.urandom(8).hex()}"
        num = hashlib.sha256(raw.encode()).hexdigest()[:10].upper()
        checksum = sum(int(c, 16) for c in num) % 16
        return f"ID-{num}-{checksum:X}"

    def generate_qr_data(self, card_number, student_id, full_name):
        return json.dumps({
            "card": card_number,
            "id": student_id,
            "name": full_name,
            "issued": datetime.now().strftime("%Y-%m-%d"),
        })

    def generate_id_card(self, student_id, full_name, photo_path=None,
                         validity_years=1):
        conn = self._conn()
        try:
            self._ensure_table(conn)
            # Deactivate existing cards
            conn.execute(
                "UPDATE student_id_cards SET status = 'replaced' WHERE student_id = ? AND status = 'active'",
                (student_id,),
            )
            card_number = self.generate_card_number()
            issue_date = datetime.now().strftime("%Y-%m-%d")
            expiry_date = (datetime.now() + timedelta(days=365 * validity_years)).strftime("%Y-%m-%d")
            qr_data = self.generate_qr_data(card_number, student_id, full_name)

            conn.execute(
                """INSERT INTO student_id_cards
                   (student_id, card_number, full_name, photo_path, qr_data,
                    issue_date, expiry_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, card_number, full_name, photo_path, qr_data,
                 issue_date, expiry_date),
            )
            conn.commit()
            return {"card_number": card_number, "issue_date": issue_date,
                    "expiry_date": expiry_date}
        finally:
            conn.close()

    def get_id_card(self, student_id):
        conn = self._conn()
        try:
            self._ensure_table(conn)
            row = conn.execute(
                "SELECT * FROM student_id_cards WHERE student_id = ? AND status = 'active'",
                (student_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def deactivate_card(self, card_id):
        conn = self._conn()
        try:
            self._ensure_table(conn)
            conn.execute(
                "UPDATE student_id_cards SET status = 'deactivated' WHERE id = ?",
                (card_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def reissue_card(self, student_id, reason="Replacement"):
        conn = self._conn()
        try:
            self._ensure_table(conn)
            old = conn.execute(
                "SELECT full_name, photo_path FROM student_id_cards WHERE student_id = ? ORDER BY id DESC LIMIT 1",
                (student_id,),
            ).fetchone()
            if not old:
                raise ValueError(f"No existing card for student {student_id}")
            conn.execute(
                "UPDATE student_id_cards SET status = 'replaced' WHERE student_id = ? AND status = 'active'",
                (student_id,),
            )
            conn.commit()
        finally:
            conn.close()
        return self.generate_id_card(student_id, old["full_name"], old["photo_path"])

    def list_active_cards(self):
        conn = self._conn()
        try:
            self._ensure_table(conn)
            rows = conn.execute(
                "SELECT * FROM student_id_cards WHERE status = 'active' ORDER BY full_name"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

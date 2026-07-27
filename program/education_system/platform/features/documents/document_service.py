"""Shared Document Storage service.

Documents that follow students across systems, stored as metadata in
the shared auth database with files on disk.
"""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def _auth_db_path():
    from education_system.platform.paths import AUTH_DB_FILE
    return AUTH_DB_FILE


def _documents_dir():
    from education_system.platform.paths import DOCUMENTS_DIR
    return DOCUMENTS_DIR


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cross_system_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name    TEXT    NOT NULL,
    student_id      TEXT,
    system          TEXT    NOT NULL,
    doc_type        TEXT    NOT NULL DEFAULT 'other',
    title           TEXT    NOT NULL,
    description     TEXT,
    file_path       TEXT,
    uploaded_by     TEXT,
    uploaded_system TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    tags            TEXT
);
"""

DOCUMENT_TYPES = [
    "ehcp",
    "medical",
    "safeguarding",
    "report",
    "transcript",
    "other",
]


class DocumentService:
    """Manages cross-system documents stored in the shared auth DB."""

    def __init__(self, auth_db=None, documents_dir=None):
        self._auth_db = Path(auth_db) if auth_db else _auth_db_path()
        self._docs_dir = Path(documents_dir) if documents_dir else _documents_dir()
        self._docs_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _connect(self):
        """Open a connection to the auth database."""
        self._auth_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._auth_db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_table(self):
        """Create the cross_system_documents table if it does not exist."""
        conn = self._connect()
        try:
            conn.executescript(_CREATE_TABLE_SQL)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_document(self, student_name, student_id, system, doc_type,
                        title, description, file_data, filename,
                        uploaded_by, uploaded_system):
        """Save a file to disk and create a DB record.

        Parameters:
            student_name: Student's full name
            student_id:   Student ID in the source system
            system:       System the student belongs to
            doc_type:     One of DOCUMENT_TYPES
            title:        Document title
            description:  Optional description
            file_data:    bytes or file path (str/Path) to copy from
            filename:     Original filename
            uploaded_by:  Username of uploader
            uploaded_system: System the uploader is using

        Returns the new document ID.
        """
        if doc_type not in DOCUMENT_TYPES:
            raise ValueError(f"Invalid doc_type: {doc_type}. Must be one of {DOCUMENT_TYPES}")

        # Create a subdirectory per student
        safe_name = "".join(c if c.isalnum() or c in "_- " else "_" for c in student_name)
        student_dir = self._docs_dir / safe_name.strip().replace(" ", "_")
        student_dir.mkdir(parents=True, exist_ok=True)

        # Save file with timestamp prefix to avoid collisions
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)
        dest_filename = f"{ts}_{safe_filename}"
        dest_path = student_dir / dest_filename

        if isinstance(file_data, (str, Path)):
            # Copy from source path
            src = Path(file_data)
            if src.exists():
                shutil.copy2(str(src), str(dest_path))
            else:
                raise FileNotFoundError(f"Source file not found: {file_data}")
        elif isinstance(file_data, bytes):
            dest_path.write_bytes(file_data)
        else:
            raise TypeError("file_data must be bytes or a file path")

        # Insert DB record
        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO cross_system_documents
                   (student_name, student_id, system, doc_type, title,
                    description, file_path, uploaded_by, uploaded_system, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_name, student_id, system, doc_type, title,
                 description, str(dest_path), uploaded_by, uploaded_system, ""),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_documents(self, student_name=None, system=None, doc_type=None):
        """Get documents matching the given filters.

        Returns a list of dicts.
        """
        conn = self._connect()
        try:
            conditions = []
            params = []
            if student_name:
                conditions.append("student_name LIKE ?")
                params.append(f"%{student_name.strip()}%")
            if system:
                conditions.append("system = ?")
                params.append(system)
            if doc_type:
                conditions.append("doc_type = ?")
                params.append(doc_type)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            rows = conn.execute(
                f"SELECT * FROM cross_system_documents {where} "
                f"ORDER BY created_at DESC LIMIT 500",
                params,
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
        finally:
            conn.close()

    def get_document(self, doc_id):
        """Get a single document by ID. Returns a dict or None."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM cross_system_documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
            return dict(row) if row else None
        except Exception:
            return None
        finally:
            conn.close()

    def delete_document(self, doc_id):
        """Delete a document record and its file from disk.

        Returns True if deleted, False otherwise.
        """
        doc = self.get_document(doc_id)
        if not doc:
            return False

        # Delete file from disk
        file_path = doc.get("file_path")
        if file_path:
            p = Path(file_path)
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass

        # Delete DB record
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM cross_system_documents WHERE id = ?",
                (doc_id,),
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def search_documents(self, query):
        """Search documents by title, description, student name, or tags.

        Returns a list of dicts.
        """
        if not query or not query.strip():
            return []

        conn = self._connect()
        try:
            like = f"%{query.strip()}%"
            rows = conn.execute(
                """SELECT * FROM cross_system_documents
                   WHERE title LIKE ? OR description LIKE ?
                         OR student_name LIKE ? OR tags LIKE ?
                   ORDER BY created_at DESC LIMIT 200""",
                (like, like, like, like),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
        finally:
            conn.close()

    def get_document_types(self):
        """Return the list of valid document types."""
        return list(DOCUMENT_TYPES)

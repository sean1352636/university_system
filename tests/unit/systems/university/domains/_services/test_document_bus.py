"""Unit tests for the document-manager bus (``modules.services.document_bus``).

``document_bus`` is the canonical file-store funnel over a shared ``documents``
table plus a ``users`` role lookup for ``can_access``. It doesn't bootstrap its
schema, so the fixture repoints the shared ``DEFAULT_DB_PATH`` at a temp file
(read by ``get_connection`` at call time) and seeds those two stand-in tables
with the columns the bus writes/reads.

``_publish`` (event-bus fan-out) is neutralised per test.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)
from education_system.systems.university.services.bus import document_bus

_SEED_SQL = """
CREATE TABLE documents (
    document_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type         TEXT,
    owner_id            TEXT,
    reference_type      TEXT,
    reference_id        TEXT,
    document_type       TEXT,
    document_name       TEXT,
    file_path           TEXT,
    file_hash           TEXT,
    file_size           INTEGER,
    original_filename   TEXT,
    upload_date         TEXT,
    expiry_date         TEXT,
    notes               TEXT,
    uploaded_by         TEXT,
    verification_status TEXT,
    version_number      INTEGER,
    workflow_status     TEXT,
    is_current_version  INTEGER,
    status              TEXT,
    created_at          TEXT,
    updated_at          TEXT
);
CREATE TABLE users (
    id       INTEGER PRIMARY KEY,
    username TEXT,
    role     TEXT
);
"""


@pytest.fixture()
def document_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "documents.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    with get_connection() as conn:
        conn.executescript(_SEED_SQL)
        conn.commit()
    monkeypatch.setattr(document_bus, "_publish", lambda *a, **k: None)
    return db_path


@pytest.fixture()
def sample_file(tmp_path):
    p = tmp_path / "contract.pdf"
    p.write_bytes(b"hello world")
    return str(p)


# ---------------------------------------------------------------------------
# link_document
# ---------------------------------------------------------------------------

class TestLinkDocument:
    def test_missing_path_returns_none(self, document_db):
        assert document_bus.link_document("contract", 1, file_path="") is None

    def test_persists_and_returns_id_with_hash_and_size(self, document_db, sample_file):
        doc_id = document_bus.link_document(
            "contract", "STAFF-99",
            file_path=sample_file, uploaded_by="hradmin",
        )
        assert isinstance(doc_id, int)
        conn = sqlite3.connect(document_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT reference_type, reference_id, document_name, file_hash, "
            "       file_size, status, document_type FROM documents "
            "WHERE document_id = ?",
            (doc_id,),
        ).fetchone()
        conn.close()
        assert row["reference_type"] == "contract"
        assert row["reference_id"] == "STAFF-99"
        assert row["document_name"] == "contract.pdf"
        assert row["file_hash"] is not None  # real file → hashed
        assert row["file_size"] == len(b"hello world")
        assert row["status"] == "active"
        # document_type defaults to the domain when not given.
        assert row["document_type"] == "contract"

    def test_missing_file_still_records_with_null_hash(self, document_db):
        doc_id = document_bus.link_document(
            "invoice", 7, file_path="/no/such/file.pdf", document_type="pdf"
        )
        assert isinstance(doc_id, int)
        conn = sqlite3.connect(document_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT file_hash, file_size, document_type FROM documents "
            "WHERE document_id = ?",
            (doc_id,),
        ).fetchone()
        conn.close()
        assert row["file_hash"] is None
        assert row["file_size"] is None
        assert row["document_type"] == "pdf"


# ---------------------------------------------------------------------------
# get_documents_for
# ---------------------------------------------------------------------------

class TestGetDocumentsFor:
    def test_empty_for_falsy_args(self, document_db):
        assert document_bus.get_documents_for("", 1) == []
        assert document_bus.get_documents_for("contract", None) == []

    def test_returns_linked_documents(self, document_db, sample_file):
        document_bus.link_document("incident", 42, file_path=sample_file)
        document_bus.link_document("incident", 42, file_path=sample_file)
        document_bus.link_document("incident", 99, file_path=sample_file)  # other ref
        rows = document_bus.get_documents_for("incident", 42)
        assert len(rows) == 2

    def test_excludes_non_active(self, document_db, sample_file):
        doc_id = document_bus.link_document("incident", 42, file_path=sample_file)
        conn = sqlite3.connect(document_db)
        conn.execute(
            "UPDATE documents SET status = 'archived' WHERE document_id = ?", (doc_id,)
        )
        conn.commit()
        conn.close()
        assert document_bus.get_documents_for("incident", 42) == []

    def test_ref_id_coerced_to_str(self, document_db, sample_file):
        document_bus.link_document("incident", 42, file_path=sample_file)
        # int and str lookups both resolve.
        assert len(document_bus.get_documents_for("incident", 42)) == 1
        assert len(document_bus.get_documents_for("incident", "42")) == 1


# ---------------------------------------------------------------------------
# has_document
# ---------------------------------------------------------------------------

class TestHasDocument:
    def test_false_when_none(self, document_db):
        assert document_bus.has_document("contract", 1) is False

    def test_true_when_present(self, document_db, sample_file):
        document_bus.link_document("contract", 1, file_path=sample_file)
        assert document_bus.has_document("contract", 1) is True

    def test_type_filter_case_insensitive(self, document_db, sample_file):
        document_bus.link_document(
            "contract", 1, file_path=sample_file, document_type="Offer"
        )
        assert document_bus.has_document("contract", 1, document_type="offer") is True
        assert document_bus.has_document("contract", 1, document_type="invoice") is False


# ---------------------------------------------------------------------------
# can_access
# ---------------------------------------------------------------------------

class TestCanAccess:
    def _make_doc(self, db_path, *, owner_id=None, uploaded_by=None):
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "INSERT INTO documents (reference_type, reference_id, owner_id, "
            " uploaded_by, status) VALUES ('contract', '1', ?, ?, 'active')",
            (owner_id, uploaded_by),
        )
        doc_id = cur.lastrowid
        conn.commit()
        conn.close()
        return doc_id

    def test_none_args_denied(self, document_db):
        assert document_bus.can_access(None, 1) is False
        assert document_bus.can_access(5, None) is False

    def test_unknown_document_denied(self, document_db):
        assert document_bus.can_access(5, 999999) is False

    def test_owner_allowed(self, document_db):
        doc_id = self._make_doc(document_db, owner_id="55")
        assert document_bus.can_access("55", doc_id) is True

    def test_uploader_allowed(self, document_db):
        doc_id = self._make_doc(document_db, uploaded_by="uploader1")
        assert document_bus.can_access("uploader1", doc_id) is True

    def test_global_read_role_allowed(self, document_db):
        doc_id = self._make_doc(document_db, owner_id="999")
        conn = sqlite3.connect(document_db)
        conn.execute("INSERT INTO users (id, username, role) VALUES (5, 'reg', 'Registrar')")
        conn.commit()
        conn.close()
        # Role match is case-insensitive and resolves by username.
        assert document_bus.can_access("reg", doc_id) is True

    def test_other_role_denied(self, document_db):
        doc_id = self._make_doc(document_db, owner_id="999")
        conn = sqlite3.connect(document_db)
        conn.execute("INSERT INTO users (id, username, role) VALUES (6, 'stu', 'student')")
        conn.commit()
        conn.close()
        assert document_bus.can_access("stu", doc_id) is False


# ---------------------------------------------------------------------------
# publish_document_changed
# ---------------------------------------------------------------------------

class TestPublishDocumentChanged:
    def test_broadcasts_via_publish(self, document_db, monkeypatch):
        captured: list[tuple] = []
        monkeypatch.setattr(
            document_bus, "_publish",
            lambda event, **kw: captured.append((event, kw)),
        )
        document_bus.publish_document_changed(
            document_id=12, action="deleted", domain="contract", ref_id="1"
        )
        assert len(captured) == 1
        event, kw = captured[0]
        assert event == "dm.document.changed"
        assert kw["action"] == "deleted"
        assert kw["document_id"] == 12

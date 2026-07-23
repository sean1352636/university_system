"""Sanity check that doc_manager fixture works."""


def test_doc_manager_initializes(doc_manager, temp_db):
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()
    assert "documents" in tables
    assert "students" in tables
    assert "document_types" in tables


def test_seed_helpers_work(doc_manager, seed_student, seed_document, temp_db):
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    sid = seed_student()
    did = seed_document(student_id=sid)
    conn = sqlite3.connect(temp_db)
    cur = conn.execute("SELECT COUNT(*) FROM documents WHERE document_id = ?", (did,))
    assert cur.fetchone()[0] == 1
    conn.close()

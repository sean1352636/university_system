"""Tests for document_manager.dashboard (DashboardMixin)"""


def test_display_dashboard_runs(doc_manager):
    doc_manager.display_dashboard()


def test_display_dashboard_with_data(doc_manager, seed_document):
    seed_document(status="Verified")
    seed_document(status="Pending")
    doc_manager.display_dashboard()


def test_display_quick_stats_no_data(doc_manager, temp_db):
    from education_system.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.display_quick_stats(cur)
    conn.close()


def test_display_quick_stats_with_data(doc_manager, temp_db, seed_document):
    from education_system.university_system.infrastructure.database.db import sqlite3
    seed_document(status="Pending")
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.display_quick_stats(cur)
    conn.close()


def test_display_status_overview(doc_manager, temp_db, seed_document):
    from education_system.university_system.infrastructure.database.db import sqlite3
    seed_document(status="Verified")
    seed_document(status="Pending")
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.display_status_overview(cur)
    conn.close()


def test_display_recent_activity_empty(doc_manager, temp_db):
    from education_system.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.display_recent_activity(cur)
    conn.close()


def test_display_recent_activity_with_data(doc_manager, temp_db, seed_document):
    from education_system.university_system.infrastructure.database.db import sqlite3
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    seed_document(upload_date=today)
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.display_recent_activity(cur)
    conn.close()


def test_display_expiry_alerts(doc_manager, temp_db, seed_document):
    from education_system.university_system.infrastructure.database.db import sqlite3
    from datetime import datetime, timedelta
    soon = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    past = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    seed_document(expiry=soon)
    seed_document(expiry=past)
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.display_expiry_alerts(cur)
    conn.close()


def test_display_performance_metrics(doc_manager, temp_db):
    from education_system.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    doc_manager.display_performance_metrics(cur)
    conn.close()


def test_display_dashboard_handles_db_error(doc_manager, monkeypatch):
    from education_system.university_system.modules.shared.utils import (
        document_manager as dm_pkg,
    )
    from education_system.university_system.infrastructure.database.db import sqlite3

    def boom(*a, **k):
        raise sqlite3.Error("boom")

    monkeypatch.setattr(dm_pkg, "get_connection", boom)
    doc_manager.display_dashboard()  # should not raise

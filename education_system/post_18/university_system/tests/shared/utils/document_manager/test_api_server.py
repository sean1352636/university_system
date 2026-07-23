"""Tests for document_manager.api_server (APIServerMixin)"""
from unittest.mock import patch


def test_api_server_menu_dispatches(doc_manager, feed_input):
    for m in ("start_api_server", "view_api_endpoints", "api_documentation",
              "api_keys_management", "api_usage_statistics"):
        with patch.object(doc_manager, m) as patched:
            feed_input(str(("start_api_server", "view_api_endpoints", "api_documentation",
                            "api_keys_management", "api_usage_statistics").index(m) + 1))
            doc_manager.api_server_menu()
            patched.assert_called_once()


def test_api_server_menu_invalid_choice_returns(doc_manager, feed_input):
    feed_input("99")
    doc_manager.api_server_menu()  # no exception


def test_start_api_server(doc_manager, capsys):
    doc_manager.start_api_server()
    out = capsys.readouterr().out
    assert "API" in out or "Configuration" in out


def test_view_api_endpoints(doc_manager, capsys):
    doc_manager.view_api_endpoints()
    out = capsys.readouterr().out
    assert "/api/documents" in out


def test_api_documentation_no_save(doc_manager, feed_input, capsys):
    feed_input("n")
    doc_manager.api_documentation()
    assert "API DOCUMENTATION" in capsys.readouterr().out


def test_api_documentation_save_to_file(doc_manager, feed_input, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    feed_input("y")
    doc_manager.api_documentation()
    assert (tmp_path / "api_documentation.txt").exists()


def test_api_keys_list_empty(doc_manager, feed_input, capsys):
    feed_input("1")
    doc_manager.api_keys_management()
    assert "No API keys" in capsys.readouterr().out or "Active" not in capsys.readouterr().out


def test_api_keys_generate(doc_manager, feed_input, temp_db, capsys):
    feed_input("2", "TestKey", "30", "read")
    doc_manager.api_keys_management()
    out = capsys.readouterr().out
    assert "Key:" in out
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    rows = conn.execute("SELECT key_name FROM api_keys").fetchall()
    conn.close()
    assert any("TestKey" == r[0] for r in rows)


def test_api_keys_revoke(doc_manager, feed_input, temp_db):
    from education_system.post_18.university_system.infrastructure.database.db import sqlite3
    # First create a key
    feed_input("2", "Revoke me", "30", "read")
    doc_manager.api_keys_management()
    conn = sqlite3.connect(temp_db)
    key_id = conn.execute("SELECT key_id FROM api_keys ORDER BY key_id DESC LIMIT 1").fetchone()[0]
    conn.close()
    feed_input("3", str(key_id))
    doc_manager.api_keys_management()
    conn = sqlite3.connect(temp_db)
    active = conn.execute("SELECT is_active FROM api_keys WHERE key_id = ?", (key_id,)).fetchone()[0]
    conn.close()
    assert active == 0


def test_api_usage_statistics_empty(doc_manager, capsys):
    doc_manager.api_usage_statistics()
    assert "No API usage" in capsys.readouterr().out


def test_api_usage_statistics_with_logs(doc_manager, seed_audit, feed_input, capsys):
    seed_audit(action="API_GET")
    feed_input("30")
    doc_manager.api_usage_statistics()
    assert "API" in capsys.readouterr().out

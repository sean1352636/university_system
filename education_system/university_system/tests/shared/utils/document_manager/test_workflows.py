"""Tests for document_manager.workflows (WorkflowMixin)"""
from unittest.mock import patch


def test_workflow_management_dispatch(doc_manager, feed_input):
    methods = ["view_active_workflows", "process_workflow_step",
               "create_custom_workflow", "workflow_templates",
               "workflow_analytics"]
    for i, m in enumerate(methods, start=1):
        with patch.object(doc_manager, m) as p:
            feed_input(str(i))
            doc_manager.workflow_management()
            p.assert_called_once()


def test_workflow_management_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.workflow_management()


def test_view_active_workflows_empty(doc_manager, capsys):
    doc_manager.view_active_workflows()
    assert "No active workflows" in capsys.readouterr().out


def test_view_active_workflows_with_data(doc_manager, temp_db, seed_document):
    from education_system.university_system.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status) "
        "VALUES (?, 'Review', 1, 'admin', 'pending')",
        (did,),
    )
    conn.commit()
    conn.close()
    doc_manager.view_active_workflows()


def test_process_workflow_step_not_found(doc_manager, feed_input, capsys):
    feed_input("999")
    doc_manager.process_workflow_step()
    assert "not found" in capsys.readouterr().out.lower()


def test_process_workflow_step_approve(doc_manager, temp_db, seed_document, feed_input):
    from education_system.university_system.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status) "
        "VALUES (?, 'Review', 1, 'admin', 'pending')",
        (did,),
    )
    wf_id = conn.execute("SELECT workflow_id FROM document_workflow ORDER BY workflow_id DESC LIMIT 1").fetchone()[0]
    conn.commit()
    conn.close()
    feed_input(str(wf_id), "1", "approved")
    doc_manager.process_workflow_step()


def test_process_workflow_step_reject(doc_manager, temp_db, seed_document, feed_input):
    from education_system.university_system.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status) "
        "VALUES (?, 'Review', 1, 'admin', 'pending')",
        (did,),
    )
    wf_id = conn.execute("SELECT workflow_id FROM document_workflow ORDER BY workflow_id DESC LIMIT 1").fetchone()[0]
    conn.commit()
    conn.close()
    feed_input(str(wf_id), "2", "no good")
    doc_manager.process_workflow_step()


def test_process_workflow_step_reassign(doc_manager, temp_db, seed_document, feed_input):
    from education_system.university_system.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status) "
        "VALUES (?, 'Review', 1, 'admin', 'pending')",
        (did,),
    )
    wf_id = conn.execute("SELECT workflow_id FROM document_workflow ORDER BY workflow_id DESC LIMIT 1").fetchone()[0]
    conn.commit()
    conn.close()
    feed_input(str(wf_id), "3", "bob")
    doc_manager.process_workflow_step()


def test_create_custom_workflow_no_name(doc_manager, feed_input, capsys):
    feed_input("")
    doc_manager.create_custom_workflow()
    assert "required" in capsys.readouterr().out.lower()


def test_create_custom_workflow_no_type(doc_manager, feed_input):
    feed_input("MyWF", "desc")
    with patch.object(doc_manager, "select_document_type", return_value=None):
        doc_manager.create_custom_workflow()


def test_create_custom_workflow_no_steps(doc_manager, feed_input, capsys):
    feed_input("MyWF", "desc", "done")
    with patch.object(doc_manager, "select_document_type",
                      return_value=(1, "ID Photo", False, 5, "jpg")):
        doc_manager.create_custom_workflow()
    assert "No steps" in capsys.readouterr().out


def test_create_custom_workflow_full(doc_manager, feed_input):
    feed_input("MyWF", "desc",
               "Step1", "admin", "y",
               "done")
    with patch.object(doc_manager, "select_document_type",
                      return_value=(1, "ID Photo", False, 5, "jpg")):
        doc_manager.create_custom_workflow()


def test_workflow_templates_no_table(doc_manager, capsys):
    doc_manager.workflow_templates()


def test_workflow_templates_with_data(doc_manager, temp_db, feed_input):
    from education_system.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS workflow_templates (template_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "template_name TEXT UNIQUE, description TEXT, type_id INTEGER, is_active BOOLEAN DEFAULT 1,"
        "created_by TEXT, created_date TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS workflow_template_steps (step_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "template_id INTEGER, step_name TEXT, step_order INTEGER, assigned_to TEXT, is_required BOOLEAN)"
    )
    conn.execute(
        "INSERT INTO workflow_templates (template_name, description, type_id, is_active, created_by, "
        "created_date) VALUES ('T1', 'desc', 1, 1, 'admin', '2025-01-01')"
    )
    tid = conn.execute("SELECT template_id FROM workflow_templates ORDER BY template_id DESC LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO workflow_template_steps (template_id, step_name, step_order, assigned_to, "
        "is_required) VALUES (?, 'S', 1, 'admin', 1)",
        (tid,),
    )
    conn.commit()
    conn.close()
    feed_input("3")
    doc_manager.workflow_templates()


def test_workflow_templates_toggle(doc_manager, temp_db, feed_input):
    from education_system.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS workflow_templates (template_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "template_name TEXT UNIQUE, description TEXT, type_id INTEGER, is_active BOOLEAN DEFAULT 1,"
        "created_by TEXT, created_date TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS workflow_template_steps (step_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "template_id INTEGER, step_name TEXT, step_order INTEGER, assigned_to TEXT, is_required BOOLEAN)"
    )
    conn.execute(
        "INSERT INTO workflow_templates (template_name, description, type_id, is_active, created_by, "
        "created_date) VALUES ('T2', 'd', 1, 1, 'admin', '2025-01-01')"
    )
    tid = conn.execute("SELECT template_id FROM workflow_templates ORDER BY template_id DESC LIMIT 1").fetchone()[0]
    conn.commit()
    conn.close()
    feed_input("1", str(tid))
    doc_manager.workflow_templates()


def test_workflow_templates_delete(doc_manager, temp_db, feed_input):
    from education_system.university_system.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS workflow_templates (template_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "template_name TEXT UNIQUE, description TEXT, type_id INTEGER, is_active BOOLEAN DEFAULT 1,"
        "created_by TEXT, created_date TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS workflow_template_steps (step_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "template_id INTEGER, step_name TEXT, step_order INTEGER, assigned_to TEXT, is_required BOOLEAN)"
    )
    conn.execute(
        "INSERT INTO workflow_templates (template_name, description, type_id, is_active, created_by, "
        "created_date) VALUES ('T3', 'd', 1, 1, 'admin', '2025-01-01')"
    )
    tid = conn.execute("SELECT template_id FROM workflow_templates ORDER BY template_id DESC LIMIT 1").fetchone()[0]
    conn.commit()
    conn.close()
    feed_input("2", str(tid), "y")
    doc_manager.workflow_templates()


def test_workflow_analytics(doc_manager):
    doc_manager.workflow_analytics()


def test_workflow_analytics_with_data(doc_manager, temp_db, seed_document):
    from education_system.university_system.infrastructure.database.db import sqlite3
    did = seed_document()
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status, "
        "completed_date) VALUES (?, 'Review', 1, 'admin', 'completed', '2025-01-02')",
        (did,),
    )
    conn.commit()
    conn.close()
    doc_manager.workflow_analytics()

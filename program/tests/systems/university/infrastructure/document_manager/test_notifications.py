"""Tests for document_manager.notifications (NotificationsMixin)"""
from unittest.mock import patch


def test_notification_center_dispatch(doc_manager, feed_input):
    methods = ["view_pending_notifications", "send_custom_notification",
               "bulk_notification_campaign", "notification_templates"]
    for i, m in enumerate(methods, start=1):
        with patch.object(doc_manager, m) as p:
            feed_input(str(i))
            doc_manager.notification_center()
            p.assert_called_once()


def test_notification_center_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.notification_center()


def test_my_notifications_none(doc_manager, feed_input, capsys):
    feed_input("STU999")
    doc_manager.my_notifications()
    assert "No notifications" in capsys.readouterr().out


def test_my_notifications_with_data(doc_manager, feed_input, temp_db, seed_student):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    sid = seed_student("STU555")
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO notifications (recipient_id, notification_type, title, message, "
        "created_date, is_read, priority) VALUES (?, 'x', 't', 'm', '2025-01-01 00:00:00', 0, 'high')",
        (sid,),
    )
    conn.commit()
    conn.close()
    feed_input(sid, "y")
    doc_manager.my_notifications()


def test_my_notifications_with_data_skip_read(doc_manager, feed_input, temp_db, seed_student):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    sid = seed_student("STU556")
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO notifications (recipient_id, notification_type, title, message, "
        "created_date, is_read, priority) VALUES (?, 'x', 't', 'm', '2025-01-01 00:00:00', 0, 'medium')",
        (sid,),
    )
    conn.commit()
    conn.close()
    feed_input(sid, "n")
    doc_manager.my_notifications()


def test_send_custom_notification_specific(doc_manager, feed_input, seed_student):
    sid = seed_student()
    with patch.object(doc_manager, "select_student", return_value=sid), \
         patch.object(doc_manager, "create_notification"):
        feed_input("1", "Title", "Msg", "normal", "y")
        doc_manager.send_custom_notification()


def test_send_custom_notification_all(doc_manager, feed_input, seed_student):
    seed_student("STU100")
    seed_student("STU101")
    with patch.object(doc_manager, "create_notification"):
        feed_input("2", "T", "M", "high", "y")
        doc_manager.send_custom_notification()


def test_send_custom_notification_program(doc_manager, feed_input, seed_student):
    seed_student("STU200", program="BSc CS")
    with patch.object(doc_manager, "create_notification"):
        feed_input("3", "BSc CS", "T", "M", "normal", "y")
        doc_manager.send_custom_notification()


def test_send_custom_notification_expiring(doc_manager, feed_input, seed_document):
    from datetime import datetime, timedelta
    expiry = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    seed_document(expiry=expiry)
    with patch.object(doc_manager, "create_notification"):
        feed_input("4", "30", "T", "M", "normal", "y")
        doc_manager.send_custom_notification()


def test_send_custom_notification_no_recipients(doc_manager, feed_input, capsys):
    feed_input("3", "NoSuchProgram")
    doc_manager.send_custom_notification()
    assert "No recipients" in capsys.readouterr().out


def test_send_custom_notification_cancel(doc_manager, feed_input, seed_student):
    seed_student()
    feed_input("2", "T", "M", "normal", "n")
    doc_manager.send_custom_notification()


def test_bulk_notification_send_alias(doc_manager):
    with patch.object(doc_manager, "send_custom_notification") as m:
        doc_manager.bulk_notification_send()
        m.assert_called_once()


def test_bulk_notification_campaign_reminder(doc_manager, feed_input, seed_student):
    seed_student("STU010")
    with patch.object(doc_manager, "create_notification"):
        feed_input("CampReminder", "1")
        doc_manager.bulk_notification_campaign()


def test_bulk_notification_campaign_expiry(doc_manager, feed_input, seed_document):
    from datetime import datetime, timedelta
    expiry = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    seed_document(expiry=expiry)
    with patch.object(doc_manager, "create_notification"):
        feed_input("CampExpiry", "2", "30")
        doc_manager.bulk_notification_campaign()


def test_bulk_notification_campaign_announcement(doc_manager, feed_input, seed_student):
    seed_student()
    with patch.object(doc_manager, "create_notification"):
        feed_input("AnnounceX", "4", "Title", "Body")
        doc_manager.bulk_notification_campaign()


def test_view_pending_notifications_empty(doc_manager, capsys):
    doc_manager.view_pending_notifications()
    assert "No pending" in capsys.readouterr().out


def test_view_pending_notifications_mark(doc_manager, feed_input, temp_db):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO notifications (recipient_id, notification_type, title, message, "
        "created_date, is_sent, priority) VALUES ('s1', 'x', 't', 'm', '2025-01-01', 0, 'high')",
    )
    conn.commit()
    conn.close()
    feed_input("m")
    doc_manager.view_pending_notifications()


def test_view_pending_notifications_delete(doc_manager, feed_input, temp_db):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO notifications (recipient_id, notification_type, title, message, "
        "created_date, is_sent, priority) VALUES ('s1', 'x', 't', 'm', '2025-01-01', 0, 'normal')",
    )
    conn.commit()
    conn.close()
    feed_input("d", "y")
    doc_manager.view_pending_notifications()


def test_view_pending_notifications_quit(doc_manager, feed_input, temp_db):
    from education_system.systems.university.infrastructure.database.db import sqlite3
    conn = sqlite3.connect(temp_db)
    conn.execute(
        "INSERT INTO notifications (recipient_id, notification_type, title, message, "
        "created_date, is_sent, priority) VALUES ('s1', 'x', 't', 'm', '2025-01-01', 0, 'normal')",
    )
    conn.commit()
    conn.close()
    feed_input("q")
    doc_manager.view_pending_notifications()


def test_notification_templates(doc_manager, feed_input):
    feed_input("y")
    doc_manager.notification_templates()


def test_notification_templates_no_view(doc_manager, feed_input):
    feed_input("n")
    doc_manager.notification_templates()

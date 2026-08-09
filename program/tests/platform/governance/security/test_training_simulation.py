import sqlite3
from datetime import date, timedelta

import pytest

from education_system.platform.governance.security.training_simulation import (
    DatabaseOnlyEmailService,
    SecurityTrainingSimulation,
    SimulationError,
    invitation_html,
)


class FakeEmailService:
    def __init__(self):
        self.messages = []

    def send_email(self, to, subject, body, html_body=None, **_kwargs):
        self.messages.append({
            "to": to, "subject": subject, "body": body, "html": html_body,
            **_kwargs,
        })
        return {"success": True}


class PartlyFailingEmailService(FakeEmailService):
    def send_email(self, to, subject, body, html_body=None, **kwargs):
        super().send_email(to, subject, body, html_body, **kwargs)
        if to == "admin@example.test":
            raise RuntimeError("SMTP connection refused")
        return {"success": True}


@pytest.fixture
def databases(tmp_path):
    auth = tmp_path / "auth.db"
    calendar = tmp_path / "calendar.db"
    with sqlite3.connect(auth) as conn:
        conn.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, display_name TEXT,
                email TEXT, is_active INTEGER);
            CREATE TABLE user_systems (user_id INTEGER, system_key TEXT, role TEXT);
            INSERT INTO users VALUES (1,'learner','Learner','learner@example.test',1);
            INSERT INTO users VALUES (2,'admin','Admin','admin@example.test',1);
            INSERT INTO users VALUES (3,'root','Super Admin','root@example.test',1);
            INSERT INTO user_systems VALUES (1,'university','student');
            INSERT INTO user_systems VALUES (2,'university','admin');
            INSERT INTO user_systems VALUES (3,'university','admin');
            INSERT INTO user_systems VALUES (3,'sixth_form','admin');
            INSERT INTO user_systems VALUES (3,'secondary','admin');
            INSERT INTO user_systems VALUES (3,'primary','admin');
            """
        )
    with sqlite3.connect(calendar) as conn:
        conn.execute(
            """CREATE TABLE academic_calendar_events (
                id TEXT PRIMARY KEY, name TEXT, date TEXT, date_start TEXT, date_end TEXT,
                description TEXT, event_type TEXT, date_added TEXT, last_modified TEXT,
                created_by TEXT, location TEXT, audience TEXT, participants TEXT,
                status TEXT, is_active INTEGER)"""
        )
    return auth, calendar


def test_launch_sends_three_messages_adds_calendar_and_records_click(databases):
    auth, calendar = databases
    mailer = FakeEmailService()
    service = SecurityTrainingSimulation(
        str(auth), str(calendar), "test-signing-secret", "https://education.example",
        email_service=mailer,
    )
    result = service.launch(
        1, "university", (date.today() + timedelta(days=7)).isoformat(), created_by=3,
        location="IT Lab 2", training_time="14:30",
    )

    assert result["sent"] == 3
    assert {m["to"] for m in mailer.messages} == {
        "learner@example.test", "admin@example.test", "root@example.test",
    }
    assert all(m["recipient_system"] == "university" for m in mailer.messages)
    assert {m["recipient_id"] for m in mailer.messages} == {1, 2, 3}
    assert "[Reset your password](https://education.example/" in mailer.messages[0]["body"]
    assert "ICT security training" not in mailer.messages[0]["body"]
    assert "Time: 14:30" not in mailer.messages[0]["body"]
    assert "Location: IT Lab 2" not in mailer.messages[0]["body"]
    url_line = next(line for line in mailer.messages[0]["body"].splitlines() if line.startswith("[Reset"))
    assert url_line.endswith(")")
    with sqlite3.connect(calendar) as conn:
        assert conn.execute("SELECT COUNT(*) FROM academic_calendar_events").fetchone()[0] == 1

    token = mailer.messages[0]["body"].split("invitation?token=", 1)[1].split(")", 1)[0]
    click = service.record_click(token)
    assert click.first_click is True
    assert click.training_time == "14:30"
    assert click.location == "IT Lab 2"
    assert "invited to ICT security training" in invitation_html(click)
    assert len(mailer.messages) == 4
    follow_up = mailer.messages[-1]
    assert follow_up["to"] == "learner@example.test"
    assert follow_up["subject"] == "ICT security training invitation"
    assert "Course: ICT Security Awareness Training" in follow_up["body"]
    assert service.record_click(token).first_click is False
    assert len(mailer.messages) == 4
    register = service.training_register()
    learner = next(row for row in register if row["email"] == "learner@example.test")
    assert learner["registered"] == 1
    assert learner["first_clicked_at"] is not None
    assert learner["click_count"] == 2
    assert learner["invitation_delivery_status"] == "sent"
    admin = next(row for row in register if row["email"] == "admin@example.test")
    assert admin["registered"] == 0


def test_launch_all_sends_once_to_every_active_user(databases):
    auth, calendar = databases
    mailer = FakeEmailService()
    service = SecurityTrainingSimulation(
        str(auth), str(calendar), "test-signing-secret", "https://education.example",
        email_service=mailer,
    )

    result = service.launch_all(
        (date.today() + timedelta(days=7)).isoformat(), created_by=3,
        training_time="13:15", location="IT Lab",
    )

    assert result["targeted"] == 3
    assert result["sent"] == 3
    assert result["failed"] == 0
    assert len(result["campaign_ids"]) == 3
    assert len(result["calendar_event_ids"]) == 3
    assert {message["to"] for message in mailer.messages} == {
        "learner@example.test", "admin@example.test", "root@example.test",
    }
    register = service.training_register()
    assert len(register) == 3
    assert all(row["registered"] == 1 for row in register)
    assert all(row["first_clicked_at"] is None for row in register)


def test_rejects_invalid_training_time(databases):
    auth, calendar = databases
    service = SecurityTrainingSimulation(
        str(auth), str(calendar), "test-signing-secret", "https://education.example",
        email_service=FakeEmailService(),
    )
    with pytest.raises(SimulationError, match="24-hour HH:MM"):
        service.launch(
            1, "university", (date.today() + timedelta(days=7)).isoformat(), 3,
            training_time="2:30pm",
        )


def test_rejects_tampered_token(databases):
    auth, calendar = databases
    mailer = FakeEmailService()
    service = SecurityTrainingSimulation(
        str(auth), str(calendar), "test-signing-secret", "https://education.example",
        email_service=mailer,
    )
    service.launch(1, "university", (date.today() + timedelta(days=7)).isoformat(), 3)
    token = mailer.messages[0]["body"].split("invitation?token=", 1)[1].split(")", 1)[0]
    with pytest.raises(SimulationError, match="Invalid invitation"):
        service.record_click(token + "x")


def test_launch_records_delivery_error_and_continues(databases):
    auth, calendar = databases
    service = SecurityTrainingSimulation(
        str(auth), str(calendar), "test-signing-secret", "https://education.example",
        email_service=PartlyFailingEmailService(),
    )

    result = service.launch(
        1, "university", (date.today() + timedelta(days=7)).isoformat(), created_by=3,
    )

    assert result["sent"] == 2
    assert result["failed"] == 1
    failure = next(item for item in result["recipients"] if item["status"] == "failed")
    assert failure["email"] == "admin@example.test"
    assert failure["error"] == "SMTP connection refused"
    report = service.campaign_report()
    assert report[0]["sent"] == 2
    assert report[0]["failed"] == 1


def test_database_only_email_service_stores_without_smtp():
    calls = []

    def store(*args):
        calls.append(args)
        return True

    service = DatabaseOnlyEmailService(store=store)
    result = service.send_email(
        "learner@example.test", "Training", "Open the in-app message", html_body="<p>ignored</p>",
    )

    assert result == {"success": True, "delivery_mode": "database"}
    assert calls[0][:3] == (
        "learner@example.test", "Training", "Open the in-app message",
    )


def test_database_only_service_uses_shared_system_inbox(monkeypatch):
    calls = []

    class FakeMessagingService:
        def send_message(self, **kwargs):
            calls.append(kwargs)
            return {"id": 42}

    monkeypatch.setattr(
        "education_system.platform.features.messaging.messaging_service."
        "InterSystemMessagingService",
        lambda: FakeMessagingService(),
    )
    result = DatabaseOnlyEmailService().send_email(
        "pupil@example.test", "Training", "Invitation body",
        recipient_id=17, recipient_system="primary", recipient_name="Pupil",
        sender_id=3,
    )

    assert result == {"success": True, "delivery_mode": "database"}
    assert calls[0]["recipient_id"] == 17
    assert calls[0]["recipient_system"] == "primary"
    assert calls[0]["sender_system"] == "security_training"


def test_local_campaign_starts_invitation_listener(databases, monkeypatch):
    auth, calendar = databases
    started = []

    class FakeServer:
        def __init__(self, address, handler):
            self.address = address
            self.handler = handler

        def serve_forever(self):
            started.append(self.address)

    class FakeThread:
        def __init__(self, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

    def unavailable(*_args, **_kwargs):
        raise OSError("not listening")

    monkeypatch.setattr("socket.create_connection", unavailable)
    monkeypatch.setattr("http.server.ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr("threading.Thread", FakeThread)
    mailer = FakeEmailService()
    service = SecurityTrainingSimulation(
        str(auth), str(calendar), "test-signing-secret", "http://127.0.0.1:54321",
        email_service=mailer,
    )
    service.launch(1, "university", (date.today() + timedelta(days=7)).isoformat(), 3)

    assert started == [("127.0.0.1", 54321)]
    assert "/security-training/invitation?token=" in mailer.messages[0]["body"]

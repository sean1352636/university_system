"""University e-mail outbox rules: inbox-only messages are stored not
sent, suppressions and bounces block everything, unsubscribes and
preferences block only bulk mail, retries back off then give up, a refused
address is suppressed, bulk sends need a role and carry an unsubscribe
footer, retention purges bodies, subject access export / erasure, the
delivery worker in sandbox mode, and moving the SMTP password out of the
config file. Temporary databases and files only."""

import json
import smtplib
import sqlite3
from datetime import datetime, timedelta

import pytest

from education_system.systems.university.application.mail import admin
from education_system.systems.university.application.mail import outbox as ob

EXISTING = [
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT, service_account INTEGER DEFAULT 0)",
    "CREATE TABLE stored_emails (id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_email TEXT, "
    "subject TEXT, body TEXT, created_date TEXT)",
    "CREATE TABLE email_log (id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT, subject TEXT, "
    "message TEXT, sent_date TEXT, status TEXT, body TEXT, template_vars TEXT)",
]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in EXISTING:
        c.execute(ddl)
    for name, role in (("s1", "student"), ("s2", "student"), ("staff1", "staff"),
                       ("sender", "staff"), ("admin", "admin")):
        c.execute("INSERT INTO users (username, email, role) VALUES (?, ?, ?)",
                  (name, f"{name}@uni.test", role))
    c.execute("INSERT INTO users (username, email, role, service_account) "
              "VALUES ('bot', 'bot@uni.test', 'staff', 1)")
    ob.ensure(c)
    c.commit()
    yield c
    c.close()


def refused(fn, *args, **kwargs) -> str:
    with pytest.raises((ValueError, PermissionError)) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def status_of(conn, message_id):
    return conn.execute("SELECT status FROM email_outbox WHERE message_id = ?",
                        (message_id,)).fetchone()[0]


# ── submit ──────────────────────────────────────────────────────────────


def test_inbox_only_stores_and_live_queues(conn):
    assert ob.submit(conn, "a@x.test", "Hi", "b", mode="inbox_only")["status"] == "stored"
    assert ob.submit(conn, "a@x.test", "Hi", "b", mode="live")["status"] == "queued"


def test_bad_addresses_and_header_injection_are_refused(conn):
    assert "valid" in refused(ob.submit, conn, "not-an-address", "Hi", "b", mode="live")
    assert "line breaks" in refused(ob.submit, conn, "a@x.test", "Hi\nBcc: x@y.test", "b",
                                    mode="live")
    assert refused(ob.submit, conn, "a@x.test", "Hi", "b", mode="carrier-pigeon")


def test_hard_suppression_blocks_even_transactional(conn):
    ob.suppress(conn, "admin", "a@x.test", "bounce")
    result = ob.submit(conn, "A@X.test", "Reset", "b", mode="live")
    assert result["status"] == "suppressed" and "bounce" in result["reason"]


def test_unsubscribe_and_preferences_block_only_bulk(conn):
    ob.suppress(conn, "link", "a@x.test", "unsubscribe", category="news")
    assert ob.blocked_reason(conn, "a@x.test", "bulk", "news")
    assert ob.blocked_reason(conn, "a@x.test", "bulk", "events") is None
    assert ob.blocked_reason(conn, "a@x.test", "transactional", "news") is None
    ob.set_preference(conn, "s1", "events", False)
    assert ob.blocked_reason(conn, "s1@uni.test", "bulk", "events", to_ref="s1")
    ob.set_preference(conn, "s1", "events", True)
    assert ob.blocked_reason(conn, "s1@uni.test", "bulk", "events", to_ref="s1") is None
    assert ob.preferences(conn, "s1") == {"events": True}


# ── delivery bookkeeping ────────────────────────────────────────────────


def test_temporary_failures_back_off_then_fail(conn):
    mid = ob.submit(conn, "a@x.test", "Hi", "b", mode="live")["message_id"]
    at = datetime.now() + timedelta(minutes=1)
    assert [r["message_id"] for r in ob.claim_due(conn, at=at)] == [mid]
    assert ob.claim_due(conn, at=at) == []  # already claimed
    assert ob.record_result(conn, mid, "live", "temporary", "timeout", at=at) == "queued"
    nxt = conn.execute("SELECT next_attempt_at FROM email_outbox").fetchone()[0]
    assert nxt == ob.now(at + timedelta(minutes=1))
    for _ in range(3):
        ob.record_result(conn, mid, "live", "temporary", "timeout", at=at)
    assert ob.record_result(conn, mid, "live", "temporary", "timeout", at=at) == "failed"
    assert len(ob.message(conn, mid)["attempt_log"]) == 5


def test_stuck_sending_is_reclaimed(conn):
    mid = ob.submit(conn, "a@x.test", "Hi", "b", mode="live")["message_id"]
    at = datetime.now() + timedelta(minutes=1)
    ob.claim_due(conn, at=at)
    conn.execute("UPDATE email_outbox SET updated_at = ?", (ob.now(at - timedelta(hours=1)),))
    assert [r["message_id"] for r in ob.claim_due(conn, at=at)] == [mid]


def test_permanent_failure_bounces_and_suppresses(conn):
    mid = ob.submit(conn, "gone@x.test", "Hi", "b", mode="live")["message_id"]
    assert ob.record_result(conn, mid, "live", "permanent", "550 no such user") == "bounced"
    assert ob.submit(conn, "gone@x.test", "Again", "b", mode="live")["status"] == "suppressed"


def test_rejected_message_fails_without_blaming_the_address(conn):
    mid = ob.submit(conn, "a@x.test", "Hi", "b", mode="live")["message_id"]
    assert ob.record_result(conn, mid, "live", "rejected", "missing attachment") == "failed"
    assert ob.blocked_reason(conn, "a@x.test") is None


def test_retry_cancel_and_bounce_need_an_email_admin(conn):
    mid = ob.submit(conn, "a@x.test", "Hi", "b", mode="live")["message_id"]
    assert refused(ob.cancel, conn, "staff1", "staff", mid)
    ob.grant(conn, "admin", "admin", "staff1", "email_admin")
    ob.cancel(conn, "staff1", "staff", mid)
    assert status_of(conn, mid) == "cancelled"
    ob.retry(conn, "staff1", "staff", mid)
    assert status_of(conn, mid) == "queued"
    ob.record_bounce(conn, "staff1", "staff", mid, "returned mail")
    assert status_of(conn, mid) == "bounced"
    assert "unblock" in refused(ob.retry, conn, "staff1", "staff", mid)
    ob.remove_suppression(conn, "staff1", "staff", "a@x.test")
    ob.retry(conn, "staff1", "staff", mid)


def test_roles_are_for_staff_and_granted_by_admins(conn):
    assert refused(ob.grant, conn, "staff1", "staff", "sender", "bulk_sender")
    assert "staff" in refused(ob.grant, conn, "admin", "admin", "s1", "bulk_sender")
    ob.grant(conn, "admin", "admin", "sender", "bulk_sender")
    assert ob.holds(conn, "sender", "bulk_sender")
    ob.revoke(conn, "admin", "admin", "sender", "bulk_sender")
    assert not ob.holds(conn, "sender", "bulk_sender")


def test_settings_are_validated(conn):
    assert refused(ob.set_setting, conn, "staff1", "staff", "max_attempts", "3")
    assert refused(ob.set_setting, conn, "admin", "admin", "max_attempts", "0")
    assert refused(ob.set_setting, conn, "admin", "admin", "public_base_url", "http://x")
    ob.set_setting(conn, "admin", "admin", "retention_days", "30")
    assert ob.int_setting(conn, "retention_days") == 30


# ── bulk and unsubscribe ────────────────────────────────────────────────


def test_bulk_needs_a_role_and_all_users_needs_email_admin(conn):
    args = dict(audience="students", subject="News", body="Hello", category="news",
                mode="live")
    assert refused(admin.send_bulk, conn, "sender", "staff", **args)
    ob.grant(conn, "admin", "admin", "sender", "bulk_sender")
    result = admin.send_bulk(conn, "sender", "staff", **args)
    assert result["recipients"] == 2 and result["queued"] == 2
    assert refused(admin.send_bulk, conn, "sender", "staff", **{**args, "audience": "all_users"})
    everyone = admin.send_bulk(conn, "admin", "admin", **{**args, "audience": "all_users"})
    assert everyone["recipients"] == 5  # the service account is left out
    assert admin.bulk_sends(conn)[0]["sent_by"] == "admin"
    assert any(a["entity"] == "bulk" for a in ob.recent_audit(conn))


def test_bulk_mail_carries_an_unsubscribe_that_works(conn):
    admin.send_bulk(conn, "admin", "admin", audience="addresses", addresses=["a@x.test"],
                    subject="News", body="Hello", category="news", mode="live")
    body = conn.execute("SELECT body FROM email_outbox").fetchone()[0]
    token = body.rsplit("unsubscribe code ", 1)[1].split(")")[0]
    assert ob.unsubscribe(conn, token) == {"address": "a@x.test", "category": "news"}
    again = admin.send_bulk(conn, "admin", "admin", audience="addresses",
                            addresses=["a@x.test"], subject="More", body="x", category="news",
                            mode="live")
    assert again["suppressed"] == 1
    assert refused(ob.unsubscribe, conn, "made-up")


def test_unsubscribe_link_uses_public_address(conn):
    ob.set_setting(conn, "admin", "admin", "public_base_url", "https://uni.test")
    footer = ob.unsubscribe_footer(conn, "a@x.test", "news")
    assert "https://uni.test" + ob.UNSUBSCRIBE_PATH in footer


# ── retention and subject access ────────────────────────────────────────


def test_purge_removes_old_bodies_but_keeps_records(conn):
    mid = ob.submit(conn, "a@x.test", "Hi", "secret body", mode="live")["message_id"]
    ob.record_result(conn, mid, "live", "sent")
    conn.execute("INSERT INTO stored_emails (recipient_email, subject, body, created_date) "
                 "VALUES ('a@x.test', 'Old', 'b', '2025-01-01 00:00:00')")
    conn.execute("INSERT INTO email_log (recipient, subject, message, sent_date) "
                 "VALUES ('a@x.test', 'Old', 'b', '2025-01-01 00:00:00')")
    done = admin.purge(conn, as_of=datetime.now() + timedelta(days=400))
    assert done["outbox"] == 1 and done["stored_emails"] == 1 and done["email_log"] == 1
    assert conn.execute("SELECT body, status FROM email_outbox").fetchone() == ("", "sent")
    assert conn.execute("SELECT message FROM email_log").fetchone() == (None,)


def test_export_and_erase(conn):
    ob.submit(conn, "a@x.test", "Hi", "b", mode="live")
    ob.suppress(conn, "link", "a@x.test", "unsubscribe")
    conn.execute("INSERT INTO stored_emails (recipient_email, subject, body, created_date) "
                 "VALUES ('A@x.test', 'S', 'b', '2026-10-01 00:00:00')")
    assert refused(admin.export, conn, "staff1", "staff", "a@x.test")
    data = admin.export(conn, "admin", "admin", "a@x.test")
    assert len(data["outbox"]) == 1 and len(data["stored_emails"]) == 1
    done = admin.erase(conn, "admin", "admin", "a@x.test")
    assert done["outbox"] == 1 and done["stored_emails"] == 1
    assert ob.blocked_reason(conn, "a@x.test", "bulk", "news")  # still not mailed


# ── delivery worker ─────────────────────────────────────────────────────


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    from education_system.systems.university.infrastructure.email import outbox_delivery as od
    cfg = tmp_path / "email_config.json"
    cfg.write_text(json.dumps({"delivery_mode": "sandbox", "smtp_server": "smtp.test",
                               "sender_email": "uni@x.test", "smtp_username": "uni@x.test"}))
    db = tmp_path / "uni.db"
    c = sqlite3.connect(db)
    for ddl in EXISTING:
        c.execute(ddl)
    c.commit()
    c.close()
    monkeypatch.setattr(od, "_config_path", lambda: cfg)
    monkeypatch.setattr(od, "SANDBOX_DIR", tmp_path / "sandbox")
    monkeypatch.setattr(od, "_connect", lambda db_path=None: sqlite3.connect(db))
    monkeypatch.setattr(od, "kick", lambda db_path=None: None)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    return od, db, cfg


def test_sandbox_writes_eml_files(delivery, tmp_path):
    od, db, _cfg = delivery
    assert od.enqueue("a@x.test", "Hi", "Body")["status"] == "queued"
    assert od.deliver_due()["sent"] == 1
    assert len(list((tmp_path / "sandbox").glob("*.eml"))) == 1


def test_live_mode_classifies_smtp_errors(delivery, monkeypatch):
    od, db, cfg = delivery
    monkeypatch.setenv("SMTP_PASSWORD", "pw")

    class Fake:
        def send_or_raise(self, to, *args):
            if to.startswith("bad"):
                raise smtplib.SMTPRecipientsRefused({to: (550, b"no such user")})
            raise smtplib.SMTPServerDisconnected("gone")

    monkeypatch.setattr(od, "_smtp_client", lambda cfg: Fake())
    c = sqlite3.connect(db)
    od.set_mode(c, "admin", "admin", "live")
    c.commit()
    od.enqueue("bad@x.test", "Hi", "b")
    od.enqueue("slow@x.test", "Hi", "b")
    done = od.deliver_due()
    assert done["bounced"] == 1 and done["retrying"] == 1
    assert json.loads(cfg.read_text())["delivery_mode"] == "live"


def test_live_mode_refused_without_a_password(delivery):
    od, db, _cfg = delivery
    c = sqlite3.connect(db)
    assert "SMTP login" in refused(od.set_mode, c, "admin", "admin", "live")
    assert refused(od.set_mode, c, "staff1", "staff", "sandbox")


def test_inbox_only_pass_sends_nothing(delivery):
    od, db, cfg = delivery
    cfg.write_text(json.dumps({"database_only_mode": True}))
    assert od.enqueue("a@x.test", "Hi", "b")["status"] == "stored"
    assert od.deliver_due()["sent"] == 0


def test_password_moves_out_of_the_config_file(tmp_path, monkeypatch):
    from education_system.platform.integrations.email import config as pcfg
    secret = tmp_path / "secrets" / "smtp_password"
    monkeypatch.setattr(pcfg, "PLATFORM_SMTP_PASSWORD_FILE", secret)
    monkeypatch.setattr(pcfg, "_KEYRING_AVAILABLE", False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    cfg = tmp_path / "email_config.json"
    cfg.write_text(json.dumps({"smtp_username": "u@x.test", "smtp_password": "pw",
                               "smtp_server": "smtp.test"}))
    assert pcfg.password_in_config_file(cfg)
    assert pcfg.move_password_out_of_config(cfg) == str(secret)
    data = json.loads(cfg.read_text())
    assert "smtp_password" not in data and data["smtp_server"] == "smtp.test"
    assert pcfg.get_smtp_password("u@x.test") == "pw"
    assert oct(secret.stat().st_mode)[-3:] == "600"
    assert pcfg.move_password_out_of_config(cfg) == ""


def test_address_list_bulk_honours_the_users_own_preferences(conn):
    ob.set_preference(conn, "s1", "news", False)
    result = admin.send_bulk(conn, "admin", "admin", audience="addresses",
                             addresses=["S1@uni.test", "a@x.test"], subject="News", body="x",
                             category="news", mode="live")
    assert result["suppressed"] == 1 and result["queued"] == 1

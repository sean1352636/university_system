"""Unit tests for the chatbot fallback inbox (``modules.services.chatbot_inbox``).

``chatbot_inbox`` owns the ``chatbot_pending_messages`` schema and reaches the
DB through the shared ``get_connection`` helper, which resolves its target file
from the module-level ``DEFAULT_DB_PATH``. Repointing that constant at a
per-test temp file gives full isolation; the module creates its table on every
call (``_ensure``), so no seeding is required.

``queue_message_for`` best-effort mirrors to email via
``email_bus.mirror_inbox_to_email`` inside a try/except; that seam is stubbed
per test so no real notification is attempted.
"""

import pytest

from education_system.post_18.university_system.infrastructure.database.db import (
    sqlite3,
    get_connection,
)
from education_system.post_18.university_system.modules.services import chatbot_inbox


@pytest.fixture()
def inbox_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "inbox.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    # Stub the email mirror seam so queueing never reaches the real email bus.
    from education_system.post_18.university_system.modules.services import email_bus
    monkeypatch.setattr(email_bus, "mirror_inbox_to_email", lambda *a, **k: True)
    return db_path


# ---------------------------------------------------------------------------
# queue_message_for
# ---------------------------------------------------------------------------

class TestQueueMessage:
    def test_returns_id_and_persists(self, inbox_db):
        mid = chatbot_inbox.queue_message_for(
            "U001", "You have a finance hold.", source="finance",
        )
        assert isinstance(mid, int)
        msgs = chatbot_inbox.pop_messages_for("U001", mark_read=False)
        assert len(msgs) == 1
        assert msgs[0]["message"] == "You have a finance hold."
        assert msgs[0]["source"] == "finance"

    def test_coerces_int_user_id(self, inbox_db):
        mid = chatbot_inbox.queue_message_for(42, "hi")
        assert mid is not None
        assert chatbot_inbox.pop_messages_for("42", mark_read=False)

    def test_default_source_is_system(self, inbox_db):
        chatbot_inbox.queue_message_for("U001", "hi")
        (msg,) = chatbot_inbox.pop_messages_for("U001", mark_read=False)
        assert msg["source"] == "system"

    @pytest.mark.parametrize(
        "uid, message",
        [(None, "hi"), ("", "hi"), ("U001", ""), ("U001", None)],
    )
    def test_missing_args_return_none(self, inbox_db, uid, message):
        assert chatbot_inbox.queue_message_for(uid, message) is None

    def test_email_mirror_failure_is_swallowed(self, inbox_db, monkeypatch):
        from education_system.post_18.university_system.modules.services import email_bus

        def _boom(*a, **k):
            raise RuntimeError("smtp down")

        monkeypatch.setattr(email_bus, "mirror_inbox_to_email", _boom)
        # Message still queues even though the mirror raises.
        mid = chatbot_inbox.queue_message_for("U001", "still queued")
        assert isinstance(mid, int)


# ---------------------------------------------------------------------------
# pop_messages_for
# ---------------------------------------------------------------------------

class TestPopMessages:
    def test_empty_for_falsy_user(self, inbox_db):
        assert chatbot_inbox.pop_messages_for("") == []
        assert chatbot_inbox.pop_messages_for(None) == []

    def test_empty_for_unknown_user(self, inbox_db):
        chatbot_inbox.queue_message_for("U001", "hi")
        assert chatbot_inbox.pop_messages_for("nobody") == []

    def test_mark_read_consumes_messages(self, inbox_db):
        chatbot_inbox.queue_message_for("U001", "one")
        chatbot_inbox.queue_message_for("U001", "two")
        first = chatbot_inbox.pop_messages_for("U001")  # mark_read default True
        assert {m["message"] for m in first} == {"one", "two"}
        # Second pull is empty — they were marked read.
        assert chatbot_inbox.pop_messages_for("U001") == []

    def test_mark_read_false_leaves_pending(self, inbox_db):
        chatbot_inbox.queue_message_for("U001", "keep me")
        chatbot_inbox.pop_messages_for("U001", mark_read=False)
        # Still unread → returned again.
        again = chatbot_inbox.pop_messages_for("U001", mark_read=False)
        assert len(again) == 1

    def test_read_at_stamped_on_consume(self, inbox_db):
        chatbot_inbox.queue_message_for("U001", "one")
        chatbot_inbox.pop_messages_for("U001")
        conn = sqlite3.connect(inbox_db)
        row = conn.execute(
            "SELECT is_read, read_at FROM chatbot_pending_messages"
        ).fetchone()
        conn.close()
        assert row[0] == 1
        assert row[1] is not None

    def test_isolated_per_user(self, inbox_db):
        chatbot_inbox.queue_message_for("U001", "mine")
        chatbot_inbox.queue_message_for("U002", "yours")
        u1 = chatbot_inbox.pop_messages_for("U001", mark_read=False)
        assert [m["message"] for m in u1] == ["mine"]

    def test_ordered_oldest_first(self, inbox_db):
        for label in ("a", "b", "c"):
            chatbot_inbox.queue_message_for("U001", label)
        msgs = chatbot_inbox.pop_messages_for("U001", mark_read=False)
        assert [m["message"] for m in msgs] == ["a", "b", "c"]

    def test_respects_limit(self, inbox_db):
        for label in ("a", "b", "c"):
            chatbot_inbox.queue_message_for("U001", label)
        msgs = chatbot_inbox.pop_messages_for("U001", mark_read=False, limit=2)
        assert len(msgs) == 2

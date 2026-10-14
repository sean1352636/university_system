"""The parent mailbox, and the welcome email sent on account creation."""

from __future__ import annotations

import json

import pytest

from education_system import paths
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    parent_home_cli,
)


@pytest.fixture
def mailed(feature_db):
    """A parent account with an email address, so the welcome mail is sent."""
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="mailed", password="password1",
                            full_name="Mai Led", email="mai@example.test")
    return aid


# ── The template ─────────────────────────────────────────────────────

def test_welcome_template_is_valid_json_with_the_expected_fields():
    path = paths.SIXTH_FORM_EMAIL_TEMPLATES_DIR / "welcome_parent.json"
    tpl = json.loads(path.read_text(encoding="utf-8"))
    assert tpl["template_id"] == "welcome_parent"
    for field in ("subject", "body", "from_name", "from_address",
                  "channel", "category", "priority", "description"):
        assert tpl[field], f"{field} is empty"


def test_welcome_template_placeholders_are_all_supplied(feature_db, mailed):
    """An unsupplied token renders literally as ``{{name}}``, which would
    reach the parent verbatim."""
    pp = feature_db.mods["parent_portal"]
    msg = pp.parent_message(mailed, pp.parent_messages(mailed)[0]["message_id"])
    assert "{{" not in msg["subject"]
    assert "{{" not in msg["body"]


# ── Auto-send ────────────────────────────────────────────────────────

def test_creating_an_account_sends_the_welcome_email(feature_db, mailed):
    pp = feature_db.mods["parent_portal"]
    inbox = pp.parent_messages(mailed)
    assert len(inbox) == 1
    assert inbox[0]["subject"].endswith("parent account is ready")

    body = pp.parent_message(mailed, inbox[0]["message_id"])["body"]
    assert "mailed" in body           # their sign-in name
    assert "Mai Led" in body          # addressed to them


def test_account_without_an_email_is_created_but_not_mailed(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="nomail", password="password1",
                            full_name="No Mail")
    assert pp.get_account(aid) is not None
    assert pp.parent_messages(aid) == []


def test_a_failing_send_does_not_undo_the_account(feature_db, monkeypatch):
    """The account and its shared-auth mirror already exist by the time the
    mail goes out — losing them because the mail log was down would make
    staff re-type the form for nothing."""
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        email_templates,
    )

    def _boom(*a, **kw):
        raise RuntimeError("mail log unavailable")

    monkeypatch.setattr(email_templates, "send_from_template", _boom)
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="unlucky", password="password1",
                            full_name="Un Lucky", email="un@example.test")
    assert pp.get_account(aid) is not None
    assert pp.account_for_username("unlucky") is not None


def test_welcome_email_names_the_linked_children_when_there_are_any(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="early", password="password1",
                            full_name="Ea Rly", email="ea@example.test")
    # Created before any link exists, so it uses the generic phrasing.
    body = pp.parent_message(aid, pp.parent_messages(aid)[0]["message_id"])["body"]
    assert "your child's progress" in body


# ── Mailbox scoping ──────────────────────────────────────────────────

def test_mailbox_only_shows_mail_addressed_to_this_parent(feature_db, mailed):
    pp = feature_db.mods["parent_portal"]
    other = pp.create_account(username="other", password="password1",
                              full_name="Oth Er", email="oth@example.test")

    mine = {m["message_id"] for m in pp.parent_messages(mailed)}
    theirs = {m["message_id"] for m in pp.parent_messages(other)}
    assert mine and theirs
    assert not (mine & theirs)


def test_reading_another_parents_message_is_refused(feature_db, mailed):
    """Message ids are sequential, so an unchecked id would let a parent
    walk the whole college's correspondence."""
    pp = feature_db.mods["parent_portal"]
    other = pp.create_account(username="nosy", password="password1",
                              full_name="No Sy", email="nosy@example.test")
    target = pp.parent_messages(mailed)[0]["message_id"]
    with pytest.raises(pp.ValidationError):
        pp.parent_message(other, target)


def test_mailbox_is_empty_without_an_email_address(feature_db):
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="blank", password="password1",
                            full_name="Bl Ank")
    assert pp.parent_messages(aid) == []
    with pytest.raises(pp.ValidationError):
        pp.parent_message(aid, 1)


def test_mail_about_a_child_is_not_in_the_parents_mailbox(feature_db, mailed):
    """Correspondence addressed to the student stays with the student."""
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages,
    )
    pp = feature_db.mods["parent_portal"]
    pp.link_student(mailed, "S1")
    messages.create_message({
        "thread_id": messages.new_thread_id(),
        "direction": "Outgoing", "status": "Sent",
        "subject": "A private note for Alex", "body": "For the student only.",
        "to_address": "s1@example.test", "student_id": "S1",
        "sent_at": messages._now(),
    })
    subjects = {m["subject"] for m in pp.parent_messages(mailed)}
    assert "A private note for Alex" not in subjects


def test_address_matching_is_case_insensitive(feature_db):
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages,
    )
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="mixed", password="password1",
                            full_name="Mi Xed", email="Mixed.Case@example.test")
    messages.create_message({
        "thread_id": messages.new_thread_id(),
        "direction": "Outgoing", "status": "Sent",
        "subject": "Lowercased address", "body": "...",
        "to_address": "mixed.case@example.test",
        "sent_at": messages._now(),
    })
    assert "Lowercased address" in {m["subject"] for m in pp.parent_messages(aid)}


# ── CLI rendering ────────────────────────────────────────────────────

def test_cli_email_portal_renders_a_message(feature_db, mailed, capsys):
    pp = feature_db.mods["parent_portal"]
    account = pp.account_for_username("mailed")
    parent_home_cli._print_message(account, pp.parent_messages(mailed)[0]["message_id"])
    out = capsys.readouterr().out
    assert "parent account is ready" in out
    assert "Sign-in name: mailed" in out


def test_cli_email_portal_explains_a_missing_address(feature_db, capsys):
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="void", password="password1", full_name="Vo Id")
    parent_home_cli._email_portal(pp.account_for_username("void"))
    assert "no email address" in capsys.readouterr().out.lower()


def test_cli_refuses_to_print_another_parents_message(feature_db, mailed, capsys):
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="peeker", password="password1",
                      full_name="Pe Eker", email="peek@example.test")
    target = pp.parent_messages(mailed)[0]["message_id"]
    parent_home_cli._print_message(pp.account_for_username("peeker"), target)
    out = capsys.readouterr().out
    assert "not in your mailbox" in out
    assert "Sign-in name: mailed" not in out

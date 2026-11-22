"""Messages log (domain.operations.communications.messages).

The module is a log, not an SMTP gateway: "sending" only flips the status.
``smtplib`` is made to raise so any real send attempt would fail the test.
"""

from __future__ import annotations

import smtplib

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.communications.messages import (
    messages as M,
)
from education_system.systems.primary.domain.operations.communications.parent_contacts import (
    parent_contacts as PC,
)
from education_system.systems.primary.domain.staff import staff as S


@pytest.fixture(autouse=True)
def no_real_email(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("tried to open a real SMTP connection")
    monkeypatch.setattr(smtplib, "SMTP", refuse)
    monkeypatch.setattr(smtplib, "SMTP_SSL", refuse)


def _pupil(first="Ada", last="Lovelace"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": "2",
                           "date_of_birth": "2019-02-02"})


def _staff(first="Tom", last="Teach"):
    return S.create_staff({"first_name": first, "last_name": last})


def _contact(pupil, first="Mary", email="mary@home.test", **extra):
    return PC.create_contact({"student_id": pupil.pupil_id, "first_name": first,
                              "last_name": pupil.last_name, "email": email, **extra})


def _msg(subject="Reading book", body="Please read nightly.", **extra):
    return M.create_message({"subject": subject, "body": body, **extra})


# ── create / read ───────────────────────────────────────────────────

def test_empty_database():
    assert M.list_messages() == []
    assert M.get_message(1) is None
    assert M.list_threads() == []
    assert M.search_messages("x") == []
    s = M.summary()
    assert s.total == 0 and s.threads == 0
    assert s.by_category == {c: 0 for c in M.CATEGORIES}


def test_categories_are_primary_ones():
    for cat in ("Reading", "Clubs", "SEND", "Trips", "Closure / Weather"):
        assert cat in M.CATEGORIES
    for secondary in ("Exams", "Careers", "UCAS", "Alumni"):
        assert secondary not in M.CATEGORIES


def test_create_applies_defaults():
    m = _msg()
    assert m.direction == "Outgoing"
    assert m.channel == "Email"
    assert m.category == "General"
    assert m.priority == "Normal"
    assert m.status == "Draft" and m.is_draft and not m.is_sent
    assert m.thread_id.startswith("TH-") and len(m.thread_id) == 11
    assert m.sent_at is None and m.reply_to_message_id is None
    assert m.tag_list == []


def test_create_stores_every_field_and_links():
    p, t = _pupil(), _staff()
    c = _contact(p)
    m = _msg("  Club letter  ", " Chess club Tuesday ", category="Clubs", priority="High",
             from_name=" Office ", from_address=" OFFICE@School.Test ",
             to_name=" Mary ", to_address="Mary@Home.Test", cc_address=" head@s.t ",
             student_id=p.pupil_id, staff_id=t.staff_id.lower(), parent_contact_id=str(
                 c.contact_id), sent_at="2026-03-01 10:00", attachments_note=" form ",
             tags=" clubs, chess ", notes=" n ", thread_id="TH-CUSTOM1")
    got = M.get_message(m.message_id)
    assert got == m
    assert m.subject == "Club letter" and m.body == "Chess club Tuesday"
    assert m.from_address == "office@school.test" and m.to_address == "mary@home.test"
    assert m.cc_address == "head@s.t"
    assert m.student_id == p.pupil_id
    assert m.staff_id == t.staff_id
    assert m.parent_contact_id == c.contact_id
    assert m.sent_at == "2026-03-01 10:00"
    assert m.tag_list == ["clubs", "chess"]
    assert m.thread_id == "TH-CUSTOM1"
    assert m.alumni_id is None


def test_addresses_are_free_text_off_email_channels():
    m = _msg(channel="Phone Call", to_address="07700 900123", from_address="office line")
    assert m.to_address == "07700 900123" and m.from_address == "office line"


def test_new_thread_ids_are_unique():
    assert len({M.new_thread_id() for _ in range(50)}) == 50


# ── validation ──────────────────────────────────────────────────────

@pytest.mark.parametrize("field,value,msg", [
    ("direction", "Sideways", "Direction must be one of"),
    ("channel", "Fax", "Channel must be one of"),
    ("category", "Careers", "Category must be one of"),
    ("priority", "Medium", "Priority must be one of"),
    ("status", "Lost", "Status must be one of"),
])
def test_allowed_values(field, value, msg):
    with pytest.raises(M.ValidationError, match=msg):
        _msg(**{field: value})


def test_subject_and_body_required():
    with pytest.raises(M.ValidationError, match="Subject is required"):
        _msg(subject="  ")
    with pytest.raises(M.ValidationError, match="Body is required"):
        _msg(body="")


def test_subject_length_cap():
    assert len(_msg(subject="x" * 200).subject) == 200
    with pytest.raises(M.ValidationError, match="200 characters or fewer"):
        _msg(subject="x" * 201)


def test_email_addresses_validated_on_email_and_portal():
    with pytest.raises(M.ValidationError, match="To address is not a valid email"):
        _msg(to_address="not-an-email")
    with pytest.raises(M.ValidationError, match="From address is not a valid email"):
        _msg(channel="Portal", from_address="nope")


def test_dates_must_be_iso():
    with pytest.raises(M.ValidationError, match="Sent at must be YYYY-MM-DD"):
        _msg(sent_at="1/3/2026")
    with pytest.raises(M.ValidationError, match="Received at must be YYYY-MM-DD"):
        _msg(received_at="2026-03-01T10:00")


def test_links_must_exist():
    with pytest.raises(M.ValidationError, match="No student with id 0000000"):
        _msg(student_id="0000000")
    with pytest.raises(M.ValidationError, match="No staff with id T0000000"):
        _msg(staff_id="t0000000")
    with pytest.raises(M.ValidationError, match="No parent contact with id 99"):
        _msg(parent_contact_id=99)
    with pytest.raises(M.ValidationError, match="Parent contact id must be a number"):
        _msg(parent_contact_id="abc")
    assert M.list_messages() == []


def test_direction_status_cross_rules():
    with pytest.raises(M.ValidationError, match="Outgoing messages cannot have status"):
        _msg(status="Received")
    with pytest.raises(M.ValidationError, match="Incoming messages cannot be 'Queued'"):
        _msg(direction="Incoming", status="Queued")
    assert _msg(direction="Incoming", status="Received").status == "Received"


def test_reply_target_must_exist():
    with pytest.raises(M.ValidationError, match="Reply target #42 does not exist"):
        _msg(reply_to_message_id=42)
    with pytest.raises(M.ValidationError, match="reply_to_message_id must be a number"):
        _msg(reply_to_message_id="first")


def test_reply_to_inherits_the_parents_thread():
    a = _msg()
    b = _msg(reply_to_message_id=str(a.message_id), thread_id="TH-IGNORED")
    assert b.thread_id == a.thread_id
    assert b.reply_to_message_id == a.message_id


# ── update / status ─────────────────────────────────────────────────

def test_update_merges_and_validates():
    m = _msg(tags="a")
    u = M.update_message(m.message_id, {"priority": "Urgent", "notes": "chase"})
    assert u.priority == "Urgent" and u.notes == "chase"
    assert u.subject == m.subject and u.tags == "a"
    with pytest.raises(M.ValidationError, match="Priority must be one of"):
        M.update_message(m.message_id, {"priority": "Meh"})
    with pytest.raises(M.ValidationError, match="No message with id 404"):
        M.update_message(404, {})


def test_send_flips_draft_to_sent_and_stamps_time():
    m = M.send_message(_msg().message_id)
    assert m.status == "Sent" and m.is_sent
    assert m.sent_at is not None and len(m.sent_at) == 19


def test_send_keeps_an_existing_sent_at():
    m = M.send_message(_msg(status="Queued", sent_at="2026-01-01 09:00").message_id)
    assert m.sent_at == "2026-01-01 09:00"


def test_send_retries_failed_but_refuses_sent_and_incoming():
    m = _msg()
    M.mark_failed(m.message_id, "bounced")
    assert M.send_message(m.message_id).status == "Sent"
    with pytest.raises(M.ValidationError, match="is already Sent"):
        M.send_message(m.message_id)
    inc = _msg(direction="Incoming", status="Received")
    with pytest.raises(M.ValidationError, match="Only Outgoing messages can be sent"):
        M.send_message(inc.message_id)
    with pytest.raises(M.ValidationError, match="No message with id 404"):
        M.send_message(404)


def test_mark_failed_appends_reasons_to_notes():
    m = _msg(notes="first try")
    f = M.mark_failed(m.message_id, "mailbox full")
    assert f.status == "Failed"
    assert f.notes == "first try\n[FAILED] mailbox full"
    g = M.mark_failed(_msg().message_id)
    assert g.status == "Failed" and g.notes is None
    with pytest.raises(M.ValidationError, match="No message with id 404"):
        M.mark_failed(404)


def test_set_status():
    m = _msg()
    assert M.set_status(m.message_id, "Read").status == "Read"
    with pytest.raises(M.ValidationError, match="Status must be one of"):
        M.set_status(m.message_id, "Opened")


def test_delete_and_replies_keep_history():
    a = _msg()
    b = _msg(reply_to_message_id=a.message_id)
    assert M.delete_message(a.message_id) is True
    assert M.get_message(a.message_id) is None
    assert M.get_message(b.message_id).reply_to_message_id is None
    assert M.delete_message(a.message_id) is False


def test_deleting_a_pupil_keeps_the_message_but_clears_the_link():
    p = _pupil()
    m = _msg(student_id=p.pupil_id)
    P.delete_pupil(p.pupil_id)
    kept = M.get_message(m.message_id)
    assert kept is not None and kept.student_id is None


# ── listing / search ────────────────────────────────────────────────

def test_list_filters_and_order():
    p, t = _pupil(), _staff()
    a = _msg("a", sent_at="2026-01-01", status="Sent", student_id=p.pupil_id,
             category="Reading")
    b = _msg("b", direction="Incoming", status="Received", received_at="2026-02-01",
             channel="Phone Call", staff_id=t.staff_id, priority="High")
    c = _msg("c", status="Queued", sent_at="2025-12-01")
    d = _msg("d", sent_at="2026-03-01")         # Draft

    assert [m.subject for m in M.list_messages()] == ["d", "b", "a", "c"]

    def subjects(**kw):
        return {m.subject for m in M.list_messages(**kw)}

    assert subjects(direction="Incoming") == {"b"}
    assert subjects(channel="Phone Call") == {"b"}
    assert subjects(category="Reading") == {"a"}
    assert subjects(priority="High") == {"b"}
    assert subjects(status="Queued") == {"c"}
    assert subjects(student_id=p.pupil_id) == {"a"}
    assert subjects(staff_id=t.staff_id.lower()) == {"b"}
    assert subjects(thread_id=a.thread_id) == {"a"}
    assert subjects(drafts_only=True) == {"d"}
    assert subjects(unsent_only=True) == {"c", "d"}
    assert subjects(sent_only=True) == {"a"}
    assert (b.subject, c.subject, d.subject) == ("b", "c", "d")


@pytest.mark.parametrize("kw,msg", [({"direction": "Up"}, "Direction"),
                                    ({"channel": "Fax"}, "Channel"),
                                    ({"category": "Exams"}, "Category"),
                                    ({"priority": "Meh"}, "Priority"),
                                    ({"status": "Lost"}, "Status")])
def test_list_refuses_unknown_filters(kw, msg):
    with pytest.raises(M.ValidationError, match=msg):
        M.list_messages(**kw)


def test_search_matches_text_fields():
    _msg("Nits letter", "Please check hair", to_name="Mrs Smith", tags="health")
    _msg("Trip", "Zoo visit", from_address="office@school.test")
    assert {m.subject for m in M.search_messages("hair")} == {"Nits letter"}
    assert {m.subject for m in M.search_messages("smith")} == {"Nits letter"}
    assert {m.subject for m in M.search_messages("office@")} == {"Trip"}
    assert {m.subject for m in M.search_messages("health")} == {"Nits letter"}
    assert len(M.search_messages("  ")) == 2


# ── threads and replies ─────────────────────────────────────────────

def test_reply_flips_direction_and_swaps_addresses():
    p = _pupil()
    out = _msg("Spelling test", from_name="Office", from_address="office@school.test",
               to_name="Mary", to_address="mary@home.test", student_id=p.pupil_id,
               category="Academic", status="Sent", sent_at="2026-01-01 09:00")
    r = M.reply(out.message_id, {"body": "Thanks!", "status": "Received",
                                 "received_at": "2026-01-01 12:00"})
    assert r.thread_id == out.thread_id
    assert r.reply_to_message_id == out.message_id
    assert r.direction == "Incoming"
    assert r.subject == "Re: Spelling test"
    assert (r.from_name, r.from_address) == ("Mary", "mary@home.test")
    assert (r.to_name, r.to_address) == ("Office", "office@school.test")
    assert r.student_id == p.pupil_id and r.category == "Academic"
    rr = M.reply(r.message_id, {"body": "You're welcome"})
    assert rr.subject == "Re: Spelling test"          # no "Re: Re:"
    assert rr.direction == "Outgoing" and rr.status == "Draft"


def test_reply_needs_body_and_existing_parent():
    m = _msg()
    with pytest.raises(M.ValidationError, match="Body is required"):
        M.reply(m.message_id, {})
    with pytest.raises(M.ValidationError, match="No message with id 404"):
        M.reply(404, {"body": "x"})


def test_thread_is_oldest_first_and_threads_summarised():
    a = _msg("Lunch money", status="Sent", sent_at="2026-01-01 09:00")
    b = M.reply(a.message_id, {"body": "Paid", "status": "Received",
                               "received_at": "2026-01-02 09:00"})
    other = _msg("Coats", sent_at="2025-12-01 09:00", status="Sent")
    assert [m.message_id for m in M.thread(a.thread_id)] == [a.message_id, b.message_id]

    threads = M.list_threads()
    assert [t.thread_id for t in threads] == [a.thread_id, other.thread_id]
    t = threads[0]
    assert t.message_count == 2
    assert t.subject == "Re: Lunch money"
    assert t.last_at == "2026-01-02 09:00"
    assert (t.last_direction, t.last_status) == ("Incoming", "Received")


def test_list_threads_for_one_pupil():
    p = _pupil()
    _msg("about Ada", student_id=p.pupil_id)
    _msg("general")
    assert [t.subject for t in M.list_threads(student_id=p.pupil_id)] == ["about Ada"]


# ── bulk send ───────────────────────────────────────────────────────

def test_bulk_send_needs_recipients():
    with pytest.raises(M.ValidationError, match="No recipients selected"):
        M.bulk_send(subject="s", body="b")


def test_bulk_send_to_contacts_and_staff_shares_a_thread():
    p = _pupil()
    c1 = _contact(p, "Mary")
    c2 = _contact(p, "John", email=None, primary_phone="01234 567890")
    t = _staff()
    sender = _staff("Head", "Teacher")
    res = M.bulk_send(subject="Sports day", body="Friday", contact_ids=[c1.contact_id,
                                                                        c2.contact_id, 999],
                      staff_ids=[t.staff_id, "T0000000"], category="Trips",
                      sender_staff_id=sender.staff_id, tags="sports")
    assert len(res.created) == 3
    assert {m.thread_id for m in res.created} == {res.thread_id}
    assert res.failed == [("contact #999", "no such contact"),
                          ("staff T0000000", "no such staff")]
    first = res.created[0]
    assert first.parent_contact_id == c1.contact_id
    assert first.student_id == p.pupil_id
    assert first.to_address == "mary@home.test"
    assert first.to_name == "Mary Lovelace"
    assert first.status == "Sent" and first.sent_at is not None
    assert first.staff_id == sender.staff_id
    assert first.category == "Trips" and first.tags == "sports"
    assert res.created[1].to_address is None
    assert res.created[2].to_address == t.email
    assert len(M.list_messages(thread_id=res.thread_id)) == 3


def test_bulk_send_as_draft_has_no_sent_at():
    p = _pupil()
    c = _contact(p)
    res = M.bulk_send(subject="s", body="b", contact_ids=[c.contact_id], status="Draft")
    assert res.created[0].status == "Draft" and res.created[0].sent_at is None


def test_bulk_send_records_invalid_rows_as_failed():
    p = _pupil()
    c = _contact(p)
    res = M.bulk_send(subject="s", body="b", contact_ids=[c.contact_id], category="Prom")
    assert res.created == []
    assert res.failed[0][0] == f"contact #{c.contact_id}"
    assert "Category must be one of" in res.failed[0][1]


def test_bulk_send_to_pupils():
    p = _pupil()
    res = M.bulk_send(subject="Class news", body="Hello", student_ids=[p.pupil_id,
                                                                       "0000000"])
    assert len(res.created) == 1
    assert res.created[0].student_id == p.pupil_id
    assert res.created[0].to_name == "Ada Lovelace"
    assert res.failed == [("student 0000000", "no such student")]


# ── summary ─────────────────────────────────────────────────────────

def test_summary_counts():
    a = _msg("a", status="Sent", channel="SMS")
    M.reply(a.message_id, {"body": "ok", "status": "Received"})
    _msg("c", status="Queued", category="Reading", priority="Urgent")
    _msg("d")
    _msg("e", status="Failed")
    _msg("f", status="Delivered")
    s = M.summary()
    assert s.total == 6
    assert s.drafts == 1 and s.queued == 1 and s.sent == 2 and s.failed == 1
    assert s.incoming == 1 and s.outgoing == 5
    assert s.threads == 5
    assert s.by_channel["SMS"] == 2 and s.by_channel["Email"] == 4
    assert s.by_category["Reading"] == 1 and s.by_category["General"] == 5
    assert s.by_priority["Urgent"] == 1 and s.by_priority["Normal"] == 5
    assert s.by_status["Received"] == 1 and s.by_status["Sent"] == 1

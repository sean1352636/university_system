"""Feedback log (systems.primary.domain.pastoral.feedback.feedback)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.pastoral.feedback import feedback as F

TODAY = dt.date.today().isoformat()


def _fb(**extra):
    data = {"feedback_type": "Suggestion", "subject": "More trips",
            "received_on": "2026-10-01", **extra}
    return F.create_feedback(data)


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_values():
    f = _fb(source="Email", submitter_name=" Mrs Jones ",
            submitter_role="Parent / Carer", contact_email="j@x.test",
            contact_phone="0123", anonymous=0, category="Events / Trips",
            description="Please", rating="4", assigned_to="Head",
            public_shareable=1, linked_to="trip-1", notes="note")
    got = F.get_feedback(f.feedback_id)
    assert got == f
    assert f.received_on == "2026-10-01"
    assert f.source == "Email"
    assert f.submitter_name == "Mrs Jones"
    assert f.submitter_role == "Parent / Carer"
    assert f.contact_email == "j@x.test"
    assert f.feedback_type == "Suggestion"
    assert f.category == "Events / Trips"
    assert f.rating == 4
    assert f.public_shareable is True
    assert f.anonymous is False
    assert f.status == "Received"
    assert f.linked_to == "trip-1"
    assert f.created_on == f.updated_on


def test_defaults_applied():
    f = F.create_feedback({"feedback_type": "Question", "subject": "When?"})
    assert f.received_on == TODAY
    assert f.source == F.DEFAULT_SOURCE == "Web Form"
    assert f.submitter_role == F.DEFAULT_SUBMITTER_ROLE == "Anonymous"
    assert f.category == F.DEFAULT_CATEGORY == "Other"
    assert f.status == F.DEFAULT_STATUS == "Received"
    assert f.rating is None
    assert f.description is None and f.response is None
    assert f.is_open is True
    assert f.has_response is False


def test_blank_strings_become_none():
    f = _fb(submitter_name="  ", notes="", response_on="", closed_on="")
    assert f.submitter_name is None
    assert f.notes is None
    assert f.response_on is None
    assert f.closed_on is None


def test_whitespace_only_dates_are_treated_as_blank():
    # The payload is normalised to None for blank-after-strip dates, so a
    # whitespace-only date must not be refused as malformed.
    f = _fb(response_on="  ", closed_on=" ")
    assert f.response_on is None
    assert f.closed_on is None


def test_get_missing_is_none():
    assert F.get_feedback(999) is None


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("field,value,msg", [
    ("received_on", "01/10/2026", "Received on must be YYYY-MM-DD"),
    ("response_on", "2026-13-01", "Response on must be YYYY-MM-DD"),
    ("closed_on", "nope", "Closed on must be YYYY-MM-DD"),
    ("source", "Pigeon", "Source must be one of"),
    ("submitter_role", "Alien", "Submitter role must be one of"),
    ("feedback_type", "Rant", "Feedback type must be one of"),
    ("feedback_type", "", "Feedback type must be one of"),
    ("category", "Parking", "Category must be one of"),
    ("subject", "   ", "Subject is required"),
    ("rating", "five", "Rating must be 1-5"),
    ("rating", 0, "Rating must be 1-5"),
    ("rating", 6, "Rating must be 1-5"),
    ("status", "Open", "Status must be one of"),
])
def test_create_validation(field, value, msg):
    with pytest.raises(F.ValidationError, match=msg):
        _fb(**{field: value})


def test_rating_bounds_accepted():
    assert _fb(rating=1).rating == 1
    assert _fb(rating=5).rating == 5
    assert _fb(rating="").rating is None


# ── update / delete ──────────────────────────────────────────────────

def test_update_replaces_fields():
    f = _fb()
    up = F.update_feedback(f.feedback_id, {
        "feedback_type": "Concern", "subject": "Lunch queue",
        "received_on": "2026-10-02", "category": "Catering", "rating": 2})
    assert up.feedback_type == "Concern"
    assert up.subject == "Lunch queue"
    assert up.category == "Catering"
    assert up.rating == 2
    assert F.get_feedback(f.feedback_id).subject == "Lunch queue"


def test_update_missing_refused():
    with pytest.raises(F.ValidationError, match="No feedback with id 42"):
        F.update_feedback(42, {"feedback_type": "Other", "subject": "x"})


def test_update_revalidates():
    f = _fb()
    with pytest.raises(F.ValidationError, match="Subject is required"):
        F.update_feedback(f.feedback_id, {"feedback_type": "Other", "subject": ""})


def test_delete():
    f = _fb()
    assert F.delete_feedback(f.feedback_id) is True
    assert F.get_feedback(f.feedback_id) is None
    assert F.delete_feedback(f.feedback_id) is False


# ── list ─────────────────────────────────────────────────────────────

def test_list_empty():
    assert F.list_feedback() == []


def test_list_sorted_newest_then_id_desc():
    a = _fb(received_on="2026-09-01")
    b = _fb(received_on="2026-10-01")
    c = _fb(received_on="2026-10-01")
    assert [f.feedback_id for f in F.list_feedback()] == [
        c.feedback_id, b.feedback_id, a.feedback_id]


def test_list_filters():
    a = _fb(feedback_type="Positive", category="Catering", source="Email",
            submitter_role="Parent / Carer", rating=5, assigned_to="Mr Head",
            subject="Lovely lunches", public_shareable=True,
            received_on="2026-09-05")
    b = _fb(feedback_type="Concern", category="Facilities", rating=2,
            received_on="2026-09-20", response="Fixed")
    c = _fb(status="Closed", rating=4, received_on="2026-10-10")

    def ids(**kw):
        return {f.feedback_id for f in F.list_feedback(**kw)}

    assert ids(feedback_type="Positive") == {a.feedback_id}
    assert ids(category="Facilities") == {b.feedback_id}
    assert ids(source="Email") == {a.feedback_id}
    assert ids(submitter_role="Parent / Carer") == {a.feedback_id}
    assert ids(status="Closed") == {c.feedback_id}
    assert ids(rating=2) == {b.feedback_id}
    assert ids(rating_min=4) == {a.feedback_id, c.feedback_id}
    assert ids(assigned_to_like="head") == {a.feedback_id}
    assert ids(subject_like="lunch") == {a.feedback_id}
    assert ids(open_only=True) == {a.feedback_id, b.feedback_id}
    assert ids(awaiting_response=True) == {a.feedback_id}
    assert ids(public_only=True) == {a.feedback_id}
    assert ids(date_from="2026-09-10") == {b.feedback_id, c.feedback_id}
    assert ids(date_to="2026-09-20") == {a.feedback_id, b.feedback_id}


def test_list_bad_date_filter_refused():
    with pytest.raises(F.ValidationError, match="From must be YYYY-MM-DD"):
        F.list_feedback(date_from="x")
    with pytest.raises(F.ValidationError, match="To must be YYYY-MM-DD"):
        F.list_feedback(date_to="2026-02-31")


# ── workflow ─────────────────────────────────────────────────────────

def test_assign_moves_received_to_reviewing():
    f = _fb()
    up = F.assign(f.feedback_id, to="Ms Lee")
    assert up.assigned_to == "Ms Lee"
    assert up.status == "Reviewing"
    assert up.subject == "More trips"


def test_assign_keeps_later_status():
    f = _fb(status="Responded")
    assert F.assign(f.feedback_id, to="Ms Lee").status == "Responded"


def test_assign_refusals():
    with pytest.raises(F.ValidationError, match="Assignee is required"):
        F.assign(1, to="")
    with pytest.raises(F.ValidationError, match="No feedback with id 5"):
        F.assign(5, to="x")


def test_respond_sets_response_and_status():
    f = _fb()
    up = F.respond(f.feedback_id, response="Thanks", response_by="Head",
                   response_on="2026-10-03")
    assert up.response == "Thanks"
    assert up.response_by == "Head"
    assert up.response_on == "2026-10-03"
    assert up.status == "Responded"
    assert up.has_response is True


def test_respond_defaults_date_to_today():
    f = _fb()
    assert F.respond(f.feedback_id, response="ok", response_by="me").response_on == TODAY


def test_respond_refusals():
    f = _fb()
    with pytest.raises(F.ValidationError, match="Response is required"):
        F.respond(f.feedback_id, response="", response_by="x")
    with pytest.raises(F.ValidationError, match="Response by is required"):
        F.respond(f.feedback_id, response="x", response_by="")
    with pytest.raises(F.ValidationError, match="No feedback with id 99"):
        F.respond(99, response="x", response_by="y")
    with pytest.raises(F.ValidationError, match="Response on must be"):
        F.respond(f.feedback_id, response="x", response_by="y", response_on="bad")


def test_mark_acted_appends_notes():
    f = _fb(notes="first")
    up = F.mark_acted(f.feedback_id, notes="bought games")
    assert up.status == "Acted"
    assert up.notes == f"first\n{TODAY} acted: bought games"
    plain = _fb()
    up2 = F.mark_acted(plain.feedback_id, notes="done")
    assert up2.notes == f"{TODAY} acted: done"
    assert F.mark_acted(plain.feedback_id).notes == f"{TODAY} acted: done"


def test_close_sets_closed_on_once():
    f = _fb()
    up = F.close_feedback(f.feedback_id)
    assert up.status == "Closed"
    assert up.closed_on == TODAY
    assert up.is_open is False
    g = _fb(closed_on="2026-09-30")
    assert F.close_feedback(g.feedback_id).closed_on == "2026-09-30"


def test_archive_and_set_status():
    f = _fb()
    assert F.archive(f.feedback_id).status == "Archived"
    assert F.get_feedback(f.feedback_id).is_open is False
    assert F.set_status(f.feedback_id, "Reviewing").status == "Reviewing"
    with pytest.raises(F.ValidationError, match="Status must be one of"):
        F.set_status(f.feedback_id, "Nope")


@pytest.mark.parametrize("fn", ["mark_acted", "close_feedback", "archive"])
def test_workflow_missing_id_refused(fn):
    with pytest.raises(F.ValidationError, match="No feedback with id 404"):
        getattr(F, fn)(404)


def test_set_status_missing_id_refused():
    with pytest.raises(F.ValidationError, match="No feedback with id 404"):
        F.set_status(404, "Closed")


# ── summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    s = F.summary()
    assert s.total == 0
    assert s.average_rating is None
    assert s.by_type == {}


def test_summary_figures():
    _fb(feedback_type="Positive", rating=5, public_shareable=True, source="Email")
    _fb(feedback_type="Compliment", rating=4, status="Closed")
    _fb(feedback_type="Concern", rating=2, response="On it", category="Catering")
    _fb(feedback_type="Negative", status="Archived")
    _fb(feedback_type="Suggestion", rating=4)
    s = F.summary()
    assert s.total == 5
    assert s.open_count == 3
    assert s.awaiting_response == 2
    assert s.positive_count == 2
    assert s.negative_count == 2
    assert s.suggestions_count == 1
    assert s.public_count == 1
    assert s.average_rating == 3.75           # (5+4+2+4)/4
    assert s.by_rating == {5: 1, 4: 2, 2: 1}
    assert s.by_type == {"Positive": 1, "Compliment": 1, "Concern": 1,
                         "Negative": 1, "Suggestion": 1}
    assert s.by_category == {"Other": 4, "Catering": 1}
    assert s.by_source == {"Email": 1, "Web Form": 4}
    assert s.by_status == {"Received": 3, "Closed": 1, "Archived": 1}

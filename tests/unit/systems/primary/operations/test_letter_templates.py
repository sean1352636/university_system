"""Letter templates (domain.operations.communications.letter_templates)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.communications.letter_templates import (
    letter_templates as LT,
)

TODAY = dt.date.today().isoformat()


def _new(name="Trip consent", **extra):
    payload = {"name": name,
               "subject_line": "{{ trip_name }} on {{trip_date}}",
               "body": "Dear {{parent_name}},\n{{child_name}} is going to {{trip_name}}."}
    payload.update(extra)
    return LT.create_template(payload)


# ── placeholders ────────────────────────────────────────────────────

def test_extract_placeholders_distinct_in_order():
    assert LT.extract_placeholders("{{a}} {{ b }} {{a}} {{c_1}}") == ["a", "b", "c_1"]
    assert LT.extract_placeholders("{{1bad}} {single} no tokens") == []
    assert LT.extract_placeholders(None) == []
    assert LT.extract_placeholders("") == []


def test_detected_placeholders_subject_first_then_body():
    t = _new()
    assert t.detected_placeholders == ["trip_name", "trip_date", "parent_name", "child_name"]


# ── create / read ───────────────────────────────────────────────────

def test_empty_database():
    assert LT.list_templates() == []
    assert LT.get_template(1) is None
    assert LT.get_template_by_name("x") is None
    s = LT.summary()
    assert s.total == 0 and s.most_used_name is None


def test_create_applies_defaults_and_detects_merge_fields():
    t = _new()
    assert t.category == "Other"
    assert t.recipient_type == "Parent / Carer"
    assert t.format == "Letter"
    assert t.status == "Draft" and t.is_active is False
    assert t.use_count == 0 and t.last_used_on is None
    assert t.merge_fields == "trip_name, trip_date, parent_name, child_name"
    assert t.merge_field_list == ["trip_name", "trip_date", "parent_name", "child_name"]


def test_create_stores_every_field():
    t = LT.create_template({
        "name": "  Attendance concern  ", "description": " below 90% ",
        "category": "Attendance", "recipient_type": "Both", "format": "Email",
        "subject_line": " Attendance ", "body": "Hello", "letterhead": "LH",
        "footer": "F", "signature": "Head", "sender_role": "Headteacher",
        "merge_fields": ["pupil", " ", "pct"], "attachments_ref": "a1",
        "status": "Active", "created_by": "admin3", "last_used_on": "2026-01-01",
        "use_count": "4", "notes": "n"})
    got = LT.get_template(t.template_id)
    assert got == t
    assert t.name == "Attendance concern"
    assert t.description == "below 90%"
    assert t.subject_line == "Attendance"
    assert t.merge_fields == "pupil, pct"
    assert (t.category, t.recipient_type, t.format, t.status) == (
        "Attendance", "Both", "Email", "Active")
    assert t.is_active is True
    assert t.use_count == 4 and t.last_used_on == "2026-01-01"
    assert LT.get_template_by_name(" Attendance concern ") == t


def test_merge_fields_string_is_normalised_and_blank_becomes_none():
    assert _new("a", merge_fields=" x ,y,, ").merge_fields == "x, y"
    assert _new("b", merge_fields=" , ").merge_fields is None
    assert _new("c", body="No tokens", subject_line=None).merge_fields is None


# ── validation ──────────────────────────────────────────────────────

def test_name_is_required():
    with pytest.raises(LT.ValidationError, match="Name is required"):
        _new("  ")


def test_name_must_be_unique():
    _new("Welcome")
    with pytest.raises(LT.ValidationError, match="'Welcome' already exists"):
        _new("Welcome")


@pytest.mark.parametrize("field,value,msg", [
    ("category", "Prom", "Category must be one of"),
    ("recipient_type", "Alumni", "Recipient type must be one of"),
    ("format", "Fax", "Format must be one of"),
    ("status", "Live", "Status must be one of"),
])
def test_allowed_value_lists(field, value, msg):
    with pytest.raises(LT.ValidationError, match=msg):
        _new(**{field: value})


def test_body_is_required():
    with pytest.raises(LT.ValidationError, match="Body is required"):
        _new(body="   ")


def test_last_used_on_must_be_iso():
    with pytest.raises(LT.ValidationError, match="Last used on must be YYYY-MM-DD"):
        _new(last_used_on="yesterday")


def test_use_count_must_be_a_non_negative_integer():
    with pytest.raises(LT.ValidationError, match="Use count must be an integer"):
        _new(use_count="many")
    with pytest.raises(LT.ValidationError, match="Use count must be >= 0"):
        _new(use_count=-2)


# ── update / delete ─────────────────────────────────────────────────

def test_update_keeps_own_name_but_refuses_another_templates_name():
    a = _new("A")
    _new("B")
    a2 = LT.update_template(a.template_id, {"name": "A", "body": "New body",
                                            "category": "Reminder"})
    assert a2.body == "New body" and a2.category == "Reminder"
    assert a2.merge_fields is None
    with pytest.raises(LT.ValidationError, match="'B' already exists"):
        LT.update_template(a.template_id, {"name": "B", "body": "x"})


def test_update_unknown_id_is_refused():
    with pytest.raises(LT.ValidationError, match="No template with id 7"):
        LT.update_template(7, {"name": "x", "body": "y"})


def test_delete():
    t = _new()
    assert LT.delete_template(t.template_id) is True
    assert LT.get_template(t.template_id) is None
    assert LT.delete_template(t.template_id) is False


# ── workflow ────────────────────────────────────────────────────────

def test_status_workflow():
    t = _new()
    assert LT.activate(t.template_id).status == "Active"
    assert LT.archive(t.template_id).status == "Archived"
    assert LT.retire(t.template_id).status == "Retired"
    assert LT.set_status(t.template_id, "Draft").status == "Draft"
    with pytest.raises(LT.ValidationError, match="Status must be one of"):
        LT.set_status(t.template_id, "Deleted")


@pytest.mark.parametrize("fn", [LT.activate, LT.archive, LT.retire, LT.record_use])
def test_workflow_on_missing_id_is_refused(fn):
    with pytest.raises(LT.ValidationError, match="No template with id 404"):
        fn(404)


def test_duplicate_copies_as_fresh_draft():
    t = LT.activate(_new(use_count=9, last_used_on="2026-01-01",
                         category="Trip / Visit").template_id)
    d = LT.duplicate(t.template_id, new_name="Trip consent (copy)")
    assert d.template_id != t.template_id
    assert d.name == "Trip consent (copy)"
    assert d.status == "Draft"
    assert d.use_count == 0 and d.last_used_on is None
    assert d.body == t.body and d.category == "Trip / Visit"
    assert d.merge_fields == t.merge_fields


def test_duplicate_needs_a_new_unique_name_and_existing_source():
    t = _new()
    with pytest.raises(LT.ValidationError, match="New name is required"):
        LT.duplicate(t.template_id, new_name="")
    with pytest.raises(LT.ValidationError, match="already exists"):
        LT.duplicate(t.template_id, new_name=t.name)
    with pytest.raises(LT.ValidationError, match="No template with id 404"):
        LT.duplicate(404, new_name="x")


# ── rendering ───────────────────────────────────────────────────────

def test_render_substitutes_and_tracks_use():
    t = _new()
    r = LT.render(t, {"trip_name": "Zoo", "trip_date": "2026-06-01",
                      "parent_name": "Mrs Smith", "child_name": "Ada", "extra": 1})
    assert r.subject == "Zoo on 2026-06-01"
    assert r.body == "Dear Mrs Smith,\nAda is going to Zoo."
    assert r.missing_fields == []
    after = LT.get_template(t.template_id)
    assert after.use_count == 1
    assert after.last_used_on == TODAY


def test_render_by_id_with_missing_fields_leaves_tokens_and_does_not_track():
    t = _new()
    r = LT.render(t.template_id, {"trip_name": "Zoo", "child_name": None})
    assert r.missing_fields == ["trip_date", "parent_name"]
    assert r.subject == "Zoo on {{trip_date}}"
    assert r.body == "Dear {{parent_name}},\n is going to Zoo."
    assert LT.get_template(t.template_id).use_count == 0


def test_render_without_tracking():
    t = _new(body="Hi", subject_line=None)
    r = LT.render(t, {}, track_use=False)
    assert r.subject is None and r.body == "Hi" and r.missing_fields == []
    assert LT.get_template(t.template_id).use_count == 0


def test_render_unknown_id_is_refused():
    with pytest.raises(LT.ValidationError, match="No template with id 5"):
        LT.render(5, {})


def test_preview_returns_raw_text_and_all_placeholders():
    t = _new()
    p = LT.preview(t.template_id)
    assert p.subject == t.subject_line and p.body == t.body
    assert p.missing_fields == t.detected_placeholders
    assert LT.get_template(t.template_id).use_count == 0
    with pytest.raises(LT.ValidationError, match="No template with id 77"):
        LT.preview(77)


def test_record_use_with_explicit_date():
    t = _new()
    LT.record_use(t.template_id, used_on="2026-03-03")
    u = LT.record_use(t.template_id, used_on="2026-03-04")
    assert u.use_count == 2 and u.last_used_on == "2026-03-04"


# ── listing ─────────────────────────────────────────────────────────

def test_list_filters_and_order():
    a = _new("Zebra", category="Behaviour", recipient_type="Both", format="Email",
             created_by="admin3")
    b = LT.activate(_new("Apple", category="Behaviour").template_id)
    c = _new("Mango", category="Achievement", format="SMS", created_by="teacher1")

    assert [t.name for t in LT.list_templates()] == ["Mango", "Apple", "Zebra"]

    def names(**kw):
        return {t.name for t in LT.list_templates(**kw)}

    assert names(category="Behaviour") == {"Apple", "Zebra"}
    assert names(recipient_type="Both") == {"Zebra"}
    assert names(format="SMS") == {"Mango"}
    assert names(status="Active") == {"Apple"}
    assert names(active_only=True) == {"Apple"}
    assert names(name_like="an") == {"Mango"}
    assert names(created_by_like="teach") == {"Mango"}
    assert (a.name, b.name, c.name) == ("Zebra", "Apple", "Mango")


# ── summary ─────────────────────────────────────────────────────────

def test_summary_counts_and_most_used():
    LT.activate(_new("A", use_count=3, category="Reminder").template_id)
    LT.archive(_new("B", use_count=7, format="Email").template_id)
    LT.retire(_new("C").template_id)
    _new("D", use_count=7)
    s = LT.summary()
    assert s.total == 4
    assert (s.active, s.drafts, s.archived, s.retired) == (1, 1, 1, 1)
    assert s.total_uses == 17
    assert s.most_used_name == "B"          # first to reach 7 in list order wins
    assert s.most_used_count == 7
    assert s.by_category == {"Reminder": 1, "Other": 3}
    assert s.by_format == {"Letter": 3, "Email": 1}
    assert s.by_recipient_type == {"Parent / Carer": 4}
    assert s.by_status == {"Active": 1, "Archived": 1, "Retired": 1, "Draft": 1}

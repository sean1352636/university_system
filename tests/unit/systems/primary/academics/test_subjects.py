"""Subjects catalogue (domain.academics.subjects.subjects)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.subjects import subjects as S
from education_system.systems.primary.domain.learners.pupils.pupils import _connect


def _subject(code="MATH", name="Maths", **extra):
    data = {"code": code, "name": name, "key_stage": "All", **extra}
    return S.create(data)


# ── empty database ──

def test_empty_db():
    assert S.list_all() == []
    assert S.get(1) is None
    assert S.get_by_code("MATH") is None
    assert S.counts() == {"total": 0, "active": 0, "inactive": 0, "core": 0}
    assert S.delete(5) is False
    assert S.is_in_use(5) is False


# ── create / read ──

def test_create_stores_every_field():
    rec = _subject(code=" engl ", name=" English ", key_stage="KS2",
                   qualification="National Curriculum", department=" Literacy ",
                   is_core=True, notes=" core ")
    assert (rec.code, rec.name, rec.key_stage, rec.qualification, rec.department,
            rec.is_core, rec.is_active, rec.notes) == (
        "ENGL", "English", "KS2", "National Curriculum", "Literacy", True, True, "core")
    assert S.get(rec.subject_id) == rec
    assert S.get_by_code("engl") == rec


def test_qualification_defaults_to_national_curriculum():
    assert _subject().qualification == "National Curriculum"


def test_key_stage_defaults_to_all():
    """The schema and DEFAULT_KEY_STAGE say a subject with no key stage is 'All'."""
    rec = S.create({"code": "ART", "name": "Art"})
    assert rec.key_stage == S.DEFAULT_KEY_STAGE == "All"


def test_create_inactive_and_not_core_by_default():
    rec = _subject(is_active=False)
    assert rec.is_active is False
    assert rec.is_core is False


# ── validation ──

def test_code_required():
    with pytest.raises(S.ValidationError, match="Code is required"):
        _subject(code="")


@pytest.mark.parametrize("code", ["M", "TOOLONGCODE", "MA-TH"])
def test_code_shape(code):
    with pytest.raises(S.ValidationError, match="2–8 uppercase"):
        _subject(code=code)


def test_name_required():
    with pytest.raises(S.ValidationError, match="Name is required"):
        _subject(name=" ")


def test_name_length():
    with pytest.raises(S.ValidationError, match="64 characters"):
        _subject(name="x" * 65)


def test_key_stage_must_be_known():
    with pytest.raises(S.ValidationError, match="Key stage must be one of"):
        _subject(key_stage="KS4")


def test_qualification_must_be_known():
    with pytest.raises(S.ValidationError, match="Qualification must be one of"):
        _subject(qualification="GCSE")


def test_duplicate_code_refused():
    _subject()
    with pytest.raises(S.ValidationError, match="already exists"):
        _subject(code="math", name="Other")


# ── listing ──

def test_list_sorted_by_name_and_filtered():
    _subject("SCI", "science", key_stage="KS2", is_core=True)
    _subject("PHON", "Phonics", key_stage="KS1")
    _subject("RE", "RE", qualification="RE / RSHE", is_active=False)
    _subject("MATH", "Maths")
    assert [s.code for s in S.list_all()] == ["MATH", "PHON", "RE", "SCI"]
    assert [s.code for s in S.list_all(key_stage="KS2")] == ["SCI"]
    assert [s.code for s in S.list_all(qualification="RE / RSHE")] == ["RE"]
    assert [s.code for s in S.list_all(active_only=True)] == ["MATH", "PHON", "SCI"]


def test_list_filters_validated():
    with pytest.raises(S.ValidationError, match="Key-stage filter"):
        S.list_all(key_stage="KS3")
    with pytest.raises(S.ValidationError, match="Qualification filter"):
        S.list_all(qualification="A level")


def test_counts():
    _subject("MATH", "Maths", is_core=True)
    _subject("ENGL", "English", is_core=True)
    _subject("ART", "Art", is_active=False)
    assert S.counts() == {"total": 3, "active": 2, "inactive": 1, "core": 2}


# ── update / toggle ──

def test_update_merges_fields():
    rec = _subject(department="Numeracy")
    out = S.update(rec.subject_id, {"name": "Mathematics", "is_core": True})
    assert (out.code, out.name, out.department, out.is_core) == (
        "MATH", "Mathematics", "Numeracy", True)


def test_update_to_existing_code_refused():
    _subject("ENGL", "English")
    rec = _subject()
    with pytest.raises(S.ValidationError, match="already exists"):
        S.update(rec.subject_id, {"code": "ENGL"})


def test_update_unknown():
    with pytest.raises(S.ValidationError, match="No subject #9"):
        S.update(9, {"name": "x"})


def test_toggle_active():
    rec = _subject()
    assert S.toggle_active(rec.subject_id).is_active is False
    assert S.toggle_active(rec.subject_id).is_active is True
    with pytest.raises(S.ValidationError, match="No subject #99"):
        S.toggle_active(99)


# ── in use / delete ──

def test_delete_unused_subject():
    rec = _subject()
    assert S.delete(rec.subject_id) is True
    assert S.get(rec.subject_id) is None


def test_subject_used_by_a_table_cannot_be_deleted():
    rec = _subject()
    with _connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS observations "
                     "(id INTEGER PRIMARY KEY, subject_id INTEGER)")
        conn.execute("INSERT INTO observations (subject_id) VALUES (?)", (rec.subject_id,))
        conn.commit()
    assert S.is_in_use(rec.subject_id) is True
    with pytest.raises(S.ValidationError, match="deactivate it instead"):
        S.delete(rec.subject_id)
    assert S.get(rec.subject_id) is not None

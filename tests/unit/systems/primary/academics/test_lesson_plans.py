"""Lesson plans (domain.academics.lesson_plans.lesson_plans)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.lesson_plans import lesson_plans as LP
from education_system.systems.primary.domain.academics.subjects import subjects as S

DAY = "2025-09-08"


def _subject(code="MATH", name="Maths"):
    return S.create({"code": code, "name": name, "key_stage": "All"})


def _plan(subject=None, **extra):
    subject = subject or _subject()
    return LP.create({"title": "Column addition", "subject_id": subject.subject_id,
                      "year_group": "3", "planned_date": DAY, **extra})


# ── empty database ──

def test_empty_db():
    assert LP.list_plans() == []
    assert LP.get(1) is None
    assert LP.delete(1) is False
    assert LP.status_counts() == {"Draft": 0, "Ready": 0, "Delivered": 0, "Reviewed": 0}


# ── create ──

def test_create_stores_every_field_with_subject_join():
    text = {k: f" {k} text " for k in ("objectives", "activities", "resources",
                                       "differentiation", "assessment", "homework",
                                       "notes")}
    p = _plan(form_group=" 3 Maple ", period="2", duration_min="60",
              teacher=" Mrs Oak ", **text)
    assert (p.title, p.year_group, p.form_group, p.planned_date, p.period,
            p.duration_min, p.teacher, p.status) == (
        "Column addition", "3", "3 Maple", DAY, 2, 60, "Mrs Oak", "Draft")
    for k in text:
        assert getattr(p, k) == f"{k} text"
    assert (p.subject_code, p.subject_name) == ("MATH", "Maths")
    assert LP.get(p.plan_id) == p


def test_optional_fields_default_to_none():
    p = _plan()
    assert (p.form_group, p.period, p.duration_min, p.teacher, p.objectives) == (
        None, None, None, None, None)


# ── validation ──

def test_title_rules():
    sub = _subject()
    with pytest.raises(LP.ValidationError, match="Title is required"):
        _plan(sub, title="")
    with pytest.raises(LP.ValidationError, match="120 characters"):
        _plan(sub, title="t" * 121)


def test_subject_rules():
    sub = _subject()
    with pytest.raises(LP.ValidationError, match="Subject is required"):
        _plan(sub, subject_id="")
    with pytest.raises(LP.ValidationError, match="Subject ID must be a number"):
        _plan(sub, subject_id="x")
    with pytest.raises(LP.ValidationError, match="No subject #42"):
        _plan(sub, subject_id=42)


def test_year_group_rules():
    sub = _subject()
    with pytest.raises(LP.ValidationError, match="Year group is required"):
        _plan(sub, year_group=None)
    with pytest.raises(LP.ValidationError, match="Year group must be one of"):
        _plan(sub, year_group="Nursery")


def test_planned_date_rules():
    sub = _subject()
    with pytest.raises(LP.ValidationError, match="Planned date is required"):
        _plan(sub, planned_date="")
    with pytest.raises(LP.ValidationError, match="Planned date must be YYYY-MM-DD"):
        _plan(sub, planned_date="8/9/25")
    with pytest.raises(LP.ValidationError, match="Planned date is not a real date"):
        _plan(sub, planned_date="2025-13-01")


@pytest.mark.parametrize("period", [0, 9])
def test_period_range(period):
    with pytest.raises(LP.ValidationError, match="Period must be between 1 and 8"):
        _plan(period=period)


@pytest.mark.parametrize("period", [1, 8])
def test_period_bounds_accepted(period):
    assert _plan(period=period).period == period


def test_period_must_be_whole_number():
    with pytest.raises(LP.ValidationError, match="Period must be a whole number"):
        _plan(period="first")


@pytest.mark.parametrize("mins", [4, 241])
def test_duration_range(mins):
    with pytest.raises(LP.ValidationError, match="between 5 and 240"):
        _plan(duration_min=mins)


def test_status_must_be_known():
    with pytest.raises(LP.ValidationError, match="Status must be one of"):
        _plan(status="Taught")


# ── listing ──

def test_list_order_and_filters():
    maths, eng = _subject(), _subject("ENGL", "English")
    a = _plan(maths, planned_date="2025-09-08", period=3, teacher="Mrs Oak")
    b = _plan(maths, planned_date="2025-09-08", period=1, status="Ready")
    c = _plan(eng, planned_date="2025-09-10", year_group="4", teacher="Mr Ash")
    ids = lambda xs: [x.plan_id for x in xs]  # noqa: E731
    assert ids(LP.list_plans()) == [c.plan_id, b.plan_id, a.plan_id]
    assert ids(LP.list_plans(year_group="4")) == [c.plan_id]
    assert ids(LP.list_plans(subject_id=maths.subject_id)) == [b.plan_id, a.plan_id]
    assert ids(LP.list_plans(teacher=" Mrs Oak")) == [a.plan_id]
    assert ids(LP.list_plans(status="Ready")) == [b.plan_id]
    assert ids(LP.list_plans(date_from="2025-09-09")) == [c.plan_id]
    assert ids(LP.list_plans(date_to="2025-09-09")) == [b.plan_id, a.plan_id]


def test_list_filters_validated():
    with pytest.raises(LP.ValidationError, match="Year filter"):
        LP.list_plans(year_group="8")
    with pytest.raises(LP.ValidationError, match="Status filter"):
        LP.list_plans(status="Done")
    with pytest.raises(LP.ValidationError, match="From date must be YYYY-MM-DD"):
        LP.list_plans(date_from="Monday")


# ── update / status / delete ──

def test_update_merges_fields():
    p = _plan(teacher="Mrs Oak", period=2)
    out = LP.update(p.plan_id, {"objectives": "Add 3-digit numbers", "period": 4})
    assert (out.teacher, out.period, out.objectives, out.title) == (
        "Mrs Oak", 4, "Add 3-digit numbers", "Column addition")
    with pytest.raises(LP.ValidationError, match="Period must be between"):
        LP.update(p.plan_id, {"period": 12})
    with pytest.raises(LP.ValidationError, match="No lesson plan #55"):
        LP.update(55, {})


def test_status_lifecycle_and_counts():
    sub = _subject()
    p = _plan(sub)
    _plan(sub)
    for status in ("Ready", "Delivered", "Reviewed"):
        assert LP.set_status(p.plan_id, status).status == status
    with pytest.raises(LP.ValidationError, match="Status must be one of"):
        LP.set_status(p.plan_id, "Archived")
    assert LP.status_counts() == {"Draft": 1, "Ready": 0, "Delivered": 0, "Reviewed": 1}


def test_delete_plan():
    p = _plan()
    assert LP.delete(p.plan_id) is True
    assert LP.get(p.plan_id) is None
    assert LP.delete(p.plan_id) is False


def test_planned_subject_counts_as_in_use():
    sub = _subject()
    _plan(sub)
    assert S.is_in_use(sub.subject_id) is True
    with pytest.raises(S.ValidationError, match="deactivate it instead"):
        S.delete(sub.subject_id)

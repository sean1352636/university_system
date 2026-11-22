"""Newsletters (domain.operations.communications.newsletters)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.communications.newsletters import (
    newsletters as NL,
)


def _new(title="Autumn news", year="2026-27", **extra):
    return NL.create({"title": title, "academic_year": year, **extra})


# ── create / read ───────────────────────────────────────────────────

def test_empty_database():
    assert NL.list_newsletters() == []
    assert NL.get(1) is None
    assert NL.known_years() == []
    assert NL.summary() == {"total": 0,
                            "by_status": {"draft": 0, "published": 0, "archived": 0},
                            "academic_years": 0}
    assert NL.next_issue_number("2026-27") == 1


def test_create_applies_defaults():
    n = _new()
    assert n.title == "Autumn news"
    assert n.academic_year == "2026-27"
    assert n.audience == "whole_school"
    assert n.status == "draft" and n.is_draft
    assert n.issue_number is None and n.issue_date is None
    assert n.target_year_group is None and n.published_on is None


def test_create_stores_every_field():
    n = _new("  Year 4 trip special  ", issue_number="3", issue_date="2026-10-01",
             audience=" Year_Group ", target_year_group="4", body=" Bring wellies ",
             authored_by=" Mr Teach ", notes=" n ")
    got = NL.get(n.newsletter_id)
    assert got == n
    assert n.title == "Year 4 trip special"
    assert n.issue_number == 3
    assert n.issue_date == "2026-10-01"
    assert n.audience == "year_group" and n.target_year_group == "4"
    assert n.body == "Bring wellies" and n.authored_by == "Mr Teach" and n.notes == "n"


@pytest.mark.parametrize("year", ["2026", "2026-27", "2026-2027"])
def test_academic_year_shapes_accepted(year):
    assert _new(year=year).academic_year == year


# ── validation ──────────────────────────────────────────────────────

def test_title_required_and_capped():
    with pytest.raises(NL.ValidationError, match="Title is required"):
        _new("  ")
    with pytest.raises(NL.ValidationError, match="200 characters or fewer"):
        _new("x" * 201)
    assert len(_new("x" * 200).title) == 200


def test_issue_number_must_be_integer_1_to_9999():
    with pytest.raises(NL.ValidationError, match="must be an integer"):
        _new(issue_number="three")
    with pytest.raises(NL.ValidationError, match="between 1 and 9999"):
        _new(issue_number=0)
    with pytest.raises(NL.ValidationError, match="between 1 and 9999"):
        _new(issue_number=10000)


def test_academic_year_required_and_shaped():
    with pytest.raises(NL.ValidationError, match="Academic year is required"):
        _new(year="")
    with pytest.raises(NL.ValidationError, match="must look like 2025 or 2025-26"):
        _new(year="26/27")


def test_issue_and_published_dates_must_be_iso():
    with pytest.raises(NL.ValidationError, match="Issue date must be YYYY-MM-DD"):
        _new(issue_date="1 Oct")
    with pytest.raises(NL.ValidationError, match="Published-on date must be YYYY-MM-DD"):
        _new(published_on="today")


def test_audience_must_be_known():
    with pytest.raises(NL.ValidationError, match="Audience must be one of"):
        _new(audience="alumni")


def test_year_group_audience_needs_a_primary_year_group():
    with pytest.raises(NL.ValidationError, match="Target year group is required"):
        _new(audience="year_group")
    with pytest.raises(NL.ValidationError, match="Target year group must be one of"):
        _new(audience="year_group", target_year_group="9")
    assert _new(audience="year_group", target_year_group="R").target_year_group == "R"


def test_status_must_be_known():
    with pytest.raises(NL.ValidationError, match="Status must be one of"):
        _new(status="sent")


def test_issue_number_unique_within_a_year_only():
    a = _new(issue_number=1)
    with pytest.raises(NL.ValidationError, match=f"Issue 1 for 2026-27 already exists "
                                                 rf"\(#{a.newsletter_id}\)"):
        _new("Again", issue_number=1)
    assert _new("Next year", year="2027-28", issue_number=1).issue_number == 1
    # issues without a number never clash
    _new("Flyer A")
    _new("Flyer B")
    assert len(NL.list_newsletters(academic_year="2026-27")) == 3


# ── update / publish workflow ───────────────────────────────────────

def test_update_merges_fields():
    n = _new(body="old", issue_number=2)
    u = NL.update(n.newsletter_id, {"body": "new", "authored_by": "Head"})
    assert u.body == "new" and u.authored_by == "Head"
    assert u.title == n.title and u.issue_number == 2


def test_update_refuses_issue_number_taken_by_another():
    _new("One", issue_number=1)
    two = _new("Two", issue_number=2)
    with pytest.raises(NL.ValidationError, match="Issue 1 for 2026-27 already exists"):
        NL.update(two.newsletter_id, {"issue_number": 1})
    assert NL.update(two.newsletter_id, {"issue_number": 2}).issue_number == 2


def test_update_unknown_is_refused():
    with pytest.raises(NL.ValidationError, match="No newsletter #99"):
        NL.update(99, {"title": "x"})


def test_publish_stamps_date_and_locks():
    n = _new()
    p = NL.publish(n.newsletter_id, published_on="2026-10-20")
    assert p.status == "published" and p.is_published
    assert p.published_on == "2026-10-20"
    with pytest.raises(NL.ValidationError, match="published — revert to draft"):
        NL.update(n.newsletter_id, {"title": "edited"})
    # publishing again is a no-op
    assert NL.publish(n.newsletter_id, published_on="2026-12-01").published_on == "2026-10-20"


def test_publish_defaults_to_today():
    p = NL.publish(_new().newsletter_id)
    # SQLite's date('now') is UTC, so allow either side of midnight
    today = {dt.date.today().isoformat(),
             dt.datetime.now(dt.timezone.utc).date().isoformat()}
    assert p.published_on in today


def test_publish_refuses_bad_date_archived_and_missing():
    n = _new()
    with pytest.raises(NL.ValidationError, match="Published-on date must be YYYY-MM-DD"):
        NL.publish(n.newsletter_id, published_on="20/10/2026")
    NL.archive(n.newsletter_id)
    with pytest.raises(NL.ValidationError, match="archived — revert to draft first"):
        NL.publish(n.newsletter_id)
    with pytest.raises(NL.ValidationError, match="No newsletter #404"):
        NL.publish(404)


def test_revert_to_draft_clears_published_date_and_unlocks():
    n = NL.publish(_new().newsletter_id, published_on="2026-10-20")
    r = NL.revert_to_draft(n.newsletter_id)
    assert r.status == "draft" and r.published_on is None
    assert NL.update(n.newsletter_id, {"title": "Edited"}).title == "Edited"
    assert NL.revert_to_draft(n.newsletter_id).status == "draft"       # idempotent
    with pytest.raises(NL.ValidationError, match="No newsletter #404"):
        NL.revert_to_draft(404)


def test_archive_from_published_and_archived_can_revert():
    n = NL.publish(_new().newsletter_id, published_on="2026-10-20")
    a = NL.archive(n.newsletter_id)
    assert a.status == "archived" and a.is_archived
    assert a.published_on == "2026-10-20"
    assert NL.archive(n.newsletter_id).status == "archived"           # idempotent
    assert NL.revert_to_draft(n.newsletter_id).status == "draft"
    with pytest.raises(NL.ValidationError, match="No newsletter #404"):
        NL.archive(404)


def test_delete():
    n = _new()
    assert NL.delete(n.newsletter_id) is True
    assert NL.get(n.newsletter_id) is None
    assert NL.delete(n.newsletter_id) is False


# ── listing ─────────────────────────────────────────────────────────

def test_list_order_year_then_date_then_issue():
    a = _new("old year", year="2025-26", issue_date="2026-06-01")
    b = _new("early", issue_date="2026-09-10", issue_number=1)
    c = _new("late", issue_date="2026-10-10", issue_number=2)
    d = _new("undated", issue_number=3)
    assert [n.title for n in NL.list_newsletters()] == [c.title, b.title, d.title, a.title]


def test_list_filters():
    a = _new("Harvest", audience="parents", authored_by="Mrs Field")
    b = NL.publish(_new("Y6 SATs", audience="year_group",
                        target_year_group="6").newsletter_id)
    c = _new("Governor report", year="2025-26", audience="governors", body="budget")

    def titles(**kw):
        return {n.title for n in NL.list_newsletters(**kw)}

    assert titles(academic_year="2025-26") == {c.title}
    assert titles(status="published") == {b.title}
    assert titles(audience="parents") == {a.title}
    assert titles(target_year_group="6") == {b.title}
    assert titles(search="budget") == {c.title}
    assert titles(search="field") == {a.title}
    assert titles(search="SATs") == {b.title}


@pytest.mark.parametrize("kw,msg", [({"status": "sent"}, "Status filter"),
                                    ({"audience": "pupils"}, "Audience filter"),
                                    ({"target_year_group": "7"}, "Year filter")])
def test_list_refuses_unknown_filters(kw, msg):
    with pytest.raises(NL.ValidationError, match=msg):
        NL.list_newsletters(**kw)


# ── summary helpers ─────────────────────────────────────────────────

def test_summary_known_years_and_next_issue():
    _new("a", issue_number=1)
    _new("b", issue_number=4)
    NL.publish(_new("c").newsletter_id)
    NL.archive(_new("d", year="2025-26", issue_number=9).newsletter_id)
    assert NL.summary() == {"total": 4,
                            "by_status": {"draft": 2, "published": 1, "archived": 1},
                            "academic_years": 2}
    assert NL.known_years() == ["2026-27", "2025-26"]
    assert NL.next_issue_number("2026-27") == 5
    assert NL.next_issue_number(" 2025-26 ") == 10
    assert NL.next_issue_number("2030-31") == 1
    with pytest.raises(NL.ValidationError, match="Academic year is required"):
        NL.next_issue_number("  ")

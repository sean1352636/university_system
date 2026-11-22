"""End-of-term pupil reports
(systems.primary.domain.operations.reporting.pupil_reports.pupil_reports)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.reporting.pupil_reports import (
    pupil_reports as R,
)

AY, PREV = "2025-26", "2024-25"


def _pupil(first="Ada", last="Lovelace", year="4"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year,
                           "date_of_birth": "2017-01-01"})


def _report(pupil, *, year=AY, term="Autumn", **extra):
    data = {"pupil_id": pupil.pupil_id, "academic_year": year, "term": term}
    data.update(extra)
    return R.create(data)


# ── constants and Report properties ──

def test_terms_and_statuses():
    assert R.TERMS == ("Autumn", "Spring", "Summer")
    assert R.STATUSES == ("draft", "published")


def test_report_status_properties():
    rep = _report(_pupil())
    assert rep.is_draft and not rep.is_published
    pub = R.publish(rep.report_id, published_on="2025-12-12")
    assert pub.is_published and not pub.is_draft


# ── create: happy path ──

def test_create_stores_every_field_and_strips_text():
    p = _pupil()
    rep = R.create({
        "pupil_id": f"  {p.pupil_id} ", "academic_year": " 2025-26 ", "term": " spring ",
        "headline": "  A great term ", "summary": " Settled well ",
        "strengths": " Reading ", "next_steps": " Times tables ",
        "attendance_pct": "96.5", "behaviour": " Excellent ",
        "authored_by": " Mrs Smith ", "notes": " Shared at parents evening ",
    })
    got = R.get(rep.report_id)
    assert got == rep
    assert (got.pupil_id, got.academic_year, got.term) == (p.pupil_id, AY, "Spring")
    assert (got.headline, got.summary, got.strengths, got.next_steps) == \
        ("A great term", "Settled well", "Reading", "Times tables")
    assert got.attendance_pct == 96.5
    assert (got.behaviour, got.authored_by, got.notes) == \
        ("Excellent", "Mrs Smith", "Shared at parents evening")
    assert got.status == "draft" and got.published_on is None
    assert got.created_at and got.updated_at


def test_create_blank_optional_fields_become_none():
    rep = _report(_pupil(), headline="   ", summary="", strengths=None,
                  next_steps="  ", attendance_pct="", behaviour=" ",
                  authored_by="", notes="   ", published_on="  ")
    assert (rep.headline, rep.summary, rep.strengths, rep.next_steps) == (None,) * 4
    assert (rep.attendance_pct, rep.behaviour, rep.authored_by, rep.notes,
            rep.published_on) == (None,) * 5


def test_create_status_defaults_and_normalises():
    p = _pupil()
    assert _report(p, term="Autumn", status="").status == "draft"
    assert _report(p, term="Spring", status=None).status == "draft"
    assert _report(p, term="Summer", status=" PUBLISHED ").status == "published"


@pytest.mark.parametrize("year", ["2025", "2025-26", "2025-2026"])
def test_create_accepts_academic_year_shapes(year):
    assert _report(_pupil(), year=year).academic_year == year


@pytest.mark.parametrize("value, expected", [(0, 0.0), ("100", 100.0), (87.25, 87.25)])
def test_create_attendance_bounds_inclusive(value, expected):
    assert _report(_pupil(), attendance_pct=value).attendance_pct == expected


def test_create_published_on_stored():
    rep = _report(_pupil(), status="published", published_on=" 2025-12-15 ")
    assert rep.published_on == "2025-12-15"


# ── create: validation ──

def test_create_requires_pupil_id():
    with pytest.raises(R.ValidationError, match="Pupil ID is required"):
        R.create({"pupil_id": "  ", "academic_year": AY, "term": "Autumn"})


def test_create_requires_academic_year():
    p = _pupil()
    with pytest.raises(R.ValidationError, match="Academic year is required"):
        R.create({"pupil_id": p.pupil_id, "academic_year": " ", "term": "Autumn"})


@pytest.mark.parametrize("year", ["25-26", "2025/26", "2025-6", "twenty", "2025-26a"])
def test_create_rejects_bad_academic_year(year):
    with pytest.raises(R.ValidationError, match="Academic year must look like"):
        _report(_pupil(), year=year)


def test_create_requires_term():
    with pytest.raises(R.ValidationError, match="Term is required"):
        _report(_pupil(), term="  ")


def test_create_rejects_unknown_term():
    with pytest.raises(R.ValidationError, match="Term must be one of Autumn, Spring, Summer"):
        _report(_pupil(), term="Winter")


def test_create_rejects_non_numeric_attendance():
    with pytest.raises(R.ValidationError, match="Attendance % must be a number"):
        _report(_pupil(), attendance_pct="ninety")


@pytest.mark.parametrize("value", [-0.1, "100.1", 250])
def test_create_rejects_attendance_out_of_range(value):
    with pytest.raises(R.ValidationError, match="between 0 and 100"):
        _report(_pupil(), attendance_pct=value)


def test_create_rejects_unknown_status():
    with pytest.raises(R.ValidationError, match="Status must be one of draft, published"):
        _report(_pupil(), status="archived")


@pytest.mark.parametrize("bad", ["2025/12/01", "01-12-2025", "2025-12-1"])
def test_create_rejects_bad_published_on(bad):
    with pytest.raises(R.ValidationError, match="Published-on date must be YYYY-MM-DD"):
        _report(_pupil(), published_on=bad)


def test_create_rejects_unknown_pupil():
    with pytest.raises(R.ValidationError, match="No pupil with id GHOST"):
        R.create({"pupil_id": "GHOST", "academic_year": AY, "term": "Autumn"})
    assert R.list_reports() == []


def test_create_rejects_duplicate_pupil_year_term():
    p = _pupil()
    first = _report(p)
    with pytest.raises(R.ValidationError,
                       match=rf"already exists \(#{first.report_id}\)"):
        _report(p, term="autumn")
    # same term in another year, or another term, is fine
    assert _report(p, year=PREV).term == "Autumn"
    assert _report(p, term="Spring").term == "Spring"
    # another pupil can have the same year/term
    assert _report(_pupil("Bob", "Brown")).academic_year == AY


# ── get ──

def test_get_missing_returns_none():
    assert R.get(999) is None


# ── update ──

def test_update_changes_only_given_fields():
    rep = _report(_pupil(), headline="Old", summary="Keep me", attendance_pct=90)
    up = R.update(rep.report_id, {"headline": " New ", "attendance_pct": "95"})
    assert up.headline == "New" and up.attendance_pct == 95.0
    assert up.summary == "Keep me"
    assert (up.pupil_id, up.academic_year, up.term, up.status) == \
        (rep.pupil_id, AY, "Autumn", "draft")
    assert R.get(rep.report_id) == up


def test_update_blank_clears_field():
    rep = _report(_pupil(), headline="Old", attendance_pct=90)
    up = R.update(rep.report_id, {"headline": "", "attendance_pct": None})
    assert up.headline is None and up.attendance_pct is None


def test_update_can_move_term_and_keep_own_slot():
    rep = _report(_pupil())
    # re-saving its own year/term is not a duplicate of itself
    assert R.update(rep.report_id, {"term": "Autumn"}).term == "Autumn"
    assert R.update(rep.report_id, {"term": "summer"}).term == "Summer"


def test_update_refuses_clash_with_another_report():
    p = _pupil()
    a = _report(p, term="Autumn")
    b = _report(p, term="Spring")
    with pytest.raises(R.ValidationError,
                       match=rf"Another report .* already exists \(#{a.report_id}\)"):
        R.update(b.report_id, {"term": "Autumn"})
    assert R.get(b.report_id).term == "Spring"


def test_update_unknown_report():
    with pytest.raises(R.ValidationError, match="No report #42"):
        R.update(42, {"headline": "x"})


def test_update_refuses_published_report():
    rep = _report(_pupil(), headline="Final")
    R.publish(rep.report_id, published_on="2025-12-12")
    with pytest.raises(R.ValidationError, match="revert to draft before editing"):
        R.update(rep.report_id, {"headline": "Changed"})
    assert R.get(rep.report_id).headline == "Final"


def test_update_runs_the_same_validation():
    rep = _report(_pupil())
    with pytest.raises(R.ValidationError, match="Term must be one of"):
        R.update(rep.report_id, {"term": "Winter"})
    with pytest.raises(R.ValidationError, match="between 0 and 100"):
        R.update(rep.report_id, {"attendance_pct": 101})
    with pytest.raises(R.ValidationError, match="Academic year must look like"):
        R.update(rep.report_id, {"academic_year": "2025/26"})
    with pytest.raises(R.ValidationError, match="Pupil ID is required"):
        R.update(rep.report_id, {"pupil_id": ""})
    with pytest.raises(R.ValidationError, match="No pupil with id GHOST"):
        R.update(rep.report_id, {"pupil_id": "GHOST"})
    assert R.get(rep.report_id) == rep


def test_update_can_reassign_to_another_pupil():
    rep = _report(_pupil())
    other = _pupil("Bob", "Brown")
    assert R.update(rep.report_id, {"pupil_id": other.pupil_id}).pupil_id == other.pupil_id


# ── publish / revert_to_draft ──

def test_publish_with_explicit_date():
    rep = _report(_pupil())
    pub = R.publish(rep.report_id, published_on=" 2025-12-12 ")
    assert (pub.status, pub.published_on) == ("published", "2025-12-12")
    assert R.get(rep.report_id) == pub


def test_publish_defaults_to_database_today():
    rep = _report(_pupil())
    before = datetime.now(timezone.utc).date()
    pub = R.publish(rep.report_id)
    after = datetime.now(timezone.utc).date()
    allowed = {(before + timedelta(days=d)).isoformat()
               for d in range((after - before).days + 1)}
    assert pub.published_on in allowed


def test_publish_blank_date_falls_back_to_today():
    pub = R.publish(_report(_pupil()).report_id, published_on="")
    assert pub.is_published and R._DOB_RE.match(pub.published_on)


def test_publish_rejects_bad_date():
    rep = _report(_pupil())
    with pytest.raises(R.ValidationError, match="Published-on date must be YYYY-MM-DD"):
        R.publish(rep.report_id, published_on="12/12/2025")
    assert R.get(rep.report_id).is_draft


def test_publish_already_published_is_a_noop():
    rep = _report(_pupil())
    first = R.publish(rep.report_id, published_on="2025-12-12")
    again = R.publish(rep.report_id, published_on="2026-01-05")
    assert again == first and again.published_on == "2025-12-12"


def test_publish_unknown_report():
    with pytest.raises(R.ValidationError, match="No report #7"):
        R.publish(7)


def test_revert_clears_published_date_and_allows_editing():
    rep = _report(_pupil())
    R.publish(rep.report_id, published_on="2025-12-12")
    back = R.revert_to_draft(rep.report_id)
    assert (back.status, back.published_on) == ("draft", None)
    assert R.update(rep.report_id, {"headline": "Amended"}).headline == "Amended"


def test_revert_draft_is_a_noop():
    rep = _report(_pupil(), headline="x")
    assert R.revert_to_draft(rep.report_id) == rep


def test_revert_unknown_report():
    with pytest.raises(R.ValidationError, match="No report #9"):
        R.revert_to_draft(9)


# ── delete ──

def test_delete_removes_once():
    rep = _report(_pupil())
    assert R.delete(rep.report_id) is True
    assert R.get(rep.report_id) is None
    assert R.delete(rep.report_id) is False


def test_delete_missing_returns_false():
    assert R.delete(12345) is False


def test_deleting_pupil_cascades_to_reports():
    p = _pupil()
    rep = _report(p)
    assert P.delete_pupil(p.pupil_id) is True
    assert R.get(rep.report_id) is None


# ── list_reports ──

def test_list_reports_empty():
    assert R.list_reports() == []


def test_list_reports_order_and_pupil_attached():
    a, b = _pupil("A", "A", "3"), _pupil("B", "B", "5")
    r1 = _report(a, year=PREV, term="Summer")
    r2 = _report(a, term="Spring")
    r3 = _report(b, term="Autumn")
    r4 = _report(a, term="Autumn")
    rows = R.list_reports()
    # academic_year DESC, then term, then pupil_id
    autumn = sorted([r3, r4], key=lambda r: r.pupil_id)
    assert [r.report_id for r, _ in rows] == \
        [autumn[0].report_id, autumn[1].report_id, r2.report_id, r1.report_id]
    for rec, pupil in rows:
        assert pupil is not None and pupil.pupil_id == rec.pupil_id


def test_list_reports_filters():
    a, b = _pupil("A", "A", "3"), _pupil("B", "B", "5")
    ra = _report(a, term="Autumn")
    rb = _report(b, term="Autumn")
    rs = _report(a, term="Spring")
    rp = _report(a, year=PREV, term="Autumn")
    R.publish(rb.report_id, published_on="2025-12-12")

    def ids(**kw):
        return sorted(r.report_id for r, _ in R.list_reports(**kw))

    assert ids(academic_year=f" {AY} ") == sorted([ra.report_id, rb.report_id, rs.report_id])
    assert ids(academic_year=PREV) == [rp.report_id]
    assert ids(term="Spring") == [rs.report_id]
    assert ids(status="published") == [rb.report_id]
    assert ids(status="draft") == sorted([ra.report_id, rs.report_id, rp.report_id])
    assert ids(pupil_id=f" {b.pupil_id} ") == [rb.report_id]
    assert ids(year_group="3") == sorted([ra.report_id, rs.report_id, rp.report_id])
    assert ids(year_group="6") == []
    assert ids(academic_year=AY, term="Autumn", status="draft", year_group="3") == \
        [ra.report_id]
    assert ids(academic_year="2030-31") == []


@pytest.mark.parametrize("kw, msg", [
    ({"term": "autumn"}, "Term filter must be one of"),
    ({"status": "Draft"}, "Status filter must be one of"),
    ({"year_group": "7"}, "Year filter must be one of R, 1, 2, 3, 4, 5, 6"),
])
def test_list_reports_rejects_bad_filters(kw, msg):
    with pytest.raises(R.ValidationError, match=msg):
        R.list_reports(**kw)


# ── list_for_pupil ──

def test_list_for_pupil_orders_newest_year_then_term():
    p = _pupil()
    old = _report(p, year=PREV, term="Summer")
    summer = _report(p, term="Summer")
    autumn = _report(p, term="Autumn")
    _report(_pupil("Other", "Child"))
    assert [r.report_id for r in R.list_for_pupil(p.pupil_id)] == \
        [autumn.report_id, summer.report_id, old.report_id]


def test_list_for_pupil_empty_and_unknown():
    assert R.list_for_pupil(_pupil().pupil_id) == []
    with pytest.raises(R.ValidationError, match="No pupil with id GHOST"):
        R.list_for_pupil("GHOST")


# ── summary ──

def test_summary_empty():
    assert R.summary() == {"total": 0, "draft": 0, "published": 0, "published_pct": 0.0,
                           "average_attendance": None, "attendance_count": 0}


def test_summary_figures_and_filters():
    a, b, c = _pupil("A", "A"), _pupil("B", "B"), _pupil("C", "C")
    ra = _report(a, attendance_pct=90)
    _report(b, attendance_pct=95)
    _report(c)
    _report(a, term="Spring", attendance_pct=80)
    _report(a, year=PREV, attendance_pct=100)
    R.publish(ra.report_id, published_on="2025-12-12")

    autumn = R.summary(academic_year=AY, term="Autumn")
    assert (autumn["total"], autumn["draft"], autumn["published"]) == (3, 2, 1)
    assert autumn["published_pct"] == pytest.approx(100 / 3)
    assert autumn["average_attendance"] == pytest.approx(92.5)
    assert autumn["attendance_count"] == 2

    year = R.summary(academic_year=AY)
    assert (year["total"], year["published"]) == (4, 1)
    assert year["published_pct"] == pytest.approx(25.0)
    assert year["average_attendance"] == pytest.approx((90 + 95 + 80) / 3)

    everything = R.summary()
    assert everything["total"] == 5 and everything["attendance_count"] == 4
    assert everything["average_attendance"] == pytest.approx(91.25)


def test_summary_no_attendance_recorded():
    _report(_pupil())
    s = R.summary()
    assert s["average_attendance"] is None and s["attendance_count"] == 0
    assert s["published_pct"] == 0.0


def test_summary_rejects_bad_term():
    with pytest.raises(R.ValidationError, match="Term filter must be one of"):
        R.summary(term="Winter")


# ── known_years ──

def test_known_years():
    assert R.known_years() == []
    a, b = _pupil("A", "A"), _pupil("B", "B")
    _report(a, year=PREV)
    _report(a, year=AY)
    _report(b, year=AY)
    _report(b, year="2023-24", term="Summer")
    assert R.known_years() == [AY, PREV, "2023-24"]

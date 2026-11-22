"""Pupil Premium records and interventions
(systems.primary.domain.finance.pupil_premium.pupil_premium).

Funding and spend are pounds held as floats (REAL columns), not pence.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.finance.pupil_premium import pupil_premium as PP
from education_system.systems.primary.domain.learners.pupils import pupils as P

AY = "2025/26"

_n = 0


def _pupil(year="3", last=None):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Kid{_n}", "last_name": last or f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2018-01-01"})


def _record(pupil_id, **extra):
    return PP.upsert({"pupil_id": pupil_id, "academic_year": AY,
                      "funding_amount": 1455, "start_date": "2025-09-01", **extra})


def _int(pp_id, **extra):
    return PP.add_intervention({"pp_id": pp_id, "title": "Reading tutor",
                                "spend": 200, "start_date": "2025-10-01", **extra})


# ── records: create / read ──

def test_upsert_inserts_with_defaults_and_pupil_join():
    p = _pupil(year="4")
    r = PP.upsert({"pupil_id": p.pupil_id, "academic_year": AY,
                   "start_date": "2025-09-01", "keyworker": "  Mrs B ",
                   "notes": "  "})
    assert r.pupil_id == p.pupil_id
    assert r.category == PP.DEFAULT_CATEGORY == "Ever 6 FSM"
    assert r.status == PP.DEFAULT_STATUS == "Eligible"
    assert r.funding_amount is None
    assert (r.start_date, r.end_date) == ("2025-09-01", None)
    assert r.keyworker == "Mrs B"
    assert r.notes is None
    assert r.pupil_name == f"{p.first_name} {p.last_name}"
    assert r.pupil_year == "4"
    assert PP.get(r.pp_id) == r
    assert PP.get_for(f" {p.pupil_id} ", f" {AY} ") == r


def test_upsert_same_pupil_and_year_updates_in_place():
    p = _pupil()
    first = _record(p.pupil_id, category="Service child")
    second = _record(p.pupil_id, category="Post-LAC", funding_amount="2570.5",
                     status="Reviewing")
    assert second.pp_id == first.pp_id
    assert (second.category, second.status, second.funding_amount) == (
        "Post-LAC", "Reviewing", 2570.5)
    assert len(PP.list_records()) == 1
    other_year = _record(p.pupil_id, academic_year="2026/27")
    assert other_year.pp_id != first.pp_id


def test_upsert_blank_start_date_defaults_to_today():
    p = _pupil()
    r = PP.upsert({"pupil_id": p.pupil_id, "academic_year": AY})
    assert r.start_date == dt.date.today().isoformat()


def test_get_missing_is_none():
    assert PP.get(404) is None
    assert PP.get_for("nobody", AY) is None


# ── records: validation ──

def test_record_pupil_required_and_must_exist():
    with pytest.raises(PP.ValidationError, match="Pupil ID is required"):
        PP.upsert({"pupil_id": " ", "academic_year": AY})
    with pytest.raises(PP.ValidationError, match="No pupil with id GHOST"):
        PP.upsert({"pupil_id": "GHOST", "academic_year": AY})


def test_record_academic_year_required_and_format():
    p = _pupil()
    with pytest.raises(PP.ValidationError, match="Academic year is required"):
        PP.upsert({"pupil_id": p.pupil_id})
    with pytest.raises(PP.ValidationError, match="YYYY/YY"):
        _record(p.pupil_id, academic_year="2025-26")


def test_record_category_and_status_must_be_listed():
    p = _pupil()
    with pytest.raises(PP.ValidationError, match="Category must be one of"):
        _record(p.pupil_id, category="Rich")
    with pytest.raises(PP.ValidationError, match="Status must be one of"):
        _record(p.pupil_id, status="Paid")


def test_record_funding_amount_range():
    p = _pupil()
    with pytest.raises(PP.ValidationError, match="must be a number"):
        _record(p.pupil_id, funding_amount="lots")
    with pytest.raises(PP.ValidationError, match="between 0 and 100000"):
        _record(p.pupil_id, funding_amount=-1)
    with pytest.raises(PP.ValidationError, match="between 0 and 100000"):
        _record(p.pupil_id, funding_amount=100000.01)
    assert _record(p.pupil_id, funding_amount=100000).funding_amount == 100000.0
    assert _record(p.pupil_id, funding_amount=0).funding_amount == 0.0


def test_record_dates_checked():
    p = _pupil()
    with pytest.raises(PP.ValidationError, match="Start date must be YYYY-MM-DD"):
        _record(p.pupil_id, start_date="1/9/2025")
    with pytest.raises(PP.ValidationError, match="End date is not a real date"):
        _record(p.pupil_id, end_date="2026-02-30")
    with pytest.raises(PP.ValidationError, match="End date cannot be before"):
        _record(p.pupil_id, end_date="2025-08-31")
    assert _record(p.pupil_id, end_date="2026-07-20").end_date == "2026-07-20"


# ── records: listing ──

def test_list_records_filters_and_order():
    a = _pupil(year="2", last="Zed")
    b = _pupil(year="2", last="Able")
    c = _pupil(year="5", last="Mid")
    ra = _record(a.pupil_id, category="Service child")
    rb = _record(b.pupil_id, status="Provisional")
    rc = _record(c.pupil_id)
    old = _record(a.pupil_id, academic_year="2024/25")
    # academic_year DESC, then year group, then surname
    assert [r.pp_id for r in PP.list_records()] == [rb.pp_id, ra.pp_id, rc.pp_id, old.pp_id]
    assert [r.pp_id for r in PP.list_records(year_group="5")] == [rc.pp_id]
    assert [r.pp_id for r in PP.list_records(academic_year="2024/25")] == [old.pp_id]
    assert [r.pp_id for r in PP.list_records(category="Service child")] == [ra.pp_id]
    assert [r.pp_id for r in PP.list_records(status="Provisional")] == [rb.pp_id]
    assert [r.pp_id for r in PP.list_records(pupil_id=a.pupil_id)] == [ra.pp_id, old.pp_id]


def test_list_records_filter_validation_and_empty():
    assert PP.list_records() == []
    with pytest.raises(PP.ValidationError, match="Year filter"):
        PP.list_records(year_group="7")
    with pytest.raises(PP.ValidationError, match="Category filter"):
        PP.list_records(category="x")
    with pytest.raises(PP.ValidationError, match="Status filter"):
        PP.list_records(status="x")


# ── records: delete ──

def test_delete_record_cascades_interventions():
    p = _pupil()
    r = _record(p.pupil_id)
    i = _int(r.pp_id)
    assert PP.delete(r.pp_id) is True
    assert PP.get(r.pp_id) is None
    assert PP.get_intervention(i.intervention_id) is None
    assert PP.delete(r.pp_id) is False


# ── interventions ──

def test_add_intervention_stores_values_and_defaults():
    r = _record(_pupil().pupil_id)
    i = PP.add_intervention({"pp_id": str(r.pp_id), "title": "  Maths club ",
                             "start_date": "2025-10-01", "description": " "})
    assert i.pp_id == r.pp_id
    assert i.title == "Maths club"
    assert i.description is None
    assert i.spend == 0.0
    assert i.status == PP.DEFAULT_INT_STATUS == "Planned"
    assert i.impact_rating == "Not yet assessed"
    assert PP.get_intervention(i.intervention_id) == i


def test_intervention_pp_id_rules():
    with pytest.raises(PP.ValidationError, match="PP record ID is required"):
        PP.add_intervention({"title": "X"})
    with pytest.raises(PP.ValidationError, match="must be a number"):
        PP.add_intervention({"pp_id": "abc", "title": "X"})
    with pytest.raises(PP.ValidationError, match="No PP record #99"):
        PP.add_intervention({"pp_id": 99, "title": "X"})


def test_intervention_title_rules():
    r = _record(_pupil().pupil_id)
    with pytest.raises(PP.ValidationError, match="Title is required"):
        _int(r.pp_id, title="  ")
    with pytest.raises(PP.ValidationError, match="120 chars"):
        _int(r.pp_id, title="x" * 121)
    assert _int(r.pp_id, title="y" * 120).title == "y" * 120


def test_intervention_spend_range():
    r = _record(_pupil().pupil_id)
    with pytest.raises(PP.ValidationError, match="Spend must be a number"):
        _int(r.pp_id, spend="ten")
    with pytest.raises(PP.ValidationError, match="between 0 and 100000"):
        _int(r.pp_id, spend=-0.01)
    with pytest.raises(PP.ValidationError, match="between 0 and 100000"):
        _int(r.pp_id, spend=100001)


def test_intervention_dates_status_and_impact():
    r = _record(_pupil().pupil_id)
    with pytest.raises(PP.ValidationError, match="Start date must be YYYY-MM-DD"):
        _int(r.pp_id, start_date="Oct 1")
    with pytest.raises(PP.ValidationError, match="End date cannot be before"):
        _int(r.pp_id, end_date="2025-09-30")
    with pytest.raises(PP.ValidationError, match="Status must be one of"):
        _int(r.pp_id, status="Done")
    with pytest.raises(PP.ValidationError, match="Impact rating must be one of"):
        _int(r.pp_id, impact_rating="Huge")


def test_complete_intervention_needs_an_impact_rating():
    r = _record(_pupil().pupil_id)
    with pytest.raises(PP.ValidationError, match="Impact rating must be set"):
        _int(r.pp_id, status="Complete")
    done = _int(r.pp_id, status="Complete", impact_rating="High")
    assert (done.status, done.impact_rating) == ("Complete", "High")


def test_list_interventions_order_and_empty():
    r = _record(_pupil().pupil_id)
    assert PP.list_interventions(r.pp_id) == []
    a = _int(r.pp_id, start_date="2025-09-10")
    b = _int(r.pp_id, start_date="2025-11-01")
    c = _int(r.pp_id, start_date="2025-11-01")
    assert [i.intervention_id for i in PP.list_interventions(r.pp_id)] == [
        c.intervention_id, b.intervention_id, a.intervention_id]


def test_update_intervention_merges_fields():
    r = _record(_pupil().pupil_id)
    i = _int(r.pp_id, notes="first")
    up = PP.update_intervention(i.intervention_id, {"spend": "350.75", "status": "Active"})
    assert (up.spend, up.status, up.title, up.notes) == (350.75, "Active", "Reading tutor", "first")
    assert PP.get_intervention(i.intervention_id).spend == 350.75


def test_update_intervention_refusals():
    with pytest.raises(PP.ValidationError, match="No PP intervention #12"):
        PP.update_intervention(12, {"title": "x"})
    r = _record(_pupil().pupil_id)
    i = _int(r.pp_id)
    with pytest.raises(PP.ValidationError, match="Impact rating must be set"):
        PP.update_intervention(i.intervention_id, {"status": "Complete"})
    assert PP.get_intervention(i.intervention_id).status == "Planned"


def test_delete_intervention():
    r = _record(_pupil().pupil_id)
    i = _int(r.pp_id)
    assert PP.delete_intervention(i.intervention_id) is True
    assert PP.get_intervention(i.intervention_id) is None
    assert PP.delete_intervention(i.intervention_id) is False


# ── summaries ──

def test_record_summary_figures():
    r = _record(_pupil().pupil_id, funding_amount=1000)
    _int(r.pp_id, spend=250.5, status="Active")
    _int(r.pp_id, spend=100.25, status="Complete", impact_rating="High")
    _int(r.pp_id, spend=0)
    s = PP.record_summary(r.pp_id)
    assert s["record"].pp_id == r.pp_id
    assert len(s["interventions"]) == 3
    assert s["total_spend"] == 350.75
    assert s["remaining"] == 649.25
    assert s["by_status"] == {"Active": 1, "Complete": 1, "Planned": 1}
    assert s["by_impact"] == {"Not yet assessed": 2, "High": 1}


def test_record_summary_without_funding_has_no_remaining():
    r = PP.upsert({"pupil_id": _pupil().pupil_id, "academic_year": AY,
                   "start_date": "2025-09-01"})
    _int(r.pp_id, spend=50)
    s = PP.record_summary(r.pp_id)
    assert (s["total_spend"], s["remaining"]) == (50.0, None)


def test_record_summary_missing_refused():
    with pytest.raises(PP.ValidationError, match="No PP record #7"):
        PP.record_summary(7)


def test_cohort_summary_empty():
    assert PP.cohort_summary() == {
        "total": 0, "by_category": {}, "by_status": {}, "total_funding": 0,
        "interventions": 0, "total_spend": 0, "remaining": 0}


def test_cohort_summary_figures_and_filters():
    a = _pupil(year="1")
    b = _pupil(year="6")
    ra = _record(a.pupil_id, funding_amount=1455)
    rb = _record(b.pupil_id, funding_amount=2570, category="LAC (Looked-after child)",
                 status="Provisional")
    _record(a.pupil_id, academic_year="2024/25", funding_amount=999)
    _int(ra.pp_id, spend=300)
    _int(rb.pp_id, spend=120.5)
    _int(rb.pp_id, spend=79.5)
    s = PP.cohort_summary(academic_year=AY)
    assert s["total"] == 2
    assert s["by_category"] == {"Ever 6 FSM": 1, "LAC (Looked-after child)": 1}
    assert s["by_status"] == {"Eligible": 1, "Provisional": 1}
    assert s["total_funding"] == 4025.0
    assert s["interventions"] == 3
    assert s["total_spend"] == 500.0
    assert s["remaining"] == 3525.0
    y6 = PP.cohort_summary(year_group="6", academic_year=AY)
    assert (y6["total"], y6["total_funding"], y6["total_spend"]) == (1, 2570.0, 200.0)
    everything = PP.cohort_summary()
    assert (everything["total"], everything["total_funding"]) == (3, 5024.0)

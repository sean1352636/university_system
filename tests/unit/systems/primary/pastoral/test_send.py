"""SEND register (systems.primary.domain.pastoral.send.send)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.send import send as S

EHCP = "EHCP (Education, Health, Care Plan)"
COG = "Cognition and learning"
SEMH = "Social, emotional and mental health"
_n = 0


def _pupil(year="3", last=None):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": last or f"Test{_n}",
                           "year_group": year, "date_of_birth": "2018-01-01"})


def _rec(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "academic_year": "2025/26",
            "start_date": "2025-09-08", **extra}
    return S.upsert(data)


# ── create / read ────────────────────────────────────────────────────

def test_upsert_inserts_with_defaults():
    ava = _pupil()
    r = _rec(ava, senco="Mrs Senco", parent_email="mum@example.org", diagnosis=" ")
    assert r.send_id > 0
    assert (r.provision_stage, r.primary_need, r.status) == ("Monitoring", COG, "Active")
    assert r.secondary_need is None and r.diagnosis is None
    assert (r.senco, r.parent_email) == ("Mrs Senco", "mum@example.org")
    assert r.pupil_name == ava.full_name and r.pupil_year == "3"
    assert S.get(r.send_id) == r
    assert S.get_for(ava.pupil_id, "2025/26") == r
    assert S.get_for(f" {ava.pupil_id} ", " 2025/26 ") == r


def test_upsert_same_pupil_and_year_updates_in_place():
    ava = _pupil()
    first = _rec(ava, senco="Mrs A")
    again = _rec(ava, provision_stage="SEN Support", senco="Mr B")
    assert again.send_id == first.send_id
    assert (again.provision_stage, again.senco) == ("SEN Support", "Mr B")
    other_year = _rec(ava, academic_year="2026/27", start_date="2026-09-07")
    assert other_year.send_id != first.send_id
    assert len(S.list_records(pupil_id=ava.pupil_id)) == 2


def test_start_date_defaults_to_today():
    assert _rec(_pupil(), start_date=None).start_date == dt.date.today().isoformat()


def test_ehcp_stage_without_reference_is_allowed():
    r = _rec(_pupil(), provision_stage=EHCP)
    assert r.provision_stage == EHCP and r.ehcp_reference is None


def test_empty_database_reads():
    assert S.get(1) is None
    assert S.get_for("P0001", "2025/26") is None
    assert S.list_records() == []
    assert S.get_review(1) is None and S.list_reviews(1) == []


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("bad, msg", [
    ({"pupil_id": ""}, "Pupil ID is required"),
    ({"pupil_id": "GHOST"}, "No pupil with id GHOST"),
    ({"academic_year": ""}, "Academic year is required"),
    ({"academic_year": "25/26"}, "YYYY/YY"),
    ({"provision_stage": "EHCP"}, "Provision stage must be one of"),
    ({"primary_need": "Speech"}, "Primary need must be one of"),
    ({"secondary_need": "Speech"}, "Secondary need must be one of"),
    ({"secondary_need": COG}, "Secondary need cannot equal primary need"),
    ({"status": "Closed"}, "Status must be one of"),
    ({"parent_email": "not-an-email"}, "Parent email is not a valid address"),
    ({"start_date": "2025/09/08"}, "Start date must be YYYY-MM-DD"),
    ({"start_date": "2025-13-01"}, "Start date is not a real date"),
    ({"next_review_date": "2025-09-01"}, "Next review date cannot be before start date"),
])
def test_record_validation(bad, msg):
    ava = _pupil()
    with pytest.raises(S.ValidationError, match=msg):
        _rec(ava, **bad)


def test_secondary_need_differs_from_primary_accepted():
    r = _rec(_pupil(), primary_need=SEMH, secondary_need=COG)
    assert (r.primary_need, r.secondary_need) == (SEMH, COG)


# ── listing ──────────────────────────────────────────────────────────

def test_list_sorted_by_year_desc_then_year_group_then_name():
    y5 = _pupil("5", last="Adams")
    y2b = _pupil("2", last="Brown")
    y2a = _pupil("2", last="Abbot")
    a = _rec(y5)
    b = _rec(y2b)
    c = _rec(y2a)
    old = _rec(y2a, academic_year="2024/25", start_date="2024-09-02")
    assert [r.send_id for r in S.list_records()] == [c.send_id, b.send_id, a.send_id, old.send_id]


def test_list_filters():
    ava, ben = _pupil("1"), _pupil("6")
    a = _rec(ava, provision_stage="SEN Support", primary_need=SEMH)
    b = _rec(ben, status="On hold", academic_year="2024/25", start_date="2024-09-02")
    assert [r.send_id for r in S.list_records(year_group="1")] == [a.send_id]
    assert [r.send_id for r in S.list_records(academic_year="2024/25")] == [b.send_id]
    assert [r.send_id for r in S.list_records(provision_stage="SEN Support")] == [a.send_id]
    assert [r.send_id for r in S.list_records(primary_need=SEMH)] == [a.send_id]
    assert [r.send_id for r in S.list_records(status="On hold")] == [b.send_id]
    assert [r.send_id for r in S.list_records(pupil_id=ben.pupil_id)] == [b.send_id]


@pytest.mark.parametrize("kw, msg", [
    ({"year_group": "Y3"}, "Year filter"), ({"provision_stage": "x"}, "Stage filter"),
    ({"primary_need": "x"}, "Need filter"), ({"status": "x"}, "Status filter")])
def test_list_filter_validation(kw, msg):
    with pytest.raises(S.ValidationError, match=msg):
        S.list_records(**kw)


# ── delete ───────────────────────────────────────────────────────────

def test_delete_cascades_reviews():
    r = _rec(_pupil())
    rev = S.add_review({"send_id": r.send_id, "review_date": "2025-10-01"})
    assert S.delete(r.send_id) is True
    assert S.get(r.send_id) is None and S.get_review(rev.review_id) is None
    assert S.delete(r.send_id) is False


# ── reviews ──────────────────────────────────────────────────────────

def test_add_review_defaults_mirrors_next_date_and_orders():
    r = _rec(_pupil())
    r1 = S.add_review({"send_id": r.send_id, "review_date": "2025-10-01",
                       "reviewer": "SENCo", "adjustments": "Visual timetable",
                       "next_review_date": "2026-01-10"})
    assert (r1.outcome, r1.adjustments) == ("Continue", "Visual timetable")
    assert S.get(r.send_id).next_review_date == "2026-01-10"
    r2 = S.add_review({"send_id": str(r.send_id), "review_date": "2026-01-10",
                       "outcome": "Escalate"})
    assert S.get(r.send_id).next_review_date == "2026-01-10"
    assert [x.review_id for x in S.list_reviews(r.send_id)] == [r2.review_id, r1.review_id]
    assert S.delete_review(r2.review_id) is True and S.delete_review(r2.review_id) is False
    assert [x.review_id for x in S.list_reviews(r.send_id)] == [r1.review_id]


def test_review_date_defaults_to_today():
    r = _rec(_pupil())
    assert S.add_review({"send_id": r.send_id}).review_date == dt.date.today().isoformat()


@pytest.mark.parametrize("bad, msg", [
    ({"send_id": ""}, "SEND record ID is required"),
    ({"send_id": "x"}, "SEND record ID must be a number"),
    ({"send_id": 777}, "No SEND record #777"),
    ({"outcome": "Celebrate"}, "Outcome must be one of"),
    ({"review_date": "01-10-2025"}, "Review date must be YYYY-MM-DD"),
    ({"next_review_date": "2025-09-30"}, "Next review date cannot be before review date"),
])
def test_review_validation(bad, msg):
    r = _rec(_pupil())
    with pytest.raises(S.ValidationError, match=msg):
        S.add_review({"send_id": r.send_id, "review_date": "2025-10-01", **bad})


# ── summaries ────────────────────────────────────────────────────────

def test_record_summary():
    r = _rec(_pupil())
    for day, outcome in (("2025-10-01", "Continue"), ("2025-12-01", "Adjust"),
                         ("2025-11-01", "Continue")):
        S.add_review({"send_id": r.send_id, "review_date": day, "outcome": outcome})
    s = S.record_summary(r.send_id)
    assert s["record"] == S.get(r.send_id)
    assert s["review_count"] == 3
    assert s["by_outcome"] == {"Continue": 2, "Adjust": 1}
    assert s["last_review"] == "2025-12-01"
    with pytest.raises(S.ValidationError, match="No SEND record #404"):
        S.record_summary(404)


def test_record_summary_no_reviews():
    s = S.record_summary(_rec(_pupil()).send_id)
    assert (s["review_count"], s["by_outcome"], s["last_review"]) == (0, {}, None)


def test_cohort_summary_counts_ehcp():
    a, b, c = _pupil("2"), _pupil("2"), _pupil("4")
    _rec(a, provision_stage=EHCP, ehcp_reference="EHC-1")
    _rec(b, provision_stage="EHCP assessment in progress", primary_need=SEMH)
    _rec(c, provision_stage="SEN Support", status="Discharged",
         academic_year="2024/25", start_date="2024-09-02")
    s = S.cohort_summary()
    assert s["total"] == 3 and s["ehcp_count"] == 2
    assert s["by_stage"] == {EHCP: 1, "EHCP assessment in progress": 1, "SEN Support": 1}
    assert s["by_primary_need"] == {COG: 2, SEMH: 1}
    assert s["by_status"] == {"Active": 2, "Discharged": 1}
    assert S.cohort_summary(year_group="2")["total"] == 2
    assert S.cohort_summary(academic_year="2024/25")["ehcp_count"] == 0
    assert S.cohort_summary(year_group="R")["total"] == 0


def test_overdue_reviews_active_only():
    a, b, c = _pupil(), _pupil(), _pupil()
    due = _rec(a, next_review_date="2025-10-01")
    _rec(b, next_review_date="2025-10-01", status="On hold")
    _rec(c, next_review_date="2025-12-01")
    assert [r.send_id for r in S.overdue_reviews("2025-11-01")] == [due.send_id]
    assert S.overdue_reviews("2025-10-01") == []

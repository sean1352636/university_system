"""Behaviour log (systems.primary.domain.pastoral.behaviour.behaviour)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.subjects import subjects as S
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.behaviour import behaviour as B

TODAY = dt.date.today().isoformat()


def _pupil(first="Ada", last="Lovelace", year="3"):
    return P.create_pupil({"first_name": first, "last_name": last,
                           "year_group": year, "date_of_birth": "2018-01-01"})


def _log(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "incident_type": "Achievement",
            "description": "Great work", "incident_date": "2026-10-05", **extra}
    return B.log_incident(data)


# ── log_incident: happy path ─────────────────────────────────────────

def test_log_positive_incident_stores_values_and_joins_pupil():
    p = _pupil()
    rec = _log(p, incident_time="09:15", location="Class 3",
               raised_by="Ms Smith", action_taken="Sticker", notes="n1",
               severity="Medium", points=5)
    assert rec.incident_id > 0
    assert rec.pupil_id == p.pupil_id
    assert rec.incident_date == "2026-10-05"
    assert rec.incident_time == "09:15"
    assert rec.location == "Class 3"
    assert rec.polarity == "positive"
    assert rec.points == 5
    assert rec.severity == "Medium"
    assert rec.status == "Open"
    assert rec.raised_by == "Ms Smith"
    assert rec.action_taken == "Sticker"
    assert rec.notes == "n1"
    assert rec.pupil_name == "Ada Lovelace"
    assert rec.pupil_year == "3"
    assert rec.subject_id is None and rec.subject_code is None


def test_default_points_follow_polarity():
    p = _pupil()
    assert _log(p).points == 1
    assert _log(p, incident_type="Disruption").points == -1


def test_negative_type_sets_negative_polarity():
    p = _pupil()
    rec = _log(p, incident_type="Bullying", points=-5)
    assert rec.polarity == "negative"
    assert rec.points == -5


def test_blank_date_defaults_to_today_and_blank_optionals_are_none():
    p = _pupil()
    rec = _log(p, incident_date="", location="  ", notes="")
    assert rec.incident_date == TODAY
    assert rec.location is None
    assert rec.notes is None
    assert rec.incident_time is None


def test_subject_is_linked_and_code_joined():
    p = _pupil()
    sub = S.create({"code": "MATH", "name": "Maths", "key_stage": "All"})
    rec = _log(p, subject_id=str(sub.subject_id))
    assert rec.subject_id == sub.subject_id
    assert rec.subject_code == "MATH"


# ── validation ───────────────────────────────────────────────────────

def test_pupil_id_required():
    with pytest.raises(B.ValidationError, match="Pupil ID is required"):
        B.log_incident({"incident_type": "Achievement", "description": "x"})


def test_unknown_pupil_refused():
    with pytest.raises(B.ValidationError, match="No pupil with id"):
        B.log_incident({"pupil_id": "NOPE", "incident_type": "Achievement",
                        "description": "x"})


def test_bad_date_format_refused():
    with pytest.raises(B.ValidationError, match="YYYY-MM-DD"):
        _log(_pupil(), incident_date="05/10/2026")


def test_impossible_date_refused():
    with pytest.raises(B.ValidationError, match="not a real date"):
        _log(_pupil(), incident_date="2026-02-30")


@pytest.mark.parametrize("bad", ["9:15", "24:00", "12:60", "noon"])
def test_bad_time_refused(bad):
    with pytest.raises(B.ValidationError, match="HH:MM"):
        _log(_pupil(), incident_time=bad)


def test_non_numeric_subject_refused():
    with pytest.raises(B.ValidationError, match="Subject ID must be a number"):
        _log(_pupil(), subject_id="abc")


def test_unknown_subject_refused():
    with pytest.raises(B.ValidationError, match="No subject #999"):
        _log(_pupil(), subject_id=999)


def test_incident_type_required():
    with pytest.raises(B.ValidationError, match="Incident type is required"):
        _log(_pupil(), incident_type="")


def test_unknown_incident_type_refused():
    with pytest.raises(B.ValidationError, match="Incident type must be one of"):
        _log(_pupil(), incident_type="Fighting")


def test_points_must_be_whole_number():
    with pytest.raises(B.ValidationError, match="whole number"):
        _log(_pupil(), points="1.5")


@pytest.mark.parametrize("pts", [101, -101])
def test_points_range(pts):
    itype = "Achievement" if pts > 0 else "Disruption"
    with pytest.raises(B.ValidationError, match="between -100 and 100"):
        _log(_pupil(), incident_type=itype, points=pts)


def test_points_bounds_inclusive():
    p = _pupil()
    assert _log(p, points=100).points == 100
    assert _log(p, incident_type="Damage", points=-100).points == -100
    assert _log(p, points=0).points == 0


def test_positive_type_cannot_have_negative_points():
    with pytest.raises(B.ValidationError, match="Positive incident types"):
        _log(_pupil(), points=-1)


def test_negative_type_cannot_have_positive_points():
    with pytest.raises(B.ValidationError, match="Negative incident types"):
        _log(_pupil(), incident_type="Lateness", points=2)


def test_unknown_severity_refused():
    with pytest.raises(B.ValidationError, match="Severity must be one of"):
        _log(_pupil(), severity="Extreme")


def test_description_required():
    with pytest.raises(B.ValidationError, match="Description is required"):
        _log(_pupil(), description="   ")


def test_description_max_500():
    p = _pupil()
    assert len(_log(p, description="x" * 500).description) == 500
    with pytest.raises(B.ValidationError, match="500 chars"):
        _log(p, description="x" * 501)


def test_unknown_status_refused():
    with pytest.raises(B.ValidationError, match="Status must be one of"):
        _log(_pupil(), status="Closed")


# ── get / list ───────────────────────────────────────────────────────

def test_get_missing_is_none():
    assert B.get(12345) is None


def test_list_empty_database():
    assert B.list_incidents() == []


def test_list_sorted_newest_first_then_time_then_id():
    p = _pupil()
    a = _log(p, incident_date="2026-10-01")
    b = _log(p, incident_date="2026-10-03", incident_time="09:00")
    c = _log(p, incident_date="2026-10-03", incident_time="14:00")
    d = _log(p, incident_date="2026-10-03", incident_time="14:00")
    ids = [r.incident_id for r in B.list_incidents()]
    assert ids == [d.incident_id, c.incident_id, b.incident_id, a.incident_id]


def test_list_filters():
    p1 = _pupil("Ann", "One", "2")
    p2 = _pupil("Ben", "Two", "5")
    a = _log(p1, incident_date="2026-09-10", severity="High")
    b = _log(p2, incident_type="Uniform", incident_date="2026-09-20",
             status="Resolved")
    c = _log(p2, incident_type="Defiance", incident_date="2026-09-30",
             severity="Critical")

    def ids(**kw):
        return {r.incident_id for r in B.list_incidents(**kw)}

    assert ids(pupil_id=p1.pupil_id) == {a.incident_id}
    assert ids(year_group="5") == {b.incident_id, c.incident_id}
    assert ids(incident_type="Uniform") == {b.incident_id}
    assert ids(polarity="negative") == {b.incident_id, c.incident_id}
    assert ids(polarity="positive") == {a.incident_id}
    assert ids(severity="Critical") == {c.incident_id}
    assert ids(status="Resolved") == {b.incident_id}
    assert ids(date_from="2026-09-15") == {b.incident_id, c.incident_id}
    assert ids(date_to="2026-09-20") == {a.incident_id, b.incident_id}
    assert ids(date_from="2026-09-15", date_to="2026-09-25") == {b.incident_id}


@pytest.mark.parametrize("kw,msg", [
    ({"year_group": "7"}, "Year filter"),
    ({"incident_type": "Nope"}, "Type filter"),
    ({"polarity": "neutral"}, "Polarity filter"),
    ({"severity": "Huge"}, "Severity filter"),
    ({"status": "Done"}, "Status filter"),
    ({"date_from": "2026/01/01"}, "From date must be YYYY-MM-DD"),
])
def test_list_filter_validation(kw, msg):
    with pytest.raises(B.ValidationError, match=msg):
        B.list_incidents(**kw)


# ── update / set_status / delete ─────────────────────────────────────

def test_update_merges_fields():
    p = _pupil()
    rec = _log(p, location="Hall", points=3)
    up = B.update(rec.incident_id, {"description": "Changed", "points": 7})
    assert up.description == "Changed"
    assert up.points == 7
    assert up.location == "Hall"
    assert B.get(rec.incident_id).description == "Changed"


def test_update_type_change_revalidates_points_sign():
    rec = _log(_pupil(), points=3)
    with pytest.raises(B.ValidationError, match="Negative incident types"):
        B.update(rec.incident_id, {"incident_type": "Disruption"})
    up = B.update(rec.incident_id, {"incident_type": "Disruption", "points": -2})
    assert up.polarity == "negative" and up.points == -2


def test_update_missing_refused():
    with pytest.raises(B.ValidationError, match="No behaviour incident #77"):
        B.update(77, {"description": "x"})


def test_set_status():
    rec = _log(_pupil())
    assert B.set_status(rec.incident_id, "Escalated").status == "Escalated"
    with pytest.raises(B.ValidationError, match="Status must be one of"):
        B.set_status(rec.incident_id, "Bogus")


def test_delete():
    rec = _log(_pupil())
    assert B.delete(rec.incident_id) is True
    assert B.get(rec.incident_id) is None
    assert B.delete(rec.incident_id) is False


# ── summaries ────────────────────────────────────────────────────────

def test_pupil_summary_counts_and_points():
    p = _pupil()
    other = _pupil("Other", "Kid")
    _log(p, points=5, severity="Medium")
    _log(p, incident_type="House points", points=2)
    _log(p, incident_type="Disruption", points=-3, status="Resolved")
    _log(other, points=50)
    s = B.pupil_summary(f"  {p.pupil_id} ")
    assert s["pupil_id"] == p.pupil_id
    assert s["total"] == 3
    assert s["positive"] == 2
    assert s["negative"] == 1
    assert s["total_points"] == 4
    assert s["by_type"] == {"Achievement": 1, "House points": 1, "Disruption": 1}
    assert s["by_status"] == {"Open": 2, "Resolved": 1}
    assert s["by_severity"] == {"Medium": 1, "Low": 2}
    assert len(s["incidents"]) == 3


def test_pupil_summary_date_window_and_empty():
    p = _pupil()
    _log(p, incident_date="2026-09-01", points=4)
    _log(p, incident_date="2026-10-01", points=6)
    assert B.pupil_summary(p.pupil_id, date_from="2026-09-15")["total_points"] == 6
    empty = B.pupil_summary(_pupil("No", "One").pupil_id)
    assert empty["total"] == 0 and empty["total_points"] == 0
    assert empty["by_type"] == {}


def test_cohort_summary():
    y3 = _pupil(year="3")
    y4 = _pupil("Bea", "Four", "4")
    _log(y3)
    _log(y3, incident_type="Lateness", status="Resolved")
    _log(y4, incident_type="Damage", severity="High")
    allc = B.cohort_summary()
    assert allc["total"] == 3
    assert allc["positive"] == 1 and allc["negative"] == 2
    assert allc["open"] == 2
    assert allc["by_status"] == {"Open": 2, "Resolved": 1}
    assert allc["by_severity"] == {"Low": 2, "High": 1}
    y = B.cohort_summary(year_group="4")
    assert y["total"] == 1 and y["by_type"] == {"Damage": 1}


def test_pupils_above_threshold():
    a = _pupil("A", "A")
    b = _pupil("B", "B", "5")
    c = _pupil("C", "C")
    _log(a, incident_type="Physical", points=-8)
    _log(a, incident_type="Defiance", points=-4)            # a = -12
    _log(b, incident_type="Damage", points=-10)             # b = -10 (at threshold)
    _log(c, incident_type="Damage", points=-20)
    _log(c, points=15)                                      # c = -5
    assert B.pupils_above_threshold() == [(a.pupil_id, -12), (b.pupil_id, -10)]
    assert B.pupils_above_threshold(year_group="5") == [(b.pupil_id, -10)]
    assert B.pupils_above_threshold(points_below=-11) == [(a.pupil_id, -12)]


def test_pupils_above_threshold_empty():
    assert B.pupils_above_threshold() == []

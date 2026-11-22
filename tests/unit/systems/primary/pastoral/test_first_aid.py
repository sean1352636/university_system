"""First-aid incidents (primary domain.pastoral.health.first_aid.first_aid)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.health.first_aid import first_aid as FA

_n = 0


def _pupil(year="3", first=None, last=None):
    global _n
    _n += 1
    return P.create_pupil({"first_name": first or f"Pupil{_n}",
                           "last_name": last or f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2018-01-01"})


def _incident(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "incident_date": "2026-10-05",
            "incident_time": "10:30", "location": "Playground",
            "description": "Fell over", "treatment": "Ice pack",
            "treated_by": "Mrs First", **extra}
    return FA.create(data)


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_values_and_defaults():
    ava = _pupil(year="4", first="Ava", last="Smith")
    rec = _incident(ava, body_part="Knee", accident_book_ref="AB-1",
                    follow_up="Check tomorrow", notes="  calm  ")
    assert rec.incident_id > 0
    assert (rec.pupil_id, rec.incident_date, rec.incident_time) == (
        ava.pupil_id, "2026-10-05", "10:30")
    assert (rec.injury_type, rec.severity, rec.outcome) == (
        FA.DEFAULT_INJURY, FA.DEFAULT_SEVERITY, FA.DEFAULT_OUTCOME)
    assert (rec.body_part, rec.accident_book_ref, rec.follow_up, rec.notes) == (
        "Knee", "AB-1", "Check tomorrow", "calm")
    assert rec.parent_contacted is False and rec.hospital_referral is False
    assert rec.riddor_reportable is False
    assert rec.pupil_name == "Ava Smith" and rec.pupil_year == "4"
    assert FA.get(rec.incident_id) == rec


def test_blank_date_defaults_to_today_and_blank_time_is_none():
    rec = _incident(_pupil(), incident_date="", incident_time="")
    assert rec.incident_date == dt.date.today().isoformat()
    assert rec.incident_time is None


def test_get_missing_is_none():
    assert FA.get(999) is None


def test_hospital_outcomes_force_hospital_referral():
    ava = _pupil()
    for outcome in ("Hospital — A&E", "Hospital — minor injuries", "Ambulance called"):
        rec = _incident(ava, outcome=outcome, hospital_referral=False)
        assert rec.hospital_referral is True, outcome
    assert _incident(ava, outcome="GP referral").hospital_referral is False
    assert _incident(ava, outcome="GP referral", hospital_referral=True).hospital_referral


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("bad, msg", [
    ({"pupil_id": ""}, "Pupil ID is required"),
    ({"pupil_id": "P0000000"}, "No pupil with id P0000000"),
    ({"incident_date": "05/10/2026"}, "Incident date must be YYYY-MM-DD"),
    ({"incident_date": "2026-02-30"}, "not a real date"),
    ({"incident_time": "25:00"}, "Incident time must be HH:MM"),
    ({"incident_time": "9:30"}, "Incident time must be HH:MM"),
    ({"location": "  "}, "Location is required"),
    ({"injury_type": "Broken heart"}, "Injury type must be one of"),
    ({"severity": "Mild"}, "Severity must be one of"),
    ({"description": ""}, "Description is required"),
    ({"description": "x" * 2001}, "too long"),
    ({"treatment": ""}, "Treatment is required"),
    ({"treated_by": ""}, "Treated-by is required"),
    ({"outcome": "Detention"}, "Outcome must be one of"),
    ({"parent_contacted": True, "parent_contact_time": "noon"}, "Parent contact time"),
])
def test_create_refuses(bad, msg):
    ava = _pupil()
    with pytest.raises(FA.ValidationError, match=msg):
        _incident(ava, **bad)
    assert FA.list_incidents() == []


def test_description_of_exactly_2000_chars_is_allowed():
    assert len(_incident(_pupil(), description="x" * 2000).description) == 2000


@pytest.mark.parametrize("severity", ["Severe", "Critical"])
def test_severe_and_critical_need_parent_contacted(severity):
    ava = _pupil()
    with pytest.raises(FA.ValidationError, match="parent_contacted=True"):
        _incident(ava, severity=severity)
    rec = _incident(ava, severity=severity, parent_contacted=True,
                    parent_contact_time="10:45")
    assert rec.severity == severity and rec.parent_contacted
    assert rec.parent_contact_time == "10:45"


def test_moderate_does_not_need_parent_contact():
    assert _incident(_pupil(), severity="Moderate").parent_contacted is False


# ── listing and filters ──────────────────────────────────────────────

def test_list_empty_database():
    assert FA.list_incidents() == []


def test_list_orders_newest_first_with_time_and_id_tiebreak():
    ava = _pupil()
    a = _incident(ava, incident_date="2026-10-01", incident_time="09:00")
    b = _incident(ava, incident_date="2026-10-03", incident_time="09:00")
    c = _incident(ava, incident_date="2026-10-03", incident_time="14:00")
    d = _incident(ava, incident_date="2026-10-03", incident_time="14:00")
    assert [r.incident_id for r in FA.list_incidents()] == [
        d.incident_id, c.incident_id, b.incident_id, a.incident_id]


def test_list_filters():
    ava, ben = _pupil(), _pupil()
    a = _incident(ava, incident_date="2026-09-10", injury_type="Cut/Graze")
    b = _incident(ben, incident_date="2026-10-10", severity="Severe",
                  parent_contacted=True, riddor_reportable=True)
    c = _incident(ava, incident_date="2026-11-01", outcome="Ambulance called")
    ids = lambda rows: {r.incident_id for r in rows}  # noqa: E731
    assert ids(FA.list_incidents(pupil_id=ava.pupil_id)) == {a.incident_id, c.incident_id}
    assert ids(FA.list_incidents(pupil_id=f"  {ben.pupil_id} ")) == {b.incident_id}
    assert ids(FA.list_incidents(from_date="2026-10-01")) == {b.incident_id, c.incident_id}
    assert ids(FA.list_incidents(to_date="2026-10-10")) == {a.incident_id, b.incident_id}
    assert ids(FA.list_incidents(from_date="2026-10-10", to_date="2026-10-10")) == {b.incident_id}
    assert ids(FA.list_incidents(severity="Severe")) == {b.incident_id}
    assert ids(FA.list_incidents(injury_type="Cut/Graze")) == {a.incident_id}
    assert ids(FA.list_incidents(riddor_only=True)) == {b.incident_id}
    assert ids(FA.list_incidents(hospital_only=True)) == {c.incident_id}
    assert FA.list_incidents(severity="Critical") == []


@pytest.mark.parametrize("kwargs, msg", [
    ({"from_date": "1/1/2026"}, "From date must be YYYY-MM-DD"),
    ({"to_date": "2026/01/01"}, "To date must be YYYY-MM-DD"),
    ({"severity": "Mild"}, "Severity filter must be one of"),
    ({"injury_type": "Paper cut"}, "Injury type filter must be one of"),
])
def test_list_refuses_bad_filters(kwargs, msg):
    with pytest.raises(FA.ValidationError, match=msg):
        FA.list_incidents(**kwargs)


# ── update / delete ──────────────────────────────────────────────────

def test_update_merges_with_existing_values():
    ava = _pupil()
    rec = _incident(ava, body_part="Arm", notes="first")
    upd = FA.update(rec.incident_id, {"severity": "Moderate", "treatment": "Plaster"})
    assert (upd.severity, upd.treatment) == ("Moderate", "Plaster")
    assert (upd.body_part, upd.notes, upd.location) == ("Arm", "first", "Playground")
    assert FA.get(rec.incident_id).treatment == "Plaster"


def test_update_revalidates_and_leaves_row_unchanged_on_refusal():
    rec = _incident(_pupil())
    with pytest.raises(FA.ValidationError, match="parent_contacted=True"):
        FA.update(rec.incident_id, {"severity": "Critical"})
    with pytest.raises(FA.ValidationError, match="No pupil"):
        FA.update(rec.incident_id, {"pupil_id": "P9999999"})
    assert FA.get(rec.incident_id).severity == "Minor"


def test_update_can_move_to_another_pupil():
    rec = _incident(_pupil())
    ben = _pupil(year="R")
    upd = FA.update(rec.incident_id, {"pupil_id": ben.pupil_id})
    assert upd.pupil_id == ben.pupil_id and upd.pupil_year == "R"


def test_update_missing_incident_refused():
    with pytest.raises(FA.ValidationError, match="No first-aid incident #42"):
        FA.update(42, {"notes": "x"})


def test_delete():
    rec = _incident(_pupil())
    assert FA.delete(rec.incident_id) is True
    assert FA.get(rec.incident_id) is None
    assert FA.delete(rec.incident_id) is False


# ── cohort summary ───────────────────────────────────────────────────

def test_cohort_summary_empty():
    s = FA.cohort_summary()
    assert s == {"total": 0, "by_severity": {}, "by_injury": {}, "by_outcome": {},
                 "by_location": {}, "pupils": 0, "parent_contacted": 0,
                 "hospital": 0, "riddor": 0}


def test_cohort_summary_counts_and_date_window():
    ava, ben = _pupil(), _pupil()
    _incident(ava, incident_date="2026-09-01")                      # outside window
    _incident(ava, incident_date="2026-10-01", injury_type="Cut/Graze",
              location="Hall")
    _incident(ava, incident_date="2026-10-02", severity="Severe",
              parent_contacted=True, outcome="Hospital — A&E",
              riddor_reportable=True)
    _incident(ben, incident_date="2026-10-03", parent_contacted=True)
    s = FA.cohort_summary(from_date="2026-10-01", to_date="2026-10-31")
    assert s["total"] == 3 and s["pupils"] == 2
    assert s["by_severity"] == {"Minor": 2, "Severe": 1}
    assert s["by_injury"] == {"Cut/Graze": 1, "Bump/Bruise": 2}
    assert s["by_outcome"] == {"Returned to lesson": 2, "Hospital — A&E": 1}
    assert s["by_location"] == {"Hall": 1, "Playground": 2}
    assert (s["parent_contacted"], s["hospital"], s["riddor"]) == (2, 1, 1)
    assert FA.cohort_summary()["total"] == 4

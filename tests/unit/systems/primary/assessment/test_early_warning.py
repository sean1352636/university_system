"""Early-warning alerts (domain.assessment.early_warning.early_warning)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.assessment.early_warning import early_warning as EW
from education_system.systems.primary.domain.learners.pupils import pupils as P

_n = 0


def _pupil(year="3"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2017-03-01"})


def _alert(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "title": "Falling behind",
            "raised_date": "2025-10-01"}
    data.update(extra)
    return EW.create(data)


# ── create / get ─────────────────────────────────────────────────────

def test_create_applies_defaults_and_joins_pupil():
    p = _pupil("4")
    a = _alert(p)
    assert (a.alert_type, a.severity, a.source, a.status) == (
        "Academic", "Medium", "Teacher", "Open")
    assert a.pupil_name == p.full_name and a.pupil_year == "4"
    assert a.raised_date == "2025-10-01"
    assert a.resolution is None and a.resolved_date is None
    assert EW.get(a.alert_id) == a


def test_create_stores_every_field():
    p = _pupil()
    a = _alert(p, alert_type="Wellbeing", severity="High", title="  Upset at drop-off ",
               details="Cries most mornings", source="Form tutor", raised_by="Ms A",
               assigned_to="Mr B", notes="Speak to parent")
    got = EW.get(a.alert_id)
    assert (got.alert_type, got.severity, got.title, got.details, got.source) == (
        "Wellbeing", "High", "Upset at drop-off", "Cries most mornings", "Form tutor")
    assert (got.raised_by, got.assigned_to, got.notes) == ("Ms A", "Mr B", "Speak to parent")


def test_missing_raised_date_defaults_to_today():
    a = EW.create({"pupil_id": _pupil().pupil_id, "title": "x"})
    assert a.raised_date == dt.date.today().isoformat()


def test_get_unknown_is_none():
    assert EW.get(404) is None


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("field, value, message", [
    ("pupil_id", "", "Pupil ID is required"),
    ("pupil_id", "P9999999", "No pupil with id P9999999"),
    ("alert_type", "Lateness", "Alert type must be one of"),
    ("severity", "Extreme", "Severity must be one of"),
    ("title", "  ", "Title is required"),
    ("title", "t" * 121, "120 characters or fewer"),
    ("source", "Parent", "Source must be one of"),
    ("status", "Closed", "Status must be one of"),
    ("raised_date", "01/10/2025", "Raised date must be YYYY-MM-DD"),
    ("raised_date", "2025-02-30", "Raised date is not a real date"),
    ("resolved_date", "2025-13-01", "Resolved date is not a real date"),
])
def test_create_refuses_invalid(field, value, message):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        _alert(p, **{field: value})
    assert EW.list_alerts() == []


def test_title_of_120_characters_is_allowed():
    assert len(_alert(_pupil(), title="t" * 120).title) == 120


@pytest.mark.parametrize("status", ["Resolved", "Dismissed"])
def test_closing_status_needs_a_resolution(status):
    with pytest.raises(P.ValidationError, match=f"Resolution is required when status is {status}"):
        _alert(_pupil(), status=status)


def test_resolved_without_date_is_stamped_today():
    a = _alert(_pupil(), status="Resolved", resolution="Caught up")
    assert a.resolved_date == dt.date.today().isoformat()


def test_resolved_date_cannot_precede_raised_date():
    with pytest.raises(P.ValidationError, match="Resolved date cannot be before raised date"):
        _alert(_pupil(), status="Resolved", resolution="ok", resolved_date="2025-09-30")


# ── update and workflow ──────────────────────────────────────────────

def test_update_merges_fields():
    a = _alert(_pupil(), notes="first")
    up = EW.update(a.alert_id, {"severity": "Critical", "assigned_to": "SENCO"})
    assert up.severity == "Critical" and up.assigned_to == "SENCO"
    assert up.notes == "first" and up.title == "Falling behind"


def test_update_unknown_alert_is_refused():
    with pytest.raises(P.ValidationError, match="No early-warning alert #7"):
        EW.update(7, {"severity": "Low"})


def test_update_validates():
    a = _alert(_pupil())
    with pytest.raises(P.ValidationError, match="Severity must be one of"):
        EW.update(a.alert_id, {"severity": "Huge"})
    assert EW.get(a.alert_id).severity == "Medium"


def test_set_status_moves_through_workflow():
    a = _alert(_pupil())
    assert EW.set_status(a.alert_id, "Acknowledged").status == "Acknowledged"
    assert EW.set_status(a.alert_id, "InAction").status == "InAction"
    with pytest.raises(P.ValidationError, match="Status must be one of"):
        EW.set_status(a.alert_id, "Done")


def test_set_status_resolved_without_resolution_is_refused():
    a = _alert(_pupil())
    with pytest.raises(P.ValidationError, match="Resolution is required"):
        EW.set_status(a.alert_id, "Resolved")


def test_resolve_records_resolution_and_date():
    a = _alert(_pupil())
    r = EW.resolve(a.alert_id, resolution="Reading recovered", resolved_date="2025-11-15")
    assert (r.status, r.resolution, r.resolved_date) == (
        "Resolved", "Reading recovered", "2025-11-15")


def test_resolve_defaults_to_today():
    a = _alert(_pupil())
    assert EW.resolve(a.alert_id, resolution="ok").resolved_date == dt.date.today().isoformat()


def test_resolve_before_raised_date_is_refused():
    a = _alert(_pupil())
    with pytest.raises(P.ValidationError, match="cannot be before raised"):
        EW.resolve(a.alert_id, resolution="ok", resolved_date="2025-01-01")
    assert EW.get(a.alert_id).status == "Open"


def test_dismiss_needs_and_keeps_resolution():
    a = _alert(_pupil())
    with pytest.raises(P.ValidationError, match="Resolution is required"):
        EW.dismiss(a.alert_id, resolution="  ")
    d = EW.dismiss(a.alert_id, resolution="Raised in error")
    assert d.status == "Dismissed" and d.resolution == "Raised in error"
    assert d.resolved_date is None


def test_delete():
    a = _alert(_pupil())
    assert EW.delete(a.alert_id) is True
    assert EW.get(a.alert_id) is None
    assert EW.delete(a.alert_id) is False


# ── listing ──────────────────────────────────────────────────────────

def _seed():
    y3, y5 = _pupil("3"), _pupil("5")
    low = _alert(y3, severity="Low", title="low", raised_date="2025-10-05",
                 alert_type="Attendance", source="Attendance team")
    crit = _alert(y5, severity="Critical", title="crit", raised_date="2025-09-01",
                  alert_type="Safeguarding flag", assigned_to="DSL")
    high_old = _alert(y3, severity="High", title="high-old", raised_date="2025-09-10")
    high_new = _alert(y5, severity="High", title="high-new", raised_date="2025-10-20")
    done = _alert(y3, severity="Critical", title="done", raised_date="2025-09-02",
                  status="Resolved", resolution="ok", resolved_date="2025-09-03")
    return y3, y5, {"low": low, "crit": crit, "high_old": high_old,
                    "high_new": high_new, "done": done}


def test_list_orders_by_severity_then_newest():
    _seed()
    assert [a.title for a in EW.list_alerts()] == [
        "done", "crit", "high-new", "high-old", "low"]


def test_list_filters():
    y3, y5, a = _seed()
    assert {x.title for x in EW.list_alerts(year_group="3")} == {"low", "high-old", "done"}
    assert {x.title for x in EW.list_alerts(pupil_id=y5.pupil_id)} == {"crit", "high-new"}
    assert [x.title for x in EW.list_alerts(alert_type="Attendance")] == ["low"]
    assert {x.title for x in EW.list_alerts(severity="High")} == {"high-old", "high-new"}
    assert [x.title for x in EW.list_alerts(status="Resolved")] == ["done"]
    assert [x.title for x in EW.list_alerts(source="Attendance team")] == ["low"]
    assert [x.title for x in EW.list_alerts(assigned_to="DSL")] == ["crit"]
    assert {x.title for x in EW.list_alerts(date_from="2025-10-01")} == {"low", "high-new"}
    assert {x.title for x in EW.list_alerts(date_to="2025-09-02")} == {"crit", "done"}
    assert {x.title for x in EW.list_alerts(date_from="2025-09-02",
                                            date_to="2025-09-10")} == {"done", "high-old"}


@pytest.mark.parametrize("kwargs, message", [
    ({"year_group": "7"}, "Year filter"),
    ({"alert_type": "x"}, "Type filter"),
    ({"severity": "x"}, "Severity filter"),
    ({"status": "x"}, "Status filter"),
    ({"source": "x"}, "Source filter"),
    ({"date_from": "yesterday"}, "From date must be YYYY-MM-DD"),
])
def test_list_refuses_bad_filters(kwargs, message):
    with pytest.raises(P.ValidationError, match=message):
        EW.list_alerts(**kwargs)


# ── summaries ────────────────────────────────────────────────────────

def test_empty_summary():
    assert EW.cohort_summary() == {"total": 0, "open": 0, "by_status": {}, "by_type": {},
                                   "by_severity": {}, "open_critical": 0, "open_high": 0}
    assert EW.pupils_at_risk() == {}


def test_cohort_summary_counts():
    _y3, _y5, a = _seed()
    EW.dismiss(a["low"].alert_id, resolution="dup")
    s = EW.cohort_summary()
    assert s["total"] == 5
    assert s["open"] == 3
    assert s["by_status"] == {"Open": 3, "Resolved": 1, "Dismissed": 1}
    assert s["by_severity"] == {"Low": 1, "Critical": 2, "High": 2}
    assert s["by_type"] == {"Attendance": 1, "Safeguarding flag": 1, "Academic": 3}
    assert s["open_critical"] == 1     # the resolved Critical one does not count
    assert s["open_high"] == 2


def test_cohort_summary_by_year_group():
    _seed()
    s = EW.cohort_summary(year_group="5")
    assert s["total"] == 2 and s["open_critical"] == 1 and s["open_high"] == 1


def test_pupils_at_risk_threshold():
    y3, y5, a = _seed()
    at_high = EW.pupils_at_risk()
    assert set(at_high) == {y3.pupil_id, y5.pupil_id}
    assert [x.title for x in at_high[y3.pupil_id]] == ["high-old"]
    assert [x.title for x in at_high[y5.pupil_id]] == ["crit", "high-new"]
    assert set(EW.pupils_at_risk(severity_min="Critical")) == {y5.pupil_id}
    assert [x.title for x in EW.pupils_at_risk(severity_min="Low")[y3.pupil_id]] == [
        "high-old", "low"]


def test_pupils_at_risk_ignores_acknowledged_only_if_closed():
    p = _pupil()
    a = _alert(p, severity="High")
    EW.set_status(a.alert_id, "InAction")
    assert set(EW.pupils_at_risk()) == {p.pupil_id}
    EW.resolve(a.alert_id, resolution="done", resolved_date="2025-10-02")
    assert EW.pupils_at_risk() == {}


def test_pupils_at_risk_refuses_unknown_severity():
    with pytest.raises(P.ValidationError, match="severity_min must be one of"):
        EW.pupils_at_risk(severity_min="Severe")

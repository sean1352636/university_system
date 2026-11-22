"""Medical records (primary domain.pastoral.health.medical_records.medical_records)."""

from __future__ import annotations

import logging

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.health.medical_records import (
    medical_records as MR,
)

_n = 0


def _pupil(year="3"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2018-01-01"})


def _rec(pupil, **extra):
    return MR.create({"pupil_id": pupil.pupil_id, "record_type": "allergy",
                      "title": "Peanut allergy", **extra})


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_values_and_defaults():
    ava = _pupil()
    rec = _rec(ava, description=" Carries EpiPen ", start_date="2025-01-01",
               end_date="2027-01-01", action_plan="Use EpiPen, call 999",
               contact_name="Dr Who", contact_phone="+44 (0)1234 567890",
               notes="  keep in office ")
    assert rec.record_id > 0 and rec.pupil_id == ava.pupil_id
    assert (rec.record_type, rec.title, rec.description) == (
        "allergy", "Peanut allergy", "Carries EpiPen")
    assert rec.severity == "low" and rec.is_active is True and rec.is_critical is False
    assert (rec.start_date, rec.end_date) == ("2025-01-01", "2027-01-01")
    assert (rec.action_plan, rec.contact_name, rec.contact_phone, rec.notes) == (
        "Use EpiPen, call 999", "Dr Who", "+44 (0)1234 567890", "keep in office")
    assert MR.get(rec.record_id) == rec


def test_type_and_severity_are_case_insensitive_and_blank_severity_is_low():
    ava = _pupil()
    rec = _rec(ava, record_type="  Medication ", severity="CRITICAL")
    assert (rec.record_type, rec.severity, rec.is_critical) == ("medication", "critical", True)
    assert _rec(ava, severity="  ").severity == "low"


def test_is_active_false_is_kept():
    assert _rec(_pupil(), is_active=False).is_active is False


def test_get_missing_is_none():
    assert MR.get(12345) is None


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def test_create_and_update_do_not_log_clinical_detail():
    ava = _pupil()
    log = logging.getLogger(MR.__name__)
    cap, old_level = _Capture(), log.level
    log.addHandler(cap)
    log.setLevel(logging.DEBUG)
    try:
        rec = _rec(ava, title="Secret condition", description="very private")
        MR.update(rec.record_id, {"notes": "hidden note"})
    finally:
        log.removeHandler(cap)
        log.setLevel(old_level)
    text = "\n".join(cap.lines)
    assert cap.lines and f"#{rec.record_id}" in text
    for secret in ("Secret condition", "very private", "hidden note"):
        assert secret not in text


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("bad, msg", [
    ({"pupil_id": "  "}, "Pupil ID is required"),
    ({"pupil_id": "P0000001"}, "No pupil with id P0000001"),
    ({"record_type": ""}, "Record type is required"),
    ({"record_type": "vaccine"}, "Record type must be one of"),
    ({"title": ""}, "Title is required"),
    ({"title": "x" * 101}, "100 characters or fewer"),
    ({"severity": "extreme"}, "Severity must be one of"),
    ({"start_date": "01/01/2025"}, "Start date must be YYYY-MM-DD"),
    ({"end_date": "2025-1-1"}, "End date must be YYYY-MM-DD"),
    ({"start_date": "2025-06-01", "end_date": "2025-05-31"}, "End date cannot be before"),
    ({"contact_phone": "call mum"}, "Contact phone contains invalid characters"),
])
def test_create_refuses(bad, msg):
    ava = _pupil()
    with pytest.raises(MR.ValidationError, match=msg):
        _rec(ava, **bad)
    assert MR.list_records() == []


def test_boundary_values_allowed():
    ava = _pupil()
    assert len(_rec(ava, title="t" * 100).title) == 100
    same = _rec(ava, start_date="2025-06-01", end_date="2025-06-01")
    assert same.start_date == same.end_date == "2025-06-01"


# ── update / toggle / delete ─────────────────────────────────────────

def test_update_merges_and_validates():
    ava = _pupil()
    rec = _rec(ava, notes="original", contact_name="Mum")
    upd = MR.update(rec.record_id, {"severity": "high", "title": "Tree-nut allergy"})
    assert (upd.severity, upd.title) == ("high", "Tree-nut allergy")
    assert (upd.notes, upd.contact_name, upd.record_type) == ("original", "Mum", "allergy")
    with pytest.raises(MR.ValidationError, match="Severity must be one of"):
        MR.update(rec.record_id, {"severity": "huge"})
    with pytest.raises(MR.ValidationError, match="No pupil with id P7777777"):
        MR.update(rec.record_id, {"pupil_id": "P7777777"})
    assert MR.get(rec.record_id).severity == "high"


def test_update_can_clear_optional_fields_and_deactivate():
    rec = _rec(_pupil(), notes="n", end_date="2027-01-01")
    upd = MR.update(rec.record_id, {"notes": "", "end_date": None, "is_active": False})
    assert (upd.notes, upd.end_date, upd.is_active) == (None, None, False)


def test_update_missing_refused():
    with pytest.raises(MR.ValidationError, match="No medical record #9"):
        MR.update(9, {"title": "x"})


def test_toggle_active_flips_both_ways():
    rec = _rec(_pupil())
    assert MR.toggle_active(rec.record_id).is_active is False
    assert MR.get(rec.record_id).is_active is False
    assert MR.toggle_active(rec.record_id).is_active is True
    with pytest.raises(MR.ValidationError, match="No medical record #404"):
        MR.toggle_active(404)


def test_delete():
    rec = _rec(_pupil())
    assert MR.delete(rec.record_id) is True
    assert MR.get(rec.record_id) is None
    assert MR.delete(rec.record_id) is False


# ── listing ──────────────────────────────────────────────────────────

def test_list_empty_database():
    assert MR.list_records() == []
    assert MR.summary()["total"] == 0


def test_list_orders_by_severity_then_pupil_then_newest():
    ava = _pupil()
    low = _rec(ava, severity="low")
    crit = _rec(ava, severity="critical")
    med1 = _rec(ava, severity="medium")
    med2 = _rec(ava, severity="medium")
    high = _rec(ava, severity="high")
    order = [r.record_id for r, _ in MR.list_records()]
    assert order == [crit.record_id, high.record_id, med2.record_id,
                     med1.record_id, low.record_id]


def test_list_returns_pupil_alongside_record():
    ava = _pupil()
    _rec(ava)
    [(rec, pupil)] = MR.list_records()
    assert pupil.pupil_id == ava.pupil_id == rec.pupil_id


def test_list_filters():
    ava, ben = _pupil(year="2"), _pupil(year="5")
    a = _rec(ava, record_type="allergy", severity="critical", description="nuts")
    b = _rec(ava, record_type="dietary", title="Vegetarian", is_active=False)
    c = _rec(ben, record_type="condition", title="Asthma", notes="inhaler in bag")
    ids = lambda rows: {r.record_id for r, _ in rows}  # noqa: E731
    assert ids(MR.list_records(record_type="dietary")) == {b.record_id}
    assert ids(MR.list_records(severity="critical")) == {a.record_id}
    assert ids(MR.list_records(pupil_id=f" {ben.pupil_id} ")) == {c.record_id}
    assert ids(MR.list_records(year_group="2")) == {a.record_id, b.record_id}
    assert ids(MR.list_records(year_group="R")) == set()
    assert ids(MR.list_records(active_only=True)) == {a.record_id, c.record_id}
    assert ids(MR.list_records(critical_only=True)) == {a.record_id}
    assert ids(MR.list_records(search="vegetarian")) == {b.record_id}   # title
    assert ids(MR.list_records(search="nuts")) == {a.record_id}         # description
    assert ids(MR.list_records(search="inhaler")) == {c.record_id}      # notes


@pytest.mark.parametrize("kwargs, msg", [
    ({"record_type": "vaccine"}, "Type filter must be one of"),
    ({"severity": "huge"}, "Severity filter must be one of"),
    ({"year_group": "7"}, "Year filter must be one of"),
])
def test_list_refuses_bad_filters(kwargs, msg):
    with pytest.raises(MR.ValidationError, match=msg):
        MR.list_records(**kwargs)


def test_list_for_pupil():
    ava, ben = _pupil(), _pupil()
    a1 = _rec(ava, record_type="medication", severity="low")
    a2 = _rec(ava, record_type="allergy", severity="high")
    a3 = _rec(ava, record_type="condition", severity="low", is_active=False)
    _rec(ben)
    got = MR.list_for_pupil(ava.pupil_id)
    # severity first, then record_type alphabetically
    assert [r.record_id for r in got] == [a2.record_id, a3.record_id, a1.record_id]
    assert [r.record_id for r in MR.list_for_pupil(ava.pupil_id, active_only=True)] == [
        a2.record_id, a1.record_id]
    assert MR.list_for_pupil(_pupil().pupil_id) == []
    with pytest.raises(MR.ValidationError, match="No pupil with id P1111111"):
        MR.list_for_pupil("P1111111")


# ── summary ──────────────────────────────────────────────────────────

def test_summary_counts():
    ava, ben = _pupil(), _pupil()
    _rec(ava, record_type="allergy", severity="critical")
    _rec(ava, record_type="allergy", severity="high")
    _rec(ben, record_type="dietary", severity="critical", is_active=False)
    _rec(ben, record_type="medication", severity="medium")
    s = MR.summary()
    assert (s["total"], s["active"], s["critical_active"], s["pupils_with_records"]) == (
        4, 3, 1, 2)
    assert s["by_type"] == {"allergy": 2, "condition": 0, "medication": 1, "dietary": 0,
                            "injury": 0, "immunisation": 0, "other": 0}
    assert s["by_severity"] == {"low": 0, "medium": 1, "high": 1, "critical": 1}


def test_records_are_removed_with_their_pupil():
    ava = _pupil()
    rec = _rec(ava)
    assert P.delete_pupil(ava.pupil_id)
    assert MR.get(rec.record_id) is None

"""Visitor sign-in log (systems.primary.domain.operations.visitors.visitors)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.operations.visitors import visitors as V
from education_system.systems.primary.domain.staff import staff as ST

TODAY = dt.date.today()
NOW = dt.datetime.now()


def _visitor(name="Jane Parent", **extra):
    return V.create_visitor({"visitor_name": name, "visitor_type": "Parent / Carer", **extra})


def _host():
    return ST.create_staff({"first_name": "Hannah", "last_name": "Host"})


# ── create / get ──

def test_create_stores_fields_and_defaults():
    v = V.create_visitor({
        "visitor_name": "  Bob Builder ", "visitor_type": "Contractor",
        "organisation": " Fixit Ltd ", "purpose": "Boiler", "badge_number": "B7",
        "visit_date": "2030-02-03", "arrived_at": "2030-02-03T09:15",
        "expected_departure": "2030-02-03T12:00", "dbs_seen": 1,
        "photo_id_seen": "yes", "escort_required": True, "car_registration": " AB12 CDE ",
        "notes": "  "})
    got = V.get_visitor(v.visitor_id)
    assert got == v
    assert (got.visitor_name, got.organisation, got.visitor_type) == \
        ("Bob Builder", "Fixit Ltd", "Contractor")
    assert (got.visit_date, got.arrived_at, got.expected_departure) == \
        ("2030-02-03", "2030-02-03T09:15", "2030-02-03T12:00")
    assert got.dbs_seen and got.photo_id_seen and got.escort_required
    assert not got.induction_given and not got.safeguarding_concern
    assert got.car_registration == "AB12 CDE" and got.notes is None
    assert (got.id_check, got.status) == ("Photo ID Seen", "Expected")
    assert got.host_staff_id is None


def test_visit_date_defaults_to_today():
    assert _visitor().visit_date == TODAY.isoformat()


def test_host_must_be_known_staff():
    host = _host()
    v = _visitor(host_staff_id=host.staff_id, host_name="Mrs Host")
    assert v.host_staff_id == host.staff_id
    with pytest.raises(V.ValidationError, match="No staff with id T0000000"):
        _visitor(host_staff_id="T0000000")


def test_get_missing_returns_none():
    assert V.get_visitor(1) is None


# ── validation ──

def test_name_required():
    with pytest.raises(V.ValidationError, match="Visitor name is required"):
        _visitor("  ")


def test_visitor_type_must_be_known():
    with pytest.raises(V.ValidationError, match="Visitor type must be one of"):
        V.create_visitor({"visitor_name": "X", "visitor_type": "Tourist"})
    with pytest.raises(V.ValidationError, match="Visitor type must be one of"):
        V.create_visitor({"visitor_name": "X"})


def test_visit_date_format():
    with pytest.raises(V.ValidationError, match="Visit date must be YYYY-MM-DD"):
        _visitor(visit_date="03/02/2030")


@pytest.mark.parametrize("field,label", [
    ("arrived_at", "Arrived at"),
    ("expected_departure", "Expected departure"),
    ("signed_out_at", "Signed out at"),
])
def test_times_must_be_iso(field, label):
    with pytest.raises(V.ValidationError, match=f"{label} must be YYYY-MM-DD or"):
        _visitor(**{field: "half nine"})


def test_id_check_and_status_must_be_known():
    with pytest.raises(V.ValidationError, match="ID check must be one of"):
        _visitor(id_check="Passport")
    with pytest.raises(V.ValidationError, match="Status must be one of"):
        _visitor(status="Gone")


# ── update / delete ──

def test_update_replaces_record():
    v = _visitor(organisation="Old Org")
    out = V.update_visitor(v.visitor_id, {"visitor_name": "New Name",
                                          "visitor_type": "Governor",
                                          "visit_date": "2030-01-01"})
    assert (out.visitor_name, out.visitor_type, out.organisation) == \
        ("New Name", "Governor", None)


def test_update_unknown_or_invalid():
    with pytest.raises(V.ValidationError, match="No visitor with id 9"):
        V.update_visitor(9, {"visitor_name": "x", "visitor_type": "Other"})
    v = _visitor()
    with pytest.raises(V.ValidationError, match="Visitor name is required"):
        V.update_visitor(v.visitor_id, {"visitor_type": "Other"})


def test_delete():
    v = _visitor()
    assert V.delete_visitor(v.visitor_id) is True
    assert V.get_visitor(v.visitor_id) is None
    assert V.delete_visitor(v.visitor_id) is False


# ── workflow ──

def test_sign_in_and_out():
    v = _visitor(notes="Bring forms")
    on = V.sign_in(v.visitor_id, badge_number="V12", arrived_at="2030-02-03T09:00")
    assert (on.status, on.arrived_at, on.badge_number) == ("Signed In", "2030-02-03T09:00", "V12")
    assert on.is_on_site and on.notes == "Bring forms"
    off = V.sign_out(v.visitor_id, signed_out_at="2030-02-03T10:30")
    assert (off.status, off.signed_out_at, off.badge_number) == \
        ("Signed Out", "2030-02-03T10:30", "V12")
    assert not off.is_on_site


def test_sign_in_defaults_to_now():
    v = V.sign_in(_visitor().visitor_id)
    stamped = dt.datetime.fromisoformat(v.arrived_at)
    assert abs((stamped - dt.datetime.now()).total_seconds()) < 120


def test_sign_out_cannot_be_before_arrival():
    v = V.sign_in(_visitor().visitor_id, arrived_at="2030-02-03T09:00")
    with pytest.raises(V.ValidationError):
        V.sign_out(v.visitor_id, signed_out_at="2030-02-03T08:00")


def test_status_shortcuts():
    v = _visitor()
    assert V.mark_overstay(v.visitor_id).status == "Overstay"
    assert V.mark_no_show(v.visitor_id).status == "No-Show"
    assert V.set_status(v.visitor_id, "On Site").status == "On Site"
    with pytest.raises(V.ValidationError, match="Status must be one of"):
        V.set_status(v.visitor_id, "Left")


def test_refuse_entry_appends_reason_to_notes():
    v = _visitor(notes="Known to office")
    out = V.refuse_entry(v.visitor_id, reason="No ID")
    assert out.status == "Refused Entry"
    assert out.notes == f"Known to office\nRefused entry ({TODAY.isoformat()}): No ID"
    plain = V.refuse_entry(_visitor().visitor_id)
    assert plain.notes is None


def test_raise_safeguarding_sets_flag_and_note():
    v = _visitor()
    out = V.raise_safeguarding(v.visitor_id, detail="Asked about pupil")
    assert out.safeguarding_concern
    assert out.notes.startswith("Safeguarding concern (")
    assert out.notes.endswith("): Asked about pupil")


@pytest.mark.parametrize("action", ["sign_in", "sign_out", "mark_overstay", "mark_no_show",
                                    "refuse_entry", "raise_safeguarding"])
def test_workflow_refuses_unknown_visitor(action):
    with pytest.raises(V.ValidationError, match="No visitor with id 77"):
        getattr(V, action)(77)


def test_set_status_unknown_visitor():
    with pytest.raises(V.ValidationError, match="No visitor with id 77"):
        V.set_status(77, "On Site")


# ── overdue ──

def test_is_overdue():
    past = (NOW - dt.timedelta(hours=1)).isoformat(timespec="minutes")
    future = (NOW + dt.timedelta(hours=1)).isoformat(timespec="minutes")
    assert _visitor(status="Signed In", expected_departure=past).is_overdue
    assert not _visitor(status="Signed In", expected_departure=future).is_overdue
    assert not _visitor(status="Signed Out", expected_departure=past).is_overdue
    assert not _visitor(status="On Site").is_overdue
    # a plain date means "by the end of that day"
    yesterday = (TODAY - dt.timedelta(days=1)).isoformat()
    assert _visitor(status="On Site", expected_departure=yesterday).is_overdue
    assert not _visitor(status="On Site",
                        expected_departure=(TODAY + dt.timedelta(days=1)).isoformat()).is_overdue


# ── listing ──

def test_list_filters_and_order():
    host = _host()
    past = (NOW - dt.timedelta(hours=2)).isoformat(timespec="minutes")
    a = _visitor("Alice Smith", visit_date="2030-01-05", organisation="Acme", status="Signed In",
                 host_staff_id=host.staff_id, expected_departure=past)
    b = V.create_visitor({"visitor_name": "Bob Jones", "visitor_type": "Contractor",
                          "visit_date": "2030-01-07", "status": "No-Show"})
    c = _visitor("Cara Smith", visit_date="2030-01-06", safeguarding_concern=True,
                 status="Overstay")
    d = _visitor("Dan Today")

    def ids(**kw):
        return [x.visitor_id for x in V.list_visitors(**kw)]

    assert len(ids()) == 4
    assert ids(visitor_type="Contractor") == [b.visitor_id]
    assert ids(status="No-Show") == ids(no_show_only=True) == [b.visitor_id]
    assert ids(host_staff_id=host.staff_id) == [a.visitor_id]
    assert [x.visitor_id for x in V.visitors_for_host(host.staff_id)] == [a.visitor_id]
    assert ids(name_like="smith") == [c.visitor_id, a.visitor_id]
    assert ids(org_like="acm") == [a.visitor_id]
    assert ids(on_site_only=True) == [c.visitor_id, a.visitor_id]
    assert ids(overdue_only=True) == [a.visitor_id]
    assert ids(today_only=True) == [d.visitor_id]
    assert ids(safeguarding_only=True) == [c.visitor_id]
    assert ids(date_from="2030-01-06", date_to="2030-01-07") == [b.visitor_id, c.visitor_id]


def test_list_orders_newest_date_first_then_newest_id():
    a = _visitor("A", visit_date="2030-01-05")
    b = _visitor("B", visit_date="2030-01-07")
    c = _visitor("C", visit_date="2030-01-05")
    assert [x.visitor_id for x in V.list_visitors(date_from="2030-01-01")] == \
        [b.visitor_id, c.visitor_id, a.visitor_id]


def test_list_rejects_bad_date_filters():
    with pytest.raises(V.ValidationError, match="From must be YYYY-MM-DD"):
        V.list_visitors(date_from="soon")
    with pytest.raises(V.ValidationError, match="To must be YYYY-MM-DD"):
        V.list_visitors(date_to="later")


# ── summary ──

def test_summary_counts():
    past = (NOW - dt.timedelta(hours=1)).isoformat(timespec="minutes")
    V.create_visitor({"visitor_name": "Con", "visitor_type": "Contractor",
                      "status": "On Site", "dbs_seen": True, "id_check": "Both Seen",
                      "expected_departure": past})
    V.create_visitor({"visitor_name": "Con2", "visitor_type": "Contractor",
                      "status": "Signed Out", "visit_date": "2030-01-01"})
    _visitor("P1", status="No-Show", safeguarding_concern=True)
    _visitor("P2", status="Signed In", dbs_seen=True, visit_date="2030-01-02")
    s = V.summary()
    assert (s.total, s.on_site_now, s.overdue, s.expected_today) == (4, 2, 1, 2)
    assert (s.no_shows, s.safeguarding_concerns, s.contractors_on_site, s.dbs_seen_count) == \
        (1, 1, 1, 2)
    assert s.by_type == {"Contractor": 2, "Parent / Carer": 2}
    assert s.by_status == {"On Site": 1, "Signed Out": 1, "No-Show": 1, "Signed In": 1}
    assert s.by_id_check == {"Both Seen": 1, "Photo ID Seen": 3}


def test_summary_empty():
    s = V.summary()
    assert s.total == 0 and s.by_type == {} and s.on_site_now == 0

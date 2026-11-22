"""Clubs and club memberships (domain.academics.enrichment.clubs.clubs)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.enrichment.clubs import clubs as CL
from education_system.systems.primary.domain.learners.pupils import pupils as P


def _club(name="Choir", **extra):
    return CL.create({"name": name, **extra})


def _pupil(first="Ada", year="4"):
    return P.create_pupil({"first_name": first, "last_name": "Test", "year_group": year,
                           "date_of_birth": "2017-01-01"}).pupil_id


# ── empty database ──

def test_empty_db():
    assert CL.list_all() == []
    assert CL.get(1) is None
    assert CL.delete(1) is False
    assert CL.remove_member(1) is False
    assert CL.counts() == {"total": 0, "active": 0, "inactive": 0, "active_members": 0}


# ── clubs ──

def test_create_stores_every_field():
    c = _club(description=" Singing ", day_of_week="Tuesday", start_time="15:15",
              end_time="16:15", location=" Hall ", lead_staff=" Mrs Song ",
              year_groups="3, 4,3", max_members="20", notes="")
    assert (c.name, c.description, c.day_of_week, c.start_time, c.end_time, c.location,
            c.lead_staff, c.year_groups, c.max_members, c.is_active, c.notes) == (
        "Choir", "Singing", "Tuesday", "15:15", "16:15", "Hall", "Mrs Song", "3,4", 20,
        True, None)
    assert c.year_group_list == ["3", "4"]
    assert CL.get(c.club_id) == c


def test_year_groups_from_list_and_empty():
    assert _club(year_groups=["R", "1", "1"]).year_groups == "R,1"
    c = _club("Open to all", year_groups=" , ")
    assert (c.year_groups, c.year_group_list) == (None, [])


def test_club_validation():
    with pytest.raises(CL.ValidationError, match="Club name is required"):
        _club(name=" ")
    with pytest.raises(CL.ValidationError, match="80 characters"):
        _club(name="c" * 81)
    with pytest.raises(CL.ValidationError, match="Day must be one of"):
        _club(day_of_week="Saturday")
    with pytest.raises(CL.ValidationError, match="Start time must be HH:MM"):
        _club(start_time="3pm")
    with pytest.raises(CL.ValidationError, match="End time must be HH:MM"):
        _club(end_time="16:60")
    with pytest.raises(CL.ValidationError, match="End time must be after start time"):
        _club(start_time="16:00", end_time="15:00")
    with pytest.raises(CL.ValidationError, match="Year group '7' must be one of"):
        _club(year_groups="5,6,7")
    with pytest.raises(CL.ValidationError, match="Max members must be an integer"):
        _club(max_members="lots")
    with pytest.raises(CL.ValidationError, match="between 1 and 200"):
        _club(max_members=0)
    with pytest.raises(CL.ValidationError, match="between 1 and 200"):
        _club(max_members=201)


def test_duplicate_name_refused():
    _club()
    with pytest.raises(CL.ValidationError, match="already exists"):
        _club()


def test_list_filters_and_order():
    _club("football", day_of_week="Monday")
    _club("Art", day_of_week="Monday", is_active=False)
    _club("Choir", day_of_week="Tuesday")
    names = lambda cs: [c.name for c in cs]  # noqa: E731
    assert names(CL.list_all()) == ["Art", "Choir", "football"]
    assert names(CL.list_all(active_only=True)) == ["Choir", "football"]
    assert names(CL.list_all(day_of_week="Monday")) == ["Art", "football"]
    with pytest.raises(CL.ValidationError, match="Day filter"):
        CL.list_all(day_of_week="Mon")


def test_update_merges_and_checks():
    _club("Art")
    c = _club(location="Hall", max_members=10)
    out = CL.update(c.club_id, {"location": "Music room", "year_groups": ["5", "6"]})
    assert (out.location, out.max_members, out.year_groups) == ("Music room", 10, "5,6")
    with pytest.raises(CL.ValidationError, match="already exists"):
        CL.update(c.club_id, {"name": "Art"})
    with pytest.raises(CL.ValidationError, match="No club #99"):
        CL.update(99, {})


def test_toggle_and_counts():
    a = _club("Art")
    _club("Choir")
    assert CL.toggle_active(a.club_id).is_active is False
    assert CL.counts() == {"total": 2, "active": 1, "inactive": 1, "active_members": 0}
    assert CL.toggle_active(a.club_id).is_active is True
    with pytest.raises(CL.ValidationError, match="No club #5"):
        CL.toggle_active(5)


def test_delete_club_removes_memberships():
    c = _club()
    pid = _pupil()
    m = CL.add_member(c.club_id, pid)
    assert CL.delete(c.club_id) is True
    assert CL.get(c.club_id) is None
    assert CL.list_clubs_for_pupil(pid) == []
    assert CL.remove_member(m.membership_id) is False


# ── memberships ──

def test_add_member_defaults_join_date_to_today():
    c = _club()
    pid = _pupil()
    m = CL.add_member(c.club_id, pid, notes="keen")
    assert (m.club_id, m.pupil_id, m.status, m.notes) == (c.club_id, pid, "active", "keen")
    assert m.joined_on == dt.datetime.now(dt.timezone.utc).date().isoformat()


def test_add_member_with_join_date():
    m = CL.add_member(_club().club_id, _pupil(), joined_on=" 2025-09-10 ")
    assert m.joined_on == "2025-09-10"


def test_add_member_refusals():
    pid = _pupil(year="2")
    with pytest.raises(CL.ValidationError, match="No club #9"):
        CL.add_member(9, pid)
    off = _club("Closed", is_active=False)
    with pytest.raises(CL.ValidationError, match="is inactive"):
        CL.add_member(off.club_id, pid)
    c = _club(year_groups="5,6")
    with pytest.raises(CL.ValidationError, match="No pupil with id GHOST"):
        CL.add_member(c.club_id, "GHOST")
    with pytest.raises(CL.ValidationError, match="year 2 is not eligible"):
        CL.add_member(c.club_id, pid)
    open_club = _club("Open")
    with pytest.raises(CL.ValidationError, match="Joined-on date must be YYYY-MM-DD"):
        CL.add_member(open_club.club_id, pid, joined_on="10/09/2025")
    CL.add_member(open_club.club_id, pid)
    with pytest.raises(CL.ValidationError, match="already a member"):
        CL.add_member(open_club.club_id, pid)


def test_capacity_enforced_on_join_and_rejoin():
    c = _club(max_members=2)
    a, b, x = _pupil("Ada"), _pupil("Bea"), _pupil("Cy")
    ma = CL.add_member(c.club_id, a)
    CL.add_member(c.club_id, b)
    with pytest.raises(CL.ValidationError, match="at capacity"):
        CL.add_member(c.club_id, x)
    CL.set_member_status(ma.membership_id, "withdrawn")
    mx = CL.add_member(c.club_id, x)
    assert mx.status == "active"
    with pytest.raises(CL.ValidationError, match="at capacity"):
        CL.add_member(c.club_id, a)            # rejoin while full
    with pytest.raises(CL.ValidationError, match="at capacity"):
        CL.set_member_status(ma.membership_id, "active")


def test_rejoin_reactivates_same_membership():
    c = _club()
    pid = _pupil()
    m = CL.add_member(c.club_id, pid, joined_on="2025-09-01", notes="first")
    CL.set_member_status(m.membership_id, "withdrawn")
    again = CL.add_member(c.club_id, pid, joined_on="2026-01-05")
    assert again.membership_id == m.membership_id
    assert (again.status, again.joined_on, again.notes) == ("active", "2026-01-05", "first")


def test_set_member_status_rules():
    m = CL.add_member(_club().club_id, _pupil())
    assert CL.set_member_status(m.membership_id, "active") == m     # no change
    assert CL.set_member_status(m.membership_id, "withdrawn").status == "withdrawn"
    with pytest.raises(CL.ValidationError, match="Status must be one of"):
        CL.set_member_status(m.membership_id, "paused")
    with pytest.raises(CL.ValidationError, match="No membership #404"):
        CL.set_member_status(404, "active")


def test_list_members_active_first_and_filter():
    c = _club()
    a, b, x = _pupil("Ada"), _pupil("Bea"), _pupil("Cy")
    ma = CL.add_member(c.club_id, a, joined_on="2025-09-01")
    CL.add_member(c.club_id, b, joined_on="2025-09-20")
    CL.add_member(c.club_id, x, joined_on="2025-09-10")
    CL.set_member_status(ma.membership_id, "withdrawn")
    rows = CL.list_members(c.club_id)
    assert [(p.pupil_id, m.status) for p, m in rows] == [
        (x, "active"), (b, "active"), (a, "withdrawn")]
    assert [p.pupil_id for p, _ in CL.list_members(c.club_id, active_only=True)] == [x, b]
    with pytest.raises(CL.ValidationError, match="No club #77"):
        CL.list_members(77)


def test_list_clubs_for_pupil_newest_first():
    pid = _pupil()
    choir, art = _club(), _club("Art")
    m1 = CL.add_member(choir.club_id, pid, joined_on="2025-09-01")
    CL.add_member(art.club_id, pid, joined_on="2025-10-01")
    CL.set_member_status(m1.membership_id, "withdrawn")
    assert [c.name for c, _ in CL.list_clubs_for_pupil(pid)] == ["Art", "Choir"]
    assert [c.name for c, _ in CL.list_clubs_for_pupil(pid, active_only=True)] == ["Art"]
    with pytest.raises(CL.ValidationError, match="No pupil with id NOPE"):
        CL.list_clubs_for_pupil("NOPE")


def test_remove_member_and_counts():
    c = _club()
    a, b = _pupil("Ada"), _pupil("Bea")
    ma = CL.add_member(c.club_id, a)
    mb = CL.add_member(c.club_id, b)
    CL.set_member_status(mb.membership_id, "withdrawn")
    assert CL.counts()["active_members"] == 1
    assert CL.remove_member(ma.membership_id) is True
    assert CL.counts()["active_members"] == 0
    assert [p.pupil_id for p, _ in CL.list_members(c.club_id)] == [b]

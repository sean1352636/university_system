"""Departments + memberships (systems.primary.domain.staff.departments.departments)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.staff import staff as S
from education_system.systems.primary.domain.staff.departments import departments as DP

TODAY = dt.date.today().isoformat()


def _staff(first="Amy", last="Adams"):
    return S.create_staff({"first_name": first, "last_name": last})


def _dept(name="KS1", **extra):
    return DP.create_department({"name": name, **extra})


# ── Departments ──────────────────────────────────────────────────────

def test_create_defaults_and_budget_figures():
    head = _staff()
    d = _dept(" KS1 ", code=" K1 ", head_of_department=head.staff_id, budget_total="1000",
              budget_spent="250.5", budget_year="2025-26")
    assert (d.name, d.code, d.faculty, d.status) == ("KS1", "K1", "Other", "Active")
    assert (d.head_of_department, d.budget_total, d.budget_spent) == (head.staff_id, 1000.0,
                                                                     250.5)
    assert d.is_active is True
    assert d.budget_remaining == 749.5 and d.budget_over is False
    assert DP.get_department(d.department_id) == d
    assert DP.get_department(999) is None


def test_budget_remaining_without_total_and_overspend():
    no_budget = _dept("No budget", budget_spent=50)
    assert no_budget.budget_remaining is None and no_budget.budget_over is False
    no_spend = _dept("Fresh", budget_total=500)
    assert no_spend.budget_remaining == 500.0
    over = _dept("Over", budget_total=100, budget_spent=120.25)
    assert over.budget_remaining == -20.25 and over.budget_over is True


@pytest.mark.parametrize("bad, msg", [
    ({"name": " "}, "Name is required"),
    ({"faculty": "Medicine"}, "Faculty must be one of"),
    ({"status": "Open"}, "Status must be one of"),
    ({"head_of_department": "T0000000"}, "head of department: no staff with id T0000000"),
    ({"deputy_head": "T0000001"}, "deputy head: no staff with id T0000001"),
    ({"budget_total": "lots"}, "budget total must be a number"),
    ({"budget_allocated": -1}, "budget allocated must be >= 0"),
    ({"budget_spent": -0.01}, "budget spent must be >= 0"),
])
def test_create_refusals(bad, msg):
    data = {"name": "KS2", **bad}
    with pytest.raises(DP.ValidationError, match=msg):
        DP.create_department(data)
    assert DP.list_departments() == []


def test_name_is_unique():
    a = _dept("Maths")
    with pytest.raises(DP.ValidationError, match="named 'Maths' already exists"):
        _dept("Maths")
    b = _dept("English")
    assert DP.update_department(a.department_id, {"name": "Maths", "notes": "x"}).notes == "x"
    with pytest.raises(DP.ValidationError, match="already exists"):
        DP.update_department(b.department_id, {"name": "Maths"})


def test_update_set_status_and_delete():
    d = _dept(code="K1")
    up = DP.update_department(d.department_id, {"name": "Key Stage 1", "faculty": "Pastoral"})
    assert (up.name, up.faculty, up.code) == ("Key Stage 1", "Pastoral", None)
    with pytest.raises(DP.ValidationError, match="No department with id 999"):
        DP.update_department(999, {"name": "x"})
    assert DP.set_status(d.department_id, "Restructuring").is_active is False
    with pytest.raises(DP.ValidationError, match="Status must be one of"):
        DP.set_status(d.department_id, "Closed")
    with pytest.raises(DP.ValidationError, match="No department with id 999"):
        DP.set_status(999, "Active")
    assert DP.delete_department(d.department_id) is True
    assert DP.delete_department(d.department_id) is False


def test_add_spend():
    d = _dept(budget_total=100)
    assert DP.add_spend(d.department_id, amount=30.10).budget_spent == 30.1
    out = DP.add_spend(d.department_id, amount="80")
    assert out.budget_spent == 110.1 and out.budget_over is True
    assert out.budget_remaining == -10.1
    with pytest.raises(DP.ValidationError, match="Amount must be a number"):
        DP.add_spend(d.department_id, amount="ten")
    with pytest.raises(DP.ValidationError, match="No department with id 999"):
        DP.add_spend(999, amount=1)
    with pytest.raises(DP.ValidationError, match="budget spent must be >= 0"):
        DP.add_spend(d.department_id, amount=-500)


def test_list_filters_and_order():
    a = _dept("Maths", faculty="Mathematics & Computing", budget_total=10, budget_spent=20)
    b = _dept("Art", faculty="Arts", status="Disbanded")
    c = _dept("Science", faculty="Arts")
    ids = lambda rows: [x.department_id for x in rows]  # noqa: E731
    assert ids(DP.list_departments()) == [b.department_id, c.department_id, a.department_id]
    assert ids(DP.list_departments(faculty="Arts")) == [b.department_id, c.department_id]
    assert ids(DP.list_departments(status="Disbanded")) == [b.department_id]
    assert ids(DP.list_departments(active_only=True)) == [c.department_id, a.department_id]
    assert ids(DP.list_departments(name_like="sci")) == [c.department_id]
    assert ids(DP.list_departments(over_budget=True)) == [a.department_id]


# ── Memberships ──────────────────────────────────────────────────────

def test_add_member_defaults_and_read_back():
    s = _staff()
    d = _dept()
    m = DP.add_member(d.department_id, {"staff_id": s.staff_id, "notes": " n "})
    assert (m.department_id, m.staff_id, m.role_in_department) == (d.department_id,
                                                                   s.staff_id, "Teacher")
    assert (m.is_primary, m.joined_on, m.left_on, m.notes) == (False, TODAY, None, "n")
    assert m.is_current is True
    assert DP.get_membership(m.membership_id) == m
    assert DP.get_membership(999) is None


@pytest.mark.parametrize("bad, msg", [
    ({"staff_id": ""}, "Staff is required"),
    ({"staff_id": "T0000000"}, "No staff with id T0000000"),
    ({"role_in_department": "Boss"}, "Role must be one of"),
    ({"joined_on": "1/9/2025"}, "Joined on must be YYYY-MM-DD"),
    ({"left_on": "x"}, "Left on must be YYYY-MM-DD"),
    ({"joined_on": "2025-09-01", "left_on": "2025-08-31"}, "Left on must be on or after"),
])
def test_member_refusals(bad, msg):
    s = _staff()
    d = _dept()
    with pytest.raises(DP.ValidationError, match=msg):
        DP.add_member(d.department_id, {"staff_id": s.staff_id, **bad})
    assert DP.member_count(d.department_id) == 0


def test_member_needs_a_department():
    s = _staff()
    with pytest.raises(DP.ValidationError, match="No department with id 999"):
        DP.add_member(999, {"staff_id": s.staff_id})


def test_one_current_primary_department_per_staff():
    s = _staff()
    ks1 = _dept("KS1")
    ks2 = _dept("KS2")
    first = DP.add_member(ks1.department_id, {"staff_id": s.staff_id, "is_primary": True,
                                              "joined_on": "2025-09-01"})
    with pytest.raises(DP.ValidationError, match="already has a primary department"):
        DP.add_member(ks2.department_id, {"staff_id": s.staff_id, "is_primary": True})
    second = DP.add_member(ks2.department_id, {"staff_id": s.staff_id})
    with pytest.raises(DP.ValidationError, match="already has a primary department"):
        DP.update_membership(second.membership_id, {"staff_id": s.staff_id,
                                                    "is_primary": True})
    DP.end_membership(first.membership_id, left_on="2026-01-01")
    out = DP.update_membership(second.membership_id, {"staff_id": s.staff_id,
                                                      "is_primary": True})
    assert out.is_primary is True


def test_update_end_delete_membership():
    s = _staff()
    d = _dept()
    m = DP.add_member(d.department_id, {"staff_id": s.staff_id, "joined_on": "2024-09-01",
                                        "role_in_department": "Subject Lead"})
    up = DP.update_membership(m.membership_id, {"staff_id": s.staff_id,
                                                "role_in_department": "Coordinator",
                                                "joined_on": "2024-09-01"})
    assert up.role_in_department == "Coordinator"
    with pytest.raises(DP.ValidationError, match="No membership with id 999"):
        DP.update_membership(999, {"staff_id": s.staff_id})
    ended = DP.end_membership(m.membership_id, left_on="2025-07-20")
    assert (ended.left_on, ended.is_current, ended.role_in_department) == (
        "2025-07-20", False, "Coordinator")
    with pytest.raises(DP.ValidationError, match="Left on must be on or after"):
        DP.end_membership(m.membership_id, left_on="2020-01-01")
    with pytest.raises(DP.ValidationError, match="No membership with id 999"):
        DP.end_membership(999)
    assert DP.delete_membership(m.membership_id) is True
    assert DP.delete_membership(m.membership_id) is False


def test_end_membership_defaults_to_today():
    s = _staff()
    d = _dept()
    m = DP.add_member(d.department_id, {"staff_id": s.staff_id, "joined_on": "2024-09-01"})
    assert DP.end_membership(m.membership_id).left_on == TODAY


def test_listing_counts_and_prune():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    d = _dept()
    other = _dept("KS2")
    old = DP.add_member(d.department_id, {"staff_id": a.staff_id, "joined_on": "2020-09-01",
                                          "left_on": "2021-07-01"})
    ta = DP.add_member(d.department_id, {"staff_id": b.staff_id,
                                         "role_in_department": "Teaching Assistant"})
    lead = DP.add_member(d.department_id, {"staff_id": a.staff_id, "is_primary": True,
                                           "joined_on": "2022-09-01"})
    elsewhere = DP.add_member(other.department_id, {"staff_id": a.staff_id,
                                                    "joined_on": "2023-09-01"})
    ids = lambda rows: [m.membership_id for m in rows]  # noqa: E731
    # current first, then primary, then by role
    assert ids(DP.list_memberships(d.department_id)) == [lead.membership_id, ta.membership_id,
                                                         old.membership_id]
    assert ids(DP.memberships_for_staff(a.staff_id)) == [elsewhere.membership_id,
                                                         lead.membership_id,
                                                         old.membership_id]
    assert DP.member_count(d.department_id) == 2
    assert DP.member_count(d.department_id, current_only=False) == 3
    assert DP.prune_for_staff(a.staff_id) == 3
    assert DP.memberships_for_staff(a.staff_id) == []
    assert DP.prune_for_staff(a.staff_id) == 0


def test_department_delete_cascades_members_but_staff_delete_does_not():
    s = _staff()
    d = _dept()
    m = DP.add_member(d.department_id, {"staff_id": s.staff_id})
    S.delete_staff(s.staff_id)
    # soft link to staff: history is kept until prune_for_staff is called
    assert DP.get_membership(m.membership_id) is not None
    DP.delete_department(d.department_id)
    assert DP.get_membership(m.membership_id) is None


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = DP.summary()
    assert (sm.total, sm.budget_total, sm.distinct_staff) == (0, 0.0, 0)


def test_summary_figures():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    ks1 = _dept("KS1", faculty="Pastoral", budget_total=1000, budget_spent=400.25)
    ks2 = _dept("KS2", faculty="Pastoral", budget_total=200, budget_spent=250,
                status="Restructuring")
    _dept("Old", status="Disbanded")
    _dept("Merged", status="Merged")
    DP.add_member(ks1.department_id, {"staff_id": a.staff_id})
    DP.add_member(ks2.department_id, {"staff_id": a.staff_id})
    DP.add_member(ks2.department_id, {"staff_id": b.staff_id, "joined_on": "2020-01-01",
                                      "left_on": "2021-01-01"})
    sm = DP.summary()
    assert (sm.total, sm.active, sm.restructuring, sm.disbanded) == (4, 1, 1, 1)
    assert (sm.budget_total, sm.budget_spent, sm.budget_over_count) == (1200.0, 650.25, 1)
    assert (sm.total_members, sm.distinct_staff) == (2, 1)
    assert sm.by_faculty == {"Pastoral": 2, "Other": 2}
    assert sm.by_status == {"Active": 1, "Restructuring": 1, "Disbanded": 1, "Merged": 1}

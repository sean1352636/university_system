"""Policy register and revision log (domain.governance.policies.policies)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.governance.policies import policies as PO

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _pol(title="Safeguarding Policy", **extra):
    return PO.create_policy({"title": title, **extra})


def _rev(policy_id, version="1.1", revised_on="2026-03-01", **extra):
    return PO.add_revision(policy_id, {"version": version, "revised_on": revised_on, **extra})


# ── create / read ──

def test_create_policy_defaults():
    p = _pol("  Behaviour Policy ")
    assert p.title == "Behaviour Policy"
    assert (p.category, p.version, p.status, p.review_cycle) == ("Other", "1.0", "Draft", "Annual")
    assert p.approved_on is None and p.next_review is None and p.owner is None
    assert PO.get_policy(p.policy_id) == p


def test_create_policy_stores_fields():
    p = _pol(category="SEND", version="2.3.1", owner=" SENCO ", status="Approved",
             review_cycle="Triennial", summary=" s ", document_ref=" doc/1 ",
             next_review="2027-01-01")
    assert (p.category, p.version, p.owner) == ("SEND", "2.3.1", "SENCO")
    assert (p.status, p.review_cycle) == ("Approved", "Triennial")
    assert (p.summary, p.document_ref, p.next_review) == ("s", "doc/1", "2027-01-01")


@pytest.mark.parametrize("cycle, expected", [
    ("Annual", "2027-01-01"), ("Biennial", "2028-01-01"),
    ("Triennial", "2028-12-31"), ("Ad-hoc", None),
])
def test_next_review_derived_from_approved_on(cycle, expected):
    p = _pol(review_cycle=cycle, approved_on="2026-01-01")
    assert p.next_review == expected


def test_explicit_next_review_kept():
    assert _pol(approved_on="2026-01-01", next_review="2026-06-01").next_review == "2026-06-01"


def test_get_missing_policy_is_none():
    assert PO.get_policy(1) is None


# ── validation ──

def test_title_required_and_length():
    with pytest.raises(PO.ValidationError, match="Title is required"):
        _pol(" ")
    with pytest.raises(PO.ValidationError, match="200 chars"):
        _pol("t" * 201)


def test_category_status_cycle_must_be_known():
    with pytest.raises(PO.ValidationError, match="Category must be one of"):
        _pol(category="Uniform")
    with pytest.raises(PO.ValidationError, match="Status must be one of"):
        _pol(status="Overdue review")
    with pytest.raises(PO.ValidationError, match="Review cycle must be one of"):
        _pol(review_cycle="Monthly")


@pytest.mark.parametrize("version", ["v1", "1.0.0.0", "1.", "one"])
def test_version_must_be_numeric(version):
    with pytest.raises(PO.ValidationError, match="Version must be numeric"):
        _pol(version=version)


@pytest.mark.parametrize("version", ["1", "1.0", "2.3.1"])
def test_version_accepted(version):
    assert _pol(version=version).version == version


def test_dates_and_summary_validated():
    with pytest.raises(PO.ValidationError, match="Approved on must be YYYY-MM-DD"):
        _pol(approved_on="01-01-2026")
    with pytest.raises(PO.ValidationError, match="Next review must be YYYY-MM-DD"):
        _pol(next_review="soon")
    with pytest.raises(PO.ValidationError, match="Summary must be 2000"):
        _pol(summary="s" * 2001)


# ── list / filter ──

def test_list_policies_empty():
    assert PO.list_policies() == []


def test_list_policies_sorted_by_next_review_then_title():
    b = _pol("B", next_review="2026-05-01")
    a = _pol("A", next_review="2026-05-01")
    z = _pol("Z")
    c = _pol("C", next_review="2026-01-01")
    assert [p.policy_id for p in PO.list_policies()] == [c.policy_id, a.policy_id,
                                                         b.policy_id, z.policy_id]


def test_list_policies_filters():
    _pol("Online safety", category="IT & Online", owner="Computing lead",
         summary="Filtering and monitoring")
    _pol("Charging", category="Finance", status="Approved", owner="Bursar")
    assert [p.title for p in PO.list_policies(category="Finance")] == ["Charging"]
    assert [p.title for p in PO.list_policies(status="Approved")] == ["Charging"]
    assert [p.title for p in PO.list_policies(owner="computing")] == ["Online safety"]
    assert [p.title for p in PO.list_policies(query="monitoring")] == ["Online safety"]


def test_list_policies_bad_filters_refused():
    with pytest.raises(PO.ValidationError):
        PO.list_policies(category="Nope")
    with pytest.raises(PO.ValidationError):
        PO.list_policies(status="Overdue review")


def test_list_policies_overdue_only():
    late = _pol("late", next_review=_iso(-1))
    _pol("archived", next_review=_iso(-10), status="Archived")
    _pol("today", next_review=_iso(0))
    _pol("undated")
    assert [p.policy_id for p in PO.list_policies(overdue_only=True)] == [late.policy_id]


# ── update / delete ──

def test_update_policy_partial():
    p = _pol(owner="Head")
    out = PO.update_policy(p.policy_id, {"status": "Under review"})
    assert out.status == "Under review" and out.owner == "Head" and out.title == p.title


def test_update_policy_empty_is_noop_and_validates():
    p = _pol()
    assert PO.update_policy(p.policy_id, {}) == p
    with pytest.raises(PO.ValidationError, match="Version"):
        PO.update_policy(p.policy_id, {"version": "x"})
    with pytest.raises(PO.ValidationError, match="No policy #50"):
        PO.update_policy(50, {"title": "x"})


def test_delete_policy_cascades_revisions():
    p = _pol()
    r = _rev(p.policy_id)
    assert PO.delete_policy(p.policy_id) is True
    assert PO.get_policy(p.policy_id) is None
    assert PO.list_revisions(p.policy_id) == []
    assert PO.delete_revision(r.revision_id) is False
    assert PO.delete_policy(p.policy_id) is False


# ── revisions ──

def test_add_revision_without_approver_leaves_policy_alone():
    p = _pol(version="1.0")
    r = _rev(p.policy_id, "1.1", revised_by=" Ann ", changes=" typo ")
    assert (r.policy_id, r.version, r.revised_on) == (p.policy_id, "1.1", "2026-03-01")
    assert (r.revised_by, r.changes, r.approved_by) == ("Ann", "typo", None)
    after = PO.get_policy(p.policy_id)
    assert after.version == "1.0" and after.status == "Draft" and after.approved_on is None


def test_add_approved_revision_syncs_policy():
    p = _pol(review_cycle="Biennial")
    _rev(p.policy_id, "2.0", "2026-03-01", approved_by="FGB")
    after = PO.get_policy(p.policy_id)
    assert after.version == "2.0" and after.status == "Approved"
    assert after.approved_on == "2026-03-01"
    assert after.next_review == "2028-02-29"     # +730 days


def test_approved_revision_on_adhoc_policy_clears_next_review():
    p = _pol(review_cycle="Ad-hoc", next_review="2026-12-01")
    _rev(p.policy_id, approved_by="Head")
    assert PO.get_policy(p.policy_id).next_review is None


def test_revision_validation():
    p = _pol()
    with pytest.raises(PO.ValidationError, match="Version is required"):
        PO.add_revision(p.policy_id, {"revised_on": "2026-01-01"})
    with pytest.raises(PO.ValidationError, match="Revised on is required"):
        PO.add_revision(p.policy_id, {"version": "1.1"})
    with pytest.raises(PO.ValidationError, match="Revised on must be YYYY-MM-DD"):
        _rev(p.policy_id, revised_on="March")
    with pytest.raises(PO.ValidationError, match="No policy #9"):
        _rev(9)


def test_list_revisions_newest_first():
    p = _pol()
    a = _rev(p.policy_id, "1.1", "2026-01-01")
    b = _rev(p.policy_id, "1.2", "2026-05-01")
    c = _rev(p.policy_id, "1.3", "2026-05-01")
    assert [r.revision_id for r in PO.list_revisions(p.policy_id)] == \
        [c.revision_id, b.revision_id, a.revision_id]
    assert PO.list_revisions(999) == []


def test_delete_revision():
    p = _pol()
    r = _rev(p.policy_id)
    assert PO.delete_revision(r.revision_id) is True
    assert PO.list_revisions(p.policy_id) == []


# ── views ──

def test_view_policy_overdue_and_counts():
    p = _pol(next_review=_iso(-3), status="Approved")
    _rev(p.policy_id)
    _rev(p.policy_id, "1.2")
    v = PO.view_policy(p.policy_id)
    assert v.derived_status == "Overdue review"
    assert v.days_until_review == -3
    assert v.revisions_count == 2


def test_view_policy_archived_never_overdue_and_undated():
    a = _pol(next_review=_iso(-3), status="Archived")
    u = _pol("undated")
    assert PO.view_policy(a.policy_id).derived_status == "Archived"
    vu = PO.view_policy(u.policy_id)
    assert vu.days_until_review is None and vu.derived_status == "Draft"
    assert PO.view_policy(404) is None


def test_list_views_counts_and_filters():
    assert PO.list_views() == []
    p1 = _pol("one", category="HR")
    _pol("two", category="HR")
    _rev(p1.policy_id)
    views = {v.policy.title: v.revisions_count for v in PO.list_views(category="HR")}
    assert views == {"one": 1, "two": 0}


# ── summary ──

def test_summary_empty():
    s = PO.summary()
    assert (s.total, s.overdue, s.due_soon, s.no_review_date, s.total_revisions) == (0, 0, 0, 0, 0)
    assert s.by_status == {k: 0 for k in PO.DERIVED_STATUSES}
    assert s.by_category == {k: 0 for k in PO.CATEGORIES}


def test_summary_counts():
    o = _pol("over", category="HR", next_review=_iso(-1), status="Approved")
    _pol("soon", category="HR", next_review=_iso(30))
    _pol("today", category="SEND", next_review=_iso(0))
    _pol("far", next_review=_iso(31))
    _pol("undated", status="Under review")
    _rev(o.policy_id)
    _rev(o.policy_id, "1.2")
    s = PO.summary()
    assert s.total == 5
    assert (s.overdue, s.due_soon, s.no_review_date, s.total_revisions) == (1, 2, 1, 2)
    assert s.by_category["HR"] == 2 and s.by_category["SEND"] == 1 and s.by_category["Other"] == 2
    assert s.by_status["Overdue review"] == 1 and s.by_status["Draft"] == 3
    assert s.by_status["Under review"] == 1 and s.by_status["Approved"] == 0
    assert PO.summary(due_soon_days=0).due_soon == 1

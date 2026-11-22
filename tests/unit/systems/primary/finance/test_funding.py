"""Funding streams and learner allocations
(systems.primary.domain.finance.funding.funding).

Amounts here are pounds held as floats (REAL columns), not pence.
"""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.finance.funding import funding as F

AY = "2025-26"


def _stream(**extra) -> F.FundingStream:
    data = {"name": "Pupil Premium 25-26", "stream_type": "Pupil Premium",
            "funder": "ESFA", "academic_year": AY,
            "allocated_amount": 1000, **extra}
    return F.create_stream(data)


def _alloc(stream_id=None, **extra) -> F.LearnerAllocation:
    data = {"stream_id": stream_id, "learner_ref": "P001",
            "learner_name": "Ada Lovelace", "funding_band": "Pupil Premium",
            "band_value": 1455, "committed_amount": 300,
            "starts_on": "2025-09-01", **extra}
    return F.create_allocation(data)


# ── streams: create / read ──

def test_create_stream_stores_values_and_defaults():
    s = F.create_stream({"name": "  Core  ", "academic_year": AY,
                         "allocated_amount": "2500.50",
                         "reference": "  REF1 ", "owner": "",
                         "starts_on": "2025-09-01", "ends_on": "2026-08-31"})
    got = F.get_stream(s.stream_id)
    assert got == s
    assert s.name == "Core"
    assert s.stream_type == F.DEFAULT_STREAM_TYPE
    assert s.funder == F.DEFAULT_FUNDER
    assert s.status == F.DEFAULT_STREAM_STATUS == "Planned"
    assert s.allocated_amount == 2500.5
    assert (s.committed_amount, s.drawn_down_amount) == (0.0, 0.0)
    assert s.reference == "REF1"
    assert s.owner is None
    assert (s.starts_on, s.ends_on) == ("2025-09-01", "2026-08-31")
    assert s.created_on and s.updated_on


def test_get_stream_missing_is_none():
    assert F.get_stream(999) is None


def test_stream_derived_properties():
    s = _stream(allocated_amount=1000, committed_amount=400,
                drawn_down_amount=250)
    assert s.remaining == 600.0
    assert s.headroom == 750.0
    assert s.utilisation_pct == 25.0
    assert s.is_overcommitted is False
    over = _stream(name="Over", allocated_amount=100, committed_amount=150)
    assert over.is_overcommitted is True
    assert over.remaining == -50.0
    zero = _stream(name="Zero", allocated_amount=0)
    assert zero.utilisation_pct == 0.0


# ── streams: validation ──

def test_stream_name_required():
    with pytest.raises(F.ValidationError, match="Name is required"):
        F.create_stream({"name": "   ", "academic_year": AY})


def test_stream_academic_year_required():
    with pytest.raises(F.ValidationError, match="Academic year is required"):
        F.create_stream({"name": "X"})


def test_stream_type_must_be_listed():
    with pytest.raises(F.ValidationError, match="Stream type must be one of"):
        _stream(stream_type="Lottery")


def test_stream_funder_must_be_listed():
    with pytest.raises(F.ValidationError, match="Funder must be one of"):
        _stream(funder="Santa")


def test_stream_status_must_be_listed():
    with pytest.raises(F.ValidationError, match="Status must be one of"):
        _stream(status="Spent")


def test_stream_dates_must_be_iso():
    with pytest.raises(F.ValidationError, match="Starts on must be YYYY-MM-DD"):
        _stream(starts_on="01/09/2025")
    with pytest.raises(F.ValidationError, match="Ends on must be YYYY-MM-DD"):
        _stream(ends_on="2026-02-30")


def test_stream_end_before_start_refused():
    with pytest.raises(F.ValidationError, match="Ends on cannot be before"):
        _stream(starts_on="2025-09-01", ends_on="2025-08-31")


def test_stream_amounts_must_be_non_negative_numbers():
    with pytest.raises(F.ValidationError, match="Allocated amount must be a number"):
        _stream(allocated_amount="lots")
    with pytest.raises(F.ValidationError, match="Allocated amount must be >= 0"):
        _stream(allocated_amount=-1)
    with pytest.raises(F.ValidationError, match="Committed amount must be >= 0"):
        _stream(committed_amount=-5)
    with pytest.raises(F.ValidationError, match="Drawn-down amount must be >= 0"):
        _stream(drawn_down_amount=-5)


def test_stream_name_unique_per_academic_year():
    _stream()
    with pytest.raises(F.ValidationError, match="already exists"):
        _stream()
    other_year = _stream(academic_year="2026-27")
    assert other_year.name == "Pupil Premium 25-26"


# ── streams: update / delete ──

def test_update_stream_changes_fields_and_keeps_own_name():
    s = _stream()
    up = F.update_stream(s.stream_id, {"name": s.name, "academic_year": AY,
                                       "stream_type": "Pupil Premium",
                                       "funder": "DfE", "allocated_amount": 1200})
    assert up.funder == "DfE"
    assert up.allocated_amount == 1200.0
    assert F.get_stream(s.stream_id).funder == "DfE"


def test_update_stream_cannot_take_another_streams_name():
    _stream(name="A")
    b = _stream(name="B")
    with pytest.raises(F.ValidationError, match="already exists"):
        F.update_stream(b.stream_id, {"name": "A", "academic_year": AY})


def test_update_missing_stream_refused():
    with pytest.raises(F.ValidationError, match="No stream with id 42"):
        F.update_stream(42, {"name": "X", "academic_year": AY})


def test_delete_stream_and_allocations_survive_unlinked():
    s = _stream()
    a = _alloc(s.stream_id)
    assert F.delete_stream(s.stream_id) is True
    assert F.get_stream(s.stream_id) is None
    assert F.get_allocation(a.allocation_id).stream_id is None
    assert F.delete_stream(s.stream_id) is False


# ── streams: listing ──

def test_list_streams_filters_and_order():
    a = _stream(name="Core", stream_type=F.DEFAULT_STREAM_TYPE,
                funder="Local Authority", status="Active")
    b = _stream(name="PE", stream_type="PE and Sport Premium",
                funder="DfE", status="Planned", allocated_amount=100,
                committed_amount=200)
    c = _stream(name="Old", academic_year="2024-25", status="Closed")
    ids = [s.stream_id for s in F.list_streams()]
    # academic_year DESC, then stream_type, then name
    assert ids == [a.stream_id, b.stream_id, c.stream_id]
    assert [s.stream_id for s in F.list_streams(funder="DfE")] == [b.stream_id]
    assert [s.stream_id for s in F.list_streams(academic_year="2024-25")] == [c.stream_id]
    assert [s.stream_id for s in F.list_streams(status="Closed")] == [c.stream_id]
    assert [s.stream_id for s in F.list_streams(
        stream_type="PE and Sport Premium")] == [b.stream_id]
    assert [s.stream_id for s in F.list_streams(active_only=True)] == [a.stream_id]
    assert [s.stream_id for s in F.list_streams(overcommitted_only=True)] == [b.stream_id]
    assert [s.stream_id for s in F.list_streams(name_like="or")] == [a.stream_id]


def test_list_streams_empty():
    assert F.list_streams() == []
    assert F.list_allocations() == []


# ── stream workflow ──

def test_stream_workflow_status_changes_keep_other_fields():
    s = _stream(reference="R9", owner="Bursar")
    assert F.confirm_stream(s.stream_id).status == "Confirmed"
    assert F.activate_stream(s.stream_id).status == "Active"
    assert F.close_stream(s.stream_id).status == "Closed"
    done = F.reconcile_stream(s.stream_id)
    assert done.status == "Reconciled"
    assert (done.reference, done.owner, done.allocated_amount) == ("R9", "Bursar", 1000.0)
    assert F.set_stream_status(s.stream_id, "Underspent").status == "Underspent"


def test_stream_workflow_refusals():
    for fn in (F.confirm_stream, F.activate_stream, F.close_stream, F.reconcile_stream):
        with pytest.raises(F.ValidationError, match="No stream with id 77"):
            fn(77)
    s = _stream()
    with pytest.raises(F.ValidationError, match="Status must be one of"):
        F.set_stream_status(s.stream_id, "Done")
    with pytest.raises(F.ValidationError, match="No stream with id 77"):
        F.set_stream_status(77, "Active")


# ── allocations: create / validation ──

def test_create_allocation_stores_values_and_defaults():
    a = F.create_allocation({"learner_ref": " P9 ", "starts_on": "2025-09-01",
                             "learner_name": " ", "committed_amount": "250"})
    got = F.get_allocation(a.allocation_id)
    assert got == a
    assert a.learner_ref == "P9"
    assert a.learner_name is None
    assert a.stream_id is None
    assert a.funding_band == F.DEFAULT_FUNDING_BAND
    assert a.status == F.DEFAULT_ALLOCATION_STATUS == "Provisional"
    assert (a.band_value, a.committed_amount, a.drawn_down_amount) == (0.0, 250.0, 0.0)
    assert a.remaining == 250.0


def test_get_allocation_missing_is_none():
    assert F.get_allocation(5) is None


def test_allocation_learner_ref_required():
    with pytest.raises(F.ValidationError, match="Learner ref is required"):
        _alloc(learner_ref="  ")


def test_allocation_band_must_be_listed():
    with pytest.raises(F.ValidationError, match="Funding band must be one of"):
        _alloc(funding_band="Gold")


def test_allocation_status_must_be_listed():
    with pytest.raises(F.ValidationError, match="Status must be one of"):
        _alloc(status="Paid")


def test_allocation_starts_on_required_and_dates_checked():
    with pytest.raises(F.ValidationError, match="Starts on is required"):
        _alloc(starts_on="")
    with pytest.raises(F.ValidationError, match="Starts on must be YYYY-MM-DD"):
        _alloc(starts_on="2025/09/01")
    with pytest.raises(F.ValidationError, match="Ends on must be YYYY-MM-DD"):
        _alloc(ends_on="soon")
    with pytest.raises(F.ValidationError, match="Ends on cannot be before"):
        _alloc(ends_on="2025-08-01")


def test_allocation_stream_id_must_be_integer_and_exist():
    with pytest.raises(F.ValidationError, match="Stream id must be an integer"):
        _alloc(stream_id="abc")
    with pytest.raises(F.ValidationError, match="No stream with id 99"):
        _alloc(stream_id=99)


def test_allocation_amount_rules():
    with pytest.raises(F.ValidationError, match="Band value must be a number"):
        _alloc(band_value="x")
    with pytest.raises(F.ValidationError, match="Committed amount must be >= 0"):
        _alloc(committed_amount=-1)
    with pytest.raises(F.ValidationError, match="cannot exceed committed amount"):
        _alloc(committed_amount=100, drawn_down_amount=101)


# ── allocations roll up onto the stream ──

def test_allocations_recompute_stream_totals():
    s = _stream(allocated_amount=1000)
    a1 = _alloc(s.stream_id, committed_amount=300, drawn_down_amount=100)
    _alloc(s.stream_id, learner_ref="P002", committed_amount=450.25,
           drawn_down_amount=50)
    got = F.get_stream(s.stream_id)
    assert got.committed_amount == 750.25
    assert got.drawn_down_amount == 150.0
    assert got.remaining == 249.75
    assert got.utilisation_pct == 15.0

    F.delete_allocation(a1.allocation_id)
    got = F.get_stream(s.stream_id)
    assert (got.committed_amount, got.drawn_down_amount) == (450.25, 50.0)


def test_moving_allocation_between_streams_updates_both():
    s1 = _stream(name="S1")
    s2 = _stream(name="S2")
    a = _alloc(s1.stream_id, committed_amount=200)
    data = {"stream_id": s2.stream_id, "learner_ref": a.learner_ref,
            "starts_on": a.starts_on, "committed_amount": 200}
    F.update_allocation(a.allocation_id, data)
    assert F.get_stream(s1.stream_id).committed_amount == 0.0
    assert F.get_stream(s2.stream_id).committed_amount == 200.0


def test_update_allocation_refusals():
    with pytest.raises(F.ValidationError, match="No allocation with id 8"):
        F.update_allocation(8, {"learner_ref": "P", "starts_on": "2025-09-01"})
    a = _alloc()
    with pytest.raises(F.ValidationError, match="No stream with id 55"):
        F.update_allocation(a.allocation_id, {"learner_ref": "P",
                                              "starts_on": "2025-09-01",
                                              "stream_id": 55})


def test_delete_allocation_missing_is_false():
    assert F.delete_allocation(123) is False
    a = _alloc()
    assert F.delete_allocation(a.allocation_id) is True
    assert F.get_allocation(a.allocation_id) is None


# ── allocations: listing ──

def test_list_allocations_filters_and_order():
    s = _stream()
    b = _alloc(s.stream_id, learner_ref="P2", status="Active",
               funding_band="High Needs Top-Up")
    a2 = _alloc(None, learner_ref="P1", starts_on="2025-10-01", status="Approved")
    a1 = _alloc(None, learner_ref="P1", starts_on="2025-09-01")
    assert [x.allocation_id for x in F.list_allocations()] == [
        a1.allocation_id, a2.allocation_id, b.allocation_id]
    assert [x.allocation_id for x in F.list_allocations(stream_id=s.stream_id)] == [b.allocation_id]
    assert [x.allocation_id for x in F.allocations_for_stream(s.stream_id)] == [b.allocation_id]
    assert [x.allocation_id for x in F.allocations_for_learner("P1")] == [
        a1.allocation_id, a2.allocation_id]
    assert [x.allocation_id for x in F.list_allocations(
        funding_band="High Needs Top-Up")] == [b.allocation_id]
    assert [x.allocation_id for x in F.list_allocations(status="Provisional")] == [a1.allocation_id]
    assert {x.allocation_id for x in F.list_allocations(active_only=True)} == {
        a2.allocation_id, b.allocation_id}
    assert F.allocations_for_learner("nobody") == []


# ── allocation workflow ──

def test_allocation_workflow_statuses():
    a = _alloc(purpose="Tutoring")
    ap = F.approve_allocation(a.allocation_id, approved_by="Head")
    assert (ap.status, ap.approved_by) == ("Approved", "Head")
    assert F.activate_allocation(a.allocation_id).status == "Active"
    assert F.suspend_allocation(a.allocation_id).status == "Suspended"
    assert F.close_allocation(a.allocation_id).status == "Closed"
    w = F.withdraw_allocation(a.allocation_id)
    assert (w.status, w.purpose, w.approved_by) == ("Withdrawn", "Tutoring", "Head")
    assert F.set_allocation_status(a.allocation_id, "Active").status == "Active"


def test_approve_without_approver_keeps_existing():
    a = _alloc(approved_by="Deputy")
    assert F.approve_allocation(a.allocation_id).approved_by == "Deputy"


def test_allocation_workflow_refusals():
    for fn in (F.approve_allocation, F.activate_allocation, F.suspend_allocation,
               F.close_allocation, F.withdraw_allocation):
        with pytest.raises(F.ValidationError, match="No allocation with id 31"):
            fn(31)
    a = _alloc()
    with pytest.raises(F.ValidationError, match="Status must be one of"):
        F.set_allocation_status(a.allocation_id, "Gone")
    with pytest.raises(F.ValidationError, match="No allocation with id 31"):
        F.set_allocation_status(31, "Active")


# ── drawdowns ──

def test_record_drawdown_accumulates_and_marks_drawn_down():
    s = _stream()
    a = _alloc(s.stream_id, committed_amount=100, status="Active")
    a = F.record_drawdown(a.allocation_id, amount=40.5)
    assert (a.drawn_down_amount, a.status, a.remaining) == (40.5, "Active", 59.5)
    assert F.get_stream(s.stream_id).drawn_down_amount == 40.5
    a = F.record_drawdown(a.allocation_id, amount=59.5)
    assert (a.drawn_down_amount, a.status, a.remaining) == (100.0, "Drawn Down", 0.0)
    assert F.get_stream(s.stream_id).drawn_down_amount == 100.0


def test_record_drawdown_refusals():
    with pytest.raises(F.ValidationError, match="No allocation with id 4"):
        F.record_drawdown(4, amount=1)
    a = _alloc(committed_amount=100)
    with pytest.raises(F.ValidationError, match="must be > 0"):
        F.record_drawdown(a.allocation_id, amount=0)
    with pytest.raises(F.ValidationError, match="must be > 0"):
        F.record_drawdown(a.allocation_id, amount=-5)
    with pytest.raises(F.ValidationError, match="would exceed committed"):
        F.record_drawdown(a.allocation_id, amount=100.01)
    assert F.get_allocation(a.allocation_id).drawn_down_amount == 0.0


# ── summary ──

def test_summary_empty():
    s = F.summary()
    assert (s.total_streams, s.total_allocations, s.distinct_learners) == (0, 0, 0)
    assert (s.total_allocated, s.total_remaining, s.avg_utilisation_pct) == (0.0, 0.0, 0.0)
    assert s.by_stream_type == {} and s.by_band == {}


def test_summary_figures():
    s1 = _stream(name="S1", allocated_amount=1000, status="Active")
    s2 = _stream(name="S2", allocated_amount=200, status="Planned",
                 funder="DfE", stream_type="PE and Sport Premium")
    _stream(name="S3", allocated_amount=0, status="Reconciled")
    _alloc(s1.stream_id, learner_ref="P1", committed_amount=500,
           drawn_down_amount=250, status="Active")
    _alloc(s2.stream_id, learner_ref="P2", committed_amount=300,
           drawn_down_amount=50, funding_band="High Needs Top-Up")
    _alloc(None, learner_ref="P1", committed_amount=10)
    out = F.summary()
    assert out.total_streams == 3
    assert (out.planned, out.active, out.closed) == (1, 1, 1)
    assert out.overcommitted == 1                       # S2: 300 committed > 200
    assert out.total_allocated == 1200.0
    assert out.total_committed == 800.0
    assert out.total_drawn_down == 300.0
    assert out.total_remaining == 400.0
    # S1 25.0 %, S2 25.0 %, S3 skipped (nothing allocated)
    assert out.avg_utilisation_pct == 25.0
    assert out.total_allocations == 3
    assert out.distinct_learners == 2
    assert out.by_stream_type == {"Pupil Premium": 2, "PE and Sport Premium": 1}
    assert out.by_funder == {"ESFA": 2, "DfE": 1}
    assert out.by_stream_status == {"Active": 1, "Planned": 1, "Reconciled": 1}
    assert out.by_band == {"Pupil Premium": 2, "High Needs Top-Up": 1}
    assert out.by_allocation_status == {"Active": 1, "Provisional": 2}

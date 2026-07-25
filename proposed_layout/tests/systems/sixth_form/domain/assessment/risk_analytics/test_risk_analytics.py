"""Tests for the risk-analytics module."""

from __future__ import annotations


def test_band_thresholds():
    from education_system.systems.sixth_form.domain.assessment.risk_analytics import (
        risk_analytics as ra,
    )
    assert ra.band_for(0) == "Low"
    assert ra.band_for(24.9) == "Low"
    assert ra.band_for(25) == "Medium"
    assert ra.band_for(50) == "High"
    assert ra.band_for(75) == "Critical"
    assert ra.band_for(100) == "Critical"


def test_forecast_blends_available_signals():
    from education_system.systems.sixth_form.domain.assessment.risk_analytics import (
        risk_analytics as ra,
    )
    # Mock dominates (50%); all-None returns None.
    assert ra._forecast(None, None, None) is None
    assert ra._forecast("A", None, None) == "A"          # only baseline
    assert ra._forecast("U", "A*", "A*") in ra.GRADE_POINTS  # blend is a valid grade


def test_at_risk_student_scores_higher_than_clean(feature_db):
    ra = feature_db.mods["risk_analytics"]
    a1 = ra.assess_student("S1")
    a2 = ra.assess_student("S2")
    assert a1.score > a2.score
    assert a1.band in ("Medium", "High", "Critical")
    assert a2.band == "Low"
    # S1 should surface multiple factors (attendance + behaviour + grade gap).
    keys = {f.key for f in a1.factors}
    assert "attendance" in keys
    assert "behaviour" in keys
    assert "grade_gap" in keys


def test_predictions_flag_below_target(feature_db):
    ra = feature_db.mods["risk_analytics"]
    a1 = ra.assess_student("S1")
    maths = next(p for p in a1.predictions if p.subject == "Mathematics")
    assert maths.predicted_grade == "D"
    assert maths.target_grade == "B"
    assert maths.on_target is False
    # S2 maths predicted A vs target B → on target.
    a2 = ra.assess_student("S2")
    m2 = next(p for p in a2.predictions if p.subject == "Mathematics")
    assert m2.on_target is True


def test_scan_persists_and_summary(feature_db):
    ra = feature_db.mods["risk_analytics"]
    results = ra.scan_all()
    assert len(results) == 2
    snaps = ra.latest_snapshots()
    assert {s["student_id"] for s in snaps} == {"S1", "S2"}
    # Highest risk first.
    assert snaps[0]["score"] >= snaps[-1]["score"]
    summary = ra.summary()
    assert sum(summary.values()) == 2


def test_unknown_student_raises(feature_db):
    ra = feature_db.mods["risk_analytics"]
    import pytest
    with pytest.raises(ValueError):
        ra.assess_student("NOPE")

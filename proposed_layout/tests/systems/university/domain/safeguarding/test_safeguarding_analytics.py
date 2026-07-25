"""Tests for the safeguarding analytics service (subject linking + reporting)."""

from datetime import datetime, timedelta

import pytest

from education_system.systems.university.domain.safeguarding.db import (
    _connect,
)
from education_system.systems.university.domain.safeguarding.services.analytics import (
    _CUMULATIVE_THRESHOLD,
    canonical_subject_id,
    cumulative_concern,
    find_linked_cases,
    incident_heatmap,
    leadership_stats,
    risk_trend,
)


def _insert(
    *,
    subject_id=None,
    severity="MEDIUM",
    submitted_at=None,
    department=None,
    lifecycle_state="Open",
    status="Pending",
    outcome_code=None,
    reviewed_at=None,
    sla_breached=0,
    mandatory=0,
    purged=0,
):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO safeguarding_submissions "
        "(username, full_name, content, submitted_at, severity, categories, status, "
        " linked_subject_id, case_department, lifecycle_state, outcome_code, "
        " reviewed_at, sla_breached, mandatory_reporting, purged) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "u",
            "Full Name",
            "content",
            submitted_at or datetime.now().isoformat(),
            severity,
            "{}",
            status,
            subject_id,
            department,
            lifecycle_state,
            outcome_code,
            reviewed_at,
            sla_breached,
            mandatory,
            purged,
        ),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


class TestCanonicalSubjectId:
    def test_stable_for_same_username(self):
        a = canonical_subject_id({"username": "alice", "full_name": "Alice"})
        b = canonical_subject_id({"username": "ALICE", "full_name": "Different"})
        assert a == b  # username is lower-cased and takes priority
        assert len(a) == 16

    def test_anonymous_returns_none(self):
        assert canonical_subject_id({"username": "bob"}, anonymous=True) is None

    def test_missing_identity_returns_none(self):
        assert canonical_subject_id({}) is None
        assert canonical_subject_id(None) is None

    def test_falls_back_to_full_name(self):
        assert canonical_subject_id({"full_name": "Carol Jones"}) is not None


class TestFindLinkedCases:
    def test_returns_all_rows_for_subject(self):
        sid = "subject123"
        r1 = _insert(subject_id=sid)
        r2 = _insert(subject_id=sid)
        _insert(subject_id="other")
        found = {row[0] for row in find_linked_cases(sid)}
        assert found == {r1, r2}

    def test_exclude_id_is_dropped(self):
        sid = "subjectX"
        r1 = _insert(subject_id=sid)
        r2 = _insert(subject_id=sid)
        found = {row[0] for row in find_linked_cases(sid, exclude_id=r1)}
        assert found == {r2}

    def test_empty_subject_returns_empty(self):
        assert find_linked_cases(None) == []
        assert find_linked_cases("") == []


class TestCumulativeConcern:
    def test_below_threshold_does_not_escalate(self):
        sid = "cum1"
        _insert(subject_id=sid, severity="LOW")
        count, escalate = cumulative_concern(sid)
        assert count == 1
        assert escalate is False

    def test_reaching_threshold_escalates(self):
        sid = "cum2"
        for _ in range(_CUMULATIVE_THRESHOLD):
            _insert(subject_id=sid, severity="MEDIUM")
        count, escalate = cumulative_concern(sid)
        assert count == _CUMULATIVE_THRESHOLD
        assert escalate is True

    def test_only_counts_recent_window(self):
        sid = "cum3"
        old = (datetime.now() - timedelta(days=90)).isoformat()
        _insert(subject_id=sid, severity="HIGH", submitted_at=old)
        _insert(subject_id=sid, severity="HIGH")
        count, _ = cumulative_concern(sid)
        assert count == 1  # the 90-day-old row is outside the 30-day window

    def test_none_severity_excluded(self):
        sid = "cum4"
        _insert(subject_id=sid, severity="NONE")
        count, escalate = cumulative_concern(sid)
        assert count == 0
        assert escalate is False


class TestIncidentHeatmap:
    def test_groups_by_department_and_severity(self):
        _insert(department="Engineering", severity="HIGH")
        _insert(department="Engineering", severity="HIGH")
        _insert(department="Law", severity="LOW")
        grid = incident_heatmap()
        assert grid["Engineering"]["HIGH"] == 2
        assert grid["Law"]["LOW"] == 1

    def test_missing_department_bucketed_as_unspecified(self):
        _insert(department=None, severity="MEDIUM")
        grid = incident_heatmap()
        assert grid["(unspecified)"]["MEDIUM"] == 1


class TestRiskTrend:
    def test_buckets_by_iso_week(self):
        _insert(severity="HIGH")
        _insert(severity="HIGH")
        trend = risk_trend()
        # Exactly one week bucket, holding both HIGH cases.
        assert len(trend) == 1
        (week,) = trend.keys()
        assert trend[week]["HIGH"] == 2


class TestLeadershipStats:
    def test_aggregates_counts_and_breakdowns(self):
        now = datetime.now()
        _insert(severity="HIGH", sla_breached=1, mandatory=1)
        _insert(
            severity="LOW",
            lifecycle_state="Closed",
            outcome_code="NFA",
            submitted_at=(now - timedelta(days=2)).isoformat(),
            reviewed_at=now.isoformat(),
        )
        stats = leadership_stats(days=90)
        assert stats["total"] == 2
        assert stats["by_severity"]["HIGH"] == 1
        assert stats["by_severity"]["LOW"] == 1
        assert stats["by_lifecycle"]["Closed"] == 1
        assert stats["by_outcome"]["NFA"] == 1
        assert stats["sla_breaches"] == 1
        assert stats["mandatory_flags"] == 1
        # Closed case took ~2 days from submission to review.
        assert stats["avg_days_to_close"] == pytest.approx(2.0, abs=0.2)

    def test_purged_rows_excluded(self):
        _insert(severity="HIGH")
        _insert(severity="HIGH", purged=1)
        assert leadership_stats()["total"] == 1

    def test_empty_period_has_no_average(self):
        stats = leadership_stats(days=90)
        assert stats["total"] == 0
        assert stats["avg_days_to_close"] is None

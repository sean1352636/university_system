"""Tests for the safeguarding risk-scoring service."""

from datetime import datetime, timedelta

import pytest

from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.db import (
    _connect,
)
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.risk import (
    DEFAULT_RISK_MATRIX,
    SLA_HOURS,
    compute_risk_score,
    compute_sla_due,
    refresh_sla_breach_flags,
)


class TestComputeRiskScore:
    def test_matrix_defaults_without_amplifiers(self):
        likelihood, impact, score = compute_risk_score("HIGH", {}, [])
        assert (likelihood, impact) == DEFAULT_RISK_MATRIX["HIGH"]
        assert score == likelihood * impact

    def test_unknown_severity_falls_back_to_none(self):
        assert compute_risk_score("BOGUS", {}, []) == (1, 1, 1)
        assert compute_risk_score(None, {}, []) == (1, 1, 1)

    def test_immediate_danger_triage_amplifies_both(self):
        base_l, base_i, _ = compute_risk_score("MEDIUM", {}, [])
        l, i, _ = compute_risk_score("MEDIUM", {"q3": "yes"}, [])
        assert l == base_l + 1
        assert i == base_i + 1

    def test_nobody_else_knows_amplifies_likelihood_only(self):
        base_l, base_i, _ = compute_risk_score("LOW", {}, [])
        l, i, _ = compute_risk_score("LOW", {"q4": "no"}, [])
        assert l == base_l + 1
        assert i == base_i

    def test_vulnerability_flags_raise_impact_each(self):
        _, base_i, _ = compute_risk_score("LOW", {}, [])
        _, i, _ = compute_risk_score("LOW", {}, ["Minor (<18)", "Disability"])
        assert i == base_i + 2

    def test_values_are_capped_at_five(self):
        l, i, score = compute_risk_score(
            "CRITICAL", {"q3": "yes", "q4": "no"}, ["Disability", "Care-leaver"]
        )
        assert l == 5
        assert i == 5
        assert score == 25


class TestComputeSlaDue:
    def test_returns_deadline_offset_by_configured_hours(self):
        before = datetime.now()
        due = compute_sla_due("HIGH")
        assert due is not None
        delta = due - before
        # ~4h HIGH SLA, with a small tolerance for the clock ticking between
        # `before` and the now() inside compute_sla_due.
        target = timedelta(hours=SLA_HOURS["HIGH"])
        assert abs(delta - target) < timedelta(seconds=5)

    def test_unknown_severity_has_no_sla(self):
        assert compute_sla_due("BOGUS") is None


class TestRefreshSlaBreachFlags:
    def _insert(self, sla_due_at, lifecycle_state="Open", sla_breached=0):
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO safeguarding_submissions "
            "(username, content, submitted_at, severity, categories, status, "
            " sla_due_at, sla_breached, lifecycle_state) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "u",
                "c",
                datetime.now().isoformat(),
                "HIGH",
                "{}",
                "Pending",
                sla_due_at,
                sla_breached,
                lifecycle_state,
            ),
        )
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid

    def _breached(self, rid):
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT sla_breached FROM safeguarding_submissions WHERE id=?", (rid,)
        )
        val = cur.fetchone()[0]
        conn.close()
        return val

    def test_past_due_open_case_is_flagged(self):
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        rid = self._insert(past)
        refresh_sla_breach_flags()
        assert self._breached(rid) == 1

    def test_future_due_case_not_flagged(self):
        future = (datetime.now() + timedelta(hours=5)).isoformat()
        rid = self._insert(future)
        refresh_sla_breach_flags()
        assert self._breached(rid) == 0

    def test_closed_case_is_never_flagged(self):
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        rid = self._insert(past, lifecycle_state="Closed")
        refresh_sla_breach_flags()
        assert self._breached(rid) == 0

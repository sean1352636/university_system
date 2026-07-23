"""Tests for the University Risk Management persistence + scoring.

Covers the pure ``Risk`` dataclass rating bands plus the ``RiskDB``
CRUD/filtering/stats. Bus-publish side effects in ``RiskDB.add`` are
swallowed by a broad except and aren't part of this surface.
"""

from __future__ import annotations

import pytest

from education_system.post_18.university_system.infrastructure.database import db as db_module
from education_system.post_18.university_system.modules.domain.operations.legal.risk_management.university_risk_management import (
    CATEGORIES,
    STATUSES,
    Risk,
    RiskDB,
)


@pytest.fixture
def risk_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "risks_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    return RiskDB()


def _make_risk(title="Phishing attempt", category="IT / Cybersecurity",
               department="IT Services", likelihood=3, impact=4,
               status="Open", owner="ciso", mitigation="Awareness training",
               description="Targeted spearphishing") -> Risk:
    return Risk(
        id=None, title=title, category=category, department=department,
        description=description, likelihood=likelihood, impact=impact,
        status=status, owner=owner, mitigation=mitigation,
        created="", updated="",
    )


class TestRiskRating:
    @pytest.mark.parametrize(
        "likelihood,impact,expected",
        [
            (1, 1, "Low"),       # 1
            (2, 2, "Low"),       # 4
            (2, 3, "Medium"),    # 6
            (3, 3, "Medium"),    # 9
            (3, 4, "High"),      # 12
            (4, 4, "High"),      # 16
            (4, 5, "Critical"),  # 20
            (5, 5, "Critical"),  # 25
        ],
    )
    def test_rating_bands(self, likelihood, impact, expected):
        r = _make_risk(likelihood=likelihood, impact=impact)
        assert r.score == likelihood * impact
        assert r.rating == expected


class TestRiskDBCrud:
    def test_add_returns_id_and_fetch_round_trips(self, risk_db):
        rid = risk_db.add(_make_risk())
        assert isinstance(rid, int) and rid > 0
        fetched = risk_db.fetch(rid)
        assert fetched is not None
        assert fetched.id == rid
        assert fetched.title == "Phishing attempt"
        assert fetched.created and fetched.updated

    def test_fetch_unknown_returns_none(self, risk_db):
        assert risk_db.fetch(999999) is None

    def test_update_persists_changes(self, risk_db):
        rid = risk_db.add(_make_risk())
        original = risk_db.fetch(rid)
        updated = Risk(
            id=rid, title="Phishing attempt (Q2)", category=original.category,
            department=original.department, description="Updated description",
            likelihood=4, impact=5, status="In Progress",
            owner=original.owner, mitigation="MFA rollout",
            created=original.created, updated=original.updated,
        )
        risk_db.update(updated)
        after = risk_db.fetch(rid)
        assert after.title == "Phishing attempt (Q2)"
        assert after.status == "In Progress"
        assert after.score == 20 and after.rating == "Critical"

    def test_delete_removes_row(self, risk_db):
        rid = risk_db.add(_make_risk())
        risk_db.delete(rid)
        assert risk_db.fetch(rid) is None


class TestRiskDBFetchAll:
    def _seed_three(self, risk_db):
        # mix of scores + categories for filter/sort coverage
        risk_db.add(_make_risk(title="Phish", category="IT / Cybersecurity",
                               likelihood=3, impact=4, status="Open"))
        risk_db.add(_make_risk(title="Budget overrun", category="Financial",
                               likelihood=2, impact=2, status="Mitigated"))
        risk_db.add(_make_risk(title="Lab fire risk", category="Health & Safety",
                               likelihood=5, impact=5, status="Open",
                               description="Chemistry block"))

    def test_default_ordering_is_score_desc(self, risk_db):
        self._seed_three(risk_db)
        rows = risk_db.fetch_all()
        scores = [r.score for r in rows]
        assert scores == sorted(scores, reverse=True)
        assert rows[0].title == "Lab fire risk"

    def test_filter_by_category(self, risk_db):
        self._seed_three(risk_db)
        rows = risk_db.fetch_all(category="Financial")
        assert {r.title for r in rows} == {"Budget overrun"}

    def test_filter_by_status(self, risk_db):
        self._seed_three(risk_db)
        rows = risk_db.fetch_all(status="Open")
        assert {r.title for r in rows} == {"Phish", "Lab fire risk"}

    def test_search_matches_title_description_or_owner(self, risk_db):
        self._seed_three(risk_db)
        # description-only hit
        rows = risk_db.fetch_all(search="Chemistry")
        assert {r.title for r in rows} == {"Lab fire risk"}
        # title-only hit
        rows = risk_db.fetch_all(search="Budget")
        assert {r.title for r in rows} == {"Budget overrun"}


class TestRiskDBStats:
    def test_stats_buckets_by_rating_status_category(self, risk_db):
        risk_db.add(_make_risk(title="A", category="Financial",
                               likelihood=1, impact=1, status="Open"))         # Low
        risk_db.add(_make_risk(title="B", category="Financial",
                               likelihood=2, impact=3, status="Open"))         # Medium
        risk_db.add(_make_risk(title="C", category="IT / Cybersecurity",
                               likelihood=3, impact=4, status="In Progress"))  # High
        risk_db.add(_make_risk(title="D", category="IT / Cybersecurity",
                               likelihood=5, impact=5, status="Closed"))       # Critical

        s = risk_db.stats()
        assert s["total"] == 4
        assert s["by_rating"] == {"Critical": 1, "High": 1, "Medium": 1, "Low": 1}
        assert s["by_status"]["Open"] == 2
        assert s["by_status"]["In Progress"] == 1
        assert s["by_status"]["Closed"] == 1
        assert s["by_category"]["Financial"] == 2
        assert s["by_category"]["IT / Cybersecurity"] == 2

    def test_stats_empty_db(self, risk_db):
        s = risk_db.stats()
        assert s["total"] == 0
        assert all(v == 0 for v in s["by_rating"].values())
        assert all(v == 0 for v in s["by_status"].values())
        # All canonical categories/statuses are preinitialised to 0
        for cat in CATEGORIES:
            assert s["by_category"][cat] == 0
        for st in STATUSES:
            assert s["by_status"][st] == 0

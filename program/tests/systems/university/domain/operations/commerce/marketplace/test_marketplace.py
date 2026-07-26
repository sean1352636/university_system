"""Tests for the Student Marketplace service.

Each test gets an isolated SQLite file. ``MarketplaceService.__init__``
runs CREATE TABLE IF NOT EXISTS for all marketplace tables, so the
fixture only needs to swap the DB path.
"""

from __future__ import annotations

import pytest

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.domain.operations.commerce.marketplace.services.marketplace_service import (
    MarketplaceService,
)


@pytest.fixture
def marketplace(tmp_path, monkeypatch):
    db_path = str(tmp_path / "marketplace_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    return MarketplaceService()


def _create_listing(svc, **overrides) -> int:
    defaults = dict(
        seller_id="S12345",
        listing_type="For Sale",
        title="Used Calculus Textbook",
        description="Excellent condition, MATH 101.",
        category="Textbooks",
        price=45.00,
        condition_status="Good",
        location="Main Campus",
    )
    defaults.update(overrides)
    return svc.create_listing(**defaults)


class TestCreateListing:
    def test_returns_positive_id(self, marketplace):
        lid = _create_listing(marketplace)
        assert isinstance(lid, int) and lid > 0

    def test_persists_fields(self, marketplace):
        lid = _create_listing(marketplace, title="Stand Desk", category="Furniture", price=120.0)
        listing = marketplace.get_listing(lid, increment_views=False)
        assert listing is not None
        assert listing["title"] == "Stand Desk"
        assert listing["category"] == "Furniture"
        assert listing["price"] == pytest.approx(120.0)
        assert listing["status"] == "Active"


class TestGetListing:
    def test_unknown_listing_returns_none(self, marketplace):
        assert marketplace.get_listing(999999, increment_views=False) is None

    def test_increment_views_default_true_bumps_counter(self, marketplace):
        lid = _create_listing(marketplace)
        first = marketplace.get_listing(lid)
        second = marketplace.get_listing(lid)
        assert second["view_count"] == first["view_count"] + 1

    def test_increment_views_false_leaves_counter(self, marketplace):
        lid = _create_listing(marketplace)
        before = marketplace.get_listing(lid, increment_views=False)
        after = marketplace.get_listing(lid, increment_views=False)
        assert before["view_count"] == after["view_count"]


class TestSearchListings:
    def test_search_by_term_in_title(self, marketplace):
        _create_listing(marketplace, title="Calculus textbook")
        _create_listing(marketplace, title="Chemistry lab kit", category="Equipment")
        rows = marketplace.search_listings(search_term="calculus")
        assert {r["title"] for r in rows} == {"Calculus textbook"}

    def test_filter_by_category(self, marketplace):
        _create_listing(marketplace, title="A", category="Textbooks")
        _create_listing(marketplace, title="B", category="Furniture")
        rows = marketplace.search_listings(category="Furniture")
        assert {r["title"] for r in rows} == {"B"}

    def test_empty_when_no_match(self, marketplace):
        _create_listing(marketplace, title="A", category="Textbooks")
        assert marketplace.search_listings(category="Vehicles") == []


class TestCategoriesAndStats:
    def test_get_categories_returns_non_empty_list(self, marketplace):
        cats = marketplace.get_categories()
        assert isinstance(cats, list)
        assert len(cats) > 0
        assert all(isinstance(c, str) for c in cats)

    def test_get_statistics_returns_mapping(self, marketplace):
        _create_listing(marketplace)
        _create_listing(marketplace, title="Other", category="Furniture", price=200.0)
        stats = marketplace.get_statistics()
        assert isinstance(stats, dict)
        # The service computes counts; at minimum, totals should be a non-negative number.
        for key, val in stats.items():
            if isinstance(val, (int, float)):
                assert val >= 0

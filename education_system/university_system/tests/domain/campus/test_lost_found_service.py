"""Tests for the campus Lost & Found service.

The ``LostFoundService`` creates its own tables in its constructor via
``transaction()``/``get_connection()``, both of which resolve the database file
from ``db_module.DEFAULT_DB_PATH`` at call time. We therefore isolate each test
by monkeypatching ``DEFAULT_DB_PATH`` to a per-test SQLite file (mirroring the
``campus_events_db`` fixture style) and redirecting ``paths.UPLOAD_DIR`` to
``tmp_path`` so photo writes stay inside the sandbox.

The service's ``report_lost_item``/``report_found_item`` will auto-insert a bare
``students`` row when the reporter/finder is unknown, but the real ``students``
schema marks ``first_name``/``last_name``/``course`` NOT NULL, so that
auto-insert path raises. We instead seed full student rows up front so the
existence check short-circuits and the service uses real, valid reporters.
"""

from __future__ import annotations

import pytest

from education_system.university_system.core import paths
from education_system.university_system.infrastructure.database import db as db_module
from education_system.university_system.infrastructure.database.schemas.core_schemas import (
    init_grade_system_db,
)
from education_system.university_system.modules.domain.campus.lost_found.services.lost_found_service import (
    LostFoundService,
)


def _seed_student(student_id: str) -> None:
    """Insert a fully-populated students row so FK/NOT NULL constraints hold."""
    from education_system.university_system.infrastructure.database.db import transaction

    with transaction() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO students
            (student_id, first_name, last_name, course, status)
            VALUES (?, ?, ?, ?, 'Active')
            """,
            (student_id, "First", "Last", "BSc Testing"),
        )


@pytest.fixture
def service(tmp_path, monkeypatch):
    db_path = str(tmp_path / "lost_found_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    # Keep photo writes inside the sandbox.
    monkeypatch.setattr(paths, "UPLOAD_DIR", str(tmp_path / "uploads"))

    # Create the students table (and its siblings) the service FK-references.
    init_grade_system_db()
    # Seed the reporters/finders used across the suite.
    for sid in ("S1", "S2", "S3", "claimant1", "reviewer1"):
        _seed_student(sid)

    svc = LostFoundService()
    yield svc


def _report_lost(svc: LostFoundService, **overrides) -> int:
    defaults = dict(
        reporter_id="S1",
        item_name="Blue Backpack",
        category="Bags",
        description="A blue Jansport backpack with a laptop inside",
        lost_date="2026-05-20",
        lost_location="Library Level 2",
        color="Blue",
        brand="Jansport",
    )
    defaults.update(overrides)
    return svc.report_lost_item(**defaults)


def _report_found(svc: LostFoundService, **overrides) -> int:
    defaults = dict(
        finder_id="S2",
        item_name="Blue Backpack",
        category="Bags",
        description="Found a blue backpack near the library",
        found_date="2026-05-21",
        found_location="Library Foyer",
        color="Blue",
        brand="Jansport",
    )
    defaults.update(overrides)
    return svc.report_found_item(**defaults)


class TestLostItems:
    def test_report_lost_item_returns_id_and_persists(self, service):
        item_id = _report_lost(service)
        assert isinstance(item_id, int) and item_id > 0

        item = service.get_lost_item(item_id)
        assert item is not None
        assert item["item_name"] == "Blue Backpack"
        assert item["category"] == "Bags"
        assert item["reporter_id"] == "S1"
        assert item["status"] == "Active"
        # get_lost_item always attaches a (possibly empty) photos list.
        assert item["photos"] == []

    def test_get_lost_item_missing_returns_none(self, service):
        assert service.get_lost_item(999999) is None

    def test_get_lost_items_filters_by_reporter_and_category(self, service):
        _report_lost(service, reporter_id="S1", category="Bags", item_name="Bag A")
        _report_lost(service, reporter_id="S1", category="Electronics", item_name="Phone")
        _report_lost(service, reporter_id="S3", category="Bags", item_name="Bag B")

        s1_bags = service.get_lost_items(reporter_id="S1", category="Bags")
        names = {i["item_name"] for i in s1_bags}
        assert names == {"Bag A"}

        all_active = service.get_lost_items()
        assert len(all_active) == 3

    def test_update_lost_item_status(self, service):
        item_id = _report_lost(service)
        assert service.update_lost_item_status(item_id, "Found", notes="reunited") is True
        assert service.get_lost_item(item_id)["status"] == "Found"
        # The 'Active' default filter should now exclude it.
        assert service.get_lost_items(status="Active") == []

    def test_update_lost_item_invalid_status_raises(self, service):
        item_id = _report_lost(service)
        with pytest.raises(ValueError):
            service.update_lost_item_status(item_id, "Bogus")


class TestFoundItems:
    def test_report_found_item_returns_id_and_persists(self, service):
        item_id = _report_found(service)
        assert isinstance(item_id, int) and item_id > 0

        item = service.get_found_item(item_id)
        assert item is not None
        assert item["finder_id"] == "S2"
        assert item["status"] == "Available"
        assert item["photos"] == []
        assert item["verification_questions"] == []

    def test_update_found_item_invalid_status_raises(self, service):
        item_id = _report_found(service)
        with pytest.raises(ValueError):
            service.update_found_item_status(item_id, "NotAStatus")

    def test_update_found_item_status(self, service):
        item_id = _report_found(service)
        assert service.update_found_item_status(item_id, "Donated") is True
        assert service.get_found_item(item_id)["status"] == "Donated"


class TestMatching:
    def test_found_item_auto_matches_existing_lost_item(self, service):
        # Report the lost item first; then a strongly-similar found item.
        lost_id = _report_lost(service)
        found_id = _report_found(service)

        # The found-side report triggers automatic matching against active lost items.
        matches = service.get_matches("lost", lost_id)
        assert len(matches) == 1
        match = matches[0]
        assert match["found_item_id"] == found_id
        # Same name + color + brand + nearby location/date -> well above threshold.
        assert match["match_score"] >= 50

        # And the same match is visible from the found item's perspective.
        found_matches = service.get_matches("found", found_id)
        assert len(found_matches) == 1
        assert found_matches[0]["lost_item_id"] == lost_id

    def test_no_match_across_different_categories(self, service):
        _report_lost(service, category="Electronics", item_name="Laptop")
        found_id = _report_found(service, category="Bags", item_name="Laptop")
        # Category is a hard gate in scoring, so no cross-category match is stored.
        assert service.get_matches("found", found_id) == []

    def test_calculate_match_score_rewards_attributes(self, service):
        lost = dict(
            category="Bags", item_name="Blue Backpack", color="Blue", brand="Jansport",
            lost_location="Library", lost_date="2026-05-20",
        )
        found = dict(
            category="Bags", item_name="Backpack", color="Blue", brand="Jansport",
            found_location="Library Foyer", found_date="2026-05-21",
        )
        score, reasons = service._calculate_match_score(lost, found)
        # name(30) + color(20) + brand(20) + location(15) + date within 3 days(15)
        assert score == pytest.approx(100.0)
        assert reasons

    def test_calculate_match_score_zero_for_different_category(self, service):
        lost = dict(
            category="Bags", item_name="X", color="", brand="",
            lost_location="A", lost_date="2026-05-20",
        )
        found = dict(
            category="Electronics", item_name="X", color="", brand="",
            found_location="A", found_date="2026-05-20",
        )
        score, reasons = service._calculate_match_score(lost, found)
        assert score == 0.0
        assert reasons == []


class TestSearch:
    def test_search_items_matches_description_and_brand(self, service):
        _report_found(service, item_name="Backpack", brand="Jansport", description="blue bag")
        _report_found(service, item_name="Umbrella", category="Accessories",
                      brand="Acme", description="black umbrella")

        by_brand = service.search_items("found", "Jansport")
        assert len(by_brand) == 1
        assert by_brand[0]["item_name"] == "Backpack"

        by_term = service.search_items("found", "umbrella")
        assert len(by_term) == 1
        assert by_term[0]["item_name"] == "Umbrella"

    def test_search_items_filters_by_category(self, service):
        _report_found(service, item_name="Phone", category="Electronics", description="phone")
        _report_found(service, item_name="Phone case", category="Accessories", description="phone case")

        results = service.search_items("found", "phone", category="Electronics")
        assert len(results) == 1
        assert results[0]["category"] == "Electronics"


class TestClaimsAndVerification:
    def test_verification_questions_and_claim_flow(self, service):
        found_id = _report_found(service)
        q_ids = service.create_verification_questions(
            found_id, created_by="S2",
            questions=["What is inside?", "What brand is it?"],
        )
        assert len(q_ids) == 2

        # Questions surface on the found item read.
        item = service.get_found_item(found_id)
        assert len(item["verification_questions"]) == 2

        claim_id = service.submit_claim(
            found_id, claimant_id="claimant1",
            claim_description="It is mine, contains my laptop",
            verification_answers={q_ids[0]: "A laptop", q_ids[1]: "Jansport"},
        )
        assert isinstance(claim_id, int) and claim_id > 0

        pending = service.get_claims(found_item_id=found_id, status="Pending")
        assert len(pending) == 1
        assert pending[0]["claimant_id"] == "claimant1"

    def test_approve_claim_marks_found_item_claimed(self, service):
        found_id = _report_found(service)
        claim_id = service.submit_claim(
            found_id, claimant_id="claimant1", claim_description="mine",
        )
        assert service.review_claim(claim_id, reviewer_id="reviewer1", approved=True) is True

        approved = service.get_claims(status="Approved")
        assert len(approved) == 1
        assert approved[0]["claim_id"] == claim_id
        # Approving a claim flips the found item to 'Claimed'.
        assert service.get_found_item(found_id)["status"] == "Claimed"

    def test_reject_claim_leaves_item_available(self, service):
        found_id = _report_found(service)
        claim_id = service.submit_claim(
            found_id, claimant_id="claimant1", claim_description="maybe mine",
        )
        assert service.review_claim(claim_id, reviewer_id="reviewer1", approved=False) is True
        assert service.get_found_item(found_id)["status"] == "Available"
        rejected = service.get_claims(status="Rejected")
        assert len(rejected) == 1


class TestPhotos:
    def test_add_and_get_item_photo(self, service):
        lost_id = _report_lost(service)
        photo_id = service.add_item_photo("lost", lost_id, b"fake-jpeg-bytes", caption="front")
        assert isinstance(photo_id, int) and photo_id > 0

        photos = service.get_item_photos("lost", lost_id)
        assert len(photos) == 1
        assert photos[0]["caption"] == "front"
        # get_lost_item should now report the attached photo.
        assert len(service.get_lost_item(lost_id)["photos"]) == 1

    def test_add_item_photo_invalid_type_raises(self, service):
        lost_id = _report_lost(service)
        with pytest.raises(ValueError):
            service.add_item_photo("sideways", lost_id, b"bytes")

    def test_delete_item_photo(self, service):
        lost_id = _report_lost(service)
        photo_id = service.add_item_photo("lost", lost_id, b"bytes")
        assert service.delete_item_photo(photo_id) is True
        assert service.get_item_photos("lost", lost_id) == []
        # Deleting a non-existent photo returns False.
        assert service.delete_item_photo(photo_id) is False


class TestAnalytics:
    def test_statistics_counts(self, service):
        lost_id = _report_lost(service)
        _report_found(service)
        service.update_lost_item_status(lost_id, "Found")

        stats = service.get_statistics()
        assert stats["lost_items"]["total"] == 1
        assert stats["lost_items"]["found"] == 1
        assert stats["found_items"]["total"] == 1
        assert stats["found_items"]["available"] == 1

    def test_category_breakdown(self, service):
        _report_lost(service, category="Bags")
        _report_lost(service, category="Electronics")
        _report_found(service, category="Bags")

        breakdown = service.get_category_breakdown()
        lost_categories = {row["category"]: row["count"] for row in breakdown["lost"]}
        found_categories = {row["category"]: row["count"] for row in breakdown["found"]}
        assert lost_categories == {"Bags": 1, "Electronics": 1}
        assert found_categories == {"Bags": 1}

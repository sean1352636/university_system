"""
Tests for university_system/api/pagination.py

Covers get_pagination_params() query-string extraction and validation,
and paginated_response() metadata wrapper.
"""

import math
import os
import sys

import pytest
from flask import Flask

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from education_system.university_system.api.pagination import get_pagination_params, paginated_response


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def app():
    """Minimal Flask app for request-context tests."""
    application = Flask(__name__)
    application.config["TESTING"] = True
    return application


# ============================================================================
# get_pagination_params – default behaviour
# ============================================================================


class TestGetPaginationParamsDefaults:
    """Tests for get_pagination_params with default / no query params."""

    def test_default_page_is_1(self, app):
        """With no query params, page defaults to 1."""
        with app.test_request_context("/"):
            page, per_page, offset = get_pagination_params()
            assert page == 1

    def test_default_per_page_is_20(self, app):
        """With no query params, per_page defaults to 20."""
        with app.test_request_context("/"):
            page, per_page, offset = get_pagination_params()
            assert per_page == 20

    def test_default_offset_is_0(self, app):
        """With no query params, offset is 0."""
        with app.test_request_context("/"):
            page, per_page, offset = get_pagination_params()
            assert offset == 0


class TestGetPaginationParamsCustomDefaults:
    """Tests for custom default_page, default_per_page, max_per_page."""

    def test_custom_default_page(self, app):
        """Custom default_page is used when no query param."""
        with app.test_request_context("/"):
            page, _, _ = get_pagination_params(default_page=3)
            assert page == 3

    def test_custom_default_per_page(self, app):
        """Custom default_per_page is used when no query param."""
        with app.test_request_context("/"):
            _, per_page, _ = get_pagination_params(default_per_page=50)
            assert per_page == 50

    def test_custom_max_per_page_caps_value(self, app):
        """per_page from query string is capped at max_per_page."""
        with app.test_request_context("/?per_page=200"):
            _, per_page, _ = get_pagination_params(max_per_page=50)
            assert per_page == 50


# ============================================================================
# get_pagination_params – query string values
# ============================================================================


class TestGetPaginationParamsFromQuery:
    """Tests for extracting page/per_page from request.args."""

    def test_page_from_query(self, app):
        """Page is read from query string."""
        with app.test_request_context("/?page=5"):
            page, _, _ = get_pagination_params()
            assert page == 5

    def test_per_page_from_query(self, app):
        """per_page is read from query string."""
        with app.test_request_context("/?per_page=30"):
            _, per_page, _ = get_pagination_params()
            assert per_page == 30

    def test_both_from_query(self, app):
        """Both page and per_page from query string."""
        with app.test_request_context("/?page=3&per_page=10"):
            page, per_page, offset = get_pagination_params()
            assert page == 3
            assert per_page == 10
            assert offset == 20  # (3-1) * 10

    def test_per_page_capped_at_default_max(self, app):
        """per_page is capped at max_per_page=100 by default."""
        with app.test_request_context("/?per_page=500"):
            _, per_page, _ = get_pagination_params()
            assert per_page == 100


# ============================================================================
# get_pagination_params – offset calculation
# ============================================================================


class TestGetPaginationParamsOffset:
    """Tests for correct offset calculation."""

    def test_offset_page_1(self, app):
        """Offset for page 1 is always 0."""
        with app.test_request_context("/?page=1&per_page=25"):
            _, _, offset = get_pagination_params()
            assert offset == 0

    def test_offset_page_2(self, app):
        """Offset for page 2 with per_page=25 is 25."""
        with app.test_request_context("/?page=2&per_page=25"):
            _, _, offset = get_pagination_params()
            assert offset == 25

    def test_offset_page_10(self, app):
        """Offset for page 10 with per_page=20 is 180."""
        with app.test_request_context("/?page=10&per_page=20"):
            _, _, offset = get_pagination_params()
            assert offset == 180

    def test_offset_formula(self, app):
        """Offset is always (page - 1) * per_page."""
        with app.test_request_context("/?page=7&per_page=15"):
            page, per_page, offset = get_pagination_params()
            assert offset == (page - 1) * per_page


# ============================================================================
# get_pagination_params – invalid / edge-case values
# ============================================================================


class TestGetPaginationParamsInvalid:
    """Tests for invalid query-string values (strings, negatives, etc.)."""

    def test_non_numeric_page_falls_back_to_default(self, app):
        """Non-numeric page falls back to default_page."""
        with app.test_request_context("/?page=abc"):
            page, _, _ = get_pagination_params()
            assert page == 1

    def test_non_numeric_per_page_falls_back_to_default(self, app):
        """Non-numeric per_page falls back to default_per_page."""
        with app.test_request_context("/?per_page=xyz"):
            _, per_page, _ = get_pagination_params()
            assert per_page == 20

    def test_negative_page_clamped_to_1(self, app):
        """Negative page is clamped to 1 via max(1, ...)."""
        with app.test_request_context("/?page=-5"):
            page, _, _ = get_pagination_params()
            assert page == 1

    def test_zero_page_clamped_to_1(self, app):
        """page=0 is clamped to 1."""
        with app.test_request_context("/?page=0"):
            page, _, _ = get_pagination_params()
            assert page == 1

    def test_negative_per_page_clamped_to_1(self, app):
        """Negative per_page is clamped to 1 via max(1, ...)."""
        with app.test_request_context("/?per_page=-10"):
            _, per_page, _ = get_pagination_params()
            assert per_page == 1

    def test_zero_per_page_clamped_to_1(self, app):
        """per_page=0 is clamped to 1."""
        with app.test_request_context("/?per_page=0"):
            _, per_page, _ = get_pagination_params()
            assert per_page == 1

    def test_float_page_truncated(self, app):
        """Float page like '2.7' is converted to int (2)."""
        with app.test_request_context("/?page=2.7"):
            # int("2.7") raises ValueError, so falls back to default
            page, _, _ = get_pagination_params()
            assert page == 1

    def test_empty_string_page_falls_back(self, app):
        """Empty string page falls back to default."""
        with app.test_request_context("/?page="):
            page, _, _ = get_pagination_params()
            assert page == 1

    def test_empty_string_per_page_falls_back(self, app):
        """Empty string per_page falls back to default."""
        with app.test_request_context("/?per_page="):
            _, per_page, _ = get_pagination_params()
            assert per_page == 20


# ============================================================================
# paginated_response tests
# ============================================================================


class TestPaginatedResponseBasic:
    """Tests for paginated_response() metadata generation."""

    def test_contains_items(self):
        """Response includes the items list."""
        items = [{"id": 1}, {"id": 2}]
        result = paginated_response(items, total=10, page=1, per_page=5)
        assert result["items"] == items

    def test_contains_pagination_key(self):
        """Response includes a 'pagination' dict."""
        result = paginated_response([], total=0, page=1, per_page=20)
        assert "pagination" in result
        assert isinstance(result["pagination"], dict)

    def test_pagination_page(self):
        """Pagination metadata includes current page."""
        result = paginated_response([], total=50, page=3, per_page=10)
        assert result["pagination"]["page"] == 3

    def test_pagination_per_page(self):
        """Pagination metadata includes per_page."""
        result = paginated_response([], total=50, page=1, per_page=15)
        assert result["pagination"]["per_page"] == 15

    def test_pagination_total(self):
        """Pagination metadata includes total count."""
        result = paginated_response([], total=42, page=1, per_page=20)
        assert result["pagination"]["total"] == 42


class TestPaginatedResponseTotalPages:
    """Tests for total_pages calculation."""

    def test_exact_division(self):
        """total_pages when total divides evenly by per_page."""
        result = paginated_response([], total=100, page=1, per_page=20)
        assert result["pagination"]["total_pages"] == 5

    def test_remainder_rounds_up(self):
        """total_pages rounds up when there is a remainder."""
        result = paginated_response([], total=101, page=1, per_page=20)
        assert result["pagination"]["total_pages"] == 6

    def test_total_zero_gives_1_page(self):
        """total=0 still yields total_pages=1 (at least one page)."""
        result = paginated_response([], total=0, page=1, per_page=20)
        assert result["pagination"]["total_pages"] == 1

    def test_single_item(self):
        """total=1 yields total_pages=1."""
        result = paginated_response([{"id": 1}], total=1, page=1, per_page=20)
        assert result["pagination"]["total_pages"] == 1

    def test_total_equals_per_page(self):
        """When total == per_page, there is exactly 1 page."""
        result = paginated_response([], total=20, page=1, per_page=20)
        assert result["pagination"]["total_pages"] == 1

    def test_total_pages_formula(self):
        """total_pages matches ceil(total / per_page), minimum 1."""
        for total in [0, 1, 19, 20, 21, 99, 100, 101]:
            result = paginated_response([], total=total, page=1, per_page=20)
            expected = max(1, math.ceil(total / 20))
            assert result["pagination"]["total_pages"] == expected


class TestPaginatedResponseHasNext:
    """Tests for has_next flag."""

    def test_has_next_true_on_first_page(self):
        """has_next is True when on page 1 of multiple pages."""
        result = paginated_response([], total=50, page=1, per_page=20)
        assert result["pagination"]["has_next"] is True

    def test_has_next_false_on_last_page(self):
        """has_next is False when on the last page."""
        result = paginated_response([], total=50, page=3, per_page=20)
        assert result["pagination"]["has_next"] is False

    def test_has_next_false_single_page(self):
        """has_next is False when there is only one page."""
        result = paginated_response([], total=5, page=1, per_page=20)
        assert result["pagination"]["has_next"] is False

    def test_has_next_true_middle_page(self):
        """has_next is True on a middle page."""
        result = paginated_response([], total=100, page=2, per_page=20)
        assert result["pagination"]["has_next"] is True


class TestPaginatedResponseHasPrev:
    """Tests for has_prev flag."""

    def test_has_prev_false_on_first_page(self):
        """has_prev is False on page 1."""
        result = paginated_response([], total=50, page=1, per_page=20)
        assert result["pagination"]["has_prev"] is False

    def test_has_prev_true_on_page_2(self):
        """has_prev is True on page 2."""
        result = paginated_response([], total=50, page=2, per_page=20)
        assert result["pagination"]["has_prev"] is True

    def test_has_prev_true_on_last_page(self):
        """has_prev is True on the last page of multiple pages."""
        result = paginated_response([], total=50, page=3, per_page=20)
        assert result["pagination"]["has_prev"] is True

    def test_has_prev_false_single_page(self):
        """has_prev is False when there is only one page."""
        result = paginated_response([], total=5, page=1, per_page=20)
        assert result["pagination"]["has_prev"] is False


class TestPaginatedResponseEdgeCases:
    """Edge case tests for paginated_response."""

    def test_empty_items_list(self):
        """Empty items list is returned as-is."""
        result = paginated_response([], total=0, page=1, per_page=20)
        assert result["items"] == []

    def test_items_not_mutated(self):
        """The original items list is not modified."""
        items = [{"id": 1}, {"id": 2}]
        original = items.copy()
        paginated_response(items, total=2, page=1, per_page=20)
        assert items == original

    def test_large_total(self):
        """Works correctly with a large total."""
        result = paginated_response([], total=1_000_000, page=1, per_page=100)
        assert result["pagination"]["total_pages"] == 10_000
        assert result["pagination"]["has_next"] is True

    def test_all_pagination_keys_present(self):
        """All expected pagination keys are present."""
        result = paginated_response([], total=50, page=1, per_page=20)
        expected_keys = {"page", "per_page", "total", "total_pages", "has_next", "has_prev"}
        assert set(result["pagination"].keys()) == expected_keys


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

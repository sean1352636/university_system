"""Tests for the Campus Navigation Service.

The ``NavigationService`` creates its own schema (campus_buildings,
points_of_interest, campus_routes, navigation_history,
navigation_favorites) and seeds sample buildings/POIs in its
constructor via ``_ensure_tables_exist``. Each test gets an isolated
SQLite file by monkeypatching ``DEFAULT_DB_PATH`` and instantiating a
fresh service through the ``nav_service`` fixture.
"""

from __future__ import annotations

import math

import pytest

from education_system.university_system.infrastructure.database import db as db_module
from education_system.university_system.modules.domain.campus.campus_navigation.services.navigation_service import (
    NavigationService,
)


@pytest.fixture
def nav_service(tmp_path, monkeypatch):
    db_path = str(tmp_path / "campus_navigation_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    # Constructing the service builds the schema and seeds sample data
    # against the isolated db.
    service = NavigationService()
    yield service


class TestBuildingQueries:
    def test_get_all_buildings_returns_seeded_set(self, nav_service):
        buildings = nav_service.get_all_buildings()
        # Sample data seeds 10 buildings.
        assert len(buildings) == 10
        codes = {b["building_code"] for b in buildings}
        assert {"MAIN", "LIB", "SCI", "GYM", "UNION"}.issubset(codes)
        # Ordered by building_name ascending.
        names = [b["building_name"] for b in buildings]
        assert names == sorted(names)

    def test_get_all_buildings_filtered_by_type(self, nav_service):
        academic = nav_service.get_all_buildings(building_type="Academic")
        assert academic, "expected at least one Academic building"
        assert all(b["building_type"] == "Academic" for b in academic)
        # LIB, SCI, ENG, ART are seeded as Academic.
        codes = {b["building_code"] for b in academic}
        assert {"LIB", "SCI", "ENG", "ART"}.issubset(codes)

    def test_get_building_by_id_and_code_match(self, nav_service):
        by_code = nav_service.get_building(building_code="LIB")
        assert by_code is not None
        assert by_code["building_name"] == "University Library"

        by_id = nav_service.get_building(building_id=by_code["building_id"])
        assert by_id is not None
        assert by_id["building_code"] == "LIB"

    def test_get_building_with_no_args_returns_none(self, nav_service):
        assert nav_service.get_building() is None

    def test_get_building_unknown_code_returns_none(self, nav_service):
        assert nav_service.get_building(building_code="DOES_NOT_EXIST") is None

    def test_search_buildings_matches_name_and_type(self, nav_service):
        # Matches building_name "University Library".
        results = nav_service.search_buildings("Library")
        assert any(b["building_code"] == "LIB" for b in results)

        # Matches building_type "Housing".
        housing = nav_service.search_buildings("Housing")
        codes = {b["building_code"] for b in housing}
        assert {"DORM1", "DORM2"}.issubset(codes)


class TestPointsOfInterest:
    def test_get_pois_filtered_by_building(self, nav_service):
        lib = nav_service.get_building(building_code="LIB")
        pois = nav_service.get_points_of_interest(building_id=lib["building_id"])
        assert pois, "expected seeded POIs for the library"
        assert all(p["building_id"] == lib["building_id"] for p in pois)
        names = {p["poi_name"] for p in pois}
        assert "Reference Desk" in names

    def test_get_pois_filtered_by_type(self, nav_service):
        athletic = nav_service.get_points_of_interest(poi_type="Athletic")
        assert athletic
        assert all(p["poi_type"] == "Athletic" for p in athletic)

    def test_search_points_of_interest_by_name(self, nav_service):
        results = nav_service.search_points_of_interest("Bookstore")
        assert any(p["poi_name"] == "Bookstore" for p in results)
        # The query joins the building, so building_name is included.
        match = next(p for p in results if p["poi_name"] == "Bookstore")
        assert match["building_name"] == "Student Union"

    def test_search_points_of_interest_by_tags(self, nav_service):
        results = nav_service.search_points_of_interest("zzz-no-match", tags=["swimming"])
        names = {p["poi_name"] for p in results}
        assert "Swimming Pool" in names


class TestNearestAndDistance:
    def test_find_nearest_orders_by_distance_and_limits(self, nav_service):
        # Coordinates near the seeded buildings (~40.71, -74.00).
        results = nav_service.find_nearest("Academic", 40.7128, -74.0060, limit=3)
        assert 0 < len(results) <= 3
        distances = [r["distance_meters"] for r in results]
        assert distances == sorted(distances)
        assert all("distance_description" in r for r in results)

    def test_distance_for_same_point_is_zero(self, nav_service):
        d = nav_service._calculate_distance(40.7128, -74.0060, 40.7128, -74.0060)
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_distance_matches_haversine(self, nav_service):
        # Independent Haversine computation for two seeded coordinates.
        lat1, lon1 = 40.7128, -74.0060
        lat2, lon2 = 40.7130, -74.0058
        r = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        expected = r * 2 * math.asin(math.sqrt(a))
        assert nav_service._calculate_distance(lat1, lon1, lat2, lon2) == pytest.approx(expected)

    def test_format_distance_units(self, nav_service):
        assert nav_service._format_distance(250.0) == "250m"
        assert nav_service._format_distance(1500.0) == "1.5km"


class TestRoutePlanning:
    def test_calculate_route_returns_structure_and_persists(self, nav_service):
        main = nav_service.get_building(building_code="MAIN")
        lib = nav_service.get_building(building_code="LIB")

        route = nav_service.calculate_route(main["building_id"], lib["building_id"])
        assert route["start_building"]["building_code"] == "MAIN"
        assert route["end_building"]["building_code"] == "LIB"
        assert route["distance_meters"] > 0
        assert route["estimated_time_minutes"] >= 0
        assert len(route["waypoints"]) == 2
        assert route["directions"], "expected turn-by-turn directions"

        # Route is persisted to campus_routes.
        from education_system.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM campus_routes WHERE start_location_id = ? "
                "AND end_location_id = ?",
                (main["building_id"], lib["building_id"]),
            ).fetchone()[0]
        assert n == 1

    def test_calculate_route_accessible_adds_notes(self, nav_service):
        main = nav_service.get_building(building_code="MAIN")
        lib = nav_service.get_building(building_code="LIB")
        route = nav_service.calculate_route(
            main["building_id"], lib["building_id"], require_accessible=True
        )
        assert route["is_accessible"] is True
        assert route["accessibility_notes"], "accessible route should include notes"

    def test_calculate_route_missing_building_raises(self, nav_service):
        main = nav_service.get_building(building_code="MAIN")
        with pytest.raises(ValueError, match="Building not found"):
            nav_service.calculate_route(main["building_id"], 999999)


class TestNavigationHistoryAndFavorites:
    def test_save_history_and_rate(self, nav_service):
        history_id = nav_service.save_navigation_history(
            user_id="S12345",
            start_location="Main Administration Building",
            end_location="University Library",
            route_taken="direct",
            duration_minutes=5,
        )
        assert isinstance(history_id, int) and history_id > 0

        assert nav_service.rate_navigation(history_id, 4, "smooth walk") is True

        from education_system.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            row = conn.execute(
                "SELECT rating, feedback FROM navigation_history WHERE history_id = ?",
                (history_id,),
            ).fetchone()
        assert row["rating"] == 4
        assert row["feedback"] == "smooth walk"

    def test_rate_navigation_rejects_out_of_range(self, nav_service):
        history_id = nav_service.save_navigation_history(
            user_id="S1",
            start_location="A",
            end_location="B",
            route_taken="x",
            duration_minutes=1,
        )
        with pytest.raises(ValueError, match="between 1 and 5"):
            nav_service.rate_navigation(history_id, 6)

    def test_add_get_and_remove_favorite(self, nav_service):
        lib = nav_service.get_building(building_code="LIB")
        fav_id = nav_service.add_favorite("S12345", "building", lib["building_id"], "My Library")
        assert isinstance(fav_id, int) and fav_id > 0

        favorites = nav_service.get_favorites("S12345")
        assert len(favorites) == 1
        fav = favorites[0]
        assert fav["nickname"] == "My Library"
        assert fav["location_name"] == "University Library"

        assert nav_service.remove_favorite(fav_id) is True
        assert nav_service.get_favorites("S12345") == []


class TestAnalytics:
    def test_get_popular_routes_aggregates_rated_history(self, nav_service):
        for _ in range(3):
            hid = nav_service.save_navigation_history(
                user_id="S1",
                start_location="Main Administration Building",
                end_location="University Library",
                route_taken="direct",
                duration_minutes=5,
            )
            nav_service.rate_navigation(hid, 5)
        # One unrated trip on a different route should be excluded.
        nav_service.save_navigation_history(
            user_id="S2",
            start_location="Science Building",
            end_location="Engineering Hall",
            route_taken="direct",
            duration_minutes=3,
        )

        popular = nav_service.get_popular_routes()
        assert len(popular) == 1
        top = popular[0]
        assert top["start_location"] == "Main Administration Building"
        assert top["end_location"] == "University Library"
        assert top["usage_count"] == 3
        assert top["avg_rating"] == pytest.approx(5.0)

    def test_get_building_stats(self, nav_service):
        lib = nav_service.get_building(building_code="LIB")
        # Navigations ending at the library by building_name.
        for _ in range(2):
            nav_service.save_navigation_history(
                user_id="S1",
                start_location="Main Administration Building",
                end_location="University Library",
                route_taken="direct",
                duration_minutes=4,
            )
        stats = nav_service.get_building_stats(lib["building_id"])
        assert stats["navigation"]["total_navigations"] == 2
        assert stats["navigation"]["avg_visit_duration"] == pytest.approx(4.0)
        # Library has seeded POIs.
        assert stats["points_of_interest"] >= 3

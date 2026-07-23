"""Campus navigation routes: buildings, points of interest, routes, and favorites."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

campus_navigation_bp = Blueprint("campus_navigation", __name__, url_prefix="/api/campus-navigation")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- buildings ----

@campus_navigation_bp.route("/buildings", methods=["GET"])
@token_required
def list_buildings():
    search = request.args.get("search")
    building_type = request.args.get("building_type")
    is_accessible = request.args.get("is_accessible")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM campus_buildings WHERE building_name LIKE ? OR building_code LIKE ? OR address LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if building_type:
            conditions.append("building_type = ?")
            params.append(building_type)
        if is_accessible:
            conditions.append("is_accessible = ?")
            params.append(is_accessible)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM campus_buildings" + where + " ORDER BY building_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM campus_buildings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "campus_buildings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@campus_navigation_bp.route("/buildings/<int:building_id>", methods=["GET"])
@token_required
def get_building(building_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_buildings WHERE building_id = ?", (building_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"buildings {building_id} not found")
    log_activity("view", "campus_buildings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@campus_navigation_bp.route("/buildings", methods=["POST"])
@token_required
def create_building():
    data = request.get_json(silent=True) or {}
    for field in ["building_code", "building_name", "building_type"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO campus_buildings
               (building_code, building_name, building_type, description, latitude, longitude, address, floors, is_accessible, operating_hours, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["building_code"], data["building_name"], data["building_type"], data.get("description", ""), data.get("latitude", ""), data.get("longitude", ""), data.get("address", ""), data.get("floors", ""), data.get("is_accessible", ""), data.get("operating_hours", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_buildings WHERE building_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "campus_buildings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- poi ----

@campus_navigation_bp.route("/poi", methods=["GET"])
@token_required
def list_poi():
    search = request.args.get("search")
    building_id = request.args.get("building_id")
    poi_type = request.args.get("poi_type")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM points_of_interest WHERE poi_name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if building_id:
            conditions.append("building_id = ?")
            params.append(building_id)
        if poi_type:
            conditions.append("poi_type = ?")
            params.append(poi_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM points_of_interest" + where + " ORDER BY poi_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM points_of_interest" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "points_of_interest", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@campus_navigation_bp.route("/poi/<int:poi_id>", methods=["GET"])
@token_required
def get_poi(poi_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM points_of_interest WHERE poi_id = ?", (poi_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"poi {poi_id} not found")
    log_activity("view", "points_of_interest", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@campus_navigation_bp.route("/poi", methods=["POST"])
@token_required
def create_poi():
    data = request.get_json(silent=True) or {}
    for field in ["building_id", "poi_name", "poi_type"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO points_of_interest
               (building_id, poi_name, poi_type, floor_number, room_number, description, is_accessible, operating_hours, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["building_id"], data["poi_name"], data["poi_type"], data.get("floor_number", ""), data.get("room_number", ""), data.get("description", ""), data.get("is_accessible", ""), data.get("operating_hours", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM points_of_interest WHERE poi_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "points_of_interest", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- routes ----

@campus_navigation_bp.route("/routes", methods=["GET"])
@token_required
def list_routes():
    search = request.args.get("search")
    route_type = request.args.get("route_type")
    is_accessible = request.args.get("is_accessible")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM campus_routes WHERE route_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if route_type:
            conditions.append("route_type = ?")
            params.append(route_type)
        if is_accessible:
            conditions.append("is_accessible = ?")
            params.append(is_accessible)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM campus_routes" + where + " ORDER BY route_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM campus_routes" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "campus_routes", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@campus_navigation_bp.route("/routes/<int:route_id>", methods=["GET"])
@token_required
def get_route(route_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_routes WHERE route_id = ?", (route_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"routes {route_id} not found")
    log_activity("view", "campus_routes", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@campus_navigation_bp.route("/routes", methods=["POST"])
@token_required
def create_route():
    data = request.get_json(silent=True) or {}
    for field in ["route_name", "start_location_id", "end_location_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO campus_routes
               (route_name, start_location_id, end_location_id, route_type, is_accessible, distance_meters, estimated_time_minutes, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["route_name"], data["start_location_id"], data["end_location_id"], data.get("route_type", ""), data.get("is_accessible", ""), data.get("distance_meters", ""), data.get("estimated_time_minutes", ""), data.get("description", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_routes WHERE route_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "campus_routes", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- find nearest ----

@campus_navigation_bp.route("/find-nearest", methods=["GET"])
@token_required
def find_nearest():
    location_type = request.args.get("location_type", "")
    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)
    limit = request.args.get("limit", 5, type=int)

    if latitude is None or longitude is None:
        raise ValidationError("latitude and longitude are required")

    import math

    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    def _fmt(m):
        return f"{int(m)}m" if m < 1000 else f"{m / 1000:.1f}km"

    results = []
    with get_connection() as conn:
        pattern = f"%{escape_like(location_type)}%"
        buildings = conn.execute(
            "SELECT *, 'building' AS result_type FROM campus_buildings WHERE building_type LIKE ?",
            (pattern,),
        ).fetchall()
        for b in buildings:
            d = _haversine(latitude, longitude, b["latitude"], b["longitude"])
            item = _row_to_dict(b)
            item["distance_meters"] = round(d, 2)
            item["distance_description"] = _fmt(d)
            results.append(item)

        pois = conn.execute(
            "SELECT p.*, cb.building_name, cb.latitude AS blat, cb.longitude AS blon, 'poi' AS result_type "
            "FROM points_of_interest p LEFT JOIN campus_buildings cb ON p.building_id = cb.building_id "
            "WHERE p.poi_type LIKE ?",
            (pattern,),
        ).fetchall()
        for p in pois:
            plat = p["latitude"] if p["latitude"] is not None else p["blat"]
            plon = p["longitude"] if p["longitude"] is not None else p["blon"]
            if plat is None or plon is None:
                continue
            d = _haversine(latitude, longitude, plat, plon)
            item = _row_to_dict(p)
            item["distance_meters"] = round(d, 2)
            item["distance_description"] = _fmt(d)
            results.append(item)

    results.sort(key=lambda x: x["distance_meters"])
    log_activity("search", "nearest_locations", user=g.current_user.get("sub"))
    return jsonify({"items": results[:limit], "total": len(results[:limit])})


# ---- calculate route ----

@campus_navigation_bp.route("/calculate-route", methods=["POST"])
@token_required
def calculate_route():
    data = request.get_json(silent=True) or {}
    start_id = data.get("start_location_id")
    end_id = data.get("end_location_id")
    require_accessible = data.get("require_accessible", False)

    if not start_id or not end_id:
        raise ValidationError("start_location_id and end_location_id are required")

    import math
    import json as _json

    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    def _fmt(m):
        return f"{int(m)}m" if m < 1000 else f"{m / 1000:.1f}km"

    with get_connection() as conn:
        start = conn.execute("SELECT * FROM campus_buildings WHERE building_id = ?", (start_id,)).fetchone()
        end = conn.execute("SELECT * FROM campus_buildings WHERE building_id = ?", (end_id,)).fetchone()

    if not start or not end:
        raise ValidationError("One or both buildings not found")

    if require_accessible and (not start["is_accessible"] or not end["is_accessible"]):
        raise ValidationError("One or both buildings are not accessible")

    distance = _haversine(start["latitude"], start["longitude"], end["latitude"], end["longitude"])
    time_minutes = int(distance / 1.4 / 60)

    waypoints = [
        {"latitude": start["latitude"], "longitude": start["longitude"], "description": f"Start at {start['building_name']}"},
        {"latitude": end["latitude"], "longitude": end["longitude"], "description": f"Arrive at {end['building_name']}"},
    ]

    with transaction() as conn:
        conn.execute(
            """INSERT INTO campus_routes
               (route_name, start_location_id, end_location_id, is_accessible, distance_meters, estimated_time_minutes, waypoints)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"{start['building_code']} to {end['building_code']}", start_id, end_id,
             require_accessible, distance, time_minutes, _json.dumps(waypoints)),
        )

    route = {
        "start_building": _row_to_dict(start),
        "end_building": _row_to_dict(end),
        "distance_meters": round(distance, 2),
        "distance_description": _fmt(distance),
        "estimated_time_minutes": time_minutes,
        "is_accessible": require_accessible,
        "waypoints": waypoints,
    }

    log_activity("create", "campus_route", user=g.current_user.get("sub"))
    return jsonify(route), 201


# ---- navigation history ----

@campus_navigation_bp.route("/history", methods=["GET"])
@token_required
def list_navigation_history():
    user_id = request.args.get("user_id")
    conditions = []
    params: list = []
    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    page, per_page, offset = get_pagination_params()
    params_count = list(params)
    params.extend([per_page, offset])

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM navigation_history" + where + " ORDER BY history_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM navigation_history" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "navigation_history", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@campus_navigation_bp.route("/history", methods=["POST"])
@token_required
def save_navigation_history():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "start_location", "end_location"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO navigation_history
               (user_id, start_location, end_location, route_taken, duration_minutes, accessibility_required)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["user_id"], data["start_location"], data["end_location"],
             data.get("route_taken", ""), data.get("duration_minutes", 0),
             data.get("accessibility_required", 0)),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM navigation_history WHERE history_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "navigation_history", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@campus_navigation_bp.route("/history/<int:history_id>/rate", methods=["PUT"])
@token_required
def rate_navigation(history_id: int):
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if rating is None or not (1 <= int(rating) <= 5):
        raise ValidationError("rating is required and must be between 1 and 5")

    with transaction() as conn:
        conn.execute(
            "UPDATE navigation_history SET rating = ?, feedback = ? WHERE history_id = ?",
            (int(rating), data.get("feedback", ""), history_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM navigation_history WHERE history_id = ?", (history_id,)
        ).fetchone()

    if not row:
        raise ValidationError(f"navigation history {history_id} not found")

    log_activity("update", "navigation_rating", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- favorites ----

@campus_navigation_bp.route("/favorites", methods=["GET"])
@token_required
def list_favorites():
    user_id = request.args.get("user_id")
    if not user_id:
        raise ValidationError("user_id query parameter is required")

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT nf.*,
                CASE
                    WHEN nf.location_type = 'building' THEN b.building_name
                    WHEN nf.location_type = 'poi' THEN p.poi_name
                END AS location_name
            FROM navigation_favorites nf
            LEFT JOIN campus_buildings b ON nf.location_type = 'building' AND nf.location_id = b.building_id
            LEFT JOIN points_of_interest p ON nf.location_type = 'poi' AND nf.location_id = p.poi_id
            WHERE nf.user_id = ?
            ORDER BY nf.created_at DESC""",
            (user_id,),
        ).fetchall()

    log_activity("view", "navigation_favorites", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@campus_navigation_bp.route("/favorites", methods=["POST"])
@token_required
def add_favorite():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "location_type", "location_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO navigation_favorites
               (user_id, location_type, location_id, nickname)
               VALUES (?, ?, ?, ?)""",
            (data["user_id"], data["location_type"], data["location_id"], data.get("nickname", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM navigation_favorites WHERE favorite_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "navigation_favorite", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@campus_navigation_bp.route("/favorites/<int:favorite_id>", methods=["DELETE"])
@token_required
def remove_favorite(favorite_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM navigation_favorites WHERE favorite_id = ?", (favorite_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"favorite {favorite_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM navigation_favorites WHERE favorite_id = ?", (favorite_id,))

    log_activity("delete", "navigation_favorite", user=g.current_user.get("sub"))
    return jsonify({"message": f"Favorite {favorite_id} deleted"})


# ---- analytics ----

@campus_navigation_bp.route("/popular-routes", methods=["GET"])
@token_required
def get_popular_routes():
    limit = request.args.get("limit", 10, type=int)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT start_location, end_location,
                      COUNT(*) AS usage_count,
                      AVG(duration_minutes) AS avg_duration,
                      AVG(rating) AS avg_rating
               FROM navigation_history
               WHERE rating IS NOT NULL
               GROUP BY start_location, end_location
               ORDER BY usage_count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    log_activity("view", "popular_routes", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@campus_navigation_bp.route("/buildings/<int:building_id>/stats", methods=["GET"])
@token_required
def get_building_stats(building_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_buildings WHERE building_id = ?", (building_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"building {building_id} not found")

    with get_connection() as conn:
        nav_stats = conn.execute(
            """SELECT COUNT(*) AS total_navigations, AVG(duration_minutes) AS avg_visit_duration
               FROM navigation_history nh
               JOIN campus_buildings cb ON nh.end_location = cb.building_name
               WHERE cb.building_id = ?""",
            (building_id,),
        ).fetchone()
        poi_count = conn.execute(
            "SELECT COUNT(*) AS count FROM points_of_interest WHERE building_id = ?",
            (building_id,),
        ).fetchone()

    log_activity("view", "building_stats", user=g.current_user.get("sub"))
    return jsonify({
        "navigation": _row_to_dict(nav_stats) if nav_stats else {},
        "points_of_interest": poi_count["count"] if poi_count else 0,
    })

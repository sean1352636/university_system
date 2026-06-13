"""Events routes: discovery events, RSVPs, attendance, and ratings."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

events_discovery_bp = Blueprint("events_discovery", __name__, url_prefix="/api/events")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- events ----

@events_discovery_bp.route("/events", methods=["GET"])
@token_required
def list_events():
    search = request.args.get("search")
    category = request.args.get("category")
    organizer_id = request.args.get("organizer_id")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM campus_events WHERE event_name LIKE ? OR description LIKE ? OR location LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if category:
            conditions.append("event_category = ?")
            params.append(category)
        if organizer_id:
            conditions.append("organizer_id = ?")
            params.append(organizer_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM campus_events" + where + " ORDER BY event_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM campus_events" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "campus_events", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@events_discovery_bp.route("/events/<int:event_id>", methods=["GET"])
@token_required
def get_event(event_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"events {event_id} not found")
    log_activity("view", "campus_events", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@events_discovery_bp.route("/events", methods=["POST"])
@token_required
def create_event():
    data = request.get_json(silent=True) or {}
    for field in ["title", "category", "start_datetime", "location"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    # Split start_datetime/end_datetime into date + time for campus_events schema
    start_dt = data["start_datetime"]
    end_dt = data.get("end_datetime", "")
    if " " in start_dt:
        event_date, start_time = start_dt.split(" ", 1)
    else:
        event_date, start_time = start_dt, ""
    end_time = end_dt.split(" ", 1)[1] if " " in end_dt else end_dt

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO campus_events
               (event_name, event_type, event_category, event_date, start_time, end_time,
                location, description, building, room_id, organizer_id, organizer_name,
                organizer_type, capacity, registration_required, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["title"], data.get("category", "Other"), data["category"],
             event_date, start_time, end_time,
             data["location"], data.get("description", ""),
             data.get("building", ""), data.get("room", ""),
             data.get("organizer_id", ""), data.get("organizer_name", ""),
             data.get("organizer_type", "Student"),
             data.get("max_capacity", 0), data.get("registration_required", 0),
             data.get("tags", ""), now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_events WHERE event_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "campus_events", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- rsvps ----

@events_discovery_bp.route("/rsvps", methods=["GET"])
@token_required
def list_rsvps():
    event_id = request.args.get("event_id")
    user_id = request.args.get("user_id")
    rsvp_status = request.args.get("rsvp_status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if event_id:
            conditions.append("event_id = ?")
            params.append(event_id)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if rsvp_status:
            conditions.append("rsvp_status = ?")
            params.append(rsvp_status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM discovery_event_rsvps" + where + " ORDER BY rsvp_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM discovery_event_rsvps" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "discovery_event_rsvps", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@events_discovery_bp.route("/rsvps/<int:rsvp_id>", methods=["GET"])
@token_required
def get_rsvp(rsvp_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM discovery_event_rsvps WHERE rsvp_id = ?", (rsvp_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"rsvps {rsvp_id} not found")
    log_activity("view", "discovery_event_rsvps", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@events_discovery_bp.route("/rsvps", methods=["POST"])
@token_required
def create_rsvp():
    data = request.get_json(silent=True) or {}
    for field in ["event_id", "user_id", "rsvp_status"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO discovery_event_rsvps
               (event_id, user_id, rsvp_status, created_at)
               VALUES (?, ?, ?, ?)""",
            (data["event_id"], data["user_id"], data["rsvp_status"], now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM discovery_event_rsvps WHERE rsvp_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "discovery_event_rsvps", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- update / cancel event ----

@events_discovery_bp.route("/events/<int:event_id>", methods=["PUT"])
@token_required
def update_event(event_id: int):
    data = request.get_json(silent=True) or {}

    allowed = ["event_name", "event_type", "event_category", "description", "location",
               "building", "room_id", "capacity", "registration_required", "tags",
               "event_date", "start_time", "end_time", "start_datetime", "end_datetime"]

    field_map = {
        "event_name": "event_name",
        "capacity": "capacity",
    }

    update_fields = []
    values = []

    for key in allowed:
        if key in data:
            col = field_map.get(key, key)
            update_fields.append(f"{col} = ?")
            values.append(data[key])

    if not update_fields:
        raise ValidationError("No valid fields to update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_fields.append("created_at = created_at")  # no-op to keep syntax valid
    values.append(event_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE campus_events SET " + ", ".join(update_fields) + " WHERE event_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_events WHERE event_id = ?", (event_id,)
        ).fetchone()

    if not row:
        raise ValidationError(f"event {event_id} not found")

    log_activity("update", "campus_events", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@events_discovery_bp.route("/events/<int:event_id>/cancel", methods=["PUT"])
@token_required
def cancel_event(event_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"event {event_id} not found")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE campus_events SET status = 'cancelled' WHERE event_id = ?",
            (event_id,),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_events WHERE event_id = ?", (event_id,)
        ).fetchone()

    log_activity("cancel", "campus_events", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- upcoming events ----

@events_discovery_bp.route("/upcoming", methods=["GET"])
@token_required
def get_upcoming_events():
    limit = request.args.get("limit", 20, type=int)
    category = request.args.get("category")

    conditions = ["date(event_date) >= date('now')"]
    params: list = []
    if category:
        conditions.append("event_category = ?")
        params.append(category)

    where = " WHERE " + " AND ".join(conditions)
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM campus_events" + where + " ORDER BY event_date ASC, start_time ASC LIMIT ?",
            params,
        ).fetchall()

    log_activity("view", "upcoming_events", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- RSVP management ----

@events_discovery_bp.route("/rsvps/<int:rsvp_id>", methods=["PUT"])
@token_required
def update_rsvp(rsvp_id: int):
    data = request.get_json(silent=True) or {}
    rsvp_status = data.get("rsvp_status")
    if not rsvp_status:
        raise ValidationError("rsvp_status is required")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE discovery_event_rsvps SET rsvp_status = ?, rsvp_date = ? WHERE rsvp_id = ?",
            (rsvp_status, now, rsvp_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM discovery_event_rsvps WHERE rsvp_id = ?", (rsvp_id,)
        ).fetchone()

    if not row:
        raise ValidationError(f"rsvp {rsvp_id} not found")

    log_activity("update", "discovery_event_rsvps", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@events_discovery_bp.route("/rsvps/<int:rsvp_id>", methods=["DELETE"])
@token_required
def cancel_rsvp(rsvp_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM discovery_event_rsvps WHERE rsvp_id = ?", (rsvp_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"rsvp {rsvp_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM discovery_event_rsvps WHERE rsvp_id = ?", (rsvp_id,))

    log_activity("delete", "discovery_event_rsvps", user=g.current_user.get("sub"))
    return jsonify({"message": f"RSVP {rsvp_id} cancelled"})


# ---- check-in / check-out ----

@events_discovery_bp.route("/attendance/check-in", methods=["POST"])
@token_required
def check_in():
    data = request.get_json(silent=True) or {}
    for field in ["event_id", "user_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        # Use INSERT OR REPLACE to handle re-check-in
        conn.execute(
            """INSERT INTO discovery_event_attendance (event_id, user_id, check_in_time)
               VALUES (?, ?, ?)
               ON CONFLICT(event_id, user_id) DO UPDATE SET check_in_time = excluded.check_in_time""",
            (data["event_id"], data["user_id"], now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM discovery_event_attendance WHERE attendance_id = ?", (new_id,)
        ).fetchone()

    log_activity("check_in", "discovery_event_attendance", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row) if row else {"event_id": data["event_id"], "user_id": data["user_id"], "check_in_time": now}), 201


@events_discovery_bp.route("/attendance/check-out", methods=["PUT"])
@token_required
def check_out():
    data = request.get_json(silent=True) or {}
    for field in ["event_id", "user_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE discovery_event_attendance SET check_out_time = ? WHERE event_id = ? AND user_id = ?",
            (now, data["event_id"], data["user_id"]),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM discovery_event_attendance WHERE event_id = ? AND user_id = ?",
            (data["event_id"], data["user_id"]),
        ).fetchone()

    if not row:
        raise ValidationError("No check-in record found for this event and user")

    log_activity("check_out", "discovery_event_attendance", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@events_discovery_bp.route("/attendance", methods=["GET"])
@token_required
def list_attendance():
    event_id = request.args.get("event_id")
    user_id = request.args.get("user_id")

    conditions = []
    params: list = []
    if event_id:
        conditions.append("event_id = ?")
        params.append(event_id)
    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM discovery_event_attendance" + where + " ORDER BY check_in_time DESC",
            params,
        ).fetchall()

    log_activity("view", "discovery_event_attendance", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- ratings / reviews ----

@events_discovery_bp.route("/ratings", methods=["POST"])
@token_required
def create_rating():
    data = request.get_json(silent=True) or {}
    for field in ["event_id", "user_id", "rating"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    rating = int(data["rating"])
    if not (1 <= rating <= 5):
        raise ValidationError("rating must be between 1 and 5")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO discovery_event_ratings (event_id, user_id, rating, review, rated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(event_id, user_id) DO UPDATE SET
                   rating = excluded.rating,
                   review = excluded.review,
                   rated_at = excluded.rated_at""",
            (data["event_id"], data["user_id"], rating, data.get("review", ""), now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM discovery_event_ratings WHERE rating_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "discovery_event_ratings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row) if row else {"rating_id": new_id}), 201


@events_discovery_bp.route("/events/<int:event_id>/reviews", methods=["GET"])
@token_required
def get_event_reviews(event_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM discovery_event_ratings WHERE event_id = ? ORDER BY rated_at DESC",
            (event_id,),
        ).fetchall()

    log_activity("view", "discovery_event_ratings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- event statistics ----

@events_discovery_bp.route("/events/<int:event_id>/statistics", methods=["GET"])
@token_required
def get_event_statistics(event_id: int):
    with get_connection() as conn:
        event = conn.execute(
            "SELECT * FROM campus_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    if not event:
        raise ValidationError(f"event {event_id} not found")

    stats: dict = {"event": _row_to_dict(event)}

    with get_connection() as conn:
        # RSVP breakdown
        rsvp_rows = conn.execute(
            "SELECT rsvp_status, COUNT(*) AS count FROM discovery_event_rsvps WHERE event_id = ? GROUP BY rsvp_status",
            (event_id,),
        ).fetchall()
        stats["rsvp_breakdown"] = {r["rsvp_status"]: r["count"] for r in rsvp_rows}

        # Attendance count
        att_row = conn.execute(
            "SELECT COUNT(*) AS count FROM discovery_event_attendance WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        stats["attendance_count"] = att_row["count"] if att_row else 0

        # Rating statistics
        rating_row = conn.execute(
            """SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count,
                      COUNT(CASE WHEN review IS NOT NULL AND review != '' THEN 1 END) AS text_review_count
               FROM discovery_event_ratings WHERE event_id = ?""",
            (event_id,),
        ).fetchone()
        stats["average_rating"] = round(rating_row["avg_rating"], 2) if rating_row and rating_row["avg_rating"] else None
        stats["review_count"] = rating_row["review_count"] if rating_row else 0
        stats["text_review_count"] = rating_row["text_review_count"] if rating_row else 0

        # Photo count
        photo_row = conn.execute(
            "SELECT COUNT(*) AS count FROM discovery_event_photos WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        stats["photo_count"] = photo_row["count"] if photo_row else 0

    log_activity("view", "event_statistics", user=g.current_user.get("sub"))
    return jsonify(stats)

"""Cinema routes: movies, screenings, and bookings."""

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

cinema_bp = Blueprint("cinema", __name__, url_prefix="/api/cinema")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- movies ----

@cinema_bp.route("/movies", methods=["GET"])
@token_required
def list_movies():
    search = request.args.get("search")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM cinema_movies WHERE title LIKE ? OR genre LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM cinema_movies" + where + " ORDER BY movie_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM cinema_movies" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "cinema_movies", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@cinema_bp.route("/movies/<int:movie_id>", methods=["GET"])
@token_required
def get_movie(movie_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cinema_movies WHERE movie_id = ?", (movie_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"movies {movie_id} not found")
    log_activity("view", "cinema_movies", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@cinema_bp.route("/movies", methods=["POST"])
@token_required
def create_movie():
    data = request.get_json(silent=True) or {}
    for field in ["title", "genre", "duration_minutes"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO cinema_movies
               (title, genre, duration_minutes, description, director, rating, release_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["title"], data["genre"], data["duration_minutes"], data.get("description", ""), data.get("director", ""), data.get("rating", ""), data.get("release_date", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cinema_movies WHERE movie_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "cinema_movies", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- screenings ----

@cinema_bp.route("/screenings", methods=["GET"])
@token_required
def list_screenings():
    movie_id = request.args.get("movie_id")
    screen_number = request.args.get("screen_number")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if movie_id:
            conditions.append("movie_id = ?")
            params.append(movie_id)
        if screen_number:
            conditions.append("screen_number = ?")
            params.append(screen_number)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM cinema_screenings" + where + " ORDER BY screening_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM cinema_screenings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "cinema_screenings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@cinema_bp.route("/screenings/<int:screening_id>", methods=["GET"])
@token_required
def get_screening(screening_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cinema_screenings WHERE screening_id = ?", (screening_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"screenings {screening_id} not found")
    log_activity("view", "cinema_screenings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@cinema_bp.route("/screenings", methods=["POST"])
@token_required
def create_screening():
    data = request.get_json(silent=True) or {}
    for field in ["movie_id", "screen_number", "screening_date", "screening_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO cinema_screenings
               (movie_id, screen_number, screening_date, screening_time, price, available_seats, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["movie_id"], data["screen_number"], data["screening_date"], data["screening_time"], data.get("price", ""), data.get("available_seats", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cinema_screenings WHERE screening_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "cinema_screenings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- bookings ----

@cinema_bp.route("/bookings", methods=["GET"])
@token_required
def list_bookings():
    customer_id = request.args.get("customer_id")
    screening_id = request.args.get("screening_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if customer_id:
            conditions.append("customer_id = ?")
            params.append(customer_id)
        if screening_id:
            conditions.append("screening_id = ?")
            params.append(screening_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM cinema_bookings" + where + " ORDER BY booking_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM cinema_bookings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "cinema_bookings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@cinema_bp.route("/bookings/<int:booking_id>", methods=["GET"])
@token_required
def get_booking(booking_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cinema_bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"bookings {booking_id} not found")
    log_activity("view", "cinema_bookings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@cinema_bp.route("/bookings", methods=["POST"])
@token_required
def create_booking():
    data = request.get_json(silent=True) or {}
    for field in ["screening_id", "customer_id", "seats"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO cinema_bookings
               (screening_id, customer_id, seats, total_amount, payment_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["screening_id"], data["customer_id"], data["seats"], data.get("total_amount", ""), data.get("payment_status", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cinema_bookings WHERE booking_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "cinema_bookings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

"""Lost & found routes: item management and claims."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_lost_found_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

lost_found_bp = Blueprint("lost_found", __name__, url_prefix="/api/lost-found")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@lost_found_bp.route("", methods=["GET"])
@token_required
def list_items():
    status = request.args.get("status")
    category = request.args.get("category")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM lost_found WHERE item_description LIKE ? OR location_found LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM lost_found" + where + " ORDER BY found_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM lost_found" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "lost_found_items", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@lost_found_bp.route("/<int:item_id>", methods=["GET"])
@token_required
def get_item(item_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Lost & found item {item_id} not found")
    log_activity("view", "lost_found_item", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@lost_found_bp.route("", methods=["POST"])
@token_required
def create_item():
    data = request.get_json(silent=True) or {}
    validate_lost_found_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO lost_found
               (item_description, category, location_found, found_date,
                found_time, storage_location, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'unclaimed', ?)""",
            (
                data["item_description"],
                data.get("category", "other"),
                data.get("location_found", ""),
                data["found_date"],
                data.get("found_time", ""),
                data.get("storage_location", ""),
                data.get("notes", ""),
            ),
        )
        item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()

    log_activity("create", "lost_found_item", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@lost_found_bp.route("/<int:item_id>/claim", methods=["POST"])
@token_required
def claim_item(item_id: int):
    with get_connection() as conn:
        item = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()
    if not item:
        raise ValidationError(f"Lost & found item {item_id} not found")
    if item["status"] == "claimed":
        raise ValidationError(f"Item {item_id} has already been claimed")

    data = request.get_json(silent=True) or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            """UPDATE lost_found
               SET status = 'claimed', claimed = 1, claimed_by_name = ?,
                   claimed_by_email = ?, claimed_by_phone = ?,
                   claim_date = ?, identification_method = ?
               WHERE id = ?""",
            (
                data.get("claimed_by_name", ""),
                data.get("claimed_by_email", ""),
                data.get("claimed_by_phone", ""),
                now,
                data.get("identification_method", ""),
                item_id,
            ),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()

    log_activity("claim", "lost_found_item", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@lost_found_bp.route("/<int:item_id>/status", methods=["PUT"])
@token_required
def update_item_status(item_id: int):
    with get_connection() as conn:
        item = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()
    if not item:
        raise ValidationError(f"Lost & found item {item_id} not found")

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    valid_statuses = ["unclaimed", "claimed", "returned", "donated", "discarded"]
    if not new_status or new_status not in valid_statuses:
        raise ValidationError(f"Invalid status. Must be one of {valid_statuses}")

    with transaction() as conn:
        conn.execute(
            "UPDATE lost_found SET status = ? WHERE id = ?",
            (new_status, item_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()

    log_activity("update", "lost_found_item_status", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@lost_found_bp.route("/search", methods=["GET"])
@token_required
def search_items():
    q = request.args.get("q", "")
    category = request.args.get("category")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    status = request.args.get("status")

    if not q and not category and not date_from and not date_to and not status:
        raise ValidationError("At least one search parameter is required")

    conditions = []
    params: list = []

    if q:
        pattern = f"%{escape_like(q)}%"
        conditions.append(
            "(item_description LIKE ? OR location_found LIKE ? OR notes LIKE ?)"
        )
        params.extend([pattern, pattern, pattern])

    if category:
        conditions.append("category = ?")
        params.append(category)

    if status:
        conditions.append("status = ?")
        params.append(status)

    if date_from:
        conditions.append("found_date >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("found_date <= ?")
        params.append(date_to)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM lost_found" + where + " ORDER BY found_date DESC",
            params,
        ).fetchall()

    items = [_row_to_dict(r) for r in rows]
    log_activity("search", "lost_found_items", user=g.current_user.get("sub"))
    return jsonify({"items": items, "total": len(items)})


@lost_found_bp.route("/matches/<int:item_id>", methods=["GET"])
@token_required
def get_matches(item_id: int):
    item_type = request.args.get("type", "lost")

    with get_connection() as conn:
        if item_type == "lost":
            rows = conn.execute(
                """SELECT im.*, fi.item_name, fi.description, fi.found_location, fi.found_date
                   FROM item_matches im
                   JOIN found_items fi ON im.found_item_id = fi.item_id
                   WHERE im.lost_item_id = ?
                   ORDER BY im.match_score DESC""",
                (item_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT im.*, li.item_name, li.description, li.lost_location, li.lost_date
                   FROM item_matches im
                   JOIN lost_items li ON im.lost_item_id = li.item_id
                   WHERE im.found_item_id = ?
                   ORDER BY im.match_score DESC""",
                (item_id,),
            ).fetchall()

    matches = [_row_to_dict(r) for r in rows]
    log_activity("view", "lost_found_matches", user=g.current_user.get("sub"))
    return jsonify({"matches": matches, "total": len(matches)})


@lost_found_bp.route("/<int:item_id>/photos", methods=["POST"])
@token_required
def add_photo(item_id: int):
    item_type = request.form.get("item_type", "found")
    caption = request.form.get("caption", "")

    if item_type not in ("lost", "found"):
        raise ValidationError("item_type must be 'lost' or 'found'")

    photo = request.files.get("photo")
    if not photo:
        raise ValidationError("No photo file provided")

    import os
    import hashlib
    from education_system.university_system.core import paths

    photo_data = photo.read()
    photo_hash = hashlib.sha256(photo_data).hexdigest()

    upload_dir = os.path.join(paths.UPLOAD_DIR, "lost_found")
    os.makedirs(upload_dir, exist_ok=True)
    # Sanitize: item_id is an int from URL, item_type validated above
    safe_id = int(item_id)
    filename = f"{item_type}_{safe_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    photo_path = os.path.join(upload_dir, filename)  # lgtm [py/path-injection]

    with open(photo_path, "wb") as f:  # lgtm [py/path-injection]
        f.write(photo_data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO item_photos
               (item_type, item_id, photo_path, photo_hash, caption)
               VALUES (?, ?, ?, ?, ?)""",
            (item_type, item_id, photo_path, photo_hash, caption),
        )
        photo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("create", "lost_found_photo", user=g.current_user.get("sub"))
    return jsonify({"photo_id": photo_id, "photo_path": photo_path}), 201


@lost_found_bp.route("/<int:item_id>/photos", methods=["GET"])
@token_required
def get_photos(item_id: int):
    item_type = request.args.get("item_type", "found")

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM item_photos
               WHERE item_type = ? AND item_id = ?
               ORDER BY uploaded_at""",
            (item_type, item_id),
        ).fetchall()

    photos = [_row_to_dict(r) for r in rows]
    log_activity("view", "lost_found_photos", user=g.current_user.get("sub"))
    return jsonify({"photos": photos, "total": len(photos)})


@lost_found_bp.route("/claims", methods=["GET"])
@token_required
def list_claims():
    found_item_id = request.args.get("found_item_id", type=int)
    claimant_id = request.args.get("claimant_id")
    status = request.args.get("status")

    conditions = []
    params: list = []

    if found_item_id:
        conditions.append("found_item_id = ?")
        params.append(found_item_id)

    if claimant_id:
        conditions.append("claimant_id = ?")
        params.append(claimant_id)

    if status:
        conditions.append("status = ?")
        params.append(status)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM item_claims" + where + " ORDER BY submitted_at DESC",
            params,
        ).fetchall()

    claims = [_row_to_dict(r) for r in rows]
    log_activity("view", "lost_found_claims", user=g.current_user.get("sub"))
    return jsonify({"claims": claims, "total": len(claims)})


@lost_found_bp.route("/claims/<int:claim_id>", methods=["PUT"])
@token_required
def review_claim(claim_id: int):
    with get_connection() as conn:
        claim = conn.execute(
            "SELECT * FROM item_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
    if not claim:
        raise ValidationError(f"Claim {claim_id} not found")

    data = request.get_json(silent=True) or {}
    approved = data.get("approved")
    if approved is None:
        raise ValidationError("'approved' field is required (true/false)")

    status = "Approved" if approved else "Rejected"
    reviewer_id = g.current_user.get("sub", "")
    resolution_notes = data.get("resolution_notes", "")
    now = datetime.now().isoformat()

    with transaction() as conn:
        conn.execute(
            """UPDATE item_claims
               SET status = ?, reviewed_at = ?, reviewed_by = ?,
                   resolution_notes = ?
               WHERE claim_id = ?""",
            (status, now, reviewer_id, resolution_notes, claim_id),
        )

        if approved:
            conn.execute(
                """UPDATE found_items
                   SET status = 'Claimed', updated_at = ?
                   WHERE item_id = ?""",
                (now, claim["found_item_id"]),
            )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM item_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()

    log_activity("review", "lost_found_claim", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@lost_found_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    with get_connection() as conn:
        lost_stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'Found' THEN 1 ELSE 0 END) as found
            FROM lost_items
        """).fetchone()

        found_stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available,
                SUM(CASE WHEN status = 'Claimed' THEN 1 ELSE 0 END) as claimed
            FROM found_items
        """).fetchone()

        claim_stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) as rejected
            FROM item_claims
        """).fetchone()

        match_stats = conn.execute("""
            SELECT COUNT(*) as total_matches, AVG(match_score) as avg_score
            FROM item_matches
            WHERE match_score >= 50
        """).fetchone()

        lf_stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'unclaimed' THEN 1 ELSE 0 END) as unclaimed,
                SUM(CASE WHEN status = 'claimed' THEN 1 ELSE 0 END) as claimed
            FROM lost_found
        """).fetchone()

    log_activity("view", "lost_found_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "lost_items": _row_to_dict(lost_stats) if lost_stats else {},
        "found_items": _row_to_dict(found_stats) if found_stats else {},
        "claims": _row_to_dict(claim_stats) if claim_stats else {},
        "matches": _row_to_dict(match_stats) if match_stats else {},
        "lost_found": _row_to_dict(lf_stats) if lf_stats else {},
    })


@lost_found_bp.route("/categories", methods=["GET"])
@token_required
def get_categories():
    with get_connection() as conn:
        lost_by_cat = conn.execute("""
            SELECT category, COUNT(*) as count
            FROM lost_items
            GROUP BY category
            ORDER BY count DESC
        """).fetchall()

        found_by_cat = conn.execute("""
            SELECT category, COUNT(*) as count
            FROM found_items
            GROUP BY category
            ORDER BY count DESC
        """).fetchall()

        lf_by_cat = conn.execute("""
            SELECT category, COUNT(*) as count
            FROM lost_found
            GROUP BY category
            ORDER BY count DESC
        """).fetchall()

    log_activity("view", "lost_found_categories", user=g.current_user.get("sub"))
    return jsonify({
        "lost": [_row_to_dict(r) for r in lost_by_cat],
        "found": [_row_to_dict(r) for r in found_by_cat],
        "lost_found": [_row_to_dict(r) for r in lf_by_cat],
    })


@lost_found_bp.route("/<int:item_id>", methods=["DELETE"])
@token_required
def delete_item(item_id: int):
    with get_connection() as conn:
        item = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()
    if not item:
        raise ValidationError(f"Lost & found item {item_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM lost_found WHERE id = ?", (item_id,))

    log_activity("delete", "lost_found_item", user=g.current_user.get("sub"))
    return jsonify({"message": f"Item {item_id} deleted", "id": item_id})

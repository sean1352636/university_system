"""Marketplace routes: listings, sublets, free items, and saved listings."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like, validate_identifier
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

marketplace_bp = Blueprint("marketplace", __name__, url_prefix="/api/marketplace")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- listings ----

@marketplace_bp.route("/listings", methods=["GET"])
@token_required
def list_listings():
    search = request.args.get("search")
    seller_id = request.args.get("seller_id")
    category = request.args.get("category")
    listing_type = request.args.get("listing_type")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM marketplace_listings WHERE title LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if seller_id:
            conditions.append("seller_id = ?")
            params.append(seller_id)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if listing_type:
            conditions.append("listing_type = ?")
            params.append(listing_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM marketplace_listings" + where + " ORDER BY listing_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM marketplace_listings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "marketplace_listings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@marketplace_bp.route("/listings/<int:listing_id>", methods=["GET"])
@token_required
def get_listing(listing_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM marketplace_listings WHERE listing_id = ?", (listing_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"listings {listing_id} not found")
    log_activity("view", "marketplace_listings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@marketplace_bp.route("/listings", methods=["POST"])
@token_required
def create_listing():
    data = request.get_json(silent=True) or {}
    for field in ["seller_id", "listing_type", "title", "price"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO marketplace_listings
               (seller_id, listing_type, title, price, description, category, condition_status, location, contact_method, contact_info, is_negotiable, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["seller_id"], data["listing_type"], data["title"], data["price"], data.get("description", ""), data.get("category", ""), data.get("condition_status", ""), data.get("location", ""), data.get("contact_method", ""), data.get("contact_info", ""), data.get("is_negotiable", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM marketplace_listings WHERE listing_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "marketplace_listings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- sublets ----

@marketplace_bp.route("/sublets", methods=["GET"])
@token_required
def list_sublets():
    search = request.args.get("search")
    landlord_id = request.args.get("landlord_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM sublet_listings WHERE title LIKE ? OR address LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if landlord_id:
            conditions.append("landlord_id = ?")
            params.append(landlord_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM sublet_listings" + where + " ORDER BY sublet_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM sublet_listings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "sublet_listings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@marketplace_bp.route("/sublets/<int:sublet_id>", methods=["GET"])
@token_required
def get_sublet(sublet_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sublet_listings WHERE sublet_id = ?", (sublet_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"sublets {sublet_id} not found")
    log_activity("view", "sublet_listings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@marketplace_bp.route("/sublets", methods=["POST"])
@token_required
def create_sublet():
    data = request.get_json(silent=True) or {}
    for field in ["landlord_id", "title", "address", "monthly_rent"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO sublet_listings
               (landlord_id, title, address, monthly_rent, description, bedrooms, bathrooms, square_feet, furnished, available_from, available_to, contact_email, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["landlord_id"], data["title"], data["address"], data["monthly_rent"], data.get("description", ""), data.get("bedrooms", ""), data.get("bathrooms", ""), data.get("square_feet", ""), data.get("furnished", ""), data.get("available_from", ""), data.get("available_to", ""), data.get("contact_email", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sublet_listings WHERE sublet_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "sublet_listings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- free-items ----

@marketplace_bp.route("/free-items", methods=["GET"])
@token_required
def list_free_items():
    search = request.args.get("search")
    giver_id = request.args.get("giver_id")
    status = request.args.get("status")
    category = request.args.get("category")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM free_stuff WHERE item_name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if giver_id:
            conditions.append("giver_id = ?")
            params.append(giver_id)
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
            "SELECT * FROM free_stuff" + where + " ORDER BY item_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM free_stuff" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "free_stuff", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@marketplace_bp.route("/free-items/<int:item_id>", methods=["GET"])
@token_required
def get_free_item(item_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM free_stuff WHERE item_id = ?", (item_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"free-items {item_id} not found")
    log_activity("view", "free_stuff", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@marketplace_bp.route("/free-items", methods=["POST"])
@token_required
def create_free_item():
    data = request.get_json(silent=True) or {}
    for field in ["giver_id", "item_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO free_stuff
               (giver_id, item_name, description, category, condition_status, location, pickup_instructions, contact_info, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["giver_id"], data["item_name"], data.get("description", ""), data.get("category", ""), data.get("condition_status", ""), data.get("location", ""), data.get("pickup_instructions", ""), data.get("contact_info", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM free_stuff WHERE item_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "free_stuff", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- update / delete / sold ----

@marketplace_bp.route("/items/<int:listing_id>", methods=["PUT"])
@token_required
def update_listing(listing_id: int):
    data = request.get_json(silent=True) or {}
    allowed_fields = {
        "title", "description", "category", "price", "condition_status",
        "location", "contact_method", "contact_info", "is_negotiable", "status",
    }
    valid_updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not valid_updates:
        raise ValidationError("No valid fields to update")

    set_clause = ", ".join(
        [validate_identifier(f, "column") + " = ?" for f in valid_updates]
    )
    set_clause += ", updated_at = ?"
    values = list(valid_updates.values())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values.append(now)
    values.append(listing_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE marketplace_listings SET " + set_clause + " WHERE listing_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM marketplace_listings WHERE listing_id = ?", (listing_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Listing {listing_id} not found")

    log_activity("update", "marketplace_listing", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@marketplace_bp.route("/items/<int:listing_id>", methods=["DELETE"])
@token_required
def delete_listing(listing_id: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = request.args.get("user_id")

    with transaction() as conn:
        if user_id:
            row = conn.execute(
                "SELECT seller_id FROM marketplace_listings WHERE listing_id = ?",
                (listing_id,),
            ).fetchone()
            if not row or row["seller_id"] != user_id:
                raise ValidationError("Not authorised to delete this listing")

        conn.execute(
            "UPDATE marketplace_listings SET status = 'Deleted', updated_at = ? WHERE listing_id = ?",
            (now, listing_id),
        )

    log_activity("delete", "marketplace_listing", user=g.current_user.get("sub"))
    return jsonify({"message": "Listing deleted", "listing_id": listing_id})


@marketplace_bp.route("/items/<int:listing_id>/sold", methods=["POST"])
@token_required
def mark_listing_sold(listing_id: int):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or g.current_user.get("sub")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        row = conn.execute(
            "SELECT seller_id FROM marketplace_listings WHERE listing_id = ?",
            (listing_id,),
        ).fetchone()
        if not row:
            raise ValidationError(f"Listing {listing_id} not found")
        if row["seller_id"] != user_id:
            raise ValidationError("Not authorised to mark this listing as sold")

        conn.execute(
            "UPDATE marketplace_listings SET status = 'Sold', updated_at = ? WHERE listing_id = ?",
            (now, listing_id),
        )

    log_activity("update", "marketplace_listing", user=g.current_user.get("sub"))
    return jsonify({"message": "Listing marked as sold", "listing_id": listing_id})


# ---- user listings ----

@marketplace_bp.route("/users/<user_id>/listings", methods=["GET"])
@token_required
def get_user_listings(user_id: str):
    status = request.args.get("status")

    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM marketplace_listings WHERE seller_id = ? AND status = ? ORDER BY listing_id DESC",
                (user_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM marketplace_listings WHERE seller_id = ? ORDER BY listing_id DESC",
                (user_id,),
            ).fetchall()

    log_activity("view", "marketplace_listings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- saved / favorite listings ----

@marketplace_bp.route("/items/<int:listing_id>/save", methods=["POST"])
@token_required
def save_listing(listing_id: int):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or g.current_user.get("sub")
    listing_type = data.get("listing_type", "marketplace")
    notes = data.get("notes", "")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO saved_listings (user_id, listing_type, listing_id, notes, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, listing_type, listing_id, notes, now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("create", "saved_listing", user=g.current_user.get("sub"))
    return jsonify({"saved_id": new_id, "listing_id": listing_id}), 201


@marketplace_bp.route("/users/<user_id>/saved", methods=["GET"])
@token_required
def get_saved_listings(user_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT sl.*,
                CASE sl.listing_type
                    WHEN 'marketplace' THEN ml.title
                    WHEN 'sublet' THEN sub.title
                    WHEN 'free_stuff' THEN fs.item_name
                END as listing_title
            FROM saved_listings sl
            LEFT JOIN marketplace_listings ml ON sl.listing_type = 'marketplace'
                AND sl.listing_id = ml.listing_id
            LEFT JOIN sublet_listings sub ON sl.listing_type = 'sublet'
                AND sl.listing_id = sub.sublet_id
            LEFT JOIN free_stuff fs ON sl.listing_type = 'free_stuff'
                AND sl.listing_id = fs.item_id
            WHERE sl.user_id = ?
            ORDER BY sl.created_at DESC""",
            (user_id,),
        ).fetchall()

    log_activity("view", "saved_listings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@marketplace_bp.route("/items/<int:listing_id>/save", methods=["DELETE"])
@token_required
def remove_saved_listing(listing_id: int):
    user_id = request.args.get("user_id") or g.current_user.get("sub")

    with transaction() as conn:
        conn.execute(
            "DELETE FROM saved_listings WHERE listing_id = ? AND user_id = ?",
            (listing_id, user_id),
        )

    log_activity("delete", "saved_listing", user=g.current_user.get("sub"))
    return jsonify({"message": "Saved listing removed", "listing_id": listing_id})


# ---- claim free item ----

@marketplace_bp.route("/items/<int:item_id>/claim", methods=["POST"])
@token_required
def claim_free_item(item_id: int):
    data = request.get_json(silent=True) or {}
    claimer_id = data.get("claimer_id") or g.current_user.get("sub")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        row = conn.execute(
            "SELECT status FROM free_stuff WHERE item_id = ?", (item_id,)
        ).fetchone()
        if not row:
            raise ValidationError(f"Free item {item_id} not found")
        if row["status"] != "Available":
            raise ValidationError("Item is no longer available")

        conn.execute(
            "UPDATE free_stuff SET status = 'Claimed', claimed_by = ?, claimed_at = ? WHERE item_id = ?",
            (claimer_id, now, item_id),
        )

    log_activity("update", "free_stuff_claim", user=g.current_user.get("sub"))
    return jsonify({"message": "Item claimed", "item_id": item_id, "claimed_by": claimer_id})


# ---- categories ----

@marketplace_bp.route("/categories", methods=["GET"])
@token_required
def get_categories():
    categories = [
        "Textbooks",
        "Electronics",
        "Furniture",
        "Housing",
        "Services",
        "Free",
        "Other",
    ]
    return jsonify({"categories": categories})


# ---- advanced search ----

@marketplace_bp.route("/search", methods=["GET"])
@token_required
def advanced_search():
    search_term = request.args.get("q")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    category = request.args.get("category")
    listing_type = request.args.get("listing_type")
    status = request.args.get("status", "Active")

    conditions = ["1=1"]
    params: list = []

    if search_term:
        pattern = f"%{escape_like(search_term)}%"
        conditions.append("(title LIKE ? OR description LIKE ?)")
        params.extend([pattern, pattern])
    if category:
        conditions.append("category = ?")
        params.append(category)
    if listing_type:
        conditions.append("listing_type = ?")
        params.append(listing_type)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if min_price is not None:
        conditions.append("price >= ?")
        params.append(min_price)
    if max_price is not None:
        conditions.append("price <= ?")
        params.append(max_price)

    where = " WHERE " + " AND ".join(conditions)
    page, per_page, offset = get_pagination_params()
    params_count = list(params)
    params.extend([per_page, offset])

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM marketplace_listings" + where + " ORDER BY listing_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM marketplace_listings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("search", "marketplace_listings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))

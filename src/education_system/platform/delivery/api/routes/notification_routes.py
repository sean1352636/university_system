"""Notification preferences for the signed-in user.

Routes (registered under ``/api/v1/notifications``):

* ``GET    /preferences``  effective settings per category and channel
* ``PUT    /preferences``  ``{"categories": {"offers": {"email": true}}}``
* ``DELETE /preferences``  back to the defaults

A user can only ever read or change their own preferences; there is no
user id in the path to get wrong. The id is the shared auth database's,
the same one the bus-driven notifications address.
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.security.authentication import token_required
from education_system.platform.features.notifications.preferences import (
    NotificationPreferences,
    PreferenceError,
)

logger = logging.getLogger(__name__)

notification_prefs_bp = Blueprint(
    "notification_preferences", __name__, url_prefix="/api/notifications")

_db_path: str | None = None


def init_notification_routes(db_path: str | None = None) -> None:
    """Point the routes at an auth DB (tests pass a temp one)."""
    global _db_path
    _db_path = db_path


def _prefs() -> NotificationPreferences:
    return NotificationPreferences(_db_path)


@notification_prefs_bp.route("/preferences", methods=["GET"])
@token_required
def get_preferences():
    return jsonify(_prefs().get_preferences(g.current_user["user_id"]))


@notification_prefs_bp.route("/preferences", methods=["PUT"])
@token_required
def put_preferences():
    body = request.get_json(silent=True) or {}
    changes = body.get("categories")
    if not isinstance(changes, dict) or not changes:
        return jsonify({"error": "categories must be an object of "
                                 "{category: {channel: true|false}}"}), 400
    try:
        result = _prefs().set_preferences(g.current_user["user_id"], changes)
    except PreferenceError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@notification_prefs_bp.route("/preferences", methods=["DELETE"])
@token_required
def reset_preferences():
    removed = _prefs().reset(g.current_user["user_id"])
    return jsonify({"reset": removed,
                    **_prefs().get_preferences(g.current_user["user_id"])})


__all__ = ["init_notification_routes", "notification_prefs_bp"]

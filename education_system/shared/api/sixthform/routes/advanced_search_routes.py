"""REST API for Sixth Form advanced search (item 40).

Read/run endpoints clients can call over HTTP instead of importing the
sixth-form package:

* GET  /api/sixthform/advanced-search/saved              — list saved searches
* GET  /api/sixthform/advanced-search/run?q=&scopes=&limit=  — run a query
* GET  /api/sixthform/advanced-search/cohorts            — list cohorts
* GET  /api/sixthform/advanced-search/telemetry          — telemetry summary

Auth mirrors the other sixth-form routes: a JWT bearer token (validated
by ``token_required`` if importable) or an ``X-Sixthform-Token`` header
matching ``SIXTHFORM_API_TOKEN``.
"""

from __future__ import annotations

import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

advanced_search_bp = Blueprint(
    "sf_advanced_search", __name__, url_prefix="/api/sixthform")


def _token_required(view):
    try:
        from education_system.shared.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("SIXTHFORM_API_TOKEN")
            got = request.headers.get("X-Sixthform-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _data():
    from education_system.sixthform_system.modules.domain.students.advanced_search import (
        advanced_search as data,
    )
    return data


@advanced_search_bp.route("/advanced-search/saved", methods=["GET"])
@_token_required
def saved_route():
    data = _data()
    rows = data.list_saved_searches()
    return jsonify({
        "saved_searches": [
            {"saved_id": s.saved_id, "name": s.name, "query": s.query,
             "scopes": s.scopes, "visibility": s.visibility,
             "tags": s.tags}
            for s in rows],
        "count": len(rows),
    })


@advanced_search_bp.route("/advanced-search/run", methods=["GET"])
@_token_required
def run_route():
    data = _data()
    q = request.args.get("q", "")
    scopes_arg = request.args.get("scopes")
    scopes = ([s.strip() for s in scopes_arg.split(",") if s.strip()]
              if scopes_arg else None)
    try:
        limit = int(request.args.get("limit", "25"))
    except ValueError:
        limit = 25
    role = request.args.get("role")
    filters = {"role": role} if role else {}
    try:
        results = data.run_search(q, scopes=scopes, limit_per_scope=limit,
                                  filters=filters, record_history=False)
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({
        "query": results.query,
        "total": results.total,
        "scopes": results.scopes,
        "suggestions": results.suggestions,
        "hits": [
            {"scope": h.scope, "entity_id": h.entity_id, "label": h.label,
             "sublabel": h.sublabel, "score": round(h.score, 4)}
            for h in (results.ranked_hits or results.all_hits())],
    })


@advanced_search_bp.route("/advanced-search/cohorts", methods=["GET"])
@_token_required
def cohorts_route():
    data = _data()
    rows = data.list_cohorts()
    return jsonify({
        "cohorts": [
            {"cohort_id": c.cohort_id, "name": c.name,
             "member_count": c.member_count, "notes": c.notes}
            for c in rows],
        "count": len(rows),
    })


@advanced_search_bp.route("/advanced-search/telemetry", methods=["GET"])
@_token_required
def telemetry_route():
    data = _data()
    ts = data.telemetry_summary()
    return jsonify({
        "total_searches": ts.total_searches,
        "zero_result": ts.zero_result,
        "top_queries": ts.top_queries,
        "slowest_scopes_ms": ts.slowest_scopes_ms,
        "zero_result_queries": ts.zero_result_queries,
    })

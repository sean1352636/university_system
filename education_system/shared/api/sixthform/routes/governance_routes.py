"""REST API for Sixth Form Governance.

Exposes CRUD over HTTP for two central governance submodules:

* policies         — the policy register (/policies) with its revision
                     log (/policies/<id>/revisions) and a summary view.
* risk_management  — the risk register (/risks) with mitigation actions
                     (/risks/<id>/actions), periodic reviews
                     (/risks/<id>/reviews) and an aggregate overview.

Auth mirrors the other sixth-form route modules: a JWT bearer token
(validated by the university ``token_required`` if importable) or an
``X-Sixthform-Token`` header matching ``SIXTHFORM_API_TOKEN``.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

governance_bp = Blueprint(
    "sf_governance", __name__, url_prefix="/api/sixthform/governance")


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


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe dicts."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# ── Policies ───────────────────────────────────────────────────────

@governance_bp.route("/policies", methods=["GET"])
@_token_required
def list_policies_route():
    from education_system.sixthform_system.modules.domain.governance.policies import (  # noqa: E501
        policies as data,
    )
    try:
        rows = data.list_policies(
            category=request.args.get("category"),
            status=request.args.get("status"),
            owner=request.args.get("owner"),
            overdue_only=_truthy(request.args.get("overdue_only")),
            query=request.args.get("query"),
        )
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"policies": _dump(rows), "count": len(rows)})


@governance_bp.route("/policies/<int:policy_id>", methods=["GET"])
@_token_required
def get_policy_route(policy_id: int):
    from education_system.sixthform_system.modules.domain.governance.policies import (  # noqa: E501
        policies as data,
    )
    p = data.get_policy(policy_id)
    if p is None:
        return jsonify({"error": f"No policy #{policy_id}"}), 404
    return jsonify(_dump(p))


@governance_bp.route("/policies", methods=["POST"])
@_token_required
def create_policy_route():
    from education_system.sixthform_system.modules.domain.governance.policies import (  # noqa: E501
        policies as data,
    )
    try:
        p = data.create_policy(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(p)), 201


@governance_bp.route("/policies/<int:policy_id>", methods=["PUT"])
@_token_required
def update_policy_route(policy_id: int):
    from education_system.sixthform_system.modules.domain.governance.policies import (  # noqa: E501
        policies as data,
    )
    if data.get_policy(policy_id) is None:
        return jsonify({"error": f"No policy #{policy_id}"}), 404
    try:
        p = data.update_policy(policy_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(p))


@governance_bp.route("/policies/<int:policy_id>", methods=["DELETE"])
@_token_required
def delete_policy_route(policy_id: int):
    from education_system.sixthform_system.modules.domain.governance.policies import (  # noqa: E501
        policies as data,
    )
    if not data.delete_policy(policy_id):
        return jsonify({"error": f"No policy #{policy_id}"}), 404
    return jsonify({"deleted": policy_id})


@governance_bp.route("/policies/<int:policy_id>/revisions", methods=["GET"])
@_token_required
def list_revisions_route(policy_id: int):
    from education_system.sixthform_system.modules.domain.governance.policies import (  # noqa: E501
        policies as data,
    )
    if data.get_policy(policy_id) is None:
        return jsonify({"error": f"No policy #{policy_id}"}), 404
    rows = data.list_revisions(policy_id)
    return jsonify({"revisions": _dump(rows), "count": len(rows)})


@governance_bp.route("/policies/<int:policy_id>/revisions", methods=["POST"])
@_token_required
def add_revision_route(policy_id: int):
    from education_system.sixthform_system.modules.domain.governance.policies import (  # noqa: E501
        policies as data,
    )
    try:
        r = data.add_revision(policy_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(r)), 201


@governance_bp.route("/policies/summary", methods=["GET"])
@_token_required
def policies_summary_route():
    from education_system.sixthform_system.modules.domain.governance.policies import (  # noqa: E501
        policies as data,
    )
    return jsonify(_dump(data.summary()))


# ── Risk management ────────────────────────────────────────────────

@governance_bp.route("/risks", methods=["GET"])
@_token_required
def list_risks_route():
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    min_score = request.args.get("min_score")
    try:
        rows = data.list_risks(
            status=request.args.get("status"),
            category=request.args.get("category"),
            owner=request.args.get("owner"),
            open_only=_truthy(request.args.get("open_only")),
            review_due_only=_truthy(request.args.get("review_due_only")),
            min_score=int(min_score) if min_score not in (None, "") else None,
            search=request.args.get("search"),
        )
    except (data.ValidationError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"risks": _dump(rows), "count": len(rows)})


@governance_bp.route("/risks/<int:risk_id>", methods=["GET"])
@_token_required
def get_risk_route(risk_id: int):
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    r = data.get_risk(risk_id)
    if r is None:
        return jsonify({"error": f"No risk #{risk_id}"}), 404
    return jsonify(_dump(r))


@governance_bp.route("/risks", methods=["POST"])
@_token_required
def create_risk_route():
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    try:
        r = data.create_risk(request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(r)), 201


@governance_bp.route("/risks/<int:risk_id>", methods=["PUT"])
@_token_required
def update_risk_route(risk_id: int):
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    if data.get_risk(risk_id) is None:
        return jsonify({"error": f"No risk #{risk_id}"}), 404
    try:
        r = data.update_risk(risk_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(r))


@governance_bp.route("/risks/<int:risk_id>", methods=["DELETE"])
@_token_required
def delete_risk_route(risk_id: int):
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    if not data.delete_risk(risk_id):
        return jsonify({"error": f"No risk #{risk_id}"}), 404
    return jsonify({"deleted": risk_id})


@governance_bp.route("/risks/<int:risk_id>/actions", methods=["GET"])
@_token_required
def list_actions_route(risk_id: int):
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    if data.get_risk(risk_id) is None:
        return jsonify({"error": f"No risk #{risk_id}"}), 404
    rows = data.list_actions(
        risk_id=risk_id,
        status=request.args.get("status"),
        open_only=_truthy(request.args.get("open_only")),
        overdue_only=_truthy(request.args.get("overdue_only")),
    )
    return jsonify({"actions": _dump(rows), "count": len(rows)})


@governance_bp.route("/risks/<int:risk_id>/actions", methods=["POST"])
@_token_required
def add_action_route(risk_id: int):
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    try:
        a = data.add_action(risk_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(a)), 201


@governance_bp.route("/risks/<int:risk_id>/reviews", methods=["GET"])
@_token_required
def list_reviews_route(risk_id: int):
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    if data.get_risk(risk_id) is None:
        return jsonify({"error": f"No risk #{risk_id}"}), 404
    rows = data.list_reviews(risk_id=risk_id)
    return jsonify({"reviews": _dump(rows), "count": len(rows)})


@governance_bp.route("/risks/<int:risk_id>/reviews", methods=["POST"])
@_token_required
def add_review_route(risk_id: int):
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    try:
        rv = data.add_review(risk_id, request.get_json(silent=True) or {})
    except data.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(rv)), 201


@governance_bp.route("/risks/overview", methods=["GET"])
@_token_required
def risks_overview_route():
    from education_system.sixthform_system.modules.domain.governance.risk_management import (  # noqa: E501
        risk_management as data,
    )
    return jsonify(_dump(data.overview()))

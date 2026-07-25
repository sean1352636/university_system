"""REST API for the Sixth Form System.

A self-contained Flask app exposing read endpoints over the domain data
plus the parent-portal session flow. It deliberately stays independent
of the big shared ``unified_server`` so it can be run on its own:

    python -m education_system.systems.sixth_form.interfaces.api.server
    # or
    from education_system.systems.sixth_form.interfaces.api.server import create_app
    app = create_app()

Two auth surfaces:

* **Parent** — ``POST /api/parent/login`` returns a signed token
  (see :mod:`.tokens`); ``Authorization: Bearer <token>`` then unlocks
  ``/api/parent/*`` and limits access to the caller's own children.
* **Staff** — analytics / workflow / automation endpoints require an
  ``X-API-Key`` header matching ``EDU_SIXTHFORM_API_KEY``. If that env
  var is unset the key check is skipped (dev convenience) and a warning
  is logged.

All routes return JSON. Errors use conventional status codes
(400/401/403/404) with an ``{"error": "..."}`` body.
"""

from __future__ import annotations

import logging
import os
from functools import wraps

from flask import Flask, g, jsonify, request

from education_system.systems.sixth_form import SYSTEM_NAME
from education_system.systems.sixth_form.interfaces.api import tokens
from education_system.systems.sixth_form.domain.assessment.risk_analytics import (
    risk_analytics,
)
from education_system.systems.sixth_form.domain.governance.automation_rules import (
    automation_rules,
)
from education_system.systems.sixth_form.domain.progression.ucas_workflow import (
    ucas_workflow,
)
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    parent_portal,
)

logger = logging.getLogger(__name__)

API_PREFIX = "/api"


# ── Auth decorators ──────────────────────────────────────────────────

def _bearer_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def parent_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        account_id = tokens.verify(token) if token else None
        if account_id is None:
            return jsonify({"error": "Invalid or missing parent token"}), 401
        g.account_id = account_id
        return fn(*args, **kwargs)
    return wrapper


def staff_key_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.environ.get("EDU_SIXTHFORM_API_KEY")
        if not expected:
            logger.warning("EDU_SIXTHFORM_API_KEY unset — staff endpoint open in dev mode")
            return fn(*args, **kwargs)
        if request.headers.get("X-API-Key") != expected:
            return jsonify({"error": "Invalid or missing API key"}), 401
        return fn(*args, **kwargs)
    return wrapper


# ── App factory ──────────────────────────────────────────────────────

def create_app() -> Flask:
    app = Flask(__name__)

    @app.get(f"{API_PREFIX}/health")
    def health():
        return jsonify({"status": "ok", "system": SYSTEM_NAME})

    # ── Parent portal ────────────────────────────────────────────────
    @app.post(f"{API_PREFIX}/parent/login")
    def parent_login():
        body = request.get_json(silent=True) or {}
        account = parent_portal.authenticate(
            body.get("username", ""), body.get("password", ""))
        if not account:
            return jsonify({"error": "Invalid credentials"}), 401
        return jsonify({
            "token": tokens.issue(account.account_id),
            "account": {"username": account.username, "full_name": account.full_name},
        })

    @app.get(f"{API_PREFIX}/parent/me")
    @parent_required
    def parent_me():
        return jsonify(parent_portal.account_dashboard(g.account_id))

    @app.get(f"{API_PREFIX}/parent/children")
    @parent_required
    def parent_children():
        return jsonify({"children": parent_portal.linked_students(g.account_id)})

    @app.get(f"{API_PREFIX}/parent/children/<student_id>")
    @parent_required
    def parent_child(student_id: str):
        allowed = {c["student_id"] for c in parent_portal.linked_students(g.account_id)}
        if student_id not in allowed:
            return jsonify({"error": "Not authorised for this student"}), 403
        return jsonify(parent_portal.student_snapshot(student_id))

    # ── Staff: risk analytics ────────────────────────────────────────
    @app.get(f"{API_PREFIX}/risk/summary")
    @staff_key_required
    def risk_summary():
        return jsonify(risk_analytics.summary())

    @app.get(f"{API_PREFIX}/risk/register")
    @staff_key_required
    def risk_register():
        band = request.args.get("band")
        return jsonify({"register": risk_analytics.latest_snapshots(band=band)})

    @app.post(f"{API_PREFIX}/risk/scan")
    @staff_key_required
    def risk_scan():
        results = risk_analytics.scan_all()
        return jsonify({"scanned": len(results), "summary": risk_analytics.summary()})

    @app.get(f"{API_PREFIX}/risk/student/<student_id>")
    @staff_key_required
    def risk_student(student_id: str):
        try:
            a = risk_analytics.assess_student(student_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        return jsonify({
            "student_id": a.student_id, "full_name": a.full_name,
            "score": a.score, "band": a.band, "attendance_pct": a.attendance_pct,
            "behaviour_points": a.behaviour_points,
            "factors": [f.__dict__ for f in a.factors],
            "predictions": [p.__dict__ for p in a.predictions],
        })

    # ── Staff: UCAS workflow ─────────────────────────────────────────
    @app.get(f"{API_PREFIX}/ucas/overview")
    @staff_key_required
    def ucas_overview():
        year = request.args.get("cycle_year", type=int)
        return jsonify({"cohort": ucas_workflow.overview(year)})

    @app.get(f"{API_PREFIX}/ucas/student/<student_id>")
    @staff_key_required
    def ucas_student(student_id: str):
        year = request.args.get("cycle_year", type=int)
        try:
            return jsonify(ucas_workflow.get_pipeline(student_id, year))
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

    # ── Staff: automation ────────────────────────────────────────────
    @app.get(f"{API_PREFIX}/automation/actions")
    @staff_key_required
    def automation_actions():
        status = request.args.get("status", "Open")
        return jsonify({"actions": automation_rules.list_actions(status=status)})

    @app.post(f"{API_PREFIX}/automation/run")
    @staff_key_required
    def automation_run():
        return jsonify(automation_rules.run_rules())

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Not found"}), 404

    logger.info("Sixth Form REST API initialised")
    return app


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    app = create_app()
    port = int(os.environ.get("EDU_SIXTHFORM_API_PORT", "5005"))
    host = os.environ.get("EDU_SIXTHFORM_API_HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=os.environ.get("FLASK_DEBUG") == "1")


if __name__ == "__main__":
    main()

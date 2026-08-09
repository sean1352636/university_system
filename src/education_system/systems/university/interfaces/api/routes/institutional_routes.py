"""Shared-auth HTTP adapters for institutional university workflows."""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.auth import role_required
from education_system.systems.university.application import (
    case_management,
    connectors,
    timetabling,
)
# Learner-record operations moved to the Learners slice.
from education_system.systems.university.domains.learners.application import identity_management
from education_system.systems.university.domain.academics.programme_governance import (
    service as programmes,
)
from education_system.systems.university.domain.academics.research.pgr import (
    service as pgr,
)
from education_system.systems.university.infrastructure.database.db import get_connection

institutional_bp = Blueprint(
    "institutional_workflows",
    __name__,
    url_prefix="/api/institutional",
)

staff_required = role_required("admin", "staff")


def _body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required")
    return data


def _actor() -> str:
    return str(g.current_user.get("username") or g.current_user.get("user_id"))


def _error(exc: Exception):
    status = 404 if "does not exist" in str(exc).lower() else 400
    return jsonify({"error": str(exc)}), status


@institutional_bp.get("/cases")
@staff_required
def list_cases():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM institutional_cases ORDER BY opened_at DESC LIMIT 200"
        ).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@institutional_bp.post("/cases")
@staff_required
def create_case():
    try:
        data = _body()
        case_id = case_management.open_case(
            str(data.get("case_type", "")).strip().lower().replace(" ", "_"),
            str(data.get("subject_id", "")).strip(),
            str(data.get("summary", "")).strip(),
            opened_by=_actor(),
            owner_id=str(data.get("owner_id") or "").strip() or None,
        )
        return jsonify({"case_id": case_id, "record": case_management.case_record(case_id)}), 201
    except (ValueError, TypeError) as exc:
        return _error(exc)


@institutional_bp.post("/identity")
@staff_required
def change_identity():
    try:
        data = _body()
        action = data.get("action")
        approved_by = str(data.get("approved_by", "")).strip()
        reason = str(data.get("reason", "")).strip()
        actor = _actor()
        if action == "correction":
            change_id = identity_management.correct_identity(
                str(data.get("student_id", "")),
                dict(data.get("changes") or {}),
                reason=reason,
                requested_by=actor,
                approved_by=approved_by,
            )
            return jsonify({"change_id": change_id}), 201
        if action == "merge":
            merge_id = identity_management.merge_students(
                str(data.get("student_id", "")),
                str(data.get("secondary_id", "")),
                reason=reason,
                requested_by=actor,
                approved_by=approved_by,
            )
            return jsonify({"merge_id": merge_id}), 201
        if action == "reverse":
            identity_management.reverse_merge(
                str(data.get("secondary_id", "")),
                reversed_by=actor,
                reason=reason,
            )
            return jsonify({"reversed": True})
        raise ValueError("Unsupported identity action")
    except (ValueError, TypeError) as exc:
        return _error(exc)


@institutional_bp.get("/connectors")
@staff_required
def list_connectors():
    with get_connection() as conn:
        configured = {
            row["connector_name"]: dict(row)
            for row in conn.execute("SELECT * FROM connector_configurations").fetchall()
        }
    items = []
    for name in sorted(connectors.SUPPORTED_CONNECTORS):
        items.append(configured.get(name) or {
            "connector_name": name,
            "enabled": 0,
            "status": "unconfigured",
            "last_checked_at": None,
            "last_error": None,
        })
    return jsonify({"items": items})


@institutional_bp.put("/connectors/<name>")
@staff_required
def configure_connector(name: str):
    try:
        data = _body()
        connectors.configure(
            name,
            dict(data.get("config") or {}),
            enabled=bool(data.get("enabled", True)),
        )
        return jsonify({"connector_name": name, "configured": True})
    except (ValueError, TypeError) as exc:
        return _error(exc)


@institutional_bp.get("/timetables")
@staff_required
def list_timetables():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT version_id, academic_year, status, created_by, created_at, "
            "published_at FROM timetable_versions ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return jsonify({
        "items": [dict(row) for row in rows],
        "published_schedule": timetabling.published_schedule(),
    })


@institutional_bp.post("/timetables")
@staff_required
def create_timetable():
    try:
        data = _body()
        version_id = timetabling.optimise(
            list(data.get("activities") or []),
            list(data.get("slots") or []),
            list(data.get("rooms") or []),
            academic_year=str(data.get("academic_year", "")),
            created_by=_actor(),
        )
        return jsonify({"version_id": version_id}), 201
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _error(exc)


@institutional_bp.post("/timetables/<version_id>/publish")
@staff_required
def publish_timetable(version_id: str):
    try:
        timetabling.publish(version_id, approved_by=_actor())
        return jsonify({"published": True, "version_id": version_id})
    except ValueError as exc:
        return _error(exc)


@institutional_bp.get("/pgr")
@staff_required
def list_pgr_projects():
    pgr.ensure_schema()
    term = request.args.get("q", "").strip()
    with get_connection() as conn:
        if term:
            rows = conn.execute(
                "SELECT * FROM pgr_projects WHERE CAST(project_id AS TEXT)=? "
                "OR student_id=? ORDER BY project_id DESC",
                (term, term),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pgr_projects ORDER BY project_id DESC LIMIT 100"
            ).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@institutional_bp.get("/pgr/<int:project_id>")
@staff_required
def get_pgr_project(project_id: int):
    try:
        return jsonify(pgr.project_record(project_id))
    except ValueError as exc:
        return _error(exc)


@institutional_bp.post("/pgr")
@staff_required
def create_pgr_project():
    try:
        data = _body()
        project_id = pgr.create_project(
            str(data.get("student_id", "")).strip(),
            str(data.get("proposal_title", "")).strip(),
            str(data.get("abstract", "")).strip(),
            created_by=_actor(),
            department=str(data.get("department", "")).strip(),
            route=str(data.get("route", "MPhil/PhD")).strip(),
            start_date=data.get("start_date") or None,
            expected_end_date=data.get("expected_end_date") or None,
        )
        return jsonify({"project_id": project_id}), 201
    except (ValueError, TypeError) as exc:
        return _error(exc)


@institutional_bp.get("/programmes")
@staff_required
def list_programmes():
    programmes.ensure_schema()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM governed_programmes ORDER BY programme_id DESC LIMIT 100"
        ).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@institutional_bp.post("/programmes")
@staff_required
def create_programme():
    try:
        data = _body()
        programme_id, proposal_id = programmes.create_proposal(
            str(data.get("programme_code", "")).strip(),
            str(data.get("programme_name", "")).strip(),
            str(data.get("award_type", "")).strip(),
            str(data.get("proposed_start_year", "")).strip(),
            created_by=_actor(),
            rationale=str(data.get("rationale", "")).strip(),
            owning_school=str(data.get("owning_school", "")).strip(),
        )
        return jsonify({
            "programme_id": programme_id,
            "proposal_id": proposal_id,
        }), 201
    except (ValueError, TypeError) as exc:
        return _error(exc)


__all__ = ["institutional_bp"]

"""REST API for sixth form onboarding.

* GET  /api/onboarding/checklists                      — list (filters: academic_year, status, open_only, student_id, archived)
* GET  /api/onboarding/checklists/<id>                 — checklist + tasks
* GET  /api/onboarding/checklists/<id>/history         — audit trail
* GET  /api/onboarding/checklists/<id>/consents        — consent tasks and their GDPR state
* POST /api/onboarding/checklists/<id>/resync          — tick tasks whose record now exists
* POST /api/onboarding/items/<id>/status               — {status, evidence?, reason?}
* POST /api/onboarding/items/<id>/confirm              — second check {note?}
* POST /api/onboarding/items/<id>/consent              — {granted, given_by?, expires_date?, notes?}
* GET  /api/onboarding/students/<student_id>/checklist — the learner's own view (students may read their own)
* GET  /api/onboarding/reports/<kind>                  — outstanding | tutor_group | course | year_group (?format=csv)
* GET  /api/onboarding/sessions                        — induction sessions
* GET  /api/onboarding/sessions/<id>/register          — a session's register

Auth: the token (platform ``token_required``) then :func:`access_gate.gate`,
which binds the sixth form principal so the onboarding domain applies its
own write rule (``admissions`` or ``students.manage``) and masks sensitive
tasks for readers without the rights.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, Response, g, jsonify, request

from education_system.api.sixth_form import access_gate

logger = logging.getLogger(__name__)

onboarding_bp = Blueprint("sf_onboarding", __name__,
                          url_prefix="/api/onboarding")


def _token_required(view):
    view = _errors(access_gate.gate(view))
    try:
        from education_system.platform.delivery.api.auth import token_required
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


def _errors(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        try:
            return view(*args, **kwargs)
        except access.AccessDenied as e:
            return jsonify({"error": str(e), "status": 403}), 403
        except ValueError as e:          # every domain ValidationError
            return jsonify({"error": str(e), "status": 400}), 400
    return wrapper


def _ob():
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding,
    )
    return onboarding


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _flag(name: str) -> bool:
    return (request.args.get(name) or "").lower() in ("1", "true", "yes")


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── Checklists ──────────────────────────────────────────────────────

@onboarding_bp.route("/checklists", methods=["GET"])
@_token_required
def list_checklists_route():
    ob = _ob()
    rows = ob.list_checklists_with_detail(
        academic_year=request.args.get("academic_year") or None,
        status=request.args.get("status") or None,
        open_only=_flag("open_only"),
        student_id=request.args.get("student_id") or None,
        archived_only=_flag("archived"))
    return jsonify({"checklists": [
        {**_dump(r.checklist), "student_name": r.student_name,
         "total": r.total, "done": r.done,
         "required_total": r.required_total,
         "required_done": r.required_done} for r in rows],
        "count": len(rows)})


@onboarding_bp.route("/checklists/<int:checklist_id>", methods=["GET"])
@_token_required
def checklist_route(checklist_id: int):
    ob = _ob()
    d = ob.get_checklist_detail(checklist_id)
    if d is None:
        return jsonify({"error": f"No checklist #{checklist_id}"}), 404
    return jsonify({"checklist": _dump(d.checklist),
                    "student_name": d.student_name,
                    "percent_complete": d.percent_complete,
                    "required_complete": d.required_complete,
                    "items": _dump(d.items)})


@onboarding_bp.route("/checklists/<int:checklist_id>/history",
                     methods=["GET"])
@_token_required
def history_route(checklist_id: int):
    ob = _ob()
    rows = ob.history(checklist_id=checklist_id)
    if not ob._can_see_sensitive():
        hidden = {i.item_id for i in ob.list_items(checklist_id=checklist_id)
                  if i.sensitive}
        rows = [r for r in rows if r.get("item_id") not in hidden]
    return jsonify({"history": rows, "count": len(rows)})


@onboarding_bp.route("/checklists/<int:checklist_id>/consents",
                     methods=["GET"])
@_token_required
def consents_route(checklist_id: int):
    links = _ob().consent_links(checklist_id)
    return jsonify({"consents": [
        {"item_id": lk.item.item_id, "task": lk.item.task_name,
         "purpose": lk.purpose, "consent_id": lk.consent_id,
         "state": lk.state, "detail": lk.detail} for lk in links]})


@onboarding_bp.route("/checklists/<int:checklist_id>/resync",
                     methods=["POST"])
@_token_required
def resync_route(checklist_id: int):
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        evidence_sources,
    )
    r = evidence_sources.resync(checklist_id)
    return jsonify({"summary": r.summary, "ticked": r.ticked,
                    "reopened": r.reopened, "errors": r.errors})


# ── Items ───────────────────────────────────────────────────────────

@onboarding_bp.route("/items/<int:item_id>/status", methods=["POST"])
@_token_required
def item_status_route(item_id: int):
    body = _body()
    status = (body.get("status") or "").strip()
    if not status:
        return jsonify({"error": "status is required"}), 400
    item = _ob().set_item_status(item_id, status,
                                 evidence=body.get("evidence"),
                                 reason=body.get("reason"))
    return jsonify(_dump(item))


@onboarding_bp.route("/items/<int:item_id>/confirm", methods=["POST"])
@_token_required
def item_confirm_route(item_id: int):
    item = _ob().confirm_evidence(item_id, note=_body().get("note"))
    return jsonify(_dump(item))


@onboarding_bp.route("/items/<int:item_id>/consent", methods=["POST"])
@_token_required
def item_consent_route(item_id: int):
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        consent_followups,
    )
    body = _body()
    if "granted" not in body:
        return jsonify({"error": "granted (true/false) is required"}), 400
    link = _ob().record_consent(
        item_id, granted=bool(body["granted"]),
        given_by=body.get("given_by"),
        expires_date=body.get("expires_date"), notes=body.get("notes"))
    follow = consent_followups.after_consent(link)
    return jsonify({"item_id": link.item.item_id, "state": link.state,
                    "consent_id": link.consent_id,
                    "follow_up_item_id": follow.item_id if follow else None})


# ── The learner's own view ──────────────────────────────────────────

@onboarding_bp.route("/students/<student_id>/checklist", methods=["GET"])
@_token_required
def student_checklist_route(student_id: str):
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding_portal,
    )
    view = onboarding_portal.learner_checklist(student_id)
    if view is None:
        return jsonify({"error": "No onboarding checklist"}), 404
    return jsonify(view)


# ── Reports ─────────────────────────────────────────────────────────

@onboarding_bp.route("/reports/<kind>", methods=["GET"])
@_token_required
def report_route(kind: str):
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        onboarding_reports as rep,
    )
    year = request.args.get("academic_year") or None
    if request.args.get("format") == "csv":
        text = rep.export_csv(kind, academic_year=year)
        return Response(text, mimetype="text/csv", headers={
            "Content-Disposition":
                f"attachment; filename=onboarding_{kind}.csv"})
    if kind == "outstanding":
        rows = rep.outstanding_tasks(academic_year=year,
                                     overdue_only=_flag("overdue_only"))
        return jsonify({"tasks": _dump(rows), "count": len(rows)})
    rows = rep.dashboard(kind, academic_year=year)
    return jsonify({"rows": [r.as_dict() for r in rows]})


# ── Induction sessions ──────────────────────────────────────────────

@onboarding_bp.route("/sessions", methods=["GET"])
@_token_required
def sessions_route():
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        induction,
    )
    rows = induction.list_sessions(
        academic_year=request.args.get("academic_year") or None,
        upcoming_only=_flag("upcoming"))
    return jsonify({"sessions": _dump(rows), "count": len(rows)})


@onboarding_bp.route("/sessions/<int:session_id>/register", methods=["GET"])
@_token_required
def session_register_route(session_id: int):
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        induction,
    )
    if induction.get_session(session_id) is None:
        return jsonify({"error": f"No session #{session_id}"}), 404
    return jsonify({"register": _dump(induction.register(session_id))})

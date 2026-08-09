"""Flask blueprint exposing External-QA read endpoints.

Register on the unified server with::

    from .qa_routes import bp as qa_bp
    app.register_blueprint(qa_bp, url_prefix="/api/eqa")

All endpoints are read-only and return JSON. Mutating endpoints are
intentionally omitted — write operations remain CLI/GUI-only and pass
through the audit hooks in ``qa_service``.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from education_system.systems.university.domain.academics.research.external_quality_assurance.services import (
    qa_service as qa,
)
from education_system.systems.university.domain.academics.research.external_quality_assurance.services.qa_integrations import (
    aggregate_qa_across_systems,
)

bp = Blueprint("eqa", __name__)


@bp.get("/summary")
def summary():
    return jsonify(qa.get_qa_summary_dict())


@bp.get("/summary/cross-system")
def summary_cross_system():
    return jsonify(aggregate_qa_across_systems())


@bp.get("/submissions")
def submissions():
    framework = request.args.get("framework")
    return jsonify(qa.list_submissions(framework=framework))


@bp.get("/b3/<int:cohort_year>")
def b3(cohort_year: int):
    course = request.args.get("course")
    return jsonify({
        "computed": qa.compute_b3_metrics(cohort_year, course=course),
        "snapshots": qa.list_b3_snapshots(cohort_year=cohort_year),
    })


@bp.get("/app-milestones")
def app_milestones():
    plan_year = request.args.get("plan_year", type=int)
    return jsonify(qa.list_app_milestones(plan_year=plan_year))


@bp.get("/tef/<int:year>")
def tef(year: int):
    return jsonify({
        "narratives": qa.list_tef_narratives(submission_year=year),
        "indicators": qa.compute_tef_indicators(year),
    })


@bp.get("/ref/<uoa>")
def ref(uoa: str):
    return jsonify({
        "summary": qa.compute_uoa_summary(uoa),
        "impact_cases": qa.list_impact_cases(uoa=uoa),
        "environment_statements": qa.list_environment_statements(uoa=uoa),
    })


@bp.get("/kpis")
def kpis():
    return jsonify(qa.compute_external_qa_kpis())

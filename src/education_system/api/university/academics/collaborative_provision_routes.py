"""Collaborative (partner) provision routes: partners, agreements, programmes, reviews."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from education_system.platform.delivery.api.university.auth import (
    is_staff,
    staff_required,
    token_required,
)
from education_system.systems.university.domains.curriculum.domain.collaborative_provision._db_init import (
    AGREEMENT_STATUSES,
    DELIVERY_MODELS,
    PARTNER_TYPES,
    REVIEW_OUTCOMES,
    REVIEW_TYPES,
    RISK_LEVELS,
)
from education_system.systems.university.domains.curriculum.domain.collaborative_provision.services.collaborative_provision_service import (
    CollaborativeProvisionService,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

collaborative_provision_bp = Blueprint(
    "collaborative_provision", __name__, url_prefix="/api/collaborative-provision")


#: Partner contracts, reviews, cohorts and risk ratings are staff-internal:
#: any staff role may read them. Changing them needs ``manage_courses``
#: (admin, staff) - instructors and learners cannot.
COLLAB_MANAGE = "manage_courses"

#: Partner fields a non-staff caller may see. The partner list is reference
#: information; contacts, due diligence, risk and notes are not.
_PUBLIC_PARTNER_FIELDS = ("partner_id", "name", "partner_type", "country",
                          "city", "website")


def _service() -> CollaborativeProvisionService:
    return CollaborativeProvisionService()


def _payload() -> dict:
    return request.get_json(silent=True) or {}


@collaborative_provision_bp.route("/vocabulary", methods=["GET"])
@token_required
def vocabulary():
    return jsonify({
        "delivery_models": list(DELIVERY_MODELS),
        "partner_types": list(PARTNER_TYPES),
        "agreement_statuses": list(AGREEMENT_STATUSES),
        "risk_levels": list(RISK_LEVELS),
        "review_types": list(REVIEW_TYPES),
        "review_outcomes": list(REVIEW_OUTCOMES),
    })


@collaborative_provision_bp.route("/summary", methods=["GET"])
@token_required
@staff_required
def summary():
    return jsonify(_service().summary())


# ---- partners ----

@collaborative_provision_bp.route("/partners", methods=["GET"])
@token_required
def list_partners():
    items = _service().list_partners(
        active_only=request.args.get("active", "1") != "0",
        country=request.args.get("country"),
        search=request.args.get("search"))
    if not is_staff():
        items = [{k: p.get(k) for k in _PUBLIC_PARTNER_FIELDS} for p in items]
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/partners", methods=["POST"])
@token_required
@staff_required(permission=COLLAB_MANAGE)
def create_partner():
    data = _payload()
    if not (data.get("name") or "").strip():
        return jsonify({"error": "name is required"}), 400
    try:
        partner_id = _service().add_partner(**{
            k: data.get(k) for k in (
                "name", "partner_type", "country", "city", "ukprn", "website",
                "contact_name", "contact_email", "contact_phone",
                "due_diligence_date", "due_diligence_due", "notes")
            if k in data
        }, risk_level=data.get("risk_level", "Medium"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    log_activity("partner_created", entity_type="partner_institution",
                 partner_id=partner_id)
    return jsonify({"partner_id": partner_id}), 201


@collaborative_provision_bp.route("/partners/<int:partner_id>", methods=["GET"])
@token_required
@staff_required
def get_partner(partner_id: int):
    partner = _service().get_partner(partner_id)
    if partner is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(partner)


@collaborative_provision_bp.route("/partners/<int:partner_id>", methods=["PATCH"])
@token_required
@staff_required(permission=COLLAB_MANAGE)
def update_partner(partner_id: int):
    if not _service().update_partner(partner_id, **_payload()):
        return jsonify({"error": "no updatable fields supplied"}), 400
    return jsonify({"updated": True})


# ---- agreements ----

@collaborative_provision_bp.route("/agreements", methods=["GET"])
@token_required
@staff_required
def list_agreements():
    items = _service().list_agreements(
        partner_id=request.args.get("partner_id", type=int),
        status=request.args.get("status"),
        delivery_model=request.args.get("delivery_model"))
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/agreements", methods=["POST"])
@token_required
@staff_required(permission=COLLAB_MANAGE)
def create_agreement():
    data = _payload()
    if not data.get("partner_id") or not data.get("delivery_model"):
        return jsonify({"error": "partner_id and delivery_model are required"}), 400
    try:
        agreement_id = _service().add_agreement(
            data["partner_id"], data["delivery_model"],
            **{k: data[k] for k in (
                "reference", "status", "start_date", "end_date", "review_due",
                "max_students", "fee_share_pct", "signed_by", "signed_date",
                "contract_ref", "notes") if k in data})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    log_activity("partner_agreement_created", entity_type="partnership_agreement",
                 agreement_id=agreement_id)
    return jsonify({"agreement_id": agreement_id}), 201


@collaborative_provision_bp.route("/agreements/<int:agreement_id>", methods=["GET"])
@token_required
@staff_required
def get_agreement(agreement_id: int):
    agreement = _service().get_agreement(agreement_id)
    if agreement is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(agreement)


@collaborative_provision_bp.route("/agreements/<int:agreement_id>", methods=["PATCH"])
@token_required
@staff_required(permission=COLLAB_MANAGE)
def update_agreement(agreement_id: int):
    try:
        updated = _service().update_agreement(agreement_id, **_payload())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not updated:
        return jsonify({"error": "no updatable fields supplied"}), 400
    return jsonify({"updated": True})


# ---- programmes and cohorts ----

@collaborative_provision_bp.route("/programmes", methods=["GET"])
@token_required
@staff_required
def list_programmes():
    items = _service().list_programmes(
        agreement_id=request.args.get("agreement_id", type=int),
        programme_code=request.args.get("programme_code"))
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/programmes", methods=["POST"])
@token_required
@staff_required(permission=COLLAB_MANAGE)
def create_programme():
    data = _payload()
    if not data.get("agreement_id") or not data.get("programme_title"):
        return jsonify({"error": "agreement_id and programme_title are required"}), 400
    try:
        programme_id = _service().add_programme(
            data["agreement_id"], data["programme_title"],
            **{k: data[k] for k in (
                "programme_code", "award", "level", "credits", "language",
                "delivery_site", "link_tutor", "external_examiner",
                "first_intake", "final_intake", "status") if k in data})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"collab_programme_id": programme_id}), 201


@collaborative_provision_bp.route("/programmes/unlinked", methods=["GET"])
@token_required
@staff_required
def unlinked_programmes():
    items = _service().unlinked_programmes()
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/cohorts", methods=["GET"])
@token_required
@staff_required
def list_cohorts():
    items = _service().list_cohorts(
        collab_programme_id=request.args.get("collab_programme_id", type=int),
        academic_year=request.args.get("academic_year"))
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/cohorts", methods=["POST"])
@token_required
@staff_required(permission=COLLAB_MANAGE)
def create_cohort():
    data = _payload()
    if not data.get("collab_programme_id") or not data.get("academic_year"):
        return jsonify(
            {"error": "collab_programme_id and academic_year are required"}), 400
    cohort_id = _service().add_cohort(
        data["collab_programme_id"], data["academic_year"],
        **{k: data[k] for k in (
            "intake_month", "planned_headcount", "actual_headcount",
            "registered_headcount", "completed_headcount", "notes") if k in data})
    return jsonify({"cohort_id": cohort_id}), 201


@collaborative_provision_bp.route("/cohorts/<int:cohort_id>", methods=["PATCH"])
@token_required
@staff_required(permission=COLLAB_MANAGE)
def update_cohort(cohort_id: int):
    if not _service().update_cohort(cohort_id, **_payload()):
        return jsonify({"error": "no updatable fields supplied"}), 400
    return jsonify({"updated": True})


# ---- reviews and monitoring ----

@collaborative_provision_bp.route("/reviews", methods=["GET"])
@token_required
@staff_required
def list_reviews():
    items = _service().list_reviews(
        partner_id=request.args.get("partner_id", type=int))
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/reviews", methods=["POST"])
@token_required
@staff_required(permission=COLLAB_MANAGE)
def create_review():
    data = _payload()
    required = ("partner_id", "review_type", "review_date")
    if any(not data.get(k) for k in required):
        return jsonify({"error": f"{', '.join(required)} are required"}), 400
    review_id = _service().add_review(
        data["partner_id"], data["review_type"], data["review_date"],
        **{k: data[k] for k in (
            "agreement_id", "reviewer", "outcome", "findings", "conditions",
            "next_review_due") if k in data})
    log_activity("partner_review_recorded", entity_type="partner_review",
                 review_id=review_id)
    return jsonify({"review_id": review_id}), 201


@collaborative_provision_bp.route("/monitoring/overdue-reviews", methods=["GET"])
@token_required
@staff_required
def overdue_reviews():
    items = _service().overdue_reviews(as_of=request.args.get("as_of"))
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/monitoring/expiring", methods=["GET"])
@token_required
@staff_required
def expiring_agreements():
    items = _service().expiring_agreements(
        within_days=request.args.get("within_days", default=180, type=int))
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/monitoring/over-recruited", methods=["GET"])
@token_required
@staff_required
def over_recruited():
    items = _service().over_recruited()
    return jsonify({"items": items, "total": len(items)})


@collaborative_provision_bp.route("/provision-map", methods=["GET"])
@token_required
@staff_required
def provision_map():
    items = _service().provision_map()
    return jsonify({"items": items, "total": len(items)})

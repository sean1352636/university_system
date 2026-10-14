"""University-side UCAS routes.

The sixth form has exposed full UCAS CRUD over HTTP for as long as the
feature has existed. The university's half — the applicant list, the
decision, the links, the internal notes, the offer terms, results day —
was reachable only from a Tkinter window and a CLI menu. Anything that is
not a member of staff sitting at the desktop app could read a sixth form's
UCAS data and could not read, let alone record, this university's response
to it.

These routes close that. They are deliberately a thin skin over the domain
modules: every rule — who may write a decision, what a conditional offer
must carry, what results day will and will not confirm on its own — lives
in the domain and is the same whether it is reached from here, the GUI or
the CLI.

Everything is admin-only. An admissions decision is not a read a student
should be making against their own record, and there is no applicant-facing
half of this API to get wrong.

Mounted at ``/api/admissions/ucas``.
"""

from __future__ import annotations

import dataclasses
import logging

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import (
    admin_required,
    token_required,
)
from education_system.systems.university.domains.admissions.domain.ucas import (
    applicants as applicants_mod,
    clearing_link,
    decision_log,
    offer_terms as offer_terms_mod,
    results_day,
    ucas as ucas_mod,
    ucas_links,
)

logger = logging.getLogger(__name__)

ucas_bp = Blueprint("admissions_ucas", __name__,
                    url_prefix="/api/admissions/ucas")


def _dump(obj):
    """Serialise a domain dataclass (or a list of them) to JSON-safe data."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dump(v) for k, v in dataclasses.asdict(obj).items()}
    return obj


def _actor() -> str | None:
    """The signed-in officer, for attribution on anything that writes."""
    user = g.get("current_user") or {}
    return user.get("username") or user.get("sub") or None


def _int_arg(name: str) -> int | None:
    raw = request.args.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── Applicants ─────────────────────────────────────────────────────

@ucas_bp.route("/applicants", methods=["GET"])
@token_required
@admin_required
def list_applicants():
    """UCAS choices naming this university."""
    try:
        rows = ucas_mod.list_applicants(
            university_name=request.args.get("university_name"),
            decision_status=request.args.get("decision_status"),
            app_status=request.args.get("app_status"),
            cycle_year=_int_arg("cycle_year"),
            search=request.args.get("search"),
        )
    except ucas_mod.UcasError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "total": len(rows)})


@ucas_bp.route("/applicants/all", methods=["GET"])
@token_required
@admin_required
def list_all_applicants():
    """Every applicant from every system that sends any — UCAS choices
    merged with cross-system handovers, deduplicated."""
    rows = applicants_mod.list_all_applicants(
        university_name=request.args.get("university_name"),
        source_system=request.args.get("source_system"),
    )
    return jsonify({
        "items": _dump(rows),
        "total": len(rows),
        "sources": applicants_mod.sources_seen(rows),
    })


@ucas_bp.route("/applications/<int:application_id>", methods=["GET"])
@token_required
@admin_required
def get_application(application_id: int):
    """The parent application plus every choice on it."""
    try:
        full = ucas_mod.get_full_application(application_id)
    except ucas_mod.UcasError as e:
        return jsonify({"error": str(e)}), 400
    if full is None:
        return jsonify({"error": f"No application {application_id}"}), 404
    return jsonify(_dump(full))


@ucas_bp.route("/summary", methods=["GET"])
@token_required
@admin_required
def summary():
    try:
        return jsonify(_dump(ucas_mod.summary(
            university_name=request.args.get("university_name"))))
    except ucas_mod.UcasError as e:
        return jsonify({"error": str(e)}), 400


# ── Decisions ──────────────────────────────────────────────────────

@ucas_bp.route("/choices/<int:choice_id>/decision", methods=["POST"])
@token_required
@admin_required
def record_decision(choice_id: int):
    """Record this university's decision on a UCAS choice.

    ``terms`` carries the structured offer terms (reply deadline, expiry,
    scholarship, guaranteed accommodation, alternative pathway); the
    attribution comes from the token, not the body, so a caller cannot
    record a decision under somebody else's name.
    """
    body = _body()
    decision = (body.get("decision_status") or "").strip()
    if not decision:
        return jsonify({"error": "decision_status is required"}), 400
    try:
        out = ucas_mod.record_decision(
            choice_id,
            decision,
            offer_terms=body.get("offer_terms"),
            notes=body.get("notes"),
            terms=body.get("terms"),
            issued_by=_actor(),
        )
    except ucas_mod.UcasError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(out))


@ucas_bp.route("/choices/<int:choice_id>/decisions", methods=["GET"])
@token_required
@admin_required
def decision_history(choice_id: int):
    """Every decision ever recorded against a choice, oldest first."""
    return jsonify({"items": _dump(decision_log.history_for_choice(choice_id))})


@ucas_bp.route("/decisions", methods=["GET"])
@token_required
@admin_required
def recent_decisions():
    """What has gone out lately, and who sent it."""
    rows = decision_log.list_decisions(
        decided_by=request.args.get("decided_by"),
        since=request.args.get("since"),
        decision_status=request.args.get("decision_status"),
        limit=_int_arg("limit") or 500,
    )
    return jsonify({"items": _dump(rows), "total": len(rows)})


# ── Offer terms ────────────────────────────────────────────────────

@ucas_bp.route("/choices/<int:choice_id>/terms", methods=["GET"])
@token_required
@admin_required
def get_offer_terms(choice_id: int):
    issued = offer_terms_mod.get_terms(choice_id)
    if issued is None:
        return jsonify({"error": f"No terms issued for choice {choice_id}"}), 404
    return jsonify(_dump(issued))


@ucas_bp.route("/choices/<int:choice_id>/terms", methods=["PUT"])
@token_required
@admin_required
def put_offer_terms(choice_id: int):
    """Revise the terms on an offer already made."""
    try:
        out = offer_terms_mod.save_terms(choice_id, _body(),
                                         issued_by=_actor())
    except offer_terms_mod.OfferTermsError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(out))


# ── Links and internal notes ───────────────────────────────────────

@ucas_bp.route("/links", methods=["GET"])
@token_required
@admin_required
def list_links():
    try:
        rows = ucas_links.list_links(
            sf_student_id=request.args.get("sf_student_id"),
            sf_application_id=_int_arg("sf_application_id"),
            status=request.args.get("status"),
        )
    except ucas_links.UcasLinkError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": _dump(rows), "total": len(rows)})


@ucas_bp.route("/links/<int:link_id>", methods=["GET"])
@token_required
@admin_required
def get_link(link_id: int):
    link = ucas_links.get_link(link_id)
    if link is None:
        return jsonify({"error": f"No link {link_id}"}), 404
    return jsonify(_dump(link))


@ucas_bp.route("/links/<int:link_id>/status", methods=["PUT"])
@token_required
@admin_required
def set_link_status(link_id: int):
    try:
        out = ucas_links.set_link_status(link_id,
                                         (_body().get("status") or "").strip())
    except ucas_links.UcasLinkError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(out))


@ucas_bp.route("/links/<int:link_id>/notes", methods=["GET"])
@token_required
@admin_required
def list_notes(link_id: int):
    """Internal admissions notes. Uni-only — the sixth form never sees these."""
    if ucas_links.get_link(link_id) is None:
        return jsonify({"error": f"No link {link_id}"}), 404
    return jsonify({"items": _dump(ucas_links.list_notes(link_id))})


@ucas_bp.route("/links/<int:link_id>/notes", methods=["POST"])
@token_required
@admin_required
def add_note(link_id: int):
    try:
        out = ucas_links.add_note(link_id, _body().get("body") or "",
                                  author=_actor())
    except ucas_links.UcasLinkError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(out)), 201


@ucas_bp.route("/notes/<int:note_id>", methods=["PUT"])
@token_required
@admin_required
def update_note(note_id: int):
    try:
        out = ucas_links.update_note(note_id, _body().get("body") or "")
    except ucas_links.UcasLinkError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(out))


@ucas_bp.route("/notes/<int:note_id>", methods=["DELETE"])
@token_required
@admin_required
def delete_note(note_id: int):
    if not ucas_links.delete_note(note_id):
        return jsonify({"error": f"No note {note_id}"}), 404
    return jsonify({"deleted": note_id})


# ── Results day ────────────────────────────────────────────────────

@ucas_bp.route("/results-day/board", methods=["GET"])
@token_required
@admin_required
def results_board():
    """Every conditional offer awaiting a results-day decision, with a
    verdict against each."""
    rows = results_day.board(
        cycle_year=_int_arg("cycle_year"),
        university_name=request.args.get("university_name"),
        include_insurance=request.args.get("include_insurance", "1") != "0",
    )
    return jsonify({"items": _dump(rows), "total": len(rows)})


@ucas_bp.route("/results-day/auto-confirm", methods=["POST"])
@token_required
@admin_required
def auto_confirm():
    """Confirm every firm applicant whose condition is met in full.

    Defaults to a dry run — pass ``{"dry_run": false}`` to actually send
    the confirmations.
    """
    body = _body()
    rows = results_day.auto_confirm(
        cycle_year=body.get("cycle_year"),
        university_name=body.get("university_name"),
        decided_by=_actor(),
        dry_run=bool(body.get("dry_run", True)),
    )
    return jsonify({
        "dry_run": bool(body.get("dry_run", True)),
        "items": _dump(rows),
        "total": len(rows),
    })


@ucas_bp.route("/choices/<int:choice_id>/confirm", methods=["POST"])
@token_required
@admin_required
def confirm_place(choice_id: int):
    try:
        out = results_day.confirm_place(choice_id, decided_by=_actor(),
                                        note=_body().get("note"))
    except ucas_mod.UcasError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(out))


@ucas_bp.route("/choices/<int:choice_id>/decline", methods=["POST"])
@token_required
@admin_required
def decline_place(choice_id: int):
    try:
        out = results_day.decline_place(choice_id, decided_by=_actor(),
                                        reason=_body().get("reason"))
    except ucas_mod.UcasError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(out))


# ── Clearing ───────────────────────────────────────────────────────

@ucas_bp.route("/clearing/unmatched", methods=["GET"])
@token_required
@admin_required
def unmatched_clearing():
    """Clearing applicants we hold no UCAS choice for — the reconciliation
    an admissions total needs before it can be trusted."""
    rows = clearing_link.unmatched_clearing_applications()
    return jsonify({"items": _dump(rows), "total": len(rows)})


@ucas_bp.route("/choices/<int:choice_id>/refer-to-clearing", methods=["POST"])
@token_required
@admin_required
def refer_to_clearing(choice_id: int):
    body = _body()
    try:
        clearing_id = clearing_link.refer_to_clearing(
            choice_id,
            preferred_course=body.get("preferred_course"),
            tariff_points=int(body.get("tariff_points") or 0),
            referred_by=_actor(),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"clearing_id": clearing_id}), 201

"""REST endpoints for absence-tracker enhancements (#47).

Exposes the new category, check-in, push, UKVI, signature, and anomaly
tables built by absence_enhancements.ensure_enhanced_schema.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.kernel.core.safe_paths import (
    PathSecurityError,
    ensure_secure_dir,
    harden_path,
    safe_join,
)
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domains.academics.domain.services.attendance.absence_tracking import (
    absence_enhancements as ae,
)

logger = logging.getLogger(__name__)

absence_bp = Blueprint("absence", __name__, url_prefix="/api/absence")


def _conn():
    return get_connection()


def _export_root() -> Path:
    """The one directory this blueprint is allowed to write exports into."""
    from education_system import paths

    return ensure_secure_dir(paths.UNIVERSITY_EXPORTS_REPORTS_DIR)


def _row(cur) -> dict:
    row = cur.fetchone()
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()} if hasattr(row, "keys") else dict(row)


# ---- categories (#11) ----
@absence_bp.route("/categories", methods=["GET"])
@token_required
def list_categories():
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    rows = ae.list_categories(conn)
    out = [
        dict(zip(("id", "name", "description", "requires_evidence",
                  "approval_route", "auto_approve"), r))
        for r in rows
    ]
    return jsonify({"categories": out})


# ---- geofenced check-in (#3) ----
@absence_bp.route("/checkin", methods=["POST"])
@token_required
def checkin():
    body = request.get_json(force=True) or {}
    required = {"student_id", "module_code", "lat", "lon"}
    if not required.issubset(body):
        return jsonify({"error": f"missing fields: {required - set(body)}"}), 400
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    ok, msg = ae.record_geofenced_checkin(
        conn, body["student_id"], body["module_code"],
        float(body["lat"]), float(body["lon"]),
        device_id=body.get("device_id", ""),
    )
    return jsonify({"accepted": ok, "message": msg}), (200 if ok else 422)


# ---- facial kiosk (#4) ----
@absence_bp.route("/kiosk/scan", methods=["POST"])
@token_required
def kiosk_scan():
    body = request.get_json(force=True) or {}
    required = {"kiosk_id", "module_code", "image_path"}
    if not required.issubset(body):
        return jsonify({"error": f"missing fields: {required - set(body)}"}), 400
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    ok, msg, sid = ae.facial_checkin(
        conn, body["kiosk_id"], body["module_code"], body["image_path"])
    return jsonify({"accepted": ok, "message": msg, "student_id": sid})


# ---- push queue (#21) ----
@absence_bp.route("/push", methods=["POST"])
@token_required
def enqueue_push():
    body = request.get_json(force=True) or {}
    required = {"user_id", "title", "body"}
    if not required.issubset(body):
        return jsonify({"error": f"missing fields: {required - set(body)}"}), 400
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    pid = ae.queue_push(conn, body["user_id"], body["title"], body["body"],
                        body.get("payload"))
    return jsonify({"queued_id": pid})


@absence_bp.route("/push/drain", methods=["POST"])
@token_required
def drain_push():
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    n = ae.drain_push_queue(conn)
    return jsonify({"sent": n})


# ---- HESA export (#30) ----
@absence_bp.route("/hesa-export", methods=["POST"])
@token_required
def hesa_export_route():
    body = request.get_json(silent=True) or {}
    # The client may name the export file but may not choose where it lands:
    # the raw body value used to be passed straight to the CSV writer, which
    # made this an authenticated arbitrary-file-write. The name is reduced to a
    # single safe component and joined beneath the approved exports root.
    requested = body.get("out_path") or f"hesa_{date.today().isoformat()}.csv"
    try:
        out_path = safe_join(_export_root(), Path(str(requested)).name)
    except PathSecurityError as exc:
        logger.warning("Rejected HESA export destination %r: %s", requested, exc)
        return jsonify({"error": "Invalid export filename"}), 400

    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    n = ae.hesa_export(conn, str(out_path),
                       term_start=body.get("term_start"),
                       term_end=body.get("term_end"))
    harden_path(out_path)
    # Return only the basename — the server's directory layout is not the
    # client's business, and leaking it aids traversal probing.
    return jsonify({"rows": n, "path": out_path.name})


# ---- UKVI (#31) ----
@absence_bp.route("/ukvi/at-risk", methods=["GET"])
@token_required
def ukvi_at_risk_route():
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    threshold = float(request.args.get("pct", "80"))
    rows = ae.ukvi_at_risk(conn, threshold)
    return jsonify({
        "threshold": threshold,
        "students": [
            {"student_id": r[0], "name": r[1],
             "engagement_pct": r[2], "missed": r[3]}
            for r in rows
        ]
    })


@absence_bp.route("/ukvi/events", methods=["POST"])
@token_required
def ukvi_log():
    body = request.get_json(force=True) or {}
    if "student_id" not in body or "event_type" not in body:
        return jsonify({"error": "student_id and event_type required"}), 400
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    ae.ukvi_log_event(conn, body["student_id"], body["event_type"],
                      body.get("event_date"), body.get("notes", ""),
                      getattr(g, "username", ""))
    return jsonify({"status": "logged"})


# ---- evidence signature (#35) ----
@absence_bp.route("/evidence/sign", methods=["POST"])
@token_required
def sign_route():
    body = request.get_json(force=True) or {}
    required = {"request_id", "file_path"}
    if not required.issubset(body):
        return jsonify({"error": f"missing fields: {required - set(body)}"}), 400
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    digest = ae.sign_evidence(conn, int(body["request_id"]),
                              body["file_path"],
                              getattr(g, "username", ""))
    return jsonify({"sha256": digest})


@absence_bp.route("/evidence/verify", methods=["POST"])
@token_required
def verify_route():
    body = request.get_json(force=True) or {}
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    ok = ae.verify_evidence(conn, int(body["request_id"]), body["file_path"])
    return jsonify({"valid": ok})


# ---- LMS (#46) ----
@absence_bp.route("/lms/sync", methods=["POST"])
@token_required
def lms_sync_route():
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    n = ae.lms_sync_approved_requests(conn)
    return jsonify({"granted": n})


# ---- anomalies (#50) ----
@absence_bp.route("/anomalies/scan", methods=["POST"])
@token_required
def anomalies_scan():
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    new = ae.anomaly_scan(conn)
    return jsonify({"found": len(new), "items": new})


@absence_bp.route("/anomalies", methods=["GET"])
@token_required
def anomalies_list():
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    cur = conn.execute(
        "SELECT id, kind, student_id, module_code, details, severity, "
        "detected_at, resolved FROM attendance_anomalies "
        "ORDER BY detected_at DESC LIMIT 500"
    )
    cols = ("id", "kind", "student_id", "module_code", "details",
            "severity", "detected_at", "resolved")
    return jsonify({"items": [dict(zip(cols, r)) for r in cur.fetchall()]})


# ---- chatbot-style quota endpoint (#49 companion API) ----
@absence_bp.route("/quota/<student_id>", methods=["GET"])
@token_required
def quota(student_id):
    conn = _conn()
    ae.ensure_enhanced_schema(conn)
    module = request.args.get("module")
    threshold = float(request.args.get("threshold", "75"))
    return jsonify({"message": ae.chatbot_absence_quota(conn, student_id,
                                                       module, threshold)})

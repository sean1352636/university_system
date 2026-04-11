"""Parent portal API routes.

Blueprint: parent_portal  —  registered at /parent/

Endpoints
---------
  GET  /parent/                                 Serve the parent SPA shell
  GET  /parent/api/children                     List linked children
  GET  /parent/api/children/<id>/attendance     Attendance summary + records
  GET  /parent/api/children/<id>/grades         Grades / assessment results
  GET  /parent/api/children/<id>/timetable      Weekly timetable
  GET  /parent/api/children/<id>/homework       Pending + completed homework
  GET  /parent/api/children/<id>/behaviour      Behaviour / reward records
  GET  /parent/api/children/<id>/messages       Messages from school
  POST /parent/api/children/<id>/messages       Send message to teacher
  GET  /parent/api/notifications                Parent notifications
  GET  /parent/api/parents-evening              Available booking slots
  POST /parent/api/parents-evening/book         Book a slot

Authentication
--------------
All endpoints require a valid JWT (Bearer token).  The parent role is
verified on every call.  The parent-child link is checked before any
child-specific data is returned.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, g, send_from_directory, current_app
from markupsafe import escape

from education_system.shared.api.auth import token_required, decode_token
from education_system.shared.auth.db import AUTH_DB_FILE
from education_system.shared.services.parent_child_link import ParentChildLinkService

logger = logging.getLogger(__name__)

_DIR = Path(__file__).parent
_TEMPLATE_DIR = _DIR / "templates"
_STATIC_DIR = _DIR / "static"

parent_portal_bp = Blueprint(
    "parent_portal",
    __name__,
    url_prefix="/parent",
)

# Module-level link service instance (lazy-initialised)
_link_svc: ParentChildLinkService | None = None


def _get_link_svc() -> ParentChildLinkService:
    global _link_svc
    if _link_svc is None:
        _link_svc = ParentChildLinkService(str(AUTH_DB_FILE))
    return _link_svc


# ── DB path resolution ───────────────────────────────────────────────────


def _get_child_db(system_key: str) -> str | None:
    """Return the SQLite database path for *system_key* (school/college/primary/university)."""
    try:
        if system_key == "school":
            from education_system.secondary_school.core.paths import DEFAULT_DB_PATH
            return str(DEFAULT_DB_PATH)
        if system_key == "college":
            from education_system.college_system.core.paths import DEFAULT_DB_PATH
            return str(DEFAULT_DB_PATH)
        if system_key == "primary":
            from education_system.primary_school.infrastructure.database.db import get_db_path
            return str(get_db_path())
        if system_key == "university":
            from education_system.university_system.infrastructure.database.database_utils import get_db_path
            return str(get_db_path())
    except Exception as exc:
        logger.warning("Could not resolve DB for system_key=%s: %s", system_key, exc)
    return None


# ── Auth helpers ─────────────────────────────────────────────────────────


def _parent_required(f):
    """Decorator: token_required + verifies the user has a 'parent' role in at least one system."""
    import functools

    @functools.wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        systems = g.current_user.get("systems", [])
        roles = {s.get("role", "") for s in systems}
        # superadmin and admin may also access parent portal (for testing/support)
        allowed = {"parent", "admin", "superadmin"}
        if not roles & allowed:
            return jsonify({"error": "Parent access required"}), 403
        return f(*args, **kwargs)

    return decorated


def _sanitize_child_id(child_id: str) -> str:
    """Sanitize and validate a child_id URL parameter to prevent injection and XSS."""
    import re
    # Only allow alphanumeric characters, hyphens, and underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '', str(child_id or ''))
    return str(escape(sanitized[:64]))  # cap length and escape for safe output


def _verify_child_access(child_student_id: str) -> tuple[dict | None, tuple | None]:
    """Return (link_record, None) if parent has access, else (None, error_response)."""
    child_student_id = _sanitize_child_id(child_student_id)
    parent_user_id = g.current_user["user_id"]
    svc = _get_link_svc()
    link = None
    for child in svc.get_children(parent_user_id):
        if child["child_student_id"] == child_student_id:
            link = child
            break
    if link is None:
        # Admins/superadmins bypass parent-child check
        roles = {s.get("role", "") for s in g.current_user.get("systems", [])}
        if not roles & {"admin", "superadmin"}:
            return None, (jsonify({"error": "No access to this child"}), 403)
        # For admin: try to detect system from any system
        link = {"child_student_id": child_student_id, "child_system_key": "school"}
    return link, None


# ── Static / SPA ─────────────────────────────────────────────────────────


@parent_portal_bp.route("/")
@parent_portal_bp.route("/dashboard")
@parent_portal_bp.route("/grades")
@parent_portal_bp.route("/attendance")
@parent_portal_bp.route("/timetable")
@parent_portal_bp.route("/homework")
@parent_portal_bp.route("/behaviour")
@parent_portal_bp.route("/messages")
@parent_portal_bp.route("/parents-evening")
@parent_portal_bp.route("/settings")
def serve_spa():
    """Serve the parent SPA shell."""
    return send_from_directory(str(_TEMPLATE_DIR), "parent.html")


@parent_portal_bp.route("/static/<path:filename>")
def serve_static(filename):
    import re
    # Validate filename contains only safe characters to prevent path traversal and XSS
    if not re.match(r'^[a-zA-Z0-9/_\-][a-zA-Z0-9/._\-]*$', filename):
        return jsonify({"error": "Invalid filename"}), 400
    return send_from_directory(str(_STATIC_DIR), filename)


# ── Children list ────────────────────────────────────────────────────────


@parent_portal_bp.route("/api/children", methods=["GET"])
@_parent_required
def list_children():
    """Return all children linked to the authenticated parent."""
    parent_user_id = g.current_user["user_id"]
    svc = _get_link_svc()
    links = svc.get_children(parent_user_id)

    enriched = []
    for link in links:
        child = dict(link)
        # Try to fetch student name from the relevant system DB
        db_path = _get_child_db(link["child_system_key"])
        if db_path:
            try:
                conn = sqlite3.connect(db_path, timeout=10)
                conn.row_factory = sqlite3.Row
                try:
                    # Try secondary/college schema first
                    row = conn.execute(
                        "SELECT first_name, last_name, year_group, form_group "
                        "FROM students WHERE student_id = ? LIMIT 1",
                        (link["child_student_id"],),
                    ).fetchone()
                    if row is None:
                        # Primary schema uses 'pupils'
                        row = conn.execute(
                            "SELECT first_name, last_name, year_group, class_name "
                            "FROM pupils WHERE pupil_id = ? LIMIT 1",
                            (link["child_student_id"],),
                        ).fetchone()
                    if row:
                        child["name"] = f"{row['first_name']} {row['last_name']}"
                        child["year_group"] = row[2] if len(row) > 2 else None
                        child["form_group"] = row[3] if len(row) > 3 else None
                finally:
                    conn.close()
            except Exception as exc:
                logger.debug("Could not enrich child %s: %s", link["child_student_id"], exc)
        enriched.append(child)

    return jsonify({"data": enriched, "count": len(enriched)})


# ── Attendance ───────────────────────────────────────────────────────────


@parent_portal_bp.route("/api/children/<child_id>/attendance", methods=["GET"])
@_parent_required
def child_attendance(child_id: str):
    child_id = _sanitize_child_id(child_id)
    link, err = _verify_child_access(child_id)
    if err:
        return err

    db_path = _get_child_db(link["child_system_key"])
    if not db_path:
        return jsonify({"error": "System database unavailable"}), 503

    limit = min(int(request.args.get("limit", 90)), 365)
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            # Try secondary/college schema
            rows = conn.execute(
                """
                SELECT date, status, subject_id, period, note
                FROM attendance
                WHERE student_id = ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (child_id, limit),
            ).fetchall()
            records = [dict(r) for r in rows]

            summary = {"present": 0, "absent": 0, "late": 0, "authorised": 0, "other": 0}
            for r in records:
                s = (r.get("status") or "other").lower()
                if s in summary:
                    summary[s] += 1
                else:
                    summary["other"] += 1
            total = sum(summary.values())
            summary["attendance_pct"] = (
                round(summary["present"] / total * 100, 1) if total > 0 else 0.0
            )
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Attendance query failed for %s: %s", child_id, exc)
        return jsonify({"error": "Could not fetch attendance data"}), 500

    return jsonify({"data": {"summary": summary, "records": records}})


# ── Grades ───────────────────────────────────────────────────────────────


@parent_portal_bp.route("/api/children/<child_id>/grades", methods=["GET"])
@_parent_required
def child_grades(child_id: str):
    child_id = _sanitize_child_id(child_id)
    link, err = _verify_child_access(child_id)
    if err:
        return err

    db_path = _get_child_db(link["child_system_key"])
    if not db_path:
        return jsonify({"error": "System database unavailable"}), 503

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT g.subject_id, s.name AS subject_name, g.grade, g.percentage,
                       g.grade_type, g.date_recorded, g.comments
                FROM grades g
                LEFT JOIN subjects s ON s.subject_id = g.subject_id
                WHERE g.student_id = ?
                ORDER BY g.date_recorded DESC
                LIMIT 200
                """,
                (child_id,),
            ).fetchall()
            grades = [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Grades query failed for %s: %s", child_id, exc)
        return jsonify({"error": "Could not fetch grades data"}), 500

    return jsonify({"data": grades, "count": len(grades)})


# ── Timetable ────────────────────────────────────────────────────────────


@parent_portal_bp.route("/api/children/<child_id>/timetable", methods=["GET"])
@_parent_required
def child_timetable(child_id: str):
    child_id = _sanitize_child_id(child_id)
    link, err = _verify_child_access(child_id)
    if err:
        return err

    db_path = _get_child_db(link["child_system_key"])
    if not db_path:
        return jsonify({"error": "System database unavailable"}), 503

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT t.day_of_week, t.period, t.start_time, t.end_time,
                       s.name AS subject_name, t.room, t.teacher_name
                FROM timetable t
                LEFT JOIN subjects s ON s.subject_id = t.subject_id
                WHERE t.student_id = ?
                ORDER BY t.day_of_week, t.period
                """,
                (child_id,),
            ).fetchall()
            slots = [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Timetable query failed for %s: %s", child_id, exc)
        return jsonify({"error": "Could not fetch timetable data"}), 500

    return jsonify({"data": slots})


# ── Homework ─────────────────────────────────────────────────────────────


@parent_portal_bp.route("/api/children/<child_id>/homework", methods=["GET"])
@_parent_required
def child_homework(child_id: str):
    child_id = _sanitize_child_id(child_id)
    link, err = _verify_child_access(child_id)
    if err:
        return err

    db_path = _get_child_db(link["child_system_key"])
    if not db_path:
        return jsonify({"error": "System database unavailable"}), 503

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT h.homework_id, s.name AS subject_name, h.title,
                       h.description, h.set_date, h.due_date, h.status,
                       h.max_marks, hs.marks_awarded, hs.submitted_at
                FROM homework h
                LEFT JOIN subjects s ON s.subject_id = h.subject_id
                LEFT JOIN homework_submissions hs
                       ON hs.homework_id = h.homework_id AND hs.student_id = ?
                WHERE h.student_id = ? OR hs.student_id = ?
                ORDER BY h.due_date ASC
                LIMIT 100
                """,
                (child_id, child_id, child_id),
            ).fetchall()
            items = [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Homework query failed for %s: %s", child_id, exc)
        return jsonify({"error": "Could not fetch homework data"}), 500

    pending = [h for h in items if not h.get("submitted_at")]
    completed = [h for h in items if h.get("submitted_at")]
    return jsonify({"data": {"pending": pending, "completed": completed}})


# ── Behaviour ────────────────────────────────────────────────────────────


@parent_portal_bp.route("/api/children/<child_id>/behaviour", methods=["GET"])
@_parent_required
def child_behaviour(child_id: str):
    child_id = _sanitize_child_id(child_id)
    link, err = _verify_child_access(child_id)
    if err:
        return err

    db_path = _get_child_db(link["child_system_key"])
    if not db_path:
        return jsonify({"error": "System database unavailable"}), 503

    limit = min(int(request.args.get("limit", 50)), 200)
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            # Behaviour incidents
            try:
                brows = conn.execute(
                    """
                    SELECT 'behaviour' AS record_type, date, category, description,
                           severity, action_taken, recorded_by
                    FROM behaviour_incidents
                    WHERE student_id = ?
                    ORDER BY date DESC
                    LIMIT ?
                    """,
                    (child_id, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                brows = []

            # Rewards / commendations
            try:
                rrows = conn.execute(
                    """
                    SELECT 'reward' AS record_type, date, category, description,
                           points, awarded_by
                    FROM rewards
                    WHERE student_id = ?
                    ORDER BY date DESC
                    LIMIT ?
                    """,
                    (child_id, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rrows = []

            records = sorted(
                [dict(r) for r in brows] + [dict(r) for r in rrows],
                key=lambda x: x.get("date", ""),
                reverse=True,
            )[:limit]
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Behaviour query failed for %s: %s", child_id, exc)
        return jsonify({"error": "Could not fetch behaviour data"}), 500

    return jsonify({"data": records, "count": len(records)})


# ── Messages ─────────────────────────────────────────────────────────────


@parent_portal_bp.route("/api/children/<child_id>/messages", methods=["GET"])
@_parent_required
def child_messages_list(child_id: str):
    child_id = _sanitize_child_id(child_id)
    link, err = _verify_child_access(child_id)
    if err:
        return err

    db_path = _get_child_db(link["child_system_key"])
    if not db_path:
        return jsonify({"error": "System database unavailable"}), 503

    parent_user_id = g.current_user["user_id"]
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT message_id, sender_id, sender_name, recipient_id,
                       subject, body, sent_at, read_at, is_read,
                       related_student_id
                FROM messages
                WHERE (sender_id = ? OR recipient_id = ?)
                  AND related_student_id = ?
                ORDER BY sent_at DESC
                LIMIT 100
                """,
                (parent_user_id, parent_user_id, child_id),
            ).fetchall()
            messages = [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Messages query failed: %s", exc)
        return jsonify({"error": "Could not fetch messages"}), 500

    return jsonify({"data": messages, "count": len(messages)})


@parent_portal_bp.route("/api/children/<child_id>/messages", methods=["POST"])
@_parent_required
def child_messages_send(child_id: str):
    child_id = _sanitize_child_id(child_id)
    link, err = _verify_child_access(child_id)
    if err:
        return err

    db_path = _get_child_db(link["child_system_key"])
    if not db_path:
        return jsonify({"error": "System database unavailable"}), 503

    body = request.get_json(silent=True) or {}
    subject = str(escape((body.get("subject") or "").strip()))
    message_body = str(escape((body.get("body") or "").strip()))
    recipient_id = str(escape(body.get("recipient_id") or ""))

    if not message_body:
        return jsonify({"error": "Message body is required"}), 400

    parent_user_id = g.current_user["user_id"]
    parent_username = g.current_user.get("username", "")
    now = datetime.utcnow().isoformat()

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """
                INSERT INTO messages
                    (sender_id, sender_name, recipient_id, subject, body,
                     sent_at, is_read, related_student_id)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (parent_user_id, parent_username, recipient_id,
                 subject, message_body, now, child_id),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Send message failed: %s", exc)
        return jsonify({"error": "Could not send message"}), 500

    return jsonify({"message": "Message sent"}), 201


# ── Notifications ────────────────────────────────────────────────────────


@parent_portal_bp.route("/api/notifications", methods=["GET"])
@_parent_required
def parent_notifications():
    parent_user_id = g.current_user["user_id"]
    notifications: list[dict] = []

    # Gather notifications from each linked child's system
    svc = _get_link_svc()
    links = svc.get_children(parent_user_id)
    seen_keys: set[str] = set()

    for link in links:
        system_key = link["child_system_key"]
        if system_key in seen_keys:
            continue
        seen_keys.add(system_key)
        db_path = _get_child_db(system_key)
        if not db_path:
            continue
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT notification_id, title, message, notification_type,
                           created_at, read_at, is_read, related_id
                    FROM notifications
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    (parent_user_id,),
                ).fetchall()
                for r in rows:
                    n = dict(r)
                    n["system_key"] = system_key
                    notifications.append(n)
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("Notifications query failed for %s: %s", system_key, exc)

    notifications.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    unread = sum(1 for n in notifications if not n.get("is_read"))
    return jsonify({"data": notifications, "unread_count": unread})


# ── Parents' evening ─────────────────────────────────────────────────────


@parent_portal_bp.route("/api/parents-evening", methods=["GET"])
@_parent_required
def parents_evening_slots():
    parent_user_id = g.current_user["user_id"]
    svc = _get_link_svc()
    links = svc.get_children(parent_user_id)
    slots: list[dict] = []

    for link in links:
        db_path = _get_child_db(link["child_system_key"])
        if not db_path:
            continue
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT pe.slot_id, pe.event_id, pe.teacher_id, pe.start_time,
                           pe.end_time, pe.is_booked, pe.booked_by_parent_id,
                           pe.student_id, pee.event_name, pee.event_date
                    FROM parents_evening_slots pe
                    LEFT JOIN parents_evening_events pee ON pee.event_id = pe.event_id
                    WHERE (pe.is_booked = 0 OR pe.booked_by_parent_id = ?)
                      AND pe.student_id = ?
                    ORDER BY pee.event_date, pe.start_time
                    """,
                    (parent_user_id, link["child_student_id"]),
                ).fetchall()
                for r in rows:
                    s = dict(r)
                    s["child_student_id"] = link["child_student_id"]
                    s["system_key"] = link["child_system_key"]
                    slots.append(s)
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("Parents evening query failed: %s", exc)

    return jsonify({"data": slots, "count": len(slots)})


@parent_portal_bp.route("/api/parents-evening/book", methods=["POST"])
@_parent_required
def book_parents_evening():
    body = request.get_json(silent=True) or {}
    slot_id = body.get("slot_id")
    child_id = _sanitize_child_id(body.get("child_id", ""))
    # Validate system_key against known values to prevent injection
    allowed_systems = {"school", "college", "primary", "university"}
    system_key = body.get("system_key", "school")
    if system_key not in allowed_systems:
        return jsonify({"error": "Invalid system_key"}), 400

    if not slot_id or not child_id:
        return jsonify({"error": "slot_id and child_id are required"}), 400

    link, err = _verify_child_access(child_id)
    if err:
        return err

    db_path = _get_child_db(system_key)
    if not db_path:
        return jsonify({"error": "System database unavailable"}), 503

    parent_user_id = g.current_user["user_id"]
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM parents_evening_slots WHERE slot_id = ? AND is_booked = 0 LIMIT 1",
                (slot_id,),
            ).fetchone()
            if not row:
                return jsonify({"error": "Slot not available"}), 409
            conn.execute(
                """
                UPDATE parents_evening_slots
                SET is_booked = 1, booked_by_parent_id = ?, student_id = ?
                WHERE slot_id = ? AND is_booked = 0
                """,
                (parent_user_id, child_id, slot_id),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Book parents evening failed: %s", exc)
        return jsonify({"error": "Could not book slot"}), 500

    return jsonify({"message": "Slot booked successfully"}), 201

"""AI study routes: study plans, tasks, flashcards, concept explanations,
reminders, settings and the staff overview.

Every route goes through ``AIStudyService`` — the API used to repeat the
service's SQL and had drifted from it (completing a task here logged no study
time; plan generation was the old random one).

**Scope.** The caller's own id is resolved from the token
(``study_context.owner_for_subject``: ``users.student_id`` for the username).
A student reads and writes only their own rows; a ``student_id`` query
parameter naming anyone else is refused. Staff may *read* the students they
teach or tutor (``companion_staff.can_view``; administrators everyone), and
write only their own. Listing without a ``student_id`` returns the caller's
own rows — it used to return every student's plans.
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import (
    get_pagination_params,
    paginated_response,
)
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domains.student_life.domain.study_hub.services import (
    study_context,
)

logger = logging.getLogger(__name__)

ai_study_bp = Blueprint("ai_study", __name__, url_prefix="/api/ai-study")


@ai_study_bp.errorhandler(ValueError)
def _bad_request(exc):
    return jsonify({"error": str(exc), "status": 400}), 400


@ai_study_bp.errorhandler(ValidationError)
def _validation(exc):
    return jsonify({"error": str(exc), "status": 400}), 400


@ai_study_bp.errorhandler(PermissionError)
def _forbidden(exc):
    return jsonify({"error": str(exc) or "Forbidden", "status": 403}), 403


_service = None


def _svc():
    global _service
    if _service is None:
        from education_system.systems.university.domains.student_life.domain.study_hub.services.planning import (
            AIStudyService,
        )
        _service = AIStudyService()
    return _service


def _viewer() -> dict:
    user = dict(g.get("current_user") or {})
    user.setdefault("username", user.get("sub"))
    return user


def _me() -> str:
    user = g.get("current_user") or {}
    with get_connection() as conn:
        me = study_context.owner_for_subject(conn, user.get("sub"), user.get("student_id"))
    if not me:
        raise PermissionError("Sign in to use the study companion")
    return me


def _target(student_id=None) -> str:
    """The student a read is for: the caller, or (staff) a student they may see."""
    me = _me()
    if not student_id or str(student_id) == me:
        return me
    if study_context.is_staff(_viewer()) and _svc().can_view_student(_viewer(), student_id):
        return str(student_id)
    raise PermissionError("You can only see your own study companion"
                          + (" or students you teach" if study_context.is_staff(_viewer()) else ""))


def _readable(owner) -> None:
    if owner is None:
        raise ValidationError("not found")
    _target(owner)


def _body() -> dict:
    return request.get_json(silent=True) or {}


def _need(data, *fields):
    for field in fields:
        if data.get(field) in (None, ""):
            raise ValidationError(f"Missing required field: {field}")


def _log(action, entity, **details):
    log_activity(action, entity, user=(g.get("current_user") or {}).get("sub"),
                 details=details or None)


# ---- plans ----

@ai_study_bp.route("/plans", methods=["GET"])
@token_required
def list_plans():
    student_id = _target(request.args.get("student_id"))
    search = (request.args.get("search") or "").strip().lower()
    status = request.args.get("status")
    items = _svc().get_student_study_plans(student_id)
    if search:
        items = [p for p in items if search in str(p.get("plan_name") or "").lower()]
    if status:
        items = [p for p in items if (p.get("status") or "Active") == status]
    page, per_page, offset = get_pagination_params()
    _log("view", "study_plans")
    return jsonify(paginated_response(items[offset:offset + per_page], len(items), page, per_page))


@ai_study_bp.route("/plans/<int:plan_id>", methods=["GET"])
@token_required
def get_plan(plan_id: int):
    _readable(_svc().owner_of_plan(plan_id))
    plan = _svc().get_study_plan(plan_id)
    _log("view", "study_plans", plan_id=plan_id)
    return jsonify(plan)


@ai_study_bp.route("/plans", methods=["POST"])
@token_required
def create_plan():
    """An empty plan for the caller to add their own tasks to."""
    data = _body()
    _need(data, "plan_name", "end_date")
    plan_id = _svc().create_plan(_me(), data["plan_name"], data["end_date"],
                                 course_id=data.get("course_id"),
                                 start_date=data.get("start_date"), notes=data.get("notes"))
    _log("create", "study_plans", plan_id=plan_id)
    return jsonify(_svc().get_study_plan(plan_id)), 201


@ai_study_bp.route("/plans/generate", methods=["POST"])
@token_required
def generate_plan():
    """Generate a plan from the caller's exams, deadlines, marks and modules."""
    data = _body()
    _need(data, "exam_date")
    result = _svc().generate_study_plan(_me(), data.get("course_id"), data["exam_date"],
                                        data.get("hours_per_day", 2),
                                        plan_name=data.get("plan_name"))
    _log("create", "study_plan_generate", plan_id=result["plan_id"])
    return jsonify(result), 201


@ai_study_bp.route("/plans/<int:plan_id>", methods=["PUT"])
@token_required
def update_plan(plan_id: int):
    data = _body()
    me = _me()
    result = {"plan_id": plan_id}
    if any(k in data for k in ("plan_name", "exam_date", "notes", "course_id")):
        result = _svc().update_plan(plan_id, me, plan_name=data.get("plan_name"),
                                    exam_date=data.get("exam_date"), notes=data.get("notes"),
                                    course_id=data.get("course_id"))
    if data.get("status"):
        result["status"] = _svc().set_plan_status(plan_id, data["status"], me)
    _log("update", "study_plans", plan_id=plan_id)
    return jsonify(result)


@ai_study_bp.route("/plans/<int:plan_id>", methods=["DELETE"])
@token_required
def delete_plan(plan_id: int):
    _svc().delete_plan(plan_id, _me())
    _log("delete", "study_plans", plan_id=plan_id)
    return jsonify({"plan_id": plan_id, "deleted": True})


@ai_study_bp.route("/plans/<int:plan_id>/reschedule-missed", methods=["POST"])
@token_required
def reschedule_missed(plan_id: int):
    result = _svc().reschedule_missed(plan_id, _me())
    _log("update", "study_plan_reschedule", plan_id=plan_id, **result)
    return jsonify(result)


# ---- tasks ----

@ai_study_bp.route("/plans/<int:plan_id>/tasks", methods=["POST"])
@token_required
def add_task(plan_id: int):
    data = _body()
    _need(data, "title", "scheduled_date")
    task_id = _svc().add_task(plan_id, data["title"], data["scheduled_date"],
                              data.get("duration_minutes", 60), data.get("priority", "Medium"),
                              data.get("description"), data.get("module_code"), student_id=_me())
    _log("create", "study_task", task_id=task_id)
    return jsonify({"task_id": task_id}), 201


@ai_study_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id: int):
    data = _body()
    me = _me()
    if data.get("scheduled_date") and len(data) == 1:
        _svc().reschedule_task(task_id, data["scheduled_date"], me)
    else:
        _svc().update_task(task_id, me, title=data.get("title"),
                           scheduled_date=data.get("scheduled_date"),
                           duration_minutes=data.get("duration_minutes"),
                           priority=data.get("priority"), description=data.get("description"),
                           notes=data.get("notes"))
    _log("update", "study_task", task_id=task_id)
    return jsonify({"task_id": task_id, "updated": True})


@ai_study_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@token_required
def delete_task(task_id: int):
    _svc().delete_task(task_id, _me())
    _log("delete", "study_task", task_id=task_id)
    return jsonify({"task_id": task_id, "deleted": True})


@ai_study_bp.route("/tasks/<int:task_id>/complete", methods=["PUT"])
@token_required
def complete_task(task_id: int):
    """Mark a study task as completed (and log the study time)."""
    _svc().complete_study_task(task_id, student_id=_me())
    _log("update", "study_task_complete", task_id=task_id, status="completed")
    return jsonify({"task_id": task_id, "completed": True})


@ai_study_bp.route("/tasks/<int:task_id>/uncomplete", methods=["PUT"])
@token_required
def uncomplete_task(task_id: int):
    _svc().uncomplete_task(task_id, _me())
    _log("update", "study_task_uncomplete", task_id=task_id)
    return jsonify({"task_id": task_id, "completed": False})


@ai_study_bp.route("/tasks/<int:task_id>/skip", methods=["PUT"])
@token_required
def skip_task(task_id: int):
    _svc().skip_task(task_id, _me())
    _log("update", "study_task_skip", task_id=task_id)
    return jsonify({"task_id": task_id, "status": "skipped"})


# ---- flashcards ----

@ai_study_bp.route("/flashcards", methods=["GET"])
@token_required
def list_flashcards():
    student_id = _target(request.args.get("student_id"))
    if student_id != _me():
        raise PermissionError("Staff see deck totals, not a student's cards")
    items = _svc().list_flashcards(student_id, request.args.get("deck_name"))
    return jsonify({"items": items, "total": len(items)})


@ai_study_bp.route("/flashcards", methods=["POST"])
@token_required
def create_flashcard():
    data = _body()
    _need(data, "deck_name", "question", "answer")
    fid = _svc().create_flashcard(_me(), data.get("course_id"), data["deck_name"],
                                  data["question"], data["answer"])
    _log("create", "flashcard", flashcard_id=fid)
    return jsonify({"flashcard_id": fid}), 201


@ai_study_bp.route("/flashcards/generate", methods=["POST"])
@token_required
def generate_flashcards():
    """Write cards from the caller's notes (Claude, else definitions in the notes)."""
    data = _body()
    _need(data, "deck_name", "notes")
    result = _svc().generate_flashcards(_me(), data.get("course_id"), data["deck_name"],
                                        data["notes"], int(data.get("count", 10)))
    _log("create", "flashcards_generate", created=len(result["created"]),
         source=result["source"])
    return jsonify(result), 201


@ai_study_bp.route("/flashcards/due", methods=["GET"])
@token_required
def get_due_flashcards():
    """Flashcards due for the caller's review (spaced repetition)."""
    student_id = _target(request.args.get("student_id"))
    if student_id != _me():
        raise PermissionError("Staff see deck totals, not a student's cards")
    items = _svc().get_due_flashcards(student_id, request.args.get("deck_name"))
    _log("view", "flashcards_due")
    return jsonify({"items": items, "total": len(items)})


@ai_study_bp.route("/flashcards/<int:flashcard_id>", methods=["PUT"])
@token_required
def update_flashcard(flashcard_id: int):
    data = _body()
    me = _me()
    if "suspended" in data:
        _svc().set_flashcard_suspended(flashcard_id, bool(data["suspended"]), me)
    if any(k in data for k in ("question", "answer", "deck_name", "course_id")):
        _svc().update_flashcard(flashcard_id, me, question=data.get("question"),
                                answer=data.get("answer"), deck_name=data.get("deck_name"),
                                course_id=data.get("course_id"))
    _log("update", "flashcard", flashcard_id=flashcard_id)
    return jsonify({"flashcard_id": flashcard_id, "updated": True})


@ai_study_bp.route("/flashcards/<int:flashcard_id>", methods=["DELETE"])
@token_required
def delete_flashcard(flashcard_id: int):
    _svc().delete_flashcard(flashcard_id, _me())
    _log("delete", "flashcard", flashcard_id=flashcard_id)
    return jsonify({"flashcard_id": flashcard_id, "deleted": True})


@ai_study_bp.route("/flashcards/<int:flashcard_id>/review", methods=["POST"])
@token_required
def review_flashcard(flashcard_id: int):
    """Review a card: ``{"quality": "again|hard|good|easy|0-5"}`` or ``{"correct": bool}``."""
    data = _body()
    if "correct" not in data and "quality" not in data:
        raise ValidationError("Missing required field: correct or quality")
    correct = bool(data["correct"]) if "correct" in data else None
    result = _svc().review_flashcard(flashcard_id, correct, data.get("quality"), student_id=_me())
    _log("update", "flashcard_review", flashcard_id=flashcard_id,
         next_review=result["next_review"])
    return jsonify(result)


@ai_study_bp.route("/flashcards/<int:flashcard_id>/from-mistake", methods=["POST"])
@token_required
def card_from_mistake(flashcard_id: int):
    """A follow-up card aimed at a wrong answer (``{"given": "what I said"}``)."""
    new_id = _svc().card_from_mistake(flashcard_id, _body().get("given"), _me())
    _log("create", "flashcard", flashcard_id=new_id, source="mistake")
    return jsonify({"flashcard_id": new_id}), 201


@ai_study_bp.route("/flashcards/decks", methods=["GET"])
@token_required
def get_flashcard_decks():
    """Deck totals for the caller, or (staff) a student they teach."""
    student_id = _target(request.args.get("student_id"))
    items = _svc().get_flashcard_decks(student_id)
    _log("view", "flashcard_decks")
    return jsonify({"items": items, "total": len(items)})


@ai_study_bp.route("/flashcards/decks/<path:deck_name>", methods=["PUT"])
@token_required
def rename_deck(deck_name: str):
    data = _body()
    _need(data, "new_name")
    count = _svc().rename_deck(_me(), deck_name, data["new_name"])
    return jsonify({"deck_name": data["new_name"], "cards": count})


@ai_study_bp.route("/flashcards/decks/<path:deck_name>", methods=["DELETE"])
@token_required
def delete_deck(deck_name: str):
    count = _svc().delete_deck(_me(), deck_name)
    _log("delete", "flashcard_deck", deck=deck_name, cards=count)
    return jsonify({"deck_name": deck_name, "deleted": count})


# ---- concept explanations ----

@ai_study_bp.route("/concept-explanations", methods=["GET"])
@token_required
def list_concept_explanations():
    student_id = _target(request.args.get("student_id"))
    if student_id != _me():
        raise PermissionError("Explanations are private to the student")
    search = (request.args.get("search") or "").strip().lower()
    course_id = request.args.get("course_id")
    items = _svc().get_explanation_history(student_id)
    if search:
        items = [e for e in items if search in str(e.get("concept_name") or "").lower()]
    if course_id:
        items = [e for e in items if e.get("course_id") == course_id]
    page, per_page, offset = get_pagination_params()
    _log("view", "concept_explanations")
    return jsonify(paginated_response(items[offset:offset + per_page], len(items), page, per_page))


@ai_study_bp.route("/concept-explanations/<int:explanation_id>", methods=["GET"])
@token_required
def get_concept_explanation(explanation_id: int):
    owner = _svc().owner_of_explanation(explanation_id)
    if owner is None:
        raise ValidationError(f"concept-explanations {explanation_id} not found")
    if owner != _me():
        raise PermissionError("Explanations are private to the student")
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM concept_explanations WHERE explanation_id = ?",
                           (explanation_id,)).fetchone()
    _log("view", "concept_explanations", explanation_id=explanation_id)
    return jsonify({k: row[k] for k in row.keys()})


@ai_study_bp.route("/concept-explanations", methods=["POST"])
@token_required
def create_concept_explanation():
    """Explain a concept (``concept_name``, optional ``difficulty_level`` and
    ``course_id``), or save the caller's own text when ``explanation`` is given."""
    data = _body()
    _need(data, "concept_name")
    me = _me()
    if data.get("explanation"):
        new_id = _svc().save_explanation(me, data["concept_name"], data["explanation"],
                                         data.get("course_id"),
                                         data.get("difficulty_level", "Beginner"))
        _log("create", "concept_explanations", explanation_id=new_id)
        return jsonify({"explanation_id": new_id}), 201
    result = _svc().explain_concept(me, data.get("course_id"), data["concept_name"],
                                    data.get("difficulty_level", "Beginner"))
    _log("create", "concept_explanations", explanation_id=result["explanation_id"],
         source=result["source"])
    return jsonify(result), 201


@ai_study_bp.route("/concept-explanations/<int:explanation_id>/rate", methods=["PUT"])
@token_required
def rate_explanation(explanation_id: int):
    """Rate the helpfulness of a concept explanation (1-5)."""
    data = _body()
    if "rating" not in data:
        raise ValidationError("Missing required field: rating")
    rating = data["rating"]
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
        raise ValidationError("Rating must be an integer between 1 and 5")
    _svc().rate_explanation(explanation_id, rating, student_id=_me())
    _log("update", "concept_explanation_rating", explanation_id=explanation_id, rating=rating)
    return jsonify({"explanation_id": explanation_id, "helpful_rating": rating})


@ai_study_bp.route("/concept-explanations/<int:explanation_id>", methods=["DELETE"])
@token_required
def delete_explanation(explanation_id: int):
    _svc().delete_explanation(explanation_id, _me())
    return jsonify({"explanation_id": explanation_id, "deleted": True})


@ai_study_bp.route("/concept-explanations/<int:explanation_id>/flashcards", methods=["POST"])
@token_required
def flashcards_from_explanation(explanation_id: int):
    data = _body()
    result = _svc().flashcards_from_explanation(explanation_id, data.get("deck_name"),
                                                int(data.get("count", 8)), student_id=_me())
    _log("create", "flashcards_from_explanation", explanation_id=explanation_id,
         created=len(result["created"]))
    return jsonify(result), 201


# ---- students ----

@ai_study_bp.route("/students/<student_id>/history", methods=["GET"])
@token_required
def get_explanation_history(student_id: str):
    """A student's own concept explanations."""
    if _target(student_id) != _me():
        raise PermissionError("Explanations are private to the student")
    rows = _svc().get_explanation_history(student_id)
    _log("view", "explanation_history")
    return jsonify({"items": rows, "total": len(rows)})


@ai_study_bp.route("/students/<student_id>/analytics", methods=["GET"])
@token_required
def get_study_analytics(student_id: str):
    """Study analytics for the caller, or (staff) a student they teach who shares."""
    target = _target(student_id)
    if target != _me():
        detail = _svc().staff_student_detail(_viewer(), target)
        if not detail.get("shared"):
            raise PermissionError("This student has not shared their study activity")
    _log("view", "study_analytics")
    return jsonify(_svc().get_study_analytics(target))


# ---- today, settings, reminders ----

@ai_study_bp.route("/today", methods=["GET"])
@token_required
def today():
    return jsonify(_svc().today(_me()))


@ai_study_bp.route("/upcoming", methods=["GET"])
@token_required
def upcoming():
    return jsonify(_svc().upcoming(_me(), int(request.args.get("days", 28))))


@ai_study_bp.route("/settings", methods=["GET"])
@token_required
def get_settings():
    return jsonify(_svc().get_settings(_me()))


@ai_study_bp.route("/settings", methods=["PUT"])
@token_required
def save_settings():
    data = _body()
    saved = _svc().save_settings(_me(), **{k: data.get(k) for k in (
        "reminders_enabled", "email_reminders", "share_with_tutor", "daily_card_limit")})
    return jsonify(saved)


@ai_study_bp.route("/reminders/me", methods=["POST"])
@token_required
def send_my_reminder():
    return jsonify(_svc().send_my_reminder(_me()))


@ai_study_bp.route("/reminders/send", methods=["POST"])
@token_required
def send_all_reminders():
    if not study_context.is_staff(_viewer()):
        raise PermissionError("Sending everyone's reminders is a staff action")
    return jsonify(_svc().send_all_reminders())


# ---- staff ----

@ai_study_bp.route("/staff/overview", methods=["GET"])
@token_required
def staff_overview():
    rows = _svc().staff_overview(_viewer(), request.args.get("module_code"))
    _log("view", "study_companion_overview")
    return jsonify({"items": rows, "total": len(rows)})


@ai_study_bp.route("/staff/students/<student_id>", methods=["GET"])
@token_required
def staff_student(student_id: str):
    if not study_context.is_staff(_viewer()):
        raise PermissionError("The student overview is for staff")
    detail = _svc().staff_student_detail(_viewer(), student_id)
    _log("view", "study_companion_student", student_id=student_id)
    return jsonify(detail)


@ai_study_bp.route("/staff/engagement-scan", methods=["POST"])
@token_required
def engagement_scan():
    if not study_context.is_staff(_viewer()):
        raise PermissionError("The engagement scan is a staff action")
    return jsonify(_svc().engagement_scan(actor=_viewer().get("username") or "staff"))

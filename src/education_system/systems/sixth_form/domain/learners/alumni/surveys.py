"""Sixth-form alumni — Survey module.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import secrets
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    SURVEY_INVITATION_TTL_DAYS,
    _log_action,
    logger,
)
from .db import (
    ValidationError,
    _connect,
    _require,
    init_db,
)


# ── Survey module ────────────────────────────────────────────────

# Recognised question types. Each entry maps to an alumnus field
# that may be auto-updated when the response comes in. ``None``
# means the answer is captured but not pushed back to the alumnus
# record.
SURVEY_QUESTION_TARGETS: dict[str, str | None] = {
    "current_role":     "current_role",
    "current_employer": "current_employer",
    "current_sector":   "current_sector",
    "current_location": "current_location",
    "country":          "country",
    "region":           "region",
    "email":            "email",
    "phone":            "phone",
    "linkedin":         "linkedin",
    "freeform":         None,
}


@dataclass
class Survey:
    survey_id: int
    name: str
    description: str | None
    questions: list[dict[str, Any]]
    status: str
    created_at: str


@dataclass
class SurveyInvitation:
    invitation_id: int
    survey_id: int
    alumni_id: int
    token: str
    sent_at: str | None
    completed_at: str | None
    expires_at: str


@dataclass
class SurveyResponse:
    response_id: int
    invitation_id: int
    answers: dict[str, Any]
    submitted_at: str


def _row_survey(r: db.Row) -> Survey:
    try:
        qs = _json.loads(r["questions_json"]) or []
    except Exception:
        logger.warning("Corrupt questions_json for survey #%s",
                         r["survey_id"], exc_info=True)
        qs = []
    return Survey(
        survey_id=r["survey_id"], name=r["name"],
        description=r["description"], questions=qs,
        status=r["status"], created_at=r["created_at"],
    )


def _row_invitation(r: db.Row) -> SurveyInvitation:
    return SurveyInvitation(
        invitation_id=r["invitation_id"], survey_id=r["survey_id"],
        alumni_id=r["alumni_id"], token=r["token"],
        sent_at=r["sent_at"], completed_at=r["completed_at"],
        expires_at=r["expires_at"],
    )


def _row_response(r: db.Row) -> SurveyResponse:
    try:
        ans = _json.loads(r["answers_json"]) or {}
    except Exception:
        logger.warning("Corrupt answers_json for response #%s",
                         r["response_id"], exc_info=True)
        ans = {}
    return SurveyResponse(
        response_id=r["response_id"],
        invitation_id=r["invitation_id"],
        answers=ans, submitted_at=r["submitted_at"],
    )


def create_survey(name: str,
                    questions: list[dict[str, Any]], *,
                    description: str | None = None) -> Survey:
    """Each question is a dict ``{"key": "...", "prompt": "...",
    "type": "current_role" | ... | "freeform"}``. Question
    ``type`` controls what (if anything) is written back to the
    alumnus profile when the response comes in."""
    init_db()
    name = _require(name, "Survey name").strip()
    if not questions:
        raise ValidationError("Survey needs at least one question")
    for i, q in enumerate(questions, 1):
        key = (q.get("key") or "").strip()
        if not key:
            raise ValidationError(
                f"Question {i} is missing 'key'")
        qtype = (q.get("type") or "freeform").strip()
        if qtype not in SURVEY_QUESTION_TARGETS:
            raise ValidationError(
                f"Question {i}: unknown type '{qtype}'. "
                f"Allowed: "
                f"{', '.join(sorted(SURVEY_QUESTION_TARGETS))}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_surveys
                   (name, description, questions_json, status)
               VALUES (?, ?, ?, 'Active')""",
            (name, (description or "").strip() or None,
             _json.dumps(questions)))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_surveys WHERE survey_id = ?",
            (cur.lastrowid,)).fetchone()
    out = _row_survey(r)
    _log_action("survey.create", survey_id=out.survey_id,
                  name=out.name, questions=len(out.questions))
    return out


def get_survey(survey_id: int) -> Survey | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_surveys WHERE survey_id = ?",
            (survey_id,)).fetchone()
    return _row_survey(r) if r else None


def list_surveys() -> list[Survey]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_surveys ORDER BY created_at DESC"
        ).fetchall()
    return [_row_survey(r) for r in rows]


def close_survey(survey_id: int) -> Survey:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_surveys SET status = 'Closed' "
            "WHERE survey_id = ?", (survey_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(f"No survey #{survey_id}")
    s = get_survey(survey_id)
    assert s is not None
    return s


def delete_survey(survey_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_surveys WHERE survey_id = ?",
            (survey_id,))
        conn.commit()
        return cur.rowcount > 0


def invite_to_survey(survey_id: int, alumni_id: int, *,
                       ttl_days: int = SURVEY_INVITATION_TTL_DAYS
                       ) -> SurveyInvitation:
    init_db()
    if get_survey(survey_id) is None:
        raise ValidationError(f"No survey #{survey_id}")
    tok = secrets.token_urlsafe(24)
    expires = (_dt.datetime.now()
                + _dt.timedelta(days=ttl_days)
                ).strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        try:
            conn.execute(
                """INSERT INTO alumni_survey_invitations
                       (survey_id, alumni_id, token, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (survey_id, alumni_id, tok, expires))
            conn.commit()
        except db.IntegrityError:
            raise ValidationError(
                f"Alumnus #{alumni_id} already invited to "
                f"survey #{survey_id}") from None
        r = conn.execute(
            "SELECT * FROM alumni_survey_invitations "
            "WHERE survey_id = ? AND alumni_id = ?",
            (survey_id, alumni_id)).fetchone()
    return _row_invitation(r)


def mark_invitation_sent(invitation_id: int) -> SurveyInvitation:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_survey_invitations "
            "SET sent_at = datetime('now') WHERE invitation_id = ?",
            (invitation_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No invitation #{invitation_id}")
        r = conn.execute(
            "SELECT * FROM alumni_survey_invitations "
            "WHERE invitation_id = ?",
            (invitation_id,)).fetchone()
    return _row_invitation(r)


def list_invitations(survey_id: int) -> list[SurveyInvitation]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_survey_invitations "
            "WHERE survey_id = ? ORDER BY invitation_id",
            (survey_id,)).fetchall()
    return [_row_invitation(r) for r in rows]


def send_survey_invitations(survey_id: int,
                              filters: dict[str, Any], *,
                              staff_id: str | None = None,
                              subject: str | None = None,
                              body_template: str | None = None
                              ) -> tuple[int, int]:
    """Invite every alumnus matching ``filters`` who has an email
    and ``opt_in_email``. Tokens are minted, an outgoing message is
    logged via the shared messages module, and each invitation is
    stamped ``sent_at``. Returns ``(sent, skipped)``."""
    init_db()
    survey = get_survey(survey_id)
    if survey is None:
        raise ValidationError(f"No survey #{survey_id}")
    rows = list_alumni(**filters)
    sent = skipped = 0
    msg = _messages_module()
    subject = subject or f"Help us update your alumni record: "\
                            f"{survey.name}"
    body_template = body_template or (
        "Hi {first_name},\n\n"
        "We're refreshing our alumni records and would love a quick "
        "update from you. Please open this link to fill in a short "
        "survey:\n\n"
        "{survey_link}\n\n"
        "Thanks,\nSixth-form alumni team")
    for a in rows:
        if not a.email:
            skipped += 1
            continue
        try:
            prefs = get_channel_prefs(a.alumni_id)
        except ValidationError:
            skipped += 1
            continue
        if not prefs.opt_in_email:
            skipped += 1
            continue
        try:
            inv = invite_to_survey(survey_id, a.alumni_id)
        except ValidationError:
            # Already invited — skip; existing token still works.
            skipped += 1
            continue
        link = f"alumni-survey/{inv.token}"
        body = _render(body_template, {
            "first_name":     a.first_name,
            "preferred_name": a.preferred_name or a.first_name,
            "last_name":      a.last_name,
            "survey_link":    link,
            "survey_name":    survey.name,
        })
        try:
            out = msg.create_message({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   "General",
                "status":     "Queued",
                "subject":    subject,
                "body":       body,
                "alumni_id":  a.alumni_id,
                "to_name":    a.full_name,
                "to_address": a.email,
                "staff_id":   (staff_id or "").strip().upper()
                                or None,
            })
            # Through the outbox: the invitation is stamped sent only
            # once the e-mail was accepted (sent, or queued/held by
            # the delivery mode) — not when the send failed.
            out = msg.send_message(out.message_id)
            if out.status == "Failed":
                skipped += 1
                continue
            mark_invitation_sent(inv.invitation_id)
            sent += 1
        except Exception:
            logger.exception(
                "Failed to send survey invitation for alumnus #%d",
                a.alumni_id)
            skipped += 1
    _log_action("survey.invite_cohort", actor=staff_id,
                  survey_id=survey_id, sent=sent, skipped=skipped,
                  filters=str(filters))
    return sent, skipped


def validate_survey_token(token: str) -> SurveyInvitation | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_survey_invitations WHERE token = ?",
            (token,)).fetchone()
        if r is None:
            return None
        inv = _row_invitation(r)
    if inv.completed_at:
        return None
    now_iso = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if inv.expires_at < now_iso:
        return None
    return inv


def submit_survey_response(token: str,
                             answers: dict[str, Any], *,
                             apply_to_profile: bool = True,
                             actor: str | None = None
                             ) -> SurveyResponse:
    """Record a survey response and (optionally) push the
    well-known answers back into the alumnus profile. ``answers``
    keys must match a question ``key`` defined on the survey."""
    inv = validate_survey_token(token)
    if inv is None:
        raise ValidationError("Invalid or expired survey token")
    survey = get_survey(inv.survey_id)
    assert survey is not None
    init_db()
    with _connect() as conn:
        try:
            conn.execute(
                """INSERT INTO alumni_survey_responses
                       (invitation_id, answers_json)
                   VALUES (?, ?)""",
                (inv.invitation_id, _json.dumps(answers)))
        except db.IntegrityError:
            raise ValidationError(
                "Response already recorded for this invitation") \
                from None
        conn.execute(
            "UPDATE alumni_survey_invitations "
            "SET completed_at = datetime('now') "
            "WHERE invitation_id = ?", (inv.invitation_id,))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_survey_responses "
            "WHERE invitation_id = ?",
            (inv.invitation_id,)).fetchone()

    if apply_to_profile:
        updates: dict[str, Any] = {}
        for q in survey.questions:
            qkey  = (q.get("key") or "").strip()
            qtype = (q.get("type") or "freeform").strip()
            target = SURVEY_QUESTION_TARGETS.get(qtype)
            if not target:
                continue
            if qkey in answers and answers[qkey] not in (None, ""):
                updates[target] = answers[qkey]
        if updates:
            try:
                update_alumnus(inv.alumni_id, updates,
                                 actor=actor or "survey")
            except ValidationError as e:
                logger.warning(
                    "Survey response for alumnus #%d failed to "
                    "apply: %s", inv.alumni_id, e)
    _log_action("survey.response_submitted",
                  actor=actor or "survey",
                  alumni_id=inv.alumni_id,
                  survey_id=inv.survey_id,
                  invitation_id=inv.invitation_id,
                  applied_to_profile=apply_to_profile)
    return _row_response(r)


def list_survey_responses(survey_id: int
                             ) -> list[SurveyResponse]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT r.* FROM alumni_survey_responses r "
            "JOIN alumni_survey_invitations i "
            "  ON i.invitation_id = r.invitation_id "
            "WHERE i.survey_id = ? "
            "ORDER BY r.submitted_at DESC",
            (survey_id,)).fetchall()
    return [_row_response(r) for r in rows]


@dataclass
class SurveyStats:
    survey_id: int
    invited: int
    sent: int
    completed: int


def survey_stats(survey_id: int) -> SurveyStats:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS invited, "
            "       COUNT(sent_at) AS sent, "
            "       COUNT(completed_at) AS completed "
            "FROM alumni_survey_invitations WHERE survey_id = ?",
            (survey_id,)).fetchone()
    return SurveyStats(
        survey_id=survey_id, invited=int(r["invited"]),
        sent=int(r["sent"]), completed=int(r["completed"]))


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .records import (  # noqa: E402,F401
    list_alumni,
    update_alumnus,
)
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
from .comms import (  # noqa: E402,F401
    _messages_module,
    _render,
    get_channel_prefs,
)

"""Surveys data layer for Sixth Form System.

Two tables:
- `surveys`: survey definition with JSON-encoded `questions_json`
  spec (list of {prompt, type, choices?, required?}). Audience,
  open/close dates and lifecycle workflow.
- `survey_responses`: per-respondent answers stored as JSON
  (mapping question index → value). FK cascade on survey delete.

Question types: Likert (1-5), Yes/No, Single Choice, Multi Choice,
Text, Number. Aggregation helpers compute counts / means as
appropriate for each type.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.systems.sixth_form.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

AUDIENCES: tuple[str, ...] = (
    "Students",
    "Parents / Carers",
    "Staff",
    "Mixed",
    "Public",
    "Governors",
    "Other",
)
DEFAULT_AUDIENCE = "Students"

STATUSES: tuple[str, ...] = (
    "Draft",
    "Open",
    "Closed",
    "Archived",
)
DEFAULT_STATUS = "Draft"

QUESTION_TYPES: tuple[str, ...] = (
    "Likert",
    "Yes/No",
    "Single Choice",
    "Multi Choice",
    "Text",
    "Number",
)


class ValidationError(Exception):
    pass


@dataclass
class Question:
    prompt: str
    type: str
    choices: list[str] = field(default_factory=list)
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "type": self.type,
            "choices": list(self.choices),
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Question":
        return cls(
            prompt=str(d.get("prompt", "")),
            type=str(d.get("type", "Text")),
            choices=list(d.get("choices") or []),
            required=bool(d.get("required")),
        )


@dataclass
class Survey:
    survey_id: int
    name: str
    description: str | None
    audience: str
    status: str
    anonymous: bool
    open_on: str | None
    close_on: str | None
    created_by: str | None
    questions: list[Question]
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status == "Open"

    @property
    def is_editable(self) -> bool:
        return self.status in ("Draft",)


@dataclass
class Response:
    response_id: int
    survey_id: int
    submitted_on: str
    respondent_name: str | None
    respondent_role: str | None
    anonymous: bool
    answers: dict[int, Any]
    notes: str | None
    created_on: str


@dataclass
class SurveysSummary:
    total: int = 0
    drafts: int = 0
    open_count: int = 0
    closed: int = 0
    archived: int = 0
    total_responses: int = 0
    by_audience: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


@dataclass
class QuestionStat:
    index: int
    prompt: str
    type: str
    answered: int
    skipped: int
    counts: dict[str, int]
    mean: float | None
    text_samples: list[str]


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.SURVEYS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS surveys (
                survey_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                audience TEXT NOT NULL,
                status TEXT NOT NULL,
                anonymous INTEGER NOT NULL DEFAULT 1,
                open_on TEXT,
                close_on TEXT,
                created_by TEXT,
                questions_json TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS survey_responses (
                response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id INTEGER NOT NULL,
                submitted_on TEXT NOT NULL,
                respondent_name TEXT,
                respondent_role TEXT,
                anonymous INTEGER NOT NULL DEFAULT 1,
                answers_json TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                FOREIGN KEY(survey_id) REFERENCES surveys(survey_id)
                  ON DELETE CASCADE
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _validate_questions(qs: list[Any]) -> list[Question]:
    if not isinstance(qs, list) or not qs:
        raise ValidationError(
            "At least one question is required")
    out: list[Question] = []
    for i, item in enumerate(qs, 1):
        if isinstance(item, Question):
            q = item
        elif isinstance(item, dict):
            q = Question.from_dict(item)
        else:
            raise ValidationError(
                f"Question {i}: must be a dict or Question")
        if not q.prompt:
            raise ValidationError(
                f"Question {i}: prompt is required")
        if q.type not in QUESTION_TYPES:
            raise ValidationError(
                f"Question {i}: type must be one of: "
                f"{', '.join(QUESTION_TYPES)}")
        if q.type in ("Single Choice", "Multi Choice"):
            if not q.choices:
                raise ValidationError(
                    f"Question {i}: choices required for "
                    f"{q.type}")
            for c in q.choices:
                if not isinstance(c, str) or not c.strip():
                    raise ValidationError(
                        f"Question {i}: choices must be "
                        "non-empty strings")
        out.append(q)
    return out


def _validate_survey_payload(p: dict[str, Any], *,
                                  existing_id: int | None = None
                                  ) -> dict[str, Any]:
    out = dict(p)
    out["name"] = (out.get("name") or "").strip()
    if not out["name"]:
        raise ValidationError("Name is required")
    audience = (out.get("audience") or DEFAULT_AUDIENCE).strip()
    if audience not in AUDIENCES:
        raise ValidationError(
            f"Audience must be one of: {', '.join(AUDIENCES)}")
    out["audience"] = audience
    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status
    _check_date("Open on",  out.get("open_on"))
    _check_date("Close on", out.get("close_on"))
    if (out.get("open_on") and out.get("close_on")
            and out["close_on"] < out["open_on"]):
        raise ValidationError(
            "Close date must be on or after open date")
    for k in ("description", "created_by", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("open_on", "close_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    out["anonymous"] = bool(out.get("anonymous", True))
    qs = out.get("questions")
    if qs is None:
        raise ValidationError("Questions are required")
    out["questions"] = _validate_questions(qs)

    # Uniqueness of name
    with _connect() as conn:
        row = conn.execute(
            "SELECT survey_id FROM surveys WHERE name=?",
            (out["name"],)).fetchone()
    if row and row["survey_id"] != existing_id:
        raise ValidationError(
            f"A survey named {out['name']!r} already exists")
    return out


def _row_survey(r: sqlite3.Row) -> Survey:
    qs_raw = json.loads(r["questions_json"] or "[]")
    questions = [Question.from_dict(q) for q in qs_raw]
    return Survey(
        survey_id=r["survey_id"],
        name=r["name"],
        description=r["description"],
        audience=r["audience"],
        status=r["status"],
        anonymous=bool(r["anonymous"]),
        open_on=r["open_on"],
        close_on=r["close_on"],
        created_by=r["created_by"],
        questions=questions,
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def _row_response(r: sqlite3.Row) -> Response:
    raw = json.loads(r["answers_json"] or "{}")
    answers = {int(k): v for k, v in raw.items()}
    return Response(
        response_id=r["response_id"],
        survey_id=r["survey_id"],
        submitted_on=r["submitted_on"],
        respondent_name=r["respondent_name"],
        respondent_role=r["respondent_role"],
        anonymous=bool(r["anonymous"]),
        answers=answers,
        notes=r["notes"],
        created_on=r["created_on"],
    )


# ── Survey CRUD ─────────────────────────────────────────────────

def create_survey(payload: dict[str, Any]) -> Survey:
    init_db()
    p = _validate_survey_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    qjson = json.dumps([q.to_dict() for q in p["questions"]])
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO surveys (
              name, description, audience, status, anonymous,
              open_on, close_on, created_by,
              questions_json, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["name"], p["description"], p["audience"],
            p["status"], 1 if p["anonymous"] else 0,
            p["open_on"], p["close_on"], p["created_by"],
            qjson, p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_survey(new_id)


def update_survey(survey_id: int,
                       payload: dict[str, Any]) -> Survey:
    init_db()
    existing = get_survey(survey_id)
    if existing is None:
        raise ValidationError(f"No survey with id {survey_id}")
    p = _validate_survey_payload(payload, existing_id=survey_id)
    if not existing.is_editable and existing.questions:
        # Questions are locked once a survey opens (to keep response
        # answer keys stable). Allow only metadata/status changes.
        if [q.to_dict() for q in p["questions"]] != \
                [q.to_dict() for q in existing.questions]:
            raise ValidationError(
                "Questions can only be edited while in Draft")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    qjson = json.dumps([q.to_dict() for q in p["questions"]])
    with _connect() as conn:
        conn.execute("""
            UPDATE surveys SET
              name=?, description=?, audience=?, status=?, anonymous=?,
              open_on=?, close_on=?, created_by=?,
              questions_json=?, notes=?, updated_on=?
            WHERE survey_id=?
        """, (
            p["name"], p["description"], p["audience"],
            p["status"], 1 if p["anonymous"] else 0,
            p["open_on"], p["close_on"], p["created_by"],
            qjson, p["notes"], now, survey_id,
        ))
    return get_survey(survey_id)


def delete_survey(survey_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM surveys WHERE survey_id=?",
            (survey_id,))
        return cur.rowcount > 0


def get_survey(survey_id: int) -> Survey | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM surveys WHERE survey_id=?",
            (survey_id,)).fetchone()
        return _row_survey(r) if r else None


def list_surveys(*,
                      audience: str | None = None,
                      status: str | None = None,
                      created_by_like: str | None = None,
                      name_like: str | None = None,
                      open_only: bool = False,
                      ) -> list[Survey]:
    init_db()
    sql = "SELECT * FROM surveys WHERE 1=1"
    params: list[Any] = []
    if audience:
        sql += " AND audience=?"
        params.append(audience)
    if status:
        sql += " AND status=?"
        params.append(status)
    if created_by_like:
        sql += " AND created_by LIKE ?"
        params.append(f"%{created_by_like}%")
    if name_like:
        sql += " AND name LIKE ?"
        params.append(f"%{name_like}%")
    if open_only:
        sql += " AND status='Open'"
    sql += " ORDER BY survey_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_survey(r) for r in rows]


# ── Workflow ─────────────────────────────────────────────────────

def _to_dict(s: Survey) -> dict[str, Any]:
    return {
        "name": s.name,
        "description": s.description,
        "audience": s.audience,
        "status": s.status,
        "anonymous": s.anonymous,
        "open_on": s.open_on,
        "close_on": s.close_on,
        "created_by": s.created_by,
        "questions": s.questions,
        "notes": s.notes,
    }


def publish(survey_id: int, *,
                open_on: str | None = None) -> Survey:
    s = get_survey(survey_id)
    if s is None:
        raise ValidationError(f"No survey with id {survey_id}")
    if not s.questions:
        raise ValidationError(
            "Survey must have at least one question")
    data = _to_dict(s)
    data["status"] = "Open"
    if not data["open_on"]:
        data["open_on"] = open_on or _dt.date.today().isoformat()
    return update_survey(survey_id, data)


def close_survey(survey_id: int, *,
                     close_on: str | None = None) -> Survey:
    s = get_survey(survey_id)
    if s is None:
        raise ValidationError(f"No survey with id {survey_id}")
    data = _to_dict(s)
    data["status"] = "Closed"
    if not data["close_on"]:
        data["close_on"] = close_on or _dt.date.today().isoformat()
    return update_survey(survey_id, data)


def archive(survey_id: int) -> Survey:
    s = get_survey(survey_id)
    if s is None:
        raise ValidationError(f"No survey with id {survey_id}")
    return update_survey(survey_id,
                              {**_to_dict(s), "status": "Archived"})


def set_status(survey_id: int, new_status: str) -> Survey:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    s = get_survey(survey_id)
    if s is None:
        raise ValidationError(f"No survey with id {survey_id}")
    return update_survey(survey_id,
                              {**_to_dict(s), "status": new_status})


# ── Responses ─────────────────────────────────────────────────────

def _validate_answer(q: Question, value: Any) -> Any:
    if value in (None, ""):
        if q.required:
            raise ValidationError(
                f"{q.prompt!r}: an answer is required")
        return None
    if q.type == "Likert":
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"{q.prompt!r}: Likert answer must be 1-5")
        if v not in (1, 2, 3, 4, 5):
            raise ValidationError(
                f"{q.prompt!r}: Likert answer must be 1-5")
        return v
    if q.type == "Yes/No":
        s = str(value).strip().lower()
        if s in ("yes", "y", "true", "1"):
            return "Yes"
        if s in ("no", "n", "false", "0"):
            return "No"
        raise ValidationError(
            f"{q.prompt!r}: answer must be Yes or No")
    if q.type == "Single Choice":
        s = str(value).strip()
        if s not in q.choices:
            raise ValidationError(
                f"{q.prompt!r}: answer must be one of: "
                f"{', '.join(q.choices)}")
        return s
    if q.type == "Multi Choice":
        if isinstance(value, str):
            parts = [v.strip() for v in value.split(",")
                       if v.strip()]
        elif isinstance(value, (list, tuple)):
            parts = [str(v).strip() for v in value if str(v).strip()]
        else:
            raise ValidationError(
                f"{q.prompt!r}: multi-choice expects a list "
                "or comma-separated string")
        for p in parts:
            if p not in q.choices:
                raise ValidationError(
                    f"{q.prompt!r}: {p!r} not in choices")
        return parts
    if q.type == "Number":
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"{q.prompt!r}: answer must be a number")
    # Text
    return str(value).strip()


def submit_response(survey_id: int, *,
                        answers: dict[int, Any],
                        respondent_name: str | None = None,
                        respondent_role: str | None = None,
                        anonymous: bool | None = None,
                        submitted_on: str | None = None,
                        notes: str | None = None) -> Response:
    init_db()
    s = get_survey(survey_id)
    if s is None:
        raise ValidationError(f"No survey with id {survey_id}")
    if s.status != "Open":
        raise ValidationError(
            f"Survey is not Open (current: {s.status})")
    if anonymous is None:
        anonymous = s.anonymous
    if not anonymous and not respondent_name:
        raise ValidationError(
            "Respondent name required for non-anonymous response")

    validated: dict[int, Any] = {}
    for idx, q in enumerate(s.questions):
        if idx in answers:
            v = _validate_answer(q, answers[idx])
        elif q.required:
            raise ValidationError(
                f"{q.prompt!r}: an answer is required")
        else:
            continue
        if v is not None:
            validated[idx] = v

    when = (submitted_on or _dt.date.today().isoformat())
    _check_date("Submitted on", when)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    answer_json = json.dumps(
        {str(k): v for k, v in validated.items()})
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO survey_responses (
              survey_id, submitted_on, respondent_name,
              respondent_role, anonymous, answers_json,
              notes, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            survey_id, when,
            (respondent_name or "").strip() or None
            if not anonymous else None,
            (respondent_role or "").strip() or None,
            1 if anonymous else 0,
            answer_json,
            (notes or "").strip() or None, now,
        ))
        new_id = cur.lastrowid
    return get_response(new_id)


def delete_response(response_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM survey_responses WHERE response_id=?",
            (response_id,))
        return cur.rowcount > 0


def get_response(response_id: int) -> Response | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM survey_responses "
            "WHERE response_id=?", (response_id,)).fetchone()
        return _row_response(r) if r else None


def list_responses(survey_id: int) -> list[Response]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM survey_responses "
            "WHERE survey_id=? "
            "ORDER BY submitted_on DESC, response_id DESC",
            (survey_id,)).fetchall()
    return [_row_response(r) for r in rows]


def response_count(survey_id: int) -> int:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM survey_responses "
            "WHERE survey_id=?", (survey_id,)).fetchone()
    return int(row["c"]) if row else 0


# ── Analysis ─────────────────────────────────────────────────────

def question_stats(survey_id: int) -> list[QuestionStat]:
    s = get_survey(survey_id)
    if s is None:
        raise ValidationError(f"No survey with id {survey_id}")
    responses = list_responses(survey_id)
    stats: list[QuestionStat] = []
    for idx, q in enumerate(s.questions):
        counts: dict[str, int] = {}
        numeric: list[float] = []
        text_samples: list[str] = []
        answered = 0
        for resp in responses:
            if idx not in resp.answers:
                continue
            answered += 1
            v = resp.answers[idx]
            if q.type == "Likert":
                numeric.append(float(v))
                counts[str(v)] = counts.get(str(v), 0) + 1
            elif q.type == "Yes/No":
                counts[str(v)] = counts.get(str(v), 0) + 1
            elif q.type == "Single Choice":
                counts[str(v)] = counts.get(str(v), 0) + 1
            elif q.type == "Multi Choice":
                if isinstance(v, list):
                    for item in v:
                        counts[str(item)] = counts.get(
                            str(item), 0) + 1
            elif q.type == "Number":
                try:
                    numeric.append(float(v))
                except (TypeError, ValueError):
                    pass
            elif q.type == "Text":
                txt = str(v).strip()
                if txt and len(text_samples) < 10:
                    text_samples.append(txt)
        mean = (round(sum(numeric) / len(numeric), 2)
                  if numeric else None)
        stats.append(QuestionStat(
            index=idx,
            prompt=q.prompt,
            type=q.type,
            answered=answered,
            skipped=len(responses) - answered,
            counts=counts,
            mean=mean,
            text_samples=text_samples,
        ))
    return stats


def summary() -> SurveysSummary:
    rows = list_surveys()
    out = SurveysSummary(total=len(rows))
    if not rows:
        return out
    for s in rows:
        if s.status == "Draft":
            out.drafts += 1
        elif s.status == "Open":
            out.open_count += 1
        elif s.status == "Closed":
            out.closed += 1
        elif s.status == "Archived":
            out.archived += 1
        out.by_audience[s.audience] = (
            out.by_audience.get(s.audience, 0) + 1)
        out.by_status[s.status] = (
            out.by_status.get(s.status, 0) + 1)
        out.total_responses += response_count(s.survey_id)
    return out


__all__ = [
    "AUDIENCES", "DEFAULT_AUDIENCE",
    "STATUSES", "DEFAULT_STATUS",
    "QUESTION_TYPES",
    "ValidationError",
    "Question", "Survey", "Response",
    "SurveysSummary", "QuestionStat",
    "init_db",
    "create_survey", "update_survey", "delete_survey",
    "get_survey", "list_surveys",
    "publish", "close_survey", "archive", "set_status",
    "submit_response", "delete_response",
    "get_response", "list_responses", "response_count",
    "question_stats", "summary",
]

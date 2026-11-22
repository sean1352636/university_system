"""Looking after the people who use the university chatbot.

* **Personal data** is only ever the asker's own: :func:`own_student_id`
  resolves the signed-in person, and a student number typed into a message
  that is not theirs is refused (:func:`personal_access`).
* **Crisis messages** (suicide, self-harm, being in danger) get an
  immediate reply with real UK contacts (999, NHS 111, Samaritans, Shout)
  and the university's own contacts from the settings, open a crisis case,
  and — after the commit — raise a CRITICAL safeguarding concern
  (:func:`send_safeguarding_alert`). One alert per person per day; later
  messages are added to the open case.
* **"Speak to a person"** opens a case in a queue that chatbot agents work;
  their answer arrives in the person's inbox. The reply promise shown is
  the one the university sets, never an invented SLA.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from education_system.systems.university.application.research import access as rows
from education_system.systems.university.infrastructure.database.schemas import (
    chatbot_care_schema as schema,
)

ADMIN_ROLES = ("admin", "administrator", "superadmin")
SETTINGS = {
    "counselling_contact": "",
    "wellbeing_contact": "",
    "out_of_hours_number": "",
    "security_number": "",
    "reply_promise": "A member of staff will reply in your inbox, usually within two working "
                     "days.",
    "retention_days": "180",
}
CRISIS_PATTERNS = tuple(re.compile(p, re.I) for p in (
    r"\bsuicid", r"\bkill(ing)? my ?self\b", r"\bend(ing)? (it all|my life)\b",
    r"\bwant(ed)? to die\b", r"\bdon'?t want to (live|be alive|be here)\b",
    r"\bself[- ]?harm", r"\bhurt(ing)? my ?self\b", r"\bcut(ting)? my ?self\b",
    r"\boverdos", r"\bno (reason|point) (to|in) (live|living|go on)\b",
    r"\bcan'?t go on\b", r"\b(i'?m|i am) (in danger|not safe)\b",
    r"\bsomeone (is )?(hurting|abusing) me\b",
))

dicts, one, now = rows.dicts, rows.one, rows.now


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


def audit(conn, actor, entity, entity_id, action, detail=None) -> None:
    conn.execute("INSERT INTO chatbot_audit (entity, entity_id, action, actor, detail) VALUES "
                 "(?, ?, ?, ?, ?)", (entity, str(entity_id), action, actor,
                                     json.dumps(detail, default=str) if detail else None))


# ── staff roles ─────────────────────────────────────────────────────────


def holds(conn, username, role, user_role="") -> bool:
    if str(user_role or "").lower() in ADMIN_ROLES:
        return True
    ensure(conn)
    return conn.execute("SELECT 1 FROM chatbot_roles WHERE username = ? AND role = ?",
                        (username, role)).fetchone() is not None


def _require(allowed, message):
    if not allowed:
        raise PermissionError(message)


def grant(conn, actor, actor_role, username, role) -> None:
    ensure(conn)
    _require(str(actor_role).lower() in ADMIN_ROLES, "Only an administrator can do this")
    if role not in ("agent", "editor"):
        raise ValueError("Role must be agent or editor")
    if not rows.is_staff_username(conn, username):
        raise ValueError(f"No member of staff with username {username!r}")
    conn.execute("INSERT OR IGNORE INTO chatbot_roles (username, role, granted_by) VALUES "
                 "(?, ?, ?)", (username, role, actor))
    audit(conn, actor, "role", username, "granted", {"role": role})


def revoke(conn, actor, actor_role, username, role) -> None:
    ensure(conn)
    _require(str(actor_role).lower() in ADMIN_ROLES, "Only an administrator can do this")
    if not conn.execute("DELETE FROM chatbot_roles WHERE username = ? AND role = ?",
                        (username, role)).rowcount:
        raise ValueError("That person does not hold that role")
    audit(conn, actor, "role", username, "revoked", {"role": role})


def roles(conn) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM chatbot_roles ORDER BY role, username"))


def agents(conn) -> list[str]:
    ensure(conn)
    found = [r[0] for r in conn.execute("SELECT username FROM chatbot_roles WHERE role = "
                                        "'agent'")]
    return found or [r[0] for r in conn.execute("SELECT username FROM users WHERE "
                                                "LOWER(COALESCE(role, '')) = 'admin'")]


# ── settings ────────────────────────────────────────────────────────────


def settings(conn) -> dict:
    ensure(conn)
    out = dict(SETTINGS)
    out.update({k: v for k, v in conn.execute("SELECT key, value FROM chatbot_settings")})
    return out


def set_setting(conn, actor, actor_role, key, value) -> None:
    ensure(conn)
    _require(str(actor_role).lower() in ADMIN_ROLES, "Only an administrator can change this")
    if key not in SETTINGS:
        raise ValueError("Unknown setting")
    value = str(value or "").strip()
    if key == "retention_days" and (not value.isdigit() or not 7 <= int(value) <= 3650):
        raise ValueError("Keep conversations for 7 to 3650 days")
    if "XXX" in value.upper():
        raise ValueError("That looks like a placeholder, not a real contact")
    conn.execute("INSERT INTO chatbot_settings (key, value, updated_by) VALUES (?, ?, ?) ON "
                 "CONFLICT (key) DO UPDATE SET value = excluded.value, updated_by = "
                 "excluded.updated_by, updated_at = datetime('now')", (key, value, actor))
    audit(conn, actor, "setting", key, "set", {"value": value})


def university_contacts(conn) -> list[tuple[str, str]]:
    s = settings(conn)
    labels = (("counselling_contact", "University counselling"),
              ("wellbeing_contact", "Student wellbeing"),
              ("out_of_hours_number", "University out-of-hours support"),
              ("security_number", "Campus security (on campus, any time)"))
    return [(label, s[key]) for key, label in labels if s.get(key)]


# ── whose data ──────────────────────────────────────────────────────────


def own_student_id(conn, user_id) -> str | None:
    """The signed-in person's student number (None for staff/anonymous)."""
    ref = str(user_id or "").strip()
    if not ref or ref == "anonymous":
        return None
    row = conn.execute("SELECT student_id FROM users WHERE (username = ? OR CAST(id AS TEXT) = ?) "
                       "AND student_id IS NOT NULL LIMIT 1", (ref, ref)).fetchone()
    if row:
        return row[0]
    row = conn.execute("SELECT student_id FROM students WHERE student_id = ?", (ref,)).fetchone()
    return row[0] if row else None


def personal_access(conn, user_id, typed_id=None) -> tuple[str | None, str | None]:
    """``(student_id, refusal)``: the asker's own number, or why not."""
    own = own_student_id(conn, user_id)
    if typed_id and str(typed_id).strip() and own and str(typed_id).strip() != own:
        return None, ("I can only show your own records. Staff who need another student's "
                      "details should use the student record screens.")
    if typed_id and not own:
        return None, ("I can't show another person's records here. Sign in as yourself to see "
                      "your own.")
    if not own:
        return None, "Please sign in as a student to see your own records."
    return own, None


# ── crisis ──────────────────────────────────────────────────────────────


def is_crisis(message) -> bool:
    text = str(message or "")
    return any(p.search(text) for p in CRISIS_PATTERNS)


def crisis_reply(conn) -> str:
    lines = ["I'm really sorry you're feeling like this. You don't have to go through it alone.",
             "",
             "If you are in immediate danger or have hurt yourself, call 999 now.",
             "• Samaritans: call 116 123 (free, any time, day or night)",
             "• Shout: text SHOUT to 85258 (free, 24/7)",
             "• NHS 111: call 111 (in England choose the mental health option)"]
    contacts = university_contacts(conn)
    if contacts:
        lines.append("")
        lines += [f"• {label}: {value}" for label, value in contacts]
    lines += ["", "I've also let the university's safeguarding team know so someone can check "
                  "in with you."]
    return "\n".join(lines)


def raise_crisis(conn, username, message, conversation_id=None) -> dict:
    """Open (or add to) a crisis case. Returns ``{"case_id", "alert"}`` —
    ``alert`` is set when a new safeguarding concern must be raised after
    the commit."""
    ensure(conn)
    since = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    open_case = one(conn, "SELECT * FROM chatbot_cases WHERE username = ? AND kind = 'crisis' AND "
                          "status <> 'closed' AND created_at >= ? ORDER BY case_id DESC LIMIT 1",
                    (username, since))
    if open_case:
        conn.execute("UPDATE chatbot_cases SET message = message || ? WHERE case_id = ?",
                     (f"\n[{now()}] {message}", open_case["case_id"]))
        return {"case_id": open_case["case_id"], "alert": None}
    cid = conn.execute("INSERT INTO chatbot_cases (username, kind, message, conversation_id) "
                       "VALUES (?, 'crisis', ?, ?)", (username, message,
                                                      conversation_id)).lastrowid
    audit(conn, "chatbot", "case", cid, "crisis_opened")
    row = conn.execute("SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')), "
                       "role FROM users WHERE username = ? OR student_id = ? LIMIT 1",
                       (username, username)).fetchone()
    return {"case_id": int(cid),
            "alert": {"username": username, "full_name": (row[0] if row else "") or username,
                      "role": row[1] if row else "student", "message": message}}


def send_safeguarding_alert(result) -> int | None:
    """After commit: raise a CRITICAL safeguarding concern and link it."""
    alert = (result or {}).get("alert")
    if not alert:
        return None
    try:
        from education_system.systems.university.domains.safeguarding.application.services import (
            submissions,
        )
        from education_system.systems.university.domains.safeguarding.domain.analysis import (
            RiskCategory,
        )
        # Categories map a category to the text that raised it (as the
        # safeguarding wizard records them); self-harm triggers mandatory
        # reporting to the safeguarding lead.
        snippet = alert["message"][:300]
        sid = submissions.save_submission(
            {"username": alert["username"], "full_name": alert["full_name"],
             "role": alert["role"]},
            f"Raised automatically by the university chatbot.\n\nMessage:\n{alert['message']}",
            "CRITICAL", {RiskCategory.SELF_HARM: [snippet], RiskCategory.MENTAL_HEALTH: []},
            consent_contact=True)
    except Exception:
        return None
    try:
        from education_system.systems.university.infrastructure.database.db import transaction
        with transaction() as conn:
            conn.execute("UPDATE chatbot_cases SET safeguarding_case_id = ? WHERE case_id = ?",
                         (sid, result["case_id"]))
    except Exception:
        pass
    return sid


# ── asking for a person ─────────────────────────────────────────────────


def open_case(conn, username, message, conversation_id=None) -> dict:
    """Queue the question for a person. Returns ``{"case_id", "reply",
    "emails"}``."""
    ensure(conn)
    if not username or username == "anonymous":
        return {"case_id": None, "emails": [],
                "reply": "Please sign in so a member of staff can reply to you, or contact the "
                         "student services desk."}
    cid = conn.execute("INSERT INTO chatbot_cases (username, kind, message, conversation_id) "
                       "VALUES (?, 'human_help', ?, ?)", (username, message,
                                                          conversation_id)).lastrowid
    audit(conn, username, "case", cid, "opened")
    emails = rows.notify(conn, agents(conn), "Chatbot: a student asked for a person",
                         f"Case {cid}: {message[:300]}")
    promise = settings(conn)["reply_promise"]
    return {"case_id": int(cid), "emails": emails,
            "reply": f"I've passed your question to a member of staff (case {cid}). {promise}"}


def case(conn, case_id) -> dict:
    ensure(conn)
    row = one(conn, "SELECT * FROM chatbot_cases WHERE case_id = ?", (case_id,))
    if not row:
        raise ValueError("No such case")
    return row


def _can_work(conn, username, role, row) -> bool:
    if row["kind"] == "crisis":
        return str(role).lower() in ADMIN_ROLES
    return holds(conn, username, "agent", role)


def cases(conn, username, role, status="open") -> list[dict]:
    ensure(conn)
    _require(holds(conn, username, "agent", role), "Only chatbot agents can see the queue")
    where = "" if not status else ("WHERE status IN ('open', 'assigned')" if status == "open"
                                   else "WHERE status = ?")
    params = () if not status or status == "open" else (status,)
    found = dicts(conn.execute(f"SELECT * FROM chatbot_cases {where} ORDER BY kind = 'crisis' "
                               "DESC, created_at", params))
    return [c for c in found if _can_work(conn, username, role, c)]


def my_cases(conn, username) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT case_id, kind, message, status, answer, answered_at, "
                              "created_at FROM chatbot_cases WHERE username = ? AND kind = "
                              "'human_help' ORDER BY case_id DESC", (username,)))


def assign(conn, username, role, case_id, assignee) -> None:
    row = case(conn, case_id)
    _require(_can_work(conn, username, role, row), "You cannot work on this case")
    if not holds(conn, assignee, "agent") and assignee != username:
        raise ValueError(f"{assignee} is not a chatbot agent")
    conn.execute("UPDATE chatbot_cases SET assigned_to = ?, status = 'assigned' WHERE case_id = ?",
                 (assignee, case_id))
    audit(conn, username, "case", case_id, "assigned", {"to": assignee})


def answer(conn, username, role, case_id, text) -> list:
    row = case(conn, case_id)
    _require(_can_work(conn, username, role, row), "You cannot work on this case")
    if row["status"] in ("answered", "closed"):
        raise ValueError("This case has already been answered")
    text = rows.text(text, "Answer", True)
    conn.execute("UPDATE chatbot_cases SET answer = ?, answered_by = ?, answered_at = ?, status = "
                 "'answered' WHERE case_id = ?", (text, username, now(), case_id))
    audit(conn, username, "case", case_id, "answered")
    return rows.notify(conn, [row["username"]], f"Reply to your question (case {case_id})",
                       f"You asked: {row['message'][:500]}\n\n{text}")


def close(conn, username, role, case_id, note="") -> None:
    row = case(conn, case_id)
    _require(_can_work(conn, username, role, row), "You cannot work on this case")
    conn.execute("UPDATE chatbot_cases SET status = 'closed', closed_at = ?, closed_by = ? WHERE "
                 "case_id = ?", (now(), username, case_id))
    audit(conn, username, "case", case_id, "closed", {"note": note} if note else None)

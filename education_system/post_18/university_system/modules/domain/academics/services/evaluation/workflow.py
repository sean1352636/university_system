"""
Action-loop service (features 29-33).

29. You said / we did tracker
30. Instructor reply box
31. Department-head review queue
32. Auto-routing of red-flag comments
33. Improvement plan templates + instances
"""

from __future__ import annotations

import re
from typing import Iterable

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)


# ---------- You said / we did (29) ----------

def ysw_create(evaluation_id: int | None, theme: str, you_said: str,
               *, owner: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_youssaid_wedid
                 (evaluation_id, theme, you_said, owner)
               VALUES (?,?,?,?)""",
            (evaluation_id, theme, you_said, owner),
        )
        conn.commit()
        return cur.lastrowid


def ysw_resolve(ysw_id: int, we_did: str) -> None:
    with transaction() as conn:
        conn.execute(
            """UPDATE evaluation_youssaid_wedid
               SET we_did=?, status='closed', resolved_at=datetime('now')
               WHERE ysw_id=?""",
            (we_did, ysw_id),
        )
        conn.commit()


def ysw_list(*, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_youssaid_wedid"
    args: list = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ---------- Instructor reply (30) ----------

def reply(evaluation_id: int, reply_text: str, *,
          theme: str = "", posted_by: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_instructor_replies
                 (evaluation_id, theme, reply_text, posted_by)
               VALUES (?,?,?,?)""",
            (evaluation_id, theme, reply_text, posted_by),
        )
        conn.commit()
        return cur.lastrowid


def list_replies(evaluation_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_instructor_replies WHERE evaluation_id=? "
            "ORDER BY posted_at DESC", (evaluation_id,),
        ).fetchall()]


# ---------- Review queue (31) ----------

def queue_for_review(evaluation_id: int, reviewer: str) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO evaluation_review_queue (evaluation_id, reviewer) VALUES (?,?)",
            (evaluation_id, reviewer),
        )
        conn.commit()
        return cur.lastrowid


def sign_off(queue_id: int, *, comment: str = "", status: str = "approved") -> None:
    with transaction() as conn:
        conn.execute(
            """UPDATE evaluation_review_queue
               SET status=?, comment=?, signed_off_at=datetime('now')
               WHERE queue_id=?""",
            (status, comment, queue_id),
        )
        conn.commit()


def list_review_queue(*, reviewer: str | None = None,
                      status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_review_queue"
    args: list = []
    where: list[str] = []
    if reviewer:
        where.append("reviewer=?")
        args.append(reviewer)
    if status:
        where.append("status=?")
        args.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ---------- Red-flag routing (32) ----------

# Default rule set — concrete enough for tests, conservative enough that
# admins can extend via `add_redflag_rule`.
_DEFAULT_REDFLAG_RULES: tuple[tuple[str, str, str], ...] = (
    ("self_harm", r"\b(suicide|kill\s+myself|end\s+my\s+life|self[- ]?harm\w*)\b", "safeguarding"),
    ("violence",  r"\b(threat\w*|attack\w*|hurt\s+(?:me|us|him|her|them)|weapon)\b", "safeguarding"),
    ("harassment", r"\b(harass\w*|bull(?:y|ies|ied|ying)|stalk\w*|abusive)\b", "title_ix"),
    ("discrim",    r"\b(racis\w*|sexis\w*|homophobi\w*|transphobi\w*|discriminat\w*)", "equity"),
)


def add_redflag_rule(category: str, pattern: str, route_to: str) -> int:
    re.compile(pattern)
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO evaluation_red_flag_rules (category, pattern, route_to) VALUES (?,?,?)",
            (category, pattern, route_to),
        )
        conn.commit()
        return cur.lastrowid


def _all_rules() -> list[tuple[str, str, str]]:
    rules = list(_DEFAULT_REDFLAG_RULES)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, pattern, route_to FROM evaluation_red_flag_rules"
        ).fetchall()
    rules.extend((r["category"], r["pattern"], r["route_to"]) for r in rows)
    return rules


def scan_response_for_redflags(answer_id: int, text: str) -> list[dict]:
    if not text:
        return []
    routed: list[dict] = []
    with transaction() as conn:
        for cat, pat, route in _all_rules():
            try:
                if re.search(pat, text, flags=re.IGNORECASE):
                    cur = conn.execute(
                        """INSERT INTO evaluation_red_flags
                             (answer_id, category, pattern, routed_to)
                           VALUES (?,?,?,?)""",
                        (answer_id, cat, pat, route),
                    )
                    routed.append({"flag_id": cur.lastrowid, "category": cat,
                                   "routed_to": route})
            except re.error:
                continue
        conn.commit()
    return routed


def acknowledge_redflag(flag_id: int) -> None:
    with transaction() as conn:
        conn.execute("UPDATE evaluation_red_flags SET acknowledged=1 WHERE flag_id=?",
                     (flag_id,))
        conn.commit()


def list_redflags(*, acknowledged: bool | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_red_flags"
    args: list = []
    if acknowledged is not None:
        sql += " WHERE acknowledged=?"
        args.append(1 if acknowledged else 0)
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ---------- Improvement plans (33) ----------

def add_improvement_template(name: str, body: str,
                             *, trigger_below_score: float | None = None) -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_improvement_templates
                 (name, body, trigger_below_score) VALUES (?,?,?)""",
            (name, body, trigger_below_score),
        )
        conn.commit()
        return cur.lastrowid


def create_plan(evaluation_id: int, *, template_id: int | None = None,
                body: str = "", author: str = "") -> int:
    if template_id and not body:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT body FROM evaluation_improvement_templates WHERE imp_template_id=?",
                (template_id,),
            ).fetchone()
        if row:
            body = row[0]
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_improvement_plans
                 (evaluation_id, template_id, body, author) VALUES (?,?,?,?)""",
            (evaluation_id, template_id, body, author),
        )
        conn.commit()
        return cur.lastrowid


def list_improvement_templates() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_improvement_templates ORDER BY imp_template_id"
        ).fetchall()]


def list_plans(evaluation_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_improvement_plans WHERE evaluation_id=? "
            "ORDER BY created_at DESC", (evaluation_id,),
        ).fetchall()]


__all__ = [
    "ysw_create", "ysw_resolve", "ysw_list",
    "reply", "list_replies",
    "queue_for_review", "sign_off", "list_review_queue",
    "add_redflag_rule", "scan_response_for_redflags",
    "acknowledge_redflag", "list_redflags",
    "add_improvement_template", "create_plan",
    "list_improvement_templates", "list_plans",
]

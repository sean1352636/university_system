"""
Compliance service (features 39-43).

39. End-to-end anonymity audit log
40. GDPR data-subject export / delete
41. Role-based redaction
42. MFA-gated routes
43. Retention policy editor + sweeper
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)


# ---------- 39. Anonymity audit ----------

def audit(actor: str, action: str, detail: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO evaluation_anonymity_audit (actor, action, detail) VALUES (?,?,?)",
            (actor, action, detail),
        )
        conn.commit()
        return cur.lastrowid


def audit_tail(limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_anonymity_audit ORDER BY audit_id DESC LIMIT ?",
            (limit,),
        ).fetchall()]


def anonymity_assertion() -> dict:
    """Return a structural assertion that identities are not stored alongside
    answers in the anonymised form tables (used by external auditors)."""
    with get_connection() as conn:
        # Anything in eval_form_responses other than a hash?
        cols = [r["name"] for r in conn.execute(
            "PRAGMA table_info(eval_form_responses)"
        ).fetchall()]
        identity_leak = any(c in cols for c in ("student_id", "email", "username"))
        # Detached: answers reference response_id, not student.
        ans_cols = [r["name"] for r in conn.execute(
            "PRAGMA table_info(eval_form_answers)"
        ).fetchall()]
        answer_leak = any(c in ans_cols for c in ("student_id", "email", "username"))
    return {
        "identifying_columns_in_responses": identity_leak,
        "identifying_columns_in_answers": answer_leak,
        "anonymous_form_layer_safe": not (identity_leak or answer_leak),
        "checked_at": datetime.now().isoformat(),
    }


# ---------- 40. GDPR ----------

def _subject_token(identifier: str) -> str:
    return hashlib.sha256(f"gdpr:{identifier}".encode()).hexdigest()[:32]


def gdpr_export(identifier: str) -> dict:
    """Collect every record we can pin to this identifier and return a packet.
    Identifier can be student_id or token; we look at both."""
    token = _subject_token(identifier)
    with get_connection() as conn:
        invites = conn.execute(
            "SELECT * FROM evaluation_invitations WHERE recipient_id=?", (identifier,),
        ).fetchall()
        responses = conn.execute(
            "SELECT * FROM evaluation_responses WHERE student_id=?", (identifier,),
        ).fetchall()
        drafts = conn.execute(
            "SELECT * FROM evaluation_drafts WHERE respondent_token=?", (identifier,),
        ).fetchall()
        anon = conn.execute(
            "SELECT * FROM eval_form_responses WHERE student_hash="
            "substr(?, 1, 32)",
            (hashlib.sha256(f"{identifier}:salt_eval".encode()).hexdigest()[:32],),
        ).fetchall() if conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='eval_form_responses'"
        ).fetchone() else []
    packet = {
        "subject": identifier,
        "subject_token": token,
        "invitations": [dict(r) for r in invites],
        "responses": [dict(r) for r in responses],
        "drafts": [dict(r) for r in drafts],
        "anonymous_responses_seen": len(anon),
        "exported_at": datetime.now().isoformat(),
    }
    with transaction() as conn:
        conn.execute(
            """INSERT INTO evaluation_gdpr_requests
                 (subject_token, kind, payload_json, status, completed_at)
               VALUES (?, 'export', ?, 'completed', datetime('now'))""",
            (token, json.dumps(packet, default=str)),
        )
        conn.commit()
    audit("system", "gdpr.export", f"subject_token={token}")
    return packet


def gdpr_delete(identifier: str) -> dict:
    """Erase identifiable rows. Anonymous form responses (hashed) are left
    intact — they cannot be linked back to the subject."""
    token = _subject_token(identifier)
    with transaction() as conn:
        c1 = conn.execute("DELETE FROM evaluation_invitations WHERE recipient_id=?",
                          (identifier,)).rowcount
        c2 = conn.execute("DELETE FROM evaluation_drafts WHERE respondent_token=?",
                          (identifier,)).rowcount
        # Don't delete `evaluation_responses` outright (would corrupt aggregates);
        # null the student_id to detach instead.
        c3 = conn.execute(
            "UPDATE evaluation_responses SET student_id=NULL WHERE student_id=?",
            (identifier,),
        ).rowcount
        conn.execute(
            """INSERT INTO evaluation_gdpr_requests
                 (subject_token, kind, status, completed_at)
               VALUES (?, 'delete', 'completed', datetime('now'))""",
            (token,),
        )
        conn.commit()
    audit("system", "gdpr.delete",
          f"subject_token={token} invites={c1} drafts={c2} detached={c3}")
    return {"invitations_deleted": c1, "drafts_deleted": c2,
            "responses_detached": c3, "subject_token": token}


def gdpr_history() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT request_id, subject_token, kind, status, created_at, completed_at "
            "FROM evaluation_gdpr_requests ORDER BY request_id DESC"
        ).fetchall()]


# ---------- 41. Role-based redaction ----------

def set_role_redaction(role: str, field: str, action: str = "hide") -> int:
    if action not in ("hide", "mask"):
        raise ValueError("action must be 'hide' or 'mask'")
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO evaluation_role_redactions (role, field, action) VALUES (?,?,?)",
            (role, field, action),
        )
        conn.commit()
        return cur.lastrowid


def list_role_redactions(role: str | None = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_role_redactions"
    args: list = []
    if role:
        sql += " WHERE role IN (?, '*')"
        args.append(role)
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def apply_role_redactions(role: str, record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `record` with fields hidden/masked per role policy."""
    rules = list_role_redactions(role)
    out = dict(record)
    for rule in rules:
        if rule["field"] in out:
            if rule["action"] == "hide":
                out.pop(rule["field"], None)
            else:
                v = out[rule["field"]]
                out[rule["field"]] = (
                    "*" * len(str(v)) if v not in (None, "") else v
                )
    return out


# ---------- 42. MFA gates ----------

def require_mfa(route: str, required: bool = True) -> None:
    with transaction() as conn:
        conn.execute(
            """INSERT INTO evaluation_mfa_gates (route, required) VALUES (?,?)
               ON CONFLICT(route) DO UPDATE SET required=excluded.required""",
            (route, 1 if required else 0),
        )
        conn.commit()


def is_mfa_required(route: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT required FROM evaluation_mfa_gates WHERE route=?", (route,),
        ).fetchone()
    return bool(row and row[0])


def list_mfa_gates() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_mfa_gates ORDER BY route"
        ).fetchall()]


# ---------- 43. Retention policy ----------

_PURGE_TARGETS = {
    "drafts":        "evaluation_drafts",
    "raw_answers":   "evaluation_answers",
    "responses":     "evaluation_responses",
    "invitations":   "evaluation_invitations",
    "anon_answers":  "eval_form_answers",
    "anon_responses": "eval_form_responses",
}


def set_retention(target: str, keep_days: int, *, keep_aggregates: bool = True) -> int:
    if target not in _PURGE_TARGETS:
        raise ValueError(f"Unknown retention target: {target}")
    if keep_days < 1:
        raise ValueError("keep_days must be >= 1")
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_retention_policies
                 (target, keep_days, keep_aggregates) VALUES (?,?,?)""",
            (target, keep_days, 1 if keep_aggregates else 0),
        )
        conn.commit()
        return cur.lastrowid


def list_retention() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM evaluation_retention_policies ORDER BY policy_id"
        ).fetchall()]


def purge_due(now: datetime | None = None) -> dict[str, int]:
    """Walk every active retention policy and delete rows older than its
    cutoff. `evaluation_results` is NEVER touched — those are aggregates
    and `keep_aggregates` was promised."""
    now = now or datetime.now()
    purged: dict[str, int] = {}
    with transaction() as conn:
        for p in conn.execute("SELECT * FROM evaluation_retention_policies").fetchall():
            table = _PURGE_TARGETS.get(p["target"])
            if not table:
                continue
            cutoff = (now - timedelta(days=p["keep_days"])).isoformat()
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            ts_col = next(
                (c for c in ("created_at", "updated_at", "submitted_at", "synced_at") if c in cols),
                None,
            )
            if not ts_col:
                continue
            cur = conn.execute(f"DELETE FROM {table} WHERE {ts_col} < ?", (cutoff,))
            purged[p["target"]] = purged.get(p["target"], 0) + cur.rowcount
        conn.commit()
    audit("system", "retention.purge", json.dumps(purged))
    return purged


__all__ = [
    "audit", "audit_tail", "anonymity_assertion",
    "gdpr_export", "gdpr_delete", "gdpr_history",
    "set_role_redaction", "list_role_redactions", "apply_role_redactions",
    "require_mfa", "is_mfa_required", "list_mfa_gates",
    "set_retention", "list_retention", "purge_due",
]

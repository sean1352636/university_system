"""Access-policy controls layered on top of the permissions overlay:

* **MFA enforcement** (#21) — declare which roles MUST have MFA
  enrolled; report flags users in those roles who haven't.
* **IP allow/deny rules** (#22) — per-user (or applied to every member
  of a role); checks an inbound IP against the merged ruleset.
* **Just-in-time access** (#26) — request a temporary permission grant
  with TTL; an approver activates it; expiry sweeps it back out.
* **Sensitive-action approvers** (#28) — two-person rule for nominated
  actions (delete_user, role_change). A request stays Pending until a
  second admin approves; applying the action is the caller's job.
* **Per-system role overrides** (#29) — the shared user_systems table
  already supports a different role per system; this module just
  surfaces a structured view and audited bulk-update helper.
* **Preview-as-user** (#30) — gather a user's effective permission
  set + role-per-system + override list so the GUI can render a
  read-only "what they see" report.
"""

from __future__ import annotations

import datetime
import logging
import re
import secrets
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.shared.auth.role_manager import ROLE_HIERARCHY
from education_system.post_16.sixthform_system.modules.domain.governance.user_management import (
    lifecycle, permissions as perms,
)
from education_system.post_16.sixthform_system.modules.shared import user_accounts as _ua
from education_system.post_16.sixthform_system.modules.shared.user_accounts import (
    SYSTEM_KEY, UserAccountError, UserRow,
)

logger = logging.getLogger(__name__)


def _init_schema(auth: Any) -> None:
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mfa_enforcement_policy (
                    role_key TEXT PRIMARY KEY,
                    required INTEGER NOT NULL DEFAULT 1,
                    set_by TEXT, set_at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_ip_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,        -- 'user' | 'role'
                    scope_value TEXT NOT NULL,  -- user_id (as text) or role_key
                    mode TEXT NOT NULL,         -- 'allow' | 'deny'
                    pattern TEXT NOT NULL,      -- IPv4 / CIDR / wildcard
                    reason TEXT, set_by TEXT, set_at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jit_access_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    system_key TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    justification TEXT,
                    requested_by TEXT, requested_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    approver TEXT, approved_at TEXT,
                    expires_at TEXT, override_set INTEGER NOT NULL DEFAULT 0
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_jit_user
                ON jit_access_requests(user_id, status)
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sensitive_action_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,           -- e.g. 'delete_user'
                    target_user_id INTEGER,
                    payload TEXT,                   -- JSON
                    reason TEXT,
                    requested_by TEXT, requested_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    approver TEXT, decided_at TEXT,
                    nonce TEXT NOT NULL
                )
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("access_policy schema init failed")
        raise


# ── 21. MFA enforcement ───────────────────────────────────────────────

def set_mfa_required(auth: Any, role_key: str, required: bool) -> None:
    _init_schema(auth)
    if role_key not in {r.role_key for r in perms.list_roles(auth)}:
        raise UserAccountError(f"Unknown role: {role_key!r}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                INSERT INTO mfa_enforcement_policy
                (role_key, required, set_by, set_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(role_key) DO UPDATE SET
                    required=excluded.required,
                    set_by=excluded.set_by, set_at=excluded.set_at
            ''', (role_key, 1 if required else 0, actor, now))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("set_mfa_required failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "mfa_policy_set", None,
                      {"role_key": role_key, "required": required})


def mfa_policy(auth: Any) -> dict[str, bool]:
    _init_schema(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            return {r["role_key"]: bool(r["required"])
                    for r in conn.execute(
                        "SELECT role_key, required FROM "
                        "mfa_enforcement_policy")}
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("mfa_policy load failed")
        return {}


@dataclass
class MfaGap:
    user_id: int
    username: str
    display_name: str | None
    role: str | None


def mfa_enforcement_gaps(auth: Any,
                          *, system_key: str = SYSTEM_KEY
                          ) -> list[MfaGap]:
    """Users in roles where MFA is required but the user has no
    mfa_secrets row enabled."""
    pol = mfa_policy(auth)
    required_roles = {k for k, v in pol.items() if v}
    if not required_roles:
        return []
    try:
        conn = lifecycle._conn(auth)
        try:
            enabled = {r["user_id"] for r in conn.execute(
                "SELECT user_id FROM mfa_secrets WHERE is_enabled = 1"
            ).fetchall()}
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("mfa enabled lookup failed")
        return []
    out: list[MfaGap] = []
    for u in _ua.list_users(auth, system_key=system_key):
        role = u.role_for(system_key)
        if role in required_roles and u.id not in enabled:
            out.append(MfaGap(u.id, u.username, u.display_name, role))
    return out


# ── 22. IP allow/deny ─────────────────────────────────────────────────

_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_CIDR_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}$")
_WILD_RE = re.compile(r"^[\d\.\*]+$")


def _validate_pattern(p: str) -> None:
    p = p.strip()
    if not p:
        raise UserAccountError("Pattern is required.")
    if _IPV4_RE.match(p) or _CIDR_RE.match(p) or _WILD_RE.match(p):
        return
    raise UserAccountError(
        "Pattern must be IPv4, IPv4/CIDR, or contain only digits/./*.")


def add_ip_rule(auth: Any, *, scope: str, scope_value: str,
                 mode: str, pattern: str,
                 reason: str | None = None) -> int:
    _init_schema(auth)
    if scope not in ("user", "role"):
        raise UserAccountError("scope must be 'user' or 'role'.")
    if mode not in ("allow", "deny"):
        raise UserAccountError("mode must be 'allow' or 'deny'.")
    _validate_pattern(pattern)
    if scope == "role" and scope_value not in {
            r.role_key for r in perms.list_roles(auth)}:
        raise UserAccountError(f"Unknown role: {scope_value!r}")
    if scope == "user":
        try:
            uid = int(scope_value)
        except ValueError as e:
            raise UserAccountError(
                "scope_value for 'user' must be a numeric user-id."
            ) from e
        if _ua.get_user(auth, uid) is None:
            raise UserAccountError(f"No user #{uid}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO user_ip_rules
                (scope, scope_value, mode, pattern, reason, set_by, set_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (scope, str(scope_value), mode, pattern.strip(),
                  reason, actor, now))
            rid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("add_ip_rule failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "ip_rule_add", None, {
        "scope": scope, "scope_value": scope_value,
        "mode": mode, "pattern": pattern,
    })
    return rid


def remove_ip_rule(auth: Any, rule_id: int) -> bool:
    _init_schema(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute(
                "DELETE FROM user_ip_rules WHERE id = ?", (rule_id,))
            conn.commit()
            ok = cur.rowcount > 0
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("remove_ip_rule failed")
        return False
    if ok:
        lifecycle._audit(auth, "ip_rule_remove", None,
                          {"rule_id": rule_id})
    return ok


def list_ip_rules(auth: Any, *, user_id: int | None = None
                    ) -> list[dict]:
    _init_schema(auth)
    sql = "SELECT * FROM user_ip_rules"
    args: list = []
    if user_id is not None:
        # rules for user OR a role the user holds
        user = _ua.get_user(auth, user_id)
        roles = [s.get('role') for s in (user.systems if user else [])]
        roles = [r for r in roles if r]
        ph = ",".join("?" * len(roles))
        if roles:
            sql += (" WHERE (scope='user' AND scope_value=?) "
                     f"OR (scope='role' AND scope_value IN ({ph}))")
            args.append(str(user_id))
            args.extend(roles)
        else:
            sql += " WHERE scope='user' AND scope_value=?"
            args.append(str(user_id))
    sql += " ORDER BY scope, scope_value, mode"
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_ip_rules failed")
        return []


def _ip_matches(pattern: str, ip: str) -> bool:
    """Cheap matcher: exact, CIDR /N (IPv4 only), or wildcard with '*'."""
    pattern = pattern.strip()
    if pattern == ip:
        return True
    if "/" in pattern:
        try:
            net, bits = pattern.split("/", 1)
            bits = int(bits)
            net_parts = [int(x) for x in net.split(".")]
            ip_parts = [int(x) for x in ip.split(".")]
            if len(net_parts) != 4 or len(ip_parts) != 4:
                return False
            mask = ((1 << 32) - 1) ^ ((1 << (32 - bits)) - 1)
            net_n = (net_parts[0] << 24) | (net_parts[1] << 16) \
                | (net_parts[2] << 8) | net_parts[3]
            ip_n = (ip_parts[0] << 24) | (ip_parts[1] << 16) \
                | (ip_parts[2] << 8) | ip_parts[3]
            return (net_n & mask) == (ip_n & mask)
        except ValueError:
            return False
    if "*" in pattern:
        # Glob — '*.foo.0' etc.
        regex = re.compile("^" + re.escape(pattern).replace(r"\*", r"[^.]+") + "$")
        return bool(regex.match(ip))
    return False


def check_ip(auth: Any, user_id: int, ip: str) -> tuple[bool, str]:
    """Decision flow: explicit user-level deny > user-level allow >
    role-level deny > role-level allow > default-allow."""
    rules = list_ip_rules(auth, user_id=user_id)
    # Order by precedence: user before role; deny before allow.
    def _key(r):
        return (0 if r["scope"] == "user" else 1,
                0 if r["mode"] == "deny" else 1)
    for r in sorted(rules, key=_key):
        if _ip_matches(r["pattern"], ip):
            ok = r["mode"] == "allow"
            return ok, (f"matched {r['scope']}:{r['scope_value']} "
                          f"{r['mode']} {r['pattern']}")
    return True, "default-allow (no matching rule)"


# ── 25/26. Just-in-time access ────────────────────────────────────────

@dataclass
class JitRequest:
    request_id: int
    user_id: int
    system_key: str
    permission: str
    justification: str | None
    requested_by: str | None
    requested_at: str
    status: str
    approver: str | None
    approved_at: str | None
    expires_at: str | None


def request_jit(auth: Any, *, user_id: int, permission: str,
                 justification: str | None,
                 system_key: str = SYSTEM_KEY) -> JitRequest:
    _init_schema(auth)
    if permission not in perms.PERMISSIONS:
        raise UserAccountError(f"Unknown permission: {permission!r}")
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO jit_access_requests
                (user_id, system_key, permission, justification,
                 requested_by, requested_at, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Pending')
            ''', (user_id, system_key, permission, justification,
                  actor, now))
            rid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("request_jit failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "jit_request", user_id, {
        "request_id": rid, "permission": permission,
        "system_key": system_key, "justification": justification,
    })
    return get_jit(auth, rid)


def approve_jit(auth: Any, request_id: int, *,
                 ttl_minutes: int = 60) -> JitRequest:
    """Approve a pending JIT request — writes a user_permission_overrides
    grant for the configured TTL. ``revoke_expired_jit`` returns those
    grants when expiry has passed."""
    _init_schema(auth)
    req = get_jit(auth, request_id)
    if req.status != 'Pending':
        raise UserAccountError(
            f"Request is {req.status!r}, not Pending.")
    actor = lifecycle._actor_name(auth)
    now = datetime.datetime.now()
    expires = (now + datetime.timedelta(minutes=max(1, ttl_minutes))
                ).isoformat(timespec='seconds')
    try:
        perms.set_user_override(
            auth, req.user_id, req.permission, "grant",
            system_key=req.system_key,
            reason=f"JIT request #{request_id} approved by {actor} "
                    f"(expires {expires})")
    except UserAccountError:
        raise
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                UPDATE jit_access_requests
                SET status='Approved', approver=?, approved_at=?,
                    expires_at=?, override_set=1
                WHERE request_id=?
            ''', (actor, now.isoformat(timespec='seconds'), expires,
                  request_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("approve_jit DB update failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "jit_approve", req.user_id, {
        "request_id": request_id, "expires_at": expires,
    })
    return get_jit(auth, request_id)


def deny_jit(auth: Any, request_id: int, *,
              reason: str | None = None) -> JitRequest:
    _init_schema(auth)
    req = get_jit(auth, request_id)
    if req.status != 'Pending':
        raise UserAccountError(
            f"Request is {req.status!r}, not Pending.")
    actor = lifecycle._actor_name(auth)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                UPDATE jit_access_requests
                SET status='Denied', approver=?, approved_at=?
                WHERE request_id=?
            ''', (actor, now, request_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("deny_jit failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "jit_deny", req.user_id, {
        "request_id": request_id, "reason": reason,
    })
    return get_jit(auth, request_id)


def revoke_expired_jit(auth: Any) -> int:
    """Sweep pass: find Approved rows whose ``expires_at`` is in the
    past, clear the user_permission_overrides row, mark Expired."""
    _init_schema(auth)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    swept = 0
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute('''
                SELECT request_id, user_id, system_key, permission
                FROM jit_access_requests
                WHERE status='Approved' AND override_set=1
                  AND expires_at IS NOT NULL AND expires_at < ?
            ''', (now,)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("revoke_expired_jit fetch failed")
        return 0
    for r in rows:
        try:
            perms.clear_user_override(
                auth, r["user_id"], r["permission"],
                system_key=r["system_key"])
        except Exception:
            logger.exception("revoke_expired_jit: override clear failed")
        try:
            conn = lifecycle._conn(auth)
            try:
                conn.execute(
                    "UPDATE jit_access_requests SET status='Expired', "
                    "override_set=0 WHERE request_id=?",
                    (r["request_id"],))
                conn.commit()
            finally:
                conn.close()
            swept += 1
            lifecycle._audit(auth, "jit_expire", r["user_id"], {
                "request_id": r["request_id"],
                "permission": r["permission"],
            })
        except sqlite3.Error:
            logger.exception("revoke_expired_jit status update failed")
    return swept


def list_jit(auth: Any, *, status: str | None = None
              ) -> list[JitRequest]:
    _init_schema(auth)
    sql = "SELECT * FROM jit_access_requests"
    args: list = []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY requested_at DESC"
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_jit failed")
        return []
    return [JitRequest(
        request_id=r["request_id"], user_id=r["user_id"],
        system_key=r["system_key"], permission=r["permission"],
        justification=r["justification"],
        requested_by=r["requested_by"],
        requested_at=r["requested_at"], status=r["status"],
        approver=r["approver"], approved_at=r["approved_at"],
        expires_at=r["expires_at"]) for r in rows]


def get_jit(auth: Any, request_id: int) -> JitRequest:
    rs = list_jit(auth)
    for r in rs:
        if r.request_id == request_id:
            return r
    raise UserAccountError(f"No JIT request #{request_id}")


# ── 28. Sensitive-action approvers ────────────────────────────────────

SENSITIVE_ACTIONS = {
    "delete_user":   "Permanently delete a user account",
    "role_change":   "Change a user's role",
    "bulk_archive":  "Archive multiple users in bulk",
    "merge_users":   "Merge two user accounts",
}


@dataclass
class SensitiveRequest:
    request_id: int
    action: str
    target_user_id: int | None
    payload: str | None
    reason: str | None
    requested_by: str | None
    requested_at: str
    status: str
    approver: str | None
    decided_at: str | None
    nonce: str


def request_sensitive(auth: Any, *, action: str,
                       target_user_id: int | None = None,
                       payload: str | None = None,
                       reason: str | None = None) -> SensitiveRequest:
    _init_schema(auth)
    if action not in SENSITIVE_ACTIONS:
        raise UserAccountError(f"Unknown sensitive action: {action!r}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    nonce = secrets.token_urlsafe(12)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO sensitive_action_requests
                (action, target_user_id, payload, reason,
                 requested_by, requested_at, status, nonce)
                VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
            ''', (action, target_user_id, payload, reason, actor, now,
                  nonce))
            rid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("request_sensitive failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "sensitive_request", target_user_id, {
        "request_id": rid, "action": action, "reason": reason,
    })
    return get_sensitive(auth, rid)


def decide_sensitive(auth: Any, request_id: int, *,
                      approved: bool, nonce: str,
                      reason: str | None = None) -> SensitiveRequest:
    """Approve / deny. The ``nonce`` from the original request must
    match — guards against muscle-memory approvals. The approver must
    NOT be the requester (two-person rule)."""
    _init_schema(auth)
    req = get_sensitive(auth, request_id)
    if req.status != 'Pending':
        raise UserAccountError(
            f"Request is {req.status!r}, not Pending.")
    if (nonce or '') != req.nonce:
        raise UserAccountError("Nonce mismatch — check the request id.")
    actor = lifecycle._actor_name(auth)
    if actor == req.requested_by:
        raise UserAccountError(
            "Two-person rule: a different admin must approve.")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    new_status = 'Approved' if approved else 'Denied'
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                UPDATE sensitive_action_requests
                SET status=?, approver=?, decided_at=?
                WHERE request_id=?
            ''', (new_status, actor, now, request_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("decide_sensitive failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, f"sensitive_{new_status.lower()}",
                      req.target_user_id, {
                          "request_id": request_id, "action": req.action,
                          "reason": reason,
                      })
    return get_sensitive(auth, request_id)


def list_sensitive(auth: Any, *, status: str | None = "Pending"
                     ) -> list[SensitiveRequest]:
    _init_schema(auth)
    sql = "SELECT * FROM sensitive_action_requests"
    args: list = []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY requested_at DESC"
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_sensitive failed")
        return []
    return [SensitiveRequest(
        request_id=r["request_id"], action=r["action"],
        target_user_id=r["target_user_id"], payload=r["payload"],
        reason=r["reason"], requested_by=r["requested_by"],
        requested_at=r["requested_at"], status=r["status"],
        approver=r["approver"], decided_at=r["decided_at"],
        nonce=r["nonce"]) for r in rows]


def get_sensitive(auth: Any, request_id: int) -> SensitiveRequest:
    for r in list_sensitive(auth, status=None):
        if r.request_id == request_id:
            return r
    raise UserAccountError(f"No sensitive request #{request_id}")


# ── 29. Per-system role overrides ─────────────────────────────────────

def per_system_view(auth: Any, user_id: int) -> dict[str, str | None]:
    user = _ua.get_user(auth, user_id)
    if user is None:
        return {}
    return {s.get("system_key"): s.get("role") for s in user.systems}


def set_per_system_role(auth: Any, user_id: int, system_key: str,
                          role: str) -> None:
    """Set or change the user's role for a specific system. Pass
    ``role=''`` (empty) to revoke. Goes through the shared
    ``grant_role``/``revoke_role`` so auth-side cascades happen."""
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    try:
        if role:
            _ua.grant_role(auth, user_id, system_key, role)
        else:
            _ua.revoke_role(auth, user_id, system_key)
    except Exception as e:
        logger.exception("set_per_system_role failed")
        raise UserAccountError(f"Could not apply: {e}") from e
    lifecycle._audit(auth, "user_per_system_role", user_id,
                      {"system_key": system_key, "role": role or None})


# ── 30. Preview-as-user ───────────────────────────────────────────────

@dataclass
class UserPreview:
    user: UserRow
    per_system_roles: dict[str, str | None]
    effective_permissions: dict[str, set[str]]      # system_key -> perms
    overrides: list[dict]


def preview_as_user(auth: Any, user_id: int) -> UserPreview:
    user = _ua.get_user(auth, user_id)
    if user is None:
        raise UserAccountError(f"No user #{user_id}")
    per_sys = per_system_view(auth, user_id)
    eff: dict[str, set[str]] = {}
    for sk in per_sys:
        eff[sk] = perms.effective_permissions(auth, user_id,
                                                 system_key=sk)
    return UserPreview(
        user=user, per_system_roles=per_sys,
        effective_permissions=eff,
        overrides=perms.list_user_overrides(auth, user_id),
    )

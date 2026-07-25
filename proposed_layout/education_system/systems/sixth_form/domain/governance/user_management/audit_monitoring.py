"""Audit + monitoring helpers (#31-38).

* 31. Per-user audit log with filters
* 32. Immutable permission-change log
* 33. Login map (last-login + ip + rough country)
* 34. Concurrent-session detector
* 35. Stale-account auto-flag
* 36. Daily admin digest
* 37. Anomalous-activity alerts (heuristics)
* 38. Snapshots history viewer
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable

from education_system.systems.sixth_form.domain.governance.user_management import (
    lifecycle,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    user_management as data,
)
from education_system.systems.sixth_form.interfaces import user_accounts as _ua

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────

# Audit actions related to roles/permissions/access — used by the
# perm-change log filter.
PERM_AUDIT_ACTIONS = (
    "role_create", "role_rename", "role_delete", "role_perms_set",
    "user_perm_override", "user_per_system_role",
    "jit_request", "jit_approve", "jit_deny", "jit_expire",
    "sensitive_request", "sensitive_approved", "sensitive_denied",
    "mfa_policy_set",
    "ip_rule_add", "ip_rule_remove",
)


def _init(auth: Any) -> None:
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    taken_at TEXT NOT NULL,
                    taken_by TEXT,
                    label TEXT,
                    payload TEXT NOT NULL       -- JSON
                )
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("audit_monitoring schema init failed")
        raise


# ── 31. Per-user audit log ────────────────────────────────────────────

def list_audit(auth: Any, *, target_user_id: int | None = None,
                action_prefix: str | None = None,
                since_hours: int | None = None,
                limit: int = 500) -> list[dict]:
    """Pull from ``user_audit_log`` (owned by lifecycle.py)."""
    lifecycle.init_lifecycle_schema(auth)
    clauses: list[str] = []
    args: list = []
    if target_user_id is not None:
        clauses.append("target_user_id = ?")
        args.append(target_user_id)
    if action_prefix:
        clauses.append("action LIKE ?")
        args.append(action_prefix + "%")
    if since_hours:
        cutoff = (datetime.datetime.now()
                  - datetime.timedelta(hours=since_hours)
                  ).isoformat(timespec='seconds')
        clauses.append("ts >= ?")
        args.append(cutoff)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM user_audit_log {where} "
            f"ORDER BY ts DESC LIMIT ?")
    args.append(int(limit))
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_audit failed")
        return []


# ── 32. Permission-change log ─────────────────────────────────────────

def list_perm_audit(auth: Any, *, since_hours: int | None = None,
                      limit: int = 500) -> list[dict]:
    """Subset of the main audit log restricted to permission/role
    actions. The user_audit_log is append-only (no UPDATE / DELETE
    in any code path we ship) so this is effectively immutable."""
    rows = list_audit(auth, since_hours=since_hours, limit=10_000)
    keep = [r for r in rows if r.get("action") in PERM_AUDIT_ACTIONS]
    return keep[:limit]


# ── 33. Login map ─────────────────────────────────────────────────────

_COUNTRY_HINTS = {     # very rough — admins should plug a real geoip
    "10.": "internal",
    "192.168.": "internal",
    "172.16.": "internal",
    "172.17.": "internal",
    "127.": "loopback",
}


def _rough_country(ip: str | None) -> str:
    if not ip:
        return "—"
    for prefix, label in _COUNTRY_HINTS.items():
        if ip.startswith(prefix):
            return label
    return "external"


@dataclass
class LoginPoint:
    user_id: int
    username: str
    display_name: str | None
    last_login: str | None
    ip_address: str | None
    rough_country: str


def login_map(auth: Any) -> list[LoginPoint]:
    """Pair each user with their most-recent login IP from
    ``security_audit_log`` (event_type containing 'login')."""
    try:
        conn = lifecycle._conn(auth)
        try:
            ip_rows = conn.execute('''
                SELECT user_id, username, ip_address, MAX(created_at)
                FROM security_audit_log
                WHERE lower(event_type) LIKE '%login%'
                  AND ip_address IS NOT NULL
                GROUP BY user_id, username, ip_address
            ''').fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("login_map ip query failed")
        ip_rows = []
    by_user_id: dict[int, str] = {}
    by_username: dict[str, str] = {}
    for r in ip_rows:
        if r["user_id"] is not None:
            by_user_id[r["user_id"]] = r["ip_address"]
        elif r["username"]:
            by_username[r["username"]] = r["ip_address"]
    out: list[LoginPoint] = []
    for u in _ua.list_users(auth):
        ip = by_user_id.get(u.id) or by_username.get(u.username)
        out.append(LoginPoint(
            user_id=u.id, username=u.username,
            display_name=u.display_name, last_login=u.last_login,
            ip_address=ip, rough_country=_rough_country(ip),
        ))
    out.sort(key=lambda r: r.last_login or "", reverse=True)
    return out


# ── 34. Concurrent-session detector ──────────────────────────────────

@dataclass
class ConcurrentSession:
    user_id: int
    username: str
    ip_set: list[str]
    session_count: int


def concurrent_sessions(auth: Any) -> list[ConcurrentSession]:
    """Active sessions per user, grouped by IP if we can detect it.
    The ``sessions`` table doesn't store IP, so we cross-reference
    security_audit_log entries within the session validity window —
    multiple distinct IPs across active sessions is the flag."""
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute('''
                SELECT s.user_id, u.username, COUNT(*) AS sess_n
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.is_active = 1
                GROUP BY s.user_id, u.username
                HAVING COUNT(*) > 1
            ''').fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("concurrent_sessions query failed")
        return []
    out: list[ConcurrentSession] = []
    for r in rows:
        ips = _recent_login_ips(auth, r["user_id"], hours=24)
        out.append(ConcurrentSession(
            user_id=r["user_id"], username=r["username"],
            ip_set=sorted(set(ips)),
            session_count=int(r["sess_n"] or 0)))
    return out


def _recent_login_ips(auth: Any, user_id: int, *,
                       hours: int = 24) -> list[str]:
    cutoff = (datetime.datetime.now()
              - datetime.timedelta(hours=hours)
              ).isoformat(timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute('''
                SELECT DISTINCT ip_address FROM security_audit_log
                WHERE user_id = ? AND created_at >= ?
                  AND ip_address IS NOT NULL
            ''', (user_id, cutoff)).fetchall()
            return [r["ip_address"] for r in rows if r["ip_address"]]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("_recent_login_ips failed")
        return []


# ── 35. Stale-account flag ────────────────────────────────────────────

@dataclass
class StaleAccount:
    user_id: int
    username: str
    display_name: str | None
    last_login: str | None
    days_idle: int | None
    is_active: bool


def stale_accounts(auth: Any, *,
                    days: int = 180,
                    include_never_logged_in: bool = True
                    ) -> list[StaleAccount]:
    now = datetime.datetime.now()
    out: list[StaleAccount] = []
    for u in _ua.list_users(auth):
        if u.last_login:
            try:
                idle = (now - datetime.datetime.fromisoformat(
                    u.last_login)).days
            except ValueError:
                idle = None
            if idle is not None and idle >= days:
                out.append(StaleAccount(
                    u.id, u.username, u.display_name, u.last_login,
                    idle, u.is_active))
        elif include_never_logged_in and u.is_active:
            out.append(StaleAccount(
                u.id, u.username, u.display_name, None, None,
                u.is_active))
    out.sort(key=lambda r: (r.days_idle if r.days_idle is not None
                              else 10**9),
              reverse=True)
    return out


# ── 36. Daily admin digest ────────────────────────────────────────────

def build_daily_digest(auth: Any,
                        *, hours: int = 24) -> dict:
    """Compose a summary of the last N hours that an admin would care
    about. Returns a dict; the caller decides whether to email it."""
    audit = list_audit(auth, since_hours=hours, limit=2000)
    new_users = [r for r in audit if r["action"] == "user_create"]
    role_changes = [r for r in audit
                     if r["action"] in {"user_perm_override",
                                         "role_perms_set",
                                         "user_per_system_role"}]
    locks = [r for r in audit if r["action"] in
              {"user_lock", "user_unlock"}]
    perm_audit = [r for r in audit
                   if r["action"] in PERM_AUDIT_ACTIONS]
    gaps = []
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access_policy,
        )
        gaps = access_policy.mfa_enforcement_gaps(auth)
    except Exception:
        logger.exception("digest: mfa gaps lookup failed")
    return {
        "window_hours": hours,
        "generated_at": datetime.datetime.now().isoformat(
            timespec='seconds'),
        "totals": {
            "new_users": len(new_users),
            "role_or_perm_changes": len(role_changes),
            "locks_or_unlocks": len(locks),
            "perm_audit_events": len(perm_audit),
            "mfa_gaps": len(gaps),
        },
        "new_users": new_users,
        "role_changes": role_changes,
        "locks": locks,
        "mfa_gaps": [g.__dict__ for g in gaps],
    }


def email_daily_digest(auth: Any, *, to: str,
                        hours: int = 24) -> bool:
    digest = build_daily_digest(auth, hours=hours)
    try:
        from education_system.systems.university.infrastructure.utils.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("digest: email_service import failed")
        return False
    body = json.dumps(digest, indent=2, default=str)
    subject = (f"Sixth-form user-management daily digest "
                f"({digest['generated_at']})")
    try:
        send_email(to, subject, body)
        return True
    except Exception:
        logger.exception("digest: send failed")
        return False


# ── 37. Anomalous-activity alerts ─────────────────────────────────────

@dataclass
class Anomaly:
    severity: str
    detail: str
    user_id: int | None = None


def anomalies(auth: Any, *, hours: int = 24) -> list[Anomaly]:
    """Cheap heuristics over the recent audit history."""
    out: list[Anomaly] = []
    audit = list_audit(auth, since_hours=hours, limit=5000)

    # 1) Mass deletes / archives by one actor.
    from collections import Counter
    actor_kills = Counter()
    for r in audit:
        if r["action"] in ("user_archive", "user_purge",
                           "user_offboard"):
            actor_kills[r["actor"] or "?"] += 1
    for actor, n in actor_kills.most_common():
        if n >= 5:
            out.append(Anomaly(
                "high",
                f"{actor} archived/purged {n} user(s) in last {hours}h."))

    # 2) Out-of-hours admin actions (between 22:00 and 06:00).
    for r in audit:
        try:
            t = datetime.datetime.fromisoformat(r["ts"])
        except ValueError:
            continue
        if t.hour >= 22 or t.hour < 6:
            if r["action"] in ("role_perms_set", "user_perm_override",
                               "user_purge"):
                out.append(Anomaly(
                    "medium",
                    (f"Out-of-hours {r['action']} by "
                     f"{r['actor'] or '?'} at {r['ts']}"),
                    user_id=r["target_user_id"]))

    # 3) Concurrent sessions across distinct IPs.
    for cs in concurrent_sessions(auth):
        if len(cs.ip_set) > 1:
            out.append(Anomaly(
                "high",
                (f"User {cs.username} (#{cs.user_id}) has "
                 f"{cs.session_count} active sessions across "
                 f"IPs: {', '.join(cs.ip_set)}"),
                user_id=cs.user_id))

    # 4) Spike in failed logins (raw count threshold).
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            security_ops,
        )
        fails = security_ops.list_failed_logins(auth, hours=hours)
        if len(fails) >= 20:
            out.append(Anomaly(
                "medium",
                f"{len(fails)} failed-login events in last {hours}h."))
    except Exception:
        logger.exception("anomaly: failed-login lookup failed")
    return out


# ── 38. Snapshots history ────────────────────────────────────────────

def save_snapshot(auth: Any, *, label: str | None = None) -> int:
    _init(auth)
    snap = data.snapshot(auth)
    payload = {
        "summary": snap.summary.__dict__,
        "matrix": [s.__dict__ for s in snap.matrix.systems],
        "role_distribution": snap.role_distribution_sixthform,
        "locked": snap.locked, "inactive": snap.inactive,
        "admins": snap.admins,
    }
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO user_snapshots
                (taken_at, taken_by, label, payload)
                VALUES (?, ?, ?, ?)
            ''', (now, actor, label, json.dumps(payload, default=str)))
            sid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("save_snapshot failed")
        raise
    lifecycle._audit(auth, "snapshot_saved", None,
                      {"snapshot_id": sid, "label": label})
    return sid


def list_snapshots(auth: Any) -> list[dict]:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            return [{"snapshot_id": r["snapshot_id"],
                     "taken_at": r["taken_at"],
                     "taken_by": r["taken_by"],
                     "label": r["label"]}
                    for r in conn.execute(
                        "SELECT snapshot_id, taken_at, taken_by, "
                        "label FROM user_snapshots "
                        "ORDER BY taken_at DESC").fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_snapshots failed")
        return []


def diff_snapshots(auth: Any, a_id: int, b_id: int) -> dict:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            a = conn.execute(
                "SELECT payload FROM user_snapshots WHERE snapshot_id = ?",
                (a_id,)).fetchone()
            b = conn.execute(
                "SELECT payload FROM user_snapshots WHERE snapshot_id = ?",
                (b_id,)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("diff_snapshots fetch failed")
        return {}
    if not a or not b:
        return {}
    pa = json.loads(a["payload"])
    pb = json.loads(b["payload"])
    out: dict[str, Any] = {"a": pa, "b": pb, "deltas": {}}
    # Compare top-level numeric fields where present.
    for k in ("locked", "inactive", "admins"):
        if k in pa and k in pb:
            out["deltas"][k] = (pb[k] - pa[k])
    # Role distribution
    ra = pa.get("role_distribution") or {}
    rb = pb.get("role_distribution") or {}
    out["deltas"]["role_distribution"] = {
        k: rb.get(k, 0) - ra.get(k, 0)
        for k in sorted(set(ra) | set(rb))
    }
    return out

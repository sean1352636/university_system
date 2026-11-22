"""Cohorts, audit trail, pinning, clustering, scheduled searches, deltas,
subscriptions, digests, dashboards, saved-search import/export, history and
saved searches for Advanced Search.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (  # noqa: F401
    ALL_SCOPES,
    Cohort,
    Dashboard,
    DashboardPanel,
    Digest,
    DigestLine,
    HistoryEntry,
    MAX_HISTORY_ROWS,
    PinnedResult,
    SavedSearch,
    ScheduleDelta,
    ScheduledSearch,
    SearchAuditEntry,
    ValidationError,
)
from ._db import (  # noqa: F401
    _NAME_RE,
    _connect,
    _validate_scopes,
    init_db,
    logger,
)
from .matching import (  # noqa: F401
    _STUDENT_KEYED_SCOPES,
)
from .query import (  # noqa: F401
    _doc_student_id,
)


# ══════════════════════════════════════════════════════════════════
# Cohorts — named, reusable student sets (item 12)
# ══════════════════════════════════════════════════════════════════

def _cohort_from_row(r: db.Row, members: list[str]) -> Cohort:
    return Cohort(
        cohort_id=r["cohort_id"], name=r["name"],
        owner_actor=r["owner_actor"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        member_count=len(members), members=members,
    )


def _resolve_cohort_id(name_or_id: str | int) -> int | None:
    with _connect() as conn:
        if isinstance(name_or_id, int) or str(name_or_id).isdigit():
            r = conn.execute(
                "SELECT cohort_id FROM cohorts WHERE cohort_id = ?",
                (int(name_or_id),)).fetchone()
        else:
            r = conn.execute(
                "SELECT cohort_id FROM cohorts WHERE name = ?",
                (str(name_or_id).strip(),)).fetchone()
    return r["cohort_id"] if r else None


def _clean_student_ids(student_ids: Any) -> list[str]:
    if isinstance(student_ids, str):
        student_ids = re.split(r"[\s,]+", student_ids)
    out: list[str] = []
    for s in (student_ids or []):
        s2 = str(s).strip()
        if s2 and s2 not in out:
            out.append(s2)
    return out


def create_cohort(name: str, student_ids: Any, *,
                  owner_actor: str | None = None,
                  notes: str | None = None) -> Cohort:
    init_db()
    name = (name or "").strip()
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Cohort name must be 1–48 chars (letters, digits, space, _ . / -)")
    ids = _clean_student_ids(student_ids)
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM cohorts WHERE name = ?",
                        (name,)).fetchone():
            raise ValidationError(f"A cohort named {name!r} already exists")
        cur = conn.execute(
            "INSERT INTO cohorts (name, owner_actor, notes) VALUES (?, ?, ?)",
            (name, (owner_actor or None), (notes or None)))
        cid = cur.lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO cohort_members (cohort_id, student_id) "
            "VALUES (?, ?)", [(cid, s) for s in ids])
        conn.commit()
    logger.info("Created cohort #%d %r with %d member(s)", cid, name, len(ids))
    out = get_cohort(cid)
    assert out is not None
    return out


def create_cohort_from_results(name: str, results: SearchResults, *,
                               owner_actor: str | None = None,
                               notes: str | None = None) -> Cohort:
    """Build a cohort from the student ids present in a result set."""
    return create_cohort(name, _student_ids_from_results(results),
                         owner_actor=owner_actor, notes=notes)


def _student_ids_from_results(results: SearchResults) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for h in results.all_hits():
        sid = ""
        if h.scope == "students":
            sid = h.entity_id
        elif h.scope in _STUDENT_KEYED_SCOPES:
            doc = (h.extra or {}).get("_doc") or {}
            sid = _doc_student_id(h.scope, doc) or _extract_student_id(h)
        sid = str(sid).strip()
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def get_cohort(cohort_id: int) -> Cohort | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM cohorts WHERE cohort_id = ?",
                         (cohort_id,)).fetchone()
        if r is None:
            return None
        members = [row["student_id"] for row in conn.execute(
            "SELECT student_id FROM cohort_members WHERE cohort_id = ? "
            "ORDER BY student_id", (cohort_id,)).fetchall()]
    return _cohort_from_row(r, members)


def get_cohort_by_name(name: str) -> Cohort | None:
    cid = _resolve_cohort_id(name)
    return get_cohort(cid) if cid else None


def list_cohorts() -> list[Cohort]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT c.*, COUNT(m.student_id) AS n FROM cohorts c "
            "LEFT JOIN cohort_members m ON m.cohort_id = c.cohort_id "
            "GROUP BY c.cohort_id ORDER BY c.name ASC").fetchall()
    out: list[Cohort] = []
    for r in rows:
        c = _cohort_from_row(r, [])
        c.member_count = r["n"] or 0
        out.append(c)
    return out


def cohort_members(name_or_id: str | int) -> list[str]:
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        return []
    c = get_cohort(cid)
    return c.members if c else []


def _cohort_member_ids(name: str) -> list[str]:
    return cohort_members(name)


def add_to_cohort(name_or_id: str | int, student_ids: Any) -> int:
    init_db()
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        raise ValidationError(f"No cohort {name_or_id!r}")
    ids = _clean_student_ids(student_ids)
    with _connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM cohort_members WHERE cohort_id = ?",
            (cid,)).fetchone()["n"]
        conn.executemany(
            "INSERT OR IGNORE INTO cohort_members (cohort_id, student_id) "
            "VALUES (?, ?)", [(cid, s) for s in ids])
        conn.execute("UPDATE cohorts SET updated_at = datetime('now') "
                     "WHERE cohort_id = ?", (cid,))
        after = conn.execute(
            "SELECT COUNT(*) AS n FROM cohort_members WHERE cohort_id = ?",
            (cid,)).fetchone()["n"]
        conn.commit()
    return after - before


def remove_from_cohort(name_or_id: str | int, student_ids: Any) -> int:
    init_db()
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        raise ValidationError(f"No cohort {name_or_id!r}")
    ids = _clean_student_ids(student_ids)
    with _connect() as conn:
        cur = conn.executemany(
            "DELETE FROM cohort_members WHERE cohort_id = ? AND student_id = ?",
            [(cid, s) for s in ids])
        conn.execute("UPDATE cohorts SET updated_at = datetime('now') "
                     "WHERE cohort_id = ?", (cid,))
        conn.commit()
        return cur.rowcount


def delete_cohort(name_or_id: str | int) -> bool:
    init_db()
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM cohort_members WHERE cohort_id = ?", (cid,))
        cur = conn.execute("DELETE FROM cohorts WHERE cohort_id = ?", (cid,))
        conn.commit()
    return cur.rowcount > 0


def _record_search_audit(actor: str | None, role: str | None, query: str,
                         scopes: list[str], sensitive: list[str],
                         break_glass: bool, reason: str | None, *,
                         action: str = "search",
                         record_count: int | None = None) -> None:
    ts = _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    try:
        init_db()
        with _connect() as conn:
            conn.execute(
                """INSERT INTO search_audit
                       (ts, actor, role, query, scopes, sensitive_scopes,
                        break_glass, reason, action, record_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ts, actor, role, query, ",".join(scopes),
                 ",".join(sensitive), 1 if break_glass else 0, reason,
                 action, record_count))
            conn.commit()
    except Exception:
        logger.exception("search audit write failed")


def list_search_audit(*, limit: int = 100, actor: str | None = None,
                      sensitive_only: bool = False
                      ) -> list[SearchAuditEntry]:
    """Audit rows, newest first. Without the governance capability a
    signed-in user sees only their own."""
    init_db()
    p = _principal()
    if p.username and not p.can("governance"):
        actor = p.username
    sql = "SELECT * FROM search_audit"
    clauses: list[str] = []
    args: list[Any] = []
    if actor:
        clauses.append("actor = ?")
        args.append(actor)
    if sensitive_only:
        clauses.append("sensitive_scopes <> ''")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY audit_id DESC LIMIT ?"
    args.append(int(limit))
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [SearchAuditEntry(
        audit_id=r["audit_id"], ts=r["ts"], actor=r["actor"],
        role=r["role"], query=r["query"],
        scopes=[s for s in (r["scopes"] or "").split(",") if s],
        sensitive_scopes=[s for s in (r["sensitive_scopes"]
                                       or "").split(",") if s],
        break_glass=bool(r["break_glass"]), reason=r["reason"],
        action=(r["action"] if "action" in r.keys() else None) or "search",
        record_count=(r["record_count"] if "record_count" in r.keys()
                      else None))
            for r in rows]


# ── Pinning (item 36) ─────────────────────────────────────────────

def pin_result(actor: str, scope: str, entity_id: str,
               label: str = "", note: str | None = None) -> PinnedResult:
    init_db()
    actor = _own_actor(actor) or actor
    if scope not in ALL_SCOPES:
        raise ValidationError(f"Unknown scope {scope!r}")
    actor = (actor or "").strip()
    if not actor:
        raise ValidationError("actor is required")
    entity_id = (entity_id or "").strip()
    if not entity_id:
        raise ValidationError("entity_id is required")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO pinned_results
                   (actor, scope, entity_id, label, note, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT (actor, scope, entity_id) DO UPDATE
                   SET label = excluded.label,
                       note  = excluded.note""",
            (actor, scope, entity_id, label or "", note),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = _get_pin(new_id) or _get_pin_for(actor, scope, entity_id)
    assert out is not None
    return out


def unpin_result(actor: str, scope: str, entity_id: str) -> bool:
    init_db()
    actor = _own_actor(actor) or actor
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM pinned_results "
            "WHERE actor = ? AND scope = ? AND entity_id = ?",
            (actor, scope, entity_id),
        )
        conn.commit()
        return cur.rowcount > 0


def _own_actor(actor: str | None) -> str | None:
    """A signed-in user reads their own pins/inbox/digest; asking for
    someone else's (or everyone's) needs the governance capability."""
    p = _principal()
    if p.username and actor != p.username and not p.can("governance"):
        return p.username
    return actor


def list_pinned(actor: str | None = None) -> list[PinnedResult]:
    init_db()
    actor = _own_actor(actor)
    with _connect() as conn:
        if actor is None:
            rows = conn.execute(
                "SELECT * FROM pinned_results "
                "ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pinned_results WHERE actor = ? "
                "ORDER BY created_at DESC", (actor,)).fetchall()
    return [_pin_from_row(r) for r in rows]


def _pin_from_row(r: db.Row) -> PinnedResult:
    return PinnedResult(
        pin_id=r["pin_id"], actor=r["actor"], scope=r["scope"],
        entity_id=r["entity_id"], label=r["label"] or "",
        note=r["note"], created_at=r["created_at"],
    )


def _get_pin(pin_id: int) -> PinnedResult | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM pinned_results WHERE pin_id = ?",
            (pin_id,)).fetchone()
        return _pin_from_row(r) if r else None


def _get_pin_for(actor: str, scope: str,
                 entity_id: str) -> PinnedResult | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM pinned_results "
            "WHERE actor = ? AND scope = ? AND entity_id = ?",
            (actor, scope, entity_id)).fetchone()
        return _pin_from_row(r) if r else None


# ── Clustering (item 37) ──────────────────────────────────────────

def _cluster_by_student(hits: list[Hit]) -> list[Hit]:
    """Group same-student hits into one cluster head per student.

    Cluster head's ``extra['cluster_children']`` lists the absorbed
    hits. Non-student hits pass through unchanged.
    """
    buckets: dict[tuple[str, str], list[Hit]] = {}
    order: list[tuple[str, str] | Hit] = []
    for h in hits:
        sid = ""
        if h.scope in _STUDENT_KEYED_SCOPES:
            sid = (_doc_student_id(h.scope, (h.extra or {}).get("_doc") or {})
                   or _extract_student_id(h))
        if sid:
            key = ("student", sid)
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(h)
        else:
            order.append(h)
    out: list[Hit] = []
    for item in order:
        if isinstance(item, tuple):
            group = buckets[item]
            head = group[0]
            if len(group) > 1:
                head.cluster_count = len(group)
                head.extra = dict(head.extra)
                head.extra["cluster_children"] = group[1:]
                head.extra["cluster_scopes"] = sorted(
                    {g.scope for g in group})
            out.append(head)
        else:
            out.append(item)
    return out


_STUDENT_ID_RE = re.compile(r"(S\d{3,}|[A-Z]\d{4,})")


def _extract_student_id(h: Hit) -> str:
    """Best-effort: pull a student id out of label / entity_id."""
    for src in (h.entity_id, h.label):
        m = _STUDENT_ID_RE.search(src or "")
        if m:
            return m.group(1)
    return ""


# ══════════════════════════════════════════════════════════════════
# Saved searches — ACL, folders (items 38, 40)
# ══════════════════════════════════════════════════════════════════

VALID_VISIBILITIES: tuple[str, ...] = ("private", "role", "public")


def _principal() -> Any:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current()


def _saved_visible(s: SavedSearch, p: Any) -> bool:
    """Whether the signed-in principal may see and run *s*. Searches saved
    before owners were recorded have no owner and stay visible to all."""
    if not p.username or p.is_admin or not s.owner_actor:
        return True
    if s.owner_actor == p.username:
        return True
    if s.visibility == "public":
        return True
    if s.visibility == "role":
        mine = {r.strip().lower() for r in (p.role, p.job_role) if r}
        mine |= {d.lower() for d in p.designations}
        return bool(mine & {r.strip().lower() for r in (s.role_acl or [])})
    return False


def _require_saved_owner(s: SavedSearch, action: str) -> None:
    """Only the owner (or an admin) may change or delete a saved search;
    ownerless legacy ones are admin-only. Nobody signed in = a script."""
    p = _principal()
    if not p.username or p.is_admin:
        return
    if s.owner_actor and s.owner_actor == p.username:
        return
    raise ValidationError(
        f"Only {s.owner_actor or 'an administrator'} can {action} "
        f"the saved search {s.name!r}.")


def _saved_acl_allows(s: SavedSearch, actor: str | None,
                      role: str | None) -> bool:
    if s.visibility == "public":
        return True
    if s.visibility == "private":
        return actor is not None and actor == s.owner_actor
    if s.visibility == "role":
        if not role:
            return False
        return role in (s.role_acl or [])
    return False


# ══════════════════════════════════════════════════════════════════
# Scheduled searches (item 39)
# ══════════════════════════════════════════════════════════════════

def _sched_from_row(r: db.Row) -> ScheduledSearch:
    keys = r.keys()
    return ScheduledSearch(
        schedule_id=r["schedule_id"], saved_id=r["saved_id"],
        cron=r["cron"] or "daily", notify_actor=r["notify_actor"],
        last_run_at=r["last_run_at"], last_count=r["last_count"],
        new_since_last=r["new_since_last"],
        enabled=bool(r["enabled"]), created_at=r["created_at"],
        threshold=(r["threshold"] if "threshold" in keys else 0) or 0,
    )


def schedule_saved_search(saved_id: int, *,
                          cron: str = "daily",
                          notify_actor: str | None = None,
                          enabled: bool = True,
                          threshold: int = 0) -> ScheduledSearch:
    init_db()
    if get_saved_search(saved_id) is None:
        raise ValidationError(f"No saved search #{saved_id}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO scheduled_searches
                   (saved_id, cron, notify_actor, enabled, threshold,
                    created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (saved_id, cron or "daily", notify_actor, 1 if enabled else 0,
             int(threshold)),
        )
        conn.commit()
        sid = cur.lastrowid
        r = conn.execute(
            "SELECT * FROM scheduled_searches WHERE schedule_id = ?",
            (sid,)).fetchone()
    return _sched_from_row(r)


def list_scheduled_searches(*,
                             enabled_only: bool = False
                             ) -> list[ScheduledSearch]:
    init_db()
    sql = "SELECT * FROM scheduled_searches"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY schedule_id"
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [_sched_from_row(r) for r in rows]


def delete_scheduled_search(schedule_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM scheduled_searches WHERE schedule_id = ?",
            (schedule_id,))
        conn.commit()
        return cur.rowcount > 0


def run_scheduled_search(schedule_id: int) -> SearchResults:
    """Run one scheduled saved-search and record delta count."""
    from .engine import run_search  # late: avoids import cycle
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM scheduled_searches WHERE schedule_id = ?",
            (schedule_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No scheduled search #{schedule_id}")
        sched = _sched_from_row(r)
    if not sched.enabled:
        raise ValidationError("Scheduled search is disabled")
    saved = get_saved_search(sched.saved_id)
    if saved is None:
        raise ValidationError(f"Saved search #{sched.saved_id} missing")
    # Run with the subscriber's own access, so the alert never reports
    # records they could not have searched for themselves.
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    token = access.bind_request(access.for_username(sched.notify_actor or ""))
    try:
        results = run_search(
            saved.query, scopes=saved.scopes, filters=saved.filters,
            record_history=True, actor=sched.notify_actor,
        )
    finally:
        access.unbind_request(token)
    new_since = max(0, results.total - sched.last_count)
    with _connect() as conn:
        conn.execute(
            """UPDATE scheduled_searches SET
                   last_run_at = datetime('now'),
                   last_count = ?, new_since_last = ?, last_keys_json = ?
               WHERE schedule_id = ?""",
            (results.total, new_since,
             json.dumps(_result_keys(results)), schedule_id),
        )
        conn.commit()
    return results


def _result_keys(results: SearchResults) -> list[str]:
    return [f"{h.scope}#{h.entity_id}" for h in results.all_hits()]


def schedule_delta(schedule_id: int) -> ScheduleDelta:
    """Run a scheduled saved-search now and report which result keys are
    new or gone since its last recorded run — without updating it (item 28)."""
    from .engine import run_search  # late: avoids import cycle
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM scheduled_searches WHERE schedule_id = ?",
            (schedule_id,)).fetchone()
    if r is None:
        raise ValidationError(f"No scheduled search #{schedule_id}")
    sched = _sched_from_row(r)
    saved = get_saved_search(sched.saved_id)
    if saved is None:
        raise ValidationError(f"Saved search #{sched.saved_id} missing")
    results = run_search(saved.query, scopes=saved.scopes,
                         filters=saved.filters, record_history=False)
    prev_raw = r["last_keys_json"] if "last_keys_json" in r.keys() else None
    try:
        prev = set(json.loads(prev_raw)) if prev_raw else set()
    except (TypeError, ValueError):
        prev = set()
    now_keys = set(_result_keys(results))
    return ScheduleDelta(
        schedule_id=schedule_id, total=results.total,
        added=sorted(now_keys - prev), removed=sorted(prev - now_keys))


# ══════════════════════════════════════════════════════════════════
# Subscriptions (item 41)
# ══════════════════════════════════════════════════════════════════

def poll_subscriptions(*,
                       only_actor: str | None = None
                       ) -> list[ScheduledSearch]:
    """Run all enabled scheduled searches and enqueue a notification row
    for each that returned more hits than its last_count.

    Returns the schedules that emitted a notification this poll. If the
    sixth-form notifications module is available, an in-app
    notification is also dispatched; otherwise the row in
    ``subscription_notifications`` is the queue.
    """
    init_db()
    fired: list[ScheduledSearch] = []
    for sched in list_scheduled_searches(enabled_only=True):
        if only_actor and sched.notify_actor != only_actor:
            continue
        if not sched.notify_actor:
            continue
        try:
            results = run_scheduled_search(sched.schedule_id)
        except ValidationError:
            continue
        if results.total <= sched.last_count:
            continue
        # Threshold alert (item 26): suppress until the running total meets
        # the configured floor (e.g. only ping once ≥5 open concerns).
        if sched.threshold and results.total < sched.threshold:
            continue
        delta = results.total - sched.last_count
        sample = results.ranked_hits[0] if results.ranked_hits else None
        with _connect() as conn:
            conn.execute(
                """INSERT INTO subscription_notifications
                       (schedule_id, actor, delta, total,
                        sample_scope, sample_label, sample_entity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sched.schedule_id, sched.notify_actor, delta,
                 results.total,
                 sample.scope if sample else None,
                 sample.label if sample else None,
                 sample.entity_id if sample else None),
            )
            conn.commit()
        _try_push_notification(sched, delta, sample)
        fired.append(sched)
    return fired


def _try_push_notification(sched: ScheduledSearch, delta: int,
                           sample: Hit | None) -> None:
    """Put an alert in the subscriber's in-app inbox. Never raises — the
    subscription notification row above is the record — but a failure is
    logged rather than hidden."""
    if not sched.notify_actor:
        return
    try:
        from education_system.systems.sixth_form.domains.communications.domain.notifications import (
            notifications as _notif,
        )
        saved = get_saved_search(sched.saved_id)
        name = saved.name if saved else f"#{sched.saved_id}"
        body = (f"Latest: {sample.label} ({sample.scope})"
                if sample else "")
        _notif.create_notification({
            "recipient_type": "Staff",
            "recipient_id": sched.notify_actor,
            "title": f"Saved search '{name}' has {delta} new result(s)",
            "body": body,
            "notification_type": "Alert",
            "status": "Sent",
            "sent_at": _dt.datetime.now().isoformat(timespec="minutes"),
            "sent_by": "advanced_search",
            "linked_to": f"advanced_search:saved:{sched.saved_id}",
        })
    except Exception:
        logger.warning("Could not send the alert for scheduled search #%s",
                       sched.schedule_id, exc_info=True)


def list_subscription_notifications(actor: str, *,
                                    unread_only: bool = False,
                                    include_snoozed: bool = False
                                    ) -> list[dict[str, Any]]:
    init_db()
    actor = _own_actor(actor) or actor
    sql = ("SELECT * FROM subscription_notifications WHERE actor = ?")
    args: list[Any] = [actor]
    if unread_only:
        sql += " AND read_at IS NULL"
    if not include_snoozed:
        # Hide rows snoozed into the future (item 30).
        sql += (" AND (snoozed_until IS NULL "
                "OR snoozed_until <= datetime('now'))")
    sql += " ORDER BY notif_id DESC LIMIT 100"
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def mark_notification_read(notif_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE subscription_notifications SET read_at = "
            "datetime('now') WHERE notif_id = ? AND read_at IS NULL",
            (notif_id,))
        conn.commit()
    return cur.rowcount > 0


def snooze_notification(notif_id: int, *, hours: int = 24) -> bool:
    """Hide a subscription notification until ``hours`` from now (item 30)."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE subscription_notifications "
            "SET snoozed_until = datetime('now', ?) WHERE notif_id = ?",
            (f"+{int(hours)} hours", notif_id))
        conn.commit()
    return cur.rowcount > 0


def build_digest(actor: str | None = None) -> Digest:
    """Roll up every scheduled search (optionally for one actor) into a
    single summary of current totals and deltas since last run."""
    init_db()
    actor = _own_actor(actor)
    lines: list[DigestLine] = []
    total_new = 0
    for sched in list_scheduled_searches():
        if actor and sched.notify_actor != actor:
            continue
        saved = get_saved_search(sched.saved_id)
        name = saved.name if saved else f"#{sched.saved_id}"
        lines.append(DigestLine(
            schedule_id=sched.schedule_id, saved_name=name,
            total=sched.last_count, new_since_last=sched.new_since_last,
            last_run_at=sched.last_run_at))
        total_new += sched.new_since_last
    lines.sort(key=lambda x: -x.new_since_last)
    return Digest(actor=actor, lines=lines, total_new=total_new)


def _resolve_dashboard_id(name_or_id: str | int) -> int | None:
    with _connect() as conn:
        if isinstance(name_or_id, int) or str(name_or_id).isdigit():
            r = conn.execute(
                "SELECT dashboard_id FROM dashboards WHERE dashboard_id = ?",
                (int(name_or_id),)).fetchone()
        else:
            r = conn.execute(
                "SELECT dashboard_id FROM dashboards WHERE name = ?",
                (str(name_or_id).strip(),)).fetchone()
    return r["dashboard_id"] if r else None


def create_dashboard(name: str, saved_ids: list[int] | None = None, *,
                     owner_actor: str | None = None,
                     notes: str | None = None) -> Dashboard:
    init_db()
    name = (name or "").strip()
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Dashboard name must be 1–48 chars (letters, digits, "
            "space, _ . / -)")
    ids = [int(s) for s in (saved_ids or [])]
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM dashboards WHERE name = ?",
                        (name,)).fetchone():
            raise ValidationError(f"A dashboard named {name!r} already exists")
        cur = conn.execute(
            "INSERT INTO dashboards (name, owner_actor, notes) "
            "VALUES (?, ?, ?)", (name, owner_actor or None, notes or None))
        did = cur.lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO dashboard_items "
            "(dashboard_id, saved_id, position) VALUES (?, ?, ?)",
            [(did, sid, i) for i, sid in enumerate(ids)])
        conn.commit()
    out = get_dashboard(did)
    assert out is not None
    return out


def get_dashboard(dashboard_id: int) -> Dashboard | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM dashboards WHERE dashboard_id = ?",
                         (dashboard_id,)).fetchone()
        if r is None:
            return None
        ids = [row["saved_id"] for row in conn.execute(
            "SELECT saved_id FROM dashboard_items WHERE dashboard_id = ? "
            "ORDER BY position, saved_id", (dashboard_id,)).fetchall()]
    return Dashboard(
        dashboard_id=r["dashboard_id"], name=r["name"],
        owner_actor=r["owner_actor"], notes=r["notes"],
        created_at=r["created_at"], saved_ids=ids)


def list_dashboards() -> list[Dashboard]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT dashboard_id FROM dashboards ORDER BY name").fetchall()
    return [d for d in (get_dashboard(r["dashboard_id"]) for r in rows)
            if d is not None]


def add_to_dashboard(name_or_id: str | int, saved_ids: list[int]) -> int:
    init_db()
    did = _resolve_dashboard_id(name_or_id)
    if did is None:
        raise ValidationError(f"No dashboard {name_or_id!r}")
    with _connect() as conn:
        start = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS p "
            "FROM dashboard_items WHERE dashboard_id = ?", (did,)).fetchone()["p"]
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM dashboard_items WHERE dashboard_id = ?",
            (did,)).fetchone()["n"]
        conn.executemany(
            "INSERT OR IGNORE INTO dashboard_items "
            "(dashboard_id, saved_id, position) VALUES (?, ?, ?)",
            [(did, int(sid), start + i) for i, sid in enumerate(saved_ids)])
        after = conn.execute(
            "SELECT COUNT(*) AS n FROM dashboard_items WHERE dashboard_id = ?",
            (did,)).fetchone()["n"]
        conn.commit()
    return after - before


def delete_dashboard(name_or_id: str | int) -> bool:
    init_db()
    did = _resolve_dashboard_id(name_or_id)
    if did is None:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM dashboard_items WHERE dashboard_id = ?",
                     (did,))
        cur = conn.execute("DELETE FROM dashboards WHERE dashboard_id = ?",
                           (did,))
        conn.commit()
    return cur.rowcount > 0


def run_dashboard(name_or_id: str | int, *,
                  actor: str | None = None,
                  role: str | None = None) -> list[DashboardPanel]:
    """Run every saved search in a dashboard and return per-panel counts."""
    from .engine import run_search  # late: avoids import cycle
    init_db()
    did = _resolve_dashboard_id(name_or_id)
    if did is None:
        raise ValidationError(f"No dashboard {name_or_id!r}")
    dash = get_dashboard(did)
    assert dash is not None
    out: list[DashboardPanel] = []
    for sid in dash.saved_ids:
        saved = get_saved_search(sid)
        if saved is None:
            continue
        filters = dict(saved.filters or {})
        if role:
            filters.setdefault("role", role)
        try:
            res = run_search(saved.query, scopes=saved.scopes,
                             filters=filters, actor=actor,
                             record_history=False)
            total = res.total
        except ValidationError:
            total = -1
        out.append(DashboardPanel(saved_id=sid, name=saved.name,
                                  query=saved.query, total=total))
    return out


# ══════════════════════════════════════════════════════════════════
# Export / import saved searches (item 42)
# ══════════════════════════════════════════════════════════════════

EXPORT_FORMAT_VERSION = 1


def export_saved_searches(*,
                          include_schedules: bool = True) -> str:
    """Serialize all saved searches (and optionally their schedules)
    to a JSON string suitable for backup or migration."""
    init_db()
    items = []
    for s in list_saved_searches():
        items.append({
            "name": s.name, "query": s.query, "scopes": s.scopes,
            "filters": s.filters, "notes": s.notes,
            "owner_actor": s.owner_actor, "visibility": s.visibility,
            "role_acl": s.role_acl, "folder": s.folder, "tags": s.tags,
        })
    schedules = []
    if include_schedules:
        # Schedule rows keyed by saved-search name for portability
        by_id = {s.saved_id: s.name for s in list_saved_searches()}
        for sch in list_scheduled_searches():
            if sch.saved_id not in by_id:
                continue
            schedules.append({
                "saved_name": by_id[sch.saved_id],
                "cron": sch.cron, "notify_actor": sch.notify_actor,
                "enabled": sch.enabled,
            })
    return json.dumps(
        {"version": EXPORT_FORMAT_VERSION,
         "saved_searches": items, "schedules": schedules},
        indent=2, ensure_ascii=False)


def import_saved_searches(json_text: str, *,
                          overwrite: bool = False) -> dict[str, int]:
    """Load saved searches from a JSON export. Returns counts."""
    init_db()
    try:
        data = json.loads(json_text)
    except ValueError as e:
        raise ValidationError(f"Invalid JSON: {e}") from None
    if not isinstance(data, dict):
        raise ValidationError("Export payload must be a JSON object")
    items = data.get("saved_searches") or []
    created = 0
    updated = 0
    skipped = 0
    saved_ids_by_name: dict[str, int] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        name = (raw.get("name") or "").strip()
        if not name:
            skipped += 1
            continue
        existing = get_saved_search_by_name(name)
        if existing and not overwrite:
            saved_ids_by_name[name] = existing.saved_id
            skipped += 1
            continue
        try:
            if existing and overwrite:
                update_saved_search(existing.saved_id, raw)
                saved_ids_by_name[name] = existing.saved_id
                updated += 1
            else:
                s = create_saved_search(raw)
                saved_ids_by_name[name] = s.saved_id
                created += 1
        except ValidationError:
            skipped += 1
    sched_created = 0
    for sch in (data.get("schedules") or []):
        sname = (sch.get("saved_name") or "").strip()
        sid = saved_ids_by_name.get(sname)
        if not sid:
            continue
        try:
            schedule_saved_search(
                sid, cron=sch.get("cron") or "daily",
                notify_actor=sch.get("notify_actor"),
                enabled=bool(sch.get("enabled", True)))
            sched_created += 1
        except ValidationError:
            pass
    return {"created": created, "updated": updated,
            "skipped": skipped, "schedules": sched_created}


# ── History ───────────────────────────────────────────────────────

def _record_history(query: str, scopes: list[str],
                    actor: str | None, count: int,
                    *,
                    elapsed_ms: dict[str, float] | None = None,
                    result_counts: dict[str, int] | None = None,
                    ) -> None:
    ts = _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO search_history
                   (ts, query, scopes, actor, result_count,
                    elapsed_ms_json, result_count_json, zero_result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, query, ",".join(scopes), actor or None, int(count),
             json.dumps(elapsed_ms) if elapsed_ms else None,
             json.dumps(result_counts) if result_counts else None,
             1 if int(count) == 0 else 0),
        )
        # Keep the latest MAX_HISTORY_ROWS per user, so one busy account
        # cannot push everyone else's history out.
        conn.execute(
            """DELETE FROM search_history
                WHERE actor IS ? AND history_id NOT IN (
                    SELECT history_id FROM search_history
                     WHERE actor IS ?
                     ORDER BY ts DESC, history_id DESC
                     LIMIT ?
                )""",
            (actor or None, actor or None, MAX_HISTORY_ROWS))
        conn.commit()


def _history_actor(actor: str | None, all_users: bool) -> tuple[bool, str | None]:
    """(filter?, actor) for a history read. Signed-in users see their own
    history; ``all_users`` needs the governance capability."""
    p = _principal()
    if all_users:
        if p.username and not p.can("governance"):
            raise ValidationError(
                "Only governance staff can see everyone's search history.")
        return False, None
    who = p.username or actor
    return (who is not None), who


def list_history(limit: int = 20, *, actor: str | None = None,
                 all_users: bool = False) -> list[HistoryEntry]:
    """Recent searches, newest first — the signed-in user's own."""
    init_db()
    filtered, who = _history_actor(actor, all_users)
    with _connect() as conn:
        if filtered:
            rows = conn.execute(
                "SELECT * FROM search_history WHERE actor = ? "
                "ORDER BY ts DESC, history_id DESC LIMIT ?",
                (who, int(limit))).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM search_history "
                "ORDER BY ts DESC, history_id DESC LIMIT ?",
                (int(limit),)).fetchall()
    out: list[HistoryEntry] = []
    for r in rows:
        out.append(HistoryEntry(
            history_id=r["history_id"], ts=r["ts"],
            query=r["query"],
            scopes=[s for s in (r["scopes"] or "").split(",") if s],
            actor=r["actor"], result_count=r["result_count"],
        ))
    return out


def clear_history(*, actor: str | None = None,
                  all_users: bool = False) -> int:
    """Clear the signed-in user's own history (everyone's needs
    ``all_users`` and the governance capability)."""
    init_db()
    filtered, who = _history_actor(actor, all_users)
    with _connect() as conn:
        if filtered:
            cur = conn.execute("DELETE FROM search_history WHERE actor = ?",
                               (who,))
        else:
            cur = conn.execute("DELETE FROM search_history")
        conn.commit()
    return cur.rowcount


# ── Saved searches ────────────────────────────────────────────────

def _saved_from_row(r: db.Row) -> SavedSearch:
    try:
        filters = json.loads(r["filters"]) if r["filters"] else {}
    except (TypeError, ValueError):
        filters = {}
    keys = r.keys()
    try:
        role_acl = (json.loads(r["role_acl"])
                    if "role_acl" in keys and r["role_acl"] else [])
    except (TypeError, ValueError):
        role_acl = []
    try:
        tags_raw = r["tags"] if "tags" in keys else None
        tags = json.loads(tags_raw) if tags_raw else []
    except (TypeError, ValueError):
        tags = []
    return SavedSearch(
        saved_id=r["saved_id"], name=r["name"], query=r["query"],
        scopes=[s for s in (r["scopes"] or "").split(",") if s],
        filters=filters, notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        owner_actor=(r["owner_actor"] if "owner_actor" in keys else None),
        visibility=((r["visibility"]
                     if "visibility" in keys else None) or "private"),
        role_acl=role_acl,
        folder=(r["folder"] if "folder" in keys else None),
        tags=tags,
    )


def _validate_saved_payload(payload: dict[str, Any]) -> dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValidationError("Name is required")
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Name must be 1–48 chars (letters, digits, space, _ . / -)")
    scopes = _validate_scopes(payload.get("scopes"))
    filters = payload.get("filters") or {}
    if isinstance(filters, str):
        s = filters.strip()
        if s:
            try:
                filters = json.loads(s)
            except ValueError as e:
                raise ValidationError(
                    f"filters is not valid JSON: {e}") from None
        else:
            filters = {}
    if not isinstance(filters, dict):
        raise ValidationError("filters must be a JSON object")
    visibility = (payload.get("visibility") or "private").strip().lower()
    if visibility not in VALID_VISIBILITIES:
        raise ValidationError(
            f"visibility must be one of {', '.join(VALID_VISIBILITIES)}")
    role_acl = payload.get("role_acl") or []
    if isinstance(role_acl, str):
        role_acl = [r.strip() for r in role_acl.split(",") if r.strip()]
    if not isinstance(role_acl, (list, tuple)):
        raise ValidationError("role_acl must be a list of role names")
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, (list, tuple)):
        raise ValidationError("tags must be a list")
    folder = (payload.get("folder") or "").strip() or None
    owner = (payload.get("owner_actor") or "").strip() or None
    return {
        "name": name,
        "query": (payload.get("query") or "").strip(),
        "scopes": scopes,
        "filters": json.dumps(filters) if filters else None,
        "notes": (payload.get("notes") or "").strip() or None,
        "owner_actor": owner,
        "visibility": visibility,
        "role_acl": json.dumps(list(role_acl)) if role_acl else None,
        "folder": folder,
        "tags": json.dumps(list(tags)) if tags else None,
    }


def create_saved_search(payload: dict[str, Any]) -> SavedSearch:
    """Save a search. The signed-in user is always its owner."""
    init_db()
    me = _principal().username
    if me:
        payload = {**payload, "owner_actor": me}
    p = _validate_saved_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM saved_searches WHERE name = ?",
                (p["name"],)).fetchone():
            raise ValidationError(
                f"A saved search named {p['name']!r} already exists")
        cur = conn.execute(
            """INSERT INTO saved_searches
                   (name, query, scopes, filters, notes,
                    owner_actor, visibility, role_acl, folder, tags,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["query"], ",".join(p["scopes"]),
             p["filters"], p["notes"],
             p["owner_actor"], p["visibility"], p["role_acl"],
             p["folder"], p["tags"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_saved_search(new_id)
    assert out is not None
    logger.info("Created saved search #%d %r", new_id, p["name"])
    return out


def get_saved_search(saved_id: int) -> SavedSearch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM saved_searches WHERE saved_id = ?",
            (saved_id,)).fetchone()
        return _saved_from_row(r) if r else None


def get_saved_search_by_name(name: str) -> SavedSearch | None:
    """The saved search called *name*, if the signed-in user may see it."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM saved_searches WHERE name = ?",
            (name.strip(),)).fetchone()
    s = _saved_from_row(r) if r else None
    return s if s is not None and _saved_visible(s, _principal()) else None


def list_saved_searches(
    *,
    folder: str | None = None,
    actor: str | None = None,
    role: str | None = None,
    include_public: bool = True,
) -> list[SavedSearch]:
    """List saved searches.

    A signed-in user sees what they own, what is shared with their role
    or publicly, and ownerless legacy searches; an admin sees everything.
    With nobody signed in, ``actor``/``role`` filter by ACL, and without
    either all rows are returned (scripts)."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM saved_searches ORDER BY name ASC").fetchall()
    out = [_saved_from_row(r) for r in rows]
    if folder is not None:
        out = [s for s in out if (s.folder or "") == folder]
    p = _principal()
    if p.username:
        return [s for s in out if _saved_visible(s, p)]
    if actor is None and role is None:
        return out
    return [s for s in out
            if (include_public and s.visibility == "public")
            or _saved_acl_allows(s, actor, role)]


def list_saved_folders() -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT folder FROM saved_searches "
            "WHERE folder IS NOT NULL AND folder <> '' "
            "ORDER BY folder ASC").fetchall()
    return [r["folder"] for r in rows]


def update_saved_search(saved_id: int,
                        payload: dict[str, Any]) -> SavedSearch:
    init_db()
    existing = get_saved_search(saved_id)
    if existing is None:
        raise ValidationError(f"No saved search #{saved_id}")
    _require_saved_owner(existing, "change")
    if _principal().username and not _principal().is_admin:
        payload = {k: v for k, v in payload.items() if k != "owner_actor"}
    merged = {
        "name":        payload.get("name", existing.name),
        "query":       payload.get("query", existing.query),
        "scopes":      payload.get("scopes", existing.scopes),
        "filters":     payload.get("filters", existing.filters),
        "notes":       payload.get("notes", existing.notes),
        "owner_actor": payload.get("owner_actor", existing.owner_actor),
        "visibility":  payload.get("visibility", existing.visibility),
        "role_acl":    payload.get("role_acl", existing.role_acl),
        "folder":      payload.get("folder", existing.folder),
        "tags":        payload.get("tags", existing.tags),
    }
    p = _validate_saved_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT saved_id FROM saved_searches WHERE name = ?",
            (p["name"],)).fetchone()
        if row and row["saved_id"] != saved_id:
            raise ValidationError(
                f"A saved search named {p['name']!r} already exists")
        conn.execute(
            """UPDATE saved_searches SET
                   name = ?, query = ?, scopes = ?, filters = ?,
                   notes = ?, owner_actor = ?, visibility = ?,
                   role_acl = ?, folder = ?, tags = ?,
                   updated_at = datetime('now')
               WHERE saved_id = ?""",
            (p["name"], p["query"], ",".join(p["scopes"]),
             p["filters"], p["notes"],
             p["owner_actor"], p["visibility"], p["role_acl"],
             p["folder"], p["tags"], saved_id),
        )
        conn.commit()
    out = get_saved_search(saved_id)
    assert out is not None
    logger.info("Updated saved search #%d %r", saved_id, p["name"])
    return out


def delete_saved_search(saved_id: int) -> bool:
    init_db()
    existing = get_saved_search(saved_id)
    if existing is None:
        return False
    _require_saved_owner(existing, "delete")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM saved_searches WHERE saved_id = ?",
            (saved_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted saved search #%d", saved_id)
            return True
        return False


def run_saved_search(saved_id: int, *,
                     actor: str | None = None) -> SearchResults:
    from .engine import run_search  # late: avoids import cycle
    s = get_saved_search(saved_id)
    if s is None or not _saved_visible(s, _principal()):
        raise ValidationError(f"No saved search #{saved_id}")
    return run_search(
        s.query, scopes=s.scopes, filters=s.filters,
        actor=actor,
    )

"""Retention purge for health data, driven by ``data_retention_policies``.

Only the health tables named in :data:`TABLES` are ever touched, and only
rows older than their policy's retention period. A policy deletes only when
``auto_delete = 1`` (and ``is_active``); ``deletion_method = 'soft'`` marks
rows deleted where the table has a ``deleted_at`` / ``is_deleted`` column
and deletes them otherwise. Every run that removes anything — by a person or
the daily worker — is written to the immutable audit log in the same
transaction, and ``last_cleanup_date`` is stamped on the policy.
"""

from __future__ import annotations

from datetime import datetime, timedelta

#: policy data_type -> (table, the date that ages the row)
TABLES: dict[str, tuple[str, str]] = {
    "health_records": ("health_records", "record_date"),
    "vaccination_records": ("vaccination_records", "administered_date"),
    "appointments": ("health_appointments", "appointment_date"),
    "prescriptions": ("prescriptions", "prescribed_date"),
    "lab_results": ("lab_results", "ordered_date"),
    "vital_signs": ("vital_signs", "measurement_date"),
}


def _columns(conn, table) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _policies(conn, *, auto_only: bool):
    cols = _columns(conn, "data_retention_policies")
    if not cols:
        return []
    where = ["1=1"]
    if auto_only:
        where.append("auto_delete = 1")
    if "is_active" in cols:
        where.append("COALESCE(is_active, 1) = 1")
    method = "deletion_method" if "deletion_method" in cols else "'hard'"
    return conn.execute(
        f"SELECT id, data_type, retention_period_days, auto_delete, {method} "  # nosec B608
        f"FROM data_retention_policies WHERE {' AND '.join(where)} ORDER BY data_type").fetchall()


def plan(conn, now=None, *, auto_only: bool = True) -> list[dict]:
    """What a purge would remove: one entry per health policy."""
    now = now or datetime.now()
    out = []
    for pid, data_type, days, auto_delete, method in _policies(conn, auto_only=auto_only):
        target = TABLES.get(data_type)
        if not target or not days:
            continue
        table, date_col = target
        cols = _columns(conn, table)
        if date_col not in cols:
            continue
        cutoff = (now - timedelta(days=int(days))).strftime("%Y-%m-%d")
        live = ""
        if "is_deleted" in cols:
            live = " AND COALESCE(is_deleted, 0) = 0"
        elif "deleted_at" in cols:
            live = " AND deleted_at IS NULL"
        count = conn.execute(
            f'SELECT COUNT(*) FROM "{table}" WHERE "{date_col}" < ?{live}',  # nosec B608
            (cutoff,)).fetchone()[0]
        out.append({"policy_id": pid, "data_type": data_type, "table": table,
                    "date_column": date_col, "cutoff": cutoff, "count": count,
                    "auto_delete": bool(auto_delete), "method": (method or "hard").lower(),
                    "soft_column": ("is_deleted" if "is_deleted" in cols else
                                    "deleted_at" if "deleted_at" in cols else None)})
    return out


def purge(conn, *, by: str, dry_run: bool = True, now=None) -> dict:
    """Remove health rows past their retention period (auto_delete policies
    only). With ``dry_run`` nothing changes and the plan is returned. The
    caller commits."""
    now = now or datetime.now()
    entries = plan(conn, now, auto_only=True)
    report = {"dry_run": dry_run, "removed": {}, "plan": entries}
    if dry_run:
        return report
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    for e in entries:
        if not e["count"]:
            continue
        table, col = e["table"], e["date_column"]
        if e["method"] == "soft" and e["soft_column"] == "is_deleted":
            cur = conn.execute(f'UPDATE "{table}" SET is_deleted = 1 WHERE "{col}" < ? '  # nosec B608
                               "AND COALESCE(is_deleted, 0) = 0", (e["cutoff"],))
        elif e["method"] == "soft" and e["soft_column"] == "deleted_at":
            cur = conn.execute(f'UPDATE "{table}" SET deleted_at = ? WHERE "{col}" < ? '  # nosec B608
                               "AND deleted_at IS NULL", (stamp, e["cutoff"]))
        else:
            cur = conn.execute(f'DELETE FROM "{table}" WHERE "{col}" < ?',  # nosec B608
                               (e["cutoff"],))
        report["removed"][e["data_type"]] = cur.rowcount
    if "last_cleanup_date" in _columns(conn, "data_retention_policies"):
        for e in entries:
            conn.execute("UPDATE data_retention_policies SET last_cleanup_date = ? WHERE id = ?",
                         (stamp, e["policy_id"]))
    if report["removed"]:
        from education_system.systems.university.infrastructure.security.immutable_audit_log import (
            log_security_event,
        )
        log_security_event(user_id=str(by), action="HEALTH_RETENTION_PURGE",
                           resource_type="health_retention", resource_id="policies",
                           details={"removed": report["removed"],
                                    "cutoffs": {e["data_type"]: e["cutoff"] for e in entries}},
                           conn=conn)
    return report


def any_auto_delete(conn) -> bool:
    return any(TABLES.get(p[1]) for p in _policies(conn, auto_only=True))


#: Who may change retention policies or run a purge.
RETENTION_ROLES = ("health_admin", "admin", "administrator", "superadmin")
DELETION_METHODS = ("soft", "hard")


def may_manage(who) -> bool:
    return bool(who and who.role in RETENTION_ROLES)


def require_manager(who, what="change retention policies") -> None:
    if not may_manage(who):
        raise PermissionError(f"Only a health administrator can {what}")


def list_policies(conn) -> list[dict]:
    """Every retention policy, with whether this module can apply it (its
    data type maps to a health table, :data:`TABLES`)."""
    cols = _columns(conn, "data_retention_policies")
    if not cols:
        return []
    wanted = [c for c in ("id", "data_type", "retention_period_days", "auto_archive",
                          "auto_delete", "deletion_method", "is_active", "last_cleanup_date",
                          "updated_at") if c in cols]
    cur = conn.execute(f"SELECT {', '.join(wanted)} FROM data_retention_policies "  # nosec B608
                       "ORDER BY data_type, id")
    out = []
    for row in cur.fetchall():
        item = dict(zip(wanted, tuple(row)))
        item["applies_to"] = TABLES.get(item.get("data_type"), (None,))[0]
        out.append(item)
    return out


def update_policy(conn, who, policy_id, *, retention_period_days, auto_delete,
                  deletion_method="soft", is_active=True) -> dict:
    """Change one policy (health administrators only), audited in ``conn``'s
    transaction; returns the old values. Does not commit."""
    require_manager(who)
    try:
        days = int(str(retention_period_days).strip())
    except ValueError:
        raise ValueError("Retention period must be a whole number of days") from None
    if days < 30:
        raise ValueError("A retention period shorter than 30 days is not allowed")
    if deletion_method not in DELETION_METHODS:
        raise ValueError(f"Deletion method must be one of {', '.join(DELETION_METHODS)}")
    cols = _columns(conn, "data_retention_policies")
    old = next((p for p in list_policies(conn) if p["id"] == int(policy_id)), None)
    if old is None:
        raise LookupError(f"Retention policy {policy_id} not found")
    values = {"retention_period_days": days, "auto_delete": 1 if auto_delete else 0}
    if "deletion_method" in cols:
        values["deletion_method"] = deletion_method
    if "is_active" in cols:
        values["is_active"] = 1 if is_active else 0
    if "updated_at" in cols:
        values["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(f"UPDATE data_retention_policies SET "  # nosec B608
                 f"{', '.join(f'{k} = ?' for k in values)} WHERE id = ?",
                 (*values.values(), int(policy_id)))
    from education_system.systems.university.infrastructure.security.immutable_audit_log import (
        log_security_event,
    )
    log_security_event(user_id=who.username, action="HEALTH_RETENTION_POLICY_CHANGE",
                       resource_type="health_retention", resource_id=str(policy_id),
                       details={"old": {k: old.get(k) for k in values}, "new": values},
                       conn=conn)
    return old


__all__ = ["TABLES", "RETENTION_ROLES", "DELETION_METHODS", "plan", "purge", "any_auto_delete",
           "may_manage", "require_manager", "list_policies", "update_policy"]

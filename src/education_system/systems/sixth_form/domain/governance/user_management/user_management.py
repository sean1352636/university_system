"""User Management — roles and access overview for the Sixth Form System.

A read-and-grant layer on top of the shared auth DB. Whereas
``shared.user_accounts`` does full per-user CRUD, this module focuses
on the *roles and access* perspective:

* the **access matrix**: for each system, who has access and at what
  role level;
* **role distribution**: per-role counts for the sixth-form system;
* bulk operations: **grant a role to many users**, **revoke a role
  for many users**;
* a summary aggregating active / inactive / locked / admin counts.

Everything ultimately calls the shared :mod:`user_accounts` helpers,
so cascades, password rules and session invalidation are inherited.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.platform.identity.auth.role_manager import ROLE_HIERARCHY
from education_system.systems.sixth_form.interfaces import user_accounts as _ua
from education_system.systems.sixth_form.interfaces.user_accounts import (
    DEFAULT_ROLE,
    ROLES,
    SYSTEM_KEY,
    UserAccountError,
    UserRow,
)

logger = logging.getLogger(__name__)

# Recognised system keys — anything in user_systems beyond these still
# appears in matrices, but these are the ones we surface first.
KNOWN_SYSTEMS: tuple[str, ...] = ("sixth_form", "secondary", "university")


# ── Access matrix / role distribution ──────────────────────────────

@dataclass
class SystemAccess:
    """Per-system access roll-up: how many users have access, and at
    what role mix."""
    system_key: str
    users: int
    by_role: dict[str, int] = field(default_factory=dict)


@dataclass
class AccessMatrix:
    systems: list[SystemAccess]
    users_without_sixthform: list[UserRow]


def access_matrix(auth: Any) -> AccessMatrix:
    """Build the access matrix from every user's ``systems`` list."""
    users = _ua.list_users(auth)
    per_system: dict[str, SystemAccess] = {}
    for u in users:
        for s in u.systems:
            key = s.get("system_key") or "(unknown)"
            role = s.get("role") or "(none)"
            entry = per_system.setdefault(key, SystemAccess(key, 0))
            entry.users += 1
            entry.by_role[role] = entry.by_role.get(role, 0) + 1
    # Sort: known systems first (in declared order), then the rest alpha.
    ordered: list[SystemAccess] = []
    for k in KNOWN_SYSTEMS:
        if k in per_system:
            ordered.append(per_system.pop(k))
    for k in sorted(per_system):
        ordered.append(per_system[k])

    without = [u for u in users if u.role_for(SYSTEM_KEY) is None]
    return AccessMatrix(systems=ordered, users_without_sixthform=without)


def role_distribution(auth: Any,
                       system_key: str = SYSTEM_KEY) -> dict[str, int]:
    """Counts of each role *within a single system*."""
    users = _ua.list_users(auth, system_key=system_key)
    counts: dict[str, int] = {r: 0 for r in ROLE_HIERARCHY}
    for u in users:
        role = u.role_for(system_key)
        if role:
            counts[role] = counts.get(role, 0) + 1
    return counts


# ── Bulk grant / revoke ────────────────────────────────────────────

@dataclass
class BulkResult:
    succeeded: list[int] = field(default_factory=list)
    failed: list[tuple[int, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.succeeded) + len(self.failed)


def bulk_grant(auth: Any, user_ids: list[int],
                 system_key: str, role: str) -> BulkResult:
    if role not in ROLE_HIERARCHY:
        raise UserAccountError(
            f"Role must be one of: {', '.join(ROLE_HIERARCHY)}")
    if not user_ids:
        return BulkResult()
    result = BulkResult()
    for uid in user_ids:
        try:
            _ua.grant_role(auth, uid, system_key, role)
            result.succeeded.append(uid)
        except Exception as e:
            logger.warning("bulk_grant failed for user_id=%d: %s", uid, e)
            result.failed.append((uid, str(e)))
    logger.info("Bulk grant '%s' on '%s': %d ok, %d failed",
                role, system_key,
                len(result.succeeded), len(result.failed))
    return result


def bulk_revoke(auth: Any, user_ids: list[int],
                  system_key: str) -> BulkResult:
    if not user_ids:
        return BulkResult()
    result = BulkResult()
    for uid in user_ids:
        try:
            _ua.revoke_role(auth, uid, system_key)
            result.succeeded.append(uid)
        except Exception as e:
            logger.warning("bulk_revoke failed for user_id=%d: %s", uid, e)
            result.failed.append((uid, str(e)))
    logger.info("Bulk revoke on '%s': %d ok, %d failed",
                system_key, len(result.succeeded), len(result.failed))
    return result


def bulk_set_active(auth: Any, user_ids: list[int],
                      active: bool) -> BulkResult:
    if not user_ids:
        return BulkResult()
    result = BulkResult()
    for uid in user_ids:
        try:
            _ua.set_active(auth, uid, active)
            result.succeeded.append(uid)
        except Exception as e:
            logger.warning("bulk_set_active failed for user_id=%d: %s",
                           uid, e)
            result.failed.append((uid, str(e)))
    return result


# ── Pre-filtered listings ──────────────────────────────────────────

def list_admins(auth: Any, *,
                 system_key: str = SYSTEM_KEY) -> list[UserRow]:
    return _ua.list_users(auth, system_key=system_key, role="admin")


def list_without_access(auth: Any, *,
                          system_key: str = SYSTEM_KEY) -> list[UserRow]:
    return [u for u in _ua.list_users(auth)
             if u.role_for(system_key) is None]


def list_locked(auth: Any) -> list[UserRow]:
    return _ua.list_users(auth, locked_only=True)


def list_inactive(auth: Any) -> list[UserRow]:
    return [u for u in _ua.list_users(auth) if not u.is_active]


# ── Snapshot ───────────────────────────────────────────────────────

@dataclass
class Snapshot:
    summary: _ua.Summary
    matrix: AccessMatrix
    role_distribution_sixthform: dict[str, int]
    locked: int
    inactive: int
    admins: int


def snapshot(auth: Any) -> Snapshot:
    s = _ua.summary(auth)
    m = access_matrix(auth)
    return Snapshot(
        summary=s,
        matrix=m,
        role_distribution_sixthform=role_distribution(auth, SYSTEM_KEY),
        locked=s.locked,
        inactive=s.inactive,
        admins=len(list_admins(auth)),
    )

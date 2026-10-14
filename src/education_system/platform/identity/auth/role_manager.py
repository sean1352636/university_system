"""Role-Based Access Control with per-system role assignments.

Also the platform's cross-system authorisation vocabulary. Each system
names its roles in its own words (an apprenticeship has an ``employer``
and an ``end_point_assessor``; a school has a ``teacher`` and a
``parent``), so a question that crosses systems — "may this person
approve a transfer out of the sixth form?" — cannot be asked in any one
system's vocabulary. :data:`SYSTEM_ROLE_CAPABILITIES` maps every system's
roles onto one small set of capability classes, and
:data:`CAPABILITY_PERMISSIONS` grants the cross-system permissions by
class. The API, GUI and CLI all ask :func:`has_cross_system_permission`
rather than comparing role strings.
"""

import logging
from collections.abc import Iterable, Mapping

from education_system.platform.identity.auth.db import connect
from education_system.platform.kernel.core.system_keys import canonical_system_key

logger = logging.getLogger(__name__)

# Unified role hierarchy across all systems
ROLE_HIERARCHY = {
    "admin": 100,
    "staff": 75,
    "instructor": 50,
    "teacher": 50,
    # An independent assessor grades the apprentice's end-point assessment
    # but belongs to neither the provider nor the employer, so it ranks
    # below teaching staff and sees only the gateway and EPA screens.
    "end_point_assessor": 45,
    "teaching_assistant": 40,
    # The employer approves and reviews its own apprentices: a guardian-like
    # external party, one step above a parent.
    "employer": 35,
    "parent": 30,
    "student": 25,
    # Same standing as a student; the apprenticeships system's word for one.
    "apprentice": 25,
    "alumni": 20,
}


# ---------------------------------------------------------------------------
# Cross-system capability classes
# ---------------------------------------------------------------------------

CAPABILITY_CLASSES: tuple[str, ...] = (
    "learner", "guardian", "staff", "manager", "admin",
    "external_assessor", "employer",
)

#: Default role -> capability class, for every system that uses the shared
#: vocabulary. ``staff`` is the admissions/office tier above teaching staff
#: (it outranks ``teacher`` in ROLE_HIERARCHY), which is why it maps to
#: ``manager``: that is the tier that runs a transfer.
_DEFAULT_ROLE_CAPABILITIES: dict[str, str] = {
    "admin": "admin",
    "superadmin": "admin",
    "manager": "manager",
    "staff": "manager",
    "teacher": "staff",
    "instructor": "staff",
    "teaching_assistant": "staff",
    "parent": "guardian",
    "guardian": "guardian",
    "student": "learner",
    "pupil": "learner",
    "alumni": "learner",
    "apprentice": "learner",
    "employer": "employer",
    "end_point_assessor": "external_assessor",
}

#: Per-system role vocabularies (see ``launcher/roles.py`` for the labels
#: each system shows). Only the systems whose words differ from the default
#: need an entry; a role missing here falls back to the default map.
SYSTEM_ROLE_CAPABILITIES: dict[str, dict[str, str]] = {
    # The apprenticeship provider's "staff" are tutors and workplace
    # assessors carrying a caseload, not an admissions office.
    "apprenticeships": {
        "admin": "admin",
        "staff": "staff",
        "apprentice": "learner",
        "employer": "employer",
        "end_point_assessor": "external_assessor",
    },
}

# ── Cross-system permissions ──────────────────────────────────────────
PERM_TRANSFER_VIEW = "transfer.view"
PERM_TRANSFER_APPROVE = "transfer.approve"
PERM_TRANSFER_ACKNOWLEDGE = "transfer.acknowledge"
PERM_IDENTITY_MERGE = "identity.merge"
PERM_EVENTS_VIEW = "events.view"
PERM_LEARNER360_VIEW = "learner360.view"

CROSS_SYSTEM_PERMISSIONS: tuple[str, ...] = (
    PERM_TRANSFER_VIEW, PERM_TRANSFER_APPROVE, PERM_TRANSFER_ACKNOWLEDGE,
    PERM_IDENTITY_MERGE, PERM_EVENTS_VIEW, PERM_LEARNER360_VIEW,
)

#: Permissions each capability class holds *within the systems where the
#: user has that class*. identity.merge is deliberately absent: merging two
#: journeys rewrites every system's view of who a learner is, so only a
#: platform superadmin may do it.
CAPABILITY_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({PERM_TRANSFER_VIEW, PERM_TRANSFER_APPROVE,
                        PERM_TRANSFER_ACKNOWLEDGE, PERM_EVENTS_VIEW,
                        PERM_LEARNER360_VIEW}),
    "manager": frozenset({PERM_TRANSFER_VIEW, PERM_TRANSFER_APPROVE,
                          PERM_TRANSFER_ACKNOWLEDGE, PERM_LEARNER360_VIEW}),
    "staff": frozenset({PERM_TRANSFER_VIEW, PERM_LEARNER360_VIEW}),
    "external_assessor": frozenset(),
    "employer": frozenset(),
    "guardian": frozenset(),
    "learner": frozenset(),
}

#: Admin in all four of these makes a platform superadmin. Mirrors
#: ``launcher.roles.is_superadmin`` (the platform may not import the
#: launcher) and keeps its rule: a university administrator alone is a
#: system-scoped admin, not a superadmin.
SUPERADMIN_SYSTEMS: frozenset[str] = frozenset(
    {"university", "sixth_form", "secondary", "primary"})


def capability_for(system_key: str | None, role: str | None) -> str | None:
    """The capability class *role* carries in *system_key*, or ``None``."""
    if not role:
        return None
    role = str(role).strip().lower()
    system = canonical_system_key(system_key) if system_key else None
    per_system = SYSTEM_ROLE_CAPABILITIES.get(system or "", {})
    return per_system.get(role) or _DEFAULT_ROLE_CAPABILITIES.get(role)


def is_superadmin_systems(systems: Iterable[Mapping] | None) -> bool:
    """True if a ``[{"system_key", "role"}, ...]`` list is a superadmin's."""
    admin_keys = {
        canonical_system_key(s.get("system_key"))
        for s in systems or () if str(s.get("role") or "").lower() == "admin"
    }
    return admin_keys >= SUPERADMIN_SYSTEMS


def permitted_systems(systems: Iterable[Mapping] | None,
                      permission: str) -> set[str]:
    """Canonical system keys in which the user holds *permission*."""
    out: set[str] = set()
    for s in systems or ():
        system = canonical_system_key(s.get("system_key"))
        capability = capability_for(system, s.get("role"))
        if system and permission in CAPABILITY_PERMISSIONS.get(capability or "", ()):
            out.add(system)
    return out


def has_cross_system_permission(systems: Iterable[Mapping] | None,
                                permission: str,
                                system_key: str | None = None) -> bool:
    """Whether the user may perform *permission*, optionally in one system.

    A superadmin holds every permission everywhere. Otherwise the answer is
    per system: an admin of the primary school may approve a transfer out
    of the primary school, not one out of the university.
    """
    systems = list(systems or ())
    if is_superadmin_systems(systems):
        return True
    held = permitted_systems(systems, permission)
    if system_key is None:
        return bool(held)
    return canonical_system_key(system_key) in held


def cross_system_permissions(systems: Iterable[Mapping] | None) -> dict[str, list[str]]:
    """``{permission: [system, ...]}`` — the whole grant, for display.

    A superadmin's entry for each permission is ``["*"]``.
    """
    systems = list(systems or ())
    if is_superadmin_systems(systems):
        return {p: ["*"] for p in CROSS_SYSTEM_PERMISSIONS}
    return {p: sorted(permitted_systems(systems, p))
            for p in CROSS_SYSTEM_PERMISSIONS}


class RoleManager:
    """Manages roles and permissions using the shared auth database."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def get_role_level(self, role: str) -> int:
        """Get the hierarchy level for a role."""
        return ROLE_HIERARCHY.get(role, 0)

    def has_minimum_role(self, user_role: str, required_role: str) -> bool:
        """Check if user_role meets or exceeds the required_role level."""
        return self.get_role_level(user_role) >= self.get_role_level(required_role)

    def get_user_role_for_system(self, user_id: int, system_key: str) -> str | None:
        """Get the user's role for a specific system.

        *system_key* is normalised so legacy names (``college``/``school``/
        ``sixthform``) resolve to the same canonical system as the new keys.
        """
        from education_system.platform.kernel.core.system_keys import canonical_system_key
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT role FROM user_systems WHERE user_id = ? AND system_key = ?",
                (user_id, canonical_system_key(system_key)),
            ).fetchone()
            return row["role"] if row else None
        finally:
            conn.close()

    def get_user_systems(self, user_id: int) -> list[dict]:
        """Get all systems a user has access to, with their role in each."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return [{"system_key": r["system_key"], "role": r["role"]} for r in rows]
        finally:
            conn.close()

    def grant_system_access(self, user_id: int, system_key: str, role: str):
        """Grant a user access to a system with the specified role."""
        if role not in ROLE_HIERARCHY:
            raise ValueError(f"Invalid role: {role}")

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO user_systems (user_id, system_key, role)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, system_key) DO UPDATE SET role = ?""",
                (user_id, system_key, role, role),
            )
            conn.commit()
            logger.info("Granted %s access to system '%s' for user_id=%d", role, system_key, user_id)
        finally:
            conn.close()

    def revoke_system_access(self, user_id: int, system_key: str):
        """Revoke a user's access to a system."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM user_systems WHERE user_id = ? AND system_key = ?",
                (user_id, system_key),
            )
            conn.commit()
            logger.info("Revoked access to system '%s' for user_id=%d", system_key, user_id)
        finally:
            conn.close()

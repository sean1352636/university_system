"""Who is signed in to the Adult Education system, and what they may do.

The unified launcher signs the user in and hands over its shared
``UserAuth`` session; :func:`from_auth` turns it into a :class:`Principal`.
Every screen asks the principal before it opens or changes anything.

Roles (``auth.defaults.SYSTEM_ROLES["adult_education"]``):

* ``admin`` - everything;
* ``staff`` - tutors and curriculum/admin staff: every area, but not deleting records.

Anything else (no role, an unknown role, or a learner/parent role from
another system) fails closed: the window refuses to open. There is no
learner portal yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SYSTEM_KEY = "adult_education"
#: Spellings an account's systems list may use for this system.
_KEYS = frozenset({SYSTEM_KEY, "adult", "adulteducation", "adult-education",
                   "community_learning"})
STAFF_ROLES = frozenset({"admin", "staff"})


@dataclass(frozen=True)
class Principal:
    username: str
    role: str | None = None
    user_id: int | None = None

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def can_open(self, label: str) -> bool:  # noqa: ARG002 - every area is staff-wide
        return self.is_staff

    def can_edit(self, area: str) -> bool:  # noqa: ARG002
        return self.is_staff

    def can_delete(self, area: str) -> bool:  # noqa: ARG002
        return self.is_admin

    def denied_message(self, label: str) -> str:
        return f"Your role ({self.role or 'none'}) can't open {label}."


ANONYMOUS = Principal(username="", role=None)


def _role_from_systems(systems: Any) -> str | None:
    for s in systems or []:
        if isinstance(s, dict) and s.get("system_key") in _KEYS:
            return s.get("role")
    return None


def from_auth(auth: Any, role: str | None = None) -> Principal:
    """Principal for the launcher's signed-in session.

    The launcher-supplied *role* (a superadmin picks one on entry) wins over
    the account's ``adult_education`` entry, which wins over its general
    role. A missing session fails closed.
    """
    cu = getattr(auth, "current_user", None) or {}
    if not isinstance(cu, dict):
        return ANONYMOUS
    resolved = role or _role_from_systems(cu.get("systems")) or cu.get("role")
    return Principal(
        username=cu.get("username", "") or "",
        role=str(resolved).lower() if resolved else None,
        user_id=cu.get("id") or cu.get("user_id"),
    )


def require_shared_session(shared_auth: Any, interface: str) -> None:
    """Refuse to start without the launcher's signed-in session (no standalone login)."""
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        raise RuntimeError(
            f"The Adult Education {interface.upper()} must be launched via python -m "
            "education_system (--adulteducation) - there is no standalone login.")


def refusal(principal: Principal) -> str:
    return ("The Adult Education system is for Adult Education staff only.\n\n"
            f"Your account is signed in as '{principal.role or 'no role'}'.")

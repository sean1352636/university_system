"""Which pupil records a signed-in student or parent may read.

Each school system's own-record screens go through one :class:`OwnRecordGate`,
so there is one answer to "whose record is this?" and it fails closed:

* identity comes only from the signed-in session, and is checked against
  auth.db on every read, so a deactivated account or a removed role takes
  effect at once;
* a student maps to exactly one pupil. The evidence is the login's learner link
  (``users.journey_id``) and the system's own pairing rule
  (``PhaseAdapter.learner_ids_for_login``: exact pupil id or school e-mail).
  If the evidence is missing or names more than one pupil, no record is shown;
* a parent maps only to the children in ``parent_child_links``. Parents are
  never paired by name, contact e-mail or anything else, and the chosen child
  is re-checked against those links on every read;
* a pupil who is not on roll is not shown to anyone through these screens.

There is no matching on names and no ``LIKE`` anywhere on this path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

STUDENT = "student"
PARENT = "parent"


class OwnRecordError(Exception):
    """A record cannot be shown. ``str(error)`` is safe to show the user."""


class NoRecordLink(OwnRecordError):
    """The login has no safe link to any pupil record."""


class RecordRefused(OwnRecordError):
    """The login may not read what was asked for."""


@dataclass(frozen=True)
class SessionAccount:
    """A signed-in account, as auth.db says it is right now."""

    user_id: int
    username: str
    display_name: str
    email: str | None
    journey_id: str | None
    role: str


def session_account(auth: Any, system_key: str) -> SessionAccount:
    """The session's account and its live role in *system_key*, or refuse."""
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.kernel.core.system_keys import canonical_system_key

    user = getattr(auth, "current_user", None)
    if not isinstance(user, dict):
        raise RecordRefused("You are not signed in.")
    user_id = user.get("user_id") or user.get("id")
    username = str(user.get("username") or "").strip()
    if not isinstance(user_id, int) or isinstance(user_id, bool) or not username:
        raise RecordRefused("You are not signed in.")

    conn = auth_db.connect()
    try:
        account = conn.execute(
            "SELECT id, username, display_name, email, is_active, journey_id "
            "FROM users WHERE id = ?", (user_id,)).fetchone()
        grants = conn.execute(
            "SELECT system_key, role FROM user_systems WHERE user_id = ?",
            (user_id,)).fetchall()
    finally:
        conn.close()

    if account is None or account["username"] != username or not account["is_active"]:
        raise RecordRefused("This account can no longer open these records.")
    roles = {str(g["role"] or "").strip().lower() for g in grants
             if canonical_system_key(g["system_key"]) == system_key}
    if len(roles) != 1:
        raise RecordRefused("This account has no role here that can open these records.")
    return SessionAccount(
        user_id=int(account["id"]), username=account["username"],
        display_name=account["display_name"] or account["username"],
        email=account["email"], journey_id=account["journey_id"], role=roles.pop())


def _ids_from_learner_link(account: SessionAccount, system_key: str,
                           pupil_for_journey: Callable[[str], Any]) -> set[str]:
    """Pupil ids named by the login's ``users.journey_id``, if it has one."""
    from education_system.platform.cross_system import identity_service

    if not account.journey_id:
        return set()
    journey_id = identity_service.resolve_journey_id(account.journey_id)
    if journey_id is None:
        return set()
    found: set[str] = set()
    journey = identity_service.get(journey_id) or {}
    _pk, id_column = identity_service.SYSTEM_SLOTS[system_key]
    if journey.get(id_column):
        found.add(str(journey[id_column]))
    local = pupil_for_journey(journey_id)
    if local is not None:
        found.add(str(local.pupil_id))
    return found


def _ids_from_sign_in_rule(account: SessionAccount, system_key: str) -> set[str]:
    """Pupil ids the system's own pairing rule finds for this login."""
    from education_system.platform.cross_system.adapters import registry

    adapter = registry.load(system_key)
    if adapter is None or not adapter.pairs_logins():
        return set()
    ids = adapter.learner_ids_for_login({
        "id": account.user_id, "username": account.username,
        "email": account.email, "display_name": account.display_name})
    return {str(i) for i in ids if i not in (None, "")}


class OwnRecordGate:
    """One system's answer to "whose record may this session read?"."""

    def __init__(self, system_key: str, *,
                 get_pupil: Callable[[str], Any],
                 pupil_for_journey: Callable[[str], Any],
                 on_roll: str = "on_roll",
                 office: str = "the school office") -> None:
        self.system_key = system_key
        self._get_pupil = get_pupil
        self._pupil_for_journey = pupil_for_journey
        self._on_roll = on_roll
        self._office = office

    def account(self, auth: Any) -> SessionAccount:
        return session_account(auth, self.system_key)

    def _account_as(self, auth: Any, role: str) -> SessionAccount:
        account = self.account(auth)
        if account.role != role:
            raise RecordRefused(f"These records are for {role} accounts only.")
        return account

    def _on_roll_pupil(self, pupil_id: str) -> Any:
        pupil = self._get_pupil(pupil_id)
        if pupil is None or getattr(pupil, "roll_status", None) != self._on_roll:
            return None
        return pupil

    def student(self, auth: Any, pupil_id: str | None = None) -> Any:
        """The one pupil this student's session belongs to.

        *pupil_id* exists only so a caller's id can be refused: identity never
        comes from it.
        """
        account = self._account_as(auth, STUDENT)
        ids = (_ids_from_learner_link(account, self.system_key, self._pupil_for_journey)
               | _ids_from_sign_in_rule(account, self.system_key))
        if not ids:
            raise NoRecordLink(
                "Your login is not linked to a pupil record, so no records can be "
                f"shown. Please ask {self._office} to check your account.")
        if len(ids) > 1:
            logger.warning("Login %s matches %d pupil records; showing none",
                           account.username, len(ids))
            raise NoRecordLink(
                "Your login matches more than one pupil record, so no records can be "
                f"shown. Please ask {self._office} to check your account.")
        own_id = next(iter(ids))
        if pupil_id is not None and pupil_id != own_id:
            logger.warning("Refused pupil id passed for student login %s", account.username)
            raise RecordRefused("You can only open your own records.")
        pupil = self._on_roll_pupil(own_id)
        if pupil is None:
            raise NoRecordLink(
                "Your login does not match a pupil currently on roll, so no records "
                f"can be shown. Please ask {self._office} to check your account.")
        return pupil

    def children(self, auth: Any) -> list[Any]:
        """This parent's own linked children who are on roll."""
        from education_system.platform.identity.auth import db as auth_db
        from education_system.platform.services.parent_child_link import active_child_ids

        account = self._account_as(auth, PARENT)
        ids = active_child_ids(str(auth_db.PLATFORM_AUTH_DB_FILE), account.user_id,
                               self.system_key)
        pupils = [self._on_roll_pupil(i) for i in ids]
        return [p for p in pupils if p is not None]

    def child(self, auth: Any, pupil_id: str) -> Any:
        """A child of this parent's, re-checked against the links on every read."""
        children = self.children(auth)
        if not children:
            raise NoRecordLink(
                "Your login is not linked to a child at this school, so no records can "
                f"be shown. Please ask {self._office} to link your account.")
        for pupil in children:
            if pupil.pupil_id == pupil_id:
                return pupil
        logger.warning("Refused pupil id passed for parent login %s",
                       getattr(auth, "current_user", {}).get("username"))
        raise RecordRefused("You can only open records for your own linked children.")

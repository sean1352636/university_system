"""Keep apprentice logins linked to their platform learner record.

The rules and the linking itself live in ``platform.cross_system.login_links``
and apply to every system; see its docstring for what is and is not linked.
This system contributes two things:

* the pairing — ``ApprenticeshipsAdapter.learner_ids_for_login``: the
  apprentice record whose ``username`` is the login's, the same rule
  sign-in uses;
* the hooks — the moments in this system when that pairing can change
  (an apprentice created or renamed, a role granted, a login attached to a
  record, degree access granted, sign-in), which call the functions here.

Links made on this system's pairing are audited under :data:`AUTO_ACTOR`.
"""

from __future__ import annotations

from education_system.platform.cross_system import login_links as _core
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
)
from education_system.systems.apprenticeships.services.access import SYSTEM_KEY

AUTO_ACTOR = _core.auto_actor(SYSTEM_KEY)

LINKED = _core.LINKED
RELINKED = _core.RELINKED
UNLINKED = _core.UNLINKED
UNCHANGED = _core.UNCHANGED
SKIPPED = _core.SKIPPED
ACTIONS = _core.ACTIONS
LinkOutcome = _core.LinkOutcome


def _ready() -> None:
    """Make sure the platform can reach this system's pairing.

    The adapter is registered at launch; a script, the API or a test may
    not have launched this system, and without the adapter every login
    would look like it had no learner record.
    """
    from education_system.systems.apprenticeships.infrastructure.integrations import (
        cross_system_adapter,
    )

    cross_system_adapter.register()


def sync_username(username: str | None, *, db_path: str | None = None) -> LinkOutcome | None:
    """Bring one login's learner link into line with the records."""
    _ready()
    return _core.sync_username(username, db_path=db_path)


def sync_apprentice(apprentice_id: int, *, previous_username: str | None = None,
                    db_path: str | None = None) -> list[LinkOutcome]:
    """Sync the login on one apprentice record, and the one it replaced.

    *previous_username* is the login the record held before an edit; it
    is re-checked so a link made for this record is taken off it.
    """
    record = apprentice_repository.get(apprentice_id)
    names: list[str] = []
    if record is not None and (record.username or "").strip():
        names.append(record.username.strip())
    previous = (previous_username or "").strip()
    if previous and previous.lower() not in {n.lower() for n in names}:
        names.append(previous)
    return [o for o in (sync_username(n, db_path=db_path) for n in names) if o]


def sync_all(*, db_path: str | None = None) -> dict[str, int]:
    """Sync every apprenticeships login; counts by action. Idempotent."""
    _ready()
    return _core.sync_all(systems=(SYSTEM_KEY,), db_path=db_path)


def try_sync_username(username: str | None, *,
                      db_path: str | None = None) -> LinkOutcome | None:
    """:func:`sync_username` for hooks: a failure is logged, never raised."""
    try:
        return sync_username(username, db_path=db_path)
    except Exception:
        _core.logger.warning("Could not check the learner link for login %s", username,
                             exc_info=True)
        return None


def try_sync_apprentice(apprentice_id: int, *, previous_username: str | None = None,
                        db_path: str | None = None) -> list[LinkOutcome]:
    """:func:`sync_apprentice` for hooks: a failure is logged, never raised."""
    try:
        return sync_apprentice(apprentice_id, previous_username=previous_username,
                               db_path=db_path)
    except Exception:
        _core.logger.warning("Could not check the learner link for apprentice %s",
                             apprentice_id, exc_info=True)
        return []


__all__ = [
    "ACTIONS",
    "AUTO_ACTOR",
    "LinkOutcome",
    "sync_all",
    "sync_apprentice",
    "sync_username",
    "try_sync_apprentice",
    "try_sync_username",
]

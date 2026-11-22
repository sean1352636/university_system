"""Link each learner's own login to their platform learner record.

A learner's login (a ``users`` row in auth.db) and their learner record (a
``journey_id``) are the same person, joined by ``users.journey_id``. This
module keeps that link without anyone setting it by hand. It does not know
how any system pairs a login with a learner — each system's adapter
answers that (``PhaseAdapter.learner_ids_for_login``) with the rule its
own sign-in uses — so the platform never imports a system to do it.

The rules are cautious, because a wrong link shows one person's learner
record, and sends their notifications, to another:

* only a role a system names as a learner's own login
  (``PhaseAdapter.learner_login_roles``) is considered — never a parent,
  guardian or staff role;
* every learner role the account holds is asked, and if the answers
  belong to different learners nothing is linked (and an automatic link
  made before the clash is taken off) — that is for an administrator;
* a link somebody set by hand is never overwritten or removed. Links made
  here carry an audit actor ending ``:auto-link`` (``<system>:auto-link``);
  only those may be moved or removed automatically.

Every change goes through ``identity_service.link_user_account`` /
``unlink_user_account``, so it is recorded in ``security_audit_log``.
Losing a learner role does not unlink: the login is still that person's.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

AUTO_SUFFIX = ":auto-link"

LINKED = "linked"
RELINKED = "relinked"
UNLINKED = "unlinked"
UNCHANGED = "unchanged"
SKIPPED = "skipped"
ACTIONS = (LINKED, RELINKED, UNLINKED, UNCHANGED, SKIPPED)


def auto_actor(system: str) -> str:
    """The audit actor for a link made on *system*'s pairing."""
    return f"{system}{AUTO_SUFFIX}"


@dataclass(frozen=True)
class LinkOutcome:
    """What one sync did to one login, and why."""

    username: str
    action: str
    journey_id: str | None = None
    reason: str = ""
    systems: tuple[str, ...] = ()


# ═════════════════════════════════════════════════════════════════════
# Syncing
# ═════════════════════════════════════════════════════════════════════

def sync_username(username: str | None, *, db_path: str | None = None) -> LinkOutcome | None:
    """Bring one login's learner link into line with the systems' records.

    Returns None for a blank username. *db_path* is the platform auth.db.
    """
    name = (username or "").strip()
    if not name:
        return None
    account = _account_by_name(name, db_path)
    if account is None:
        return LinkOutcome(name, SKIPPED, reason="no platform account with this username")
    return _sync(account, db_path)


def sync_user(user_id: int, *, db_path: str | None = None) -> LinkOutcome | None:
    """:func:`sync_username` by ``users.id``."""
    rows = _rows("SELECT id, username, email, display_name FROM users WHERE id = ?",
                 (int(user_id),), db_path)
    return _sync(rows[0], db_path) if rows else None


def sync_email(email: str | None, *, db_path: str | None = None) -> list[LinkOutcome]:
    """Sync every account whose email is *email* (case-insensitive).

    For a system that pairs logins with learners by email, a learner
    record gaining or changing an email is the moment its pairing changes,
    and the accounts to re-check are found by that address.
    """
    address = (email or "").strip()
    if not address:
        return []
    rows = _rows("SELECT id FROM users WHERE LOWER(email) = LOWER(?) ORDER BY id",
                 (address,), db_path)
    return [o for o in (sync_user(int(r["id"]), db_path=db_path) for r in rows) if o]


def sync_all(*, systems: Iterable[str] | None = None,
             db_path: str | None = None) -> dict[str, int]:
    """Sync every login that could need a link; counts by action.

    That is every account holding a learner role in a system that pairs
    logins, plus every account linked automatically before (so a stale
    automatic link is found after its record lost the login). *systems*
    narrows both to those systems. Idempotent: a second run reports
    nothing linked, relinked or unlinked.
    """
    wanted = {_canonical(s) for s in systems} if systems is not None else None
    counts = dict.fromkeys(ACTIONS, 0)
    candidates = _candidate_users(wanted, db_path)
    try:
        settled = _settled_without_sync(candidates, db_path)
    except Exception:
        logger.warning("Could not pre-check learner logins in one pass; checking each",
                       exc_info=True)
        settled = {}
    for action in settled.values():
        counts[action] += 1
    for user_id in candidates:
        if user_id in settled:
            continue
        outcome = try_sync_user(user_id, db_path=db_path)
        counts[outcome.action if outcome else SKIPPED] += 1
    if counts[LINKED] + counts[RELINKED] + counts[UNLINKED]:
        logger.info("Learner login links synced%s: %s",
                    f" for {sorted(wanted)}" if wanted else "", counts)
    return counts


def try_sync_username(username: str | None, *,
                      db_path: str | None = None) -> LinkOutcome | None:
    """:func:`sync_username` for hooks: a failure is logged, never raised."""
    try:
        return sync_username(username, db_path=db_path)
    except Exception:
        logger.warning("Could not check the learner link for login %s", username,
                       exc_info=True)
        return None


def try_sync_user(user_id: int, *, db_path: str | None = None) -> LinkOutcome | None:
    """:func:`sync_user` for hooks: a failure is logged, never raised."""
    try:
        return sync_user(user_id, db_path=db_path)
    except Exception:
        logger.warning("Could not check the learner link for user %s", user_id,
                       exc_info=True)
        return None


def try_sync_email(email: str | None, *, db_path: str | None = None) -> list[LinkOutcome]:
    """:func:`sync_email` for hooks: a failure is logged, never raised."""
    try:
        return sync_email(email, db_path=db_path)
    except Exception:
        logger.warning("Could not check learner links for email %s", email, exc_info=True)
        return []


def try_sync_all(*, systems: Iterable[str] | None = None,
                 db_path: str | None = None) -> dict[str, int] | None:
    """:func:`sync_all` for start-up: a failure is logged, never raised."""
    try:
        return sync_all(systems=systems, db_path=db_path)
    except Exception:
        logger.warning("Learner login links could not be synced", exc_info=True)
        return None


# ═════════════════════════════════════════════════════════════════════
# The decision
# ═════════════════════════════════════════════════════════════════════

def _sync(account: Any, db_path: str | None) -> LinkOutcome:
    from education_system.platform.cross_system import identity_service

    name = str(account["username"])
    user_id = int(account["id"])
    current = identity_service.journey_for_user(user_id, db_path=db_path)
    ours = _linked_automatically(user_id, db_path)

    eligible, records = _learner_records(account, db_path)
    systems = tuple(sorted(records))
    if not eligible:
        return LinkOutcome(name, SKIPPED, current,
                           "the account holds no learner role in a system that pairs logins")

    if not any(records.values()):
        if current and ours:
            identity_service.unlink_user_account(user_id, actor=_actor(eligible),
                                                 db_path=db_path)
            return LinkOutcome(name, UNLINKED, current,
                               "no learner record uses this login any more", systems)
        return LinkOutcome(name, UNCHANGED, current, "no learner record uses this login",
                           systems)

    journeys: dict[str, set[str]] = {}
    for system, ids in records.items():
        for local_id in ids:
            jid = _journey_for(system, local_id, db_path)
            if jid:
                journeys.setdefault(jid, set()).add(system)
    if not journeys:
        return LinkOutcome(name, SKIPPED, current,
                           "the learner record is not registered on the platform yet", systems)
    if len(journeys) > 1:
        logger.warning(
            "Login %s resolves to different learners (%s); not linking it until an "
            "administrator resolves that", name, {s: records[s] for s in systems})
        reason = "this login's learner records belong to different learners"
        if current and ours:
            # Made when the records agreed; now it is not knowable which
            # learner is right, so the guess comes off.
            identity_service.unlink_user_account(user_id, actor=_actor(eligible),
                                                 db_path=db_path)
            return LinkOutcome(name, UNLINKED, current, reason, systems)
        return LinkOutcome(name, SKIPPED, current, reason, systems)

    ((target, sources),) = journeys.items()
    actor = auto_actor(sorted(sources)[0])
    if current == target:
        return LinkOutcome(name, UNCHANGED, target, systems=systems)
    if current is None:
        identity_service.link_user_account(user_id, target, actor=actor, db_path=db_path)
        return LinkOutcome(name, LINKED, target, systems=systems)
    if ours:
        identity_service.link_user_account(user_id, target, actor=actor, db_path=db_path)
        return LinkOutcome(name, RELINKED, target,
                           "the login moved to another learner's record", systems)
    logger.warning(
        "Login %s was linked by hand to learner %s, but its learner record belongs to "
        "%s; leaving the manual link alone", name, current, target)
    return LinkOutcome(name, SKIPPED, current,
                       f"linked by hand to another learner record ({current})", systems)


def _learner_records(account: Any, db_path: str | None) -> tuple[list[str], dict[str, list[str]]]:
    """(systems where the account holds a learner role, {system: local ids}).

    Only systems whose adapter pairs logins count, and only the roles that
    adapter names as a learner's own login.
    """
    eligible: list[str] = []
    records: dict[str, list[str]] = {}
    grants = _rows("SELECT system_key, role FROM user_systems WHERE user_id = ?",
                   (int(account["id"]),), db_path)
    for grant in grants:
        system = _canonical(grant["system_key"])
        adapter = _pairing_adapter(system)
        role = str(grant["role"] or "").strip().lower()
        if adapter is None or role not in adapter.learner_login_roles:
            continue
        eligible.append(system)
        ids = adapter.learner_ids_for_login(dict(account))
        records.setdefault(system, []).extend(str(i) for i in ids if i not in (None, ""))
    return eligible, records


def _pairing_adapter(system: str) -> Any:
    from education_system.platform.cross_system.adapters import registry

    try:
        adapter = registry.load(system)
    except Exception:
        logger.debug("No adapter loadable for %s", system, exc_info=True)
        return None
    return adapter if adapter is not None and adapter.pairs_logins() else None


# ═════════════════════════════════════════════════════════════════════
# Internals
# ═════════════════════════════════════════════════════════════════════

def _rows(sql: str, params: tuple[Any, ...], db_path: str | None) -> list[Any]:
    from education_system.platform.identity.auth.db import connect

    conn = connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _canonical(system_key: str | None) -> str:
    from education_system.platform.kernel.core.system_keys import canonical_system_key

    return canonical_system_key(system_key) or str(system_key or "")


def _actor(systems: list[str]) -> str:
    return auto_actor(sorted(systems)[0])


def _account_by_name(name: str, db_path: str | None) -> Any:
    """The shared-auth account for *name*; an exact-case match wins a tie."""
    rows = _rows(
        "SELECT id, username, email, display_name FROM users "
        "WHERE LOWER(username) = LOWER(?) ORDER BY (username = ?) DESC, id LIMIT 1",
        (name, name), db_path)
    return rows[0] if rows else None


def _linked_automatically(user_id: int, db_path: str | None) -> bool:
    """Was the account's current link made here?

    Read from the audit trail ``link_user_account`` writes: the latest
    link-or-unlink entry says who set what the account holds now. A link
    with no audit entry at all was not made here, so it is treated like a
    manual one and left alone.
    """
    rows = _rows(
        "SELECT event_type, username FROM security_audit_log "
        "WHERE user_id = ? AND event_type IN ('identity.user_linked', "
        "'identity.user_unlinked') ORDER BY id DESC LIMIT 1",
        (user_id,), db_path)
    return bool(rows) and rows[0]["event_type"] == "identity.user_linked" \
        and str(rows[0]["username"] or "").endswith(AUTO_SUFFIX)


def _journey_for(system: str, local_id: str, db_path: str | None) -> str | None:
    from education_system.platform.cross_system import identity_service

    row = identity_service.find_by_student(system, local_id, db_path=db_path)
    return row["journey_id"] if row else None


def _settled_without_sync(user_ids: list[int], db_path: str | None) -> dict[int, str]:
    """Candidates whose sync can only report UNCHANGED or SKIPPED: {id: action}.

    A login with no link today and no learner record behind it in any
    system that pairs logins leaves :func:`_sync` nothing to do — it
    returns SKIPPED (no learner role) or UNCHANGED (a learner role, no
    record) without writing. Settling those from three batched reads keeps
    the start-up catch-up from re-checking thousands of logins one at a
    time. Anything uncertain — an existing link, a record found, an adapter
    that fails — is left out so it gets the full per-login check.
    """
    if not user_ids:
        return {}
    from education_system.platform.identity.auth.db import connect

    wanted_ids = set(user_ids)
    conn = connect(db_path)
    try:
        accounts = {int(r["id"]): r for r in conn.execute(
            "SELECT id, username, email, display_name, journey_id FROM users")
            if int(r["id"]) in wanted_ids}
        grants = [g for g in conn.execute("SELECT user_id, system_key, role FROM user_systems")
                  if g["user_id"] is not None and int(g["user_id"]) in wanted_ids]
    finally:
        conn.close()

    eligible: dict[int, set[str]] = {}
    for grant in grants:
        system = _canonical(grant["system_key"])
        adapter = _pairing_adapter(system)
        role = str(grant["role"] or "").strip().lower()
        if adapter is not None and role in adapter.learner_login_roles:
            eligible.setdefault(int(grant["user_id"]), set()).add(system)

    has_records: set[int] = set()
    by_system: dict[str, list[dict]] = {}
    for uid, systems_held in eligible.items():
        if uid in accounts:
            for system in systems_held:
                by_system.setdefault(system, []).append(
                    {k: accounts[uid][k] for k in ("id", "username", "email", "display_name")})
    for system, batch in by_system.items():
        try:
            found = _pairing_adapter(system).learner_ids_for_logins(batch)
        except Exception:
            logger.warning("Could not pair %s logins in one pass; checking them one by one",
                           system, exc_info=True)
            has_records.update(int(a["id"]) for a in batch)
            continue
        for a in batch:
            if any(i not in (None, "") for i in found.get(int(a["id"]), [])):
                has_records.add(int(a["id"]))

    settled: dict[int, str] = {}
    for uid in user_ids:
        account = accounts.get(uid)
        if account is None or account["journey_id"] or uid in has_records:
            continue
        settled[uid] = UNCHANGED if eligible.get(uid) else SKIPPED
    return settled


def _candidate_users(wanted: set[str] | None, db_path: str | None) -> list[int]:
    ids: set[int] = set()
    for grant in _rows("SELECT user_id, system_key, role FROM user_systems", (), db_path):
        system = _canonical(grant["system_key"])
        if wanted is not None and system not in wanted:
            continue
        adapter = _pairing_adapter(system)
        if adapter is not None and str(grant["role"] or "").lower() in adapter.learner_login_roles:
            ids.add(int(grant["user_id"]))
    for row in _rows(
            "SELECT DISTINCT user_id, username FROM security_audit_log "
            "WHERE event_type = 'identity.user_linked' AND username LIKE ?",
            (f"%{AUTO_SUFFIX}",), db_path):
        system = str(row["username"])[: -len(AUTO_SUFFIX)]
        if row["user_id"] is not None and (wanted is None or system in wanted):
            ids.add(int(row["user_id"]))
    return sorted(ids)


__all__ = [
    "ACTIONS",
    "AUTO_SUFFIX",
    "LinkOutcome",
    "auto_actor",
    "sync_all",
    "sync_email",
    "sync_user",
    "sync_username",
    "try_sync_all",
    "try_sync_email",
    "try_sync_user",
    "try_sync_username",
]

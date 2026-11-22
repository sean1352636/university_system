"""Who the caller is on the university side, for the API routes.

A signed-in token names the person twice, in two id spaces that overlap
without agreeing:

* ``user_id`` is the central ``auth.db`` id. Cross-system messages key on it.
* ``sub`` is the username, which is the only value that means the same person
  in ``student_records.db``. ``messages``, ``chat_room_members`` and
  ``announcements`` key on that database's own ``users.id``.

``admin`` is 19 centrally and 1 locally, and local id 19 is a student, so
handing ``user_id`` to a local table does not fail: it reads someone else's
rows. Every local id here therefore comes from the username, and a caller with
no local profile gets ``None``, never a fallback to the central id.
"""

from __future__ import annotations

from types import SimpleNamespace

from flask import g

from education_system.systems.university.infrastructure.auth.session_user import (
    resolve_local_identity,
)

#: Roles the communication services do not know by name, as the ones they do.
_SERVICE_ROLE = {"superadmin": "admin", "teacher": "instructor", "faculty": "instructor"}


def username() -> str:
    return str((g.get("current_user") or {}).get("sub") or "")


def shared_auth_id():
    """The central auth.db id. Only for tables keyed on it."""
    return (g.get("current_user") or {}).get("user_id")


def service_role() -> str:
    role = str((g.get("current_user") or {}).get("role") or "").lower()
    return _SERVICE_ROLE.get(role, role)


def local_identity() -> tuple[int | None, str | None]:
    """``(student_records users.id, student_id)``; once per request."""
    cached = g.get("_university_local_identity")
    if cached is None:
        cached = resolve_local_identity(username()) if username() else (None, None)
        g._university_local_identity = cached
    return cached


def local_user_id() -> int | None:
    return local_identity()[0]


def owns(owner_id) -> bool:
    """Whether a TEXT owner column names the caller.

    Compared with the username and the local student id only. The central
    numeric id is left out on purpose, because ``owner_id`` holds free-form
    references and a stray ``"19"`` must not match auth id 19.
    """
    owner = str(owner_id or "")
    if not owner:
        return False
    return owner in {username(), str(local_identity()[1] or "")}


def communications():
    """The communication service, acting as the caller; ``None`` with no profile.

    Built from the same mixins as the GUI's ``CommunicationDashboard`` so the
    rules cannot drift (bans, mutes, the safeguarding filter, encrypted rooms).
    Its ``__init__`` is skipped: that creates tables, writes templates and can
    start the mail workers, none of which belongs in a request.
    """
    local_id = local_user_id()
    if local_id is None:
        return None
    from education_system.systems.university.infrastructure.email.admin import (
        _AnnouncementsMixin,
        _ChatMixin,
        _LoggingMixin,
    )

    class _Communications(_ChatMixin, _AnnouncementsMixin, _LoggingMixin):
        pass

    service = _Communications.__new__(_Communications)
    service.auth = SimpleNamespace(current_user={
        "id": local_id,
        "username": username(),
        "display_name": username(),
        "role": service_role(),
    })
    return service

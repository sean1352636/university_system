"""Who can see which pupil in the pupil and parent portals.

* **Pupils** sign in with the login made when they were added
  (:mod:`pupil_accounts`). Staff can also link an existing login to a pupil
  by hand (``kind = 'pupil'``) - e.g. the seeded ``student2``.
* **Parents** get a login automatically: every contact with parental
  responsibility and an e-mail address is linked to a parent login matched on
  that address, so one login covers all their children. A new login is made
  (username ``firstname.lastname``, a random password, the ``welcome_parent``
  e-mail); a login that already has the address (say, from another school in
  the platform) is reused and just gains the secondary parent role. Changing
  the contact (address, parental responsibility) or deleting it moves or
  removes the link; when a parent has no children left the parent role comes
  off again. Staff can also link a login to a pupil as their parent by hand.

Every portal read goes through :func:`pupils_for` / :func:`require_pupil`,
so a portal can only ever show a pupil the signed-in login is linked to, and
only while the pupil is on roll.
"""

from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.communication.domain import email_templates
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

WELCOME_TEMPLATE = "welcome_parent"
LINKED_TEMPLATE = "parent_linked"
KINDS = ("pupil", "parent")
ROLE_FOR = {"pupil": accounts.PUPIL_ROLE, "parent": accounts.PARENT_ROLE}
#: Staff roles that may also hold parent links (a teacher whose child is here).
_STAFF = frozenset({"admin", "superadmin", "teacher", "staff"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portal_links (
    link_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL COLLATE NOCASE,
    user_id      INTEGER,
    pupil_id     INTEGER NOT NULL REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('pupil', 'parent')),
    source       TEXT NOT NULL CHECK (source IN ('contact', 'manual')),
    contact_id   INTEGER REFERENCES pupil_contacts(contact_id) ON DELETE SET NULL,
    granted_role INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'removed')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    created_by   TEXT,
    removed_at   TEXT,
    removed_by   TEXT
);
CREATE INDEX IF NOT EXISTS ix_portal_links_user ON portal_links (username, status);
CREATE INDEX IF NOT EXISTS ix_portal_links_pupil ON portal_links (pupil_id, kind);
CREATE INDEX IF NOT EXISTS ix_portal_links_contact ON portal_links (contact_id);

-- Parent logins this system made (or took over by e-mail), for the
-- User Accounts screen and the welcome e-mail.
CREATE TABLE IF NOT EXISTS parent_accounts (
    username           TEXT PRIMARY KEY COLLATE NOCASE,
    user_id            INTEGER,
    email              TEXT NOT NULL COLLATE NOCASE,
    display_name       TEXT,
    created_new        INTEGER NOT NULL DEFAULT 0,
    welcome_message_id INTEGER,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by         TEXT
);
"""

database.register_schema("portal_accounts", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class Link:
    link_id: int
    username: str
    user_id: int | None
    pupil_id: int
    kind: str
    source: str
    contact_id: int | None
    granted_role: bool
    status: str
    created_at: str
    created_by: str | None
    removed_at: str | None
    removed_by: str | None
    pupil_name: str = ""
    admission_no: str = ""

    @property
    def active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class SyncResult:
    """What one contact sync did. *password* is only set for a new login (shown
    once, never stored); *message_id* is the queued e-mail to deliver."""

    action: str               # created / linked / moved / removed / unchanged / skipped
    username: str | None = None
    password: str | None = None
    message_id: int | None = None
    note: str = ""


_LINK_SELECT = ("SELECT l.*, p.legal_first_name, p.legal_last_name, p.preferred_name, "
                "p.admission_no FROM portal_links l JOIN pupils p USING (pupil_id)")


def _link(r) -> Link:
    keys = r.keys()
    name = " ".join(x for x in ((r["preferred_name"] or r["legal_first_name"]),
                                r["legal_last_name"]) if x) if "legal_last_name" in keys else ""
    return Link(r["link_id"], r["username"], r["user_id"], r["pupil_id"], r["kind"],
                r["source"], r["contact_id"], bool(r["granted_role"]), r["status"],
                r["created_at"], r["created_by"], r["removed_at"], r["removed_by"],
                name, r["admission_no"] if "admission_no" in keys else "")


def _require_admin(actor: Principal, action: str, target: Any = None) -> None:
    if not actor.is_admin:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only a system administrator can change portal logins.")


# ── Who sees which pupil ─────────────────────────────────────────────

def _pupil_logins(username: str) -> list[int]:
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts  # noqa: F401 - schema
    with database.connect() as conn:
        own = [r[0] for r in conn.execute(
            "SELECT pupil_id FROM pupil_accounts WHERE username = ? COLLATE NOCASE AND "
            "status = 'active'", (username,))]
        linked = [r[0] for r in conn.execute(
            "SELECT pupil_id FROM portal_links WHERE username = ? AND kind = 'pupil' AND "
            "status = 'active'", (username,))]
    return list(dict.fromkeys(own + linked))


def _parent_links(username: str) -> list[int]:
    with database.connect() as conn:
        return list(dict.fromkeys(r[0] for r in conn.execute(
            "SELECT pupil_id FROM portal_links WHERE username = ? AND kind = 'parent' AND "
            "status = 'active' ORDER BY link_id", (username,))))


def pupils_for(principal: Principal, kind: str | None = None) -> list[P.Pupil]:
    """The on-roll pupils this login may see: its own record for a pupil login,
    its children for a parent (or a member of staff who is also a parent)."""
    if not principal.username:
        return []
    kind = kind or ("pupil" if principal.is_student else "parent")
    ids = _pupil_logins(principal.username) if kind == "pupil" else \
        _parent_links(principal.username)
    out = []
    for pid in ids:
        p = P.get_pupil(pid)
        if p is not None and p.roll_status == "on_roll":
            out.append(p)
    return sorted(out, key=lambda p: (-p.year_group, p.display_name.lower()))


def require_pupil(principal: Principal, pupil_id: int, kind: str | None = None) -> P.Pupil:
    """The pupil, if *principal* may see them in a portal; else PermissionDenied."""
    for p in pupils_for(principal, kind):
        if p.pupil_id == int(pupil_id):
            return p
    activity_log.record("portal.view", target=f"pupil:{pupil_id}", outcome="denied",
                        principal=principal)
    raise PermissionDenied("You can only see your own record.")


def has_children(principal: Principal) -> bool:
    return bool(principal.username) and bool(_parent_links(principal.username))


# ── Parent logins from contacts ──────────────────────────────────────

def _password() -> str:
    """Three groups, e.g. ``Kfpq-7342-Tzwm`` (upper, lower, digits)."""
    def letters() -> str:
        return (secrets.choice(string.ascii_uppercase)
                + "".join(secrets.choice(string.ascii_lowercase) for _ in range(3)))
    return f"{letters()}-{''.join(secrets.choice(string.digits) for _ in range(4))}-{letters()}"


def _username_for(full_name: str) -> str:
    """``firstname.lastname`` from the contact's name (``sarah.khan``, then
    ``sarah.khan2``...). Not the e-mail address: usernames appear in the
    activity log, which carries no contact details."""
    from education_system.systems.secondary.modules.pupils.domain.pupil_accounts import (
        _ascii_letters,
        _first_free,
    )
    words = [_ascii_letters(w) for w in (full_name or "").split()]
    words = [w for w in words if w]
    base = ".".join((words[0], words[-1])) if len(words) > 1 else (words[0] if words
                                                                  else "parent")
    return _first_free(base, accounts.usernames_like(base), lambda b, n: b + n)


def _wants_link(c: C.Contact | None, pupil: P.Pupil | None) -> bool:
    return bool(c and pupil and c.parental_responsibility and c.email
                and C.valid_email(c.email) and pupil.roll_status == "on_roll")


def _remove_links(conn, rows, actor: Principal) -> list[tuple[str, int]]:
    out = []
    for r in rows:
        conn.execute("UPDATE portal_links SET status = 'removed', removed_at = datetime('now'), "
                     "removed_by = ? WHERE link_id = ?", (actor.username, r["link_id"]))
        out.append((r["username"], r["pupil_id"]))
    return out


def _tidy_roles(usernames: set[str], actor: Principal) -> None:
    """Take the parent role off logins with no children left - only where this
    system gave them the role."""
    for username in usernames:
        with database.connect() as conn:
            left = conn.execute("SELECT count(*) FROM portal_links WHERE username = ? AND "
                                "kind = 'parent' AND status = 'active'", (username,)).fetchone()[0]
            granted = conn.execute("SELECT count(*) FROM portal_links WHERE username = ? AND "
                                   "kind = 'parent' AND granted_role = 1",
                                   (username,)).fetchone()[0]
        if left or not granted:
            continue
        login = accounts.find_login(username)
        if login and login["role"] == accounts.PARENT_ROLE:
            try:
                accounts.revoke_role(login["username"], login["email"], accounts.PARENT_ROLE)
                activity_log.record("portal.role.revoke", target=f"user:{login['id']}",
                                    principal=actor)
            except Exception:  # noqa: BLE001
                logger.exception("Revoking parent role failed")


def _queue(template: str, values: dict[str, Any], email: str, name: str, actor: Principal,
           pupil: P.Pupil, kind: str) -> int | None:
    try:
        subject, body = email_templates.load_template(template).render(values)
        return E.send_to_address(email, name, subject, body, actor=actor, kind=kind,
                                 label=f"Parent portal e-mail for {pupil.admission_no}",
                                 pupil=pupil)
    except Exception as e:  # noqa: BLE001 - the login stands; report the e-mail problem
        logger.exception("Parent portal e-mail failed")
        activity_log.record("portal.parent.email", target=pupil.admission_no, outcome="error",
                            principal=actor, error=type(e).__name__)
        return None


def _link_parent(c: C.Contact, pupil: P.Pupil, actor: Principal, *, moved: bool
                 ) -> SyncResult:
    email = (c.email or "").strip().lower()
    login = accounts.find_login_by_email(email)
    password = None
    granted = False
    if login is None:
        username = _username_for(c.full_name)
        password = _password()
        user_id = accounts.create_parent_login(username, password, display_name=c.full_name,
                                               email=email)
        login = {"id": user_id, "username": username, "email": email, "role": "parent",
                 "display_name": c.full_name}
        granted = True
    elif login["role"] is None:
        if not accounts.grant_role(login["username"], login["email"], accounts.PARENT_ROLE):
            return SyncResult("skipped", login["username"],
                              note="the existing login with that address didn't match")
        granted = True
    elif login["role"] not in (accounts.PARENT_ROLE, *_STAFF):
        return SyncResult("skipped", login["username"],
                          note=f"that address belongs to a {login['role']} login")
    with database.connect() as conn:
        dup = conn.execute("SELECT link_id FROM portal_links WHERE username = ? AND pupil_id = ? "
                           "AND kind = 'parent' AND status = 'active'",
                           (login["username"], pupil.pupil_id)).fetchone()
        if dup:
            conn.execute("UPDATE portal_links SET contact_id = ? WHERE link_id = ?",
                         (c.contact_id, dup[0]))
        else:
            conn.execute(
                "INSERT INTO portal_links (username, user_id, pupil_id, kind, source, contact_id, "
                "granted_role, created_by) VALUES (?, ?, ?, 'parent', 'contact', ?, ?, ?)",
                (login["username"], login["id"], pupil.pupil_id, c.contact_id, int(granted),
                 actor.username))
        conn.execute(
            "INSERT INTO parent_accounts (username, user_id, email, display_name, created_new, "
            "created_by) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(username) DO NOTHING",
            (login["username"], login["id"], email, c.full_name, int(password is not None),
             actor.username))
    if dup:
        return SyncResult("unchanged", login["username"])
    values = {"parent_name": c.full_name, "pupil_first_name": pupil.preferred_name
              or pupil.legal_first_name, "pupil_name": pupil.display_name,
              "username": login["username"], "password": password or ""}
    if password:
        mid = _queue(WELCOME_TEMPLATE, values, email, c.full_name, actor, pupil,
                     "parent_welcome")
        with database.connect() as conn:
            conn.execute("UPDATE parent_accounts SET welcome_message_id = ? WHERE username = ?",
                         (mid, login["username"]))
    else:
        mid = _queue(LINKED_TEMPLATE, values, email, c.full_name, actor, pupil, "parent_linked")
    activity_log.record("portal.parent.link", target=pupil.admission_no, principal=actor,
                        user_id=login["id"], new_login=password is not None)
    return SyncResult("moved" if moved else ("created" if password else "linked"),
                      login["username"], password, mid)


def sync_contact(contact_id: int, *, actor: Principal, pupil_id: int | None = None
                 ) -> SyncResult:
    """Bring the parent login and link for one contact up to date (after it is
    added, changed or deleted - pass *pupil_id* for a deleted contact)."""
    c = C.get_contact(contact_id)
    pupil = P.get_pupil(c.pupil_id if c else int(pupil_id or 0))
    want = _wants_link(c, pupil)
    email = (c.email or "").strip().lower() if c else ""
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM portal_links WHERE contact_id = ? AND kind = 'parent' "
                            "AND status = 'active'", (contact_id,)).fetchall()
    keep = {r["link_id"] for r in rows if want and (
        (accounts.find_login(r["username"]) or {}).get("email") or "").lower() == email}
    current = [r for r in rows if r["link_id"] in keep]
    with database.connect() as conn:
        removed = _remove_links(conn, [r for r in rows if r["link_id"] not in keep], actor)
    if removed:
        activity_log.record("portal.parent.unlink", target=pupil.admission_no if pupil else
                            f"contact:{contact_id}", principal=actor, links=len(removed))
    _tidy_roles({u for u, _p in removed}, actor)
    if not want:
        return SyncResult("removed" if removed else "skipped")
    if current:
        return SyncResult("unchanged", current[0]["username"])
    try:
        return _link_parent(c, pupil, actor, moved=bool(removed))  # type: ignore[arg-type]
    except Exception as e:  # noqa: BLE001
        logger.exception("Parent login for contact %s failed", contact_id)
        activity_log.record("portal.parent.link", target=pupil.admission_no, outcome="error",
                            principal=actor, error=type(e).__name__)
        return SyncResult("skipped", note=f"couldn't make the login: {e}")


def sync_all(*, actor: Principal) -> dict[str, int]:
    """Make parent logins for every contact who should have one (and remove
    links that no longer apply). Returns counts by action."""
    _require_admin(actor, "portal.parent.sync_all")
    with database.connect() as conn:
        ids = [r[0] for r in conn.execute("SELECT contact_id FROM pupil_contacts ORDER BY "
                                          "contact_id")]
        orphans = conn.execute(
            "SELECT * FROM portal_links WHERE kind = 'parent' AND source = 'contact' AND "
            "status = 'active' AND (contact_id IS NULL OR pupil_id IN (SELECT pupil_id FROM "
            "pupils WHERE roll_status != 'on_roll'))").fetchall()
        gone = _remove_links(conn, orphans, actor)
    _tidy_roles({u for u, _p in gone}, actor)
    counts: dict[str, int] = {"removed": len(gone)}
    for cid in ids:
        r = sync_contact(cid, actor=actor)
        counts[r.action] = counts.get(r.action, 0) + 1
    activity_log.record("portal.parent.sync_all", principal=actor, **counts)
    return counts


def contact_removed(contact_id: int, *, actor: Principal) -> None:
    """Called by :mod:`contacts` just *before* a contact is deleted: remove its
    parent links (and the parent role if that was their last child). Never
    raises."""
    try:
        with database.connect() as conn:
            rows = conn.execute("SELECT * FROM portal_links WHERE contact_id = ? AND "
                                "kind = 'parent' AND status = 'active'",
                                (int(contact_id),)).fetchall()
            removed = _remove_links(conn, rows, actor)
        if removed:
            activity_log.record("portal.parent.unlink", target=f"contact:{contact_id}",
                                principal=actor, links=len(removed))
        _tidy_roles({u for u, _p in removed}, actor)
    except Exception:  # noqa: BLE001
        logger.exception("Removing parent links for contact %s failed", contact_id)


def contact_hook(contact_id: int, *, actor: Principal, pupil_id: int | None = None) -> None:
    """Called by :mod:`contacts` after every add / change / delete. Never raises."""
    try:
        sync_contact(contact_id, actor=actor, pupil_id=pupil_id)
    except Exception:  # noqa: BLE001
        logger.exception("Parent portal sync failed for contact %s", contact_id)


def undelivered(*, pupil_id: int | None = None) -> list[int]:
    """Parent portal e-mails still waiting in the outbox (to deliver now)."""
    sql = ("SELECT DISTINCT m.message_id FROM email_messages m JOIN email_recipients r USING "
           "(message_id) WHERE r.status = 'queued' AND m.audience_kind IN ('parent_welcome', "
           "'parent_linked')")
    params: list[Any] = []
    if pupil_id is not None:
        sql += " AND r.pupil_id = ?"
        params.append(int(pupil_id))
    try:
        with database.connect() as conn:
            return [r[0] for r in conn.execute(sql + " ORDER BY m.message_id", params)]
    except Exception:  # noqa: BLE001 - outbox columns differ: nothing to deliver
        logger.exception("Reading undelivered parent e-mails failed")
        return []


# ── Linking by hand ──────────────────────────────────────────────────

def links_for_pupil(pupil_id: int, *, include_removed: bool = False) -> list[Link]:
    sql = _LINK_SELECT + " WHERE l.pupil_id = ?" + ("" if include_removed else
                                                    " AND l.status = 'active'")
    with database.connect() as conn:
        return [_link(r) for r in conn.execute(sql + " ORDER BY l.kind, l.link_id",
                                               (int(pupil_id),))]


def list_links(*, kind: str | None = None, search: str | None = None,
               include_removed: bool = False) -> list[Link]:
    sql, params = _LINK_SELECT + " WHERE 1 = 1", []
    if not include_removed:
        sql += " AND l.status = 'active'"
    if kind:
        sql += " AND l.kind = ?"
        params.append(kind)
    if search and search.strip():
        sql += (" AND (lower(l.username) LIKE ? OR lower(p.legal_last_name) LIKE ? OR "
                "lower(p.legal_first_name) LIKE ? OR lower(p.admission_no) LIKE ?)")
        params += [f"%{search.strip().lower()}%"] * 4
    with database.connect() as conn:
        return [_link(r) for r in conn.execute(sql + " ORDER BY l.username, l.link_id", params)]


def parent_logins() -> list[dict[str, Any]]:
    """Parent logins this system made or linked, with their children."""
    with database.connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM parent_accounts ORDER BY "
                                              "lower(display_name), username")]
    links = list_links(kind="parent")
    for r in rows:
        r["children"] = [x for x in links if x.username.lower() == r["username"].lower()]
    return rows


def link_login(username: str, pupil_id: int, kind: str, *, actor: Principal) -> Link:
    """Link an existing login to a pupil as that pupil or as their parent. A
    login with no secondary role is given the matching one; a login with a
    different role is refused (a staff login can be linked as a parent)."""
    pupil = P.get_pupil(int(pupil_id))
    target = pupil.admission_no if pupil else f"pupil:{pupil_id}"
    _require_admin(actor, "portal.link", target)
    problems = []
    if pupil is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    if kind not in KINDS:
        problems.append("Link as the pupil or as a parent")
    login = accounts.find_login(username or "")
    if login is None:
        problems.append(f"No login called '{(username or '').strip()}'")
    if problems:
        raise ValidationError(problems)
    assert login is not None
    role = ROLE_FOR[kind]
    if login["role"] not in (None, role) and not (kind == "parent" and login["role"] in _STAFF):
        raise ValidationError([f"{login['username']} is a secondary {login['role']} login - it "
                               f"can't be linked as a {'pupil' if kind == 'pupil' else 'parent'}"])
    if kind == "pupil":
        from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
        own = pupil_accounts.get_for_pupil(pupil.pupil_id)
        others = [x for x in links_for_pupil(pupil.pupil_id) if x.kind == "pupil"]
        if (own and own.status == "active" and own.username.lower() != login["username"].lower()) \
                or others:
            raise ValidationError([f"{pupil.display_name} already has a pupil login"])
        if [p for p in _pupil_logins(login["username"]) if p != pupil.pupil_id]:
            raise ValidationError([f"{login['username']} is already linked to another pupil"])
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM portal_links WHERE username = ? AND pupil_id = ? AND "
                        "kind = ? AND status = 'active'",
                        (login["username"], pupil.pupil_id, kind)).fetchone():
            raise ValidationError([f"{login['username']} is already linked to "
                                   f"{pupil.display_name}"])
    granted = False
    if login["role"] is None:
        if not accounts.grant_role(login["username"], login["email"], role):
            raise ValidationError(["That login couldn't be given access - check its e-mail"])
        granted = True
    with database.connect() as conn:
        cur = conn.execute(
            "INSERT INTO portal_links (username, user_id, pupil_id, kind, source, granted_role, "
            "created_by) VALUES (?, ?, ?, ?, 'manual', ?, ?)",
            (login["username"], login["id"], pupil.pupil_id, kind, int(granted),
             actor.username))
        link_id = cur.lastrowid
    activity_log.record("portal.link", target=pupil.admission_no, principal=actor, kind=kind,
                        user_id=login["id"], granted=granted)
    return get_link(link_id)


def get_link(link_id: int) -> Link:
    with database.connect() as conn:
        r = conn.execute(_LINK_SELECT + " WHERE l.link_id = ?", (int(link_id),)).fetchone()
    if r is None:
        raise NotFound(f"No portal link {link_id}")
    return _link(r)


def unlink(link_id: int, *, actor: Principal) -> Link:
    """Remove a link. A link made from a contact comes back on the next sync
    unless the contact changes, so staff are told to change the contact."""
    link = get_link(link_id)
    _require_admin(actor, "portal.unlink", link.admission_no)
    if not link.active:
        raise ValidationError(["That link has already been removed"])
    if link.source == "contact" and link.contact_id and C.get_contact(link.contact_id):
        raise ValidationError(["This link comes from the pupil's contacts - remove the "
                               "contact's e-mail or parental responsibility instead"])
    with database.connect() as conn:
        conn.execute("UPDATE portal_links SET status = 'removed', removed_at = datetime('now'), "
                     "removed_by = ? WHERE link_id = ?", (actor.username, link.link_id))
    if link.kind == "parent":
        _tidy_roles({link.username}, actor)
    elif link.granted_role and not _pupil_logins(link.username):
        login = accounts.find_login(link.username)
        if login and login["role"] == accounts.PUPIL_ROLE:
            accounts.revoke_role(login["username"], login["email"], accounts.PUPIL_ROLE)
    activity_log.record("portal.unlink", target=link.admission_no, principal=actor,
                        kind=link.kind)
    return get_link(link.link_id)

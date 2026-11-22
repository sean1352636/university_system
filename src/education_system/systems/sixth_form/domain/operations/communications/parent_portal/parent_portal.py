"""Parent / guardian portal for the Sixth Form System.

This is the data + auth layer behind a parent-facing self-service view.
The system already records parent *contact details* (``parent_contacts``)
but has no way for a parent to log in and see their child's record. This
module adds:

* **Parent accounts** — username + salted PBKDF2 password hash, stored
  in the shared ``sixthform.db``. Each account is also mirrored into the
  platform auth DB as a ``sixth_form``/``parent`` user (see
  :mod:`.shared_auth_mirror`) so the same credentials work at the
  universal login screen, not just against the REST API below.
* **Student links** — which students an account may view. A parent can
  be linked to more than one child; a child can have more than one
  linked guardian.
* **Read-only snapshots** — a safe, aggregated view of each linked
  child built from the modules a parent should see: attendance, risk
  band, predicted grades, recent behaviour and UCAS progress. No raw
  safeguarding / medical data is ever exposed here.

The staff CLI/GUI manage accounts and links; the REST API
(:mod:`sixthform_system.api`) serves the snapshots to authenticated
parents.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    shared_auth_mirror as _mirror,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_PARENT_PORTAL_DB

_PBKDF2_ROUNDS = 200_000

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(value: str | None) -> str | None:
    """Normalise an address, or raise if it is obviously not one.

    An empty value is a legitimate "no address on file", so it comes back
    as ``None`` rather than an error. A typo, though, is worth catching
    here: the address is mirrored into shared auth and used for welcome
    mail, so a bad one fails somewhere far away from where it was typed.
    """
    value = (value or "").strip()
    if not value:
        return None
    if not _EMAIL_RE.match(value):
        raise ValidationError(f"'{value}' is not a valid email address")
    return value


@dataclass
class ParentAccount:
    account_id: int
    username: str
    full_name: str
    email: str | None
    is_active: bool
    created_at: str
    last_login: str | None


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_accounts (
    account_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    email         TEXT,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now')),
    last_login    TEXT
);

CREATE TABLE IF NOT EXISTS parent_student_links (
    account_id   INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    relationship TEXT NOT NULL DEFAULT 'Parent',
    contact_id   INTEGER,
    created_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (account_id, student_id),
    FOREIGN KEY (account_id) REFERENCES parent_accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)        ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES parent_contacts(contact_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pslink_student ON parent_student_links(student_id);
"""

# Created only after _add_contact_column() has guaranteed the column exists;
# see init_db(). Keeping it in _SCHEMA breaks pre-contact_id databases.
_CONTACT_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_pslink_contact "
    "ON parent_student_links(contact_id)"
)

_DB_READY = False


def contacts_module():
    """The parent/guardian *contacts* module this portal links against.

    Imported lazily: the two modules share ``sixthform.db`` but neither
    owns the other, and a module-level import would make the dependency
    circular the first time contacts wants to know about accounts.
    """
    from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
        parent_contacts,
    )
    return parent_contacts


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    # parent_student_links.contact_id points at parent_contacts, so that
    # table has to exist before this schema is applied.
    contacts_module().init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _add_contact_column(conn)
        conn.execute(_CONTACT_INDEX)
    _DB_READY = True
    logger.debug("Parent-portal schema ready at %s", DB_PATH)


def _add_contact_column(conn: sqlite3.Connection) -> None:
    """Backfill ``contact_id`` onto a link table that predates it.

    ``CREATE TABLE IF NOT EXISTS`` leaves an existing table alone, so
    databases created before contacts and accounts were linked need the
    column adding by hand. Added without the foreign key: SQLite cannot
    attach one to an existing table, and the constraint is enforced in
    :func:`set_link_contact` anyway.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(parent_student_links)")}
    if "contact_id" not in cols:
        conn.execute("ALTER TABLE parent_student_links ADD COLUMN contact_id INTEGER")
        conn.commit()
        logger.info("Added parent_student_links.contact_id to %s", DB_PATH)


class ValidationError(ValueError):
    """Raised for invalid portal input."""


def _mirror_safely(what: str, username: str, action) -> None:
    """Run a shared-auth mirror write without letting it undo portal work.

    The portal row is already committed by the time these run, so raising
    here would report failure for a change that did happen. The mismatch
    is logged instead, and a later password reset re-syncs the account.
    """
    try:
        action()
    except Exception:
        logger.exception(
            "Parent account '%s': %s did not reach the shared auth database. "
            "The universal login may be out of step until the account's "
            "password is reset.", username, what,
        )


# ── Password hashing (stdlib PBKDF2) ─────────────────────────────────

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return dk.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    candidate, _ = _hash_password(password, salt)
    return secrets.compare_digest(candidate, stored_hash)


# ── Account management ───────────────────────────────────────────────

def _row_to_account(r: sqlite3.Row) -> ParentAccount:
    return ParentAccount(
        account_id=r["account_id"], username=r["username"], full_name=r["full_name"],
        email=r["email"], is_active=bool(r["is_active"]),
        created_at=r["created_at"], last_login=r["last_login"])


def create_account(*, username: str, password: str, full_name: str,
                   email: str = "") -> int:
    init_db()
    username = (username or "").strip().lower()
    if not username:
        raise ValidationError("Username is required")
    if len(password or "") < 8:
        raise ValidationError("Password must be at least 8 characters")
    if not (full_name or "").strip():
        raise ValidationError("Full name is required")
    clean_email = _clean_email(email)
    pw_hash, salt = _hash_password(password)
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM parent_accounts WHERE username=?", (username,)).fetchone():
            raise ValidationError(f"Username '{username}' already exists")

        # Claim the username in shared auth *before* writing the portal row.
        # A portal account the parent cannot sign in with is worse than no
        # account at all, so a name clash fails the whole creation.
        available, reason = _mirror.username_available(username)
        if not available:
            raise ValidationError(reason)

        cur = conn.execute(
            "INSERT INTO parent_accounts (username, full_name, email, password_hash, password_salt) "
            "VALUES (?,?,?,?,?)",
            (username, full_name.strip(), clean_email, pw_hash, salt))
        conn.commit()
        account_id = cur.lastrowid

    _mirror.upsert(username, password, full_name.strip(), clean_email)
    logger.info("Created parent account %s", username)
    _send_welcome_email(account_id, username, password, full_name.strip(),
                        clean_email)
    return account_id


def _send_welcome_email(account_id: int, username: str, password: str,
                        full_name: str, email: str | None,
                        *, strict: bool = False) -> None:
    """Send the ``welcome_parent`` template to a parent account.

    Swallows failures by default: on the automatic send at account
    creation the account and its shared-auth mirror already exist, and
    failing the whole creation because the mail log was unavailable would
    leave staff re-typing a form for no reason. ``strict=True`` re-raises
    instead, for the staff-triggered send where somebody is waiting on
    the result.
    """
    if not email:
        logger.info(
            "Parent account '%s' has no email address — welcome email skipped",
            username)
        return

    from education_system.systems.sixth_form import SYSTEM_NAME
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        email_templates,
    )
    children = linked_students(account_id)
    context = {
        "system_name": SYSTEM_NAME,
        "full_name": full_name,
        "username": username,
        "password": password,
        # Accounts are usually linked to a child after they are created,
        # so this is normally the generic phrasing rather than a name.
        "children": (", ".join(c["full_name"] for c in children)
                     if children else "your child's progress"),
    }
    try:
        email_templates.send_from_template(
            "welcome_parent", context,
            to_name=full_name, to_address=email)
    except Exception:
        logger.exception(
            "Welcome email for parent account '%s' could not be sent", username)
        if strict:
            raise


def update_account(account_id: int, *, full_name: str | None = None,
                   email: str | None = None) -> ParentAccount:
    """Edit a portal account's name and/or email address.

    Only the fields passed are changed, so ``email=""`` clears the address
    while omitting it leaves whatever is there. The username is *not*
    editable — it is the key the shared-auth mirror is matched on, and
    renaming it would strand the login.

    Once the account is linked to a contact record the email address
    belongs to that record, and passing one here is refused rather than
    quietly ignored: two editable copies of the same address is the
    duplication the link exists to remove. Edit the contact instead.
    """
    init_db()
    account = get_account(account_id)
    if account is None:
        raise ValidationError(f"Unknown account: {account_id}")

    new_name = account.full_name if full_name is None else full_name.strip()
    if not new_name:
        raise ValidationError("Full name is required")
    if email is not None and has_contact_link(account_id):
        raise ValidationError(
            "This account's email address is held on its linked contact "
            "record — edit it in Parent Contacts.")
    new_email = account.email if email is None else _clean_email(email)

    with _connect() as conn:
        conn.execute(
            "UPDATE parent_accounts SET full_name=?, email=? WHERE account_id=?",
            (new_name, new_email, account_id))
        conn.commit()

    _mirror_safely("details update", account.username,
                   lambda: _mirror.set_details(account.username, new_name,
                                               resolved_email(account_id)))
    logger.info("Updated parent account %s", account.username)
    return get_account(account_id)


def send_welcome_email(account_id: int, password: str) -> None:
    """Send (or re-send) the welcome email for an existing account.

    Takes the plaintext *password* because the stored hash cannot be
    reversed and a welcome email quoting credentials that do not work is
    worse than none. Callers pair this with :func:`set_password` so what
    is emailed is what the parent can actually sign in with.
    """
    init_db()
    account = get_account(account_id)
    if account is None:
        raise ValidationError(f"Unknown account: {account_id}")
    address = resolved_email(account_id)
    if not address:
        raise ValidationError(
            "This account has no email address — add one before sending.")
    # Staff pressed a button and are waiting for an answer, so a failure
    # here is reported rather than swallowed the way the automatic send
    # on account creation is.
    _send_welcome_email(account_id, account.username, password,
                        account.full_name, address, strict=True)


def set_password(account_id: int, new_password: str) -> None:
    init_db()
    if len(new_password or "") < 8:
        raise ValidationError("Password must be at least 8 characters")
    pw_hash, salt = _hash_password(new_password)
    with _connect() as conn:
        row = conn.execute(
            "SELECT username, full_name, email, is_active FROM parent_accounts "
            "WHERE account_id=?", (account_id,)).fetchone()
        conn.execute(
            "UPDATE parent_accounts SET password_hash=?, password_salt=? WHERE account_id=?",
            (pw_hash, salt, account_id))
        conn.commit()

    if row is None:
        return
    # A reset is the one moment a pre-existing portal account (created
    # before mirroring existed, so with no recoverable plaintext) can be
    # backfilled into shared auth — hence upsert rather than set_password.
    _mirror_safely(
        "password reset", row["username"],
        lambda: _mirror.upsert(
            row["username"], new_password, row["full_name"],
            resolved_email(account_id), is_active=bool(row["is_active"])),
    )


def set_active(account_id: int, active: bool) -> None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT username FROM parent_accounts WHERE account_id=?",
            (account_id,)).fetchone()
        conn.execute("UPDATE parent_accounts SET is_active=? WHERE account_id=?",
                     (1 if active else 0, account_id))
        conn.commit()

    if row is not None:
        _mirror_safely("enable/disable", row["username"],
                       lambda: _mirror.set_active(row["username"], active))


def delete_account(account_id: int) -> None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT username FROM parent_accounts WHERE account_id=?",
            (account_id,)).fetchone()
        conn.execute("DELETE FROM parent_accounts WHERE account_id=?", (account_id,))
        conn.commit()

    if row is not None:
        _mirror_safely("deletion", row["username"],
                       lambda: _mirror.remove(row["username"]))


def list_accounts() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM parent_accounts ORDER BY username").fetchall()
        # Contact-owned addresses for every account in one pass rather
        # than a contact_email() call (and a fresh connection) per row.
        # Same precedence as contact_email(): primary contact, then oldest.
        owned = {}
        for cr in conn.execute(
                """
                SELECT l.account_id, c.email
                  FROM parent_student_links l
                  JOIN parent_contacts c ON c.contact_id = l.contact_id
                 WHERE c.email IS NOT NULL AND TRIM(c.email) <> ''
                 ORDER BY l.account_id, c.is_primary DESC, c.contact_id
                """):
            owned.setdefault(cr["account_id"], cr["email"])
        out = []
        for r in rows:
            links = conn.execute(
                "SELECT COUNT(*) AS n FROM parent_student_links WHERE account_id=?",
                (r["account_id"],)).fetchone()["n"]
            d = _row_to_account(r).__dict__
            d["linked_students"] = links
            # ``email`` stays the stored column; the UI shows and edits
            # the resolved one so a linked account displays the address
            # staff actually maintain, over in Parent Contacts.
            d["contact_email"] = owned.get(r["account_id"])
            d["email_from_contact"] = d["contact_email"] is not None
            d["resolved_email"] = d["contact_email"] or d["email"]
            # Whether this account also exists in the shared auth DB, i.e.
            # whether the parent can actually sign in at the login screen.
            # Accounts predating the mirror show False until reset.
            d["login_enabled"] = _mirror.has_mirror(r["username"])
            out.append(d)
    return out


def authenticate(username: str, password: str) -> ParentAccount | None:
    """Return the account on success, recording last_login; else None."""
    init_db()
    username = (username or "").strip().lower()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM parent_accounts WHERE username=? AND is_active=1", (username,)).fetchone()
        if not r:
            logger.info("Failed parent login for %s", username)
            return None

        if _verify_password(password or "", r["password_hash"], r["password_salt"]):
            resync = False
        elif _mirror.verify_shared_password(username, password or ""):
            # The parent changed their password at the universal login
            # screen, which only writes to the shared auth DB. Accept it
            # and bring the portal's own hash back in step.
            resync = True
            logger.info(
                "Parent '%s' authenticated against shared auth; re-syncing "
                "the portal password hash", username,
            )
        else:
            logger.info("Failed parent login for %s", username)
            return None

        if resync:
            new_hash, new_salt = _hash_password(password)
            conn.execute(
                "UPDATE parent_accounts SET password_hash=?, password_salt=? "
                "WHERE account_id=?", (new_hash, new_salt, r["account_id"]))

        conn.execute("UPDATE parent_accounts SET last_login=? WHERE account_id=?",
                     (_dt.datetime.now().isoformat(timespec="seconds"), r["account_id"]))
        conn.commit()
        return _row_to_account(r)


# ── Student links ────────────────────────────────────────────────────

def link_student(account_id: int, student_id: str, *, relationship: str = "Parent",
                 contact_id: int | None = None) -> None:
    """Link a child to an account, optionally naming the contact record.

    *contact_id* identifies which of the student's ``parent_contacts``
    rows is this account holder. Supplying it makes the contact the
    account's source of truth for the email address — see
    :func:`resolved_email`.
    """
    init_db()
    with _connect() as conn:
        if not conn.execute("SELECT 1 FROM students WHERE student_id=?", (student_id,)).fetchone():
            raise ValidationError(f"Unknown student: {student_id}")
        if not conn.execute("SELECT 1 FROM parent_accounts WHERE account_id=?", (account_id,)).fetchone():
            raise ValidationError(f"Unknown account: {account_id}")
        if contact_id is not None:
            _check_contact(conn, student_id, contact_id)
        conn.execute(
            "INSERT OR REPLACE INTO parent_student_links "
            "(account_id, student_id, relationship, contact_id) VALUES (?,?,?,?)",
            (account_id, student_id, relationship or "Parent", contact_id))
        conn.commit()

    if contact_id is not None:
        _sync_mirror_email(account_id)


def unlink_student(account_id: int, student_id: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM parent_student_links WHERE account_id=? AND student_id=?",
            (account_id, student_id))
        conn.commit()
    # Dropping the child may have dropped the contact that owned the
    # address, so the login copy needs re-pointing at whatever is left.
    _sync_mirror_email(account_id)


# ── Contact records ──────────────────────────────────────────────────

def _check_contact(conn: sqlite3.Connection, student_id: str, contact_id: int) -> None:
    """Reject a contact that is not one of *student_id*'s guardians."""
    row = conn.execute(
        "SELECT student_id FROM parent_contacts WHERE contact_id=?",
        (contact_id,)).fetchone()
    if row is None:
        raise ValidationError(f"Unknown contact: {contact_id}")
    if row["student_id"] != student_id:
        raise ValidationError(
            f"Contact {contact_id} belongs to a different student "
            f"({row['student_id']}), not {student_id}")


def set_link_contact(account_id: int, student_id: str,
                     contact_id: int | None) -> None:
    """Point one account/child link at a contact record, or clear it.

    Clearing hands the email address back to ``parent_accounts.email``,
    which is why the mirror is re-synced either way.
    """
    init_db()
    with _connect() as conn:
        if not conn.execute(
                "SELECT 1 FROM parent_student_links WHERE account_id=? AND student_id=?",
                (account_id, student_id)).fetchone():
            raise ValidationError(
                f"Account {account_id} is not linked to student {student_id}")
        if contact_id is not None:
            _check_contact(conn, student_id, contact_id)
        conn.execute(
            "UPDATE parent_student_links SET contact_id=? "
            "WHERE account_id=? AND student_id=?",
            (contact_id, account_id, student_id))
        conn.commit()
    _sync_mirror_email(account_id)
    logger.info("Account %s / student %s now points at contact %s",
                account_id, student_id, contact_id)


def suggest_contacts(account_id: int, student_id: str) -> list[dict[str, Any]]:
    """This student's contacts, likeliest match to this account first.

    A match is only ever a suggestion — two guardians often share one
    household address, so the choice stays with whoever is doing the
    linking. ``match`` says why a row was promoted, for display next to
    it.
    """
    init_db()
    account = get_account(account_id)
    acc_email = (account.email or "").strip().lower() if account else ""
    acc_name = (account.full_name or "").strip().lower() if account else ""

    out = []
    for c in contacts_module().contacts_for_student(student_id):
        email = (c.email or "").strip().lower()
        name = f"{c.first_name} {c.last_name}".strip().lower()
        if acc_email and email == acc_email:
            rank, match = 0, "same email address"
        elif acc_name and name == acc_name:
            rank, match = 1, "same name"
        elif acc_name and (c.last_name or "").strip().lower() in acc_name.split():
            rank, match = 2, "same surname"
        else:
            rank, match = 3, ""
        out.append({"contact_id": c.contact_id, "full_name": c.full_name,
                    "relationship": c.relationship, "email": c.email,
                    "is_primary": c.is_primary, "match": match, "_rank": rank})
    out.sort(key=lambda d: (d["_rank"], not d["is_primary"], d["contact_id"]))
    for d in out:
        del d["_rank"]
    return out


def contact_email(account_id: int) -> str | None:
    """The address held by this account's linked contact record(s).

    ``None`` when no linked contact carries one. A parent with two
    children has two contact rows; the primary contact wins, then the
    oldest, so the answer does not wander between calls.
    """
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT c.email
              FROM parent_student_links l
              JOIN parent_contacts c ON c.contact_id = l.contact_id
             WHERE l.account_id = ?
               AND c.email IS NOT NULL AND TRIM(c.email) <> ''
             ORDER BY c.is_primary DESC, c.contact_id
             LIMIT 1
            """, (account_id,)).fetchone()
    return row["email"] if row else None


def has_contact_link(account_id: int) -> bool:
    """True when any of this account's children names a contact record."""
    init_db()
    with _connect() as conn:
        return conn.execute(
            "SELECT 1 FROM parent_student_links "
            "WHERE account_id=? AND contact_id IS NOT NULL",
            (account_id,)).fetchone() is not None


def resolved_email(account_id: int) -> str | None:
    """The address to actually write to for this account.

    The linked contact record owns it: contacts are where staff maintain
    guardian details, and a portal account is a login sitting on top of
    that person. ``parent_accounts.email`` is the fallback for accounts
    with no contact link — and for a linked account whose contact has no
    address on file, since a stale address beats none.
    """
    from_contact = contact_email(account_id)
    if from_contact:
        return from_contact
    account = get_account(account_id)
    return account.email if account else None


def _sync_mirror_email(account_id: int) -> None:
    """Push the resolved address to shared auth after a link change."""
    account = get_account(account_id)
    if account is None:
        return
    _mirror_safely(
        "contact link", account.username,
        lambda: _mirror.set_details(account.username, account.full_name,
                                    resolved_email(account_id)))


def account_for_username(username: str) -> ParentAccount | None:
    """Resolve a signed-in shared-auth username to its portal account.

    The parent-facing GUI/CLI are launched by the unified launcher, which
    has already authenticated the user — so they identify the account by
    username rather than asking for the password a second time. Returns
    ``None`` when the user holds a ``parent`` role but has no portal
    record (or it has been disabled), which the callers surface as an
    explanatory screen rather than an error.
    """
    init_db()
    username = (username or "").strip().lower()
    if not username:
        return None
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM parent_accounts WHERE username=? AND is_active=1",
            (username,)).fetchone()
    return _row_to_account(r) if r else None


def is_linked(account_id: int, student_id: str) -> bool:
    """True when *student_id* is one of this account's children.

    Every parent-facing read goes through this first: the snapshot
    helpers take a bare ``student_id``, so without the check a caller
    could ask for any student in the college.
    """
    init_db()
    with _connect() as conn:
        return conn.execute(
            "SELECT 1 FROM parent_student_links WHERE account_id=? AND student_id=?",
            (account_id, student_id)).fetchone() is not None


def linked_students(account_id: int) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT l.student_id, l.relationship, l.contact_id,
                   s.first_name, s.last_name,
                   c.first_name AS c_first, c.last_name AS c_last, c.email AS c_email
              FROM parent_student_links l
              JOIN students s ON s.student_id = l.student_id
              LEFT JOIN parent_contacts c ON c.contact_id = l.contact_id
             WHERE l.account_id=?
             ORDER BY s.last_name, s.first_name
            """, (account_id,)).fetchall()
    return [{"student_id": r["student_id"], "relationship": r["relationship"],
             "full_name": f"{r['first_name']} {r['last_name']}".strip(),
             "contact_id": r["contact_id"],
             "contact_name": (f"{r['c_first']} {r['c_last']}".strip()
                              if r["contact_id"] else None),
             "contact_email": r["c_email"]} for r in rows]


# ── Read-only child snapshots ────────────────────────────────────────

def student_snapshot(student_id: str) -> dict[str, Any]:
    """Build the parent-safe view of one student.

    Aggregates only the fields appropriate for a guardian: identity,
    attendance, risk band (no internal factor breakdown), predicted vs
    target grades, a recent behaviour summary and UCAS progress %.
    """
    init_db()
    from education_system.systems.sixth_form.domain.assessment.risk_analytics import risk_analytics

    with _connect() as conn:
        s = conn.execute(
            "SELECT first_name, last_name, email, status FROM students WHERE student_id=?",
            (student_id,)).fetchone()
        if not s:
            raise ValidationError(f"Unknown student: {student_id}")
        # Recent behaviour (last 30 days), positive/negative split.
        behaviour = {"positive": 0, "negative": 0}
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='behaviour_entries'").fetchone():
            start = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
            for r in conn.execute(
                "SELECT entry_type, COUNT(*) n FROM behaviour_entries "
                "WHERE student_id=? AND entry_date>=? GROUP BY entry_type", (student_id, start)):
                if r["entry_type"] == "Positive":
                    behaviour["positive"] = r["n"]
                elif r["entry_type"] == "Negative":
                    behaviour["negative"] = r["n"]

    assessment = risk_analytics.assess_student(student_id)
    # Predicted grades have no share flag, so a guardian only sees a
    # prediction that went out on a published (approved) report card.
    # The forecast blends the prediction in, so it is withheld with it.
    from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
        learner_view as _lv,
    )
    try:
        shared = _lv.shareable_predictions(student_id)
    except Exception:
        logger.debug("Shareable predictions unavailable for %s", student_id,
                     exc_info=True)
        shared = {}
    subjects = []
    for p in assessment.predictions:
        ok = p.subject in shared
        subjects.append({
            "subject": p.subject,
            "predicted": shared.get(p.subject) if ok else None,
            "target": p.target_grade, "latest_mock": p.latest_mock_grade,
            "forecast": p.forecast_grade if ok else None,
            "on_target": p.on_target if ok else None,
        })

    ucas = None
    try:
        from education_system.systems.sixth_form.domain.progression.university import workflow as ucas_workflow
        pipe = ucas_workflow.get_pipeline(student_id)
        ucas = {"percent": pipe["percent"], "complete": pipe["complete"],
                "total": pipe["total"]}
    except Exception:
        logger.debug("UCAS pipeline unavailable for %s", student_id, exc_info=True)

    # Coursework: what is set, what is in, and only those results the
    # student has already had released to them.
    coursework = None
    try:
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_scheduling as _scheduling,
        )
        coursework = {
            "summary": _scheduling.parent_summary(student_id),
            "recent": [
                {
                    "title": v.title, "subject": v.subject_name,
                    "due_date": v.due_date, "state": v.state,
                    "marks": v.marks, "max_marks": v.max_marks,
                    "grade": v.grade,
                    "feedback_available": v.feedback_available,
                }
                for v in _scheduling.parent_view(student_id, limit=10)
            ],
        }
    except Exception:
        logger.debug("Coursework unavailable for %s", student_id,
                      exc_info=True)

    return {
        "student_id": student_id,
        "full_name": f"{s['first_name']} {s['last_name']}".strip(),
        "status": s["status"],
        "attendance_pct": assessment.attendance_pct,
        "risk_band": assessment.band,
        "behaviour_30d": behaviour,
        "subjects": subjects,
        "ucas": ucas,
        "coursework": coursework,
    }


def recent_attendance(student_id: str, days: int | None = None) -> dict[str, Any]:
    """Attendance detail behind the headline percentage.

    Returns per-status counts plus the individual sessions the student
    missed or arrived late for. Staff-only fields (who marked the
    register, internal notes) are not included.

    Deliberately does **not** compute its own percentage. The college's
    definition — ``Late`` counts as attending, authorised absence is
    excluded from the denominator — lives in
    :mod:`...risk_analytics`, and a second naive figure alongside it read
    as a contradiction on the same screen. The window defaults to the
    same one that figure uses so the counts here explain it.
    """
    init_db()
    from education_system.systems.sixth_form.domain.assessment.risk_analytics import (
        risk_analytics,
    )
    if days is None:
        days = risk_analytics.DEFAULT_WINDOW_DAYS

    start = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    counts: dict[str, int] = {}
    sessions: list[dict[str, Any]] = []
    with _connect() as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='attendance_records'"
        ).fetchone():
            return {"days": days, "counts": {}, "total": 0, "absences": []}

        for r in conn.execute(
            "SELECT status, COUNT(*) n FROM attendance_records "
            "WHERE student_id=? AND date>=? GROUP BY status", (student_id, start)):
            counts[r["status"]] = r["n"]

        for r in conn.execute(
            "SELECT date, status, minutes_late FROM attendance_records "
            "WHERE student_id=? AND date>=? AND status<>'Present' "
            "ORDER BY date DESC LIMIT 50", (student_id, start)):
            sessions.append({"date": r["date"], "status": r["status"],
                             "minutes_late": r["minutes_late"]})

    return {
        "days": days,
        "counts": counts,
        "total": sum(counts.values()),
        "absences": sessions,
    }


def recent_behaviour(student_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """The student's recent behaviour record, positive and negative.

    Deliberately excludes the recording staff member and any follow-up
    workflow state — a parent sees what happened, not how the college is
    handling it internally.
    """
    init_db()
    with _connect() as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='behaviour_entries'"
        ).fetchone():
            return []
        rows = conn.execute(
            "SELECT entry_date, entry_type, category, severity, points, "
            "       description, action_taken "
            "  FROM behaviour_entries WHERE student_id=? "
            " ORDER BY entry_date DESC, entry_id DESC LIMIT ?",
            (student_id, limit)).fetchall()
    return [{"date": r["entry_date"], "type": r["entry_type"],
             "category": r["category"], "severity": r["severity"],
             "points": r["points"], "description": r["description"],
             "action_taken": r["action_taken"]} for r in rows]


def child_detail(account_id: int, student_id: str) -> dict[str, Any]:
    """The full parent-facing view of one linked child.

    Refuses students this account is not linked to, so the parent-facing
    GUI/CLI cannot be steered at another family's record.
    """
    init_db()
    if not is_linked(account_id, student_id):
        raise ValidationError("You are not linked to this student.")
    detail = student_snapshot(student_id)
    detail["attendance"] = recent_attendance(student_id)
    detail["behaviour"] = recent_behaviour(student_id)
    # The read-only move-to-university tracker the learner sees in their own
    # portal (results-day embargo applied there). None without an application.
    detail["ucas_tracker"] = None
    try:
        from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
            learner_view as _lv,
        )
        detail["ucas_tracker"] = _lv.ucas_tracker(student_id)
    except Exception:
        logger.debug("UCAS tracker unavailable for %s", student_id, exc_info=True)
    return detail


# ── Mailbox ──────────────────────────────────────────────────────────

def parent_messages(account_id: int, limit: int = 50) -> list[dict[str, Any]]:
    """Messages the college has sent to this parent's own address.

    Scoped to ``to_address`` on purpose. Correspondence *about* a child is
    usually addressed to the student, and a guardian account is not a
    licence to read their child's mail — so only what was sent to the
    parent themselves appears here.
    """
    init_db()
    address = resolved_email(account_id)
    if not address:
        return []

    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msgs,
    )
    rows = _msgs.list_messages(to_address=address, inbox_visible=True)
    return [{
        "message_id": m.message_id,
        "subject": m.subject,
        "from_name": m.from_name,
        "from_address": m.from_address,
        "category": m.category,
        "priority": m.priority,
        "sent_at": m.sent_at,
    } for m in rows[:limit]]


def parent_message(account_id: int, message_id: int) -> dict[str, Any]:
    """One message in full, provided it was addressed to this parent.

    Re-checks the recipient rather than trusting the id from the caller —
    message ids are sequential, so without this a parent could walk the
    whole college's correspondence.
    """
    init_db()
    address = resolved_email(account_id)
    if not address:
        raise ValidationError("This account has no email address.")

    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msgs,
    )
    msg = _msgs.get_message(int(message_id))
    if msg is None or (msg.to_address or "").strip().lower() != address.strip().lower():
        raise ValidationError("That message is not in your mailbox.")
    return {
        "message_id": msg.message_id,
        "subject": msg.subject,
        "body": msg.body,
        "from_name": msg.from_name,
        "from_address": msg.from_address,
        "category": msg.category,
        "priority": msg.priority,
        "sent_at": msg.sent_at,
    }


def get_account(account_id: int) -> ParentAccount | None:
    """Look one account up by id, active or not."""
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM parent_accounts WHERE account_id=?",
                         (account_id,)).fetchone()
    return _row_to_account(r) if r else None


def account_dashboard(account_id: int) -> dict[str, Any]:
    """Everything one logged-in parent should see: their identity plus a
    snapshot per linked child."""
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM parent_accounts WHERE account_id=?", (account_id,)).fetchone()
        if not r:
            raise ValidationError(f"Unknown account: {account_id}")
        account = _row_to_account(r)
    children = []
    for link in linked_students(account_id):
        snap = student_snapshot(link["student_id"])
        snap["relationship"] = link["relationship"]
        children.append(snap)
    return {
        "account": {"username": account.username, "full_name": account.full_name,
                    "email": resolved_email(account_id)},
        "children": children,
    }


# ── Parent actions (scoped to linked children) ───────────────────────
#
# Everything below takes the signed-in account and a child, and refuses
# unless the two are linked. The work itself is done by the owning
# module (attendance, trips, bursaries, parents' evenings, report cards);
# this layer only scopes it and records who acted.

def _require_link(account_id: int, student_id: str) -> str:
    sid = (student_id or "").strip()
    if not sid or not is_linked(account_id, sid):
        raise ValidationError("You are not linked to this student.")
    return sid


def _require_account(account_id: int) -> ParentAccount:
    account = get_account(account_id)
    if account is None or not account.is_active:
        raise ValidationError("Your parent portal account is not active.")
    return account


def _lv():
    from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
        learner_view,
    )
    return learner_view


def child_timetable(account_id: int, student_id: str) -> list[dict[str, Any]]:
    return _lv().timetable(_require_link(account_id, student_id))


def child_report_cards(account_id: int, student_id: str) -> list[dict[str, Any]]:
    return _lv().report_cards(_require_link(account_id, student_id))


def child_report_card_text(account_id: int, student_id: str, card_id: int) -> str:
    return _lv().report_card_text(_require_link(account_id, student_id), card_id)


def child_report_card_file(account_id: int, student_id: str, card_id: int, *,
                           fmt: str = "html") -> str:
    """Write a published report to a file and return its path."""
    from education_system.systems.sixth_form.domain.assessment.report_cards import (
        report_cards as _rc,
    )
    sid = _require_link(account_id, student_id)
    card = _rc.published_card(sid, card_id)
    return str(_rc.render(card.card_id, fmt=fmt))


# Absence ----------------------------------------------------------------

def report_child_absence(account_id: int, student_id: str, date_from: str, *,
                         date_to: str | None = None, reason: str | None = None,
                         message: str | None = None):
    """Tell the college a linked child is or will be absent.

    Goes to the attendance office's queue as Pending (exactly like a phone
    call) via ``attendance_absence_reports.report_absence_as_parent``,
    which re-checks the link itself.
    """
    account = _require_account(account_id)
    sid = _require_link(account_id, student_id)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_absence_reports as _abs,
    )
    return _abs.report_absence_as_parent(
        account.username, sid, date_from, date_to=date_to,
        reason_text=(reason or "").strip() or None,
        message=(message or "").strip() or None)


def child_absence_reports(account_id: int, student_id: str) -> list[dict[str, Any]]:
    sid = _require_link(account_id, student_id)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_absence_reports as _abs,
    )
    return [{"report_id": r.report_id, "dates": r.span, "reason": r.reason_text,
             "reported_by": r.reported_by, "state": r.state,
             "self_certified": r.self_certified, "received_at": r.received_at}
            for r in _abs.list_reports(student_id=sid, limit=50)]


# Trips and consent ------------------------------------------------------

def child_trips(account_id: int, student_id: str) -> list[dict[str, Any]]:
    return _lv().trips(_require_link(account_id, student_id))


def set_trip_consent(account_id: int, student_id: str, booking_id: int, *,
                     consent: bool, medical_note: str | None = None,
                     dietary_note: str | None = None,
                     note: str | None = None) -> dict[str, Any]:
    """Give (or withdraw) consent for a linked child's trip booking.

    The booking must belong to the child. Medical and dietary notes are
    stored on the booking for the trip leader. The consent note records
    who consented, how and when, so the trip file shows it was the
    parent and not staff.
    """
    account = _require_account(account_id)
    sid = _require_link(account_id, student_id)
    from education_system.systems.sixth_form.domains.finance.domain.trips import trips as _t
    booking = _t.get_booking(int(booking_id))
    if booking is None or booking.student_id != sid:
        raise ValidationError("That trip booking is not for this student.")
    trip = _t.get_trip(booking.trip_id)
    if trip is not None and trip.status in ("Completed", "Cancelled"):
        raise ValidationError(f"{trip.name} is {trip.status.lower()} — consent "
                              "can no longer be changed here.")
    stamp = _dt.datetime.now().isoformat(sep=" ", timespec="minutes")
    action = "given" if consent else "withdrawn"
    record = f"Consent {action} by {account.full_name} via parent portal {stamp}"
    if (note or "").strip():
        record += f": {note.strip()}"
    payload: dict[str, Any] = {"consent_received": bool(consent),
                               "consent_note": record}
    if medical_note is not None:
        payload["medical_note"] = medical_note
    if dietary_note is not None:
        payload["dietary_note"] = dietary_note
    try:
        _t.update_booking(booking.booking_id, payload)
    except _t.ValidationError as e:
        raise ValidationError(str(e)) from None
    logger.info("Trip consent %s for booking #%s by parent %s", action,
                booking.booking_id, account.username)
    return next((t for t in _lv().trips(sid) if t["booking_id"] == booking.booking_id),
                {})


# Bursaries --------------------------------------------------------------

def child_bursaries(account_id: int, student_id: str) -> list[dict[str, Any]]:
    return _lv().bursaries(_require_link(account_id, student_id))


def bursary_types() -> tuple[str, ...]:
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _b,
    )
    return _b.BURSARY_TYPES


def start_bursary_application(account_id: int, student_id: str, *,
                              bursary_type: str, reason: str,
                              amount_requested: float | None = None,
                              household_income: float | None = None,
                              household_size: int | None = None):
    """Start a bursary application for a linked child.

    Lands as Submitted with no evidence recorded; the finance office
    assesses it and asks for evidence in the usual way.
    """
    account = _require_account(account_id)
    sid = _require_link(account_id, student_id)
    if not (reason or "").strip():
        raise ValidationError("Please say briefly what the support is for.")
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _b,
    )
    try:
        return _b.create_application({
            "student_id": sid, "bursary_type": bursary_type,
            "application_date": _dt.date.today().isoformat(),
            "amount_requested": amount_requested, "status": "Submitted",
            "household_income": household_income, "household_size": household_size,
            "reason": reason.strip(),
            "notes": f"Started by {account.full_name} ({account.username}) "
                     "via the parent portal",
        })
    except _b.ValidationError as e:
        raise ValidationError(str(e)) from None


# Parents' evenings ------------------------------------------------------

def _pe():
    from education_system.systems.sixth_form.domains.communications.domain.parents_evenings import (
        parents_evenings,
    )
    return parents_evenings


def parents_evening_events() -> list[Any]:
    return _pe().bookable_events()


def parents_evening_options(account_id: int, event_id: int, student_id: str):
    return _pe().parent_options(int(event_id), _require_link(account_id, student_id))


def book_parents_evening(account_id: int, event_id: int, student_id: str,
                         staff_id: str, slot_time: str, *,
                         notes: str | None = None):
    account = _require_account(account_id)
    sid = _require_link(account_id, student_id)
    pe = _pe()
    try:
        return pe.parent_book(int(event_id), student_id=sid, staff_id=staff_id,
                              slot_time=slot_time, parent_account_id=account_id,
                              parent_name=account.full_name, notes=notes)
    except pe.ValidationError as e:
        raise ValidationError(str(e)) from None


def cancel_parents_evening(account_id: int, booking_id: int):
    _require_account(account_id)
    pe = _pe()
    children = {c["student_id"] for c in linked_students(account_id)}
    try:
        return pe.parent_cancel(int(booking_id), student_ids=children,
                                parent_account_id=account_id)
    except pe.ValidationError as e:
        raise ValidationError(str(e)) from None


def parents_evening_bookings(account_id: int) -> list[Any]:
    children = [c["student_id"] for c in linked_students(account_id)]
    return _pe().bookings_for_students(children)


# Contact-detail change requests -----------------------------------------

CONTACT_REQUEST_FIELDS: dict[str, str] = {
    "email": "Email",
    "primary_phone": "Main phone",
    "secondary_phone": "Other phone",
    "address": "Address",
    "preferred_method": "Preferred contact method",
    "preferred_language": "Preferred language",
}
REQUEST_PENDING = "Pending"
REQUEST_APPLIED = "Applied"
REQUEST_REJECTED = "Rejected"

_REQUEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_contact_change_requests (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL,
    student_id      TEXT,
    contact_id      INTEGER,
    changes         TEXT NOT NULL,
    note            TEXT,
    status          TEXT NOT NULL DEFAULT 'Pending',
    created_at      TEXT DEFAULT (datetime('now')),
    resolved_by     TEXT,
    resolved_at     TEXT,
    resolution_note TEXT,
    FOREIGN KEY (account_id) REFERENCES parent_accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)        ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES parent_contacts(contact_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pccr_status  ON parent_contact_change_requests(status);
CREATE INDEX IF NOT EXISTS idx_pccr_account ON parent_contact_change_requests(account_id);
"""

_REQUESTS_READY = False


def _init_requests() -> None:
    global _REQUESTS_READY
    if _REQUESTS_READY:
        return
    init_db()
    with _connect() as conn:
        conn.executescript(_REQUEST_SCHEMA)
    _REQUESTS_READY = True


def _request_row(r: sqlite3.Row) -> dict[str, Any]:
    import json
    d = dict(r)
    try:
        d["changes"] = json.loads(r["changes"] or "{}")
    except ValueError:
        d["changes"] = {}
    return d


def request_contact_update(account_id: int, changes: dict[str, Any], *,
                           student_id: str | None = None,
                           note: str | None = None) -> dict[str, Any]:
    """Ask the office to change the contact details held for this parent.

    Never edits the contact record itself: the office checks and applies
    the request (a changed phone number or address on a child's record
    is a safeguarding matter, not a self-service one).
    """
    import json
    _init_requests()
    account = _require_account(account_id)
    clean = {k: str(v).strip() for k, v in (changes or {}).items()
             if k in CONTACT_REQUEST_FIELDS and v is not None and str(v).strip()}
    if not clean:
        raise ValidationError("Enter at least one detail to change.")
    if "email" in clean:
        _clean_email(clean["email"])
    contact_id = None
    sid = None
    if student_id:
        sid = _require_link(account_id, student_id)
    links = linked_students(account_id)
    for link in links:
        if (sid is None or link["student_id"] == sid) and link["contact_id"]:
            contact_id = link["contact_id"]
            sid = sid or link["student_id"]
            break
    if sid is None and links:
        sid = links[0]["student_id"]
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO parent_contact_change_requests (account_id, student_id, "
            "contact_id, changes, note) VALUES (?,?,?,?,?)",
            (account_id, sid, contact_id, json.dumps(clean),
             (note or "").strip() or None))
        conn.commit()
        rid = cur.lastrowid
    logger.info("Contact change request #%s from parent %s", rid, account.username)
    return get_contact_request(rid)


def get_contact_request(request_id: int) -> dict[str, Any]:
    _init_requests()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM parent_contact_change_requests WHERE request_id=?",
                         (int(request_id),)).fetchone()
    if r is None:
        raise ValidationError(f"No request #{request_id}")
    return _request_row(r)


def my_contact_requests(account_id: int) -> list[dict[str, Any]]:
    _init_requests()
    with _connect() as conn:
        return [_request_row(r) for r in conn.execute(
            "SELECT * FROM parent_contact_change_requests WHERE account_id=? "
            "ORDER BY created_at DESC, request_id DESC", (account_id,))]


def list_contact_requests(*, status: str | None = REQUEST_PENDING) -> list[dict[str, Any]]:
    """Staff queue of contact-detail change requests."""
    _init_requests()
    sql = ("SELECT r.*, a.full_name AS parent_name, a.username, "
           "s.first_name || ' ' || s.last_name AS student_name "
           "FROM parent_contact_change_requests r "
           "JOIN parent_accounts a ON a.account_id = r.account_id "
           "LEFT JOIN students s ON s.student_id = r.student_id")
    args: list[Any] = []
    if status:
        sql += " WHERE r.status=?"
        args.append(status)
    sql += " ORDER BY r.created_at, r.request_id"
    with _connect() as conn:
        return [_request_row(r) for r in conn.execute(sql, args)]


def resolve_contact_request(request_id: int, *, apply: bool, by: str,
                            note: str | None = None) -> dict[str, Any]:
    """Office decision on a request.

    ``apply=True`` writes the changes to the linked contact record through
    ``parent_contacts.update_contact`` (its validation applies). With no
    contact record linked the request is marked Applied with a note so
    the office can update the record by hand.
    """
    req = get_contact_request(request_id)
    if req["status"] != REQUEST_PENDING:
        raise ValidationError(f"Request #{request_id} is already {req['status'].lower()}")
    resolution = (note or "").strip() or None
    if apply:
        if req["contact_id"]:
            contacts = contacts_module()
            try:
                contacts.update_contact(req["contact_id"], req["changes"])
            except contacts.ValidationError as e:
                raise ValidationError(str(e)) from None
            _sync_mirror_email(req["account_id"])
        else:
            resolution = ((resolution + " — ") if resolution else "") + \
                "no contact record linked; update the record by hand"
    with _connect() as conn:
        conn.execute(
            "UPDATE parent_contact_change_requests SET status=?, resolved_by=?, "
            "resolved_at=datetime('now'), resolution_note=? WHERE request_id=?",
            (REQUEST_APPLIED if apply else REQUEST_REJECTED, by, resolution,
             request_id))
        conn.commit()
    logger.info("Contact change request #%s %s by %s", request_id,
                "applied" if apply else "rejected", by)
    return get_contact_request(request_id)

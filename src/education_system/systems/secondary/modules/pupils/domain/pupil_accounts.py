"""Pupil logins and school e-mail addresses.

When a pupil is added, they get:

* a **login** in the shared ``auth.db`` with the secondary ``student`` role.
  The username is their legal first name in lower case (``amira``); if that is
  taken, a number is added (``amira2``, ``amira3``...).
* a **password**: their legal surname followed by 5 random digits
  (``Khan48213``). Pupil passwords are deliberately simpler than the staff
  password policy (school's choice, 2026-11-03).
* a **school e-mail address** ``firstname.lastname@secondarysch.uk``, numbered the
  same way if already used (``amira.khan2@...``).
* a **welcome e-mail** to that address from the ``welcome_pupil`` JSON
  template, through the school outbox (so it follows the delivery mode).

The password is never stored here or written to the activity log; it exists
only in the account's hash and the welcome e-mail. Deleting a pupil record
takes the pupil role off their login.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import secrets
import unicodedata
from dataclasses import dataclass

from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.communication.domain import email_templates
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

SCHOOL_EMAIL_DOMAIN = "secondarysch.uk"
WELCOME_TEMPLATE = "welcome_pupil"
PASSWORD_DIGITS = 5

_SCHEMA = """
-- No foreign key to pupils: a deleted pupil's username and address stay
-- reserved, so they are never handed to a different child.
CREATE TABLE IF NOT EXISTS pupil_accounts (
    pupil_id           INTEGER PRIMARY KEY,
    user_id            INTEGER NOT NULL,
    username           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    school_email       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    status             TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'removed')),
    welcome_message_id INTEGER,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by         TEXT,
    removed_at         TEXT
);
"""

database.register_schema("pupil_accounts", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class PupilAccount:
    pupil_id: int
    user_id: int
    username: str
    school_email: str
    status: str
    welcome_message_id: int | None
    created_at: str
    created_by: str | None


@dataclass(frozen=True)
class NewAccount:
    """What :func:`create_for_pupil` made. ``password`` is shown once to the
    member of staff and is not kept anywhere else."""

    account: PupilAccount
    password: str
    welcome_message_id: int | None
    welcome_error: str | None


# ── Names ────────────────────────────────────────────────────────────

def _ascii_letters(text: str, keep: str = "") -> str:
    folded = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(rf"[^a-z{re.escape(keep)}]", "", folded.lower()).strip(keep)


def _first_free(base: str, taken: set[str], fmt) -> str:
    n = 1
    while True:
        candidate = fmt(base, "" if n == 1 else str(n))
        if candidate.lower() not in taken:
            return candidate
        n += 1


def _username_for(pupil: P.Pupil) -> str:
    base = _ascii_letters(pupil.legal_first_name) or "pupil"
    with database.connect() as conn:
        mine = {r[0].lower() for r in conn.execute(
            "SELECT username FROM pupil_accounts WHERE username LIKE ?", (base + "%",))}
    return _first_free(base, mine | accounts.usernames_like(base), lambda b, n: b + n)


def _email_for(pupil: P.Pupil) -> str:
    first = _ascii_letters(pupil.legal_first_name, "-") or "pupil"
    last = _ascii_letters(pupil.legal_last_name, "-") or "pupil"
    base = f"{first}.{last}"
    with database.connect() as conn:
        taken = {r[0].lower() for r in conn.execute(
            "SELECT school_email FROM pupil_accounts WHERE school_email LIKE ?",
            (base + "%@" + SCHOOL_EMAIL_DOMAIN,))}
    return _first_free(base, taken, lambda b, n: f"{b}{n}@{SCHOOL_EMAIL_DOMAIN}")


def _password_for(pupil: P.Pupil) -> str:
    surname = "".join(pupil.legal_last_name.split()) or "Pupil"
    return surname + "".join(str(secrets.randbelow(10)) for _ in range(PASSWORD_DIGITS))


# ── Read ─────────────────────────────────────────────────────────────

def get_for_pupil(pupil_id: int) -> PupilAccount | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pupil_accounts WHERE pupil_id = ?",
                         (int(pupil_id),)).fetchone()
    if r is None:
        return None
    return PupilAccount(r["pupil_id"], r["user_id"], r["username"], r["school_email"],
                        r["status"], r["welcome_message_id"], r["created_at"], r["created_by"])


def list_accounts() -> list[PupilAccount]:
    """Every pupil login record (active and removed), newest first."""
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM pupil_accounts ORDER BY created_at DESC, "
                            "pupil_id DESC").fetchall()
    return [PupilAccount(r["pupil_id"], r["user_id"], r["username"], r["school_email"],
                         r["status"], r["welcome_message_id"], r["created_at"], r["created_by"])
            for r in rows]


# ── Create / remove ──────────────────────────────────────────────────

def create_for_pupil(pupil_id: int, *, actor: Principal,
                     send_welcome: bool = True) -> NewAccount:
    """Create the pupil's login and school address, and queue the welcome e-mail.

    The e-mail is saved to the outbox but not delivered: run
    ``email_outbox.deliver(result.welcome_message_id)`` next (the GUI does it
    off the Tk thread). A problem with the e-mail doesn't undo the account; it
    comes back in ``welcome_error``.
    """
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    if not actor.can_edit_pupils:
        activity_log.record("account.create", target=pupil.admission_no, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Your account can't create pupil logins.")
    if get_for_pupil(pupil_id) is not None:
        activity_log.record("account.create", target=pupil.admission_no,
                            outcome="already_exists", principal=actor)
        raise ValidationError([f"{pupil.display_name} already has a login"])

    username = _username_for(pupil)
    school_email = _email_for(pupil)
    password = _password_for(pupil)
    try:
        user_id = accounts.create_login(username, password, display_name=pupil.full_name,
                                        email=school_email)
    except Exception as e:
        logger.exception("Creating pupil login failed")
        activity_log.record("account.create", target=pupil.admission_no, outcome="error",
                            principal=actor, error=type(e).__name__)
        raise
    try:
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO pupil_accounts (pupil_id, user_id, username, school_email, "
                "created_by) VALUES (?, ?, ?, ?, ?)",
                (pupil.pupil_id, user_id, username, school_email, actor.username))
    except Exception:
        # Don't leave a login nobody knows about.
        try:
            accounts.remove_pupil_access(username, school_email)
        except Exception:
            logger.exception("Could not roll back pupil login")
        activity_log.record("account.create", target=pupil.admission_no, outcome="error",
                            principal=actor, user_id=user_id)
        raise
    activity_log.record("account.create", target=pupil.admission_no, principal=actor,
                        user_id=user_id)

    message_id = error = None
    if send_welcome:
        message_id, error = _queue_welcome(pupil, username, password, school_email, actor)
    return NewAccount(get_for_pupil(pupil.pupil_id), password, message_id, error)  # type: ignore[arg-type]


def _form_values(pupil: P.Pupil) -> dict[str, str]:
    """Form name, tutor, room and the ready-made ``form_details`` lines for the e-mails.
    A problem reading forms mustn't stop the e-mail: fall back to the name alone."""
    from education_system.systems.secondary.modules.curriculum.domain import form_groups
    try:
        return form_groups.details_for(pupil)
    except Exception:  # noqa: BLE001
        logger.exception("Form details for e-mail failed")
        name = pupil.form_group or "not set yet"
        return {"form_group": pupil.form_group or "",
                "form_details": f"    Form:        {name} (Year {pupil.year_group})"}


def _queue_welcome(pupil: P.Pupil, username: str, password: str, school_email: str,
                   actor: Principal) -> tuple[int | None, str | None]:
    try:
        template = email_templates.load_template(WELCOME_TEMPLATE)
        subject, body = template.render({
            "pupil_first_name": pupil.preferred_name or pupil.legal_first_name,
            "pupil_name": pupil.display_name,
            "username": username,
            "password": password,
            "school_email": school_email,
            "year_group": pupil.year_group,
            **_form_values(pupil),
        })
        message_id = E.send_to_address(school_email, pupil.display_name, subject, body,
                                       actor=actor, kind="pupil_welcome",
                                       label=f"Welcome e-mail to {pupil.admission_no}",
                                       pupil=pupil)
    except Exception as e:  # noqa: BLE001 - the account stands; report the e-mail problem
        logger.exception("Welcome e-mail failed")
        activity_log.record("account.welcome", target=pupil.admission_no, outcome="error",
                            principal=actor, error=type(e).__name__)
        return None, str(e)
    with database.connect() as conn:
        conn.execute("UPDATE pupil_accounts SET welcome_message_id = ? WHERE pupil_id = ?",
                     (message_id, pupil.pupil_id))
    return message_id, None


# ── Record-updated notice ────────────────────────────────────────────

UPDATE_TEMPLATE = "record_updated"

#: How each field is described to the pupil. Fields mapping to None are staff-only
#: (needs, eligibility, notes): they are never named in the e-mail, and a change
#: to only those sends nothing.
PUPIL_FACING_LABELS: dict[str, str | None] = {
    "upn": "Unique pupil number",
    "legal_first_name": "Name",
    "middle_names": "Name",
    "legal_last_name": "Name",
    "preferred_name": "Preferred name",
    "date_of_birth": "Date of birth",
    "gender": "Gender",
    "year_group": "Year group",
    "form_group": "Form group",
    "admission_date": "Date you joined the school",
    "roll_status": "Enrolment status",
    "leaving_date": "Enrolment status",
    "leaving_reason": "Enrolment status",
    "address_line1": "Home address",
    "address_line2": "Home address",
    "town": "Home address",
    "postcode": "Home address",
    "sen_status": None,
    "fsm_eligible": None,
    "eal": None,
    "notes": None,
}


def pupil_facing_changes(changed_fields: list[str]) -> list[str]:
    """The parts of the record a pupil is told about, in a stable order."""
    labels = [PUPIL_FACING_LABELS.get(f) for f in changed_fields]
    return list(dict.fromkeys(label for label in labels if label))


def notify_record_updated(pupil_id: int, changed_fields: list[str], *,
                          actor: Principal) -> tuple[int | None, str]:
    """Queue the "your record has been updated" e-mail to the pupil.

    Returns ``(message_id, note)``. ``message_id`` is None when nothing was
    sent, with *note* saying why (no login, only staff-only fields changed,
    or an error). Run ``email_outbox.deliver(message_id)`` next.
    """
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        return None, "the pupil record no longer exists"
    parts = pupil_facing_changes(changed_fields)
    if not parts:
        return None, "no e-mail: nothing the pupil is told about changed"
    account = get_for_pupil(pupil_id)
    if account is None or account.status != "active":
        activity_log.record("account.update_notice", target=pupil.admission_no,
                            outcome="no_login", principal=actor)
        return None, "no e-mail: the pupil has no school login yet"
    try:
        import datetime as _dt
        today = _dt.date.today()
        subject, body = email_templates.load_template(UPDATE_TEMPLATE).render({
            "pupil_first_name": pupil.preferred_name or pupil.legal_first_name,
            "pupil_name": pupil.display_name,
            "changes": "\n".join(f"  - {p}" for p in parts),
            "updated_date": f"{today.day} {today:%B %Y}",
            "school_email": account.school_email,
            "year_group": pupil.year_group,
            **_form_values(pupil),
        })
        message_id = E.send_to_address(account.school_email, pupil.display_name, subject,
                                       body, actor=actor, kind="pupil_record_updated",
                                       label=f"Record-updated notice to {pupil.admission_no}",
                                       pupil=pupil)
    except Exception as e:  # noqa: BLE001 - the edit stands; report the e-mail problem
        logger.exception("Record-updated e-mail failed")
        activity_log.record("account.update_notice", target=pupil.admission_no,
                            outcome="error", principal=actor, error=type(e).__name__)
        return None, f"the e-mail could not be prepared: {e}"
    return message_id, "e-mail queued"


#: What a leaver sees if they try to sign in after their login was closed.
LEAVER_MESSAGE = ("Your school account was closed on {date} because you have left the school. "
                  "If you think this is a mistake, please contact the school office.")


def close_for_leaver(pupil_id: int, *, actor: Principal, left_on: str) -> bool:
    """Close a leaver's login, leaving the "you have left" message for sign-in.
    False if there was no active login (or it couldn't be closed - logged)."""
    account = get_for_pupil(pupil_id)
    if account is None or account.status != "active":
        return False
    try:
        d = _dt.date.fromisoformat(left_on)
        message = LEAVER_MESSAGE.format(date=f"{d.day} {d:%B %Y}")
    except ValueError:
        message = LEAVER_MESSAGE.format(date=left_on)
    target = f"pupil:{pupil_id}"
    try:
        accounts.close_pupil_login(account.username, account.school_email, message)
    except Exception as e:  # noqa: BLE001 - retried by the next startup sweep
        logger.exception("Closing leaver login failed")
        activity_log.record("account.close", target=target, outcome="error",
                            principal=actor, error=type(e).__name__)
        return False
    with database.connect() as conn:
        conn.execute("UPDATE pupil_accounts SET status = 'removed', removed_at = "
                     "datetime('now') WHERE pupil_id = ?", (int(pupil_id),))
    activity_log.record("account.close", target=target, principal=actor,
                        user_id=account.user_id, reason="leaver")
    return True


def reopen_for_pupil(pupil_id: int, *, actor: Principal) -> bool:
    """Reopen the login of a pupil who is back on roll. False if there was no
    closed login to reopen (or it couldn't be - logged)."""
    account = get_for_pupil(pupil_id)
    if account is None or account.status == "active":
        return False
    target = f"pupil:{pupil_id}"
    try:
        ok = accounts.reopen_pupil_login(account.username, account.school_email)
    except Exception as e:  # noqa: BLE001
        logger.exception("Reopening pupil login failed")
        activity_log.record("account.reopen", target=target, outcome="error",
                            principal=actor, error=type(e).__name__)
        return False
    if not ok:
        activity_log.record("account.reopen", target=target, outcome="not_found",
                            principal=actor)
        return False
    with database.connect() as conn:
        conn.execute("UPDATE pupil_accounts SET status = 'active', removed_at = NULL "
                     "WHERE pupil_id = ?", (int(pupil_id),))
    activity_log.record("account.reopen", target=target, principal=actor,
                        user_id=account.user_id)
    return True


def remove_for_pupil(pupil_id: int, *, actor: Principal) -> bool:
    """Take the pupil role off the login of a deleted pupil. False if there was
    no active login."""
    account = get_for_pupil(pupil_id)
    if account is None or account.status != "active":
        return False
    try:
        accounts.remove_pupil_access(account.username, account.school_email)
    except Exception as e:  # noqa: BLE001
        logger.exception("Removing pupil login failed")
        activity_log.record("account.remove", target=f"pupil:{pupil_id}", outcome="error",
                            principal=actor, error=type(e).__name__)
        return False
    with database.connect() as conn:
        conn.execute("UPDATE pupil_accounts SET status = 'removed', removed_at = "
                     "datetime('now') WHERE pupil_id = ?", (int(pupil_id),))
    activity_log.record("account.remove", target=f"pupil:{pupil_id}", principal=actor,
                        user_id=account.user_id)
    return True

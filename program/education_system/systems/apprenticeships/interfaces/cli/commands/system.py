"""Account and system commands, available to every role.

Exposes: change_password, mfa, settings, about, user_accounts.

Mirrors the GUI's System menu. The account commands are thin on purpose:
a login is the platform's, shared with the other five systems, so
everything here goes through ``services.account_service`` rather than
touching ``auth.db`` from an interface module.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import SYSTEM_NAME, VERSION, config
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import account_service, preferences
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)


def about(actor) -> None:
    """About this system and what your role may do."""
    prompts.title(f"About {SYSTEM_NAME}")
    prompts.note(
        "Work-based learning: employed apprentices, off-the-job training, "
        "and independent End-Point Assessment."
    )
    prompts.details([
        ("Version", VERSION),
        ("Signed in as", actor.username or prompts.EMPTY),
        ("Name", actor.name),
        ("Role", actor.role_label),
        ("Linked apprentice record", actor.apprentice_id or prompts.EMPTY),
        ("Linked employer record", actor.employer_id or prompts.EMPTY),
        ("Linked staff record", actor.staff_id or prompts.EMPTY),
    ])

    if not actor.is_admin and not _is_linked(actor):
        prompts.fail(
            f"This login has the {actor.role_label} role but is not linked to a "
            "record in this system, so most screens will be empty. An "
            "administrator needs to set your username on the matching record."
        )

    held = actor.permissions()
    granted = sorted(p for p in config.PERMISSIONS if p in held)
    withheld = sorted(p for p in config.PERMISSIONS if p not in held)

    prompts.title("What your role may do")
    prompts.table(
        [("Capability", 34), ("Held", 6)],
        [*[(p, True) for p in granted], *[(p, False) for p in withheld]],
        lambda row: (row[0], "yes" if row[1] else "no"),
        noun="capability",
    )
    if "epa.grade" not in held:
        prompts.note(
            "\n  Note: nobody at the training provider — administrators included —\n"
            "  may approve gateway or grade an End-Point Assessment. Those belong\n"
            "  solely to the independent assessor."
        )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Password
# ═════════════════════════════════════════════════════════════════════

def change_password(actor: Actor) -> None:
    """Change the password on the shared platform account."""
    prompts.title("Change password")
    account = account_service.whoami(actor)
    if account["user_id"] is None:
        prompts.fail(_NO_ACCOUNT)
        prompts.pause()
        return

    prompts.note(f"Signed in as {account['username']}.")
    prompts.note("Requirements:")
    for rule in account_service.password_requirements():
        prompts.note(f"  · {rule}")
    prompts.note(
        "\n  Changing it signs out every session on this account, including this one."
    )

    current = prompts.ask("Current password", required=True)
    new = prompts.ask("New password", required=True)
    confirm = prompts.ask("Confirm new password", required=True)

    account_service.change_password(actor, current=current, new=new, confirm=confirm)
    prompts.ok("Password changed. Sign in again with the new one.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Multi-factor authentication
# ═════════════════════════════════════════════════════════════════════

def mfa(actor: Actor) -> None:
    """Set up or remove the authenticator app on this account."""
    status = account_service.mfa_status(actor)
    if not status["available"]:
        prompts.title("Multi-factor authentication")
        prompts.fail(_NO_ACCOUNT)
        prompts.pause()
        return

    entries: list[tuple[str, Callable[[], None]]] = [
        ("Where I stand", partial(_mfa_status, actor)),
        ("Enrol an authenticator", partial(_mfa_enrol, actor)),
    ]
    if status["enabled"]:
        entries += [
            ("Turn MFA off", partial(_mfa_disable, actor)),
            ("Turn MFA off with a recovery code", partial(_mfa_disable_recovery, actor)),
        ]
    prompts.run_menu("Multi-Factor Authentication", entries)


def _mfa_status(actor: Actor) -> None:
    status = account_service.mfa_status(actor)
    prompts.title("Multi-factor authentication")
    prompts.details([
        ("Enabled", status["enabled"]),
        ("Recovery codes left", status["recovery_codes_remaining"]),
    ])
    if status["enabled"] and status["recovery_codes_remaining"] <= 2:
        prompts.note(
            "  ! Few recovery codes left. Re-enrol to generate a fresh set — losing "
            "your last one means an administrator has to unlock the account."
        )
    prompts.pause()


def _mfa_enrol(actor: Actor) -> None:
    """Generate a fresh secret and recovery codes.

    Re-enrolling replaces any existing secret and invalidates the old
    codes, which is what "I lost my phone" needs — so it is confirmed
    rather than done on a keystroke.
    """
    status = account_service.mfa_status(actor)
    if status["enabled"] and not prompts.ask_yes_no(
        "MFA is already on. Re-enrolling replaces the secret and every recovery "
        "code. Continue?"
    ):
        raise prompts.Abort

    result = account_service.enrol_mfa(actor)
    prompts.title("Enrol your authenticator")
    prompts.note("Add this account to your authenticator app using either of these:")
    prompts.details([
        ("Setup key", result["secret"]),
        ("Provisioning URI", result["provisioning_uri"]),
    ])

    prompts.note("\n  Recovery codes — write these down now. They are shown once:")
    for code in result["recovery_codes"]:
        prompts.note(f"    {code}")

    prompts.note("\n  Confirm the app is working before you rely on it.")
    code = prompts.ask("Six-digit code from the app", required=True)
    if account_service.confirm_mfa(actor, code):
        prompts.ok("Confirmed. You will be asked for a code at your next sign-in.")
    else:
        prompts.fail(
            "That code was not accepted. MFA is enrolled, so check the app's clock "
            "and try signing in — or re-enrol if the app did not take the key."
        )
    prompts.pause()


def _mfa_disable(actor: Actor) -> None:
    prompts.title("Turn MFA off")
    prompts.note(
        "A current code is required: an unlocked, unattended session must not be "
        "able to strip the second factor off the account."
    )
    code = prompts.ask("Six-digit code from the app", required=True)
    account_service.disable_mfa(actor, code)
    prompts.ok("MFA is off. Your recovery codes have been discarded.")
    prompts.pause()


def _mfa_disable_recovery(actor: Actor) -> None:
    prompts.title("Turn MFA off with a recovery code")
    prompts.note("For a lost or replaced authenticator. The code is used up either way.")
    code = prompts.ask("Recovery code (XXXX-XXXX)", required=True)
    account_service.disable_mfa_with_recovery_code(actor, code)
    prompts.ok("MFA is off. Enrol a new authenticator when you have one.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Settings
# ═════════════════════════════════════════════════════════════════════

def settings(actor: Actor) -> None:
    """Interface preferences for this login, shared with the GUI."""
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Where they stand", partial(_show_settings, actor)),
        ("Date format", partial(_set_date_format, actor)),
        ("Rows per table", partial(_set_rows, actor)),
        ("Idle timeout", partial(_set_idle, actor)),
        ("Reset to defaults", partial(_reset_settings, actor)),
    ]
    prompts.run_menu("Settings", entries)


def _show_settings(actor: Actor) -> None:
    values = preferences.get(actor)
    prompts.title("Settings")
    prompts.note("These follow your login between the CLI and the desktop app.")
    prompts.details([
        ("Date format", preferences.date_format_label(values[preferences.DATE_FORMAT])),
        ("Rows per table", values[preferences.ROWS_PER_PAGE]),
        ("Idle timeout", preferences.idle_timeout_label(
            values[preferences.IDLE_TIMEOUT_MINUTES]
        )),
    ])
    prompts.note(
        "\n  The idle timeout signs the desktop app out after that long without a "
        "keystroke. It does not apply to this terminal."
    )
    prompts.pause()


def _set_date_format(actor: Actor) -> None:
    current = preferences.get(actor)[preferences.DATE_FORMAT]
    label = prompts.choose_value(
        "Date format", tuple(preferences.DATE_FORMATS),
        default=preferences.date_format_label(current),
    )
    preferences.set_preferences(actor, {preferences.DATE_FORMAT: label})
    prompts.ok(f"Dates will show as {label}.")
    prompts.pause()


def _set_rows(actor: Actor) -> None:
    current = preferences.get(actor)[preferences.ROWS_PER_PAGE]
    chosen = prompts.choose_value(
        "Rows per table",
        tuple(str(n) for n in preferences.ROWS_PER_PAGE_CHOICES),
        default=str(current),
    )
    preferences.set_preferences(actor, {preferences.ROWS_PER_PAGE: chosen})
    prompts.ok(f"Tables will show {chosen} rows at a time.")
    prompts.pause()


def _set_idle(actor: Actor) -> None:
    current = preferences.get(actor)[preferences.IDLE_TIMEOUT_MINUTES]
    labels = {
        preferences.idle_timeout_label(n): n for n in preferences.IDLE_TIMEOUT_CHOICES
    }
    chosen = prompts.choose_value(
        "Sign the desktop app out after", tuple(labels),
        default=preferences.idle_timeout_label(current),
    )
    preferences.set_preferences(actor, {preferences.IDLE_TIMEOUT_MINUTES: labels[chosen]})
    prompts.ok(f"Idle timeout set to {chosen.lower()}.")
    prompts.pause()


def _reset_settings(actor: Actor) -> None:
    if not prompts.ask_yes_no("Put every setting back to its default?"):
        raise prompts.Abort
    preferences.reset(actor)
    prompts.ok("Settings reset.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# User accounts
# ═════════════════════════════════════════════════════════════════════

def user_accounts(actor: Actor) -> None:
    """Grant and revoke apprenticeships access. Administrators only."""
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Who can sign in here", partial(_list_accounts, actor)),
        ("Grant access", partial(_grant, actor)),
        ("Change a role", partial(_change_role, actor)),
        ("Link a login to a record", partial(_link, actor)),
        ("Revoke access", partial(_revoke, actor)),
    ]
    prompts.run_menu("User Accounts", entries)


def _list_accounts(actor: Actor) -> None:
    rows = account_service.list_accounts(actor)
    prompts.title("Accounts with apprenticeships access")
    prompts.table(
        (("Username", 18), ("Name", 24), ("Role", 20), ("Linked to", 26),
         ("Active", 7), ("Must change pw", 15)),
        rows,
        lambda r: (r["username"], r["display_name"], r["role_label"],
                   r["linked_to"], r["is_active"], r["must_change_password"]),
        noun="account",
        empty="nobody has access yet",
    )
    unlinked = [
        r for r in rows
        if r["role"] in account_service.LINK_TARGETS and not r["linked_to"]
    ]
    if unlinked:
        prompts.note(
            f"\n  ! {len(unlinked)} account(s) have a role but no record behind it, so "
            "they sign in to empty screens. Link them."
        )
    prompts.pause()


def _grant(actor: Actor) -> None:
    candidates = account_service.list_grantable_accounts(actor)
    if not candidates:
        prompts.fail("Every active platform account already has access here.")
        prompts.note("Create the account in the platform first, then come back.")
        prompts.pause()
        return

    chosen = prompts.choose(
        "Account", candidates,
        render=lambda a: f"{a['username']} — {a['display_name']}",
    )
    role = _pick_role("Role in this system")
    result = account_service.grant_role(actor, chosen["username"], role)
    prompts.ok(f"{result['username']}: {result['detail']}.")

    if result["needs_link"]:
        prompts.note(
            f"A {config.ROLE_LABELS[role]} login is scoped by the record behind it. "
            "Link it now or the screens will be empty."
        )
        if prompts.ask_yes_no("Link it to a record now?", default=True):
            _link_one(actor, result["username"], role)
    prompts.pause()


def _change_role(actor: Actor) -> None:
    account = _pick_account(actor, "Account to change")
    prompts.note(f"{account['username']} currently holds {account['role_label']}.")
    role = _pick_role("New role", default=account["role"])
    result = account_service.grant_role(actor, account["username"], role)
    prompts.ok(f"{result['username']}: {result['detail']}.")
    if result["needs_link"]:
        prompts.note(
            "The new role is scoped by a different kind of record — link it, or the "
            "screens will be empty."
        )
        if prompts.ask_yes_no("Link it now?", default=True):
            _link_one(actor, result["username"], role)
    prompts.pause()


def _link(actor: Actor) -> None:
    account = _pick_account(actor, "Account to link")
    _link_one(actor, account["username"], account["role"])
    prompts.pause()


def _link_one(actor: Actor, username: str, role: str) -> None:
    candidates = account_service.link_candidates(actor, role)
    if not candidates:
        prompts.fail(
            f"There are no {account_service.LINK_TARGETS.get(role, 'record')}s to link to yet."
        )
        return
    chosen = prompts.choose(
        f"Which {account_service.LINK_TARGETS.get(role, 'record')}?",
        candidates,
        render=lambda c: (
            f"{c['label']} — {c['detail']}"
            + (f"  [currently {c['username']}]" if c["username"] else "")
        ),
    )
    if chosen["username"] and chosen["username"].lower() != username.lower():
        if not prompts.ask_yes_no(
            f"{chosen['label']} is already linked to {chosen['username']}. Move the "
            f"link to {username}?"
        ):
            raise prompts.Abort

    prompts.ok(account_service.link_to_record(actor, username, role, int(chosen["id"])))


def _revoke(actor: Actor) -> None:
    account = _pick_account(actor, "Account to revoke")
    prompts.note(
        "The records behind the login are untouched — an apprentice whose portal "
        "account is revoked is still an apprentice."
    )
    if not prompts.ask_yes_no(
        f"Revoke {account['username']}'s access to this system?"
    ):
        raise prompts.Abort
    account_service.revoke_access(actor, account["username"])
    prompts.ok(f"{account['username']} can no longer sign in here.")
    prompts.pause()


def _pick_account(actor: Actor, heading: str) -> dict:
    rows = account_service.list_accounts(actor)
    if not rows:
        prompts.fail("Nobody has access to this system yet.")
        raise prompts.Abort
    return prompts.choose(
        heading, rows,
        render=lambda r: (
            f"{r['username']} — {r['display_name']} ({r['role_label']}"
            + (f", {r['linked_to']}" if r["linked_to"] else ", not linked") + ")"
        ),
    )


def _pick_role(heading: str, *, default: str | None = None) -> str:
    labels = {config.ROLE_LABELS[role]: role for role in config.ROLES}
    chosen = prompts.choose_value(
        heading, tuple(labels),
        default=config.ROLE_LABELS.get(default or "") or None,
    )
    return labels[chosen]


_NO_ACCOUNT = (
    "This session is not backed by an account in the shared login database, so "
    "account changes are not available here."
)


def _is_linked(actor) -> bool:
    if actor.role == config.APPRENTICE:
        return actor.apprentice_id is not None
    if actor.role == config.EMPLOYER:
        return actor.employer_id is not None
    if actor.role == config.STAFF:
        return actor.staff_id is not None
    return True

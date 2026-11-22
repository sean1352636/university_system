"""User Accounts. Administrators only.

Granting a role and linking it to a record are one job, not two. A
login with the apprentice role and no apprentice record behind it signs
in successfully and then sees nothing — which reads as a broken system
rather than a half-finished setup — so this screen flags unlinked
accounts and offers the link straight after the grant.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.security import account_service

logger = logging.getLogger(__name__)

TITLE = "User Accounts"
SUBTITLE = "Who may sign in to the apprenticeships system, as what, and as whom."

_COLUMNS = (
    ("username", "Username", 150),
    ("name", "Name", 200),
    ("role", "Role", 160),
    ("linked", "Linked to", 220),
    ("active", "Active", 80),
    ("mustchange", "Must change password", 160),
)


def render(gui) -> None:
    """Draw the user accounts screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.is_admin:
        widgets.empty_state(
            frame, "Only a provider administrator may manage accounts."
        )
        return

    ok, rows = widgets.guard(lambda: account_service.list_accounts(gui.actor))
    if not ok:
        return
    rows = rows or []

    table = widgets.DataTable(frame, _COLUMNS)
    table.populate(
        rows,
        lambda r: (r["username"], r["display_name"], r["role_label"],
                   r["linked_to"], r["is_active"], r["must_change_password"]),
        identity=lambda r: r["username"],
        tag=lambda r: _tag(r),
        noun="account",
    )
    by_username = {r["username"]: r for r in rows}

    unlinked = [
        r for r in rows
        if r["role"] in account_service.LINK_TARGETS and not r["linked_to"]
    ]
    if unlinked:
        ttk.Label(
            frame,
            text=f"{len(unlinked)} account(s) hold a role with no record behind it, so "
                 "they sign in to empty screens. Select one and link it.",
            foreground=config.ERROR_FG, wraplength=760, justify="left",
        ).pack(anchor="w", pady=(6, 0))
    elif not rows:
        widgets.empty_state(
            frame,
            "Nobody has access to this system yet. Grant it to an existing platform "
            "account — accounts themselves are created in the platform, not here.",
        )

    def selected(action: str) -> dict | None:
        username = table.require_selection(action)
        return by_username.get(username) if username else None

    widgets.button_bar(frame, [
        ("Grant Access…", lambda: _grant(gui)),
        ("Change Role…", lambda: _change_role(gui, selected("change a role"))),
        ("Link to Record…", lambda: _link(gui, selected("link an account"))),
        ("Revoke Access", lambda: _revoke(gui, selected("revoke access"))),
    ])


def _tag(row: dict) -> str | None:
    """Colour the rows that need attention."""
    if not row["is_active"]:
        return "Red"
    if row["role"] in account_service.LINK_TARGETS and not row["linked_to"]:
        return "Amber"
    return None


# ═════════════════════════════════════════════════════════════════════
# Access
# ═════════════════════════════════════════════════════════════════════

def _grant(gui) -> None:
    ok, candidates = widgets.guard(
        lambda: account_service.list_grantable_accounts(gui.actor)
    )
    if not ok:
        return
    if not candidates:
        widgets.inform(
            "Every active platform account already has access here. New accounts are "
            "created in the platform, then granted a role from this screen.",
            title="Nothing to grant",
        )
        return

    labels = {f"{c['username']} — {c['display_name']}": c["username"] for c in candidates}
    roles = {config.ROLE_LABELS[role]: role for role in config.ROLES}
    fields = [
        {"key": "account", "label": "Account", "kind": "combo", "required": True,
         "options": list(labels)},
        {"key": "role", "label": "Role", "kind": "combo", "required": True,
         "options": list(roles), "value": config.ROLE_LABELS[config.STAFF],
         "help": "An apprentice, employer or tutor login is scoped by the record "
                 "behind it — you will be asked to link one next."},
    ]

    granted: dict[str, Any] = {}

    def save(values: dict[str, Any]) -> None:
        username = labels[values["account"]]
        role = roles[values["role"]]
        granted.update(account_service.grant_role(gui.actor, username, role))

    if not widgets.FormDialog(gui.root, "Grant access", fields, save).saved:
        return
    _after_grant(gui, granted)


def _change_role(gui, account: dict | None) -> None:
    if account is None:
        return
    roles = {config.ROLE_LABELS[role]: role for role in config.ROLES}
    fields = [
        {"key": "role", "label": "New role", "kind": "combo", "required": True,
         "options": list(roles),
         "value": config.ROLE_LABELS.get(account["role"], ""),
         "help": f"{account['username']} currently holds {account['role_label']}."},
    ]

    granted: dict[str, Any] = {}

    def save(values: dict[str, Any]) -> None:
        granted.update(
            account_service.grant_role(gui.actor, account["username"], roles[values["role"]])
        )

    if not widgets.FormDialog(
        gui.root, f"Change {account['username']}'s role", fields, save
    ).saved:
        return
    _after_grant(gui, granted)


def _after_grant(gui, granted: dict[str, Any]) -> None:
    """Offer the link the new role needs, then redraw."""
    if granted.get("needs_link") and widgets.confirm(
        f"{granted['username']} now holds "
        f"{config.ROLE_LABELS.get(granted['role'], granted['role'])}, which is scoped "
        "by the record behind it.\n\nLink it to a record now?",
        title="Link the account",
    ):
        _link_form(gui, granted["username"], granted["role"])
    gui.refresh()


def _revoke(gui, account: dict | None) -> None:
    if account is None:
        return
    if not widgets.confirm(
        f"Revoke {account['username']}'s access to the apprenticeships system?\n\n"
        "The records behind the login are untouched — an apprentice whose portal "
        "account is revoked is still an apprentice.",
        title="Revoke access",
    ):
        return
    ok, _ = widgets.guard(
        lambda: account_service.revoke_access(gui.actor, account["username"])
    )
    if ok:
        gui.refresh()


# ═════════════════════════════════════════════════════════════════════
# Linking
# ═════════════════════════════════════════════════════════════════════

def _link(gui, account: dict | None) -> None:
    if account is None:
        return
    if account["role"] not in account_service.LINK_TARGETS:
        widgets.inform(
            f"A {account['role_label']} login is not scoped to a single record, so "
            "there is nothing to link it to.",
            title="Nothing to link",
        )
        return
    _link_form(gui, account["username"], account["role"])
    gui.refresh()


def _link_form(gui, username: str, role: str) -> None:
    target = account_service.LINK_TARGETS.get(role, "record")
    ok, candidates = widgets.guard(
        lambda: account_service.link_candidates(gui.actor, role)
    )
    if not ok:
        return
    if not candidates:
        widgets.inform(f"There are no {target}s to link to yet.", title="Nothing to link")
        return

    labels: dict[str, dict] = {}
    for candidate in candidates:
        label = f"{candidate['label']} — {candidate['detail']}"
        if candidate["username"]:
            label += f"  [currently {candidate['username']}]"
        labels[label] = candidate

    fields = [
        {"key": "record", "label": target.capitalize(), "kind": "combo", "required": True,
         "options": list(labels),
         "help": f"Sets {username} as the login on that record. Every scope check "
                 "this role makes reads that link."},
    ]

    def save(values: dict[str, Any]) -> str:
        chosen = labels[values["record"]]
        if (
            chosen["username"]
            and chosen["username"].lower() != username.lower()
            and not widgets.confirm(
                f"{chosen['label']} is already linked to {chosen['username']}.\n\n"
                f"Move the link to {username}?",
                title="Reassign the link",
            )
        ):
            raise ValueError("Left as it was.")
        return account_service.link_to_record(
            gui.actor, username, role, int(chosen["id"])
        )

    dialog = widgets.FormDialog(gui.root, f"Link {username}", fields, save)
    if dialog.saved and dialog.result:
        widgets.inform(str(dialog.result), title="Linked")

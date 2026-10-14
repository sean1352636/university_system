"""Awaiting Signature — everything waiting for the signed-in user to sign.

A learning plan or an agreement document needs the apprentice, their
employer and the provider to sign it. Each signature covers the content
as it stood when given, so this list holds two kinds of row: things the
user has not signed yet, and things they did sign that have changed
since. The second kind comes first and is marked red — somebody may be
relying on an agreement that no longer carries the user's name.

The sign-off helpers at the bottom (the signatory table and the sign
dialog) are shared with the Documents and Learning Plan screens, so a
signature looks and behaves the same wherever it is given.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.records import signatures as sig_rules
from education_system.systems.apprenticeships.domain.records.signatures import (
    PendingSignature,
    SignOff,
)
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import signature_service

logger = logging.getLogger(__name__)

PENDING_COLUMNS = (
    ("what", "What", 120),
    ("title", "Title", 300),
    ("apprentice", "Apprentice", 200),
    ("category", "Category", 160),
    ("status", "Your signature", 190),
    ("progress", "Signed so far", 260),
)

SIGNOFF_COLUMNS = (
    ("role", "Signatory", 110),
    ("state", "State", 170),
    ("by", "Signed by", 150),
    ("when", "When", 150),
    ("statement", "Statement", 380),
)

_STATE_TEXT = {
    sig_rules.SIGNED: "Signed",
    sig_rules.INVALIDATED: "Changed since signing",
    sig_rules.AWAITING: "Not yet signed",
}


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(
        frame,
        "Awaiting Signature",
        subtitle="Learning plans and agreements waiting for your signature — including "
                 "anything you signed that has changed since, which needs signing again.",
    )
    signatory = sig_rules.signatory_for(gui.actor.role)
    if not gui.actor.can("signature.sign") or signatory is None:
        widgets.empty_state(frame, "Your role does not sign plans or agreements.")
        return

    ok, rows = widgets.guard(lambda: signature_service.awaiting_signature(gui.actor))
    if not ok:
        return
    changed = sum(1 for r in rows if r.status == sig_rules.INVALIDATED)
    widgets.kpi_row(frame, [
        ("Waiting for you", len(rows)),
        ("Changed since you signed", changed),
        ("You sign as", signatory),
    ])
    if not rows:
        widgets.empty_state(frame, "Nothing is waiting for your signature.")
        return

    by_key = {r.key: r for r in rows}
    table: widgets.DataTable | None = None

    def selected(action: str) -> PendingSignature | None:
        if table is None:
            return None
        key = table.require_selection(action)
        return by_key.get(key) if key else None

    def sign() -> None:
        row = selected("sign it")
        if row is not None and sign_dialog(
            gui, row.entity_type, row.entity_id, row.title, signatory=signatory
        ):
            render(gui)

    def who() -> None:
        row = selected("see who has signed")
        if row is not None:
            show_signoff(gui, row.signoff, on_signed=lambda: render(gui))

    widgets.button_bar(frame, [("Sign…", sign), ("Who has signed…", who)])
    table = widgets.DataTable(frame, PENDING_COLUMNS, on_activate=lambda _k: sign())
    table.populate(
        rows,
        lambda r: (
            r.what, r.title, r.apprentice_name, r.category,
            _STATE_TEXT.get(r.status, r.status), _progress(r.signoff),
        ),
        identity=lambda r: r.key,
        tag=lambda r: "Red" if r.status == sig_rules.INVALIDATED else "Amber",
        noun="item",
    )


# ═════════════════════════════════════════════════════════════════════
# Shared with the Documents and Learning Plan screens
# ═════════════════════════════════════════════════════════════════════

def signoff_table(parent: Any, signoff: SignOff) -> widgets.DataTable:
    """One row per required signatory: signed, changed since, or awaited."""
    table = widgets.DataTable(parent, SIGNOFF_COLUMNS, height=max(1, len(signoff.required)))
    table.populate(
        list(signoff.required),
        lambda role: _signoff_row(signoff, role),
        identity=lambda role: role,
        tag=lambda role: {
            sig_rules.SIGNED: "Green", sig_rules.INVALIDATED: "Red",
        }.get(signoff.state(role), "Amber"),
        noun="signatory",
    )
    return table


def sign_dialog(
    gui: Any, entity_type: str, entity_id: int, title: str, *, signatory: str | None = None
) -> bool:
    """Ask for the signature statement and sign. True if it was signed."""
    signatory = signatory or sig_rules.signatory_for(gui.actor.role)
    fields = [
        {"key": "statement", "label": "Statement", "kind": "text",
         "value": config.SIGNATURE_DEFAULT_STATEMENT,
         "help": "Recorded with your signature, word for word."},
    ]

    def save(values: dict[str, Any]) -> object:
        return signature_service.sign(
            gui.actor, entity_type, entity_id, statement=values.get("statement"),
        )

    dialog = widgets.FormDialog(
        gui.root, f"Sign as {signatory}", fields, save,
        intro=f"You are signing “{title}” as it stands now. If it is changed after you "
              "sign, your signature lapses and you will be asked to sign again.",
        save_label="Sign",
    )
    return dialog.saved


def show_signoff(gui: Any, signoff: SignOff, *, on_signed: Callable[[], None]) -> None:
    """A small window with the signatory table and, if it is theirs to give, Sign."""
    win = widgets.open_window(gui, f"Signatures — {signoff.title}", geometry="1000x360")
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    widgets.heading(body, signoff.title, subtitle=signoff.summary)
    signatory = sig_rules.signatory_for(gui.actor.role)

    def sign() -> None:
        if sign_dialog(gui, signoff.entity_type, signoff.entity_id, signoff.title,
                       signatory=signatory):
            win.destroy()
            on_signed()

    buttons: list[tuple[str, Callable[[], None]]] = [("Close", win.destroy)]
    if (gui.actor.can("signature.sign") and signatory in signoff.required
            and signoff.state(signatory) != sig_rules.SIGNED):
        buttons.insert(0, (f"Sign as {signatory}…", sign))
    widgets.button_bar(body, buttons)
    signoff_table(body, signoff)


def _signoff_row(signoff: SignOff, role: str) -> tuple:
    state = signoff.state(role)
    shown = signoff.valid_signature(role) or signoff.latest(role)
    return (
        role, _STATE_TEXT.get(state, state),
        shown.signed_by if shown else None,
        shown.signed_at if shown else None,
        shown.statement if shown else None,
    )


def _progress(signoff: SignOff) -> str:
    marks = {sig_rules.SIGNED: "✓", sig_rules.INVALIDATED: "changed", sig_rules.AWAITING: "—"}
    return ", ".join(f"{r} {marks.get(signoff.state(r), '')}" for r in signoff.required)

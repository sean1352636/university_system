"""Awaiting Signature: what is waiting for the signed-in user to sign.

Exposes: menu, show_signoff, sign.

A plan or agreement needs the apprentice, the employer and the provider
to sign it, and each signature covers the content as it stood when
given. So the list holds what the user has not signed yet, and — first,
because somebody may be relying on it — what they signed that has
changed since.

:func:`show_signoff` and :func:`sign` are shared with the Documents and
Learning Plan commands, so a signature is given the same way everywhere.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.records import signatures as sig_rules
from education_system.systems.apprenticeships.domain.records.signatures import (
    PendingSignature,
    SignOff,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.records import signature_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_PENDING_COLUMNS = (
    ("What", 13), ("Title", 32), ("Apprentice", 20), ("Your signature", 22),
    ("Signed so far", 36),
)
_SIGNOFF_COLUMNS = (("Signatory", 11), ("State", 22), ("Signed by", 16), ("When", 19),
                    ("Statement", 36))

_STATE_TEXT = {
    sig_rules.SIGNED: "Signed",
    sig_rules.INVALIDATED: "Changed since signing",
    sig_rules.AWAITING: "Not yet signed",
}


def menu(actor: Actor) -> None:
    signatory = sig_rules.signatory_for(actor.role)
    if not actor.can("signature.sign") or signatory is None:
        prompts.fail("Your role does not sign plans or agreements.")
        prompts.pause()
        return
    entries: list[tuple[str, Callable[[], None]]] = [
        ("What is waiting for my signature", partial(_list, actor)),
        ("Sign something", partial(_sign_one, actor)),
        ("Who has signed something", partial(_who, actor)),
    ]
    prompts.run_menu(f"Awaiting Signature — you sign as {signatory}", entries)


def show_signoff(signoff: SignOff) -> None:
    """Print one signatory per line: signed, changed since, or awaited."""
    prompts.note(f"\n{signoff.title}: {signoff.summary}")
    if not signoff.required:
        return
    prompts.table(
        _SIGNOFF_COLUMNS,
        list(signoff.required),
        lambda role: _signoff_row(signoff, role),
        noun="signatory",
    )


def sign(actor: Actor, entity_type: str, entity_id: int, title: str) -> None:
    """Confirm, take the statement, and sign."""
    signatory = sig_rules.signatory_for(actor.role)
    prompts.note(
        f"You are signing “{title}” as {signatory}, as it stands now. If it is changed "
        "afterwards your signature lapses and you will be asked to sign again."
    )
    statement = prompts.ask("Statement", default=config.SIGNATURE_DEFAULT_STATEMENT)
    if not prompts.ask_yes_no("Sign now?", default=True):
        raise prompts.Abort
    signature_service.sign(actor, entity_type, entity_id, statement=statement)
    prompts.ok(f"Signed as {signatory}.")


# ═════════════════════════════════════════════════════════════════════
# The list
# ═════════════════════════════════════════════════════════════════════

def _list(actor: Actor) -> None:
    rows = signature_service.awaiting_signature(actor)
    prompts.title("Waiting for your signature")
    _table(rows)
    prompts.pause()


def _sign_one(actor: Actor) -> None:
    row = _pick(actor, "What will you sign?")
    show_signoff(row.signoff)
    sign(actor, row.entity_type, row.entity_id, row.title)
    prompts.pause()


def _who(actor: Actor) -> None:
    row = _pick(actor, "Which one?")
    show_signoff(row.signoff)
    prompts.pause()


def _pick(actor: Actor, heading: str) -> PendingSignature:
    rows = signature_service.awaiting_signature(actor)
    if not rows:
        prompts.ok("Nothing is waiting for your signature.")
        raise prompts.Abort
    return prompts.choose(
        heading, rows,
        render=lambda r: (
            f"{r.what}: {r.title}"
            + (f" — {r.apprentice_name}" if r.apprentice_name else "")
            + (" (changed since you signed)" if r.status == sig_rules.INVALIDATED else "")
        ),
    )


def _table(rows: list[PendingSignature]) -> None:
    prompts.table(
        _PENDING_COLUMNS,
        rows,
        lambda r: (r.what, r.title, r.apprentice_name, _STATE_TEXT.get(r.status, r.status),
                   _progress(r.signoff)),
        noun="item",
        empty="nothing is waiting for your signature",
    )


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
    marks = {sig_rules.SIGNED: prompts.TICK, sig_rules.INVALIDATED: "changed",
             sig_rules.AWAITING: "—"}
    return ", ".join(f"{r} {marks.get(signoff.state(r), '')}" for r in signoff.required)

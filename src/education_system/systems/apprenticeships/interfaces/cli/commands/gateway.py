"""Gateway: the checkpoint between training and end-point assessment.

Exposes: menu, my_gateway, epao_menu.

Three menus for three sides of one decision. The provider evaluates and
requests; the apprentice sees what is still holding them up; the EPAO —
and only the EPAO — approves or rejects. That last split is not a menu
convenience: ``gateway.approve`` is withheld from the provider admin on
purpose, so :func:`menu` never offers it and :func:`epao_menu` never
offers the provider's verbs.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.application.assessments import gateway_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_QUEUE_COLUMNS = (
    ("Apprentice", 24), ("Programme", 24), ("Employer", 20), ("Tutor", 18),
    ("Gateway", 12), ("Requested", 12), ("Decided", 12),
)


# ═════════════════════════════════════════════════════════════════════
# The provider's view
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Gateway queue", partial(_queue, actor)),
        ("Check one apprentice", partial(_evaluate, actor)),
        ("Readiness report", partial(_readiness, actor)),
    ]
    if actor.can("gateway.request"):
        entries += [
            ("Request gateway", partial(_request, actor)),
            ("Record the employer's sign-off", partial(_sign_off, actor)),
        ]
    if actor.can("gateway.approve"):
        entries += [
            ("Approve a request", partial(_approve, actor)),
            ("Reject a request", partial(_reject, actor)),
        ]
    prompts.run_menu("Gateway", entries)


def _queue(actor: Actor) -> None:
    status = prompts.choose("Gateway status filter", config.GATEWAY_STATUSES, allow_blank=True)
    rows = gateway_service.gateway_queue(actor, status=status)
    prompts.title("Gateway queue")
    _queue_table(rows)
    prompts.pause()


def _evaluate(actor: Actor) -> None:
    summary = apprentices.pick(actor, heading="Apprentice to check")
    show_record(
        gateway_service.evaluate_gateway(actor, summary.apprentice.apprentice_id),
        summary.full_name,
    )
    prompts.pause()


def _readiness(actor: Actor) -> None:
    """Who could go to gateway now, and what is holding the rest up."""
    rows = gateway_service.readiness_report(actor)
    prompts.title("Gateway readiness")
    rows.sort(key=lambda r: (not r["is_ready"], -r["met"]))
    prompts.table(
        (("Apprentice", 24), ("Met", -5), ("Of", -4), ("Ready", 6), ("Outstanding", 52)),
        rows,
        lambda r: (r["apprentice"].full_name, r["met"], r["total"], r["is_ready"],
                   "; ".join(r["outstanding_labels"])),
        noun="apprentice",
    )
    ready = sum(1 for r in rows if r["is_ready"])
    prompts.note(f"\n  {ready} of {len(rows)} could be put forward today.")
    prompts.pause()


def _request(actor: Actor) -> None:
    """Put an apprentice forward, once everything is actually met."""
    summary = apprentices.pick(actor, heading="Apprentice to put forward")
    apprentice_id = summary.apprentice.apprentice_id
    record = gateway_service.evaluate_gateway(actor, apprentice_id)
    show_record(record, summary.full_name)

    if not record.is_ready:
        prompts.fail("Not everything is met yet, so the request would be refused.")
        prompts.note("Clear the outstanding requirements above and try again.")
        prompts.pause()
        return
    if not prompts.ask_yes_no(f"Put {summary.full_name} forward to the EPAO?"):
        raise prompts.Abort
    note = prompts.ask("Note for the audit trail")

    updated = gateway_service.request_gateway(actor, apprentice_id, note=note or None)
    prompts.ok(f"{summary.full_name} is now {updated.status} with the EPAO.")
    prompts.note("The EPAO decides from here — the provider cannot approve its own gateway.")
    prompts.pause()


def _sign_off(actor: Actor) -> None:
    """Record the one requirement no system can derive."""
    summary = apprentices.pick(actor, heading="Whose sign-off?")
    apprentice_id = summary.apprentice.apprentice_id
    record = gateway_service.evaluate_gateway(actor, apprentice_id)
    current = next(
        (c for c in record.checks if c.requirement_key == "employer_sign_off"), None
    )
    if current is not None:
        prompts.details([
            ("Currently", "Confirmed" if current.met else "Not confirmed"),
            ("Recorded by", current.checked_by),
            ("Recorded", current.checked_at),
            ("Note", current.evidence_note),
        ])

    confirmed = prompts.ask_yes_no(
        f"Does the employer confirm {summary.full_name} is ready for assessment?",
        default=True,
    )
    note = prompts.ask("Evidence note (who said so, and where)")

    gateway_service.set_employer_sign_off(
        actor, apprentice_id, confirmed=confirmed, note=note or None
    )
    prompts.ok(
        f"Employer sign-off {'confirmed' if confirmed else 'withdrawn'} for "
        f"{summary.full_name}."
    )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# The apprentice's view
# ═════════════════════════════════════════════════════════════════════

def my_gateway(actor: Actor) -> None:
    """What stands between the signed-in apprentice and their assessment."""
    apprentice_id = actor.apprentice_id
    if apprentice_id is None:
        prompts.fail("Your login is not linked to an apprentice record yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return

    record = gateway_service.evaluate_gateway(actor, apprentice_id)
    show_record(record, "My gateway")
    if record.is_ready and record.status == "Not Ready":
        prompts.note(
            "\n  Everything is met. Your tutor puts you forward from here — "
            "ask them to request gateway."
        )
    elif record.outstanding:
        prompts.note("\n  Still to do:")
        for check in record.outstanding:
            prompts.note(f"    · {check.label} — {check.detail or 'not met'}")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# The EPAO's view
# ═════════════════════════════════════════════════════════════════════

def epao_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Requests awaiting a decision", partial(_requests, actor)),
        ("Evaluate one request", partial(_evaluate, actor)),
    ]
    if actor.can("gateway.approve"):
        entries += [
            ("Approve", partial(_approve, actor)),
            ("Reject", partial(_reject, actor)),
        ]
    prompts.run_menu("Gateway Requests", entries)


def _requests(actor: Actor) -> None:
    rows = gateway_service.gateway_queue(actor, status="Requested")
    prompts.title("Gateway requests awaiting a decision")
    _queue_table(rows, empty="nothing is waiting on you")
    prompts.pause()


def _approve(actor: Actor) -> None:
    row = _pick_request(actor, "Request to approve")
    apprentice_id = int(row["apprentice_id"])
    show_record(
        gateway_service.evaluate_gateway(actor, apprentice_id), row["apprentice_name"]
    )
    if not prompts.ask_yes_no(f"Approve gateway for {row['apprentice_name']}?"):
        raise prompts.Abort
    note = prompts.ask("Decision note")

    gateway_service.approve_gateway(actor, apprentice_id, note=note or None)
    prompts.ok(f"Gateway approved for {row['apprentice_name']}.")
    prompts.note("Assessment methods can now be booked against this apprentice.")
    prompts.pause()


def _reject(actor: Actor) -> None:
    row = _pick_request(actor, "Request to send back")
    apprentice_id = int(row["apprentice_id"])
    show_record(
        gateway_service.evaluate_gateway(actor, apprentice_id), row["apprentice_name"]
    )
    prompts.note(
        "A rejected apprentice goes back to training, so say what the provider has "
        "to put right before re-requesting."
    )
    reason = prompts.ask("Reason", required=True)

    gateway_service.reject_gateway(actor, apprentice_id, reason=reason)
    prompts.ok(f"Gateway rejected for {row['apprentice_name']} — back to training.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Shared
# ═════════════════════════════════════════════════════════════════════

def show_record(record, name: str) -> None:
    """One apprentice against every gateway requirement."""
    prompts.title(f"Gateway — {name}")
    prompts.note(f"  {record.summary_line()}")
    prompts.note(f"  {prompts.bar(record.percent_complete)}")
    prompts.details([
        ("Status", record.status),
        ("Requested", record.requested_at),
        ("Requested by", record.requested_by),
        ("Decided", record.decided_at),
        ("Decided by", record.decided_by),
        ("Decision notes", record.decision_notes),
    ])
    prompts.table(
        (("Requirement", 44), ("Met", 5), ("How", 10), ("Detail", 40)),
        record.checks,
        lambda c: (c.label, prompts.TICK if c.met else prompts.CROSS,
                   "automatic" if c.automatic else "recorded", c.detail),
        noun="requirement",
    )


def _queue_table(rows: list, *, empty: str | None = None) -> None:
    prompts.table(
        _QUEUE_COLUMNS,
        rows,
        lambda r: (r.get("apprentice_name"), r.get("programme_title"),
                   r.get("employer_name"), r.get("tutor_name"),
                   r.get("gateway_status"), r.get("requested_at"), r.get("decided_at")),
        noun="apprentice",
        empty=empty,
    )


def _pick_request(actor: Actor, heading: str) -> dict:
    rows = gateway_service.gateway_queue(actor, status="Requested")
    if not rows:
        prompts.fail("There are no gateway requests waiting on a decision.")
        raise prompts.Abort
    return prompts.choose(
        heading, rows,
        render=lambda r: (
            f"{r.get('apprentice_name')} — {r.get('programme_title') or 'no programme'} "
            f"({r.get('employer_name') or 'no employer'}), requested "
            f"{r.get('requested_at') or 'date unknown'}"
        ),
    )

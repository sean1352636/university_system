"""The portfolio: evidence, the KSBs it claims, and the assessor's judgement.

Exposes: menu, my_menu.

The split between the two menus is the split the service enforces. An
apprentice gathers evidence and claims which KSBs it shows; an assessor
decides whether the claim lands. Neither menu offers the other's verbs,
so the one place the boundary is visible to a user is here rather than
in a refusal after they have typed everything in.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.services import portfolio_service, programme_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

# Where an assessment decision may land. The other two evidence statuses
# belong to the apprentice, not the assessor.
OUTCOMES: tuple[str, ...] = ("Accepted", "Referred", "Rejected")

_EVIDENCE_COLUMNS = (
    ("Title", 30), ("Type", 22), ("KSBs", 16), ("Status", 11),
    ("Submitted", 18), ("Assessed", 18),
)

_GAP_COLUMNS = (
    ("KSB", 7), ("Type", 11), ("Coverage", 12), ("Evidence", -9), ("Statement", 44),
)


# ═════════════════════════════════════════════════════════════════════
# The assessor's view
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Assessment queue", partial(_queue, actor)),
        ("List evidence", partial(_list, actor)),
        ("View one item", partial(_view, actor)),
        ("An apprentice's coverage", partial(_coverage, actor)),
        ("An apprentice's gaps", partial(_gaps, actor)),
    ]
    if actor.can("portfolio.assess"):
        entries += [
            ("Assess an item", partial(_assess, actor)),
            ("Work through the queue", partial(_work_queue, actor)),
            ("Set a KSB's coverage", partial(_set_coverage, actor)),
        ]
    if actor.can("portfolio.verify"):
        entries.append(("Sample an assessment (IQA)", partial(_verify, actor)))
    prompts.run_menu("Portfolios", entries)


def _queue(actor: Actor) -> None:
    rows = portfolio_service.assessment_queue(actor)
    names = apprentices.names(actor)
    prompts.title("Evidence awaiting assessment")
    prompts.table(
        (("Apprentice", 22), ("Title", 30), ("Type", 22), ("KSBs", 16), ("Submitted", 18)),
        rows,
        lambda e: (names.get(e.apprentice_id, f"#{e.apprentice_id}"), e.title,
                   e.evidence_type, ", ".join(e.ksb_codes), e.submitted_at),
        noun="item",
        empty="nothing is waiting on your judgement",
    )
    prompts.pause()


def _list(actor: Actor) -> None:
    summary = apprentices.pick(actor) if prompts.ask_yes_no("Filter to one apprentice?") else None
    status = prompts.choose("Status filter", config.EVIDENCE_STATUSES, allow_blank=True)
    kind = prompts.choose("Type filter", config.EVIDENCE_TYPES, allow_blank=True)

    rows = portfolio_service.list_evidence(
        actor,
        apprentice_id=summary.apprentice.apprentice_id if summary else None,
        status=status, evidence_type=kind,
    )
    prompts.title("Portfolio evidence")
    if summary is not None:
        _evidence_table(rows)
    else:
        names = apprentices.names(actor)
        prompts.table(
            (("Apprentice", 22), *_EVIDENCE_COLUMNS),
            rows,
            lambda e: (names.get(e.apprentice_id, f"#{e.apprentice_id}"), e.title,
                       e.evidence_type, ", ".join(e.ksb_codes), e.status,
                       e.submitted_at, e.assessed_at),
            noun="item",
        )
    prompts.pause()


def _view(actor: Actor) -> None:
    show_evidence(actor, _pick_evidence(actor, "Evidence to open"))
    prompts.pause()


def _assess(actor: Actor) -> None:
    evidence = _pick_evidence(actor, "Evidence to assess", queue_first=True)
    show_evidence(actor, evidence)
    _assess_one(actor, evidence)
    prompts.pause()


def _work_queue(actor: Actor) -> None:
    """Take each submitted item in turn."""
    rows = portfolio_service.assessment_queue(actor)
    if not rows:
        prompts.ok("Nothing is waiting on your judgement.")
        prompts.pause()
        return

    decided = 0
    prompts.title(f"Working through {len(rows)} submitted item(s)")
    for evidence in rows:
        prompts.rule()
        show_evidence(actor, evidence)
        if not prompts.ask_yes_no("Judge this one now?", default=True):
            continue
        _assess_one(actor, evidence)
        decided += 1
    prompts.ok(f"{decided} item(s) judged.")
    prompts.pause()


def _assess_one(actor: Actor, evidence) -> None:
    if not evidence.mappings:
        prompts.note(
            "This item is not mapped to any KSB, so accepting it moves nothing "
            "forward. Map it first, or refer it back."
        )
    outcome = prompts.choose_value("Outcome", OUTCOMES, default="Accepted")
    feedback = prompts.ask(
        "Feedback", required=outcome in ("Referred", "Rejected")
    )
    updated = portfolio_service.assess_evidence(
        actor, evidence.evidence_id, outcome=outcome, feedback=feedback or None
    )
    prompts.ok(f"“{updated.title}” marked {updated.status}.")


def _set_coverage(actor: Actor) -> None:
    """Re-judge how far one KSB claim on a piece of evidence goes."""
    evidence = _pick_evidence(actor, "Evidence to re-judge")
    if not evidence.mappings:
        prompts.fail("That evidence is not mapped to any KSB, so there is nothing to judge.")
        prompts.pause()
        return

    mapping = prompts.choose(
        "KSB claim", evidence.mappings,
        render=lambda m: f"{m.ksb_code} ({m.ksb_type}) — {m.coverage}: {m.ksb_description[:44]}",
    )
    coverage = prompts.choose_value(
        "Coverage", config.KSB_COVERAGE_LEVELS, default=mapping.coverage
    )
    note = prompts.ask("Assessor note")

    updated = portfolio_service.update_mapping(
        actor, mapping.map_id, coverage=coverage, note=note or None
    )
    prompts.ok(f"{updated.ksb_code} set to {updated.coverage}.")
    prompts.pause()


def _verify(actor: Actor) -> None:
    """Record an IQA sampling decision on an assessed item."""
    evidence = _pick_evidence(actor, "Assessed evidence to sample")
    show_evidence(actor, evidence)

    history = portfolio_service.list_verifications(actor, evidence.evidence_id)
    prompts.note("\nSampling history:")
    prompts.table(
        (("When", 20), ("Verifier", 20), ("Outcome", 20), ("Comments", 32)),
        history,
        lambda v: (v.get("verified_at"), v.get("verifier_name"), v.get("outcome"),
                   v.get("comments")),
        noun="sample",
        empty="never sampled",
    )

    outcome = prompts.ask("Sampling outcome (e.g. Agreed)", required=True)
    comments = prompts.ask("Comments")
    portfolio_service.verify_evidence(
        actor, evidence.evidence_id, outcome=outcome, comments=comments or None
    )
    prompts.ok(f"Sampled “{evidence.title}”: {outcome}.")
    prompts.pause()


def _coverage(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    show_coverage(actor, summary.apprentice.apprentice_id, summary.full_name)
    prompts.pause()


def _gaps(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    show_gaps(actor, summary.apprentice.apprentice_id, summary.full_name)
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# The apprentice's own portfolio
# ═════════════════════════════════════════════════════════════════════

def my_menu(actor: Actor) -> None:
    apprentice_id = actor.apprentice_id
    if apprentice_id is None:
        prompts.fail("Your login is not linked to an apprentice record yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return

    entries: list[tuple[str, Callable[[], None]]] = [
        ("My coverage", partial(_my_coverage, actor, apprentice_id)),
        ("My evidence", partial(_my_evidence, actor, apprentice_id)),
        ("What is still missing", partial(_my_gaps, actor, apprentice_id)),
    ]
    if actor.can("portfolio.upload"):
        entries += [
            ("Add evidence", partial(_add, actor)),
            ("Edit an item", partial(_my_edit, actor, apprentice_id)),
            ("Map an item to a KSB", partial(_map, actor, apprentice_id)),
            ("Remove a KSB claim", partial(_unmap, actor, apprentice_id)),
            ("Submit for assessment", partial(_submit, actor, apprentice_id)),
            ("Delete an item", partial(_my_delete, actor, apprentice_id)),
        ]
    prompts.run_menu("My Portfolio", entries)


def _my_coverage(actor: Actor, apprentice_id: int) -> None:
    show_coverage(actor, apprentice_id, "My portfolio")
    prompts.pause()


def _my_evidence(actor: Actor, apprentice_id: int) -> None:
    status = prompts.choose("Status filter", config.EVIDENCE_STATUSES, allow_blank=True)
    rows = portfolio_service.list_evidence(
        actor, apprentice_id=apprentice_id, status=status
    )
    prompts.title("My evidence")
    _evidence_table(rows)
    prompts.pause()


def _my_gaps(actor: Actor, apprentice_id: int) -> None:
    show_gaps(actor, apprentice_id, "My portfolio")
    prompts.pause()


def _add(actor: Actor) -> None:
    prompts.title("Add evidence")
    prompts.note(
        "Saved as a draft. Map it to the KSBs it shows, then submit it — nothing "
        "counts towards a KSB until an assessor has accepted it."
    )
    evidence = portfolio_service.add_evidence(actor, _evidence_payload(None))
    prompts.ok(f"Added “{evidence.title}”.")
    if prompts.ask_yes_no("Map it to a KSB now?", default=True):
        _map_one(actor, evidence)
    prompts.pause()


def _my_edit(actor: Actor, apprentice_id: int) -> None:
    evidence = _pick_own(actor, apprentice_id, "Evidence to edit", editable_only=True)
    prompts.title(f"Edit “{evidence.title}”")
    updated = portfolio_service.update_evidence(
        actor, evidence.evidence_id, _evidence_payload(evidence)
    )
    prompts.ok(f"Updated “{updated.title}”.")
    prompts.pause()


def _map(actor: Actor, apprentice_id: int) -> None:
    _map_one(actor, _pick_own(actor, apprentice_id, "Evidence to map"))
    prompts.pause()


def _map_one(actor: Actor, evidence) -> None:
    """Claim that a piece of evidence shows a KSB."""
    summary = _apprentice_of(actor, evidence)
    if summary is None or summary.apprentice.programme_id is None:
        prompts.fail("There is no programme on this record, so there are no KSBs to map to.")
        return

    claimed = {m.ksb_id for m in evidence.mappings}
    available = [
        k for k in programme_service.list_ksbs(actor, summary.apprentice.programme_id)
        if k.ksb_id not in claimed
    ]
    if not available:
        prompts.note("Every KSB on this standard is already claimed by this item.")
        return

    ksb = prompts.choose(
        "KSB this evidence shows", available,
        render=lambda k: f"{k.code} ({k.ksb_type}) — {k.description[:52]}",
    )
    levels = config.KSB_COVERAGE_LEVELS
    if not actor.can("portfolio.assess"):
        # Competent is the assessor's judgement, and it is the one the
        # gateway check reads. Not offering it beats a refusal after the
        # apprentice has picked it.
        levels = tuple(level for level in levels if level != "Competent")
        prompts.note("Your assessor decides whether a claim reaches 'Competent'.")
    coverage = prompts.choose_value("How far does it take the KSB?", levels, default="Developing")
    note = prompts.ask("Note")

    mapping = portfolio_service.map_to_ksb(
        actor, evidence.evidence_id, ksb.ksb_id, coverage=coverage, note=note or None
    )
    prompts.ok(f"“{evidence.title}” now claims {mapping.ksb_code} at {mapping.coverage}.")


def _unmap(actor: Actor, apprentice_id: int) -> None:
    evidence = _pick_own(actor, apprentice_id, "Evidence to unmap")
    if not evidence.mappings:
        prompts.fail("That item does not claim any KSB.")
        prompts.pause()
        return
    mapping = prompts.choose(
        "Claim to withdraw", evidence.mappings,
        render=lambda m: f"{m.ksb_code} — {m.coverage}: {m.ksb_description[:44]}",
    )
    if not prompts.ask_yes_no(f"Withdraw the claim on {mapping.ksb_code}?"):
        raise prompts.Abort

    portfolio_service.unmap_ksb(actor, mapping.map_id)
    prompts.ok(f"Withdrawn: {mapping.ksb_code}.")
    prompts.pause()


def _submit(actor: Actor, apprentice_id: int) -> None:
    evidence = _pick_own(actor, apprentice_id, "Evidence to submit", editable_only=True)
    if not evidence.mappings and not prompts.ask_yes_no(
        "This item does not claim any KSB, so accepting it would move nothing "
        "forward. Submit it anyway?"
    ):
        raise prompts.Abort

    updated = portfolio_service.submit_evidence(actor, evidence.evidence_id)
    prompts.ok(f"“{updated.title}” is with your assessor.")
    prompts.pause()


def _my_delete(actor: Actor, apprentice_id: int) -> None:
    evidence = _pick_own(actor, apprentice_id, "Evidence to delete", editable_only=True)
    if not prompts.ask_yes_no(f"Delete “{evidence.title}” and its KSB claims?"):
        raise prompts.Abort
    portfolio_service.delete_evidence(actor, evidence.evidence_id)
    prompts.ok("Deleted.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Shared
# ═════════════════════════════════════════════════════════════════════

def show_evidence(actor: Actor, evidence) -> None:
    """One item, its KSB claims and the decision on it."""
    prompts.title(evidence.title)
    prompts.details([
        ("Type", evidence.evidence_type),
        ("Status", evidence.status),
        ("Description", evidence.description),
        ("File", evidence.file_name),
        ("Submitted", evidence.submitted_at),
        ("Assessed", evidence.assessed_at),
        ("Assessor feedback", evidence.feedback),
    ])
    prompts.note("\nKSBs claimed:")
    prompts.table(
        (("KSB", 7), ("Type", 11), ("Coverage", 12), ("Statement", 40), ("Note", 26)),
        evidence.mappings,
        lambda m: (m.ksb_code, m.ksb_type, m.coverage, m.ksb_description, m.assessor_note),
        noun="claim",
        empty="none — accepting this would move nothing forward",
    )


def show_coverage(actor: Actor, apprentice_id: int, heading: str) -> None:
    """The whole portfolio: how far each KSB has got, and on what."""
    summary = portfolio_service.get_portfolio(actor, apprentice_id)
    prompts.title(heading)
    prompts.note(
        f"KSBs  {prompts.bar(summary.percent_competent)}  "
        f"{summary.competent_ksbs} / {summary.total_ksbs} competent"
    )
    prompts.details([
        ("Competent", summary.competent_ksbs),
        ("Developing", summary.developing_ksbs),
        ("Not started", summary.not_started_ksbs),
        ("Evidence items", len(summary.evidence)),
        ("Accepted", summary.accepted_count),
        ("Awaiting assessment", len(summary.awaiting_assessment)),
        ("Portfolio complete", summary.is_complete),
    ])
    prompts.table(
        _GAP_COLUMNS,
        summary.coverage,
        lambda c: (c.ksb.code, c.ksb.ksb_type, c.coverage, c.evidence_count,
                   c.ksb.description),
        noun="KSB",
    )


def show_gaps(actor: Actor, apprentice_id: int, heading: str) -> None:
    """Only what is still to be evidenced, worst first."""
    gaps = portfolio_service.coverage_gaps(actor, apprentice_id)
    prompts.title(f"Coverage gaps — {heading}")
    prompts.table(
        _GAP_COLUMNS,
        gaps,
        lambda c: (c.ksb.code, c.ksb.ksb_type, c.coverage, c.evidence_count,
                   c.ksb.description),
        noun="gap",
        empty="every KSB is competent — the portfolio gateway requirement is met",
    )


def _evidence_table(rows: list) -> None:
    prompts.table(
        _EVIDENCE_COLUMNS,
        rows,
        lambda e: (e.title, e.evidence_type, ", ".join(e.ksb_codes), e.status,
                   e.submitted_at, e.assessed_at),
        noun="item",
    )


def _pick_evidence(actor: Actor, heading: str, *, queue_first: bool = False):
    """Choose any evidence in scope, optionally offering the queue first."""
    rows = portfolio_service.assessment_queue(actor) if queue_first else []
    if not rows:
        rows = portfolio_service.list_evidence(actor)
    names = apprentices.names(actor)
    return prompts.choose(
        heading, rows,
        render=lambda e: (
            f"{names.get(e.apprentice_id, f'#{e.apprentice_id}')} — {e.title} "
            f"({e.evidence_type}, {e.status})"
        ),
    )


def _pick_own(actor: Actor, apprentice_id: int, heading: str, *, editable_only: bool = False):
    rows = portfolio_service.list_evidence(actor, apprentice_id=apprentice_id)
    if editable_only:
        rows = [e for e in rows if e.is_editable]
        if not rows:
            prompts.fail(
                "You have no draft or returned evidence. Submitted work is with the "
                "assessor and accepted work is locked, because the KSBs it covers "
                "depend on it."
            )
            raise prompts.Abort
    return prompts.choose(
        heading, rows,
        render=lambda e: f"{e.title} ({e.evidence_type}, {e.status})",
    )


def _apprentice_of(actor: Actor, evidence):
    from education_system.systems.apprenticeships.services import apprentice_service

    try:
        return apprentice_service.get_apprentice(actor, evidence.apprentice_id)
    except Exception:
        logger.debug("Could not load apprentice %s", evidence.apprentice_id, exc_info=True)
        return None


def _evidence_payload(evidence) -> dict[str, object]:
    return {
        "title": prompts.ask(
            "Title", default=evidence.title if evidence else "", required=True
        ),
        "evidence_type": prompts.choose_value(
            "Type", config.EVIDENCE_TYPES,
            default=evidence.evidence_type if evidence else None,
        ),
        "description": prompts.ask(
            "Description", default=(evidence.description if evidence else "") or ""
        ),
        "file_name": prompts.ask(
            "Attached file name", default=(evidence.file_name if evidence else "") or ""
        ),
    }

"""Operate the concurrent university half of degree apprenticeships."""

from __future__ import annotations

from functools import partial

from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.application.programmes import (
    degree_apprenticeship_service as service,
)
from education_system.systems.apprenticeships.application.security.access import Actor


def menu(actor: Actor) -> None:
    entries = [("Academic progress", partial(_progress, actor))]
    if actor.is_provider:
        entries.append(
            ("Reconciliation dashboard", partial(_reconciliation, actor))
        )
    if actor.can("programme.manage"):
        entries.insert(0, ("Map a degree programme", partial(_map, actor)))
    if actor.can("apprentice.manage"):
        entries.insert(1, ("Link an apprentice", partial(_link, actor)))
    prompts.run_menu("Degree apprenticeships", entries)


def _map(actor: Actor) -> None:
    from education_system.systems.apprenticeships.interfaces.cli.commands import programmes

    programme = programmes.pick(actor)
    mapping = service.map_programme(
        actor, programme.programme_id,
        prompts.ask_int("University degree programme id", required=True),
        credits_required=prompts.ask_float("Credits required"),
        integration_type=prompts.choose(
            "Integration type", tuple(sorted(service.INTEGRATION_TYPES)),
        ),
    )
    prompts.ok(
        f"Mapped {programme.reference} to university programme "
        f"{mapping.university_degree_program_id}."
    )
    prompts.pause()


def _link(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    link = service.link_learner(
        actor, summary.apprentice.apprentice_id,
        journey_id=prompts.ask("Shared journey id", required=True),
        university_student_id=prompts.ask(
            "Requested/existing university student id", required=True,
        ),
        institution_id=prompts.ask("Institution id"),
        start_date=prompts.ask("University start date (YYYY-MM-DD)"),
    )
    prompts.ok(
        f"University link {link.link_id} is {link.status.lower()}; "
        "admissions will validate it before enrolment."
    )
    prompts.pause()


def _progress(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    progress = service.academic_progress(
        actor, summary.apprentice.apprentice_id,
    )
    prompts.title(f"Academic progress — {summary.full_name}")
    prompts.details([
        ("University student", progress.get("university_student_id")),
        ("Degree", progress.get("degree_program_name")),
        ("Registration", progress.get("registration_status")),
        ("Credits", f"{progress.get('credits_earned', 0)} / "
                    f"{progress.get('credits_required', 0)}"),
        ("Modules completed", progress.get("modules_completed")),
        ("Academic standing", progress.get("academic_standing")),
        ("University gateway confirmed",
         bool(progress.get("university_gateway_confirmed"))),
        ("Degree outcome", progress.get("degree_outcome")),
    ])
    prompts.pause()


def _reconciliation(actor: Actor) -> None:
    rows = service.reconciliation_dashboard(actor)
    prompts.title("Degree-apprenticeship reconciliation")
    prompts.table(
        (("Apprentice", 24), ("University ID", 14), ("Link", 10),
         ("Reconciliation", 32), ("Last sync", 20), ("Issues", 42)),
        rows,
        lambda row: (
            row["apprentice_name"], row["university_student_id"],
            row["link_status"], row["reconciliation_state"],
            row["last_academic_sync_at"], "; ".join(row["issues"]),
        ),
        noun="degree-apprenticeship link",
    )
    prompts.pause()

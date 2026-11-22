"""The standards catalogue: programmes, their KSBs and their duties."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.programmes import versions
from education_system.systems.apprenticeships.domain.programmes.models import Programme
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.programmes import programme_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)


def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List standards", partial(_list, actor)),
        ("View a standard", partial(_view, actor)),
        ("Knowledge, skills and behaviours", partial(_ksb_menu, actor)),
        ("Occupational duties", partial(_duty_menu, actor)),
        ("Curriculum", partial(_curriculum_menu, actor)),
        ("Version history", partial(_versions, actor)),
    ]
    if actor.can("programme.manage"):
        entries += [
            ("Add a standard", partial(_create, actor)),
            ("Edit a standard", partial(_edit, actor)),
            ("Activate a standard", partial(_activate, actor)),
            ("Withdraw a standard", partial(_withdraw, actor)),
            ("Cut a new version", partial(_new_version, actor)),
        ]
    if actor.can("training.manage"):
        entries.append(("Apply the curriculum to an apprentice", partial(_apply, actor)))
    if actor.is_admin:
        entries.append(("Delete a standard", partial(_delete, actor)))
    prompts.run_menu("Programmes and KSBs", entries)


# ═════════════════════════════════════════════════════════════════════
# Standards
# ═════════════════════════════════════════════════════════════════════

def _list(actor: Actor) -> None:
    status = prompts.choose("Status filter", config.PROGRAMME_STATUSES, allow_blank=True)
    level = prompts.choose("Level filter", config.PROGRAMME_LEVELS,
                           render=lambda v: config.LEVEL_LABELS[v], allow_blank=True)
    search = prompts.ask("Reference or title contains")
    programmes = programme_service.list_programmes(
        actor, status=status, level=level, search=search or None
    )
    prompts.title("Apprenticeship standards")
    _table(programmes)
    prompts.pause()


def _view(actor: Actor) -> None:
    programme = pick(actor)
    breakdown = programme_service.ksb_breakdown(actor, programme.programme_id)
    prompts.title(f"{programme.reference} v{programme.version} {programme.title}")
    prompts.details([
        ("Version", programme.version),
        ("Level", programme.level_label),
        ("Pathway", programme.pathway),
        ("Duration", f"{programme.duration_months} months"),
        ("Funding band", f"{programme.funding_band} "
                         f"(max {prompts.money(programme.band_maximum)})"),
        ("Sector", programme.sector),
        ("Status", programme.status),
        ("Degree apprenticeship", programme.is_degree_apprenticeship),
        ("EPA methods", "; ".join(programme.epa_methods) or prompts.EMPTY),
        ("Knowledge", breakdown["Knowledge"]),
        ("Skills", breakdown["Skill"]),
        ("Behaviours", breakdown["Behaviour"]),
        ("Description", programme.description),
    ])

    prompts.note("\nOccupational duties:")
    _duty_table(programme_service.list_duties(actor, programme.programme_id))
    prompts.note("\nKnowledge, skills and behaviours:")
    _ksb_table(programme_service.list_ksbs(actor, programme.programme_id))
    prompts.pause()


def _create(actor: Actor) -> None:
    prompts.title("Add a standard")
    payload = {
        "reference": prompts.ask("Reference (e.g. ST0119)", required=True),
        "title": prompts.ask("Title", required=True),
        "level": prompts.choose_value(
            "Level", tuple(str(v) for v in config.PROGRAMME_LEVELS), default="3"
        ),
        "funding_band": prompts.ask_int("Funding band (1-15)", required=True),
        "duration_months": prompts.ask_int("Duration in months", default=12, required=True),
        "sector": prompts.ask("Sector"),
        "description": prompts.ask("Description"),
        "epa_methods": _pick_methods(),
    }
    created = programme_service.create_programme(actor, payload)
    prompts.ok(f"Added {created.reference} {created.title} as a draft.")
    prompts.note("Add its KSBs, then activate it before enrolling anyone.")
    prompts.pause()


def _edit(actor: Actor) -> None:
    programme = pick(actor)
    prompts.title(f"Edit {programme.reference}")
    payload = {
        "reference": prompts.ask("Reference", default=programme.reference, required=True),
        "title": prompts.ask("Title", default=programme.title, required=True),
        "level": prompts.choose_value(
            "Level", tuple(str(v) for v in config.PROGRAMME_LEVELS), default=str(programme.level)
        ),
        "funding_band": prompts.ask_int("Funding band", default=programme.funding_band),
        "duration_months": prompts.ask_int("Duration in months",
                                           default=programme.duration_months),
        "sector": prompts.ask("Sector", default=programme.sector or ""),
        "description": prompts.ask("Description", default=programme.description or ""),
    }
    if prompts.ask_yes_no("Change the EPA methods?"):
        payload["epa_methods"] = _pick_methods(current=programme.epa_methods)

    updated = programme_service.update_programme(actor, programme.programme_id, payload)
    prompts.ok(f"Updated {updated.reference} {updated.title}.")
    prompts.pause()


def _activate(actor: Actor) -> None:
    programme = pick(actor, status="Draft")
    updated = programme_service.activate_programme(actor, programme.programme_id)
    prompts.ok(f"{updated.reference} is active — apprentices may now be enrolled on it.")
    prompts.pause()


def _withdraw(actor: Actor) -> None:
    # Superseded versions too: once their last apprentice finishes they can close.
    programme = pick(actor, in_delivery=True)
    reason = prompts.ask("Reason for withdrawing it", required=True)
    updated = programme_service.withdraw_programme(actor, programme.programme_id, reason=reason)
    prompts.ok(f"{updated.reference} is closed to new enrolments.")
    prompts.pause()


def _delete(actor: Actor) -> None:
    programme = pick(actor, heading="Standard to delete")
    prompts.note("Deleting erases the standard along with its KSBs and duties.")
    if not prompts.ask_yes_no(f"Really delete {programme.reference}?"):
        raise prompts.Abort
    reason = prompts.ask("Reason for deletion", required=True)

    programme_service.delete_programme(actor, programme.programme_id, reason=reason)
    prompts.ok(f"Deleted {programme.reference} {programme.title}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Versions
# ═════════════════════════════════════════════════════════════════════

def _new_version(actor: Actor) -> None:
    programme = pick(actor, heading="Standard to revise")
    prompts.note(
        f"The KSBs, duties and curriculum of v{programme.version} are copied across. "
        f"v{programme.version} becomes Superseded: its apprentices stay on it, and new "
        "starts go onto the new version."
    )
    version = prompts.ask("New version", default=versions.next_version(programme.version),
                          required=True)
    reason = prompts.ask("What changed")
    created = programme_service.new_version(
        actor, programme.programme_id, version=version, reason=reason or None
    )
    prompts.ok(f"{created.reference} v{created.version} created ({created.status}).")
    prompts.pause()


def _versions(actor: Actor) -> None:
    programme = pick(actor)
    prompts.title(f"{programme.reference}: version history")
    prompts.table(
        (("Version", 8), ("Title", 34), ("Status", 11), ("Apprentices", -11),
         ("Created", 17)),
        programme_service.version_history(actor, programme.programme_id),
        lambda h: (h.programme.version, h.programme.title, h.programme.status,
                   h.apprentices, h.programme.created_at),
        noun="version",
    )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Curriculum
# ═════════════════════════════════════════════════════════════════════

def _curriculum_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List a standard's curriculum", partial(_list_modules, actor)),
    ]
    if actor.can("programme.manage"):
        entries += [
            ("Add a module", partial(_add_module, actor)),
            ("Edit a module", partial(_edit_module, actor)),
            ("Delete a module", partial(_delete_module, actor)),
        ]
    if actor.can("training.manage"):
        entries += [
            ("Apply the curriculum to an apprentice", partial(_apply, actor)),
            ("Apply the curriculum to everyone on a standard", partial(_apply_cohort, actor)),
        ]
    prompts.run_menu("Curriculum", entries)


def _list_modules(actor: Actor) -> None:
    programme = pick(actor)
    prompts.title(f"Curriculum — {programme.reference} v{programme.version} {programme.title}")
    _module_table(programme_service.list_modules(actor, programme.programme_id))
    prompts.pause()


def _add_module(actor: Actor) -> None:
    programme = pick(actor)
    created = programme_service.add_module(
        actor, programme.programme_id, _module_payload(None)
    )
    prompts.ok(f"Added {created.stage}: {created.title} to {programme.reference}.")
    prompts.pause()


def _edit_module(actor: Actor) -> None:
    _, module = _pick_module(actor)
    updated = programme_service.update_module(actor, module.module_id, _module_payload(module))
    prompts.ok(f"Updated {updated.title}.")
    prompts.pause()


def _delete_module(actor: Actor) -> None:
    _, module = _pick_module(actor)
    prompts.note("Plans it was already applied to keep their objective.")
    if not prompts.ask_yes_no(f"Delete {module.title}?"):
        raise prompts.Abort
    programme_service.delete_module(actor, module.module_id,
                                    reason=prompts.ask("Reason (optional)") or None)
    prompts.ok(f"Deleted {module.title}.")
    prompts.pause()


def _apply(actor: Actor) -> None:
    from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices

    summary = apprentices.pick(actor, heading="Whose learning plan?")
    result = programme_service.apply_curriculum(actor, summary.apprentice.apprentice_id)
    prompts.ok(f"{summary.full_name}'s learning plan: {result.summary}.")
    prompts.pause()


def _apply_cohort(actor: Actor) -> None:
    programme = pick(actor, in_delivery=True)
    if not prompts.ask_yes_no(
        f"Apply the curriculum to everyone on {programme.reference} v{programme.version}?"
    ):
        raise prompts.Abort
    results = programme_service.apply_curriculum_to_cohort(actor, programme.programme_id)
    added = sum(len(r.created) for r in results)
    prompts.ok(f"{len(results)} learning plan(s) checked; {added} objective(s) added.")
    prompts.pause()


def _pick_module(actor: Actor):
    programme = pick(actor)
    modules = programme_service.list_modules(actor, programme.programme_id)
    module = prompts.choose(
        "Module", modules, render=lambda m: f"{m.stage} #{m.position} — {m.title}"
    )
    return programme, module


def _module_payload(module) -> dict[str, object]:
    def current(attr: str) -> str:
        value = getattr(module, attr, None) if module is not None else None
        return "" if value is None else str(value)

    return {
        "title": prompts.ask("Module", default=current("title"), required=True),
        "stage": prompts.ask("Stage (e.g. Year 1)", default=current("stage") or "Year 1",
                             required=True),
        "position": prompts.ask("Position (blank puts it last)", default=current("position")),
        "ksb_codes": prompts.ask("KSBs (comma-separated)", default=current("ksb_codes")),
        "planned_hours": prompts.ask("Planned off-the-job hours",
                                     default=current("planned_hours") or "0"),
        "description": prompts.ask("Description", default=current("description")),
    }


def _module_table(modules: list) -> None:
    prompts.table(
        (("Stage", 10), ("#", -3), ("Module", 32), ("KSBs", 18), ("Hours", -6)),
        modules,
        lambda m: (m.stage, m.position, m.title, m.ksb_codes, m.planned_hours),
        noun="module",
        empty="no modules yet",
    )


# ═════════════════════════════════════════════════════════════════════
# KSBs
# ═════════════════════════════════════════════════════════════════════

def _ksb_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List a standard's KSBs", partial(_list_ksbs, actor)),
    ]
    if actor.can("programme.manage"):
        entries += [
            ("Add a KSB", partial(_add_ksb, actor)),
            ("Edit a KSB", partial(_edit_ksb, actor)),
            ("Delete a KSB", partial(_delete_ksb, actor)),
        ]
    prompts.run_menu("Knowledge, skills and behaviours", entries)


def _list_ksbs(actor: Actor) -> None:
    programme = pick(actor)
    ksb_type = prompts.choose("Type filter", config.KSB_TYPES, allow_blank=True)
    prompts.title(f"KSBs — {programme.reference} {programme.title}")
    _ksb_table(programme_service.list_ksbs(actor, programme.programme_id, ksb_type=ksb_type))
    prompts.pause()


def _add_ksb(actor: Actor) -> None:
    programme = pick(actor)
    payload = {
        "code": prompts.ask("Code (K1, S12, B3 …)", required=True),
        "description": prompts.ask("Statement", required=True),
        "duty_ref": prompts.ask("Duty reference (optional)"),
    }
    created = programme_service.add_ksb(actor, programme.programme_id, payload)
    prompts.ok(f"Added {created.code} ({created.ksb_type}) to {programme.reference}.")
    prompts.pause()


def _edit_ksb(actor: Actor) -> None:
    programme, ksb = _pick_ksb(actor)
    payload = {
        "code": prompts.ask("Code", default=ksb.code, required=True),
        "description": prompts.ask("Statement", default=ksb.description, required=True),
        "duty_ref": prompts.ask("Duty reference", default=ksb.duty_ref or ""),
    }
    updated = programme_service.update_ksb(actor, ksb.ksb_id, payload)
    prompts.ok(f"Updated {updated.code} on {programme.reference}.")
    prompts.pause()


def _delete_ksb(actor: Actor) -> None:
    _, ksb = _pick_ksb(actor)
    prompts.note("Evidence mapped to it survives — it simply covers one thing fewer.")
    if not prompts.ask_yes_no(f"Delete {ksb.code}?"):
        raise prompts.Abort
    reason = prompts.ask("Reason (optional)")

    programme_service.delete_ksb(actor, ksb.ksb_id, reason=reason or None)
    prompts.ok(f"Deleted {ksb.code}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Occupational duties
# ═════════════════════════════════════════════════════════════════════

def _duty_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List a standard's duties", partial(_list_duties, actor)),
    ]
    if actor.can("programme.manage"):
        entries += [
            ("Add a duty", partial(_add_duty, actor)),
            ("Edit a duty", partial(_edit_duty, actor)),
            ("Delete a duty", partial(_delete_duty, actor)),
        ]
    prompts.run_menu("Occupational duties", entries)


def _list_duties(actor: Actor) -> None:
    programme = pick(actor)
    prompts.title(f"Duties — {programme.reference} {programme.title}")
    _duty_table(programme_service.list_duties(actor, programme.programme_id))
    prompts.pause()


def _add_duty(actor: Actor) -> None:
    programme = pick(actor)
    payload = {
        "code": prompts.ask("Duty code (e.g. D1)", required=True),
        "description": prompts.ask("Duty", required=True),
    }
    created = programme_service.add_duty(actor, programme.programme_id, payload)
    prompts.ok(f"Added {created.code} to {programme.reference}.")
    prompts.pause()


def _edit_duty(actor: Actor) -> None:
    _, duty = _pick_duty(actor)
    payload = {
        "code": prompts.ask("Duty code", default=duty.code, required=True),
        "description": prompts.ask("Duty", default=duty.description, required=True),
    }
    programme_service.update_duty(actor, duty.duty_id, payload)
    prompts.ok(f"Updated duty {payload['code']}.")
    prompts.pause()


def _delete_duty(actor: Actor) -> None:
    _, duty = _pick_duty(actor)
    prompts.note("KSBs referencing it keep the reference text — it is a label, not a key.")
    if not prompts.ask_yes_no(f"Delete duty {duty.code}?"):
        raise prompts.Abort

    programme_service.delete_duty(actor, duty.duty_id)
    prompts.ok(f"Deleted duty {duty.code}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Pickers and tables
# ═════════════════════════════════════════════════════════════════════

def pick(actor: Actor, *, heading: str = "Standard", **filters: object) -> Programme:
    """Choose one standard from the catalogue."""
    return prompts.choose(
        heading,
        programme_service.list_programmes(actor, **filters),
        render=lambda p: f"{p.reference} v{p.version} {p.title} — Level {p.level}, {p.status}",
    )


def _pick_ksb(actor: Actor):
    programme = pick(actor)
    ksbs = programme_service.list_ksbs(actor, programme.programme_id)
    ksb = prompts.choose(
        "KSB", ksbs, render=lambda k: f"{k.code} ({k.ksb_type}) — {k.description[:60]}"
    )
    return programme, ksb


def _pick_duty(actor: Actor):
    programme = pick(actor)
    duties = programme_service.list_duties(actor, programme.programme_id)
    duty = prompts.choose(
        "Duty", duties, render=lambda d: f"{d.code} — {d.description[:60]}"
    )
    return programme, duty


def _pick_methods(current: list[str] | None = None) -> list[str]:
    """Collect the EPA plan one method at a time.

    A standard is assessed by two or three methods, so the list is built
    by repeated selection rather than by asking for a comma-separated
    string nobody can be sure they typed correctly.
    """
    chosen: list[str] = list(current or [])
    while True:
        prompts.note(f"EPA methods so far: {', '.join(chosen) or prompts.EMPTY}")
        method = prompts.choose("Add an EPA method", config.EPA_METHODS, allow_blank=True)
        if method is None:
            return chosen
        if method not in chosen:
            chosen.append(method)


def _table(programmes: list[Programme]) -> None:
    prompts.table(
        (("Reference", 10), ("Ver", 5), ("Title", 32), ("Lvl", -4), ("Months", -7),
         ("Band", -5), ("Status", 11), ("EPA methods", 28)),
        programmes,
        lambda p: (p.reference, p.version, p.title, p.level, p.duration_months,
                   p.funding_band, p.status, ", ".join(p.epa_methods)),
        noun="standard",
    )


def _ksb_table(ksbs: list) -> None:
    prompts.table(
        (("Code", 6), ("Type", 11), ("Duty", 6), ("Statement", 60)),
        ksbs,
        lambda k: (k.code, k.ksb_type, k.duty_ref, k.description),
        noun="KSB",
    )


def _duty_table(duties: list) -> None:
    prompts.table(
        (("Code", 8), ("Duty", 72)),
        duties,
        lambda d: (d.code, d.description),
        noun="duty",
    )

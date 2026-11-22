"""Research Office console menu: dashboard, projects, ethics, grants,
outputs, REF, IP, integrity and people — the same rules as the Research
Portal (``university/application/research/``), which check permissions.

Students get the dashboard and ethics only; REF is for REF leads and the
research office.
"""

from __future__ import annotations

from education_system.systems.university.domains.research.interfaces.cli.research.research_office import (  # noqa: E501
    ethics,
    grants,
    ip,
    outputs,
    people,
    projects,
)
from education_system.systems.university.domains.research.interfaces.cli.research.research_office._io import (  # noqa: E501
    menu,
    run,
)


def _who(auth):
    from education_system.systems.university.application.research import access as ra
    user = getattr(auth, "current_user", None) if auth is not None else None
    if not user:
        print("You must be signed in to use the Research Office.")
        return None
    who = run(ra.from_user, user)
    if not isinstance(who, ra.Researcher):      # run() turns "nobody" into True
        print("You must be signed in to use the Research Office.")
        return None
    return who


def _areas(who):
    areas = [("Dashboard", people.dashboard_menu), ("Ethics", ethics.ethics_menu)]
    if not who.is_staff:
        return areas
    areas[1:1] = [("Projects", projects.projects_menu)]
    areas += [("Grants", grants.grants_menu), ("Outputs", outputs.outputs_menu)]
    if who.leads_ref():
        areas.append(("REF", outputs.ref_menu))
    areas += [("IP & commercialisation", ip.ip_menu), ("Integrity", people.integrity_menu),
              ("People", people.people_menu)]
    return areas


def display_research_office_menu(auth):
    """Top-level Research Office menu."""
    who = _who(auth)
    if who:
        menu("RESEARCH OFFICE", _areas(who), who)


def display_research_grants_menu(auth):
    """Straight to the grants menu (staff only)."""
    who = _who(auth)
    if not who:
        return
    if not who.is_staff:
        print("Research grants are for staff.")
        return
    grants.grants_menu(who)


__all__ = ["display_research_office_menu", "display_research_grants_menu"]

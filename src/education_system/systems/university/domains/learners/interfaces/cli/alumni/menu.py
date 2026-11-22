"""The Alumni Relations console menu.

Who sees what comes from ``alumni_access``: the alumni office gets
everything; fundraising, the mentoring coordinator and moderators get their
own areas; alumni get their own account; current students get their
mentoring. Anyone else is refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from education_system.systems.university.application.alumni import access as aa
from education_system.systems.university.domains.learners.interfaces.cli.alumni import (
    _io,
    community,
    giving,
    office,
    self_service,
)


@dataclass
class Context:
    who: aa.AlumniUser
    auth: Any


def _current_user(auth):
    user = getattr(auth, "current_user", None) if auth is not None else None
    if user:
        return user
    try:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        shared = get_auth()
        return getattr(shared, "current_user", None) if shared else None
    except Exception:
        return None


def has_access(who) -> bool:
    return who is not None and (who.is_staff_role or who.is_alumnus or who.is_student)


def items_for(ctx) -> list:
    who = ctx.who
    items = []
    if who.is_alumnus:
        items.append(("My alumni account", lambda: self_service.alumnus_menu(ctx)))
    if who.is_student and not who.is_alumnus:
        items.append(("My mentoring", lambda: self_service.student_menu(ctx)))
    if who.is_office:
        items += [("Alumni records", lambda: office.records_menu(ctx)),
                  ("Newsletters", lambda: office.newsletter_menu(ctx)),
                  ("Chapters", lambda: community.chapters_menu(ctx))]
    if who.is_fundraiser:
        items.append(("Giving", lambda: giving.giving_menu(ctx)))
    if who.is_coordinator:
        items.append(("Mentoring", lambda: community.mentoring_menu(ctx)))
    if who.is_moderator:
        items.append(("Moderation", lambda: community.moderation_menu(ctx)))
    if who.is_office:
        items.append(("Roles and audit", lambda: office.roles_menu(ctx)))
    items.append(("Alumni directory", lambda: office.directory_search(ctx)))
    if who.is_alumnus or who.is_staff_role:
        items.append(("Community (classic: events, jobs, forum…)",
                      lambda: community.classic_menu(ctx)))
    return items


def display_alumni_relations_menu(auth=None) -> None:
    """Entry point from the main university menu."""
    user = _current_user(auth)
    if not user:
        print("\nYou must be logged in to use Alumni Relations.")
        return
    who = _io.read(aa.from_user, user)
    if not has_access(who):
        print("\nAlumni Relations is for alumni, current students and alumni-office staff. "
              "Ask the alumni office for a role if you need one.")
        return
    _io.menu("Alumni Relations", items_for(Context(who=who, auth=auth)))


display_alumni_menu = display_alumni_relations_menu

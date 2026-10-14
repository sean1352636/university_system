"""Shared context for student union helpers."""

from __future__ import annotations

import os
import random
from education_system.systems.university.infrastructure.database.db import sqlite3
import string
from datetime import datetime, timedelta
from typing import Optional

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.database.db import DatabaseManager, get_connection
try:
    from education_system.systems.university.infrastructure.email import send_confirmation_email
except Exception:  # pragma: no cover - optional dependency
    def send_confirmation_email(*_args, **_kwargs):
        return False

try:
    from education_system.systems.university.domains.academics.domain.services.academic_calendar.calendar_core import AcademicCalendarManager
except Exception:  # pragma: no cover - optional dependency
    AcademicCalendarManager = None

auth: Optional[UserAuth] = None

# ---------------------------------------------------------------------------
# Cross-module pass-throughs
# ---------------------------------------------------------------------------
#
# These names exist so one Student Union module can reach another without an
# import cycle. They used to be hand-written stubs that took no arguments and
# forwarded none, while every real caller passes `(student_id, cursor, conn)`
# or `(auth_obj)` — so each one died with "takes 0 positional arguments but N
# were given" the moment a user picked that screen. Several also pointed at a
# module that imports the same name straight back from here, which would have
# recursed, and a few named a module that has no such function at all.
#
# The table below records where each name is *actually* implemented; the
# adapter forwards the caller's arguments to it. Legacy callers that still
# pass an `auth_obj` to a screen that now reads the module-level `auth` get
# that extra argument dropped rather than a TypeError.

_DELEGATES = {
    "engagement_trend_analysis": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.community",
    "member_retention_insights": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.community",
    "event_popularity_predictions": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.event_management",
    "generate_advanced_analytics": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.analytics",
    "learning_analytics_dashboard": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.analytics",
    "auto_award_points": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.points",
    "check_and_award_badges": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.rewards",
    "manage_book_clubs": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.community",
    "manage_shared_resources": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.support",
    "knowledge_sharing_sessions": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.knowledge_sharing",
    "manage_learning_integration": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.events",
    "manage_community_engagement": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.community",
    "display_club_menu": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.student_union_core",
    "display_event_menu": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.student_union_core",
    "display_facility_menu": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.student_union_core",
    "display_election_menu": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.student_union_core",
    "display_admin_menu": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.student_union_core",
    "manage_engagement_rewards": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.rewards",
    "manage_interclub_competitions": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.competitions",
    "manage_peer_support_system": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.support",
    "manage_academic_support": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.support",
    "manage_mentorship_system": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.mentorship",
    "manage_equipment_system": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.facilities.facility_management",
    "manage_green_initiatives": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.sustainability",
    "manage_virtual_events": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.event_management",
    "manage_enhanced_voting": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.services.voting",
    "manage_support_groups_admin": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.admin_management",
    "generate_support_reports": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.admin_management",
    "manage_sustainable_events": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.event_management",
    "generate_environmental_reports": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.admin_management",
    "view_elections_with_campaigns": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "view_elections": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "view_candidate_profiles": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "view_election_results": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "election_accessibility_features": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "nominate_for_election": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "vote_in_election": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "submit_campaign_materials": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "track_campaign_expenses": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "set_up_election": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "monitor_campaign_compliance": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "election_security_audit": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.elections.election_management",
    "export_voting_configuration": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.admin_management",
    "import_voting_configuration": "education_system.systems.university.domains.pastoral.domain.student_life.student_union.administration.admin_management",
}


def _resolve(name):
    """Import and return the module that implements ``name``."""
    import importlib
    return getattr(importlib.import_module(_DELEGATES[name]), name)


def _call(name, args, kwargs):
    """Call the real implementation, tolerating superseded call styles."""
    import inspect

    impl = _resolve(name)
    try:
        params = inspect.signature(impl).parameters
    except (TypeError, ValueError):       # pragma: no cover - builtins
        return impl(*args, **kwargs)

    if not any(p.kind is p.VAR_POSITIONAL for p in params.values()):
        accepts = sum(
            1 for p in params.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        )
        if len(args) > accepts:
            # e.g. display_club_menu(auth) against a screen that now reads
            # the module-level auth: drop what it cannot take.
            args = args[:accepts]
    if not any(p.kind is p.VAR_KEYWORD for p in params.values()):
        kwargs = {k: v for k, v in kwargs.items() if k in params}
    return impl(*args, **kwargs)


def _make_delegate(name):
    def delegate(*args, **kwargs):
        return _call(name, args, kwargs)
    delegate.__name__ = name
    delegate.__qualname__ = name
    delegate.__doc__ = f"Delegates to ``{_DELEGATES[name]}.{name}``."
    return delegate


for _name in _DELEGATES:
    globals()[_name] = _make_delegate(_name)
del _name

__all__ = ["auth", *sorted(_DELEGATES)]

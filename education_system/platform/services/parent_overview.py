"""Unified parent view — every child, every system, one login.

Builds on the existing :class:`ParentChildLinkService` (parent ↔ child
links) and the canonical journey registry so a parent with children in,
say, nursery *and* secondary sees both — each child rendered as the full
cross-system :func:`student_view.build_overview`. Five portals collapse
into one.

:func:`link_parent_across_journey` links a parent to a child in **every**
system that child's journey touches in one call, so a single link follows
the child as they progress instead of needing a new link per phase.
"""

from __future__ import annotations

import logging

from education_system.platform.identity.auth.db import AUTH_DB_FILE
from education_system.platform.cross_system import identity_service, student_view
from education_system.platform.services.parent_child_link import (
    ParentChildLinkService,
)

logger = logging.getLogger(__name__)


def _link_service(auth_db: str | None) -> ParentChildLinkService:
    return ParentChildLinkService(auth_db or str(AUTH_DB_FILE))


def get_children_overviews(parent_user_id: int, *,
                           auth_db: str | None = None) -> list[dict]:
    """Return a cross-system overview for each child linked to a parent.

    De-duplicates on canonical journey so a child linked in two systems is
    shown once with their whole history.
    """
    svc = _link_service(auth_db)
    seen_journeys: set[str] = set()
    overviews: list[dict] = []
    for link in svc.get_children(parent_user_id):
        system = link["child_system_key"]
        sid = link["child_student_id"]
        row = identity_service.find_by_student(system, sid, db_path=auth_db)
        if row is not None:
            jid = row["journey_id"]
            if jid in seen_journeys:
                continue
            seen_journeys.add(jid)
            ov = student_view.build_overview(jid, auth_db=auth_db)
        else:
            # No canonical journey yet — fall back to a single-system view.
            ov = student_view.build_overview_for_student(
                system, sid, auth_db=auth_db)
        ov["relationship"] = link.get("relationship", "parent")
        overviews.append(ov)
    return overviews


def link_parent_across_journey(parent_user_id: int, journey_id: str, *,
                               relationship: str = "parent",
                               auth_db: str | None = None) -> list[dict]:
    """Link a parent to a child in *every* system the journey touches.

    Returns the list of link records created/reactivated.
    """
    journey = identity_service.get(journey_id, db_path=auth_db)
    if journey is None:
        raise ValueError(f"No journey {journey_id}")
    svc = _link_service(auth_db)
    created = []
    for system, (_pk, id_col) in identity_service.SYSTEM_SLOTS.items():
        sid = journey.get(id_col)
        if not sid:
            continue
        created.append(svc.link_child(
            parent_user_id=parent_user_id, child_student_id=sid,
            child_system_key=system, relationship=relationship))
    logger.info("Linked parent %s across %d system(s) of journey %s",
                parent_user_id, len(created), journey_id)
    return created


__all__ = ["get_children_overviews", "link_parent_across_journey"]

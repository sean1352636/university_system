"""Cross-system messaging for the Nursery System (CLI).

Thin adapter onto the shared ``InterSystemMessagingService`` CLI so nursery
staff can email — and be emailed by — staff in the university, sixth-form,
secondary and primary systems. The shared loop keys everyone by their
``auth.db`` user id, so messages line up across systems.

The shared ``run`` reads the sender's system from ``auth['system_key']``; the
shared nursery login doesn't carry that key, so we pass an explicit auth dict
stamped with ``"nursery"``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

NURSERY_SYSTEM_KEY = "nursery"


def open_manager(auth=None) -> None:
    from education_system.shared.messaging import cross_system_cli as shared_cli

    cu = getattr(auth, "current_user", None) or {}
    auth_dict = {
        "user_id": cu.get("user_id") or cu.get("id"),
        "display_name": cu.get("display_name") or cu.get("username", ""),
        "system_key": NURSERY_SYSTEM_KEY,
    }
    if not auth_dict["user_id"]:
        print("  Cross-system email needs a signed-in account — please log in "
              "via run.py.")
        return
    logger.debug("Opening cross-system CLI for nursery user %s",
                 auth_dict["user_id"])
    shared_cli.run(auth=auth_dict)


_DISPATCH = {"Cross-System Email": open_manager}


def dispatch(label: str, auth=None) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    handler(auth=auth)
    return True

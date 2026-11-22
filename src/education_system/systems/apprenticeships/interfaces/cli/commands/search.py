"""Search everything you can see.

Exposes: menu.
"""

from __future__ import annotations

import logging

from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.workspace import search_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (("Kind", 16), ("Match", 36), ("Details", 60))


def menu(actor: Actor) -> None:
    """Search repeatedly until a blank query."""
    prompts.title("Search")
    prompts.note("Names, references or phrases. Leave blank to go back.")
    while True:
        query = prompts.ask("\nSearch for")
        if not query.strip():
            return
        results = search_service.search(actor, query)
        prompts.table(
            _COLUMNS, results, lambda r: (r.kind, r.title, r.subtitle),
            noun="result", empty=f"nothing you can see matches “{query.strip()}”",
        )

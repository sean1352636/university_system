"""Academic integrity CLI: students, module staff and integrity officers.
Rules live in ``university/application/integrity/plagiarism_checks`` and
``integrity_*``; this package only asks questions and prints answers."""

from education_system.systems.university.domains.integrity.interfaces.cli.integrity.menu import (  # noqa: E501
    cases_menu,
    integrity_menu,
)

__all__ = ["integrity_menu", "cases_menu"]

"""Academic integrity from the university CLI shell (AI tools, the
plagiarism menu entry). The menu itself belongs to the academics slice."""

from education_system.systems.university.domains.integrity.interfaces.cli.integrity import (
    integrity_menu,
)

__all__ = ["integrity_menu"]

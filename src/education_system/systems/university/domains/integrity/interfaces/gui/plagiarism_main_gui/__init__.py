"""Academic Integrity (similarity checks, review, cases and appeals).

:func:`open_integrity_window` opens the role-aware window for the signed-in
person; the rules are in ``university/application/integrity/`` and
``integrity_*``.
"""

from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.launcher import (  # noqa: E501
    integrate_plagiarism_checker_with_main,
    launch_gui_from_main_system,
    main,
)
from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.window import (  # noqa: E501
    IntegrityWindow,
    open_integrity_window,
    signed_in_user,
)


__all__ = [
    "IntegrityWindow",
    "integrate_plagiarism_checker_with_main",
    "launch_gui_from_main_system",
    "main",
    "open_integrity_window",
    "signed_in_user",
]

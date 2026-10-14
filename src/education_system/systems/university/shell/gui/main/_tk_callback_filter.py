"""Tk destroy-race filters — moved to the platform.

The implementation now lives at
``education_system.platform.delivery.gui.tk_callback_filter``. It is a
generic Tk helper with no university coupling, and it sat here only for
historical reasons — which made it a problem twice over:

* **A circular import.** Reaching it pulled in this package's
  ``__init__``, which imports ``main_gui``, which imports back into
  ``domains.learners...student_crud_gui`` — so loading that package
  before the shell raised ``ImportError: cannot import name
  'create_student_dialog' ... (most likely due to a circular import)``.
* **A boundary violation.** 15 of its importers are domain modules, and
  a domain must never import the shell.

Kept as a re-export so any straggler import keeps resolving.
"""

from __future__ import annotations

from education_system.platform.delivery.gui.tk_callback_filter import (  # noqa: F401
    install_clean_close,
    install_destroy_race_filter,
)

__all__ = ["install_clean_close", "install_destroy_race_filter"]

"""The errors every Secondary School rule raises when it refuses.

One set of classes for the whole system, so a screen can catch them once
(``ui.gui.components.widgets.ERRORS``) whichever module refused. Modules keep their own
names for them (``BH.ValidationError`` is this ``ValidationError``).
"""

from __future__ import annotations


class ValidationError(ValueError):
    """The submitted details break one or more rules.

    ``problems`` lists every problem found, so a form can show them all at
    once rather than one per attempt.
    """

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


class PermissionDenied(PermissionError):
    """The signed-in person may not do that."""


class NotFound(LookupError):
    """No record with that id."""

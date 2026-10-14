"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ModuleTab(ttk.Frame):
    """Base class for each feature tab."""
    def __init__(self, parent, db, app):
        super().__init__(parent, style="TFrame")
        self.db = db
        self.app = app
        self._build()
        self.refresh()

    def _build(self):
        raise NotImplementedError

    def refresh(self):
        raise NotImplementedError

    def people_choices(self, role=None):
        """Choices for a person field, from the university's own registers.

        Keys are composite (``"staff:12"``) because staff, students and
        external examiners live in three separate tables with independent
        primary keys. See ``university_research_parts.people``.
        """
        return person_choices(self.db, role)

    def person_name(self, key):
        return person_name(self.db, key)

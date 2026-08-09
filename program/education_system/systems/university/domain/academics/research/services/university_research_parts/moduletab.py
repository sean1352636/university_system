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
        if role:
            rows = self.db.query(
                "SELECT id,name,department FROM research_people WHERE role=? ORDER BY name",
                (role,))
        else:
            rows = self.db.query(
                "SELECT id,name,department FROM research_people ORDER BY name")
        return [(r["id"], f"{r['name']} ({r['department'] or '—'})") for r in rows]

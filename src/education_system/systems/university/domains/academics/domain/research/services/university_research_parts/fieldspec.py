"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class FieldSpec:
    """Describes one field shown in an edit dialog."""
    def __init__(self, key, label, kind="text", choices=None, required=False,
                 default=None, hint=None):
        self.key = key
        self.label = label
        self.kind = kind  # 'text','multiline','combo','date','int','float','bool','people'
        self.choices = choices or []
        self.required = required
        self.default = default
        self.hint = hint

"""CLI bootstrap package.

Bootstrap implementations are deliberately not imported here: importing a
submodule must not initialize databases, authentication, or optional GUIs.
"""

__all__ = []

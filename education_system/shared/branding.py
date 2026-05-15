"""Active-system display name.

Set by the launcher just before dispatching into a system's run() so
that shared CLI/GUI surfaces (window titles, banners, log lines) can
look up the *current* system's display name at call-time rather than
binding to whatever was the default at import-time.

Read via module attribute access (e.g. ``branding.SYSTEM_NAME``), not
``from ... import SYSTEM_NAME`` — the latter snapshots the value.
"""

from __future__ import annotations

SYSTEM_NAME: str = "Sixth Form System"


def set_system_name(name: str) -> None:
    global SYSTEM_NAME
    SYSTEM_NAME = name

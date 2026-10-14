"""Compatibility shim.

``report_view`` was promoted to ``shell.gui.report_view`` when the
finance, advanced search, student support and IT helpdesk GUIs started
using it too. This re-export keeps the batch_operations import path
working; new code should import from the shared location.
"""

from education_system.systems.university.shell.gui.report_view import *  # noqa: F401,F403
from education_system.systems.university.shell.gui.report_view import (  # noqa: F401
    ACCENT, BAD, CARD_BG, GOOD, HEADER_BG, INFO, NEUTRAL, PAGE_BG, RULE,
    TEXT, TEXT_MUTED, TONES, TRACK, WARN,
    ReportView, colour, mono_font, report_toolbar, tone_for, ui_font,
)

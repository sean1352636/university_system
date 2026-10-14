"""Compatibility re-export of the shared report presentation helpers.

These mixins started life here, in Academics, because Course Management and
Library needed them first. Academic Progress (Assessment) needs the same
vocabulary, and a domain must never import another domain's GUI package — so
the module now lives in ``platform.delivery.gui.report_presentation`` and this
name stays as an alias for the Academics modules that already import it.
"""

from education_system.platform.delivery.gui.report_presentation import *  # noqa: F401,F403
from education_system.platform.delivery.gui.report_presentation import (  # noqa: F401
    ReportPresentationMixin,
    TextReportRendererMixin,
    SectionReportMixin,
    ReportPane,
    parse_text_report,
    _split_row,
    _split_section_lines,
    _column_names,
    _looks_numeric,
    _merge_currency,
    _RULE,
    _HEADING,
    _KEYVALUE,
    _NUMERIC,
)

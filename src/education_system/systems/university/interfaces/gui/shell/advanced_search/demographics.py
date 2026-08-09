"""Backward-compatible demographic-reporting façade."""

# Preserve the analytics helpers historically exposed by this GUI module while
# keeping their implementations in the canonical service package.
from education_system.systems.university.services.analytics.advanced_search import *  # noqa: F401,F403

from .demographic_reporting.ui import (
    AdvancedDemographicReportGUI,
    StudentDemographicReportGUI,
)


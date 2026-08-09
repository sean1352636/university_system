"""Package split from the original student_features.py.

Public API used by absence_tracker.py: StudentContext, build_student_tab.
The 51 stu_NN_* legacy aliases are also re-exposed as package attributes
for backwards compatibility with any caller that imported them by name.
"""

from .context import StudentContext, ensure_student_tables
from .prefs import StudentPrefs
from .gauge import GaugeThresholds
from .widgets.prompt import Prompt
from .widgets.module_picker import ModulePicker
from .widgets.calendar_window import _CalendarWindow
from .services import (
    AttendanceVisibilityService, RequestService, NotificationService,
    PlanningService, SupportService, SocialService, AppealsService,
    IntegrationsService, CustomisationService,
)
from .facade import StudentServices
from .registry import FeatureSpec, FEATURES
from .tab import build_student_tab
from .legacy import _wrap, _LEGACY_ALIASES

# Expose stu_NN_* aliases at the package top level (original behaviour).
globals().update(_LEGACY_ALIASES)

__all__ = [
    "StudentContext",
    "build_student_tab",
    "StudentServices",
    "FEATURES",
    "FeatureSpec",
    "ensure_student_tables",
    *_LEGACY_ALIASES.keys(),
]

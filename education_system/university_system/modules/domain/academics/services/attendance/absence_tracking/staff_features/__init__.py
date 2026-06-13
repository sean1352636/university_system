"""Package split from the original staff_features.py.

Public API used by absence_tracker.py: StaffContext, build_staff_tab.
The 51 stf_NN_* legacy aliases are also re-exposed as package attributes
for backwards compatibility with any caller that imported them by name.
"""

from .context import StaffContext, ensure_staff_tables
from .prefs import StaffPrefs
from .widgets.prompt import Prompt
from .widgets.module_picker import ModulePicker
from .widgets.staff_picker import StaffPicker
from .services import (
    RollCallService, RosterService, RequestReviewService,
    AnalyticsService, CommunicationService, PastoralService,
    AssessmentIntegrationService, CollaborationService,
    ConfigurationService, ProductivityService, LeaveService,
)
from .facade import StaffServices
from .registry import FeatureSpec, FEATURES
from .tab import build_staff_tab
from .legacy import _wrap, _LEGACY_ALIASES

globals().update(_LEGACY_ALIASES)

__all__ = [
    "StaffContext",
    "build_staff_tab",
    "StaffServices",
    "FEATURES",
    "FeatureSpec",
    "ensure_staff_tables",
    *_LEGACY_ALIASES.keys(),
]

"""Compatibility façade for the split implementation."""

from . import early_warning_core_shared as _shared
from .early_warning_core_shared import *  # noqa: F401,F403

from .early_warning_core_parts import resolve_staff_email as _part_1
_resolve_staff_email = _part_1._resolve_staff_email
_shared._resolve_staff_email = _resolve_staff_email
_shared.__all__.append("_resolve_staff_email") if "_resolve_staff_email" not in _shared.__all__ else None

from .early_warning_core_parts import riskassessmentmanager as _part_2
RiskAssessmentManager = _part_2.RiskAssessmentManager
_shared.RiskAssessmentManager = RiskAssessmentManager
_shared.__all__.append("RiskAssessmentManager") if "RiskAssessmentManager" not in _shared.__all__ else None

from .early_warning_core_parts import indicatormanager as _part_3
IndicatorManager = _part_3.IndicatorManager
_shared.IndicatorManager = IndicatorManager
_shared.__all__.append("IndicatorManager") if "IndicatorManager" not in _shared.__all__ else None

from .early_warning_core_parts import interventionmanager as _part_4
InterventionManager = _part_4.InterventionManager
_shared.InterventionManager = InterventionManager
_shared.__all__.append("InterventionManager") if "InterventionManager" not in _shared.__all__ else None

from .early_warning_core_parts import coachingmanager as _part_5
CoachingManager = _part_5.CoachingManager
_shared.CoachingManager = CoachingManager
_shared.__all__.append("CoachingManager") if "CoachingManager" not in _shared.__all__ else None

from .early_warning_core_parts import tutoringmanager as _part_6
TutoringManager = _part_6.TutoringManager
_shared.TutoringManager = TutoringManager
_shared.__all__.append("TutoringManager") if "TutoringManager" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['CoachingManager', 'IndicatorManager', 'InterventionManager', 'RiskAssessmentManager', 'TutoringManager', '_resolve_staff_email']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = [
    'RiskAssessmentManager',
    'IndicatorManager',
    'InterventionManager',
    'CoachingManager',
    'TutoringManager',
]
# The Early Warning window and CLI menu now live in the pastoral
# interfaces layer, in the Interventions window/menu (intervention_hub).

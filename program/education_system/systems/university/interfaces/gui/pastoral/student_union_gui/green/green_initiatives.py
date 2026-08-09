"""Compatibility façade for the split implementation."""

from . import green_initiatives_shared as _shared
from .green_initiatives_shared import *  # noqa: F401,F403

from .green_initiatives_parts import ensure_green_tables as _part_1
_ensure_green_tables = _part_1._ensure_green_tables
_shared._ensure_green_tables = _ensure_green_tables
_shared.__all__.append("_ensure_green_tables") if "_ensure_green_tables" not in _shared.__all__ else None

from .green_initiatives_parts import get_current_user_id as _part_2
_get_current_user_id = _part_2._get_current_user_id
_shared._get_current_user_id = _get_current_user_id
_shared.__all__.append("_get_current_user_id") if "_get_current_user_id" not in _shared.__all__ else None

from .green_initiatives_parts import greeninitiativesdialog as _part_3
GreenInitiativesDialog = _part_3.GreenInitiativesDialog
_shared.GreenInitiativesDialog = GreenInitiativesDialog
_shared.__all__.append("GreenInitiativesDialog") if "GreenInitiativesDialog" not in _shared.__all__ else None

from .green_initiatives_parts import carbontrackingdialog as _part_4
CarbonTrackingDialog = _part_4.CarbonTrackingDialog
_shared.CarbonTrackingDialog = CarbonTrackingDialog
_shared.__all__.append("CarbonTrackingDialog") if "CarbonTrackingDialog" not in _shared.__all__ else None

from .green_initiatives_parts import wastereductiondialog as _part_5
WasteReductionDialog = _part_5.WasteReductionDialog
_shared.WasteReductionDialog = WasteReductionDialog
_shared.__all__.append("WasteReductionDialog") if "WasteReductionDialog" not in _shared.__all__ else None

from .green_initiatives_parts import greentransportdialog as _part_6
GreenTransportDialog = _part_6.GreenTransportDialog
_shared.GreenTransportDialog = GreenTransportDialog
_shared.__all__.append("GreenTransportDialog") if "GreenTransportDialog" not in _shared.__all__ else None

from .green_initiatives_parts import environmentalreportsdialog as _part_7
EnvironmentalReportsDialog = _part_7.EnvironmentalReportsDialog
_shared.EnvironmentalReportsDialog = EnvironmentalReportsDialog
_shared.__all__.append("EnvironmentalReportsDialog") if "EnvironmentalReportsDialog" not in _shared.__all__ else None

from .green_initiatives_parts import sustainableeventsdialog as _part_8
SustainableEventsDialog = _part_8.SustainableEventsDialog
_shared.SustainableEventsDialog = SustainableEventsDialog
_shared.__all__.append("SustainableEventsDialog") if "SustainableEventsDialog" not in _shared.__all__ else None

from .green_initiatives_parts import ecosuppliersdialog as _part_9
EcoSuppliersDialog = _part_9.EcoSuppliersDialog
_shared.EcoSuppliersDialog = EcoSuppliersDialog
_shared.__all__.append("EcoSuppliersDialog") if "EcoSuppliersDialog" not in _shared.__all__ else None

from .green_initiatives_parts import greencertificationsdialog as _part_10
GreenCertificationsDialog = _part_10.GreenCertificationsDialog
_shared.GreenCertificationsDialog = GreenCertificationsDialog
_shared.__all__.append("GreenCertificationsDialog") if "GreenCertificationsDialog" not in _shared.__all__ else None

from .green_initiatives_parts import offsetprogramsdialog as _part_11
OffsetProgramsDialog = _part_11.OffsetProgramsDialog
_shared.OffsetProgramsDialog = OffsetProgramsDialog
_shared.__all__.append("OffsetProgramsDialog") if "OffsetProgramsDialog" not in _shared.__all__ else None

from .green_initiatives_parts import open_green_initiatives_dialog as _part_12
open_green_initiatives_dialog = _part_12.open_green_initiatives_dialog
_shared.open_green_initiatives_dialog = open_green_initiatives_dialog
_shared.__all__.append("open_green_initiatives_dialog") if "open_green_initiatives_dialog" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['CarbonTrackingDialog', 'EcoSuppliersDialog', 'EnvironmentalReportsDialog', 'GreenCertificationsDialog', 'GreenInitiativesDialog', 'GreenTransportDialog', 'OffsetProgramsDialog', 'SustainableEventsDialog', 'WasteReductionDialog', '_ensure_green_tables', '_get_current_user_id', 'open_green_initiatives_dialog']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['CarbonTrackingDialog', 'EcoSuppliersDialog', 'EnvironmentalReportsDialog', 'GreenCertificationsDialog', 'GreenInitiativesDialog', 'GreenTransportDialog', 'OffsetProgramsDialog', 'SustainableEventsDialog', 'WasteReductionDialog', '_ensure_green_tables', '_get_current_user_id', 'open_green_initiatives_dialog']

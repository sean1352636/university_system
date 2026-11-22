"""Reusable Tk dialogs and panels for the cross-GUI services.

Each helper renders one of the views in ``_cross_services.py`` so a
caller can wire a button without rebuilding the dialog every time.

Split by the domain each panel reads from; this package is the public
surface and its exports are unchanged.
"""

from __future__ import annotations

from .dialogs import (
    show_conflicts_dialog,
    show_instructor_workload_dialog,
    show_at_risk_dialog,
    show_module_timeline_dialog,
)
from .academic import (
    ModuleTimelinePanel,
    AcademicPeriodPanel,
)
from .student import (
    StudentFinancePanel,
    StudentUnionPanel,
    EngagementsPanel,
)
from .campus import (
    ResourceAvailabilityPanel,
    TripsAndParkingPanel,
    RestaurantPanel,
)
from .staff import (
    ResearchOutputPanel,
    StaffWorkloadPanel,
    StaffCertificationsPanel,
)
from .timetable import (
    WeeklyGridPanel,
)
from .compliance import (
    IncidentEvidencePanel,
    OpenCasesPanel,
)
from .chatbot import (
    ChatbotPanel,
)

__all__ = [
    "show_conflicts_dialog",
    "show_instructor_workload_dialog",
    "show_at_risk_dialog",
    "show_module_timeline_dialog",
    "ModuleTimelinePanel",
    "AcademicPeriodPanel",
    "StudentFinancePanel",
    "StudentUnionPanel",
    "EngagementsPanel",
    "ResourceAvailabilityPanel",
    "TripsAndParkingPanel",
    "RestaurantPanel",
    "ResearchOutputPanel",
    "StaffWorkloadPanel",
    "StaffCertificationsPanel",
    "WeeklyGridPanel",
    "IncidentEvidencePanel",
    "OpenCasesPanel",
    "ChatbotPanel",
]

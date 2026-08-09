"""Cross-domain data adapters for the assignment GUI.

Each module here exposes pure data-fetching helpers (no UI, no I/O loops)
so the assignment GUI can pull from parent_portal, library and attendance
services without re-implementing their queries.
"""

from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.parent_portal import (
    fetch_child_assignments,
    fetch_parent_children,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.library import (
    fetch_module_resources,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.attendance import (
    fetch_module_attendance,
    fetch_attendance_warning,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.finance import (
    calc_late_penalty,
    record_late_penalty,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.helpdesk import (
    escalate_dispute_to_helpdesk,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.legal import (
    open_integrity_case,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.transcripts import (
    sync_grade_to_gradebook,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.kpi import (
    push_assignment_kpi,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.calendar_sync import (
    sync_assignment_to_calendar,
    remove_assignment_from_calendar,
)
from education_system.systems.university.interfaces.gui.academics.assignment_system.integrations.activity import (
    recent_late_fines,
    recent_dispute_tickets,
    recent_integrity_cases,
    recent_gradebook_syncs,
    recent_calendar_events,
)

__all__ = [
    "fetch_child_assignments",
    "fetch_parent_children",
    "fetch_module_resources",
    "fetch_module_attendance",
    "fetch_attendance_warning",
    "calc_late_penalty",
    "record_late_penalty",
    "escalate_dispute_to_helpdesk",
    "open_integrity_case",
    "sync_grade_to_gradebook",
    "push_assignment_kpi",
    "sync_assignment_to_calendar",
    "remove_assignment_from_calendar",
    "recent_late_fines",
    "recent_dispute_tickets",
    "recent_integrity_cases",
    "recent_gradebook_syncs",
    "recent_calendar_events",
]

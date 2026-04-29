"""Cross-domain data adapters for the grade tracking GUI.

Same pattern as ``assignment_system/integrations/``: pure data
helpers so the GUI doesn't keep re-implementing queries against
other subsystems' tables.
"""

from education_system.university_system.modules.domain.academics.gui.grade_tracking.integrations.submissions import (
    fetch_assignment_submissions,
    fetch_graded_submission_count,
)

__all__ = [
    "fetch_assignment_submissions",
    "fetch_graded_submission_count",
]

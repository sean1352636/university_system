"""Grade Tracking Dialogs.

Grade entry lives in ``grades/ui/`` as mixins on GradeManager
(add_dialog, edit_dialog, batch_dialog, import_dialog). Six
standalone grade dialogs used to sit here as a second, parallel
implementation — unreachable from any screen, and two of them
wrote to the grades table without an audit entry, so wiring one
up would have bypassed the FERPA trail the live path enforces.
They were removed; this package now holds only the dialogs that
are actually used.
"""

from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.dialogs.student_dialog import StudentDialog
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.dialogs.module_dialog import ModuleDialog
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.dialogs.assessment_dialog import AssessmentDialog
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.dialogs.enrollment_dialog import ModuleEnrollmentDialog
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.dialogs.add_outcome_dialog import AddLearningOutcomeDialog
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.dialogs.edit_outcome_dialog import EditLearningOutcomeDialog

__all__ = [
    'StudentDialog',
    'ModuleDialog',
    'AssessmentDialog',
    'ModuleEnrollmentDialog',
    'AddLearningOutcomeDialog',
    'EditLearningOutcomeDialog',
]

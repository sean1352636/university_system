# Backward-compatible re-exports — all code moved to exam_management
from education_system.university_system.modules.domain.academics.gui.exam_management import (
    ExamSchedulerApp, main, Exam, Room, DataManager, StudentExamViewer, ExamPortalGUI,
)

__all__ = ['ExamSchedulerApp', 'main', 'Exam', 'Room', 'DataManager', 'StudentExamViewer', 'ExamPortalGUI']

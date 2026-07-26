"""
Exam Management System — unified exam scheduling, management, and online examination portal.
Merges the former Exam Scheduler and Exam Portal into a single package.
"""

from education_system.systems.university.interfaces.gui.academics.exam_management.app import ExamSchedulerApp, main
from education_system.systems.university.interfaces.gui.academics.exam_management.models import Exam, Room
from education_system.systems.university.interfaces.gui.academics.exam_management.data_manager import DataManager
from education_system.systems.university.interfaces.gui.academics.exam_management.student_viewer import StudentExamViewer
from education_system.systems.university.interfaces.gui.academics.exam_management.exam_portal_gui import ExamPortalGUI

__all__ = ['ExamSchedulerApp', 'main', 'Exam', 'Room', 'DataManager', 'StudentExamViewer', 'ExamPortalGUI']

"""
Exam Scheduling System
A comprehensive GUI application for managing exam schedules, rooms, and courses.
Enhanced with database integration for modules, instructors, and email notifications.
"""

from education_system.university_system.modules.domain.academics.gui.exam_scheduler.app import ExamSchedulerApp, main
from education_system.university_system.modules.domain.academics.gui.exam_scheduler.models import Exam, Room
from education_system.university_system.modules.domain.academics.gui.exam_scheduler.data_manager import DataManager
from education_system.university_system.modules.domain.academics.gui.exam_scheduler.student_viewer import StudentExamViewer

__all__ = ['ExamSchedulerApp', 'main', 'Exam', 'Room', 'DataManager', 'StudentExamViewer']

"""
Exam Scheduling System
A comprehensive GUI application for managing exam schedules, rooms, and courses.
Enhanced with database integration for modules, instructors, and email notifications.
"""

from .app import ExamSchedulerApp, main
from .models import Exam, Room
from .data_manager import DataManager
from .student_viewer import StudentExamViewer

__all__ = ['ExamSchedulerApp', 'main', 'Exam', 'Room', 'DataManager', 'StudentExamViewer']

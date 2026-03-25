"""
This package consolidates the various mixin modules for the
alumni management GUI. Importing from this package will
re-export the primary `AlumniGUIApp` class along with the
standard entry points (main and launch_alumni_gui).

The individual mixins are also imported for static type
checking purposes, though they are not re-exported into
__all__.
"""

from education_system.university_system.modules.domain.student_affairs.gui.alumni.main_gui import AlumniGUIApp, main, launch_alumni_gui
from education_system.university_system.modules.domain.student_affairs.gui.alumni.dashboard import DashboardMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.alumni_crud import AlumniCRUDMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.directory import DirectoryMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.business_directory import BusinessDirectoryMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.events import EventsMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.forum import ForumMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.stories_photos import StoriesPhotosMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.donations import DonationsMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.reports import ReportsMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.chapters import ChaptersMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.mentorship import MentorshipMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.jobs_career import JobsCareerMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.reunions import ReunionsMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.gamification import GamificationMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.notifications import NotificationsMixin

__all__ = [
    'AlumniGUIApp',
    'main',
    'launch_alumni_gui',
    'DashboardMixin',
    'AlumniCRUDMixin',
    'DirectoryMixin',
    'BusinessDirectoryMixin',
    'EventsMixin',
    'ForumMixin',
    'StoriesPhotosMixin',
    'DonationsMixin',
    'ReportsMixin',
    'ChaptersMixin',
    'MentorshipMixin',
    'JobsCareerMixin',
    'ReunionsMixin',
    'GamificationMixin',
    'NotificationsMixin',
]

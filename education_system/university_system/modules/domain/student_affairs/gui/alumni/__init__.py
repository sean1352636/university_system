"""
This package consolidates the various mixin modules for the
alumni management GUI. Importing from this package will
re-export the primary `AlumniGUIApp` class along with the
standard entry points (main and launch_alumni_gui).

The individual mixins are also imported for static type
checking purposes, though they are not re-exported into
__all__.
"""

from .main_gui import AlumniGUIApp, main, launch_alumni_gui
from .dashboard import DashboardMixin
from .alumni_crud import AlumniCRUDMixin
from .directory import DirectoryMixin
from .business_directory import BusinessDirectoryMixin
from .events import EventsMixin
from .forum import ForumMixin
from .stories_photos import StoriesPhotosMixin
from .donations import DonationsMixin
from .reports import ReportsMixin
from .chapters import ChaptersMixin
from .mentorship import MentorshipMixin
from .jobs_career import JobsCareerMixin
from .reunions import ReunionsMixin
from .gamification import GamificationMixin
from .notifications import NotificationsMixin

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

"""Alumni management GUI package — public API.

Aggregates the 15 sibling mixin modules (dashboard, CRUD, directory,
business directory, events, forum, stories/photos, donations, reports,
chapters, mentorship, jobs/career, reunions, gamification, notifications)
plus the main app class. Canonical import pattern:

    from education_system.systems.university.interfaces.gui.learners.alumni \\
        import AlumniGUIApp, launch_alumni_gui

Live callers (verified 2026-05): the unified GUI's launcher registry, the
staff portal, the alumni-management service's menu module, and the GUI
test suite. This is the canonical aggregator, not a deprecated shim — the
mixin imports are exposed in __all__ so callers can subclass and reuse them.
"""

from education_system.systems.university.interfaces.gui.learners.alumni.main_gui import AlumniGUIApp, main, launch_alumni_gui
from education_system.systems.university.interfaces.gui.learners.alumni.dashboard import DashboardMixin
from education_system.systems.university.interfaces.gui.learners.alumni.alumni_crud import AlumniCRUDMixin
from education_system.systems.university.interfaces.gui.learners.alumni.directory import DirectoryMixin
from education_system.systems.university.interfaces.gui.learners.alumni.business_directory import BusinessDirectoryMixin
from education_system.systems.university.interfaces.gui.learners.alumni.events import EventsMixin
from education_system.systems.university.interfaces.gui.learners.alumni.forum import ForumMixin
from education_system.systems.university.interfaces.gui.learners.alumni.stories_photos import StoriesPhotosMixin
from education_system.systems.university.interfaces.gui.learners.alumni.donations import DonationsMixin
from education_system.systems.university.interfaces.gui.learners.alumni.reports import ReportsMixin
from education_system.systems.university.interfaces.gui.learners.alumni.chapters import ChaptersMixin
from education_system.systems.university.interfaces.gui.learners.alumni.mentorship import MentorshipMixin
from education_system.systems.university.interfaces.gui.learners.alumni.jobs_career import JobsCareerMixin
from education_system.systems.university.interfaces.gui.learners.alumni.reunions import ReunionsMixin
from education_system.systems.university.interfaces.gui.learners.alumni.gamification import GamificationMixin
from education_system.systems.university.interfaces.gui.learners.alumni.notifications import NotificationsMixin

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

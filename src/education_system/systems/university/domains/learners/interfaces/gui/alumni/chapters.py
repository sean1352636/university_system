"""Regional chapters in the alumni window.

The old screen wrote memberships to ``chapter_members`` while the rules
read ``chapter_memberships``; it is in ``remove/``. These open the screens
in ``alumni_office_community`` (rules: ``application/alumni/community``).
"""


def _screens():
    from education_system.systems.university.domains.learners.interfaces.gui.alumni import (
        alumni_office_community,
    )
    return alumni_office_community


class ChaptersMixin:
    def show_regional_chapters(self):
        screens = _screens()
        who = screens.who_of(self)
        if who is not None and who.is_office:
            screens.show_chapters(self)
        else:
            screens.show_my_chapters(self)

    def view_my_chapters(self):
        _screens().show_my_chapters(self)

    def join_regional_chapter(self):
        _screens().show_my_chapters(self)

    def admin_manage_chapters(self):
        _screens().show_chapters(self)

    def create_regional_chapter(self):
        _screens().show_chapters(self)

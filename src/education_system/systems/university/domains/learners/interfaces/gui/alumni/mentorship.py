"""Mentoring in the alumni window.

The old screens paired mentors and students with no vetting, no student
consent and no way to raise a concern; they are in ``remove/``. These open
the screens in ``alumni_office_mentoring`` (rules:
``application/alumni/community``): the coordinator gets Mentoring, alumni
and students get My mentoring.
"""


def _screens():
    from education_system.systems.university.domains.learners.interfaces.gui.alumni import (
        alumni_office_community,
        alumni_office_mentoring,
    )
    return alumni_office_community, alumni_office_mentoring


class MentorshipMixin:
    def show_setup_mentorship(self):
        base, screens = _screens()
        who = base.who_of(self)
        if who is not None and who.is_coordinator:
            screens.show_mentoring(self)
        else:
            screens.show_my_mentoring(self)

    def show_view_mentorships(self):
        self.show_setup_mentorship()

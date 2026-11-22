"""Giving in the alumni window.

The old screens wrote gifts straight into the database without Gift Aid
declarations, receipts or Finance posting; they are in ``remove/``. These
open the screens in ``alumni_office_community`` (rules:
``application/alumni/giving``): fundraising staff get Giving, alumni get My
giving.
"""


def _screens():
    from education_system.systems.university.domains.learners.interfaces.gui.alumni import (
        alumni_office_community,
    )
    return alumni_office_community


def _giving(app):
    screens = _screens()
    who = screens.who_of(app)
    if who is not None and who.is_fundraiser:
        screens.show_giving(app)
    else:
        screens.show_my_giving(app)


class DonationsMixin:
    def show_record_donation(self):
        _giving(self)

    def show_view_donations(self):
        _giving(self)

    def show_campaigns(self):
        _giving(self)

    def show_donor_recognition(self):
        _giving(self)

    def view_campaign_performance(self):
        _giving(self)

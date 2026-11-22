"""CLI flows for Sixth Form Alumni."""

from __future__ import annotations

from typing import Callable
from education_system.systems.sixth_form.domain.learners.alumni import models as alumni_models


from ._helpers import (
    logger,
    _UserAbort,
    _pause,
)
from .cli_records import (
    list_all,
    filter_alumni,
    view_alumnus,
    new_alumnus,
    edit_alumnus,
    archive_student_flow,
    record_contact_flow,
    set_status_flow,
    delete_alumnus_flow,
    summary_flow,
    education_flow,
    career_flow,
    contacts_flow,
    tags_flow,
    achievements_flow,
)
from .cli_comms import (
    comms_flow,
    send_email_flow,
    channel_prefs_flow,
    consent_flow,
    unarchived_leavers_flow,
    retention_flow,
    portal_token_flow,
)
from .cli_programmes import (
    events_flow,
    mentoring_flow,
    speakers_flow,
    work_exp_flow,
    references_flow,
    volunteering_flow,
    campaigns_flow,
    donations_flow,
)
from .cli_extensions_a import (
    social_handles_flow,
    connections_flow,
    chapters_flow,
    engagement_flow,
    directory_flow,
    skills_flow,
    promotion_timeline_flow,
    employers_flow,
    jobs_flow,
    internships_flow,
    mentor_match_flow,
)
from .cli_extensions_b import (
    mentor_profile_flow,
    mentor_rate_flow,
    mentor_safeguarding_flow,
    templates_flow,
    drip_flow,
    ab_flow,
    sms_flow,
    postal_flow,
    newsletter_flow,
    tracking_flow,
    ticketing_flow,
    checkin_flow,
    close_event_flow,
    reunion_planner_flow,
    gift_aid_flow,
    recurring_flow,
    donor_pipeline_flow,
    funds_flow,
    bequests_flow,
    matched_giving_flow,
    neet_flow,
    first_gen_flow,
    protected_chars_flow,
    custom_fields_flow,
    media_flow,
    ops_flow,
    reports_flow,
)


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All",           list_all),
    ("Filter",             filter_alumni),
    ("View",               view_alumnus),
    ("New (manual)",       new_alumnus),
    ("Archive student",    archive_student_flow),
    ("Unarchived leavers", unarchived_leavers_flow),
    ("Edit",               edit_alumnus),
    ("Education history",  education_flow),
    ("Career history",     career_flow),
    ("Emails & phones",    contacts_flow),
    ("Tags",               tags_flow),
    ("Achievements",       achievements_flow),
    ("Communications",     comms_flow),
    ("Send email",         send_email_flow),
    ("Channel prefs",      channel_prefs_flow),
    ("GDPR consent",       consent_flow),
    ("Portal token",       portal_token_flow),
    ("Record contact",     record_contact_flow),
    ("Events",             events_flow),
    ("Mentoring",          mentoring_flow),
    ("Speakers",           speakers_flow),
    ("Work-experience",    work_exp_flow),
    ("References",         references_flow),
    ("Volunteering",       volunteering_flow),
    ("Campaigns",          campaigns_flow),
    ("Donations & pledges", donations_flow),
    ("Social handles",     social_handles_flow),
    ("Connections",        connections_flow),
    ("Chapters",           chapters_flow),
    ("Engagement score",   engagement_flow),
    ("Public directory",   directory_flow),
    ("Skills",             skills_flow),
    ("Promotion timeline", promotion_timeline_flow),
    ("Employers directory", employers_flow),
    ("Job postings",       jobs_flow),
    ("Internships",        internships_flow),
    ("Mentor matching",    mentor_match_flow),
    ("Mentor profile",     mentor_profile_flow),
    ("Mentor session rate", mentor_rate_flow),
    ("Mentor safeguarding", mentor_safeguarding_flow),
    ("Email templates",    templates_flow),
    ("Drip campaigns",     drip_flow),
    ("A/B tests",          ab_flow),
    ("SMS",                sms_flow),
    ("Postal mail merge",  postal_flow),
    ("Newsletters",        newsletter_flow),
    ("Open/click tracking", tracking_flow),
    ("Event ticketing",    ticketing_flow),
    ("Event check-in",     checkin_flow),
    ("Close event + survey", close_event_flow),
    ("Reunion planner",    reunion_planner_flow),
    ("Gift Aid",           gift_aid_flow),
    ("Recurring donations", recurring_flow),
    ("Donor pipeline",     donor_pipeline_flow),
    ("Funds",              funds_flow),
    ("Bequests",           bequests_flow),
    ("Matched giving",     matched_giving_flow),
    ("NEET tracking",      neet_flow),
    ("First-gen HE",       first_gen_flow),
    ("Protected characteristics", protected_chars_flow),
    ("Custom fields",      custom_fields_flow),
    ("Media attachments",  media_flow),
    ("Change status",      set_status_flow),
    ("Retention",          retention_flow),
    ("Delete",             delete_alumnus_flow),
    ("Operational tools",  ops_flow),
    ("Reports",            reports_flow),
    ("Summary",            summary_flow),
]


def run() -> None:
    alumni_models._log_action("cli.menu_entered", menu="alumni")
    while True:
        print("\n── Alumni ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            alumni_models._log_action("cli.menu_exited", menu="alumni",
                              reason="interrupt")
            return
        if choice == "0":
            alumni_models._log_action("cli.menu_exited", menu="alumni")
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        alumni_models._log_action("cli.menu_select",
                          menu="alumni", option=label)
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
            alumni_models._log_action("cli.handler_cancelled",
                              menu="alumni", option=label)
        except Exception as e:
            logger.exception("Alumni CLI handler crashed (option=%s)",
                              label)
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Alumni":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Alumni CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True

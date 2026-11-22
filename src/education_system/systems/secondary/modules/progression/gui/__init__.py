"""Progression screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "move_to_sixth_form": Page(
        "Move to Sixth Form",
        "sixth_form_progression_views",
        "draw_move_to_sixth_form",
        state="_sixth_form_progression_state",
        links=("open_pupil",),
    ),
    "student_journey": Page(
        "Student Journey",
        "student_journey_views",
        "draw_student_journey",
        state="_student_journey_state",
        links=("open_pupil",),
    ),
    "incoming_primary": Page(
        "Incoming from Primary",
        "incoming_primary_views",
        "draw_incoming_primary",
        state="_incoming_primary_state",
        links=("open_pupil",),
    ),
    "ap_referrals": Page(
        "Referrals to Alternative Provision",
        "ap_referrals_views",
        "draw_ap_referrals",
        state="_ap_referrals_state",
        links=("open_pupil",),
    ),
    "send_requests": Page(
        "SEND Service Requests",
        "send_requests_views",
        "draw_send_requests",
        state="_send_requests_state",
        links=("open_pupil",),
    ),
    "local_authority": Page(
        "Local Authority",
        "local_authority_views",
        "draw_local_authority",
        state="_local_authority_state",
        links=("open_pupil",),
    ),
    "year6_transition": Page(
        "Year 6 Transition",
        "year6_transition_views",
        "draw_year6_transition",
        state="_year6_transition_state",
        links=("open_pupil",),
    ),
}

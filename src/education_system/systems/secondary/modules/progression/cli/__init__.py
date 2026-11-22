"""Progression menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "move_to_sixth_form": "sixth_form_progression_cli",
    "student_journey": "student_journey_cli",
    "incoming_primary": "incoming_primary_cli",
    "ap_referrals": "ap_referrals_cli",
    "send_requests": "send_requests_cli",
    "local_authority": "local_authority_cli",
    "year6_transition": "year6_transition_cli",
}

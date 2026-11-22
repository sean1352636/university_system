"""Administration screens: what each menu key opens (see ui.gui.navigation.pages)."""

from education_system.systems.secondary.ui.gui.navigation.pages import Page

PAGES: dict[str, Page] = {
    "complaints": Page(
        "Complaints",
        "complaints_views",
        "draw_complaints",
        state="_complaints_state",
        links=("open_pupil",),
    ),
    "user_accounts": Page(
        "User Accounts", "user_accounts_views", "draw_user_accounts", state="_user_accounts_state"
    ),
    "settings": Page(
        "Settings",
        "settings_views",
        "draw_settings",
        state="_settings_state",
    ),
    "audit_log": Page(
        "Audit Log",
        "audit_log_views",
        "draw_audit_log",
        state="_audit_log_state",
    ),
}

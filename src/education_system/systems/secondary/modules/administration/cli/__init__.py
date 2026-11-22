"""Administration menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "complaints": "complaints_cli",
    "user_accounts": "user_accounts_cli",
    "settings": "settings_cli",
    "audit_log": "audit_log_cli",
}

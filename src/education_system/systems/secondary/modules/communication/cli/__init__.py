"""Communication menus: what each menu key runs (see ui.cli.menus.menus)."""

MENUS: dict[str, str] = {
    "parent_contacts": "contacts_cli:parent_contacts",
    "messages": "email_cli",
    "parents_evenings": "parents_evenings_cli",
    "announcements": "announcements_cli",
    "letters": "letters_cli",
}

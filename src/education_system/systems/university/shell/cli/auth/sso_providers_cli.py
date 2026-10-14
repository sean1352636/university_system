"""Admin-only console menu for SSO identity providers — mirrors room_booking_cli.

Lists, configures, enables/disables and dry-run tests providers through
``SSOService``. The login flow is untouched: nothing here authenticates a
user, and SAML providers fail closed while python3-saml is absent.
"""
from __future__ import annotations

import json
from typing import Any

from education_system.systems.university.infrastructure.auth import sso_admin
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_admin() -> bool:
    user = getattr(auth, "current_user", None) if auth else None
    if not user:
        print(get_text("cli.sso.login_required", default="You must be logged in to manage SSO providers."))
        return False
    if not sso_admin.is_admin(user):
        print(get_text("cli.sso.admin_only", default="SSO provider management is admin only."))
        return False
    return True


def _print_status() -> None:
    print("\nProtocol availability:")
    for row in sso_admin.provider_type_status():
        state = "available" if row["available"] else "UNAVAILABLE (fails closed)"
        print(f"  {row['label']:<16} {state}")


def _list(svc) -> None:
    rows = svc.list_providers(enabled_only=False)
    if not rows:
        print(get_text("cli.sso.none", default="No SSO providers configured."))
        return
    print(f"\n{'Provider ID':<20} {'Type':<6} {'Enabled':<8} {'Display name':<28} {'Updated':<20}")
    print("-" * 86)
    for p in rows:
        print(f"{p['provider_id']:<20} {p['provider_type']:<6} {'yes' if p['is_enabled'] else 'no':<8} "
              f"{p['display_name'][:28]:<28} {str(p['updated_at'] or '-')[:19]:<20}")
    print(f"\nTotal: {len(rows)}")


def _view(svc) -> None:
    provider = svc.get_provider(input("Provider ID: ").strip())
    if not provider:
        print("Provider not found.")
        return
    config = provider.pop("config", {})
    for key, value in provider.items():
        print(f"  {key:<14} {value}")
    print("  config:")
    for key, value in config.items():
        shown = "********" if "secret" in key.lower() else value
        print(f"    {key:<24} {shown}")


def _configure(svc) -> None:
    provider_id = input("Provider ID (new or existing): ").strip()
    provider_type = input("Type (oidc/saml): ").strip().lower()
    display_name = input("Display name: ").strip()
    print("Config as a JSON object, e.g. "
          '{"client_id": "...", "client_secret": "...", "authorization_endpoint": "...", '
          '"token_endpoint": "...", "redirect_uri": "..."}')
    raw = input("Config JSON: ").strip()
    try:
        config = json.loads(raw or "{}")
        if not isinstance(config, dict):
            raise ValueError("Config must be a JSON object")
        result = svc.register_provider(provider_id, provider_type, display_name, config)
        print(result["message"])
    except (ValueError, *sso_admin.SSO_ERRORS) as exc:
        print(f"Error: {exc}")


def _set_enabled(svc, enabled: bool) -> None:
    provider_id = input("Provider ID: ").strip()
    provider = svc.get_provider(provider_id)
    if not provider:
        print("Provider not found.")
        return
    if enabled:
        allowed, why = sso_admin.can_enable(provider)
        if not allowed:
            print(f"Refused: {why}")
            return
    try:
        print(svc.set_provider_enabled(provider_id, enabled)["message"])
    except sso_admin.SSO_ERRORS as exc:
        print(f"Error: {exc}")


def _test(svc) -> None:
    provider = svc.get_provider(input("Provider ID: ").strip())
    if not provider:
        print("Provider not found.")
        return
    result = sso_admin.test_provider(svc, provider)
    print(("OK: " if result["ok"] else "FAILED: ") + result["message"])
    if result["auth_url"]:
        print(f"  auth_url: {result['auth_url']}")


def display_sso_providers_menu() -> None:
    """Top-level SSO providers menu (admin only)."""
    if not _require_admin():
        return
    try:
        svc = sso_admin.build_sso_service()
    except Exception as exc:
        print(f"SSO service unavailable: {exc}")
        return
    _print_status()
    actions = {
        "1": (get_text("cli.sso.list", default="List Providers"), _list),
        "2": (get_text("cli.sso.view", default="View Provider"), _view),
        "3": (get_text("cli.sso.configure", default="Add / Update Provider"), _configure),
        "4": (get_text("cli.sso.enable", default="Enable Provider"), lambda s: _set_enabled(s, True)),
        "5": (get_text("cli.sso.disable", default="Disable Provider"), lambda s: _set_enabled(s, False)),
        "6": (get_text("cli.sso.test", default="Test Provider"), _test),
    }
    while True:
        print("\n" + get_text("cli.sso.title", default="SSO Providers"))
        print("=" * 30)
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        print("0. " + get_text("cli.menu.return", default="Return to Previous Menu"))
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print(get_text("cli.invalid_choice", default="Invalid choice."))
            continue
        try:
            action[1](svc)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except sso_admin.SSO_ERRORS as exc:
            print(f"Error: {exc}")

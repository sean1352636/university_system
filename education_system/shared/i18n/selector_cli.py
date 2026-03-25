"""CLI language selector for the shared i18n system.

Prints a numbered list of all supported languages and lets the user pick one.

Usage::

    from education_system.shared.i18n.selector_cli import show_language_selector_cli

    code = show_language_selector_cli()  # returns e.g. "fr"
"""

from __future__ import annotations

import sys

from education_system.shared.i18n.core import (
    get_available_language_list,
    get_current_language,
    get_english_name,
    set_language,
    SUPPORTED_LANGUAGES,
)


def show_language_selector_cli() -> str:
    """Show CLI language selector menu and return chosen code.

    Displays all 13 supported languages with their native and English
    names, highlights the current selection, and prompts the user to
    pick one by number.  Pressing Enter without a number keeps the
    current language.
    """
    languages = get_available_language_list()
    current = get_current_language()

    print()
    print("=" * 50)
    print("  Select Language".center(50))
    print("=" * 50)
    print()

    for idx, (code, native_name) in enumerate(languages, 1):
        english = get_english_name(code)
        marker = " *" if code == current else ""
        if native_name == english:
            line = f"  {idx:>2}. {native_name}{marker}"
        else:
            line = f"  {idx:>2}. {native_name} ({english}){marker}"
        print(line)

    print()
    print("-" * 50)

    while True:
        try:
            choice = input(f"Enter choice [1-{len(languages)}] (Enter to keep current): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return current

        if not choice:
            print(f"\nKeeping current language: {SUPPORTED_LANGUAGES.get(current, current)}")
            return current

        try:
            num = int(choice)
        except ValueError:
            print(f"  Invalid input. Please enter a number between 1 and {len(languages)}.")
            continue

        if 1 <= num <= len(languages):
            code, native_name = languages[num - 1]
            set_language(code)
            print(f"\nLanguage set to: {native_name} ({get_english_name(code)})")
            return code

        print(f"  Invalid choice. Please enter a number between 1 and {len(languages)}.")


__all__ = [
    "show_language_selector_cli",
]

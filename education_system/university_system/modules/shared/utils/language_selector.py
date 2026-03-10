"""
Language Selector Module for the University Management System.

This module provides a language selection menu that can be displayed
before the main application interface starts. It allows users to
choose their preferred language for the application.

Usage:
    from education_system.university_system.modules.shared.utils.language_selector import (
        display_language_selector,
        display_language_menu_option
    )

    # Show full language selector at startup
    display_language_selector()

    # Show language option in main menu
    display_language_menu_option()
"""

from __future__ import annotations

import sys
from typing import Optional

from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_language_list,
    SUPPORTED_LANGUAGES,
)


def display_language_selector(force_show: bool = False) -> str:
    """
    Display the language selection menu.

    This function shows a menu allowing users to select their preferred
    language. It is typically shown at application startup.

    Args:
        force_show: If True, always show the selector even if a language
                    preference is already saved.

    Returns:
        The selected language code
    """
    # Initialize i18n system (loads saved preference if exists)
    current_lang = init_i18n()

    # Get available languages
    languages = get_available_language_list()
    lang_count = len(languages)

    print("\n" + "=" * 60)
    print(get_text("language_selector.title").center(60))
    print("=" * 60)

    # Show current language
    current_name = get_current_language_name()
    print(f"\n{get_text('language_selector.current', language=current_name)}")

    print(f"\n{get_text('language_selector.prompt')}\n")

    # Display language options
    for i, (code, name) in enumerate(languages, 1):
        marker = " *" if code == current_lang else ""
        print(f"  {i}. {name}{marker}")

    print("-" * 60)

    while True:
        try:
            prompt = get_text("language_selector.change_prompt", count=lang_count)
            choice = input(f"\n{prompt} ").strip()

            # If empty, keep current language
            if not choice:
                print(f"\n{get_text('language_selector.language_set', language=current_name)}")
                return current_lang

            # Validate choice
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= lang_count:
                    selected_code, selected_name = languages[choice_num - 1]
                    set_language(selected_code)
                    # Reload the translation for the new language
                    init_i18n(selected_code)
                    print(f"\n{get_text('language_selector.language_set', language=selected_name)}")
                    return selected_code
                else:
                    print(get_text("language_selector.invalid_choice", count=lang_count))
            except ValueError:
                print(get_text("language_selector.invalid_choice", count=lang_count))

        except KeyboardInterrupt:
            print("\n\n" + get_text("menu.exiting"))
            sys.exit(0)
        except EOFError:
            print("\n\n" + get_text("menu.exiting"))
            sys.exit(0)


def display_language_menu_option() -> None:
    """
    Display the language selection option from within the main menu.

    This is a simplified version that just allows changing the language
    and returns to the main menu.
    """
    display_language_selector(force_show=True)
    input(f"\n{get_text('language_selector.continue_prompt')} ")


def get_startup_language_choice() -> Optional[str]:
    """
    Prompt for language selection only on first run or if no preference exists.

    Returns:
        The language code if user made a selection, None if using existing preference
    """
    from education_system.university_system.modules.shared.utils.i18n import load_saved_language, _get_config_path

    config_path = _get_config_path()

    # If no config exists, show selector
    if not config_path.exists():
        return display_language_selector(force_show=True)

    # Otherwise just initialize with saved preference
    return init_i18n()


__all__ = [
    "display_language_selector",
    "display_language_menu_option",
    "get_startup_language_choice",
]

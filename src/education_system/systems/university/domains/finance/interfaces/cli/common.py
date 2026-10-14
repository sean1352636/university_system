"""Shared prompt, table and menu helpers for the Finance CLI menus.

Every menu package under ``finance/interfaces/cli`` is a numbered loop over
domain functions. The pieces that do not depend on the domain — reading a
value, printing a table, gating on a permission, running the loop — live here
so each menu module holds only its actions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from typing import Any, Optional

from education_system.systems.university.infrastructure.i18n import get_text

logger = logging.getLogger(__name__)

#: Permission every finance menu requires.
FINANCE_PERMISSION = 'manage_finances'

_I18N_PREFIX = 'finance_cli.'


def t(key: str, default: str, **kwargs: Any) -> str:
    """Translate ``finance_cli.<key>`` with an English default.

    ``get_text`` formats placeholders only when the key is translated; this
    applies them to the default as well so callers never see raw braces.
    """
    text = get_text(_I18N_PREFIX + key, default=default, **kwargs)
    if kwargs and text == default:
        try:
            return default.format(**kwargs)
        except (KeyError, IndexError):
            return default
    return text


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
def prompt(text: str, default: str = '') -> str:
    suffix = f" [{default}]" if default else ''
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def prompt_int(text: str, *, allow_blank: bool = True, minimum: Optional[int] = None) -> Optional[int]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print(t('prompt.value_required', "A value is required."))
            continue
        try:
            value = int(raw)
        except ValueError:
            print(t('prompt.whole_number', "Please enter a whole number."))
            continue
        if minimum is not None and value < minimum:
            print(t('prompt.at_least', "Please enter a number of at least {minimum}.", minimum=minimum))
            continue
        return value


def prompt_float(text: str, *, allow_blank: bool = True, default: Optional[float] = None,
                 minimum: Optional[float] = None) -> Optional[float]:
    suffix = f" [{default}]" if default is not None else ''
    while True:
        raw = input(f"{text}{suffix}: ").strip()
        if not raw:
            if default is not None:
                return default
            if allow_blank:
                return None
            print(t('prompt.value_required', "A value is required."))
            continue
        try:
            value = float(raw)
        except ValueError:
            print(t('prompt.number', "Please enter a number."))
            continue
        if minimum is not None and value < minimum:
            print(t('prompt.at_least', "Please enter a number of at least {minimum}.", minimum=minimum))
            continue
        return value


def prompt_bool(text: str, default: bool = False) -> bool:
    hint = 'Y/n' if default else 'y/N'
    raw = input(f"{text} ({hint}): ").strip().lower()
    if not raw:
        return default
    return raw in ('y', 'yes', 'true', '1')


def prompt_choice(text: str, options: Sequence[str], default: Optional[str] = None) -> Optional[str]:
    """Pick one of ``options`` by number or by name; blank returns ``default``."""
    for index, option in enumerate(options, 1):
        marker = ' *' if option == default else ''
        print(f"  {index}. {option}{marker}")
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            return default
        if raw in options:
            return raw
        try:
            index = int(raw) - 1
        except ValueError:
            index = -1
        if 0 <= index < len(options):
            return options[index]
        print(t('prompt.choose_listed', "Please choose one of the listed options."))


def prompt_date(text: str, default: Optional[str] = None, *, allow_blank: bool = False) -> Optional[str]:
    """A ``YYYY-MM-DD`` date; ``default`` is offered when supplied."""
    while True:
        raw = prompt(text, default or '')
        if not raw:
            if allow_blank:
                return None
            print(t('prompt.value_required', "A value is required."))
            continue
        try:
            datetime.strptime(raw, '%Y-%m-%d')
            return raw
        except ValueError:
            print(t('prompt.date_format', "Please enter a date as YYYY-MM-DD."))


def prompt_multiline(text: str) -> str:
    """Read lines until an empty line; returns them joined with newlines."""
    print(t('prompt.multiline_hint', "{text} (finish with an empty line):", text=text))
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return '\n'.join(lines).strip()


def pause() -> None:
    try:
        input('\n' + t('prompt.press_enter', "Press Enter to continue..."))
    except EOFError:
        pass


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def header(title: str) -> None:
    print('\n' + '=' * 60)
    print(f"  {title}")
    print('=' * 60)


def money(value: Any) -> str:
    try:
        return f"£{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return '£0.00'


def cell(value: Any, width: int = 30) -> str:
    """A table cell: ``None`` becomes ``-`` and long text is cut to ``width``."""
    if value is None or value == '':
        return '-'
    text = str(value).replace('\n', ' ')
    return text if len(text) <= width else text[:width - 1] + '…'


def print_table(headers: Sequence[str], rows: Iterable[Sequence[Any]],
                max_width: int = 30, empty: Optional[str] = None) -> None:
    """Print rows under headers, sizing each column to its widest value."""
    rows = [[cell(value, max_width) for value in row] for row in rows]
    if not rows:
        print('\n' + (empty or t('table.no_rows', "Nothing to show.")))
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    line = '  '.join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print('\n' + line)
    print('-' * len(line))
    for row in rows:
        print('  '.join(value.ljust(widths[i]) for i, value in enumerate(row)))
    print(t('table.row_count', "{count} row(s)", count=len(rows)))


def ok(message: str) -> None:
    print(f"\n✓ {message}")


def fail(message: str) -> None:
    print(f"\n✗ {message}")


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def current_username(auth: Any) -> str:
    try:
        user = getattr(auth, 'current_user', None)
        if isinstance(user, dict):
            return user.get('username') or user.get('name') or 'cli-user'
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return 'cli-user'


def require_permission(auth: Any, permission: str = FINANCE_PERMISSION) -> bool:
    """Print a denial and return False unless ``auth`` grants ``permission``."""
    try:
        allowed = bool(auth and auth.check_permission(permission))
    except Exception:
        logger.debug("permission check failed", exc_info=True)
        allowed = False
    if not allowed:
        print(t('auth.denied', "You don't have permission to use this menu ({permission}).",
                permission=permission))
    return allowed


def bind_legacy_auth(auth: Any, *modules: Any) -> None:
    """Point the shared finance context and legacy module globals at ``auth``.

    The menu-driven domain functions (``process_refund``, ``manage_payment_plans``
    and friends) read a module-level ``auth`` captured at import time. Rebinding
    it keeps them working when this menu is entered from a different session.
    """
    try:
        from education_system.systems.university.domains.finance.domain.core.finance_context import (
            set_auth,
        )
        set_auth(auth)
    except Exception:
        logger.debug("finance_context.set_auth failed", exc_info=True)
    for module in modules:
        try:
            module.auth = auth
        except Exception:
            logger.debug("could not rebind auth on %s", module, exc_info=True)


# --------------------------------------------------------------------------- #
# Menu loop
# --------------------------------------------------------------------------- #
MenuAction = Callable[[], Any]


def run_menu(title: str, options: Sequence[tuple[str, MenuAction]],
             return_label: Optional[str] = None) -> None:
    """Loop over numbered ``options`` until ``0`` is chosen.

    Each action runs inside a guard so a bad value or a database error returns
    the user to the menu instead of unwinding the whole CLI.
    """
    return_label = return_label or t('menu.return', "Return")
    while True:
        header(title)
        for index, (label, _action) in enumerate(options, 1):
            print(f"{index}. {label}")
        print(f"0. {return_label}")
        print('=' * 60)
        try:
            choice = input(t('menu.enter_choice', "Enter your choice (0-{count}): ",
                             count=len(options))).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if choice == '0':
            return
        try:
            index = int(choice) - 1
        except ValueError:
            index = -1
        if not 0 <= index < len(options):
            print(t('menu.invalid_choice', "Invalid choice."))
            continue
        try:
            options[index][1]()
        except (KeyboardInterrupt, EOFError):
            print('\n' + t('menu.cancelled', "Cancelled."))
        except (ValueError, LookupError) as exc:
            fail(str(exc))
        except Exception as exc:  # keep the menu resilient
            logger.exception("finance CLI action failed")
            fail(t('menu.error', "Error: {error}", error=exc))
        pause()

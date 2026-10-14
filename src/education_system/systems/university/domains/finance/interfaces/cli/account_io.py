"""Prompt and table helpers shared by the student-facing finance CLIs.

Used by ``bank_app`` and ``my_finances``; both act on the logged-in user's own
finance account, so they also share the owner lookup.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from education_system.systems.university.domains.finance.domain.student_account import (
    resolve_account_owner,
    signed_amount,
)
from education_system.systems.university.infrastructure.i18n import get_text


def tr(key: str, default: str = "", **kwargs: Any) -> str:
    """``get_text`` whose English default is also formatted with ``kwargs``.

    The shared i18n engine formats a translated string but returns ``default``
    verbatim, so a placeholder in the fallback would otherwise print as-is.
    """
    text = get_text(key, default=default, **kwargs)
    if kwargs and "{" in text:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def current_user(auth: Any) -> Optional[Dict[str, Any]]:
    user = getattr(auth, "current_user", None)
    return user if isinstance(user, dict) else None


def account_owner(auth: Any) -> Optional[str]:
    """The only account these menus act on: the logged-in user's own."""
    return resolve_account_owner(current_user(auth))


def display_name(user: Optional[Dict[str, Any]], fallback: str) -> str:
    if not user:
        return fallback
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    return name or user.get("username") or fallback


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
def prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def prompt_amount(text: str) -> Optional[float]:
    """A positive money amount, or ``None`` when the user leaves it blank."""
    while True:
        raw = input(f"{text}: ").strip().replace("£", "").replace(",", "")
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            print(get_text("cli.finance.account.invalid_amount", default="Please enter a valid amount."))
            continue
        if value <= 0:
            print(get_text("cli.finance.account.positive_amount", default="Amount must be positive."))
            continue
        return value


def prompt_choice(text: str, options: Sequence[str], default: str) -> str:
    """Pick one of ``options`` by number or name; blank keeps ``default``."""
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option.replace('_', ' ').title()}")
    while True:
        raw = input(f"{text} [{default}]: ").strip().lower()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print(get_text("cli.finance.account.invalid_choice", default="Invalid choice."))


def confirm(text: str) -> bool:
    return input(f"{text} (y/n): ").strip().lower() == "y"


def pause() -> None:
    input("\n" + get_text("cli.finance.account.press_enter", default="Press Enter to continue..."))


def header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def money(amount: Any) -> str:
    return f"£{float(amount or 0):,.2f}"


def short_date(timestamp: str) -> str:
    timestamp = timestamp or ""
    if "T" in timestamp:
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "")).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return timestamp[:16]
    return timestamp[:16]


def print_transactions(transactions: Iterable[Dict[str, Any]], empty_message: str) -> None:
    """Date / Type / Amount / Balance / Description table, newest first."""
    rows: List[Dict[str, Any]] = list(transactions)
    if not rows:
        print(f"\n{empty_message}")
        return
    print(f"\n{'Date':<17}{'Type':<14}{'Amount':>12}{'Balance':>12}  Description")
    print("-" * 80)
    for txn in rows:
        signed = signed_amount(txn.get("type"), txn.get("amount", 0))
        sign = "+" if signed >= 0 else "-"
        print(f"{short_date(txn.get('timestamp', '')):<17}"
              f"{(txn.get('type') or 'unknown').replace('_', ' ').title()[:13]:<14}"
              f"{sign + money(abs(signed)):>12}{money(txn.get('balance_after', 0)):>12}  "
              f"{(txn.get('description') or '')[:34]}")

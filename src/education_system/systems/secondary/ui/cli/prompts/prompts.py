"""Terminal prompts shared by every Secondary School menu.

Enter keeps the current value and ``-`` (:data:`CLEAR`) clears an optional
field wherever :func:`ask` is used.
"""

from __future__ import annotations

from typing import Sequence

CLEAR = "-"


def prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except EOFError:
        return ""


def pause() -> None:
    prompt("\n  Press Enter to continue...")


def yes(msg: str) -> bool:
    return prompt(f"{msg} (y/N): ").lower() in {"y", "yes"}


def ask(label: str, current: str | None = None, *, required: bool = False,
        hint: str = "") -> str | None:
    """Prompt for one field. Returns None to keep the current value (edit),
    "" to clear it, or the new text."""
    shown = f" [{current}]" if current not in (None, "") else ""
    suffix = f" ({hint})" if hint else ""
    raw = prompt(f"  {label}{' *' if required else ''}{suffix}{shown}: ")
    if raw == CLEAR and not required:
        return ""
    if raw == "":
        return None
    return raw


def to_int(text: str | None) -> int | None:
    """``"12"`` -> 12; anything else -> None."""
    text = (text or "").strip()
    return int(text) if text.isdigit() else None


def ask_int(msg: str) -> int | None:
    """Prompt, then :func:`to_int`."""
    return to_int(prompt(msg))


def pick(label: str, options: Sequence[str], default: str | None = None) -> str | None:
    """Show the options numbered on one line; a number picks one, typed text
    is returned as typed, Enter gives *default*."""
    print(f"  {label}: " + ", ".join(f"{i}) {o}" for i, o in enumerate(options, 1)))
    v = prompt(f"  {label}" + (f" [{default}]" if default else "") + ": ")
    if v.isdigit() and 1 <= int(v) <= len(options):
        return options[int(v) - 1]
    return v or default


def problem(e: Exception, heading: str = "Not done:") -> None:
    """Print a refused action: each validation problem on its own line."""
    probs = getattr(e, "problems", None)
    if probs:
        print(f"\n  {heading}")
        for p in probs:
            print(f"   • {p}")
    else:
        print(f"\n  Not done: {e}")

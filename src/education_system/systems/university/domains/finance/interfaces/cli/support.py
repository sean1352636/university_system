"""Console helpers shared by the Finance CLI packages.

Prompting, access gating, table rendering, a numbered menu loop and the
optional "save chart as PNG" path.  Nothing heavy is imported at module level:
matplotlib is only imported inside :func:`save_chart` and only when the user
asks for a PNG.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Roles the Finance GUI treats as staff (``FinanceGUI.is_staff``) plus admin.
STAFF_ROLES: tuple[str, ...] = ("admin", "superadmin", "staff", "instructor", "faculty")
ADMIN_ROLES: tuple[str, ...] = ("admin", "superadmin")


# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #
def text(key: str, default: str, **kwargs: Any) -> str:
    """Translate *key* with an English *default*; never raises."""
    value = default
    try:
        from education_system.systems.university.infrastructure.i18n import get_text

        found = get_text(key, default=default, **kwargs)
        if found and found != key:
            value = found
    except Exception:
        logger.debug("i18n unavailable for %s", key, exc_info=True)
    # get_text only formats translations it found; the English default comes
    # back verbatim, so apply the placeholders here (never raise on a mismatch).
    if kwargs and "{" in value:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return value
    return value


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def prompt_int(label: str, default: int | None = None, *, minimum: int | None = None) -> int | None:
    """Whole-number prompt; blank returns *default* (``None`` when none given)."""
    while True:
        raw = input(f"{label}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print(text("finance_cli.common.whole_number", "Please enter a whole number."))
            continue
        if minimum is not None and value < minimum:
            print(text("finance_cli.common.minimum", "Value must be at least {minimum}.",
                       minimum=minimum))
            continue
        return value


def prompt_float(label: str, default: float | None = None) -> float | None:
    """Decimal prompt; blank returns *default* (``None`` when none given)."""
    while True:
        raw = input(f"{label}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print(text("finance_cli.common.number", "Please enter a number."))


def prompt_bool(label: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"{label} ({hint}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "true", "1")


def prompt_date(label: str, default: str = "", *, allow_blank: bool = False) -> str:
    """ISO date prompt (YYYY-MM-DD); re-asks until valid."""
    while True:
        raw = prompt(label, default)
        if not raw and allow_blank:
            return ""
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            print(text("finance_cli.common.date_format", "Please use the YYYY-MM-DD format."))


def prompt_choice(label: str, options: Sequence[str], default: str | None = None) -> str | None:
    """Numbered pick from *options*; blank returns *default*."""
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    while True:
        raw = input(f"{label}{f' [{default}]' if default else ''}: ").strip()
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
        print(text("finance_cli.common.invalid_choice", "Invalid choice."))


def pause() -> None:
    input("\n" + text("finance_cli.common.press_enter", "Press Enter to continue..."))


def header(title: str, width: int = 60) -> None:
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def confirm_destructive(label: str, keyword: str = "YES") -> bool:
    """Require the user to type *keyword* before a destructive action."""
    raw = input(f"{label} " + text("finance_cli.common.type_to_confirm",
                                   "Type {keyword} to confirm: ", keyword=keyword)).strip()
    return raw == keyword


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def current_username(auth: Any) -> str:
    user = getattr(auth, "current_user", None)
    if isinstance(user, dict):
        return user.get("username") or user.get("name") or "cli-user"
    return "cli-user"


def user_role(auth: Any) -> str:
    """The role string the Finance GUI gates its navigation on, lower-cased."""
    user = getattr(auth, "current_user", None)
    if isinstance(user, dict):
        return str(user.get("role") or "").lower()
    role = getattr(auth, "user_role", None)
    return role.lower() if isinstance(role, str) else ""


def _has_finance_permission(auth: Any) -> bool:
    check = getattr(auth, "check_permission", None)
    if not callable(check):
        return False
    try:
        return bool(check("manage_finances"))
    except Exception:
        logger.debug("check_permission failed", exc_info=True)
        return False


def require_finance_access(auth: Any, *, admin_only: bool = False) -> bool:
    """Gate a menu the way the Finance GUI gates its tabs.

    * Not logged in → denied.
    * ``admin_only`` → role must be admin (the GUI's ``is_admin``).
    * Otherwise → admin or staff role, or the ``manage_finances`` permission.
    """
    if auth is None or not getattr(auth, "current_user", None):
        print(text("finance_cli.common.login_required",
                   "You must be logged in to use this finance area."))
        return False
    role = user_role(auth)
    if role in ADMIN_ROLES:
        return True
    if admin_only:
        print(text("finance_cli.common.admin_only",
                   "This finance area is available to administrators only."))
        return False
    if role in STAFF_ROLES or _has_finance_permission(auth):
        return True
    print(text("finance_cli.common.no_permission",
               "You don't have permission to use this finance area."))
    return False


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def print_table(headers: Sequence[str], rows: Sequence[Sequence[Any]],
                align: Sequence[str] | None = None) -> None:
    """Render *rows* under *headers* with per-column widths.

    *align* is one ``"<"``/``">"`` per column (default: numbers right-aligned).
    """
    cells = [[_fmt(v) for v in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in cells:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    if align is None:
        align = [">" if rows and _is_number(rows[0][i]) else "<" for i in range(len(headers))]
    line = "  ".join(f"{h:{a}{w}}" for h, a, w in zip(headers, align, widths))
    print(line)
    print("-" * len(line))
    for row in cells:
        print("  ".join(f"{c:{a}{w}}" for c, a, w in zip(row, align, widths)))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
    return "" if value is None else str(value)


def money(value: float | None) -> str:
    return f"£{float(value or 0):,.2f}"


# --------------------------------------------------------------------------- #
# Charts (optional, lazy)
# --------------------------------------------------------------------------- #
def chart_available() -> bool:
    try:
        import matplotlib  # noqa: F401
    except Exception:
        return False
    return True


def save_chart(path: str, kind: str, labels: Sequence[str], values: Sequence[float],
               title: str, ylabel: str = "", secondary: Sequence[float] | None = None,
               secondary_label: str = "") -> str:
    """Write a ``pie``/``bar``/``line`` chart to *path* with the Agg backend."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10, 6), dpi=100)
    ax = fig.add_subplot(111)
    if kind == "pie":
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    elif kind == "line":
        ax.plot(labels, values, marker="o", linewidth=2)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis="x", rotation=45)
        ax.set_ylabel(ylabel)
    else:
        ax.bar(range(len(labels)), values)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.grid(axis="y", alpha=0.3)
        ax.set_ylabel(ylabel)
    if secondary is not None and kind != "pie":
        ax2 = ax.twinx()
        ax2.bar(labels, secondary, alpha=0.3, color="gray")
        ax2.set_ylabel(secondary_label, color="gray")
    ax.set_title(title, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    return path


def offer_chart(default_name: str, kind: str, labels: Sequence[str], values: Sequence[float],
                title: str, ylabel: str = "", **kwargs: Any) -> None:
    """Ask whether to save a PNG; silently skipped when matplotlib is absent."""
    if not labels or not chart_available():
        return
    if not prompt_bool(text("finance_cli.common.save_chart", "Save this chart as a PNG?")):
        return
    path = prompt(text("finance_cli.common.png_path", "PNG path"), default_name)
    try:
        save_chart(path, kind, labels, values, title, ylabel, **kwargs)
        print(text("finance_cli.common.chart_saved", "Chart saved to {path}", path=path))
    except Exception as exc:
        print(text("finance_cli.common.chart_failed", "Could not save chart: {error}", error=exc))


# --------------------------------------------------------------------------- #
# Menu loop
# --------------------------------------------------------------------------- #
MenuOption = tuple[str, Callable[[], None]]


def run_menu(title: str, options: Sequence[MenuOption], width: int = 60) -> None:
    """Numbered loop over *options*; ``0`` returns.  Errors never eject the user."""
    while True:
        print("\n" + "=" * width)
        print(f"      {title}")
        print("=" * width)
        for i, (label, _action) in enumerate(options, 1):
            print(f"{i}. {label}")
        print("0. " + text("finance_cli.common.return", "Return"))
        print("=" * width)
        try:
            choice = input("\n" + text("finance_cli.common.enter_choice", "Enter your choice: ")).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if choice == "0":
            return
        action = _pick(options, choice)
        if action is None:
            print(text("finance_cli.common.invalid_choice", "Invalid choice."))
            continue
        try:
            action()
        except KeyboardInterrupt:
            print("\n" + text("finance_cli.common.cancelled", "Cancelled."))
        except EOFError:
            return
        except Exception as exc:
            logger.debug("menu action failed", exc_info=True)
            print(text("finance_cli.common.error", "Error: {error}", error=exc))
        try:
            pause()
        except (KeyboardInterrupt, EOFError):
            return


def _pick(options: Sequence[MenuOption], choice: str) -> Callable[[], None] | None:
    try:
        index = int(choice) - 1
    except ValueError:
        return None
    if 0 <= index < len(options):
        return options[index][1]
    return None


__all__ = [
    "ADMIN_ROLES",
    "STAFF_ROLES",
    "chart_available",
    "confirm_destructive",
    "current_username",
    "header",
    "money",
    "offer_chart",
    "pause",
    "print_table",
    "prompt",
    "prompt_bool",
    "prompt_choice",
    "prompt_date",
    "prompt_float",
    "prompt_int",
    "require_finance_access",
    "run_menu",
    "save_chart",
    "text",
    "user_role",
]

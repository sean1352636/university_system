"""Shared prompts for the Wellbeing Casework CLI menus."""

from __future__ import annotations


def ask(label, default=None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else ("" if default is None else str(default))


def ask_text(label) -> str:
    print(f"{label} (finish with an empty line):")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines).strip()


def yes(label) -> bool:
    return input(f"{label} (y/n): ").strip().lower() in ("y", "yes")


def choose(label, options):
    """Pick one of ``options`` (``[(value, text)]``) by number; ``None`` if blank."""
    for i, (_value, text) in enumerate(options, 1):
        print(f"  {i}. {text}")
    raw = input(f"{label}: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1][0]
    return None


def table(rows, columns, empty="(none)") -> None:
    """Print ``rows`` (dicts) as fixed-width columns ``[(key, label, width)]``."""
    if not rows:
        print(f"  {empty}")
        return
    print("  " + " ".join(label[:w].ljust(w) for _k, label, w in columns))
    for row in rows:
        print("  " + " ".join(str("" if row.get(k) is None else row.get(k))[:w].ljust(w)
                              for k, _l, w in columns))


def run(fn, *args, done=None, **kwargs):
    """Call ``fn``; print a PermissionError / ValueError as it is."""
    try:
        result = fn(*args, **kwargs)
    except (PermissionError, ValueError) as exc:
        print(f"\n❌ {exc}")
        return None
    if done:
        print(f"\n✅ {done}")
    return result


def pause() -> None:
    input("\nPress Enter to continue...")

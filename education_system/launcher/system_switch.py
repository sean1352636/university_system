"""Per-system "Switch System" helper for superadmins.

Each system's main CLI/GUI exposes a "Switch System" option that calls
into here. The helper presents the systems this user can access (other
than the current one), and on selection schedules a
``switch.request_switch(target, mode)`` for the dispatcher to pick up.

Non-superadmin accounts won't usually have access to more than one
system, so ``available_targets`` returns an empty list and callers
should hide the entry point.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Sentinel target understood by the launcher dispatcher (dispatch.py) to
# return a superadmin to the superadmin dashboard rather than a system.
SUPERADMIN_KEY = "__superadmin__"
SUPERADMIN_LABEL = "Superadmin Dashboard"

# Mirrors the SYSTEM_LABELS dict in shared/cli/superadmin_cli.py and
# shared/gui/superadmin_dashboard.py — kept here so this module has no
# circular import.
SYSTEM_LABELS: dict[str, str] = {
    "university": "University",
    "college":    "Sixth Form College",
    "school":     "Secondary School",
    "primary":    "Primary School",
    "nursery":    "Nursery",
}


def available_targets(user_info: dict[str, Any] | None,
                      current_system: str) -> list[tuple[str, str]]:
    """Return ``[(system_key, label)]`` for every system the user has
    access to (other than the one they're already in)."""
    if not user_info:
        return []
    systems = user_info.get("systems") or []
    keys = sorted({
        s["system_key"] for s in systems
        if s.get("system_key") and s["system_key"] != current_system
    })
    return [(k, SYSTEM_LABELS.get(k, k.title())) for k in keys]


def pick_system_cli(user_info: dict[str, Any] | None,
                    current_system: str) -> str | None:
    """Render a numbered system picker on the CLI. Returns the chosen
    system_key (or the superadmin-dashboard sentinel), or None on
    cancel / no targets available."""
    from education_system.launcher.roles import is_superadmin

    targets = available_targets(user_info, current_system)
    if is_superadmin(user_info):
        targets = [*targets, (SUPERADMIN_KEY, SUPERADMIN_LABEL)]
    if not targets:
        print("\n  No other systems available.")
        return None
    print("\n  ── Switch System ──")
    for i, (_, label) in enumerate(targets, 1):
        print(f"    {i}) {label}")
    print("    0) Cancel")
    try:
        raw = input("  Select: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if raw == "0":
        return None
    if not raw.isdigit() or not (1 <= int(raw) <= len(targets)):
        print("  Invalid selection.")
        return None
    target_key = targets[int(raw) - 1][0]
    logger.info("Superadmin requested switch from %s to %s",
                current_system, target_key)
    return target_key


def pick_system_gui(parent, user_info: dict[str, Any] | None,
                    current_system: str) -> str | None:
    """Open a small modal Toplevel and return the chosen system_key
    or None if the user cancelled / has no other systems."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    from education_system.launcher.roles import is_superadmin

    targets = available_targets(user_info, current_system)
    superadmin = is_superadmin(user_info)
    if superadmin:
        targets = [*targets, (SUPERADMIN_KEY, SUPERADMIN_LABEL)]
    if not targets:
        messagebox.showinfo(
            "Switch System",
            "You don't have access to any other systems.",
            parent=parent,
        )
        return None

    chosen: dict[str, str | None] = {"key": None}
    dlg = tk.Toplevel(parent)
    dlg.title("Switch System")
    dlg.transient(parent)
    dlg.grab_set()
    dlg.resizable(False, False)

    body = ttk.Frame(dlg, padding=20)
    body.pack()
    ttk.Label(
        body, text="Switch to:", font=("", 12, "bold"),
    ).pack(anchor="w", pady=(0, 8))

    def _pick(k: str) -> None:
        chosen["key"] = k
        dlg.destroy()

    for key, label in targets:
        if key == SUPERADMIN_KEY:
            ttk.Separator(body, orient="horizontal").pack(
                fill="x", pady=(8, 6))
        ttk.Button(
            body, text=label, width=28,
            command=lambda k=key: _pick(k),
        ).pack(anchor="w", pady=2)

    ttk.Button(body, text="Cancel",
               command=dlg.destroy).pack(anchor="w", pady=(10, 0))

    parent.wait_window(dlg)
    if chosen["key"]:
        logger.info("Superadmin requested switch from %s to %s",
                    current_system, chosen["key"])
    return chosen["key"]

"""Standalone Academic Appeals window (students: their own appeals; staff: all).

Launched as a subprocess by the main GUI (``_NEW_FEATURE_MODULES``), so the
signed-in user arrives through the ``EDU_AUTH_*`` env bundle and is resolved by
``require_launcher_auth``. Staff also reach the same panel as a tab of Case
Management. Nothing touches the DB at import time.
"""
from __future__ import annotations

import pathlib
import sys
import tkinter as tk
from tkinter import messagebox

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

from education_system.systems.university.infrastructure.i18n import get_text as _t  # noqa: E402

TITLE = "Academic Appeals"
ALLOWED_ROLES = ("student", "admin", "administrator", "superadmin", "staff", "registrar")


def main() -> None:
    from education_system.platform.delivery.gui.window_sizing import install
    from education_system.systems.university.domains.governance.interfaces.gui.case_management.appeals_panel import (  # noqa: E501
        AppealsPanel,
    )
    from education_system.systems.university.shell.gui.auth.launch_guard import require_launcher_auth

    user = require_launcher_auth(TITLE)
    if user is None:
        return
    if str(user.get("role", "")).lower() not in ALLOWED_ROLES:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(TITLE, "Academic appeals are for students and appeals staff.",
                             parent=root)
        root.destroy()
        return
    install()
    root = tk.Tk()
    root.title(_t("gui.governance.appeals.title", default=TITLE))
    root.geometry("1400x900")
    root.minsize(1200, 800)
    AppealsPanel(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()

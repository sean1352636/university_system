"""Standalone Tk launcher for the Employer Portal."""
from __future__ import annotations

import sys, pathlib  # noqa: E401
_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

import tkinter as tk

from education_system.university_system.modules.domain.student_affairs.employer_portal.gui.employer_portal_gui import (
    EmployerPortalFrame,
)


def main() -> None:
    root = tk.Tk()
    root.title("Employer Portal")
    root.geometry("980x640")
    EmployerPortalFrame(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()

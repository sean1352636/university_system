
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from tkinter.simpledialog import Dialog

_K = 'gui.operations.campus.mobility.trip_management_gui.about_dialog'


def app_versions():
    """``(university_version, package_version)`` from the real sources.

    The University system's ``__version__`` and the installed
    ``education_system`` distribution version (pyproject); either is
    ``None`` when it cannot be read.
    """
    university = package = None
    try:
        from education_system.systems import university as _university
        university = getattr(_university, '__version__', None)
    except Exception:
        university = None
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            package = version('education_system')
        except PackageNotFoundError:
            package = version('education-system')
    except Exception:
        package = None
    return university, package


class AboutDialog(Dialog):
    def __init__(self, parent):
        super().__init__(parent, _t(f"{_K}.windows.about", default="About Trip Management System"))

    def body(self, master):
        ttk.Label(master, text="\U0001f392", font=('Arial', 48)).pack(pady=10)
        ttk.Label(master, text=_t(f"{_K}.labels.trip_management_system", default="Trip Management System"),
                  font=('Arial', 16, 'bold')).pack(pady=5)

        university, package = app_versions()
        parts = []
        if university:
            parts.append(f"University System {university}")
        if package:
            parts.append(f"Education System {package}")
        ttk.Label(master, text=" · ".join(parts) or _t(f"{_K}.labels.version_unknown", default="Version unknown")).pack(pady=2)

        description = _t(f"{_K}.labels.description", default=(
            "Planning, approving and running university and Students' Union trips.\n\n"
            "Features:\n"
            "• Trip creation, approval and risk assessment\n"
            "• Registration, waiting lists, payments and refunds\n"
            "• Staffing, safeguarding and overseas checks\n"
            "• Incidents, roll calls and emergency cards\n"
            "• Budgets, reconciliation and evaluations\n"
            "• Calendar integration and reports"))
        ttk.Label(master, text=description, justify=tk.LEFT).pack(pady=20, padx=20)

        ttk.Label(master, text=f"© {datetime.now().year} " + _t(f"{_K}.labels.copyright_holder", default="Education System"),
                  font=('Arial', 8)).pack(pady=5)
        return None

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text=_t(f"{_K}.buttons.close", default="Close"), command=self.ok).pack()
        box.pack(pady=10)

"""Shared launchers for the three evaluation portals.

The evaluation modules are standalone Tk apps that own their own
``tk.Tk()`` root, so the dashboards spawn them as subprocesses (mirroring
``main_gui._launch_new_feature_module``) rather than embedding them.
"""

import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

EVALUATION_MODULES = (
    ("Course Evaluation",
     "education_system.university_system.modules.domain.academics.gui.course_management_gui.course_evaluation_system"),
    ("Module Evaluation",
     "education_system.university_system.modules.domain.academics.gui.course_management_gui.module_evaluation_portal"),
    ("Lecturer Evaluation",
     "education_system.university_system.modules.domain.academics.gui.course_management_gui.lecturer_evaluation"),
)


def _build_auth_env(auth):
    """Return an env dict with EDU_AUTH_* propagated from the auth instance."""
    env = os.environ.copy()
    try:
        cu = (auth.current_user if auth is not None else None) or {}
        if cu:
            env['EDU_AUTH_USER_ID'] = str(cu.get('id', '') or cu.get('user_id', ''))
            env['EDU_AUTH_USERNAME'] = str(cu.get('username', '') or '')
            env['EDU_AUTH_ROLE'] = str(cu.get('role', '') or '')
            env['EDU_AUTH_EMAIL'] = str(cu.get('email', '') or '')
            perms = cu.get('permissions') or []
            if isinstance(perms, (list, tuple, set)):
                env['EDU_AUTH_PERMISSIONS'] = ','.join(str(p) for p in perms)
    except Exception:
        logger.exception("failed to build auth env")
    return env


def launch_evaluation_module(parent, auth, module_dotted: str, label: str) -> None:
    """Spawn an evaluation portal as a subprocess with EDU_AUTH_* env."""
    try:
        spec = importlib.util.find_spec(module_dotted)
    except Exception:
        spec = None
        logger.exception("find_spec failed for %s", module_dotted)
    origin = getattr(spec, "origin", None) if spec else None
    if not origin:
        logger.error("could not locate %s on disk", module_dotted)
        try:
            from tkinter import messagebox
            messagebox.showerror("Launch failed",
                                 f"Could not locate {label} on disk.",
                                 parent=parent)
        except Exception:
            pass
        return

    def _set_pdeathsig():
        try:
            import ctypes
            import signal
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            libc.prctl(1, signal.SIGTERM, 0, 0, 0)  # PR_SET_PDEATHSIG = 1
        except Exception:
            pass

    popen_kwargs = {
        "cwd": str(Path(origin).parent),
        "env": _build_auth_env(auth),
    }
    if sys.platform.startswith("linux"):
        popen_kwargs["preexec_fn"] = _set_pdeathsig

    try:
        subprocess.Popen([sys.executable, origin], **popen_kwargs)
        logger.info("launched %s -> %s", label, origin)
    except Exception as e:
        logger.exception("Popen failed for %s", label)
        try:
            from tkinter import messagebox
            messagebox.showerror("Launch failed",
                                 f"Could not launch {label}:\n{e}",
                                 parent=parent)
        except Exception:
            pass

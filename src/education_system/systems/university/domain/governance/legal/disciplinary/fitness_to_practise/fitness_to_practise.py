"""University Fitness to Practise (FtP) Portal — entry point shim.

Specialist disciplinary surface for students on regulated programmes
(NMC, HCPC, GMC, GPhC, GTC, etc.). The implementation lives in
``services/ftp_service.py`` (data access) and ``gui/ftp_portal_gui.py``
(Tk portal); this file is the subprocess entry point and a backward-
compatible re-export.

Conventions match disciplinary_portal.py: env-var auth bootstrap when
launched as a subprocess by the main GUI.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk

# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# ``education_system`` isn't importable. Walk up from this file until
# we find the dir that contains the ``education_system`` package and
# put it on sys.path. No-op when imported normally.
if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(
            os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


# ============================================================
# AUTH BOOTSTRAP (mirrors disciplinary_portal.py)
# ============================================================
def _bootstrap_auth_from_env():
    """Rebuild a global auth instance from EDU_AUTH_* env vars when
    launched as a subprocess. No-op when running standalone."""
    user_id = os.environ.get('EDU_AUTH_USER_ID')
    username = os.environ.get('EDU_AUTH_USERNAME')
    if not (user_id or username):
        return
    perms = [p for p in os.environ.get(
        'EDU_AUTH_PERMISSIONS', '').split(',') if p]
    current_user = {
        'id': user_id or None,
        'user_id': user_id or None,
        'username': username or '',
        'role': os.environ.get('EDU_AUTH_ROLE', '') or '',
        'email': os.environ.get('EDU_AUTH_EMAIL', '') or '',
        'permissions': perms,
    }
    try:
        from types import SimpleNamespace

        def _check_permission(perm, _u=current_user):
            return perm in _u['permissions']

        shim = SimpleNamespace(
            current_user=current_user,
            user_role=current_user['role'],
            check_permission=_check_permission,
            is_authenticated=True,
        )
        from education_system.systems.university.infrastructure.auth import (
            set_global_auth,
        )
        set_global_auth(shim)
    except Exception:
        pass


_bootstrap_auth_from_env()


# Backward-compat re-exports. Existing imports
# ``from ...fitness_to_practise import FtPDataAccess`` /
# ``FitnessToPractisePortal`` continue to resolve here.
from education_system.systems.university.domain.governance.legal.disciplinary.fitness_to_practise.services.ftp_service import (  # noqa: E402, E501
    FtPDataAccess,
    current_username as _current_username,
)
from education_system.systems.university.interfaces.gui.governance.legal.disciplinary.fitness_to_practise.ftp_portal_gui import (  # noqa: E402, E501
    FitnessToPractisePortal,
)


__all__ = ["FtPDataAccess", "FitnessToPractisePortal"]


# ============================================================
# ENTRY POINT
# ============================================================
def main():
    root = tk.Tk()
    FitnessToPractisePortal(root)
    root.mainloop()


if __name__ == "__main__":
    main()

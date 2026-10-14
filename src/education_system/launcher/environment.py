"""Launch-time environment defaults for the launcher.

Deliberately dependency-free — it imports nothing from the package — so both
:mod:`education_system.launcher.main` (at import time, beside the ``.env`` load)
and :mod:`education_system.launcher.systems` can call it without dragging in
auth, tkinter, or any system package.
"""

from __future__ import annotations

import os

#: ``EDU_PRODUCTION`` values that opt a launcher run back into strict behaviour.
_TRUTHY = ("1", "true", "yes")

#: ``APP_ENV`` value used when the launcher has to pick one.
_LAUNCHER_DEFAULT = "development"


def apply_launcher_env_defaults() -> str:
    """Name the environment for a launcher run that hasn't declared one.

    Every fail-closed secret guard in the platform reads
    ``os.getenv("APP_ENV", "production")`` — the audit log's ``AUDIT_LOG_SECRET``,
    CSRF's ``CSRF_SECRET``, log integrity's ``LOG_HMAC_KEY``, field encryption's
    ``ENCRYPTION_KEY``. An unset ``APP_ENV`` therefore counts as production and
    those guards refuse to run without real secrets. That is the right default
    for a deployment and the wrong one for ``python -m education_system`` in a
    source checkout, where it kills the first audit write and takes the
    surrounding transaction with it.

    The launcher is a local entry point, so it states the environment instead of
    leaving it to be inferred. Two things are never overridden: an explicit
    ``APP_ENV``, and ``EDU_PRODUCTION`` set truthy — which ``.env.example``
    documents as forcing strict secret enforcement, and which consequently has
    to select production here rather than fall through to the dev default.

    Returns:
        The ``APP_ENV`` value in effect once the default has been applied.
    """
    declared = os.getenv("APP_ENV", "").strip()
    if declared:
        return declared

    forced_production = os.getenv("EDU_PRODUCTION", "").strip().lower() in _TRUTHY
    os.environ["APP_ENV"] = "production" if forced_production else _LAUNCHER_DEFAULT
    return os.environ["APP_ENV"]


__all__ = ["apply_launcher_env_defaults"]

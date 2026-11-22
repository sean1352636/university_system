"""The single source of truth for every filesystem path in the platform.

This module replaces the nine per-system ``paths.py`` modules that previously
each defined their own roots, data directories and database constants. Those
modules disagreed on 60 of their 225 names — ``DATA_DIR``, ``STAFF_DB``,
``ensure_directories`` and others meant different files in different packages,
so the same logical database resolved differently depending on which module a
caller happened to import.

Every name is therefore prefixed with the system that owns it
(``UNIVERSITY_``, ``SIXTH_FORM_``, ``FE_COLLEGE_``, ``SECONDARY_``, ``PRIMARY_``,
``NURSERY_``, ``APPRENTICESHIPS_``, ``PLATFORM_``). Only the three anchors that
are genuinely identical across all of them — :data:`PROGRAM_ROOT`,
:data:`VAR_DIR` and :data:`REPO_ROOT` — are left unprefixed.

Runtime state lives in one gitignored tree under ``var`` (ADR 0018),
never inside the importable package.

IMPORTANT: Directories are NOT created on import. Call the relevant
``ensure_*_directories()`` during application initialisation, or
:func:`ensure_all_directories` to create every system's tree at once.

This module depends on nothing beyond the standard library, so it can be
imported from anywhere without risking a circular import.

Layout: ``core`` (roots, backups, config permissions), ``platform_shared``,
``systems/<system>``, ``registry``; ``_exports`` holds ``__all__``. Every name
is re-exported here, so ``paths.X`` and ``from education_system.paths import X``
work as before. The functions below stay in this namespace on purpose: tests
monkeypatch ``paths.<NAME>`` and these functions must see the patched value.
"""

from __future__ import annotations

import importlib as _importlib
import os
import stat
import sys as _sys
from pathlib import Path

# Load the parts in dependency order. ``importlib.reload(paths)`` re-runs only
# this file, so on a reload each part is reloaded too: that is what lets the
# EDU_*_DATA_DIR overrides take effect, exactly as with the old single module.
_PARTS = ('core', 'platform_shared', 'systems.nursery', 'systems.primary', 'systems.secondary', 'systems.sixth_form', 'systems.university', 'systems.fe_college', 'systems.apprenticeships', 'systems.special_education', 'systems.adult_education', 'systems.alternative_provision', 'systems.training_provider', 'systems.local_authority', 'registry')
for _part in _PARTS:
    _qualname = f"{__name__}.{_part}"
    if _qualname in _sys.modules:
        _importlib.reload(_sys.modules[_qualname])
    else:
        _importlib.import_module(_qualname)
del _part, _qualname

from education_system.paths.core import *  # noqa: F403
from education_system.paths.platform_shared import *  # noqa: F403
from education_system.paths.systems.nursery import *  # noqa: F403
from education_system.paths.systems.primary import *  # noqa: F403
from education_system.paths.systems.secondary import *  # noqa: F403
from education_system.paths.systems.sixth_form import *  # noqa: F403
from education_system.paths.systems.university import *  # noqa: F403
from education_system.paths.systems.fe_college import *  # noqa: F403
from education_system.paths.systems.apprenticeships import *  # noqa: F403
from education_system.paths.systems.special_education import *  # noqa: F403
from education_system.paths.systems.adult_education import *  # noqa: F403
from education_system.paths.systems.alternative_provision import *  # noqa: F403
from education_system.paths.systems.training_provider import *  # noqa: F403
from education_system.paths.systems.local_authority import *  # noqa: F403
from education_system.paths.registry import *  # noqa: F403
from education_system.paths.core import (
    BACKUP_DIR,
    _CONFIG_DIR_MODE,
    _CONFIG_FILE_MODE,
    _ensure,
    harden_config_permissions,
    MAINTENANCE_BACKUP_DIR,
    MAINTENANCE_BACKUP_KEEP,
    MAINTENANCE_BACKUP_MAX_AGE_DAYS,
    _MAINTENANCE_RUN_RE,
    _SYSTEMS_ROOT,
)
from education_system.paths.platform_shared import (
    PLATFORM_CONFIG_DIR,
    PLATFORM_DATA_DIR,
    PLATFORM_DB_FILES_DIR,
    PLATFORM_DOCUMENTS_DIR,
    PLATFORM_LOGS_DIR,
)
from education_system.paths.systems.nursery import (
    NURSERY_DATA_DIR,
)
from education_system.paths.systems.primary import (
    PRIMARY_DATA_DIR,
)
from education_system.paths.systems.secondary import (
    SECONDARY_DATA_DIR,
    SECONDARY_LOG_DIR,
)
from education_system.paths.systems.special_education import (
    SPECIAL_EDUCATION_DATA_DIR,
)
from education_system.paths.systems.alternative_provision import (
    ALTERNATIVE_PROVISION_DATA_DIR,
)
from education_system.paths.systems.training_provider import (
    TRAINING_PROVIDER_DATA_DIR,
)
from education_system.paths.systems.local_authority import (
    LOCAL_AUTHORITY_DATA_DIR,
)
from education_system.paths.systems.adult_education import (
    ADULT_EDUCATION_DATA_DIR,
)
from education_system.paths.systems.sixth_form import (
    SIXTH_FORM_COURSEWORK_FILES_DIR,
    SIXTH_FORM_DATA_DIR,
)
from education_system.paths.systems.university import (
    UNIVERSITY_ANALYTICS_DIR,
    UNIVERSITY_ANALYTICS_PLOTS_DIR,
    UNIVERSITY_ANALYTICS_REPORTS_DIR,
    UNIVERSITY_ASSIGNMENT_TEMPLATES_DIR,
    UNIVERSITY_BACKUP_ASSIGNMENTS_DIR,
    UNIVERSITY_BACKUP_ATTENDANCE_DIR,
    UNIVERSITY_BACKUP_CALENDAR_DIR,
    UNIVERSITY_BACKUP_DATABASE_DIR,
    UNIVERSITY_BACKUP_FILES_DIR,
    UNIVERSITY_BACKUP_FINANCE_DIR,
    UNIVERSITY_BACKUP_HEALTH_DIR,
    UNIVERSITY_BACKUP_LIBRARY_DIR,
    UNIVERSITY_BACKUP_SAFETY_DIR,
    UNIVERSITY_BACKUP_SETTINGS_DIR,
    UNIVERSITY_BACKUP_SUBMISSIONS_DIR,
    UNIVERSITY_BACKUP_TEMPLATES_DIR,
    UNIVERSITY_BRANDING_DIR,
    UNIVERSITY_CHARTS_DIR,
    UNIVERSITY_CHATBOT_DATA_DIR,
    UNIVERSITY_CHATBOT_MODELS_DIR,
    UNIVERSITY_CHATBOT_UPLOAD_DIR,
    UNIVERSITY_CONFIG_DIR,
    UNIVERSITY_DATA_DIR,
    UNIVERSITY_DATA_TEMPLATES_DIR,
    UNIVERSITY_DB_DIR,
    UNIVERSITY_DOCUMENT_TEMPLATES_DIR,
    UNIVERSITY_EMAIL_DATA_DIR,
    UNIVERSITY_EMAIL_REMINDER_TEMPLATES_DIR,
    UNIVERSITY_EMAIL_TEMPLATES_DIR,
    UNIVERSITY_EXPORTS_BAKERY_DIR,
    UNIVERSITY_EXPORTS_DATABASE_DIR,
    UNIVERSITY_EXPORTS_PDF_DIR,
    UNIVERSITY_EXPORTS_REPORTS_DIR,
    UNIVERSITY_EXPORTS_SUBMISSIONS_DIR,
    UNIVERSITY_EXPORTS_TICKETS_DIR,
    UNIVERSITY_FINANCE_TEMPLATES_DIR,
    UNIVERSITY_LOCALES_DIR,
    UNIVERSITY_LOG_DIR,
    UNIVERSITY_LOGGER_CONFIG_DIR,
    UNIVERSITY_MEDICAL_TEMPLATES_DIR,
    UNIVERSITY_NLTK_DATA_DIR,
    UNIVERSITY_QR_CODES_DIR,
    UNIVERSITY_REPORT_CACHE_DIR,
    UNIVERSITY_REPORT_TEMPLATES_DIR,
    UNIVERSITY_REPORTS_DIR,
    _university_resolve_email_config_file,
    UNIVERSITY_SEED_TEMPLATES_DIR,
    UNIVERSITY_STUDENT_DOCUMENTS_DIR,
    UNIVERSITY_SUBMISSIONS_DIR,
    UNIVERSITY_TEMP_DIR,
    UNIVERSITY_TEMPLATE_REGISTRY_DIR,
    UNIVERSITY_TEMPLATES_DIR,
    UNIVERSITY_TICKET_TEMPLATES_DIR,
    UNIVERSITY_UI_TEMPLATES_DIR,
    UNIVERSITY_UPLOAD_DIR,
    UNIVERSITY_USER_BACKUP_TEMPLATES_DIR,
)
from education_system.paths.systems.fe_college import (
    FE_COLLEGE_DATA_DIR,
    FE_COLLEGE_EXPORTS_DIR,
    FE_COLLEGE_LOG_DIR,
    FE_COLLEGE_SUBMISSIONS_DIR,
)
from education_system.paths.systems.apprenticeships import (
    APPRENTICESHIPS_DATA_DIR,
    APPRENTICESHIPS_DOCUMENTS_DIR,
    APPRENTICESHIPS_EVIDENCE_DIR,
    APPRENTICESHIPS_EXPORTS_DIR,
    APPRENTICESHIPS_LOG_DIR,
)
from education_system.paths._exports import __all__


def system_backup_dir(system_key: str, category: str | None = None) -> Path:
    """Return the backup directory for *system_key*, optionally by category.

    ``system_backup_dir("university", "database")`` ->
    ``var/backups/university/database``. Unknown keys still resolve under
    :data:`BACKUP_DIR` rather than escaping the tree.
    """
    base = BACKUP_DIR / system_key
    return base / category if category else base


def _maintenance_run_sort_key(run: Path) -> tuple[float, str]:
    """Order a run directory by the date in its name, falling back to mtime.

    Names are not uniformly ``%Y%m%d_%H%M%S``; the tree also holds forms like
    ``20260815_pre_seed`` and ``20260812_110613_pre_restore``. Parsing only the
    leading stamp orders those correctly, and mtime breaks ties between runs
    that share a date but carry no time.
    """
    import re
    from datetime import datetime as _dt

    try:
        mtime = run.stat().st_mtime
    except OSError:
        mtime = 0.0
    match = re.match(_MAINTENANCE_RUN_RE, run.name)
    if not match:
        return (mtime, run.name)
    day, time_part = match.group(1), match.group(2)
    try:
        parsed = _dt.strptime(day + (time_part or "000000"), "%Y%m%d%H%M%S")
    except ValueError:
        return (mtime, run.name)
    # A dateless name sorts at the start of its day; mtime separates same-day runs.
    return (parsed.timestamp() if time_part else mtime, run.name)


def prune_maintenance_backups(
    label: str,
    *,
    keep: int = MAINTENANCE_BACKUP_KEEP,
    max_age_days: int = MAINTENANCE_BACKUP_MAX_AGE_DAYS,
    exclude: Path | None = None,
    dry_run: bool = False,
) -> list[Path]:
    """Delete superseded run directories under ``maintenance/<label>``.

    The newest *keep* runs are always retained. Of what remains, a run is
    deleted once it is older than *max_age_days*. Pass ``max_age_days=0`` for a
    strict keep-the-newest-N rule with no age reprieve.

    Only immediate subdirectories whose name begins with a date stamp are
    considered, so loose files sitting directly in the label directory and
    hand-named drops are left alone. *exclude* is never removed — callers pass
    the run they are about to write into.

    Returns the directories removed, or the ones that would be removed when
    *dry_run* is set. Missing labels return ``[]`` rather than raising.
    """
    import shutil
    from datetime import datetime as _dt, timedelta as _td

    # Validate the label before touching the filesystem: a label that escapes
    # the tree must raise, not quietly resolve to nothing because the traversal
    # target happens not to exist.
    if (
        not label
        or label in (".", "..")
        or "/" in label
        or "\\" in label
        or Path(label).is_absolute()
    ):
        raise ValueError(f"maintenance label escapes the backup tree: {label!r}")

    base = MAINTENANCE_BACKUP_DIR / label
    if not base.is_dir():
        return []

    import re
    runs = sorted(
        (p for p in base.iterdir() if p.is_dir() and re.match(_MAINTENANCE_RUN_RE, p.name)),
        key=_maintenance_run_sort_key,
        reverse=True,
    )
    keep = max(keep, 0)
    candidates = runs[keep:]

    if max_age_days > 0:
        cutoff = (_dt.now() - _td(days=max_age_days)).timestamp()
        candidates = [p for p in candidates if _maintenance_run_sort_key(p)[0] < cutoff]

    excluded = exclude.resolve() if exclude is not None else None
    removed: list[Path] = []
    for run in candidates:
        if excluded is not None and run.resolve() == excluded:
            continue
        if not dry_run:
            shutil.rmtree(run)
        removed.append(run)
    return removed


def maintenance_backup_dir(
    label: str,
    timestamp: str | None = None,
    *,
    create: bool = False,
    prune: bool | None = None,
) -> Path:
    """Return ``var/backups/maintenance/<label>/<timestamp>``.

    For the pre-change safety copies taken by repair scripts and one-off
    tooling. By default this only computes a path — nothing is created and
    nothing is deleted, so it stays safe to call just to locate a backup.

    Pass ``create=True`` to make the directory and apply the retention rule in
    :func:`prune_maintenance_backups`, which is how a script taking a fresh
    backup should call it. Pruning follows *create* unless *prune* overrides it;
    the run being created is never itself a prune candidate.
    """
    from datetime import datetime as _dt
    stamp = timestamp or _dt.now().strftime("%Y%m%d_%H%M%S")
    target = MAINTENANCE_BACKUP_DIR / label / stamp
    if create:
        target.mkdir(parents=True, exist_ok=True)
    if prune if prune is not None else create:
        prune_maintenance_backups(label, exclude=target)
    return target


# ═════════════════════════════════════════════════════════════════════
# Directory creation
# ═════════════════════════════════════════════════════════════════════


def ensure_platform_directories() -> None:
    """Create the runtime directory structure. Safe to call repeatedly."""
    for d in (PLATFORM_DATA_DIR, PLATFORM_DB_FILES_DIR, PLATFORM_CONFIG_DIR, PLATFORM_DOCUMENTS_DIR, PLATFORM_LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    harden_config_permissions(PLATFORM_CONFIG_DIR)


def ensure_nursery_directories() -> None:
    NURSERY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_primary_directories() -> None:
    PRIMARY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_secondary_directories() -> None:
    """Create the data and log directories if they don't exist yet."""
    SECONDARY_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SECONDARY_LOG_DIR.mkdir(parents=True, exist_ok=True)


def ensure_adult_education_directories() -> None:
    """Create the Adult Education data directory if it doesn't exist yet."""
    ADULT_EDUCATION_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_alternative_provision_directories() -> None:
    """Create the Alternative Provision data directory if it doesn't exist yet."""
    ALTERNATIVE_PROVISION_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_training_provider_directories() -> None:
    """Create the Training Provider data directory if it doesn't exist yet."""
    TRAINING_PROVIDER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_local_authority_directories() -> None:
    """Create the Local Authority Education data directory if it doesn't exist yet."""
    LOCAL_AUTHORITY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_special_education_directories() -> None:
    """Create the SEND data directory if it doesn't exist yet."""
    SPECIAL_EDUCATION_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_sixth_form_directories() -> None:
    """Create any directories listed above. Safe to call repeatedly."""
    SIXTH_FORM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SIXTH_FORM_COURSEWORK_FILES_DIR.mkdir(parents=True, exist_ok=True)


def ensure_fe_college_directories() -> None:
    """Create the FE College runtime tree. Safe to call repeatedly."""
    FE_COLLEGE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    FE_COLLEGE_SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    FE_COLLEGE_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FE_COLLEGE_LOG_DIR.mkdir(parents=True, exist_ok=True)


def ensure_apprenticeships_directories() -> None:
    """Create the apprenticeships runtime tree. Safe to call repeatedly."""
    APPRENTICESHIPS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    APPRENTICESHIPS_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    APPRENTICESHIPS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    APPRENTICESHIPS_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    APPRENTICESHIPS_LOG_DIR.mkdir(parents=True, exist_ok=True)


def ensure_university_directories() -> None:
    """
    Explicitly create all required directories.

    This function should be called during application bootstrap/initialization,
    not at import time. This keeps imports side-effect free.
    """
    _ensure(UNIVERSITY_DATA_DIR)
    _ensure(UNIVERSITY_DB_DIR)
    _ensure(UNIVERSITY_LOG_DIR)
    _ensure(UNIVERSITY_CONFIG_DIR)
    harden_config_permissions(UNIVERSITY_CONFIG_DIR)
    # Backup subdirectories
    _ensure(UNIVERSITY_BACKUP_DATABASE_DIR)
    _ensure(UNIVERSITY_BACKUP_FILES_DIR)
    _ensure(UNIVERSITY_BACKUP_ATTENDANCE_DIR)
    _ensure(UNIVERSITY_BACKUP_FINANCE_DIR)
    _ensure(UNIVERSITY_BACKUP_LIBRARY_DIR)
    _ensure(UNIVERSITY_BACKUP_HEALTH_DIR)
    _ensure(UNIVERSITY_BACKUP_SETTINGS_DIR)
    _ensure(UNIVERSITY_BACKUP_CALENDAR_DIR)
    _ensure(UNIVERSITY_BACKUP_SUBMISSIONS_DIR)
    _ensure(UNIVERSITY_BACKUP_SAFETY_DIR)
    _ensure(UNIVERSITY_BACKUP_ASSIGNMENTS_DIR)
    # Export subdirectories
    _ensure(UNIVERSITY_EXPORTS_DATABASE_DIR)
    _ensure(UNIVERSITY_EXPORTS_PDF_DIR)
    _ensure(UNIVERSITY_EXPORTS_TICKETS_DIR)
    _ensure(UNIVERSITY_EXPORTS_SUBMISSIONS_DIR)
    _ensure(UNIVERSITY_EXPORTS_REPORTS_DIR)
    _ensure(UNIVERSITY_EXPORTS_BAKERY_DIR)
    _ensure(UNIVERSITY_REPORTS_DIR)
    _ensure(UNIVERSITY_REPORT_TEMPLATES_DIR)
    _ensure(UNIVERSITY_REPORT_CACHE_DIR)
    _ensure(UNIVERSITY_EMAIL_DATA_DIR)
    _ensure(UNIVERSITY_EMAIL_TEMPLATES_DIR)
    _ensure(UNIVERSITY_LOGGER_CONFIG_DIR)
    _ensure(UNIVERSITY_CHATBOT_DATA_DIR)
    _ensure(UNIVERSITY_CHATBOT_UPLOAD_DIR)
    _ensure(UNIVERSITY_CHATBOT_MODELS_DIR)
    _ensure(UNIVERSITY_QR_CODES_DIR)
    _ensure(UNIVERSITY_ANALYTICS_DIR)
    _ensure(UNIVERSITY_ANALYTICS_PLOTS_DIR)
    _ensure(UNIVERSITY_ANALYTICS_REPORTS_DIR)
    _ensure(UNIVERSITY_SUBMISSIONS_DIR)
    _ensure(UNIVERSITY_UPLOAD_DIR)
    _ensure(UNIVERSITY_TEMPLATES_DIR)
    _ensure(UNIVERSITY_TEMPLATE_REGISTRY_DIR)
    _ensure(UNIVERSITY_UI_TEMPLATES_DIR)
    _ensure(UNIVERSITY_DOCUMENT_TEMPLATES_DIR)
    _ensure(UNIVERSITY_DATA_TEMPLATES_DIR)
    _ensure(UNIVERSITY_SEED_TEMPLATES_DIR)
    _ensure(UNIVERSITY_ASSIGNMENT_TEMPLATES_DIR)
    _ensure(UNIVERSITY_BACKUP_TEMPLATES_DIR)
    _ensure(UNIVERSITY_USER_BACKUP_TEMPLATES_DIR)
    _ensure(UNIVERSITY_MEDICAL_TEMPLATES_DIR)
    _ensure(UNIVERSITY_TICKET_TEMPLATES_DIR)
    _ensure(UNIVERSITY_EMAIL_REMINDER_TEMPLATES_DIR)
    _ensure(UNIVERSITY_FINANCE_TEMPLATES_DIR)
    _ensure(UNIVERSITY_NLTK_DATA_DIR)
    _ensure(UNIVERSITY_STUDENT_DOCUMENTS_DIR)
    _ensure(UNIVERSITY_BRANDING_DIR)
    _ensure(UNIVERSITY_TEMP_DIR)
    _ensure(UNIVERSITY_CONFIG_DIR)
    _ensure(UNIVERSITY_CHARTS_DIR)
    _ensure(UNIVERSITY_LOCALES_DIR)


def ensure_all_directories() -> None:
    """Create every system's runtime tree. Safe to call repeatedly."""
    ensure_platform_directories()
    ensure_nursery_directories()
    ensure_primary_directories()
    ensure_secondary_directories()
    ensure_sixth_form_directories()
    ensure_university_directories()
    ensure_fe_college_directories()
    ensure_apprenticeships_directories()
    ensure_special_education_directories()
    ensure_adult_education_directories()
    ensure_alternative_provision_directories()
    ensure_training_provider_directories()
    ensure_local_authority_directories()

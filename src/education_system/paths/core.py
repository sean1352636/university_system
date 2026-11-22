"""Roots, the backup tree, package roots and config-file permissions.

Part of :mod:`education_system.paths`; import names from the package, not from here.
"""

from __future__ import annotations

from pathlib import Path
import stat

# ═══════════════════════════════════════════════════════════════════════
# Roots
# ═══════════════════════════════════════════════════════════════════════

# `.../src/education_system/paths/core.py` -> the `education_system` package.
EDUCATION_SYSTEM_ROOT: Path = Path(__file__).resolve().parent.parent
# -> the `src` directory holding the installable package.
SRC_ROOT: Path = EDUCATION_SYSTEM_ROOT.parent
# -> the repository root, which holds src/, tests/, docs/, tools/ and var/.
REPO_ROOT: Path = SRC_ROOT.parent

# Deprecated alias from the old `program/` layout, where the package parent and
# the runtime-state anchor were the same directory. They no longer are: this now
# points at `src/`. Anchor runtime state on VAR_DIR and repo files on REPO_ROOT.
PROGRAM_ROOT: Path = SRC_ROOT

# Runtime state lives in one gitignored tree at the repository root (ADR 0018).
VAR_DIR: Path = REPO_ROOT / "var"

# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------
# Every backup this project writes belongs under BACKUP_DIR and nowhere else.
# Backups used to be scattered — some under ``var/backups/<system>``, some
# under ``var/data/university/backups/``, some in ad-hoc one-off directories —
# which made them hard to find when they were actually needed. Route new
# backups through ``system_backup_dir()`` or ``maintenance_backup_dir()``
# rather than composing a path of your own.
BACKUP_DIR: Path = VAR_DIR / "backups"

#: One directory per system, holding that system's routine//automated backups.
NURSERY_BACKUP_DIR: Path = BACKUP_DIR / "nursery"
PRIMARY_BACKUP_DIR: Path = BACKUP_DIR / "primary"
SECONDARY_BACKUP_DIR: Path = BACKUP_DIR / "secondary"
SIXTH_FORM_BACKUP_DIR: Path = BACKUP_DIR / "sixth_form"
FE_COLLEGE_BACKUP_DIR: Path = BACKUP_DIR / "fe_college"
APPRENTICESHIPS_BACKUP_DIR: Path = BACKUP_DIR / "apprenticeships"
PLATFORM_BACKUP_DIR: Path = BACKUP_DIR / "platform"

#: One-off backups taken before a manual repair, migration or cleanup.
MAINTENANCE_BACKUP_DIR: Path = BACKUP_DIR / "maintenance"

# Retention for the maintenance tree. Nothing pruned these until 2026-08-23,
# by which point 31 snapshots of `student_records.db` — all holding the same 24
# students, differing only in which views a campaign had added — accounted for
# 466MB of a 667MB backup tree. One campaign wrote three identical copies inside
# two minutes. The defaults keep every run for MAINTENANCE_BACKUP_MAX_AGE_DAYS,
# then collapse each campaign to its newest MAINTENANCE_BACKUP_KEEP runs.
MAINTENANCE_BACKUP_KEEP: int = 3
MAINTENANCE_BACKUP_MAX_AGE_DAYS: int = 30

# A run directory is only ever a prune candidate if its name starts with a date
# stamp. That deliberately excludes hand-named drops such as `loose/`, so a
# human-curated backup is never removed by an automated sweep.
_MAINTENANCE_RUN_RE = r"^(\d{8})(?:_(\d{6}))?"

# Package roots, formerly derived from each module's own ``__file__``.
PLATFORM_ROOT: Path = EDUCATION_SYSTEM_ROOT / "platform"
_SYSTEMS_ROOT: Path = EDUCATION_SYSTEM_ROOT / "systems"
NURSERY_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "nursery"
PRIMARY_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "primary"
SECONDARY_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "secondary"
SIXTH_FORM_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "sixth_form"
UNIVERSITY_PROJECT_ROOT: Path = _SYSTEMS_ROOT / "university"

# University aliases kept for callers that used the older spellings.
UNIVERSITY_BASE_DIR: Path = UNIVERSITY_PROJECT_ROOT
UNIVERSITY_SYSTEM_DIR: Path = UNIVERSITY_PROJECT_ROOT
# The modules/ layer no longer exists (ADR 0018), so the package root is the
# source root.
UNIVERSITY_SRC_DIR: Path = UNIVERSITY_PROJECT_ROOT


def _ensure(dir_path: Path) -> Path:
    """Create *dir_path* (and parents) if it does not already exist."""
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# Config files hold credentials — an SMTP password, and historically an API
# key. They are written by a dozen different ``save_config`` implementations,
# each using a plain ``json.dump`` that inherits the process umask (0644 on a
# typical host), so hardening any single writer would not hold. Sweeping the
# directories at bootstrap covers every writer, including a GUI that rewrites
# a file later in the session.
_CONFIG_FILE_MODE = 0o600
_CONFIG_DIR_MODE = 0o700


def harden_config_permissions(*config_dirs: Path) -> list[Path]:
    """Restrict config files to owner-only access. Returns what changed.

    Best-effort: a permission change can fail on a mounted volume or a
    filesystem without POSIX modes, and that must not stop the application
    from starting.
    """
    changed: list[Path] = []
    for directory in config_dirs:
        try:
            if not directory.is_dir():
                continue
            if stat.S_IMODE(directory.stat().st_mode) != _CONFIG_DIR_MODE:
                directory.chmod(_CONFIG_DIR_MODE)
                changed.append(directory)
            for entry in directory.iterdir():
                if not entry.is_file():
                    continue
                if stat.S_IMODE(entry.stat().st_mode) != _CONFIG_FILE_MODE:
                    entry.chmod(_CONFIG_FILE_MODE)
                    changed.append(entry)
        except OSError:
            continue
    return changed

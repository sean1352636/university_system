"""List the university's real database backups for the admin screens.

Two trees hold them, both resolved through ``education_system.paths``:

* ``system_backup_dir("university")`` - the routine backups written by
  ``create_enhanced_backup`` (``database/``) and the per-feature ones
  (``submissions/``, ``maintenance/``, ...).
* the maintenance tree (``maintenance_backup_dir``'s root) - the safety copies
  taken by repair scripts before they changed ``student_records.db``.

Nothing here writes; it only reads file names, sizes, times and any
``.meta.json`` sidecar.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from education_system.paths import MAINTENANCE_BACKUP_DIR, system_backup_dir

_BACKUP_SUFFIXES = (".db", ".db.gz", ".db.enc", ".db.gz.enc", ".encrypted", ".db.zip",
                    ".sqlite", ".sqlite3", ".sql", ".sql.gz")
_STAMP_RE = re.compile(r"(\d{8})[_-]?(\d{6})")


def _is_backup_file(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith((".meta.json", "-wal", "-shm", "-journal")):
        return False
    return name.endswith(_BACKUP_SUFFIXES)


def _when(path: Path, meta: dict) -> datetime:
    stamp = meta.get("timestamp") if isinstance(meta, dict) else None
    if isinstance(stamp, str):
        try:
            return datetime.fromisoformat(stamp.replace("Z", ""))
        except ValueError:
            pass
    match = _STAMP_RE.search(path.name) or _STAMP_RE.search(path.parent.name)
    if match:
        try:
            return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def _kind(path: Path, root_label: str) -> str:
    name = path.name.lower()
    if root_label == "maintenance":
        # var/backups/maintenance/<label>/<run>/file
        try:
            label = path.relative_to(MAINTENANCE_BACKUP_DIR).parts[0]
        except ValueError:
            label = path.parent.name
        return f"Maintenance ({label})"
    m = re.search(r"_before_(.+?)_\d{8}_\d{6}", name)
    if m:
        return f"Pre-change ({m.group(1).replace('_', ' ')})"
    for word, label in (("manual", "Manual"), ("scheduled", "Scheduled"),
                        ("incremental", "Incremental"), ("schema", "Schema"),
                        ("selective", "Selective")):
        if word in name:
            return label
    return "Full" if path.parent.name == "database" else path.parent.name.capitalize()


def _read_meta(path: Path) -> dict:
    sidecar = path.with_name(path.name + ".meta.json")
    if not sidecar.exists():
        return {}
    try:
        with sidecar.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def list_university_backups(include_maintenance: bool = True) -> list[dict]:
    """Every university database backup on disk, newest first.

    Each entry: ``path``, ``filename``, ``when`` (datetime), ``date`` (str),
    ``kind``, ``size_bytes``, ``size``, ``duration`` (from metadata, or ""),
    ``location`` (path relative to the backups root).
    """
    roots: list[tuple[Path, str]] = [(system_backup_dir("university"), "university")]
    if include_maintenance:
        roots.append((MAINTENANCE_BACKUP_DIR, "maintenance"))

    entries: list[dict] = []
    seen: set[Path] = set()
    for root, label in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or not _is_backup_file(path):
                continue
            if label == "maintenance" and "student_records" not in path.name:
                # The maintenance tree also holds auth.db, locale and code
                # snapshots; this screen is about the university database.
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                meta = _read_meta(path)
                when = _when(path, meta)
                size = path.stat().st_size
            except OSError:
                continue
            duration = meta.get("duration") or meta.get("duration_seconds") or ""
            if isinstance(duration, (int, float)):
                duration = f"{int(duration) // 60}m {int(duration) % 60}s"
            try:
                location = str(path.relative_to(root.parent))
            except ValueError:
                location = str(path)
            entries.append({
                "path": str(path),
                "filename": path.name,
                "when": when,
                "date": when.strftime("%Y-%m-%d %H:%M"),
                "kind": _kind(path, label),
                "size_bytes": size,
                "size": format_size(size),
                "duration": str(duration),
                "location": location,
            })
    entries.sort(key=lambda e: e["when"], reverse=True)
    return entries


def is_inside_backup_tree(path: str) -> bool:
    """True when *path* lies under one of the trees listed above."""
    target = Path(path).resolve()
    for root in (system_backup_dir("university"), MAINTENANCE_BACKUP_DIR):
        try:
            target.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False

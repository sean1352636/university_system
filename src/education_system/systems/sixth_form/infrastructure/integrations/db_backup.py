"""Sixth form database backups: take, rotate, check, preview and restore.

Which databases: every ``SIXTH_FORM_*_DB`` constant in
:mod:`education_system.paths`, resolved and de-duplicated (today they all
point at ``sixthform.db``, but a split-out DB is picked up automatically).

Where: ``paths.system_backup_dir("sixth_form", "database")``, as
``<db stem>_<YYYYmmdd_HHMMSS>[_<label>].db``.

How: the sqlite3 online backup API, which copies a consistent snapshot
even while the app has the database open. The copy is written to a
``.part`` file, ``PRAGMA integrity_check``-ed, and only then renamed into
place, so a half-written or corrupt copy never appears as a backup.

Rotation keeps the newest N backups per (database, label) group; N comes
from the ``backup_keep`` integration setting (default 14). Pre-restore
safety copies (label ``pre_restore``) rotate in their own group so a run
of scheduled backups never pushes them out.

Restore always takes a ``pre_restore`` backup of the current database
first, refuses a backup that fails its integrity check or lies outside the
backup directory, and needs the typed phrase from
:func:`confirmation_phrase`. The app should be restarted afterwards.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from pathlib import Path

from education_system import paths
from education_system.systems.sixth_form.infrastructure.integrations import (
    store,
)

logger = logging.getLogger(__name__)

SYSTEM_KEY = "sixth_form"
CATEGORY = "database"
PRE_RESTORE_LABEL = "pre_restore"
DEFAULT_KEEP = 14
MIN_KEEP = 1

_NAME_RE = re.compile(
    r"^(?P<stem>.+?)_(?P<ts>\d{8}_\d{6})(?:_(?P<label>[a-z0-9_]+))?\.db$")
_LABEL_RE = re.compile(r"^[a-z0-9_]{1,40}$")
_CONST_RE = re.compile(r"^SIXTH_FORM_[A-Z0-9_]*_DB$")


class ValidationError(ValueError):
    pass


def backup_dir() -> Path:
    return paths.system_backup_dir(SYSTEM_KEY, CATEGORY)


def database_constants() -> dict[Path, list[str]]:
    """Resolved DB path -> the paths constants that point at it."""
    out: dict[Path, list[str]] = {}
    for name in sorted(dir(paths)):
        if not _CONST_RE.match(name):
            continue
        value = getattr(paths, name)
        if not isinstance(value, (str, Path)):
            continue
        out.setdefault(Path(value).resolve(), []).append(name)
    return out


def database_paths() -> list[Path]:
    """Every distinct sixth form database file (existing or not)."""
    return list(database_constants())


def _target_for_stem(stem: str) -> Path | None:
    for p in database_paths():
        if p.stem == stem:
            return p
    return None


# ── Inspection ─────────────────────────────────────────────────────

def _ro(path: Path) -> _sql.Connection:
    """A connection used only for reading.

    Not ``mode=ro``: the databases (and so their backup copies) are in WAL
    mode, and a read-only URI connection cannot open a WAL database whose
    -shm file does not exist yet.
    """
    return _sql.connect(str(path), timeout=30)


def integrity_check(path: str | Path) -> str:
    """'ok' or the problems PRAGMA integrity_check reports."""
    p = Path(path)
    if not p.is_file():
        return f"missing: {p}"
    try:
        conn = _ro(p)
        try:
            rows = conn.execute("PRAGMA integrity_check").fetchall()
        finally:
            conn.close()
    except _sql.Error as e:
        return f"error: {e}"
    return "; ".join(str(r[0]) for r in rows) or "no result"


def table_counts(path: str | Path) -> dict[str, int]:
    """Row count of every table in the database at *path* (read-only)."""
    conn = _ro(Path(path))
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]
        out = {}
        for n in names:
            quoted = '"' + n.replace('"', '""') + '"'
            out[n] = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]  # noqa: S608 - name from sqlite_master, quoted
        return out
    finally:
        conn.close()


@dataclass
class BackupInfo:
    path: Path
    stem: str
    created: _dt.datetime
    label: str | None
    size: int

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def size_label(self) -> str:
        n = float(self.size)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024
        return f"{self.size} B"


def _info(p: Path) -> BackupInfo | None:
    m = _NAME_RE.match(p.name)
    if not m:
        return None
    try:
        created = _dt.datetime.strptime(m["ts"], "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return BackupInfo(path=p, stem=m["stem"], created=created,
                      label=m["label"], size=p.stat().st_size)


def list_backups(stem: str | None = None) -> list[BackupInfo]:
    """Backups in the backup directory, newest first."""
    d = backup_dir()
    if not d.is_dir():
        return []
    out = [i for p in d.glob("*.db") if (i := _info(p)) is not None]
    if stem:
        out = [i for i in out if i.stem == stem]
    return sorted(out, key=lambda i: (i.created, i.name), reverse=True)


# ── Settings ───────────────────────────────────────────────────────

def keep_count() -> int:
    try:
        return max(MIN_KEEP, int(store.get_setting("backup_keep") or DEFAULT_KEEP))
    except (TypeError, ValueError):
        return DEFAULT_KEEP


def set_keep_count(n: int) -> None:
    who = store.require("ADMIN", "backup retention")
    if int(n) < MIN_KEEP:
        raise ValidationError(f"Keep at least {MIN_KEEP} backup")
    store.set_setting("backup_keep", int(n), by=who)


# ── Backup ─────────────────────────────────────────────────────────

@dataclass
class BackupResult:
    source: Path
    backup: BackupInfo
    integrity: str
    removed: list[Path] = field(default_factory=list)


def _copy(src: Path, dst: Path) -> None:
    """Online-backup *src* into *dst* (dst is overwritten page by page)."""
    s = _ro(src)
    d = _sql.connect(str(dst))
    try:
        s.backup(d)
        # Make the copy one self-contained file (no -wal/-shm beside it).
        d.execute("PRAGMA journal_mode=DELETE")
    finally:
        d.close()
        s.close()


def rotate(stem: str, *, label: str | None = None,
           keep: int | None = None) -> list[Path]:
    """Delete all but the newest *keep* backups of (stem, label)."""
    keep = keep if keep is not None else keep_count()
    keep = max(MIN_KEEP, int(keep))
    group = [i for i in list_backups(stem) if i.label == label]
    removed = []
    for old in group[keep:]:
        try:
            old.path.unlink()
            removed.append(old.path)
        except OSError:
            logger.exception("Could not remove old backup %s", old.path)
    if removed:
        logger.info("Backup rotation for %s (%s): removed %d, kept %d",
                    stem, label or "regular", len(removed), keep)
    return removed


def backup_database(source: str | Path, *, label: str | None = None,
                    keep: int | None = None) -> BackupResult:
    """Back up one database file, verify the copy, rotate old copies."""
    who = store.require("OPERATIONS", "database backup")
    src = Path(source).resolve()
    if not src.is_file():
        raise ValidationError(f"Database not found: {src}")
    if label is not None and not _LABEL_RE.match(label):
        raise ValidationError("Label may use lower-case letters, digits and _ only")
    d = backup_dir()
    d.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now()
    while True:
        name = f"{src.stem}_{ts:%Y%m%d_%H%M%S}" + (f"_{label}" if label else "") + ".db"
        final = d / name
        if not final.exists():
            break
        ts += _dt.timedelta(seconds=1)
    part = final.with_name(final.name + ".part")
    try:
        _copy(src, part)
        result = integrity_check(part)
        if result != "ok":
            raise ValidationError(f"Backup copy failed its integrity check: {result}")
        part.replace(final)
    finally:
        if part.exists():
            part.unlink()
    info = _info(final)
    assert info is not None
    removed = rotate(src.stem, label=label, keep=keep)
    logger.info("Backed up %s to %s (%s) by %s", src, final, info.size_label,
                who or "?")
    return BackupResult(source=src, backup=info, integrity="ok", removed=removed)


def backup_all(*, label: str | None = None) -> list[BackupResult]:
    """Back up every existing sixth form database."""
    return [backup_database(p, label=label)
            for p in database_paths() if p.is_file()]


# ── Restore ────────────────────────────────────────────────────────

@dataclass
class RestorePreview:
    backup: BackupInfo
    target: Path
    integrity: str
    backup_counts: dict[str, int]
    current_counts: dict[str, int]

    def differences(self) -> list[tuple[str, int | None, int | None]]:
        """(table, current rows, backup rows) where they differ."""
        names = sorted(set(self.backup_counts) | set(self.current_counts))
        return [(n, self.current_counts.get(n), self.backup_counts.get(n))
                for n in names
                if self.current_counts.get(n) != self.backup_counts.get(n)]


def _resolve_backup(backup: str | Path | BackupInfo) -> BackupInfo:
    p = backup.path if isinstance(backup, BackupInfo) else Path(backup)
    if not p.is_absolute():
        p = backup_dir() / p
    p = p.resolve()
    if p.parent != backup_dir().resolve():
        raise ValidationError("Only backups inside the sixth form backup "
                              f"directory can be restored ({backup_dir()})")
    info = _info(p) if p.is_file() else None
    if info is None:
        raise ValidationError(f"Not a sixth form backup file: {p.name}")
    return info


def restore_preview(backup: str | Path | BackupInfo) -> RestorePreview:
    """What a restore would do (read-only)."""
    store.require("ADMIN", "restore preview")
    info = _resolve_backup(backup)
    target = _target_for_stem(info.stem)
    if target is None:
        raise ValidationError(f"No sixth form database named {info.stem}.db")
    integrity = integrity_check(info.path)
    backup_counts = table_counts(info.path) if integrity == "ok" else {}
    current = table_counts(target) if target.is_file() else {}
    return RestorePreview(backup=info, target=target, integrity=integrity,
                          backup_counts=backup_counts, current_counts=current)


def confirmation_phrase(backup: str | Path | BackupInfo) -> str:
    name = backup.name if isinstance(backup, BackupInfo) else Path(backup).name
    return f"RESTORE {name}"


@dataclass
class RestoreResult:
    target: Path
    restored_from: Path
    safety_backup: Path | None
    integrity: str


def restore(backup: str | Path | BackupInfo, confirmation: str) -> RestoreResult:
    """Replace the live DB's contents with *backup*.

    Takes a pre-restore backup of the current database first. The typed
    *confirmation* must equal :func:`confirmation_phrase`.
    """
    who = store.require("ADMIN", "database restore")
    info = _resolve_backup(backup)
    expected = confirmation_phrase(info)
    if (confirmation or "").strip() != expected:
        raise ValidationError(f"Type exactly: {expected}")
    target = _target_for_stem(info.stem)
    if target is None:
        raise ValidationError(f"No sixth form database named {info.stem}.db")
    check = integrity_check(info.path)
    if check != "ok":
        raise ValidationError(f"Backup failed its integrity check: {check}")
    safety = None
    if target.is_file():
        safety = backup_database(target, label=PRE_RESTORE_LABEL).backup.path
    src = _ro(info.path)
    dst = _sql.connect(str(target), timeout=30)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    after = integrity_check(target)
    logger.warning("Sixth form DB %s restored from %s by %s (safety copy %s, "
                   "integrity %s)", target, info.path, who or "?", safety, after)
    return RestoreResult(target=target, restored_from=info.path,
                         safety_backup=safety, integrity=after)

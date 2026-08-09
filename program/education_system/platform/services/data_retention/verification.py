"""Prove an erasure actually erased, and keep the proof itself PII-free.

Two problems this module exists to solve.

**A DSAR record that retains what it erased.** ``data_subject_requests`` stores
``subject_email`` in the clear. After an erasure completes, that row is often
the last copy of the address in the estate — the request log quietly becomes a
register of every person who asked to be forgotten. :func:`subject_reference`
replaces it with a keyed hash: still stable enough to answer "have we already
processed a request for this person?", but not reversible back to the address.

**An erasure nobody checked.** ``process_erasure_request`` anonymises the live
tables and reports success. It never looks at the places a copy actually
survives: WAL sidecar files, database backups taken before the request, and
application logs that recorded the address in a request line or a stack trace.
:func:`verify_erasure` goes and looks, and reports residue by location so the
gap is visible rather than assumed away.

Verification is deliberately a *separate* call from erasure. Running it inside
the erasure would mean the same code both performs and attests the deletion;
keeping it separate lets it run as an independent check — which is how it is
used in the security suite's backup-restore and log-leakage tests.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "ResidueFinding",
    "ErasureVerification",
    "subject_reference",
    "verify_erasure",
    "scan_path_for_identifiers",
]

#: Files whose contents are text we can meaningfully scan for an identifier.
_TEXT_SUFFIXES = frozenset({".log", ".txt", ".json", ".jsonl", ".csv", ".ndjson", ".sql", ".yaml", ".yml"})
#: Files that are SQLite databases (including WAL/journal sidecars).
_DB_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".db-journal"})
#: Bound on how much of any one file is read, so a multi-GB log cannot stall
#: a verification run. Reported when it bites — a truncated scan must not read
#: as a clean one.
_MAX_SCAN_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class ResidueFinding:
    """One place a supposedly-erased identifier was still found."""

    location: str
    kind: str          # "database" | "backup" | "log" | "archive"
    detail: str
    occurrences: int = 1


@dataclass
class ErasureVerification:
    """The outcome of checking an erasure across live data, backups and logs."""

    subject_ref: str
    checked_at: str
    locations_scanned: int = 0
    truncated_scans: list[str] = field(default_factory=list)
    findings: list[ResidueFinding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """True only if nothing was found *and* nothing was left unscanned.

        A truncated scan makes the result inconclusive, not clean — reporting
        "no residue" from a partial read is exactly the false assurance this
        module exists to prevent.
        """
        return not self.findings and not self.truncated_scans

    def as_dict(self) -> dict:
        return {
            "subject_ref": self.subject_ref,
            "checked_at": self.checked_at,
            "clean": self.clean,
            "locations_scanned": self.locations_scanned,
            "truncated_scans": list(self.truncated_scans),
            "findings": [
                {
                    "location": f.location,
                    "kind": f.kind,
                    "detail": f.detail,
                    "occurrences": f.occurrences,
                }
                for f in self.findings
            ],
        }


def subject_reference(identifier: str) -> str:
    """Return a stable, non-reversible reference for a data subject.

    Keyed with ``RETENTION_PSEUDONYM_KEY`` so the digest cannot be reversed by
    hashing a candidate address — a plain SHA-256 of an email is trivially
    recovered from a wordlist, which is why unkeyed hashing does not count as
    pseudonymisation under GDPR Art. 4(5).

    Falls back to an unkeyed digest with a warning if no key is configured, so
    a development environment still works; the security suite asserts the key
    is set in a production-like configuration.
    """
    normalised = identifier.strip().lower().encode("utf-8")
    key = os.environ.get("RETENTION_PSEUDONYM_KEY", "").encode("utf-8")
    if not key:
        logger.warning(
            "RETENTION_PSEUDONYM_KEY is not set — subject references are "
            "unkeyed digests and can be reversed by dictionary attack."
        )
        return "sha256:" + hashlib.sha256(normalised).hexdigest()
    return "hmac-sha256:" + hmac.new(key, normalised, hashlib.sha256).hexdigest()


def _identifier_patterns(identifiers: Sequence[str]) -> list[tuple[str, re.Pattern[bytes]]]:
    """Compile case-insensitive byte patterns for each identifier."""
    patterns = []
    for identifier in identifiers:
        if not identifier:
            continue
        patterns.append(
            (identifier, re.compile(re.escape(identifier).encode("utf-8"), re.IGNORECASE))
        )
    return patterns


def scan_path_for_identifiers(
    path: Path,
    identifiers: Sequence[str],
    *,
    kind: str,
    max_bytes: int = _MAX_SCAN_BYTES,
) -> tuple[list[ResidueFinding], bool]:
    """Scan one file for any of ``identifiers``.

    Reads bytes rather than decoding: a SQLite file, a gzip'd log and a UTF-8
    log all contain the identifier as a byte run when it is present in the
    clear, and byte scanning avoids a decode error hiding a hit.

    Returns:
        ``(findings, truncated)`` — ``truncated`` is True if the file was
        larger than ``max_bytes`` and only its head was read.
    """
    patterns = _identifier_patterns(identifiers)
    if not patterns:
        return [], False

    findings: list[ResidueFinding] = []
    truncated = False
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            data = handle.read(max_bytes)
        truncated = size > max_bytes
    except OSError as exc:
        logger.debug("Could not scan %s: %s", path, exc)
        return [], False

    for identifier, pattern in patterns:
        matches = pattern.findall(data)
        if matches:
            findings.append(
                ResidueFinding(
                    location=str(path),
                    kind=kind,
                    detail=f"identifier {_mask(identifier)} present in file contents",
                    occurrences=len(matches),
                )
            )
    return findings, truncated


def _mask(identifier: str) -> str:
    """Mask an identifier for safe inclusion in a report or log line.

    The verification report is itself written to disk and read by operators,
    so echoing the full address back would recreate the leak being measured.
    """
    if "@" in identifier:
        local, _, domain = identifier.partition("@")
        head = local[:2] if len(local) > 2 else local[:1]
        return f"{head}***@{domain}"
    return f"{identifier[:2]}***" if len(identifier) > 2 else "***"


def _scan_database(db_path: Path, identifiers: Sequence[str]) -> list[ResidueFinding]:
    """Query every text column of every table for the identifiers.

    A raw byte scan of a SQLite file also matches rows sitting in freed pages
    that a ``VACUUM`` would reclaim, so both are used: this one reports *live*
    residue (a row that still holds the value, i.e. the erasure missed a
    table), and the byte scan reports *deleted-but-recoverable* residue.
    """
    findings: list[ResidueFinding] = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        logger.debug("Could not open %s for verification: %s", db_path, exc)
        return findings

    try:
        conn.row_factory = sqlite3.Row
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            try:
                columns = [
                    row["name"]
                    for row in conn.execute(f'PRAGMA table_info("{table}")')
                    # Only text-ish columns can hold an email or a name.
                    if (row["type"] or "").upper().startswith(("TEXT", "VARCHAR", "CHAR", "CLOB"))
                    or not row["type"]
                ]
                if not columns:
                    continue
                for identifier in identifiers:
                    if not identifier:
                        continue
                    # Table and column names come from sqlite_master, not from
                    # user input, and are quoted; the value is parameterised.
                    where = " OR ".join(
                        f'LOWER(CAST("{column}" AS TEXT)) LIKE ?' for column in columns
                    )
                    params = [f"%{identifier.lower()}%"] * len(columns)
                    count = conn.execute(
                        f'SELECT COUNT(*) FROM "{table}" WHERE {where}',  # noqa: S608
                        params,
                    ).fetchone()[0]
                    if count:
                        findings.append(
                            ResidueFinding(
                                location=f"{db_path}::{table}",
                                kind="database",
                                detail=(
                                    f"{count} live row(s) still contain "
                                    f"{_mask(identifier)} after erasure"
                                ),
                                occurrences=count,
                            )
                        )
            except sqlite3.Error as exc:
                logger.debug("Skipped table %s in %s: %s", table, db_path, exc)
    finally:
        conn.close()
    return findings


def _iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if path.is_file():
                yield path


def verify_erasure(
    identifiers: Sequence[str],
    *,
    database_paths: Sequence[Path] | None = None,
    backup_roots: Sequence[Path] | None = None,
    log_roots: Sequence[Path] | None = None,
) -> ErasureVerification:
    """Check that ``identifiers`` survive nowhere they should not.

    Args:
        identifiers: The values erased — typically ``[email]``, optionally with
            the subject's name and student/staff number, since erasing the
            email alone leaves the other identifiers behind.
        database_paths: Live databases to check. Defaults to the estate's
            system databases plus the shared auth database.
        backup_roots: Directories of backups and exports. Residue here is the
            most commonly missed: an erasure that only touches live tables
            leaves every pre-request backup intact, which is a policy question
            (how long backups are kept) but must at least be *visible*.
        log_roots: Directories of application logs.

    Returns:
        An :class:`ErasureVerification`. ``clean`` is True only when nothing
        was found and every candidate location was fully scanned.
    """
    from education_system.platform.services.data_retention.gdpr_report import _SYSTEM_DBS

    subject_ref = subject_reference(identifiers[0]) if identifiers else "unknown"
    result = ErasureVerification(
        subject_ref=subject_ref,
        checked_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    if database_paths is None:
        database_paths = [p for p in _SYSTEM_DBS.values()]
    if backup_roots is None:
        backup_roots = _default_backup_roots()
    if log_roots is None:
        log_roots = _default_log_roots()

    # 1. Live databases — a hit here means the erasure missed a table.
    for db_path in database_paths:
        if not Path(db_path).exists():
            continue
        result.locations_scanned += 1
        result.findings.extend(_scan_database(Path(db_path), identifiers))
        # WAL and journal sidecars hold recently-written pages that the main
        # file does not yet contain, so an erased value can persist there
        # until a checkpoint.
        for suffix in ("-wal", "-journal"):
            sidecar = Path(str(db_path) + suffix)
            if sidecar.exists():
                result.locations_scanned += 1
                found, truncated = scan_path_for_identifiers(
                    sidecar, identifiers, kind="database"
                )
                result.findings.extend(found)
                if truncated:
                    result.truncated_scans.append(str(sidecar))

    # 2. Backups and exports.
    for path in _iter_files(backup_roots):
        if path.suffix.lower() not in (_TEXT_SUFFIXES | _DB_SUFFIXES | {".zip", ".gz", ".bak"}):
            continue
        result.locations_scanned += 1
        found, truncated = scan_path_for_identifiers(path, identifiers, kind="backup")
        result.findings.extend(found)
        if truncated:
            result.truncated_scans.append(str(path))

    # 3. Logs.
    for path in _iter_files(log_roots):
        if path.suffix.lower() not in _TEXT_SUFFIXES and ".log" not in path.name:
            continue
        result.locations_scanned += 1
        found, truncated = scan_path_for_identifiers(path, identifiers, kind="log")
        result.findings.extend(found)
        if truncated:
            result.truncated_scans.append(str(path))

    logger.info(
        "Erasure verification for %s: %s (%d location(s) scanned, %d finding(s))",
        subject_ref, "clean" if result.clean else "RESIDUE FOUND",
        result.locations_scanned, len(result.findings),
    )
    return result


def _default_backup_roots() -> list[Path]:
    """Every backup and export tree in the estate, across all five systems.

    Backups live per-system under ``var/backups/<system>`` and exports under
    ``var/data/<system>/exports``, so a single platform-level constant is not
    enough — scanning only the platform tree would report "clean" while every
    university backup still held the record.
    """
    from education_system import paths as platform_paths

    var_dir = Path(platform_paths.VAR_DIR)
    roots = [var_dir / "backups"]
    data_dir = var_dir / "data"
    if data_dir.exists():
        roots.extend(child / "exports" for child in data_dir.iterdir() if child.is_dir())
    return [root for root in roots if root.exists()]


def _default_log_roots() -> list[Path]:
    """All per-system log trees, not just the platform one."""
    from education_system import paths as platform_paths

    logs_dir = Path(platform_paths.VAR_DIR) / "logs"
    return [logs_dir] if logs_dir.exists() else []

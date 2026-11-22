"""Files attached to academic integrity cases.

Each file is copied into ``var/data/university/integrity_evidence/<case>/``
(owner-only), so later changes to the original do not change the evidence,
and its SHA-256 is kept so the copy can be shown to be the one attached.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

MAX_BYTES = 50 * 1024 * 1024


def _root() -> Path:
    from education_system.paths import UNIVERSITY_INTEGRITY_EVIDENCE_DIR
    return UNIVERSITY_INTEGRITY_EVIDENCE_DIR


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def store(case_id, source) -> tuple[str, str, str]:
    """Copy ``source`` in as evidence for ``case_id``. Returns ``(stored
    path, original file name, sha256)``."""
    source = Path(str(source))
    if not source.is_file():
        raise ValueError(f"No such file: {source.name}")
    if source.stat().st_size > MAX_BYTES:
        raise ValueError(f"{source.name} is larger than {MAX_BYTES // (1024 * 1024)} MB")
    digest = sha256_of(source)
    folder = _root() / str(int(case_id))
    folder.mkdir(parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    target = folder / f"{digest[:12]}_{source.name}"
    if not target.exists():
        shutil.copy2(source, target)
        os.chmod(target, 0o600)
    return str(target), source.name, digest


def verify(path, digest) -> bool:
    """Is the stored copy still the file that was attached?"""
    try:
        return sha256_of(path) == digest
    except OSError:
        return False


def remove(path) -> bool:
    """Delete a stored copy (retention). Only files under the evidence
    folder are ever deleted."""
    try:
        target = Path(str(path)).resolve()
        if _root().resolve() not in target.parents:
            return False
        target.unlink(missing_ok=True)
        return True
    except OSError:
        return False

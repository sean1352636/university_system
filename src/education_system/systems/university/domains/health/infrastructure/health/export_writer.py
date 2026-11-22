"""Where health exports go, and how they are protected.

Every health export is written under ``UNIVERSITY_EXPORTS_DIR/health/``
(owner-only directory, owner-only files) — never the current directory. A
file may also be encrypted with the managed health key
(``field_crypto.key_bytes()``): the plain file is replaced by ``<name>.enc``.
"""

import csv
import os
from collections.abc import Iterable, Sequence
from pathlib import Path


def export_dir() -> Path:
    from education_system import paths
    target = Path(paths.UNIVERSITY_EXPORTS_DIR) / "health"
    target.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target, 0o700)
    except OSError:
        pass
    return target


def export_path(filename: str) -> Path:
    """A fresh path for ``filename`` in the health export folder (a numeric
    suffix is added rather than overwriting)."""
    name = os.path.basename(filename)
    target = export_dir() / name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    counter = 1
    while target.exists() or target.with_name(target.name + ".enc").exists():
        target = export_dir() / (f"{stem}_{counter}.{ext}" if ext else f"{stem}_{counter}")
        counter += 1
    # Create it owner-only before anything is written to it.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    return target


def finalize(path, *, encrypt: bool = False) -> Path:
    """Make ``path`` owner-only and, if asked, encrypt it in place. Returns
    the file that now holds the export."""
    target = Path(path)
    os.chmod(target, 0o600)
    if not encrypt:
        return target
    from cryptography.fernet import Fernet

    from education_system.systems.university.domains.health.infrastructure.health import (
        field_crypto,
    )
    sealed = target.with_name(target.name + ".enc")
    fd = os.open(sealed, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(Fernet(field_crypto.key_bytes()).encrypt(target.read_bytes()))
    target.unlink()
    return sealed


def decrypt_export(path) -> bytes:
    """The contents of an encrypted export (``.enc``)."""
    from cryptography.fernet import Fernet

    from education_system.systems.university.domains.health.infrastructure.health import (
        field_crypto,
    )
    return Fernet(field_crypto.key_bytes()).decrypt(Path(path).read_bytes())


def write_csv(path: str | Path, headers: Sequence[str], rows: Iterable[Sequence[object]],
              *, encrypt: bool = False) -> Path:
    target = Path(path)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return finalize(target, encrypt=encrypt)

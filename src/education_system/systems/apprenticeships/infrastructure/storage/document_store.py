"""The bytes behind uploaded documents.

The ``documents`` table holds what a file is; this module holds the file.
Everything lives flat in ``paths.APPRENTICESHIPS_DOCUMENTS_DIR`` under a
name generated here — 32 hex characters and an extension taken from the
allowlist — so there is no path a user can influence. The uploader's
filename is kept in the database for display and never touches the
filesystem.

The directory is read from ``paths`` at call time rather than captured at
import, so a test can repoint ``paths.APPRENTICESHIPS_DOCUMENTS_DIR`` at a
temporary directory and every read and write follows it.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from education_system import paths
from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.records.documents import format_size

_CHUNK = 1024 * 1024

# What a generated name looks like. Checked again on every read, so a
# row edited by hand to "../../something" is refused rather than followed.
STORED_NAME = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{1,5}$")


@dataclass(frozen=True)
class StoredFile:
    stored_name: str
    size_bytes: int
    sha256: str


def root() -> Path:
    """The documents directory, created on first use."""
    paths.ensure_apprenticeships_directories()
    return Path(paths.APPRENTICESHIPS_DOCUMENTS_DIR)


def store(source: Path, extension: str, *, max_bytes: int) -> StoredFile:
    """Copy *source* into the store under a new generated name.

    The size limit is enforced during the copy as well as before it: a
    file that grows between the check and the copy must not get in by
    being quick. Anything left half-written is removed.
    """
    if extension not in config.DOCUMENT_EXTENSIONS:
        raise ValidationError(f"{extension or 'That'} is not an allowed file type")
    stored_name = f"{uuid.uuid4().hex}{extension}"
    target = root() / stored_name
    digest = hashlib.sha256()
    size = 0
    try:
        # "xb" refuses to overwrite: a name collision would be a bug, and
        # silently replacing another document's bytes the worst version.
        with open(source, "rb") as src, open(target, "xb") as dst:
            while chunk := src.read(_CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise ValidationError(
                        f"The file is larger than the {format_size(max_bytes)} limit"
                    )
                digest.update(chunk)
                dst.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return StoredFile(stored_name=stored_name, size_bytes=size, sha256=digest.hexdigest())


def path_for(stored_name: str) -> Path:
    """Where a stored file lives. Refuses anything not shaped like our names."""
    if not STORED_NAME.fullmatch(stored_name or ""):
        raise ValidationError("That document's stored file name is not valid")
    return root() / stored_name


def exists(stored_name: str) -> bool:
    try:
        return path_for(stored_name).is_file()
    except ValidationError:
        return False


def sha256_of(stored_name: str) -> str:
    digest = hashlib.sha256()
    with open(path_for(stored_name), "rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def copy_to(stored_name: str, destination: Path) -> Path:
    """Copy a stored file out to wherever the user asked for it."""
    source = path_for(stored_name)
    destination = Path(destination)
    shutil.copyfile(source, destination)
    return destination


def discard(stored_name: str) -> None:
    """Remove a stored file — only ever to undo an upload that failed."""
    try:
        path_for(stored_name).unlink(missing_ok=True)
    except ValidationError:
        return

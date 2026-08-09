"""Secure file and path handling primitives shared by every system.

Every filesystem operation that touches a user-influenced name — an upload, a
document-manager attachment, an export target, a backup archive member — must
route through this module rather than composing paths by hand.

The rules this module enforces:

* **Containment.** :func:`resolve_under` resolves a candidate path *fully*
  (following symlinks) and refuses to return anything that does not live under
  an approved root. That catches ``..`` traversal, absolute-path injection,
  Windows drive-letter escapes and symlink escapes in one check, because the
  test is applied to the *resolved* path rather than the textual one.
* **Exclusive creation.** :func:`open_exclusive` uses ``O_CREAT | O_EXCL`` so a
  pre-planted symlink or an attacker-controlled existing file cannot be written
  through, and applies a restrictive mode at creation time rather than
  ``chmod``-ing afterwards (which leaves a window where the file is readable).
* **Restrictive permissions.** Files default to ``0o600`` and directories to
  ``0o700``. :func:`harden_path` fixes up anything created elsewhere.
* **Safe temporary directories.** :func:`secure_temp_dir` returns a private
  ``0o700`` directory, never a predictable ``/tmp/<name>`` path.
* **Archive safety.** :func:`safe_extract` refuses zip-slip members, absolute
  members, symlink/device members and archives whose uncompressed size or
  member count exceeds a bound (zip bombs).

All failures raise :class:`PathSecurityError`, which callers should let
propagate — a containment failure is a security denial, never something to
paper over with a default path.
"""

from __future__ import annotations

import errno
import io
import os
import re
import stat
import tarfile
import tempfile
import unicodedata
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterable, Iterator

__all__ = [
    "PathSecurityError",
    "FILE_MODE",
    "DIR_MODE",
    "resolve_under",
    "is_within",
    "sanitize_filename",
    "safe_join",
    "ensure_secure_dir",
    "harden_path",
    "open_exclusive",
    "atomic_write",
    "secure_temp_dir",
    "secure_temp_file",
    "safe_extract",
]


class PathSecurityError(ValueError):
    """A path or archive member failed a containment or safety check.

    Subclasses :class:`ValueError` so existing ``except ValueError`` validation
    handlers keep working, but callers that care about the distinction can
    catch this type specifically.
    """


#: Owner read/write only — the default for anything that may hold personal data.
FILE_MODE = 0o600
#: Owner read/write/execute only — the default for directories we create.
DIR_MODE = 0o700

#: Uncompressed bytes an archive may expand to before we call it a bomb.
MAX_EXTRACT_BYTES = 512 * 1024 * 1024
#: Members an archive may contain before we call it a bomb.
MAX_EXTRACT_MEMBERS = 10_000

# Characters that are illegal in a filename on at least one supported platform,
# plus the path separators and the NUL byte.
_UNSAFE_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]')
# Windows reserved device names — creating these can hang or leak I/O.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


# ─────────────────────────────────────────────────────────────────────────────
# Containment
# ─────────────────────────────────────────────────────────────────────────────

def resolve_under(root: str | os.PathLike[str], candidate: str | os.PathLike[str]) -> Path:
    """Resolve ``candidate`` and return it only if it lives under ``root``.

    ``candidate`` may be relative (interpreted against ``root``) or absolute.
    Both sides are resolved with ``strict=False`` so the target need not exist
    yet, which is what makes this usable for *write* destinations as well as
    reads. Because resolution follows symlinks, a symlink inside ``root`` that
    points outside it is rejected.

    Raises:
        PathSecurityError: if the resolved path escapes ``root``, or if either
            path cannot be resolved (e.g. a symlink loop).
    """
    root_path = Path(root)
    candidate_path = Path(candidate)

    if "\x00" in str(candidate_path):
        raise PathSecurityError("Path contains a NUL byte")

    try:
        resolved_root = root_path.resolve(strict=False)
        if candidate_path.is_absolute():
            resolved = candidate_path.resolve(strict=False)
        else:
            resolved = (resolved_root / candidate_path).resolve(strict=False)
    except (OSError, RuntimeError) as exc:  # symlink loop, ELOOP, ENAMETOOLONG
        raise PathSecurityError(f"Path could not be resolved safely: {exc}") from exc

    if resolved != resolved_root and not _is_relative_to(resolved, resolved_root):
        raise PathSecurityError(
            f"Path escapes the approved root: {candidate!s} resolves outside {resolved_root}"
        )
    return resolved


def is_within(root: str | os.PathLike[str], candidate: str | os.PathLike[str]) -> bool:
    """Boolean form of :func:`resolve_under` for use in conditionals."""
    try:
        resolve_under(root, candidate)
    except PathSecurityError:
        return False
    return True


def _is_relative_to(path: Path, root: Path) -> bool:
    """``Path.is_relative_to`` without relying on the 3.9+ signature quirks."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# User-supplied names
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_filename(filename: str, *, default: str = "unnamed", max_length: int = 200) -> str:
    """Reduce a user-supplied filename to a single safe path component.

    Strips any directory part, normalises Unicode (so a decomposed or
    full-width character cannot smuggle a separator past the regex), removes
    control and separator characters, refuses Windows device names, and bounds
    the length while preserving the extension.

    The result never contains a separator, never starts with a dot, and is
    never empty — so it is always safe to pass to :func:`safe_join`.
    """
    if not filename:
        return default

    # NFKC folds full-width and compatibility forms down to ASCII equivalents
    # so "／" (U+FF0F) becomes "/" and is then stripped, rather than surviving.
    name = unicodedata.normalize("NFKC", str(filename))
    # Take the last component under *both* separator conventions — a Windows
    # client can send "C:\\evil\\payload.pdf" to a POSIX server.
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = _UNSAFE_CHARS.sub("_", name).strip(" .")

    if not name:
        return default

    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"_{stem}"

    ext = ext[:32]
    keep = max_length - (len(ext) + 1 if ext else 0)
    stem = stem[:keep] if keep > 0 else stem[:max_length]

    result = f"{stem}.{ext}" if ext else stem
    result = result.strip(" .")
    return result or default


def safe_join(root: str | os.PathLike[str], *parts: str) -> Path:
    """Join user-supplied ``parts`` beneath ``root``, sanitising each component.

    Unlike :func:`resolve_under`, which validates a whole candidate path, this
    builds the path from scratch: every component is reduced to a safe name
    first, so traversal is impossible by construction. The containment check is
    still applied afterwards as defence in depth against a symlinked ``root``
    subdirectory.
    """
    relative = Path(*(sanitize_filename(part) for part in parts if part not in ("", ".")))
    return resolve_under(root, relative)


# ─────────────────────────────────────────────────────────────────────────────
# Creation with restrictive permissions
# ─────────────────────────────────────────────────────────────────────────────

def ensure_secure_dir(path: str | os.PathLike[str], mode: int = DIR_MODE) -> Path:
    """Create ``path`` (and parents) with restrictive permissions and return it.

    ``mkdir`` honours the process umask, so the mode is re-applied explicitly
    afterwards — otherwise a umask of ``0o022`` silently yields ``0o755``.
    """
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    _chmod_quietly(directory, mode)
    return directory


def harden_path(path: str | os.PathLike[str]) -> Path:
    """Apply the restrictive default mode to an existing file or directory."""
    target = Path(path)
    if target.is_dir():
        _chmod_quietly(target, DIR_MODE)
    elif target.exists():
        _chmod_quietly(target, FILE_MODE)
    return target


def _chmod_quietly(path: Path, mode: int) -> None:
    """chmod, tolerating filesystems that do not implement POSIX modes.

    Windows and some network filesystems raise here; that is a capability gap,
    not a security failure we can act on, so it is not fatal. Anything else —
    notably ``EPERM`` on a file we do not own — is a real problem and is raised.
    """
    try:
        os.chmod(path, mode)
    except NotImplementedError:
        return
    except OSError as exc:
        if exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL):
            return
        raise


@contextmanager
def open_exclusive(
    path: str | os.PathLike[str],
    *,
    mode: int = FILE_MODE,
    text: bool = True,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> Iterator[IO]:
    """Create and open ``path`` for writing, failing if it already exists.

    ``O_EXCL`` makes creation atomic: if the path exists — including as a
    symlink an attacker planted to redirect the write — the call fails with
    :class:`FileExistsError` instead of following it. The permission bits are
    passed to ``open(2)`` so the file is never momentarily world-readable.

    Raises:
        FileExistsError: if the path already exists.
    """
    target = Path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    if not text:
        flags |= getattr(os, "O_BINARY", 0)

    fd = os.open(target, flags, mode)
    try:
        if text:
            handle: IO = os.fdopen(fd, "w", encoding=encoding, newline=newline)
        else:
            handle = os.fdopen(fd, "wb")
    except BaseException:
        os.close(fd)
        raise

    try:
        yield handle
    finally:
        handle.close()


@contextmanager
def atomic_write(
    path: str | os.PathLike[str],
    *,
    mode: int = FILE_MODE,
    text: bool = True,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> Iterator[IO]:
    """Write ``path`` via a private temp file in the same directory, then rename.

    Unlike :func:`open_exclusive` this *replaces* an existing file, but it does
    so without ever exposing a partially-written or over-permissive file: the
    temp file is created ``0o600`` in the destination directory (same
    filesystem, so the rename is atomic) and only moved into place on success.
    A failure leaves the original untouched.
    """
    target = Path(path)
    ensure_secure_dir(target.parent)

    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        _chmod_quietly(tmp_path, mode)
        if text:
            handle: IO = os.fdopen(fd, "w", encoding=encoding, newline=newline)
        else:
            handle = os.fdopen(fd, "wb")
        try:
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        os.replace(tmp_path, target)
        _chmod_quietly(target, mode)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def secure_temp_dir(prefix: str = "edu_") -> Path:
    """Return a fresh private temporary directory (mode ``0o700``).

    ``mkdtemp`` already creates ``0o700``; the explicit chmod guards against
    a ``TMPDIR`` on a filesystem that widens the mode. Callers own the
    directory and are responsible for removing it.
    """
    directory = Path(tempfile.mkdtemp(prefix=prefix))
    _chmod_quietly(directory, DIR_MODE)
    return directory


@contextmanager
def secure_temp_file(
    suffix: str = "", prefix: str = "edu_", *, text: bool = False
) -> Iterator[tuple[IO, Path]]:
    """Yield ``(handle, path)`` for a private temp file, removed on exit.

    Use this instead of ``tempfile.mktemp()`` (which is a TOCTOU race) or
    ``NamedTemporaryFile(delete=False)`` (which leaks the file on the error
    path). The file is created ``0o600`` and unlinked when the block exits,
    whether or not it raised.
    """
    fd, name = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    path = Path(name)
    _chmod_quietly(path, FILE_MODE)
    handle = os.fdopen(fd, "w" if text else "wb", **({"encoding": "utf-8"} if text else {}))
    try:
        yield handle, path
    finally:
        try:
            handle.close()
        finally:
            path.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Archive extraction
# ─────────────────────────────────────────────────────────────────────────────

def safe_extract(
    archive: zipfile.ZipFile | tarfile.TarFile,
    destination: str | os.PathLike[str],
    *,
    max_bytes: int = MAX_EXTRACT_BYTES,
    max_members: int = MAX_EXTRACT_MEMBERS,
    members: Iterable[str] | None = None,
) -> list[Path]:
    """Extract ``archive`` beneath ``destination``, rejecting unsafe members.

    Python's ``extractall`` will happily write ``../../etc/cron.d/x`` or follow
    a symlink member out of the destination ("zip slip"). This validates every
    member before any bytes are written:

    * the member's resolved path must stay under ``destination``;
    * absolute paths and drive letters are rejected;
    * tar symlink, hardlink, device and FIFO members are rejected;
    * the declared uncompressed total and member count are bounded.

    Extraction is all-or-nothing in intent: validation runs over the full
    member list first, so a malicious member aborts the operation before any
    file is created.

    Returns:
        The list of paths written.

    Raises:
        PathSecurityError: on any unsafe member or exceeded bound.
    """
    dest_root = ensure_secure_dir(destination)

    if isinstance(archive, zipfile.ZipFile):
        infos = [i for i in archive.infolist() if members is None or i.filename in set(members)]
        names = [i.filename for i in infos]
        total = sum(i.file_size for i in infos)
        specials = [i.filename for i in infos if _zip_member_is_special(i)]
    else:
        infos = [m for m in archive.getmembers() if members is None or m.name in set(members)]
        names = [m.name for m in infos]
        total = sum(m.size for m in infos)
        specials = [
            m.name for m in infos
            if not (m.isfile() or m.isdir())  # symlink, hardlink, dev, fifo
        ]

    if len(infos) > max_members:
        raise PathSecurityError(
            f"Archive has {len(infos)} members, above the {max_members} limit"
        )
    if total > max_bytes:
        raise PathSecurityError(
            f"Archive expands to {total} bytes, above the {max_bytes} limit"
        )
    if specials:
        raise PathSecurityError(
            f"Archive contains link or device members, which are never extracted: {specials[:5]}"
        )

    # Validate every destination before writing anything.
    targets: list[Path] = []
    for name in names:
        if not name or name in (".", ".."):
            raise PathSecurityError(f"Archive member has an invalid name: {name!r}")
        normalised = name.replace("\\", "/")
        if normalised.startswith("/") or re.match(r"^[A-Za-z]:", normalised):
            raise PathSecurityError(f"Archive member uses an absolute path: {name!r}")
        # resolve_under does the real work: it catches "a/../../b" as well as
        # any component that resolves through an existing symlink in dest.
        targets.append(resolve_under(dest_root, normalised))

    written: list[Path] = []
    for info, target in zip(infos, targets):
        is_dir = (
            info.is_dir() if isinstance(info, zipfile.ZipInfo) else info.isdir()
        )
        if is_dir:
            ensure_secure_dir(target)
            continue
        ensure_secure_dir(target.parent)
        source = (
            archive.open(info) if isinstance(archive, zipfile.ZipFile)
            else archive.extractfile(info)
        )
        if source is None:  # pragma: no cover — guarded by the specials check
            continue
        with source:
            with open_exclusive(target, text=False) as out:
                _copy_bounded(source, out, max_bytes)
        written.append(target)

    return written


def _zip_member_is_special(info: zipfile.ZipInfo) -> bool:
    """True if a zip member declares a symlink or other non-regular file type.

    Zip stores the Unix mode in the top 16 bits of ``external_attr`` when the
    archive was created on a Unix host, which is how symlink members are
    smuggled in.
    """
    unix_mode = info.external_attr >> 16
    if not unix_mode:
        return False
    file_type = stat.S_IFMT(unix_mode)
    return file_type not in (0, stat.S_IFREG, stat.S_IFDIR)


def _copy_bounded(source: IO[bytes], destination: IO[bytes], limit: int) -> None:
    """Stream ``source`` to ``destination``, aborting past ``limit`` bytes.

    The declared ``file_size`` in a zip header is attacker-controlled, so the
    up-front total is only a first filter; this enforces the bound on the bytes
    actually produced.
    """
    copied = 0
    while True:
        chunk = source.read(io.DEFAULT_BUFFER_SIZE)
        if not chunk:
            return
        copied += len(chunk)
        if copied > limit:
            raise PathSecurityError(
                f"Archive member exceeds the {limit} byte extraction limit"
            )
        destination.write(chunk)

"""Record documents: uploaded files, their versions, approval and expiry.

The compliance checklist says whether a document exists; this is the
document itself. Every upload is kept — a new version supersedes the
last rather than overwriting it, because "which version did the
employer sign?" is a question that gets asked at audit, and an
overwritten file cannot answer it.

Two rules matter more than the rest. The file is stored under a name
the system generates, never the uploader's filename: a filename is user
input, and building a path from it is how uploads escape their
directory. And the extension must come from a short allowlist, because
files are opened in the user's browser, where HTML or SVG could run.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import PurePath

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

TITLE_MAX_LENGTH = 200
FILENAME_MAX_LENGTH = 255
REASON_MAX_LENGTH = 1000


@dataclass
class Document:
    """One uploaded file — one version of one document."""

    document_id: int
    category: str
    title: str
    original_filename: str
    stored_name: str
    size_bytes: int
    sha256: str
    uploaded_by: str
    uploaded_role: str
    apprentice_id: int | None = None
    employer_id: int | None = None
    version: int = 1
    series_id: int | None = None
    supersedes: int | None = None
    checklist_key: str | None = None
    uploaded_at: str = ""
    expiry_date: str | None = None
    approval_status: str = "Pending"
    approved_by: str | None = None
    approved_at: str | None = None
    rejection_reason: str | None = None
    # Joined labels and derived state, filled in by the repository.
    apprentice_name: str | None = None
    employer_name: str | None = None
    # A newer version of this document exists.
    is_superseded: bool = False

    @property
    def is_current(self) -> bool:
        return not self.is_superseded

    @property
    def is_employer_document(self) -> bool:
        """The employer's own paperwork rather than one apprentice's."""
        return self.apprentice_id is None

    @property
    def owner_label(self) -> str:
        return self.apprentice_name or self.employer_name or config.EMPTY_CELL

    @property
    def extension(self) -> str:
        return PurePath(self.stored_name).suffix.lower()

    @property
    def size_label(self) -> str:
        return format_size(self.size_bytes)

    def is_expired(self, today: date) -> bool:
        expiry = _parse(self.expiry_date)
        return expiry is not None and expiry < today

    def expires_soon(self, today: date) -> bool:
        """Inside the warning window but not yet past it."""
        expiry = _parse(self.expiry_date)
        if expiry is None or expiry < today:
            return False
        return expiry <= today + timedelta(days=config.DOCUMENT_EXPIRY_WARNING_DAYS)

    def expiry_flag(self, today: date) -> str | None:
        if self.is_expired(today):
            return "Expired"
        if self.expires_soon(today):
            return "Expiring soon"
        return None

    def rag(self, today: date) -> str | None:
        """Red for expired or rejected, Amber for expiring soon.

        Pending is not amber: most uploads sit pending for a while, and a
        screen that is all amber tells nobody anything.
        """
        if self.is_expired(today) or self.approval_status == "Rejected":
            return "Red"
        if self.expires_soon(today):
            return "Amber"
        return None


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_category(value: str | None) -> str:
    cleaned = (value or "").strip()
    match = next(
        (c for c in config.DOCUMENT_CATEGORIES if c.casefold() == cleaned.casefold()), None
    )
    if match is None:
        allowed = ", ".join(config.DOCUMENT_CATEGORIES)
        raise ValidationError(f"Document category must be one of: {allowed}")
    return match


def validate_title(value: str | None, *, fallback: str = "") -> str:
    """A title, defaulting to the file's name without its extension."""
    text = (value or "").strip() or PurePath(fallback).stem.strip()
    if not text:
        raise ValidationError("A document needs a title")
    if len(text) > TITLE_MAX_LENGTH:
        raise ValidationError(f"A title must be {TITLE_MAX_LENGTH} characters or fewer")
    return text


def validate_upload(filename: str | None, size_bytes: int) -> str:
    """Check an upload's type and size; return its canonical extension.

    The extension returned is the allowlist's own string, not the
    uploader's text, so nothing typed by a user reaches the storage name.
    """
    name = clean_filename(filename)
    suffix = PurePath(name).suffix.lower()
    extension = next((e for e in config.DOCUMENT_EXTENSIONS if e == suffix), None)
    if extension is None:
        allowed = ", ".join(config.DOCUMENT_EXTENSIONS)
        raise ValidationError(
            f"{name or 'That file'} is not a type that can be uploaded. Allowed: {allowed}"
        )
    if size_bytes <= 0:
        raise ValidationError(f"{name} is empty")
    if size_bytes > config.DOCUMENT_MAX_BYTES:
        raise ValidationError(
            f"{name} is {format_size(size_bytes)}; the limit is "
            f"{format_size(config.DOCUMENT_MAX_BYTES)}"
        )
    return extension


def clean_filename(value: str | None) -> str:
    """The uploader's filename, reduced to something safe to *display*.

    Only the last path component is kept and control characters are
    dropped. This is still never used to build a storage path — it is
    kept so a saved copy can be offered back under the name it arrived
    with.
    """
    raw = str(value or "").replace("\\", "/")
    name = PurePath(raw).name if raw else ""
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip()
    return name[:FILENAME_MAX_LENGTH]


def validate_expiry(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError("Expiry date must be a date in YYYY-MM-DD format") from exc


def validate_rejection_reason(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(
            "A reason is required to reject a document — the uploader needs to know "
            "what to fix"
        )
    if len(text) > REASON_MAX_LENGTH:
        raise ValidationError(f"A reason must be {REASON_MAX_LENGTH} characters or fewer")
    return text


def require_approval_change(current: str, target: str) -> None:
    """Approve what is pending or was rejected; reject what is not already."""
    if target == current:
        raise ValidationError(f"This document is already {current.lower()}")
    if target not in config.DOCUMENT_APPROVAL_STATUSES:
        allowed = ", ".join(config.DOCUMENT_APPROVAL_STATUSES)
        raise ValidationError(f"Approval status must be one of: {allowed}")


def format_size(size_bytes: int) -> str:
    size = float(max(0, size_bytes))
    for unit in ("bytes", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{int(size)} bytes" if unit == "bytes" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} MB"  # pragma: no cover - loop always returns


def _parse(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None

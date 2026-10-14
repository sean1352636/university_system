"""Record documents: upload, versions, approval, expiry, and getting a copy out.

Who sees what is the heart of this module, and it is enforced here
rather than in the screens:

* an apprentice sees their own documents;
* an employer sees their apprentices' documents and their own
  organisation's paperwork;
* provider staff see their caseload's documents;
* an administrator sees everything;
* the end-point assessor sees the EPA category and nothing else. The
  EPAO is independent of the provider, so its view of an apprentice is
  the assessment paperwork, not the formative record.

Uploads from an apprentice or an employer wait for provider approval
(``document.approve``). An upload by provider staff lands approved —
they are the approvers, and making them approve their own file would be
ceremony. Every upload is kept: a new version supersedes the last
rather than replacing it.

Every function takes ``actor`` first; every write is audited.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.compliance.eligibility import (
    validate_doc_key,
)
from education_system.systems.apprenticeships.domain.records import audit
from education_system.systems.apprenticeships.domain.records import documents as rules
from education_system.systems.apprenticeships.domain.records.documents import Document
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    document_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    employer_repository,
)
from education_system.systems.apprenticeships.infrastructure.storage import document_store
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    may_view_apprentice,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def list_documents(
    actor: Actor,
    *,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    category: str | None = None,
    categories: list[str] | tuple[str, ...] | None = None,
    approval_status: str | None = None,
    current_only: bool = True,
    expiring_only: bool = False,
    expiring_within_days: int | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> list[Document]:
    """The documents *actor* may see, with any extra filters applied.

    The actor's own scope is applied last and wins: an employer passing
    somebody else's ``employer_id`` narrows to nothing rather than
    widening. ``expiring_only`` keeps documents expired or expiring
    within the warning window (or *expiring_within_days*, if given).
    """
    require(actor, "document.view")
    filters: dict[str, Any] = {
        "apprentice_id": apprentice_id,
        "employer_id": employer_id,
        "tutor_id": tutor_id,
        "category": category,
        "categories": categories,
        "approval_status": approval_status,
        "current_only": current_only,
        "search": search,
        "limit": limit,
    }
    if expiring_only or expiring_within_days is not None:
        days = (
            config.DOCUMENT_EXPIRY_WARNING_DAYS
            if expiring_within_days is None else int(expiring_within_days)
        )
        filters["expiring_before"] = (date.today() + timedelta(days=days)).isoformat()

    if actor.role == config.END_POINT_ASSESSOR:
        wanted = {category} if category else set(categories or ())
        if wanted and config.EPA_DOCUMENT_CATEGORY not in wanted:
            return []
        filters.update(
            category=config.EPA_DOCUMENT_CATEGORY, categories=None, apprentice_only=True
        )
    else:
        filters.update(apprentice_filters(actor))
    return repo.list_documents(**filters)


def get_document(actor: Actor, document_id: int) -> Document:
    """One document, or raise if the actor may not see it."""
    require(actor, "document.view")
    return _load(actor, document_id)


def version_history(actor: Actor, document_id: int) -> list[Document]:
    """Every version of a document, newest first."""
    document = get_document(actor, document_id)
    return repo.list_versions(document.series_id or document.document_id)


def expiring_documents(actor: Actor, **filters: Any) -> list[Document]:
    """Current documents expired or inside the warning window, soonest first."""
    rows = list_documents(actor, expiring_only=True, **filters)
    return sorted(rows, key=lambda d: d.expiry_date or "")


def document_counts(actor: Actor) -> dict[str, int]:
    """Headline figures for the documents screen and dashboards."""
    rows = list_documents(actor)
    today = date.today()
    return {
        "total": len(rows),
        "pending": sum(1 for d in rows if d.approval_status == "Pending"),
        "rejected": sum(1 for d in rows if d.approval_status == "Rejected"),
        "expiring": sum(1 for d in rows if d.expires_soon(today)),
        "expired": sum(1 for d in rows if d.is_expired(today)),
    }


def checklist_files(actor: Actor, apprentice_id: int) -> dict[str, list[Document]]:
    """Uploaded files per compliance-checklist item, for one apprentice.

    Lets the checklist show which items have the actual paperwork behind
    them, without the checklist itself changing.
    """
    grouped: dict[str, list[Document]] = {}
    for document in list_documents(actor, apprentice_id=apprentice_id):
        if document.checklist_key:
            grouped.setdefault(document.checklist_key, []).append(document)
    return grouped


def categories_for(actor: Actor) -> tuple[str, ...]:
    """The categories this actor can see, for filter dropdowns."""
    if actor.role == config.END_POINT_ASSESSOR:
        return (config.EPA_DOCUMENT_CATEGORY,)
    return config.DOCUMENT_CATEGORIES


def upload_owners(actor: Actor) -> list[dict[str, Any]]:
    """Whose file an upload can be filed against, for a picker.

    Each row is ``{"label", "apprentice_id", "employer_id"}``; exactly one
    id is set. An apprentice gets only themselves; an employer their
    apprentices plus their own organisation; staff their caseload; an
    administrator everyone, and every employer.
    """
    require(actor, "document.upload")
    if actor.role == config.APPRENTICE:
        if actor.apprentice_id is None:
            return []
        record = apprentice_repository.get(actor.apprentice_id)
        label = record.full_name if record else "My documents"
        return [{"label": label, "apprentice_id": actor.apprentice_id, "employer_id": None}]

    owners = [
        {"label": f"{s.full_name} ({s.apprentice.status})",
         "apprentice_id": s.apprentice.apprentice_id, "employer_id": None}
        for s in apprentice_repository.list_summaries(**apprentice_filters(actor))
    ]
    if actor.role == config.EMPLOYER and actor.employer_id:
        employer = employer_repository.get(actor.employer_id)
        owners.insert(0, {
            "label": f"{employer.name if employer else 'Our organisation'} "
                     "(organisation document)",
            "apprentice_id": None, "employer_id": actor.employer_id,
        })
    elif actor.is_admin:
        owners += [
            {"label": f"{e.name} (employer document)", "apprentice_id": None,
             "employer_id": e.employer_id}
            for e in employer_repository.list_all()
        ]
    return owners


# ═════════════════════════════════════════════════════════════════════
# Uploads
# ═════════════════════════════════════════════════════════════════════

def upload_document(
    actor: Actor,
    source: str | Path,
    *,
    category: str,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    title: str | None = None,
    expiry_date: str | None = None,
    checklist_key: str | None = None,
) -> Document:
    """File a new document, copying *source* into the document store.

    The copy is stored under a generated name; the original filename is
    kept only as a label. If the database write fails the copied file is
    removed, so the store never holds bytes no row points at.
    """
    require(actor, "document.upload")
    owner_apprentice, owner_employer = _resolve_owner(actor, apprentice_id, employer_id)
    cleaned_category = rules.validate_category(category)
    expiry = rules.validate_expiry(expiry_date)
    checklist = _validate_checklist_key(checklist_key, owner_apprentice)
    path, name, extension = _check_source(source)
    cleaned_title = rules.validate_title(title, fallback=name)

    stored = document_store.store(path, extension, max_bytes=config.DOCUMENT_MAX_BYTES)
    payload = {
        "apprentice_id": owner_apprentice,
        "employer_id": owner_employer,
        "category": cleaned_category,
        "title": cleaned_title,
        "original_filename": name,
        "stored_name": stored.stored_name,
        "size_bytes": stored.size_bytes,
        "sha256": stored.sha256,
        "version": 1,
        "checklist_key": checklist,
        "uploaded_by": actor.username,
        "uploaded_role": actor.role,
        "expiry_date": expiry,
        **_initial_approval(actor),
    }
    document_id = _insert(payload, stored.stored_name)

    compliance_repository.record(
        action="create", entity="document", entity_id=document_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Uploaded {cleaned_category} “{cleaned_title}” "
               f"({rules.format_size(stored.size_bytes)}) for {_owner_text(payload)}",
    )
    logger.info("Document %s uploaded by %s", document_id, actor.username)
    return _reload(document_id)


def upload_new_version(
    actor: Actor,
    document_id: int,
    source: str | Path,
    *,
    title: str | None = None,
    expiry_date: str | None = None,
) -> Document:
    """Add a new version of a document, keeping every earlier one.

    Only the latest version can be superseded, so the history stays a
    single line. The new version inherits the owner, category and
    checklist link; its approval starts again, because it is a
    different file. *expiry_date* left as None keeps the current one;
    an empty string clears it.
    """
    require(actor, "document.upload")
    existing = _load(actor, document_id)
    _require_current(existing, "add a new version")
    path, name, extension = _check_source(source)
    cleaned_title = rules.validate_title(title, fallback=existing.title)
    expiry = existing.expiry_date if expiry_date is None else rules.validate_expiry(expiry_date)

    stored = document_store.store(path, extension, max_bytes=config.DOCUMENT_MAX_BYTES)
    payload = {
        "apprentice_id": existing.apprentice_id,
        "employer_id": existing.employer_id,
        "category": existing.category,
        "title": cleaned_title,
        "original_filename": name,
        "stored_name": stored.stored_name,
        "size_bytes": stored.size_bytes,
        "sha256": stored.sha256,
        "version": existing.version + 1,
        "series_id": existing.series_id or existing.document_id,
        "supersedes": existing.document_id,
        "checklist_key": existing.checklist_key,
        "uploaded_by": actor.username,
        "uploaded_role": actor.role,
        "expiry_date": expiry,
        **_initial_approval(actor),
    }
    new_id = _insert(payload, stored.stored_name)

    compliance_repository.record(
        action="create", entity="document", entity_id=new_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"New version of “{cleaned_title}” (supersedes document {document_id})",
        changes=audit.diff(existing, payload, fields=(
            "version", "original_filename", "title", "size_bytes", "expiry_date",
        )),
    )
    logger.info("Document %s superseded by %s (%s)", document_id, new_id, actor.username)
    return _reload(new_id)


# ═════════════════════════════════════════════════════════════════════
# Approval and details
# ═════════════════════════════════════════════════════════════════════

def approve_document(actor: Actor, document_id: int) -> Document:
    require(actor, "document.approve")
    existing = _load(actor, document_id)
    _require_current(existing, "approve it")
    rules.require_approval_change(existing.approval_status, "Approved")
    return _decide(actor, existing, "Approved", reason=None)


def reject_document(actor: Actor, document_id: int, *, reason: str) -> Document:
    """Send a document back. The reason is shown to the uploader."""
    require(actor, "document.approve")
    existing = _load(actor, document_id)
    _require_current(existing, "reject it")
    rules.require_approval_change(existing.approval_status, "Rejected")
    return _decide(actor, existing, "Rejected", reason=rules.validate_rejection_reason(reason))


def update_details(actor: Actor, document_id: int, payload: dict[str, Any]) -> Document:
    """Correct a document's title, expiry date or checklist link.

    The file itself cannot be edited — a different file is a new
    version. Only keys present in *payload* change.
    """
    require(actor, "document.approve")
    existing = _load(actor, document_id)
    data: dict[str, Any] = {}
    if "title" in payload:
        data["title"] = rules.validate_title(payload.get("title"), fallback=existing.title)
    if "expiry_date" in payload:
        data["expiry_date"] = rules.validate_expiry(payload.get("expiry_date"))
    if "checklist_key" in payload:
        data["checklist_key"] = _validate_checklist_key(
            payload.get("checklist_key"), existing.apprentice_id
        )
    changes = audit.diff(existing, data, fields=list(data))
    if not changes:
        return existing

    repo.update(document_id, data)
    compliance_repository.record(
        action="update", entity="document", entity_id=document_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Details of “{existing.title}” corrected", changes=changes,
    )
    return _reload(document_id)


# ═════════════════════════════════════════════════════════════════════
# Getting at the file
# ═════════════════════════════════════════════════════════════════════

def file_path(actor: Actor, document_id: int) -> Path:
    """Where the stored file is, for opening it in place.

    Read-only use only: a caller wanting a copy to keep or send should
    use :func:`save_copy`, which is audited.
    """
    document = get_document(actor, document_id)
    path = document_store.path_for(document.stored_name)
    if not path.is_file():
        raise ValidationError(
            f"The file for “{document.title}” is missing from the document store"
        )
    return path


def save_copy(
    actor: Actor, document_id: int, destination: str | Path, *, overwrite: bool = False
) -> Path:
    """Copy a document out to a path of the user's choosing.

    A directory as the destination gets the file under the name it was
    uploaded with. Refuses to write into the document store itself.
    """
    document = get_document(actor, document_id)
    if not str(destination or "").strip():
        raise ValidationError("Choose where to save the copy")
    target = Path(destination).expanduser()
    if target.is_dir():
        target = target / (document.original_filename or f"document-{document_id}")
    if not target.parent.is_dir():
        raise ValidationError(f"The folder {target.parent} does not exist")
    store_root = document_store.root().resolve()
    if target.resolve().parent == store_root or store_root in target.resolve().parents:
        raise ValidationError("Save the copy somewhere outside the document store")
    if target.exists() and not overwrite:
        raise ValidationError(f"{target} already exists")
    if not document_store.exists(document.stored_name):
        raise ValidationError(
            f"The file for “{document.title}” is missing from the document store"
        )

    document_store.copy_to(document.stored_name, target)
    compliance_repository.record(
        action="export", entity="document", entity_id=document_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Saved a copy of “{document.title}” v{document.version}",
    )
    return target


def verify_file(actor: Actor, document_id: int) -> bool:
    """Is the stored file still exactly what was uploaded?"""
    document = get_document(actor, document_id)
    if not document_store.exists(document.stored_name):
        return False
    return document_store.sha256_of(document.stored_name) == document.sha256


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def may_view(actor: Actor, document: Document) -> bool:
    """Is this document inside *actor*'s scope? See the module docstring."""
    if not actor.can("document.view"):
        return False
    if actor.role == config.END_POINT_ASSESSOR:
        return (
            document.category == config.EPA_DOCUMENT_CATEGORY
            and document.apprentice_id is not None
        )
    if document.apprentice_id is not None:
        return may_view_apprentice(actor, apprentice_repository.get(document.apprentice_id))
    if actor.is_admin:
        return True
    if actor.role == config.EMPLOYER:
        return actor.employer_id is not None and document.employer_id == actor.employer_id
    return False


def _load(actor: Actor, document_id: int) -> Document:
    document = repo.get(document_id)
    if document is None:
        raise ValidationError(f"No document with id {document_id}")
    if not may_view(actor, document):
        # Deliberately does not confirm the document exists.
        raise PermissionDenied("You do not have access to this document")
    return document


def _reload(document_id: int) -> Document:
    document = repo.get(document_id)
    assert document is not None
    return document


def _insert(payload: dict[str, Any], stored_name: str) -> int:
    """Write the row; if that fails, take the copied file back out."""
    try:
        return repo.create(payload)
    except Exception:
        document_store.discard(stored_name)
        raise


def _decide(actor: Actor, existing: Document, status: str, *, reason: str | None) -> Document:
    data = {
        "approval_status": status,
        "approved_by": actor.username,
        "approved_at": _now(),
        "rejection_reason": reason,
    }
    repo.update(existing.document_id, data)
    compliance_repository.record(
        action="approve" if status == "Approved" else "reject",
        entity="document", entity_id=existing.document_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"{status} “{existing.title}” v{existing.version}"
               + (f": {reason}" if reason else ""),
        changes=audit.diff(
            existing, data, fields=("approval_status", "approved_by", "rejection_reason")
        ),
    )
    logger.info("Document %s %s by %s", existing.document_id, status.lower(), actor.username)
    return _reload(existing.document_id)


def _resolve_owner(
    actor: Actor, apprentice_id: int | None, employer_id: int | None
) -> tuple[int | None, int | None]:
    """Whose document this is: (apprentice_id, None) or (None, employer_id)."""
    if actor.role == config.APPRENTICE:
        if actor.apprentice_id is None:
            raise PermissionDenied("Your login is not linked to an apprentice record yet")
        if employer_id is not None or apprentice_id not in (None, actor.apprentice_id):
            raise PermissionDenied("You may only upload documents to your own record")
        return actor.apprentice_id, None

    if apprentice_id is not None and employer_id is not None:
        raise ValidationError("A document belongs to an apprentice or to an employer, not both")
    if apprentice_id is not None:
        record = apprentice_repository.get(apprentice_id)
        if record is None:
            raise ValidationError(f"No apprentice with id {apprentice_id}")
        require_apprentice_access(actor, record)
        return apprentice_id, None

    if employer_id is None and actor.role == config.EMPLOYER:
        employer_id = actor.employer_id
    if employer_id is None:
        raise ValidationError("Choose the apprentice or employer this document belongs to")
    if actor.role == config.EMPLOYER:
        if employer_id != actor.employer_id:
            raise PermissionDenied("You may only file documents for your own organisation")
    elif not actor.is_admin:
        raise PermissionDenied(
            "An employer's own documents are filed by the employer or an administrator"
        )
    if employer_repository.get(employer_id) is None:
        raise ValidationError(f"No employer with id {employer_id}")
    return None, employer_id


def _check_source(source: str | Path | None) -> tuple[Path, str, str]:
    """The upload's path, display name and canonical extension."""
    if not str(source or "").strip():
        raise ValidationError("Choose a file to upload")
    path = Path(str(source)).expanduser()
    if not path.is_file():
        raise ValidationError(f"There is no file at {path}")
    name = rules.clean_filename(path.name)
    extension = rules.validate_upload(name, path.stat().st_size)
    return path, name, extension


def _validate_checklist_key(value: Any, apprentice_id: int | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if apprentice_id is None:
        raise ValidationError("Only an apprentice's document can evidence a checklist item")
    return validate_doc_key(text)


def _initial_approval(actor: Actor) -> dict[str, Any]:
    if actor.is_provider:
        return {"approval_status": "Approved", "approved_by": actor.username,
                "approved_at": _now()}
    return {"approval_status": "Pending"}


def _owner_text(payload: dict[str, Any]) -> str:
    if payload.get("apprentice_id") is not None:
        return f"apprentice {payload['apprentice_id']}"
    return f"employer {payload.get('employer_id')}"


def _require_current(document: Document, action: str) -> None:
    if document.is_superseded:
        raise ValidationError(
            f"A newer version of “{document.title}” exists — open that one to {action}"
        )


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

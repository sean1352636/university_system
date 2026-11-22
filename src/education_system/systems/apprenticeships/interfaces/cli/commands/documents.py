"""Documents: uploaded files, their versions, approval and expiry.

Exposes: menu.

The same commands serve every role; the service decides what each sees
(an apprentice their own, an employer their apprentices' and their
organisation's, a tutor their caseload's, the end-point assessor EPA
documents only) and each entry below appears only for a role that may
use it. Files come in by typed path and go out by typed path: the copy
kept in the document store is never handed out directly.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial
from pathlib import Path

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.records.documents import (
    Document,
    format_size,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import signatures
from education_system.systems.apprenticeships.application.records import (
    document_service,
    signature_service,
)
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("#", -5), ("Category", 20), ("Title", 28), ("Belongs to", 20), ("Ver", -4),
    ("Approval", 9), ("Expires", 11), ("Expiry", 13),
)
_VERSION_COLUMNS = (
    ("#", -5), ("Ver", -4), ("File uploaded", 30), ("Uploaded", 19), ("By", 12),
    ("Approval", 9), ("Size", -9),
)

_CHECKLIST_LABELS = dict(config.COMPLIANCE_DOCUMENTS)


def menu(actor: Actor) -> None:
    """Everything this actor may do with documents."""
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List documents", partial(_list, actor)),
        ("Expired and expiring documents", partial(_expiring, actor)),
        ("One document's details", partial(_details, actor)),
        ("Version history", partial(_history, actor)),
        ("Save a copy", partial(_save_copy, actor)),
    ]
    if actor.can("document.upload"):
        entries += [
            ("Upload a document", partial(_upload, actor)),
            ("Upload a new version", partial(_new_version, actor)),
        ]
    if actor.can("document.approve"):
        entries += [
            ("Approve a document", partial(_approve, actor)),
            ("Reject a document", partial(_reject, actor)),
            ("Correct a document's details", partial(_correct, actor)),
        ]
    if actor.can("signature.sign"):
        entries.append(("Sign an agreement", partial(_sign, actor)))
    heading = "EPA Documents" if actor.role == config.END_POINT_ASSESSOR else "Documents"
    prompts.run_menu(heading, entries)


# ═════════════════════════════════════════════════════════════════════
# Reading
# ═════════════════════════════════════════════════════════════════════

def _list(actor: Actor) -> None:
    categories = document_service.categories_for(actor)
    category = (
        categories[0] if len(categories) == 1
        else prompts.choose("Category (blank for all)", categories, allow_blank=True)
    )
    approval = prompts.choose(
        "Approval (blank for all)", config.DOCUMENT_APPROVAL_STATUSES, allow_blank=True
    )
    history = prompts.ask_yes_no("Include earlier versions?")
    rows = document_service.list_documents(
        actor, category=category, approval_status=approval, current_only=not history,
    )
    prompts.title("Documents")
    _table(rows)
    prompts.pause()


def _expiring(actor: Actor) -> None:
    rows = document_service.expiring_documents(actor)
    prompts.title("Expired and expiring documents")
    prompts.note(
        f"Expired, or expiring within {config.DOCUMENT_EXPIRY_WARNING_DAYS} days. Upload a "
        "new version to replace one."
    )
    _table(rows, empty="nothing has expired or is about to")
    prompts.pause()


def _details(actor: Actor) -> None:
    document = _pick(actor, "Which document?")
    today = date.today()
    prompts.title(document.title)
    prompts.details([
        ("Category", document.category),
        ("Belongs to", document.owner_label
         + (" (organisation document)" if document.is_employer_document else "")),
        ("Version", f"{document.version}" + ("" if document.is_current else " (superseded)")),
        ("File uploaded", document.original_filename),
        ("Size", document.size_label),
        ("Uploaded", f"{document.uploaded_at} by {document.uploaded_by}"),
        ("Approval", document.approval_status
         + (f" by {document.approved_by} on {document.approved_at}"
            if document.approved_by else "")),
        ("Rejection reason", document.rejection_reason),
        ("Expires", document.expiry_date),
        ("Expiry", document.expiry_flag(today)),
        ("Checklist item", _CHECKLIST_LABELS.get(document.checklist_key or "")),
        ("SHA-256", document.sha256),
    ])
    state = signature_service.signoff(actor, "document", document.document_id)
    if state.required:
        signatures.show_signoff(state)
    prompts.pause()


def _history(actor: Actor) -> None:
    document = _pick(actor, "Which document?")
    versions = document_service.version_history(actor, document.document_id)
    prompts.title(f"Versions — {document.title}")
    prompts.table(
        _VERSION_COLUMNS,
        versions,
        lambda v: (v.document_id, v.version, v.original_filename, v.uploaded_at,
                   v.uploaded_by, v.approval_status, v.size_label),
        noun="version",
    )
    prompts.pause()


def _save_copy(actor: Actor) -> None:
    document = _pick(actor, "Which document?", include_history=True)
    suggested = str(Path.cwd() / document.original_filename)
    destination = prompts.ask("Save the copy to (a file or a folder)", default=suggested)
    target = Path(destination).expanduser()
    if target.is_dir():
        target = target / document.original_filename
    overwrite = False
    if target.exists():
        if not prompts.ask_yes_no(f"{target} already exists. Replace it?"):
            raise prompts.Abort
        overwrite = True
    saved = document_service.save_copy(actor, document.document_id, target, overwrite=overwrite)
    prompts.ok(f"Saved to {saved}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Uploading
# ═════════════════════════════════════════════════════════════════════

def _upload(actor: Actor) -> None:
    owners = document_service.upload_owners(actor)
    if not owners:
        prompts.fail("There is no record you can file a document against yet.")
        raise prompts.Abort
    prompts.title("Upload a document")
    owner = owners[0] if len(owners) == 1 else prompts.choose(
        "Whose document is it?", owners, render=lambda o: o["label"]
    )
    path = _ask_path()
    category = prompts.choose_value("Category", config.DOCUMENT_CATEGORIES, default="Other")
    title = prompts.ask("Title", default=path.stem)
    expiry = prompts.ask("Expires (YYYY-MM-DD, blank if it does not lapse)")
    checklist = None
    if actor.is_provider and owner["apprentice_id"] is not None:
        chosen = prompts.choose(
            "Evidences checklist item (blank for none)", list(config.COMPLIANCE_DOCUMENTS),
            render=lambda pair: pair[1], allow_blank=True,
        )
        checklist = chosen[0] if chosen else None

    document = document_service.upload_document(
        actor, path, category=category, apprentice_id=owner["apprentice_id"],
        employer_id=owner["employer_id"], title=title, expiry_date=expiry or None,
        checklist_key=checklist,
    )
    prompts.ok(f"Uploaded “{document.title}” ({document.size_label}) — "
               f"{document.approval_status.lower()}.")
    if document.approval_status == "Pending":
        prompts.note("Your provider will check it before it is approved.")
    prompts.pause()


def _new_version(actor: Actor) -> None:
    document = _pick(actor, "New version of which document?")
    path = _ask_path()
    title = prompts.ask("Title", default=document.title)
    expiry = prompts.ask(
        "Expires (YYYY-MM-DD; type 'none' to clear)", default=document.expiry_date or ""
    )
    updated = document_service.upload_new_version(
        actor, document.document_id, path, title=title,
        expiry_date="" if expiry.lower() == "none" else expiry,
    )
    prompts.ok(f"“{updated.title}” is now at version {updated.version}. Earlier versions "
               "are kept.")
    prompts.pause()


def _ask_path() -> Path:
    raw = prompts.ask("Path to the file", required=True)
    path = Path(raw.strip().strip("'\"")).expanduser()
    if not path.is_file():
        prompts.fail(f"There is no file at {path}.")
        raise prompts.Abort
    prompts.note(f"{path.name} — {format_size(path.stat().st_size)}")
    return path


# ═════════════════════════════════════════════════════════════════════
# Approval, details, signing
# ═════════════════════════════════════════════════════════════════════

def _approve(actor: Actor) -> None:
    document = _pick(actor, "Approve which document?", approval_status="Pending")
    if not prompts.ask_yes_no(f"Approve “{document.title}”?", default=True):
        raise prompts.Abort
    document_service.approve_document(actor, document.document_id)
    prompts.ok(f"Approved “{document.title}”.")
    prompts.pause()


def _reject(actor: Actor) -> None:
    document = _pick(actor, "Reject which document?")
    reason = prompts.ask("Reason (the uploader sees this)", required=True)
    document_service.reject_document(actor, document.document_id, reason=reason)
    prompts.ok(f"Rejected “{document.title}”.")
    prompts.pause()


def _correct(actor: Actor) -> None:
    document = _pick(actor, "Which document?")
    payload: dict[str, object] = {
        "title": prompts.ask("Title", default=document.title, required=True),
        "expiry_date": prompts.ask(
            "Expires (YYYY-MM-DD; type 'none' to clear)", default=document.expiry_date or ""
        ),
    }
    if str(payload["expiry_date"]).lower() == "none":
        payload["expiry_date"] = ""
    updated = document_service.update_details(actor, document.document_id, payload)
    prompts.ok(f"Updated “{updated.title}”.")
    prompts.pause()


def _sign(actor: Actor) -> None:
    rows = [r for r in signature_service.awaiting_signature(actor) if r.entity_type == "document"]
    if not rows:
        prompts.ok("No agreement is waiting for your signature.")
        prompts.pause()
        return
    row = prompts.choose(
        "Which agreement?", rows,
        render=lambda r: f"{r.title} — {r.apprentice_name or ''} ({r.signoff.summary})",
    )
    signatures.show_signoff(row.signoff)
    signatures.sign(actor, row.entity_type, row.entity_id, row.title)
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _pick(
    actor: Actor, heading: str, *, include_history: bool = False, **filters: object
) -> Document:
    rows = document_service.list_documents(
        actor, current_only=not include_history, **filters  # type: ignore[arg-type]
    )
    if not rows:
        prompts.fail("There are no documents to choose from.")
        raise prompts.Abort
    return prompts.choose(
        heading, rows,
        render=lambda d: (
            f"{d.category}: {d.title} — {d.owner_label} (v{d.version}, {d.approval_status})"
        ),
    )


def _table(rows: list[Document], *, empty: str | None = None) -> None:
    today = date.today()
    prompts.table(
        _COLUMNS,
        rows,
        lambda d: (d.document_id, d.category, d.title, d.owner_label,
                   f"{d.version}" + ("" if d.is_current else "*"), d.approval_status,
                   d.expiry_date, d.expiry_flag(today)),
        noun="document",
        empty=empty or "no documents",
    )

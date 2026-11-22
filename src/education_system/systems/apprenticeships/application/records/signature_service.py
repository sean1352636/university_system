"""Digital signatures on learning plans and agreement documents.

A signature records that a signatory agreed to something *as it then
stood*: the content is hashed when they sign, and the signature counts
only while the content still hashes the same. Editing a plan after the
employer signed it therefore lapses the employer's signature on its
own, and the plan reappears on their "Awaiting Signature" list.

Who signs as what is fixed by role (config.SIGNATORY_BY_ROLE), and a
signatory may sign only inside their own scope: an apprentice their own
plan and documents, an employer those of the apprentices they employ,
provider staff their caseload's (administrators, everyone's). The
end-point assessor never signs.

Two things are signable today (config.SIGNATURE_REQUIREMENTS): the
learning plan, and apprentice documents in the Learning Agreement and
Commitment Statement categories. Progress reviews keep their own,
older ``review_signatures`` and are not handled here.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.records import audit
from education_system.systems.apprenticeships.domain.records import signatures as rules
from education_system.systems.apprenticeships.domain.records.documents import Document
from education_system.systems.apprenticeships.domain.records.signatures import (
    DOCUMENT,
    LEARNING_PLAN,
    PendingSignature,
    Signature,
    SignOff,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    signature_repository as repo,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    learning_plan_repository,
    training_repository,
)
from education_system.systems.apprenticeships.infrastructure.storage import document_store
from education_system.systems.apprenticeships.application.records import document_service
from education_system.systems.apprenticeships.application.security.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
    require_apprentice_access,
)

logger = logging.getLogger(__name__)

# Whose plans still want signing. A finished or departed apprentice's
# plan is history, not an agreement anybody is waiting on.
_CLOSED_STATUSES = frozenset({"Completed", "Withdrawn", "Transferred"})


# ═════════════════════════════════════════════════════════════════════
# Reads
# ═════════════════════════════════════════════════════════════════════

def signoff(actor: Actor, entity_type: str, entity_id: int) -> SignOff:
    """Where one thing stands: its required signatories and their state."""
    subject = _subject(actor, entity_type, entity_id)
    return _signoff(subject, repo.list_signatures(entity_type=entity_type, entity_id=entity_id))


def signoffs_for_documents(actor: Actor, documents: list[Document]) -> dict[int, SignOff]:
    """Sign-off state for many documents at once, keyed by document id.

    For a list screen's "Signatures" column. The documents are assumed
    to have come from :mod:`document_service`, so already scoped; this
    reads their signatures in one query rather than one per row.
    """
    require(actor, "document.view")
    ids = [d.document_id for d in documents]
    by_entity = _group(repo.list_signatures(entity_type=DOCUMENT, entity_ids=ids))
    return {
        d.document_id: _signoff(_document_subject(d), by_entity.get(d.document_id, []))
        for d in documents
    }


def awaiting_signature(actor: Actor) -> list[PendingSignature]:
    """Everything in *actor*'s scope that still needs their signature.

    That includes anything they signed which has changed since — those
    come first, because somebody is relying on an agreement that no
    longer carries their name.
    """
    require(actor, "signature.sign")
    signatory = rules.signatory_for(actor.role)
    if signatory is None:
        return []
    pending = _pending_plans(actor, signatory) + _pending_documents(actor, signatory)
    pending.sort(key=lambda p: (
        p.status != rules.INVALIDATED, (p.apprentice_name or "").casefold(), p.title.casefold(),
    ))
    return pending


# ═════════════════════════════════════════════════════════════════════
# Signing
# ═════════════════════════════════════════════════════════════════════

def sign(
    actor: Actor, entity_type: str, entity_id: int, *, statement: str | None = None
) -> Signature:
    """Sign something as the actor's signatory role.

    Refused if the thing does not need that signatory, if they have
    already signed its current content, or — for a document — if it is
    not the latest version, was rejected, or its stored file no longer
    matches what was uploaded.
    """
    require(actor, "signature.sign")
    signatory = rules.signatory_for(actor.role)
    if signatory is None:
        raise PermissionDenied("Your role does not sign records")
    subject = _subject(actor, entity_type, entity_id)
    current = _signoff(subject, repo.list_signatures(entity_type=entity_type, entity_id=entity_id))
    rules.require_can_sign(current, signatory)
    _require_signable(subject)
    text = rules.validate_statement(statement)
    previous_state = current.state(signatory)

    signature_id = repo.create(
        entity_type=entity_type,
        entity_id=entity_id,
        apprentice_id=subject["apprentice_id"],
        signatory_role=signatory,
        signed_by=actor.username,
        signer_role=actor.role,
        statement=text,
        content_hash=subject["hash"],
    )
    compliance_repository.record(
        action="sign", entity=entity_type, entity_id=entity_id,
        actor=actor.username, actor_role=actor.role,
        detail=f"Signed as {signatory}: {subject['title']}"
               + (" (re-signed after a change)" if previous_state == rules.INVALIDATED else ""),
        changes=audit.change(f"{signatory} signature", previous_state, rules.SIGNED),
    )
    logger.info("%s %s signed as %s by %s", entity_type, entity_id, signatory, actor.username)

    created = repo.get(signature_id)
    assert created is not None
    return created


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _subject(actor: Actor, entity_type: str, entity_id: int) -> dict[str, Any]:
    """Load the thing, check the actor may see it, and hash its content now."""
    if entity_type == LEARNING_PLAN:
        # The plan is formative: training.view is what reading it needs,
        # and the end-point assessor deliberately lacks it.
        require(actor, "training.view")
        apprentice = apprentice_repository.get(entity_id)
        if apprentice is None:
            raise ValidationError(f"No apprentice with id {entity_id}")
        require_apprentice_access(actor, apprentice)
        return _plan_subject(entity_id, apprentice.full_name)
    if entity_type == DOCUMENT:
        return _document_subject(document_service.get_document(actor, entity_id))
    raise ValidationError(f"{entity_type!r} is not something that can be signed")


def _plan_subject(apprentice_id: int, name: str) -> dict[str, Any]:
    objectives = learning_plan_repository.list_objectives(apprentice_id)
    activities = training_repository.list_plan_items(apprentice_id)
    return {
        "entity_type": LEARNING_PLAN,
        "entity_id": apprentice_id,
        "apprentice_id": apprentice_id,
        "title": f"Learning plan — {name}",
        "hash": rules.plan_hash(objectives, activities),
        "required": rules.required_signatories(LEARNING_PLAN),
        "empty": not objectives and not activities,
        "document": None,
    }


def _document_subject(document: Document) -> dict[str, Any]:
    # An employer's own paperwork has no apprentice to sign it, so the
    # three-way requirement applies to apprentice documents only.
    required = (
        rules.required_signatories(DOCUMENT, document.category)
        if document.apprentice_id is not None else ()
    )
    return {
        "entity_type": DOCUMENT,
        "entity_id": document.document_id,
        "apprentice_id": document.apprentice_id,
        "title": document.title,
        "hash": rules.document_hash(document.sha256),
        "required": required,
        "empty": False,
        "document": document,
    }


def _signoff(subject: dict[str, Any], signatures: list[Signature]) -> SignOff:
    return rules.signoff(
        subject["entity_type"], subject["entity_id"], subject["hash"], subject["required"],
        signatures, apprentice_id=subject["apprentice_id"], title=subject["title"],
    )


def _require_signable(subject: dict[str, Any]) -> None:
    if subject["empty"]:
        raise ValidationError("There is nothing on this plan to sign yet")
    document: Document | None = subject["document"]
    if document is None:
        return
    if document.is_superseded:
        raise ValidationError("A newer version of this document exists — sign that one")
    if document.approval_status == "Rejected":
        raise ValidationError("A rejected document cannot be signed; upload a new version")
    # The signature vouches for the bytes on file, so check they are the
    # bytes that were uploaded before putting a name to them.
    if (not document_store.exists(document.stored_name)
            or document_store.sha256_of(document.stored_name) != document.sha256):
        raise ValidationError(
            "The stored file no longer matches what was uploaded, so it cannot be signed. "
            "Ask the provider to check the document store."
        )


def _pending_plans(actor: Actor, signatory: str) -> list[PendingSignature]:
    required = rules.required_signatories(LEARNING_PLAN)
    if signatory not in required or not actor.can("training.view"):
        return []
    people = [
        s for s in apprentice_repository.list_summaries(**apprentice_filters(actor))
        if s.apprentice.status not in _CLOSED_STATUSES
    ]
    by_entity = _group(repo.list_signatures(
        entity_type=LEARNING_PLAN, entity_ids=[s.apprentice.apprentice_id for s in people],
    ))
    pending = []
    for summary in people:
        apprentice_id = summary.apprentice.apprentice_id
        subject = _plan_subject(apprentice_id, summary.full_name)
        if subject["empty"]:
            continue
        state = _signoff(subject, by_entity.get(apprentice_id, []))
        if state.state(signatory) != rules.SIGNED:
            pending.append(PendingSignature(
                signoff=state, signatory_role=signatory, title=subject["title"],
                apprentice_name=summary.full_name,
            ))
    return pending


def _pending_documents(actor: Actor, signatory: str) -> list[PendingSignature]:
    categories = [
        c for c in config.DOCUMENT_CATEGORIES
        if signatory in rules.required_signatories(DOCUMENT, c)
    ]
    if not categories or not actor.can("document.view"):
        return []
    documents = [
        d for d in document_service.list_documents(actor, categories=categories)
        if d.apprentice_id is not None and d.approval_status != "Rejected"
    ]
    states = signoffs_for_documents(actor, documents)
    return [
        PendingSignature(
            signoff=states[d.document_id], signatory_role=signatory, title=d.title,
            apprentice_name=d.apprentice_name, category=d.category,
        )
        for d in documents
        if states[d.document_id].state(signatory) != rules.SIGNED
    ]


def _group(signatures: list[Signature]) -> dict[int, list[Signature]]:
    grouped: dict[int, list[Signature]] = {}
    for signature in signatures:
        grouped.setdefault(signature.entity_id, []).append(signature)
    return grouped

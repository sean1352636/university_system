"""Search across the whole system, within what the actor may see.

Every source is searched through the same scoped reads its own screen
uses, so a search can never show an employer another organisation's
apprentice, or a tutor someone outside their caseload. A source the
actor has no permission for is simply skipped — the results do not say
"there were matches you cannot see", because that would tell them
something.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.workspace.items import SearchResult, matches
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    portfolio_repository,
    review_repository,
)
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    email_service,
    employer_service,
    programme_service,
    qualification_service,
)
from education_system.systems.apprenticeships.services import (
    appeal_service,
    assignment_service,
    complaint_service,
    document_service,
)
from education_system.systems.apprenticeships.services.access import (
    Actor,
    PermissionDenied,
    apprentice_filters,
    require,
)

logger = logging.getLogger(__name__)

Provider = Callable[[Actor, str], list[SearchResult]]

_APPRENTICE_SCREENS: dict[str, tuple[str, str]] = {
    config.ADMIN: ("admin.apprentices", "Apprentices"),
    config.STAFF: ("staff.caseload", "My Caseload"),
    config.EMPLOYER: ("employer.apprentices", "My Apprentices"),
    config.APPRENTICE: ("apprentice.profile", "My Details"),
}
_EMPLOYER_SCREENS: dict[str, tuple[str, str]] = {
    config.ADMIN: ("admin.employers", "Employers"),
    config.STAFF: ("shared.employer_contacts", "Employer Contacts"),
}
_REVIEW_SCREENS: dict[str, tuple[str, str]] = {
    config.STAFF: ("staff.reviews", "Progress Reviews"),
    config.APPRENTICE: ("apprentice.reviews", "Progress Reviews"),
    config.EMPLOYER: ("employer.reviews", "Progress Reviews"),
}
_EVIDENCE_SCREENS: dict[str, tuple[str, str]] = {
    config.STAFF: ("staff.portfolios", "Portfolios"),
    config.APPRENTICE: ("apprentice.portfolio", "Portfolio"),
    config.EMPLOYER: ("employer.evidence", "Evidence"),
}
_MESSAGE_SCREEN: tuple[str, str] = ("shared.email", "Correspondence")


def search(actor: Actor, text: str) -> list[SearchResult]:
    """Everything *actor* may see that matches *text*, grouped by kind."""
    require(actor, "search.use")
    query = (text or "").strip()
    if len(query) < config.SEARCH_MIN_LENGTH:
        raise ValidationError(f"Type at least {config.SEARCH_MIN_LENGTH} characters to search")
    results: list[SearchResult] = []
    for provider in _PROVIDERS:
        try:
            results.extend(provider(actor, query)[:config.SEARCH_LIMIT_PER_KIND])
        except PermissionDenied:
            continue
        except Exception:
            logger.exception("Search source %s failed for %s", provider.__name__, actor.username)
    return results


# ═════════════════════════════════════════════════════════════════════
# Providers
# ═════════════════════════════════════════════════════════════════════

def _apprentices(actor: Actor, query: str) -> list[SearchResult]:
    if not (actor.can("apprentice.view") or actor.can("apprentice.view_own")):
        return []
    return [
        SearchResult(
            "Apprentice", s.full_name,
            " · ".join([s.programme_title or "No programme", s.employer_name or "No employer",
                        s.apprentice.status]),
            apprentice_id=s.apprentice.apprentice_id,
            opens=_APPRENTICE_SCREENS.get(actor.role),
        )
        # An apprentice's cohort is always just themselves, whatever the
        # search, so the match is re-checked on the fields the listing's
        # own search covers.
        for s in apprentice_service.list_apprentices(actor, search=query)
        if matches(query, s.full_name, s.apprentice.uln, s.apprentice.email)
    ]


def _employers(actor: Actor, query: str) -> list[SearchResult]:
    if not actor.can("employer.view"):
        return []
    return [
        SearchResult(
            "Employer", e.employer.name,
            f"{e.active_apprentices} active apprentice(s) · {e.employer.status}",
            opens=_EMPLOYER_SCREENS.get(actor.role),
        )
        # An employer user always gets their own organisation back, so
        # the match is re-checked here rather than trusted.
        for e in employer_service.list_employers(actor, search=query)
        if matches(query, e.employer.name)
    ]


def _programmes(actor: Actor, query: str) -> list[SearchResult]:
    if not actor.can("programme.view"):
        return []
    opens = ("admin.programmes", "Programmes & KSBs") if actor.role == config.ADMIN else None
    return [
        SearchResult("Programme", f"{p.reference} {p.title}", f"Level {p.level} · {p.status}",
                     opens=opens)
        for p in programme_service.list_programmes(actor, search=query)
    ]


def _reviews(actor: Actor, query: str) -> list[SearchResult]:
    if not actor.can("review.view"):
        return []
    return [
        SearchResult(
            "Progress review", f"{r.apprentice_name} — {r.held_date or r.scheduled_date}",
            f"{r.status}" + (f" · {r.summary[:80]}" if r.summary else ""),
            apprentice_id=r.apprentice_id, opens=_REVIEW_SCREENS.get(actor.role),
        )
        for r in review_repository.list_reviews(**apprentice_filters(actor))
        if matches(query, r.apprentice_name, r.summary, r.apprentice_comments,
                   r.employer_comments)
    ]


def _evidence(actor: Actor, query: str) -> list[SearchResult]:
    if not actor.can("portfolio.view"):
        return []
    names = {
        s.apprentice.apprentice_id: s.full_name
        for s in apprentice_repository.list_summaries(**apprentice_filters(actor))
    }
    return [
        SearchResult(
            "Evidence", e.title,
            f"{names.get(e.apprentice_id, 'Apprentice')} · {e.evidence_type} · {e.status}",
            apprentice_id=e.apprentice_id, opens=_EVIDENCE_SCREENS.get(actor.role),
        )
        for e in portfolio_repository.list_evidence(**apprentice_filters(actor), limit=1000)
        if matches(query, e.title, e.description, e.evidence_type, names.get(e.apprentice_id))
    ]


def _messages(actor: Actor, query: str) -> list[SearchResult]:
    if not actor.can("email.view"):
        return []
    return [
        SearchResult(
            "Message", m.get("subject") or "(no subject)",
            " · ".join(filter(None, [
                str(m.get("sent_at") or m.get("created_at") or ""),
                m.get("to_name") or m.get("from_name") or m.get("to_address"),
            ])),
            apprentice_id=m.get("apprentice_id"), opens=_MESSAGE_SCREEN,
        )
        for m in email_service.search(actor, query=query)
    ]


def _qualifications(actor: Actor, query: str) -> list[SearchResult]:
    if not actor.can("qualification.view"):
        return []
    return [
        SearchResult(
            "Qualification", q.title,
            " · ".join(filter(None, [q.status, q.level, q.awarding_body, q.reference])),
            apprentice_id=q.apprentice_id, opens=("shared.qualifications", "Qualifications"),
        )
        for q in qualification_service.list_qualifications(actor)
        if matches(query, q.title, q.awarding_body, q.reference, q.level)
    ]


def _assignments(actor: Actor, query: str) -> list[SearchResult]:
    if not actor.can("assignment.view"):
        return []
    return [
        SearchResult("Assignment", a.title,
                     " · ".join(filter(None, [a.apprentice_name, a.assignment_type, a.status])),
                     apprentice_id=a.apprentice_id, opens=("shared.assignments", "Assignments"))
        for a in assignment_service.list_assignments(actor)
        if matches(query, a.title, a.assignment_type, a.ksb_codes, a.apprentice_name)
    ]


def _documents(actor: Actor, query: str) -> list[SearchResult]:
    """By title or filename — through the document service, so the EPAO
    still only ever sees EPA documents."""
    if not actor.can("document.view"):
        return []
    return [
        SearchResult(
            "Document", d.title,
            " · ".join(filter(None, [d.apprentice_name or d.employer_name, d.category,
                                     f"v{d.version}", d.approval_status])),
            apprentice_id=d.apprentice_id, opens=("shared.documents", "Documents"),
        )
        for d in document_service.list_documents(actor, search=query)
    ]


def _complaints(actor: Actor, query: str) -> list[SearchResult]:
    """By reference or subject — the complainant's own, or all for a handler."""
    if not (actor.can("complaint.raise") or actor.can("complaint.manage")):
        return []
    return [
        SearchResult("Complaint", f"{c.reference} {c.subject}", f"{c.category} · {c.status}",
                     apprentice_id=c.apprentice_id, opens=("shared.complaints", "Complaints"))
        for c in complaint_service.list_complaints(actor)
        if matches(query, c.reference, c.subject, c.category)
    ]


def _appeals(actor: Actor, query: str) -> list[SearchResult]:
    if not (actor.can("appeal.raise") or actor.can("appeal.decide")):
        return []
    return [
        SearchResult("Appeal", f"{a.reference} {a.appeal_type}",
                     " · ".join(filter(None, [a.apprentice_name, a.status])),
                     apprentice_id=a.apprentice_id, opens=("shared.appeals", "Appeals"))
        for a in appeal_service.list_appeals(actor)
        if matches(query, a.reference, a.appeal_type, a.apprentice_name, a.decision_ref)
    ]


_PROVIDERS: tuple[Provider, ...] = (
    _apprentices,
    _employers,
    _programmes,
    _reviews,
    _evidence,
    _messages,
    _qualifications,
    _assignments,
    _documents,
    _complaints,
    _appeals,
)

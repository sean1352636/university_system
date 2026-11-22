"""Comparing work with sources outside the university.

The university's own corpus (other submissions, references) misses text
taken from the web, published papers and essay mills. Two ways in:

* **Import** (:func:`import_text`) — an integrity officer adds known
  external texts (an essay-mill sample bought for comparison, a widely
  copied article) as ``external`` documents. Every later check compares
  against them, on every module.
* **Search** (:func:`search_external`) — for one document, the most
  distinctive phrases (at most ``external_max_queries``) are searched in
  published sources (``infrastructure/integrity/external_sources``, CORE).
  Works found are stored as ``external`` documents and the document is
  checked again, so the new result shows them as matched sources. Only the
  phrases leave the university, and only when ``external_checks`` is on;
  the student notice should say so before it is turned on.
"""

from __future__ import annotations

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.application.integrity import plagiarism_text as ptext

PHRASE_WORDS = 10
MIN_SENTENCE_WORDS = 12


def import_text(conn, who: access.Person, *, title, content, file_type="txt",
                source_url=None) -> int:
    """Add one external text (integrity officers)."""
    access.require(access.is_officer(conn, who), "Only an integrity officer can add external "
                                                 "sources")
    doc_id = checks._store(conn, title=title, content=content, file_type=file_type,
                           module_code=None, kind="external", author_id=who.user_id,
                           source_url=source_url or None)
    access.audit(conn, who.username, "document", doc_id, "external added",
                 {"url": source_url or None})
    return doc_id


def phrases(text, file_type="txt", limit=5) -> list[str]:
    """The most distinctive phrases of ``text``: from its longest sentences,
    the ten-word stretch with the most long words."""
    prepared = ptext.prepare(text, file_type)
    if prepared.code:
        return []
    picks = []
    for first, last in prepared.sentences:
        if last - first + 1 < MIN_SENTENCE_WORDS:
            continue
        best, best_rank = None, -1
        for start in range(first, last - PHRASE_WORDS + 2):
            window = prepared.tokens[start:start + PHRASE_WORDS]
            rank = sum(1 for w in window if len(w) >= 7)
            if rank > best_rank:
                best, best_rank = start, rank
        if best is not None:
            a = prepared.spans[best][0]
            b = prepared.spans[best + PHRASE_WORDS - 1][1]
            picks.append((best_rank, " ".join(str(text)[a:b].split())))
    picks.sort(key=lambda p: p[0], reverse=True)
    seen, out = set(), []
    for _rank, phrase in picks:
        if phrase.lower() not in seen:
            seen.add(phrase.lower())
            out.append(phrase)
        if len(out) >= limit:
            break
    return out


def search_external(conn, who: access.Person, document_id) -> dict:
    """Search published sources for ``document_id`` and check it again.
    Returns ``{"result_id", "queries", "sources_added", "errors"}``."""
    from education_system.systems.university.infrastructure.integrity import external_sources
    access.ensure(conn)
    if access.setting(conn, "external_checks") != "1":
        raise ValueError("External-source checks are turned off in the integrity settings")
    doc = access.one(conn, "SELECT * FROM document_repository WHERE id = ?", (document_id,))
    if not doc:
        raise ValueError(f"No document {document_id}")
    access.require(who.is_staff and access.can_review(conn, who, doc["module_code"]),
                   "Only the module's staff can search external sources for this work")
    if doc.get("purged"):
        raise ValueError("This document's text has been removed under the retention policy")
    if not external_sources.configured():
        raise ValueError("No external search service is set up: an administrator must add a "
                         "CORE API key")
    queries = phrases(doc["content"], doc["file_type"],
                      int(access.number(conn, "external_max_queries")))
    if not queries:
        raise ValueError("No phrases long enough to search (external search is for prose)")
    found, errors = [], []
    for phrase in queries:              # no write yet: nothing is locked while we wait
        try:
            found += external_sources.search(phrase)
        except external_sources.ExternalSearchError as exc:
            errors.append(str(exc))
    added = 0
    for work in found:
        before = conn.execute("SELECT COUNT(*) FROM document_repository WHERE kind = 'external'"
                              ).fetchone()[0]
        checks._store(conn, title=work["title"], content=work["text"], file_type="txt",
                      module_code=None, kind="external", author_id=who.user_id,
                      source_url=work["url"] or None)
        added += conn.execute("SELECT COUNT(*) FROM document_repository WHERE kind = 'external'"
                              ).fetchone()[0] - before
    conn.execute("INSERT INTO integrity_external_searches (document_id, provider, queries, "
                 "sources_added, error, ran_by, ran_at) VALUES (?, 'core', ?, ?, ?, ?, ?)",
                 (document_id, len(queries), added, "; ".join(errors) or None, who.username,
                  access.now()))
    access.audit(conn, who.username, "document", document_id, "external search",
                 {"queries": len(queries), "added": added, "errors": len(errors)})
    if errors and not found:
        raise ValueError(errors[0])
    result_id = checks.run_check(conn, document_id, who=who)
    conn.execute("UPDATE plagiarism_results SET external_checked_at = ? WHERE id = ?",
                 (access.now(), result_id))
    return {"result_id": result_id, "queries": len(queries), "sources_added": added,
            "errors": errors}


def searches(conn, who: access.Person, document_id) -> list[dict]:
    doc = checks.document(conn, who, document_id)
    access.require(who.is_staff, "Only staff can see this")
    return access.dicts(conn.execute("SELECT * FROM integrity_external_searches WHERE "
                                     "document_id = ? ORDER BY search_id DESC", (doc["id"],)))

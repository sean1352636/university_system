"""Search fan-out and the ``run_search`` entry point for Advanced Search.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

from typing import Any

from .models import (  # noqa: F401
    ALL_SCOPES,
    DEFAULT_LIMIT_PER_SCOPE,
    QueryOptions,
    SearchResults,
    ValidationError,
)
from ._db import (  # noqa: F401
    _cache_get,
    _cache_key,
    _cache_put,
    _validate_scopes,
    init_db,
    logger,
)
from .query import (  # noqa: F401
    _collect_student_predicates,
    _doc_student_id,
    _extract_scope_directives,
    _resolve_student_predicates,
    did_you_mean,
    expand_macros,
    parse_query,
)
from .matching import (  # noqa: F401
    SCOPE_ACL,
    SENSITIVE_LOG_AREAS,
    _STUDENT_KEYED_SCOPES,
    _build_filter_context,
    _ctx_allows,
    _doc_match,
    _hit_matched_fields,
    _make_highlights,
    _redact_hit,
    _score_hit,
)
from .sources import (  # noqa: F401
    _ADAPTERS,
)
from .history import (  # noqa: F401
    _cluster_by_student,
    _record_history,
    _record_search_audit,
    list_pinned,
)


# ══════════════════════════════════════════════════════════════════
# Async fan-out (item 49)
# ══════════════════════════════════════════════════════════════════

def _fanout(scopes: list[str], parsed: ParsedQuery,
            opts: QueryOptions, filters: dict[str, Any],
            max_workers: int = 8,
            ) -> tuple[dict[str, list[Hit]], dict[str, float]]:
    import concurrent.futures as _cf
    import time as _t
    raw: dict[str, list[Hit]] = {}
    ms: dict[str, float] = {}

    def one(scope: str) -> tuple[str, list[Hit], float]:
        adapter = _ADAPTERS[scope]
        t0 = _t.monotonic()
        try:
            hits = adapter(parsed, opts, filters)
        except Exception:
            logger.exception("Adapter %s failed", scope)
            hits = []
        return scope, hits, (_t.monotonic() - t0) * 1000.0

    if max_workers <= 1 or len(scopes) <= 1:
        for s in scopes:
            _, h, t = one(s)
            raw[s] = h
            ms[s] = round(t, 2)
        return raw, ms
    with _cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for fut in _cf.as_completed(ex.submit(one, s) for s in scopes):
            s, h, t = fut.result()
            raw[s] = h
            ms[s] = round(t, 2)
    return raw, ms


# ══════════════════════════════════════════════════════════════════
# Public search API
# ══════════════════════════════════════════════════════════════════

def run_search(
    query: str,
    *,
    scopes: list[str] | tuple[str, ...] | None = None,
    filters: dict[str, Any] | None = None,
    limit_per_scope: int = DEFAULT_LIMIT_PER_SCOPE,
    record_history: bool = True,
    actor: str | None = None,
    options: QueryOptions | None = None,
    rank: bool = True,
    highlight: bool = True,
    recency_boost: bool = True,
    interleave: bool = False,
    cluster_by_student: bool = False,
) -> SearchResults:
    """Run a query across the given scopes.

    Filter dict (item 23–30) accepts: ``year_group``, ``tutor_group``,
    ``owned_by_staff``, ``role``, ``include_archived``, ``sen_only``,
    ``tags``, ``postcode_prefix``, ``actor``.

    When someone is signed in, the actor and role are that account's, and
    the ``actor`` argument and ``role``/``actor`` filters are ignored.
    """
    init_db()
    scopes_use = _validate_scopes(scopes)
    filters = filters or {}
    if limit_per_scope is None or limit_per_scope <= 0:
        raise ValidationError("limit_per_scope must be positive")
    raw_q = (query or "").strip()
    opts = options or QueryOptions()

    # Preprocess: expand @macros (item 18), then strip scope: / -scope:
    # directives (item 17) and fold them into the scope selection.
    q = expand_macros(raw_q)
    q, inc_scopes, exc_scopes = _extract_scope_directives(q)
    if inc_scopes or exc_scopes:
        for name in (*inc_scopes, *exc_scopes):
            if name not in ALL_SCOPES:
                raise ValidationError(
                    f"Unknown scope {name!r} in query. "
                    f"Valid: {', '.join(ALL_SCOPES)}")
        base = inc_scopes if inc_scopes else list(scopes_use)
        scopes_use = [s for s in dict.fromkeys(base) if s not in exc_scopes]
        if not scopes_use:
            raise ValidationError(
                "Scope directives left no scopes to search")

    try:
        parsed = parse_query(q, opts)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Could not parse query: {exc}") from exc

    ctx = _build_filter_context(filters, opts)
    if ctx.signed_in or not actor:
        actor = ctx.actor
    active_scopes = [s for s in scopes_use if s not in ctx.drop_scopes]

    # Student-level predicates — aggregates (13), has/missing joins (11),
    # cohort membership (12) → one student set per predicate node, used to
    # evaluate the query per student-keyed row (so OR / NOT work).
    predicates = _collect_student_predicates(parsed)
    pred_sets: dict[int, set[str]] | None = None
    if predicates:
        pred_sets = _resolve_student_predicates(predicates, opts)

    # Sensitive-access audit (items 33, 35): log whenever a gated scope is
    # actually searched, or accessed under break-glass.
    sensitive_active = [s for s in active_scopes
                        if s in SCOPE_ACL or s in SENSITIVE_LOG_AREAS]
    if sensitive_active and (actor or ctx.break_glass_reason):
        _record_search_audit(
            actor, ctx.role, raw_q, active_scopes, sensitive_active,
            bool(ctx.break_glass_reason), ctx.break_glass_reason)
    if ctx.signed_in:
        _log_sensitive_search(sensitive_active, raw_q, ctx)

    flags = (rank, highlight, recency_boost, interleave,
             cluster_by_student, bool(filters.get("use_cache", True)))
    cache_key = _cache_key(q, active_scopes, filters, opts, actor, flags)
    if filters.get("use_cache", True):
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    pinned_keys: set[tuple[str, str]] = set()
    if actor:
        pinned_keys = {(p.scope, p.entity_id) for p in list_pinned(actor)}

    # Async fan-out (item 49) with per-scope timing
    raw_by_scope, elapsed_ms = _fanout(
        active_scopes, parsed, opts, filters,
        max_workers=int(filters.get("max_workers", 8)))

    hits_by_scope: dict[str, list[Hit]] = {}
    matched_by_scope: dict[str, int] = {}
    total = 0
    for scope in scopes_use:
        if scope in ctx.drop_scopes:
            hits_by_scope[scope] = []
            matched_by_scope[scope] = 0
            continue
        # Adapters read the live tables, so every row is considered; the
        # FTS index (Tools ▸ Index) is not used to narrow them, because a
        # stale index would silently hide new records.
        raw_hits = raw_by_scope.get(scope, [])
        kept: list[Hit] = []
        for h, doc in _zip_hits_with_docs(raw_hits, scope, parsed, opts,
                                          ctx, filters):
            if not _ctx_allows(scope, doc, ctx):
                continue
            # Student predicates (items 11–13) only mean something for rows
            # about one student; re-evaluate the whole query with them.
            if pred_sets is not None:
                if scope not in _STUDENT_KEYED_SCOPES:
                    continue
                if not _doc_match(parsed, {**doc, "_pred_sets": pred_sets,
                                           "_sid": _doc_student_id(scope, doc)},
                                  opts):
                    continue
            mf = _hit_matched_fields(parsed, doc, opts)
            h.matched_fields = mf
            if mf and not h.matched_field:
                h.matched_field = "matched in: " + ", ".join(mf[:3])
            if rank:
                h.score = _score_hit(parsed, doc, mf, ctx, opts,
                                     recency_boost)
            if highlight:
                h.highlights = _make_highlights(parsed, doc, mf, opts)
            if (scope, h.entity_id) in pinned_keys:
                h.pinned = True
                h.score += 1.0
            if ctx.redact:
                _redact_hit(h, scope)
            kept.append(h)
        if rank:
            kept.sort(key=lambda x: (-x.pinned, -x.score))
        matched_by_scope[scope] = len(kept)
        if limit_per_scope and len(kept) > limit_per_scope:
            kept = kept[:limit_per_scope]
        hits_by_scope[scope] = kept
        total += len(kept)

    flat = [h for hits in hits_by_scope.values() for h in hits]
    if cluster_by_student:
        flat = _cluster_by_student(flat)
    if interleave:
        flat.sort(key=lambda x: (-x.pinned, -x.score))

    # Did-you-mean (item 20): only when a real query found nothing.
    suggestions: list[str] = []
    if total == 0 and q:
        try:
            suggestions = did_you_mean(q, opts)
        except Exception:
            logger.debug("did_you_mean failed", exc_info=True)

    matched_total = sum(matched_by_scope.values())
    if record_history:
        try:
            _record_history(raw_q, scopes_use, actor, matched_total,
                            elapsed_ms=elapsed_ms,
                            result_counts={s: len(hits_by_scope[s])
                                            for s in scopes_use})
        except Exception:
            logger.exception("Failed to record search history")

    out = SearchResults(
        query=raw_q,
        scopes=scopes_use,
        hits_by_scope=hits_by_scope,
        total=total,
        ranked_hits=flat,
        suggestions=suggestions,
        matched_by_scope=matched_by_scope,
        matched_total=matched_total,
    )
    if filters.get("use_cache", True):
        _cache_put(cache_key, out)
    return out


def _log_sensitive_search(scopes: list[str], query: str,
                          ctx: FilterContext) -> None:
    """Write searches of safeguarding/SEND/medical records to the
    sensitive-access log the DSL reviews, as opening one would be."""
    sensitive = [s for s in scopes if s in SENSITIVE_LOG_AREAS]
    if not sensitive:
        return
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    action = "search" + (f" (break-glass: {ctx.break_glass_reason})"
                         if ctx.break_glass_reason else "")
    for scope in sensitive:
        access.log_sensitive_access(p, SENSITIVE_LOG_AREAS[scope], action,
                                    record_ref=f"advanced_search:{query[:200]}")


def _zip_hits_with_docs(hits: list[Hit], scope: str,
                         parsed: ParsedQuery,
                         opts: QueryOptions,
                         ctx: FilterContext,
                         filters: dict) -> Any:
    """Re-derive each hit's doc dict. Adapters discard the dict after
    emitting the Hit, so we ask them to expose it via ``extra['_doc']``
    when one was built. As a fallback we synthesize a minimal doc from
    the hit's label/sublabel so filters/scoring still apply."""
    for h in hits:
        doc = h.extra.get("_doc") if isinstance(h.extra, dict) else None
        if not doc:
            doc = {
                "id":    h.entity_id,
                "title": h.label,
                "notes": h.sublabel,
            }
        yield h, doc

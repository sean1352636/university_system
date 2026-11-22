"""Index status/refresh, FTS candidates, duplicates, data gaps, facets,
trends, NL-to-query, examples, telemetry and suggestions for Advanced Search.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

import json
import re
from dataclasses import field
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (  # noqa: F401
    ALL_SCOPES,
    DataGap,
    DuplicateGroup,
    Facet,
    IndexStatus,
    QueryOptions,
    TelemetrySummary,
    TrendPoint,
    ValidationError,
)
from ._db import (  # noqa: F401
    _connect,
    _fts_available,
    _validate_scopes,
    init_db,
    logger,
)
from .query import (  # noqa: F401
    _Aggregate,
    _And,
    _Cohort,
    _Compare,
    _Has,
    _Not,
    _Or,
    _Phrase,
    _Range,
    _Regex,
    _RelCompare,
    _Term,
    _fold,
)
from .sources import (  # noqa: F401
    _ADAPTERS,
)


def _doc_to_index_text(doc: dict[str, Any]) -> str:
    parts = []
    for k, v in doc.items():
        if k.startswith("_") and k != "_all":
            continue
        if v:
            parts.append(str(v))
    return " ".join(parts)


def _scope_row_count(scope: str, opts: QueryOptions) -> int:
    adapter = _ADAPTERS.get(scope)
    if adapter is None:
        return 0
    try:
        return len(adapter(None, opts, {}))
    except Exception:
        logger.exception("row count for %s failed", scope)
        return 0


def index_status(
    scopes: list[str] | tuple[str, ...] | None = None,
) -> list[IndexStatus]:
    """Per-scope FTS index freshness (item 41): indexed vs current row
    counts, last refresh, and whether the mirror is stale."""
    init_db()
    scopes_use = _validate_scopes(scopes) if scopes else list(ALL_SCOPES)
    opts = QueryOptions()
    with _connect() as conn:
        meta = {r["scope"]: r for r in conn.execute(
            "SELECT scope, indexed_rows, last_refresh "
            "FROM search_index_meta").fetchall()}
    out: list[IndexStatus] = []
    for scope in scopes_use:
        m = meta.get(scope)
        indexed = (m["indexed_rows"] if m else 0) or 0
        last = m["last_refresh"] if m else None
        current = _scope_row_count(scope, opts)
        out.append(IndexStatus(
            scope=scope, indexed_rows=indexed, current_rows=current,
            last_refresh=last, stale=(last is None or current != indexed)))
    return out


def stale_scopes() -> list[str]:
    return [s.scope for s in index_status() if s.stale]


def refresh_index(
    scopes: list[str] | tuple[str, ...] | None = None,
    *, only_stale: bool = False,
) -> dict[str, int]:
    """Rebuild the FTS5 mirror for the given scopes (default: all).

    With ``only_stale=True`` only scopes whose row count drifted from the
    last indexed count are rebuilt — a cheap incremental refresh (item 41).

    Returns ``{scope: rows_indexed}``. Adapters are called with an empty
    parsed query so every row appears, and the text bag is the doc
    field-values joined."""
    init_db()
    if not _fts_available():
        return {}
    scopes_use = _validate_scopes(scopes) if scopes else list(ALL_SCOPES)
    if only_stale:
        stale = {s.scope for s in index_status(scopes_use) if s.stale}
        scopes_use = [s for s in scopes_use if s in stale]
    opts = QueryOptions()
    counts: dict[str, int] = {}
    with _connect() as conn:
        for scope in scopes_use:
            adapter = _ADAPTERS.get(scope)
            if adapter is None:
                continue
            try:
                hits = adapter(None, opts, {})
            except Exception:
                logger.exception("refresh_index: adapter %s failed", scope)
                continue
            conn.execute(
                "DELETE FROM search_index_fts WHERE scope = ?", (scope,))
            n = 0
            for h in hits:
                doc = (h.extra or {}).get("_doc") or {}
                text = _doc_to_index_text(doc) \
                       or f"{h.label} {h.sublabel}"
                conn.execute(
                    "INSERT INTO search_index_fts(scope, entity_id, text) "
                    "VALUES (?, ?, ?)",
                    (scope, h.entity_id, text),
                )
                n += 1
            conn.execute(
                "INSERT INTO search_index_meta(scope, indexed_rows, "
                "last_refresh) VALUES (?, ?, datetime('now')) "
                "ON CONFLICT(scope) DO UPDATE SET "
                "indexed_rows = excluded.indexed_rows, "
                "last_refresh = excluded.last_refresh",
                (scope, n))
            counts[scope] = n
        conn.commit()
    logger.info("Refreshed FTS index: %s", counts)
    return counts


def _fts_query_for(parsed: ParsedQuery) -> str | None:
    """Build an FTS5 MATCH string from the AST. Returns None when the
    query can't be cleanly expressed (wildcards, fuzzy, comparators)."""
    if parsed is None:
        return None

    def walk(n: ParsedQuery) -> str | None:
        if isinstance(n, _Term):
            if n.fuzzy or n.wildcard or n.field:
                return None
            if not n.text:
                return None
            return f'"{n.text}"'
        if isinstance(n, _Phrase):
            if n.field or n.proximity:
                return None
            return f'"{n.text}"'
        if isinstance(n, (_Compare, _Range, _Regex, _RelCompare,
                          _Aggregate, _Has, _Cohort)):
            return None
        if isinstance(n, _Not):
            sub = walk(n.child)
            return f"NOT {sub}" if sub else None
        if isinstance(n, _And):
            ps = [walk(c) for c in n.children]
            if any(p is None for p in ps):
                return None
            return "(" + " AND ".join(ps) + ")"
        if isinstance(n, _Or):
            ps = [walk(c) for c in n.children]
            if any(p is None for p in ps):
                return None
            return "(" + " OR ".join(ps) + ")"
        return None

    return walk(parsed)


def _fts_candidates(parsed: ParsedQuery,
                    scopes: list[str]) -> dict[str, set[str]] | None:
    """Return {scope: {entity_id,...}} candidate hits from FTS5, or None
    if we should fall back to a full scan."""
    if not _fts_available():
        return None
    qstr = _fts_query_for(parsed)
    if not qstr:
        return None
    out: dict[str, set[str]] = {s: set() for s in scopes}
    try:
        with _connect() as conn:
            ph = ",".join("?" * len(scopes))
            rows = conn.execute(
                f"SELECT scope, entity_id FROM search_index_fts "
                f"WHERE scope IN ({ph}) AND text MATCH ?",
                (*scopes, qstr)).fetchall()
        for r in rows:
            out.setdefault(r["scope"], set()).add(r["entity_id"])
        return out
    except db.OperationalError:
        return None


def find_duplicate_students() -> list[DuplicateGroup]:
    """Likely-duplicate student records grouped by matching email,
    surname+date-of-birth, or normalised full name (item 44)."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    buckets: dict[tuple[str, str], set[str]] = {}

    def add(reason: str, key: str, sid: str) -> None:
        buckets.setdefault((reason, key), set()).add(sid)

    for s in sm.list_students():
        if s.email:
            add("email", s.email.strip().lower(), s.student_id)
        if s.last_name and s.date_of_birth:
            add("surname+dob",
                f"{s.last_name.strip().lower()}|{s.date_of_birth.strip()}",
                s.student_id)
        fn = _fold((s.full_name or "").lower()).strip()
        if fn:
            add("name", fn, s.student_id)
    out = [DuplicateGroup(reason=reason, key=key, student_ids=sorted(ids))
           for (reason, key), ids in buckets.items() if len(ids) > 1]
    out.sort(key=lambda g: -len(g.student_ids))
    return out


_DEFAULT_REQUIRED: dict[str, tuple[str, ...]] = {
    "students": ("email", "phone", "date_of_birth", "subjects"),
}


def find_data_gaps(scope: str = "students", *,
                   required: list[str] | None = None) -> list[DataGap]:
    """Records missing required fields (item 45). For ``students`` the
    default required set is email/phone/DOB/three-subjects; other scopes
    use their adapter docs and the given ``required`` field names."""
    if scope not in ALL_SCOPES:
        raise ValidationError(f"Unknown scope {scope!r}")
    out: list[DataGap] = []
    if scope == "students":
        from education_system.systems.sixth_form.domain.learners.students import (
            students as sm,
        )
        req = list(required or _DEFAULT_REQUIRED["students"])
        for s in sm.list_students():
            missing: list[str] = []
            for f in req:
                if f == "subjects":
                    if len([x for x in (s.subjects or []) if x]) < 3:
                        missing.append("subjects")
                elif not getattr(s, f, None):
                    missing.append(f)
            if missing:
                out.append(DataGap("students", s.student_id,
                                   s.full_name, missing))
        return out
    adapter = _ADAPTERS.get(scope)
    if adapter is None:
        raise ValidationError(f"No adapter for scope {scope!r}")
    req = list(required or ("name",))
    for h in adapter(None, QueryOptions(), {}):
        doc = (h.extra or {}).get("_doc") or {}
        missing = [f for f in req if not doc.get(f)]
        if missing:
            out.append(DataGap(scope, h.entity_id, h.label, missing))
    return out


# ══════════════════════════════════════════════════════════════════
# Analytics & discovery (items 46–50)
# ══════════════════════════════════════════════════════════════════

def search_volume_by_day(*, days: int = 30) -> list[tuple[str, int]]:
    """Search counts per calendar day from history, newest first (item 46)."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT substr(ts, 1, 10) AS d, COUNT(*) AS n "
            "FROM search_history GROUP BY d ORDER BY d DESC LIMIT ?",
            (int(days),)).fetchall()
    return [(r["d"], r["n"]) for r in rows]


_FACET_FIELDS: tuple[str, ...] = (
    "status", "category", "level", "type", "role", "department")


def facets(results: SearchResults, *,
           fields: list[str] | None = None, top: int = 6) -> list[Facet]:
    """Value distributions across a result set, for click-to-narrow filter
    chips (item 47)."""
    use = list(fields or _FACET_FIELDS)
    counts: dict[str, dict[str, int]] = {f: {} for f in use}
    for h in results.all_hits():
        doc = (h.extra or {}).get("_doc") or {}
        for f in use:
            v = str(doc.get(f) or "").strip()
            if v:
                counts[f][v] = counts[f].get(v, 0) + 1
    out: list[Facet] = []
    for f in use:
        if counts[f]:
            vals = sorted(counts[f].items(),
                          key=lambda kv: (-kv[1], kv[0]))[:top]
            out.append(Facet(field=f, values=vals))
    return out


def query_trend(query: str, *, limit: int = 30) -> list[TrendPoint]:
    """Historical result counts for an identical query over time (item 48),
    oldest→newest."""
    init_db()
    q = (query or "").strip()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ts, result_count FROM search_history WHERE query = ? "
            "ORDER BY ts DESC, history_id DESC LIMIT ?",
            (q, int(limit))).fetchall()
    return [TrendPoint(ts=r["ts"], count=r["result_count"])
            for r in reversed(rows)]


# Subjects the NL translator recognises (kept small + explicit).
_NL_SUBJECTS: frozenset[str] = frozenset({
    "maths", "mathematics", "physics", "chemistry", "biology", "english",
    "geography", "psychology", "economics", "accounting", "history",
    "sociology", "philosophy", "politics", "art", "music", "drama",
})

_NL_JOIN_SCOPES: tuple[tuple[str, str], ...] = (
    ("attendance concern", "attendance_concerns"),
    ("behaviour", "behaviour"),
    ("safeguarding", "safeguarding"),
    ("ucas", "ucas"),
    ("predicted grade", "predicted_grades"),
)


def nl_to_query(text: str) -> str:
    """Best-effort natural-language → structured-query translator (item 49).

    Recognises a fixed set of patterns (attendance thresholds, has/missing
    joins, predicted<target, grade floors, subjects, cohorts); anything it
    can't map is dropped. Always review the result before running."""
    t = " " + (text or "").lower().strip() + " "
    parts: list[str] = []

    m = re.search(r"(under|below|less than)\s+(\d{1,3})\s*%?\s*attendance", t)
    if m:
        parts.append(f"attendance:<{m.group(2)}")
    m = re.search(r"(over|above|more than)\s+(\d{1,3})\s*%?\s*attendance", t)
    if m:
        parts.append(f"attendance:>{m.group(2)}")

    for kw, scope in _NL_JOIN_SCOPES:
        if re.search(r"(without|no|missing)\s+(a\s+)?" + re.escape(kw), t):
            parts.append(f"missing({scope})")
        elif re.search(r"(with|has|having)\s+(a\s+|an\s+)?" + re.escape(kw), t):
            parts.append(f"has({scope})")

    if "below target" in t or "under target" in t:
        parts.append("predicted<target")

    m = re.search(r"grade\s+([a-eu]\*?)\s*(or above|and above|\+|or higher)", t)
    if m:
        parts.append(f"grade:>={m.group(1).upper()}")

    for w in sorted(_NL_SUBJECTS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(w) + r"\b", t):
            parts.append(f"subject:{w}")

    m = re.search(r"cohort\s+([a-z0-9_./-]+)", t)
    if m:
        parts.append(f"cohort:{m.group(1)}")

    return " ".join(dict.fromkeys(parts))


# Onboarding examples (item 50) — (description, query).
QUERY_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("Students named Smith", "name:smith"),
    ("Under 85% attendance", "attendance:<85"),
    ("Attendance between 80 and 90%", "attendance:80..90"),
    ('Exact phrase "merit award"', '"merit award"'),
    ("Student IDs by pattern (regex)", r"/C\d{4,}/"),
    ("Open safeguarding (needs role)", "scope:safeguarding status:open"),
    ("Behaviour log AND predicted below target",
     "has(behaviour) predicted<target"),
    ("No UCAS application yet", "missing(ucas)"),
    ("3+ behaviour entries", "count(behaviour)>3"),
    ("Members of a saved cohort", "cohort:year12_at_risk"),
    ("Expand a saved search macro", "@at_risk"),
    ("UCAS applicants, Oxford only", "in:ucas oxford"),
)


def query_examples() -> list[tuple[str, str]]:
    return list(QUERY_EXAMPLES)


def telemetry_summary(limit: int = 200) -> TelemetrySummary:
    """Aggregate metrics from recent search_history rows."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM search_history "
            "ORDER BY history_id DESC LIMIT ?",
            (int(limit),)).fetchall()
    total = len(rows)
    zero = sum(1 for r in rows if (r["zero_result"] or 0))
    counts: dict[str, int] = {}
    zero_qs: list[str] = []
    scope_ms_sum: dict[str, float] = {}
    scope_ms_n: dict[str, int] = {}
    for r in rows:
        q = (r["query"] or "").strip()
        if q:
            counts[q] = counts.get(q, 0) + 1
        if r["zero_result"]:
            if q and q not in zero_qs:
                zero_qs.append(q)
        try:
            elapsed = (json.loads(r["elapsed_ms_json"])
                       if r["elapsed_ms_json"] else {})
        except (TypeError, ValueError):
            elapsed = {}
        for scope, ms in (elapsed or {}).items():
            scope_ms_sum[scope] = scope_ms_sum.get(scope, 0.0) + float(ms)
            scope_ms_n[scope] = scope_ms_n.get(scope, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    slowest = {
        s: round(scope_ms_sum[s] / max(1, scope_ms_n[s]), 2)
        for s in sorted(scope_ms_sum,
                        key=lambda s: -scope_ms_sum[s] / scope_ms_n[s])[:10]
    }
    return TelemetrySummary(
        total_searches=total, zero_result=zero,
        top_queries=top,
        slowest_scopes_ms=slowest,
        zero_result_queries=zero_qs[:10],
    )


# ══════════════════════════════════════════════════════════════════
# Suggestions (item 43)
# ══════════════════════════════════════════════════════════════════

def suggest(prefix: str, *, limit: int = 8,
            actor: str | None = None) -> list[str]:
    """Type-ahead suggestions mixed from saved-search names, recent
    history, and a sampling of entity labels."""
    from .history import list_history, list_saved_searches  # late: avoids import cycle
    init_db()
    p = (prefix or "").strip().lower()
    out: list[str] = []
    seen: set[str] = set()

    def push(s: str) -> None:
        s2 = s.strip()
        if not s2 or s2.lower() in seen:
            return
        if p and p not in s2.lower():
            return
        seen.add(s2.lower())
        out.append(s2)

    for s in list_saved_searches(actor=actor):
        push(s.name)
        if s.query:
            push(s.query)
        if len(out) >= limit:
            return out[:limit]
    for h in list_history(limit=40, actor=actor):
        if h.query:
            push(h.query)
        if len(out) >= limit:
            return out[:limit]
    if p and _fts_available():
        try:
            with _connect() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT entity_id, scope FROM "
                    "search_index_fts WHERE text MATCH ? LIMIT 20",
                    (f'"{p}"*',)).fetchall()
            for r in rows:
                push(f"{r['entity_id']}")
                if len(out) >= limit:
                    break
        except db.OperationalError:
            pass
    return out[:limit]

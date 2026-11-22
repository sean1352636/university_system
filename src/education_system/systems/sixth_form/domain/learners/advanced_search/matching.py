"""Doc matching, adapter helpers, ACL/filter context, redaction and scoring
for Advanced Search.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — avoids import cycles
    from .models import Hit, QueryOptions
    from .query import ParsedQuery

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .models import (  # noqa: F401
    ValidationError,
)
from ._db import (  # noqa: F401
    logger,
)
from .query import (  # noqa: F401
    SYNONYMS,
    _Aggregate,
    _And,
    _Cohort,
    _Compare,
    _Has,
    _Not,
    _Or,
    _Phrase,
    _REL_FIELDS,
    _Range,
    _Regex,
    _RelCompare,
    _Term,
    _doc_student_id,
    _fold,
    _grade_rank,
    _lev,
    _stem,
)


# ── Doc representation & matching ─────────────────────────────────

# A `doc` passed in to match() is a plain dict:
#   text fields → str values (e.g. {"name": "John Smith", "email": "..."}).
#   structured  → reserved keys "_date" (ISO str), "_grade" (letter),
#                  "_attendance" (float-like).
# An "_all" text field is added automatically if absent.


def _normalize_words(s: str, _opts: QueryOptions) -> list[str]:
    """Return raw lowercased word tokens. Stemming is applied
    on demand inside term matching so wildcard/fuzzy can use the
    raw form."""
    return re.findall(r"[A-Za-z0-9_]+", (s or "").lower())


def _maybe_fold(s: str, opts: QueryOptions) -> str:
    """Fold diacritics when the option is on (item 19)."""
    return _fold(s) if opts.fold_diacritics else s


def _doc_match(parsed: ParsedQuery,
               doc: dict[str, Any],
               opts: QueryOptions) -> bool:
    if parsed is None:
        return True
    return _eval_doc(parsed, doc, opts) is not False


def _eval_doc(parsed: ParsedQuery,
              doc: dict[str, Any],
              opts: QueryOptions) -> bool | None:
    """Evaluate *parsed* against *doc* in three-valued logic.

    Student-level predicates (has/missing/count/avg/cohort) are ``None``
    (unknown) unless the doc carries ``_pred_sets`` — the resolved student
    sets keyed by ``id(node)`` — and its student id in ``_sid``. An adapter
    keeps every row that is not definitely False; the engine re-evaluates
    student-keyed rows with the sets so OR and NOT combine correctly."""
    text_fields: dict[str, str] = {}
    for k, v in doc.items():
        if k.startswith("_") and k != "_all":
            continue
        text_fields[k] = "" if v is None else str(v)
    text_fields.setdefault(
        "_all", " ".join(v for v in text_fields.values() if v))
    raw_lower = {k: _maybe_fold(v.lower(), opts)
                 for k, v in text_fields.items()}
    word_idx: dict[str, list[str]] = {
        k: _normalize_words(v, opts) for k, v in raw_lower.items()
    }
    return _eval(parsed, raw_lower, word_idx, doc, opts)


def _eval(node: ParsedQuery,
          raw: dict[str, str],
          words: dict[str, list[str]],
          doc: dict[str, Any],
          opts: QueryOptions) -> bool | None:
    if isinstance(node, _And):
        vals = [_eval(c, raw, words, doc, opts) for c in node.children]
        if False in vals:
            return False
        return None if None in vals else True
    if isinstance(node, _Or):
        vals = [_eval(c, raw, words, doc, opts) for c in node.children]
        if True in vals:
            return True
        return None if None in vals else False
    if isinstance(node, _Not):
        v = _eval(node.child, raw, words, doc, opts)
        return None if v is None else not v
    if isinstance(node, _Phrase):
        return _eval_phrase(node, raw, words, opts)
    if isinstance(node, _Compare):
        return _eval_compare(node, doc)
    if isinstance(node, _Range):
        return _eval_range(node, doc)
    if isinstance(node, _Regex):
        return _eval_regex(node, doc, opts)
    if isinstance(node, _RelCompare):
        return _eval_relcompare(node, doc)
    if isinstance(node, (_Aggregate, _Has, _Cohort)):
        sets = doc.get("_pred_sets")
        if sets is None or id(node) not in sets:
            return None
        return str(doc.get("_sid") or "") in sets[id(node)]
    if isinstance(node, _Term):
        return _eval_term(node, raw, words, opts)
    raise ValidationError(f"Unknown query node: {type(node).__name__}")


def _eval_phrase(node: _Phrase,
                 raw: dict[str, str],
                 words: dict[str, list[str]],
                 opts: QueryOptions) -> bool:
    target = node.field or "_all"
    needle = _maybe_fold(node.text, opts)
    if not needle:
        return False
    if node.proximity <= 0:
        return needle in raw.get(target, "")
    # Proximity (item 15): every word of the phrase present and spanning a
    # window no wider than len(words)+proximity tokens.
    parts = re.findall(r"[A-Za-z0-9_]+", needle)
    if not parts:
        return False
    haystack = words.get(target, [])
    positions: list[list[int]] = []
    for p in parts:
        ps = [i for i, w in enumerate(haystack) if w == p]
        if not ps:
            return False
        positions.append(ps)
    span = len(parts) + node.proximity
    # Greedy check: does some ordering fit inside a window of `span`?
    flat = sorted({i for ps in positions for i in ps})
    needed = set(parts)
    for start in flat:
        window = [w for i, w in enumerate(haystack)
                  if start <= i < start + span]
        if needed.issubset(set(window)):
            return True
    return False


def _eval_range(node: _Range, doc: dict[str, Any]) -> bool:
    if node.field == "date":
        dv = doc.get("_date")
        if not dv:
            return False
        d = _iso(str(dv))
        return _iso(node.lo) <= d <= _iso(node.hi)
    if node.field == "grade":
        dv = _grade_rank(str(doc.get("_grade") or ""))
        lo, hi = _grade_rank(node.lo), _grade_rank(node.hi)
        if dv is None or lo is None or hi is None:
            return False
        if lo > hi:
            lo, hi = hi, lo
        return lo <= dv <= hi
    if node.field == "attendance":
        dv = doc.get("_attendance")
        if dv is None:
            return False
        try:
            v, lo, hi = float(dv), float(node.lo), float(node.hi)
        except (TypeError, ValueError):
            return False
        if lo > hi:
            lo, hi = hi, lo
        return lo <= v <= hi
    return False


def _eval_regex(node: _Regex, doc: dict[str, Any],
                opts: QueryOptions) -> bool:
    # Match against original-case text (raw dicts are lowercased), so
    # case-sensitive patterns like /S1\d{4}/ behave as written.
    if node.field:
        v = doc.get(node.field)
        hay = "" if v is None else str(v)
    else:
        hay = " ".join(
            str(v) for k, v in doc.items()
            if not (k.startswith("_") and k != "_all") and v)
    if opts.fold_diacritics:
        hay = _fold(hay)
    try:
        return re.search(
            node.pattern, hay,
            re.IGNORECASE if node.ignore_case else 0) is not None
    except re.error:
        return False


def _eval_relcompare(node: _RelCompare, doc: dict[str, Any]) -> bool:
    lkey, rkey = _REL_FIELDS[node.left], _REL_FIELDS[node.right]
    lv, rv = doc.get(lkey), doc.get(rkey)
    if lv in (None, "") or rv in (None, ""):
        return False
    # Prefer grade-rank comparison when both look like letter grades.
    lr, rr = _grade_rank(str(lv)), _grade_rank(str(rv))
    if lr is not None and rr is not None:
        return _cmp(lr, node.op, rr)
    try:
        return _cmp(float(lv), node.op, float(rv))
    except (TypeError, ValueError):
        return _cmp(str(lv).lower(), node.op, str(rv).lower())


def _eval_term(t: _Term,
               raw: dict[str, str],
               words: dict[str, list[str]],
               opts: QueryOptions) -> bool:
    target = t.field or "_all"
    target_raw = raw.get(target, "")
    target_words = words.get(target, [])
    text = _maybe_fold(t.text, opts)
    if not text:
        return False
    if t.wildcard:
        pattern = re.compile(
            "^" + re.escape(text)
            .replace(r"\*", ".*")
            .replace(r"\?", ".") + "$"
        )
        return any(pattern.match(w) for w in target_words)
    if t.fuzzy > 0:
        stemmed_term = _stem(text) if opts.use_stemming else text
        max_d = t.fuzzy
        for w in target_words:
            if _lev(stemmed_term, w, max_d) <= max_d:
                return True
        return False
    # Plain substring on words (with stemming + synonym expansion)
    candidates = [text]
    if opts.expand_synonyms:
        candidates.extend(_maybe_fold(s, opts)
                          for s in SYNONYMS.get(t.text, ()))
    stemmed_words = (
        [_stem(w) for w in target_words] if opts.use_stemming else None
    )
    for cand in candidates:
        if cand and any(cand in w for w in target_words):
            return True
        if opts.use_stemming:
            stem_cand = _stem(cand)
            if stem_cand and any(stem_cand in w for w in stemmed_words):
                return True
        if cand and cand in target_raw:
            return True
    return False


def _eval_compare(c: _Compare, doc: dict[str, Any]) -> bool:
    if c.field == "date":
        dv = doc.get("_date")
        if not dv:
            return False
        return _cmp(_iso(dv), c.op, _iso(c.value))
    if c.field == "grade":
        dv = _grade_rank(str(doc.get("_grade") or ""))
        rv = _grade_rank(c.value)
        if dv is None or rv is None:
            return False
        return _cmp(dv, c.op, rv)
    # Generic numeric
    if c.field in ("attendance",):
        dv = doc.get("_attendance")
        if dv is None:
            return False
        try:
            return _cmp(float(dv), c.op, float(c.value))
        except (TypeError, ValueError):
            return False
    return False


def _iso(s: str) -> str:
    """Normalize a date-ish string to YYYY-MM-DD for lexical compare."""
    s = (s or "").strip()
    if not s:
        return ""
    s2 = s.replace("/", "-")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s2)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return s


def _cmp(a, op: str, b) -> bool:
    if op == "=":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    return False


# ══════════════════════════════════════════════════════════════════
# Search adapters
# ══════════════════════════════════════════════════════════════════

def _trim(value: Any, n: int = 80) -> str:
    s = "" if value is None else str(value).strip()
    if not s:
        return ""
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _safe_search(label: str, fn: Callable[[], list[Hit]]) -> list[Hit]:
    try:
        return fn()
    except Exception:
        logger.exception("Search adapter %s failed", label)
        return []


def _first_attr(obj: Any, *names: str) -> str:
    for n in names:
        v = getattr(obj, n, None)
        if v:
            return str(v)
    return ""


def _filter_match(parsed: ParsedQuery,
                  opts: QueryOptions,
                  doc: dict[str, Any]) -> bool:
    return parsed is None or _doc_match(parsed, doc, opts)


def _emit(out: list[Hit], doc: dict[str, Any], hit: Hit) -> None:
    """Append a Hit and stash its backing doc for the engine."""
    if hit.extra is None:
        hit.extra = {}
    if "_sid" not in doc and hit.scope in _STUDENT_KEYED_SCOPES:
        doc["_sid"] = _doc_student_id(hit.scope, doc)
    hit.extra["_doc"] = doc
    out.append(hit)


# ══════════════════════════════════════════════════════════════════
# Filters / facets (items 23–30)
# ══════════════════════════════════════════════════════════════════

# Roles allowed to see safeguarding hits silently. Anything else is gated.
SAFEGUARDING_ROLES: frozenset[str] = frozenset({
    "admin", "headteacher", "dsl", "deputy_dsl", "safeguarding_lead",
    "safeguarding", "sendco",
})

# Per-scope role ACL (item 32). A scope listed here is dropped for roles not
# in its set — unless break-glass is used. Extend with more sensitive scopes.
SCOPE_ACL: dict[str, frozenset[str]] = {
    "safeguarding": SAFEGUARDING_ROLES,
}

# Scopes that need a capability on the signed-in account (see
# domain/governance/user_management/access.py). Each matches the menu the
# records live under, so search never shows what the menu would refuse.
# Students need students.view, which opening Advanced Search already does.
SCOPE_CAPABILITIES: dict[str, str] = {
    "safeguarding": "safeguarding",
    "accommodations": "send",
    "medical": "medical",
    "finance": "finance",
    "audit_logs": "governance",
    "staff": "staff.directory",
    "behaviour": "teaching",
    "absence_requests": "teaching",
    "attendance": "teaching",
    "attendance_concerns": "pastoral",
    "predicted_grades": "assessment",
    "progress_reviews": "assessment",
    "exam_results": "exams",
    "enrolments": "admissions",
    "ucas": "careers",
    "alumni": "careers",
    "messages": "comms",
    "surveys": "comms",
    "documents": "comms",
}

# Scopes whose records are restricted per student as well as per scope:
# a tutor-only pastoral account sees its own tutees' concerns only.
SCOPE_STUDENT_CAPABILITY: dict[str, str] = {
    "attendance_concerns": "pastoral",
}

# Scopes whose searches are written to the sensitive-access log (the one
# the DSL reviews), not just the search audit.
SENSITIVE_LOG_AREAS: dict[str, str] = {
    "safeguarding": "safeguarding",
    "accommodations": "send",
    "medical": "medical",
}

# Fields masked when redaction is on (item 31). Label/id are kept; the
# free-text detail (which carries the sensitive content) is masked.
SENSITIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "safeguarding":   ("summary", "description", "notes"),
    "accommodations": ("description", "notes"),
    "medical":        ("description", "notes"),
    "behaviour":      ("description",),
}
REDACTION_MASK = "[redacted]"

# Statuses that count as "archived" / inactive per scope.
_ARCHIVED_STATUSES: frozenset[str] = frozenset({
    "archived", "withdrawn", "left", "inactive", "deleted",
    "lost-contact", "closed",
})


@dataclass
class FilterContext:
    """Resolved set of constraints to apply across adapters."""
    role: str | None = None
    actor: str | None = None
    allowed_student_ids: set[str] | None = None
    allowed_alumni_ids: set[int] | None = None
    include_archived: bool = False
    postcode_prefix: str | None = None
    drop_scopes: set[str] = field(default_factory=set)
    today: _dt.date | None = None
    redact: bool = False                       # item 31
    break_glass_reason: str | None = None      # item 35
    consent_excluded: set[str] | None = None   # item 34
    #: Per-scope student allow-lists from the signed-in account's own
    #: access (e.g. a tutor's tutees); a scope absent here is unrestricted.
    scope_student_ids: dict[str, set[str]] = field(default_factory=dict)
    #: Whether actor/role came from the signed-in account.
    signed_in: bool = False


def _build_filter_context(filters: dict[str, Any],
                          opts: QueryOptions) -> FilterContext:
    """Translate raw filter dict into an effective FilterContext.

    Actor and role come from the signed-in account. The ``role`` and
    ``actor`` filters are only honoured when nobody is signed in (scripts,
    scheduled jobs), so a user cannot type their way into a gated scope."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    principal = access.current()
    signed_in = bool(principal.username)
    ctx = FilterContext(
        role=(principal.role if signed_in else filters.get("role")) or None,
        actor=(principal.username if signed_in else
               (filters.get("actor") or filters.get("owned_by_staff"))) or None,
        signed_in=signed_in,
        include_archived=bool(filters.get("include_archived", False)),
        postcode_prefix=(filters.get("postcode_prefix") or "").strip()
                         or None,
        today=opts.today,
        redact=bool(filters.get("redact", False)),
        break_glass_reason=(filters.get("break_glass") or "").strip() or None,
    )

    # 32. Per-scope role ACL, for headless callers that pass a role.
    # Break-glass (item 35) bypasses the drop but is audited in run_search.
    if not signed_in:
        for scope, allowed in SCOPE_ACL.items():
            if ctx.role and ctx.role not in allowed \
                    and not ctx.break_glass_reason:
                ctx.drop_scopes.add(scope)

    # Scopes holding restricted records are dropped for anyone whose
    # signed-in account lacks the capability; break-glass does not
    # override this.
    for scope, capability in SCOPE_CAPABILITIES.items():
        if not principal.can(capability):
            ctx.drop_scopes.add(scope)
    for scope, capability in SCOPE_STUDENT_CAPABILITY.items():
        if scope in ctx.drop_scopes:
            continue
        ids = access.visible_student_ids(principal, capability=capability)
        if ids is not None:
            ctx.scope_student_ids[scope] = ids

    # 34. GDPR consent filter — exclude students who withdrew consent for a
    # named processing purpose.
    purpose = filters.get("require_consent")
    if purpose:
        ctx.consent_excluded = _students_without_consent(str(purpose))

    student_ids: set[str] | None = None

    # 23. Year-group filter via tutor-group membership
    yr = filters.get("year_group")
    if yr is not None:
        student_ids = _student_ids_for_year(yr)

    # 24. Tutor / form group filter
    tg = filters.get("tutor_group")
    if tg:
        ids = _student_ids_for_tutor_group(tg)
        student_ids = ids if student_ids is None else student_ids & ids

    # 27. "My students" — restrict to staff member's tutees
    owned = filters.get("owned_by_staff")
    if owned:
        ids = _student_ids_for_staff(owned)
        student_ids = ids if student_ids is None else student_ids & ids

    # 29. SEN / accommodation status filter
    if filters.get("sen_only") or filters.get("with_accommodations"):
        ids = _student_ids_with_active_accommodations()
        student_ids = ids if student_ids is None else student_ids & ids

    ctx.allowed_student_ids = student_ids

    # 26. Tag filter — currently only Alumni has a tag system
    tags = filters.get("tags")
    if tags:
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        ctx.allowed_alumni_ids = _alumni_ids_for_tags(tags)
        if not ctx.allowed_alumni_ids:
            # No alumni match these tags — alumni scope returns nothing.
            ctx.allowed_alumni_ids = set()

    return ctx


def _student_ids_for_year(year: Any) -> set[str]:
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as tg,
        )
        wanted = int(year) if str(year).strip().isdigit() else None
        if wanted is None:
            s = str(year).strip().upper()
            wanted = int(s[1:]) if s.startswith("Y") and s[1:].isdigit() \
                     else None
        if wanted is None:
            return set()
        out: set[str] = set()
        for g in tg.list_groups():
            if g.year_group == wanted:
                out.update(tg.list_members(g.tutor_group_id))
        return out
    except Exception:
        logger.exception("year filter failed")
        return set()


def _student_ids_for_tutor_group(name: str) -> set[str]:
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as tg,
        )
        g = tg.get_group_by_name(str(name).strip())
        if not g:
            return set()
        return set(tg.list_members(g.tutor_group_id))
    except Exception:
        logger.exception("tutor-group filter failed")
        return set()


def _student_ids_for_staff(staff_id: str) -> set[str]:
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as tg,
        )
        out: set[str] = set()
        for g in tg.list_groups():
            if (g.tutor or "").strip() == str(staff_id).strip():
                out.update(tg.list_members(g.tutor_group_id))
        return out
    except Exception:
        logger.exception("owned_by_staff filter failed")
        return set()


def _student_ids_with_active_accommodations() -> set[str]:
    try:
        from education_system.systems.sixth_form.domain.pastoral.accessibility import (
            accessibility as ac,
        )
        out: set[str] = set()
        for a in ac.list_accommodations():
            if (a.status or "").strip().lower() in ("active", "approved",
                                                     "in place"):
                if a.student_id:
                    out.add(a.student_id)
        return out
    except Exception:
        logger.exception("sen_only filter failed")
        return set()


def _alumni_ids_for_tags(tags: list[str]) -> set[int]:
    try:
        from education_system.systems.sixth_form.domain.learners.alumni import (
            records as alumni_records,
        )
        wanted: set[int] = set()
        first = True
        for t in tags:
            try:
                ids = {a.alumni_id for a in alumni_records.list_alumni(tag=t)}
            except TypeError:
                ids = set()
            if first:
                wanted = ids
                first = False
            else:
                wanted &= ids
        return wanted
    except Exception:
        logger.exception("alumni-tag filter failed")
        return set()


def _ctx_allows(scope: str, doc: dict[str, Any],
                ctx: FilterContext) -> bool:
    """Apply filter context to one doc. Returns False to drop the row."""
    if scope in ctx.drop_scopes:
        return False
    # Archived gating — only when scope rows expose a "status".
    if not ctx.include_archived:
        st = str(doc.get("status") or "").strip().lower()
        # A student who is Inactive or Suspended is still on roll; only
        # one who has left is archived.
        archived = (st == "left" if scope == "students"
                    else st in _ARCHIVED_STATUSES)
        if archived:
            return False
    if scope in _STUDENT_KEYED_SCOPES:
        sid = _doc_student_id(scope, doc)
        if ctx.allowed_student_ids is not None \
                and sid not in ctx.allowed_student_ids:
            return False
        own = ctx.scope_student_ids.get(scope)
        if own is not None and sid not in own:
            return False
    # Alumni tag set
    if scope == "alumni" and ctx.allowed_alumni_ids is not None:
        try:
            aid = int(str(doc.get("id") or "0"))
        except ValueError:
            aid = 0
        if aid not in ctx.allowed_alumni_ids:
            return False
    # Postcode prefix — student home postcode; alumni only hold a location.
    if ctx.postcode_prefix and scope in ("students", "alumni"):
        want = re.sub(r"\s", "", ctx.postcode_prefix.upper())
        if scope == "students":
            have = re.sub(r"\s", "", str(doc.get("postcode") or "").upper())
            if not have.startswith(want):
                return False
        elif want not in re.sub(r"\s", "",
                                str(doc.get("location") or "").upper()):
            return False
    # Consent exclusion (item 34) — drop students who withdrew consent.
    if ctx.consent_excluded and scope in _STUDENT_KEYED_SCOPES:
        if _doc_student_id(scope, doc) in ctx.consent_excluded:
            return False
    return True


def _students_without_consent(purpose: str) -> set[str]:
    """Student ids with a GDPR consent record for ``purpose`` that is no
    longer active (withdrawn/expired/not granted) — item 34."""
    out: set[str] = set()
    try:
        from education_system.systems.sixth_form.domain.governance.gdpr import (
            gdpr as g,
        )
        for c in g.list_consents(purpose=purpose):
            sid = getattr(c, "subject_ref", None)
            if not sid:
                continue
            active = getattr(c, "is_active", None)
            if active is False:
                out.add(str(sid).strip())
    except Exception:
        logger.debug("consent filter unavailable")
    return out


def _redact_hit(h: Hit, scope: str) -> None:
    """Mask the sensitive free-text of a hit in place (item 31)."""
    fields = SENSITIVE_FIELDS.get(scope)
    if not fields:
        return
    doc = h.extra.get("_doc") if isinstance(h.extra, dict) else None
    if isinstance(doc, dict):
        masked = dict(doc)
        for f in fields:
            if masked.get(f):
                masked[f] = REDACTION_MASK
        h.extra = dict(h.extra)
        h.extra["_doc"] = masked
    if h.sublabel:
        h.sublabel = REDACTION_MASK
    h.highlights = {}
    h.matched_field = ""


# Scopes whose docs refer to one student (``_sid``; see _doc_student_id).
# Filters that constrain by student id apply to these.
_STUDENT_KEYED_SCOPES: frozenset[str] = frozenset({
    "students", "behaviour", "absence_requests", "attendance_concerns",
    "accommodations", "safeguarding", "predicted_grades",
    "progress_reviews", "ucas", "finance", "attendance", "exam_results",
    "enrolments", "medical",
})


# ══════════════════════════════════════════════════════════════════
# Scoring, highlights, clustering, pinning (items 31–37)
# ══════════════════════════════════════════════════════════════════

# Field weights for relevance scoring — title/name/id beat description.
_FIELD_WEIGHTS: dict[str, float] = {
    "id": 1.4, "name": 1.4, "title": 1.4, "code": 1.3,
    "email": 1.2, "subject": 1.1, "author": 1.1, "category": 1.0,
    "status": 0.9, "level": 0.9, "type": 0.9, "role": 0.9,
    "department": 0.9, "location": 0.9, "tutor": 1.0,
    "reason": 1.0, "description": 0.7, "summary": 0.8,
    "notes": 0.6, "body": 0.7,
}


def _collect_terms(node: ParsedQuery) -> list[_Term | _Phrase]:
    """Flatten an AST into the leaf term/phrase nodes (positive matches)."""
    out: list[_Term | _Phrase] = []

    def walk(n, polarity):
        if isinstance(n, _Not):
            walk(n.child, not polarity)
            return
        if isinstance(n, (_And, _Or)):
            for c in n.children:
                walk(c, polarity)
            return
        if isinstance(n, (_Term, _Phrase)) and polarity:
            out.append(n)
    if node is not None:
        walk(node, True)
    return out


def _term_text(node: _Term | _Phrase) -> str:
    return node.text


def _hit_matched_fields(parsed: ParsedQuery,
                        doc: dict[str, Any],
                        opts: QueryOptions) -> list[str]:
    """Return field names where positive query terms hit the doc."""
    if parsed is None:
        return []
    seen: list[str] = []
    text_fields: dict[str, str] = {
        k: "" if v is None else str(v)
        for k, v in doc.items()
        if not (k.startswith("_") and k != "_all")
    }
    text_fields.setdefault(
        "_all", " ".join(v for v in text_fields.values() if v))
    raw_lower = {k: _maybe_fold(v.lower(), opts)
                 for k, v in text_fields.items()}
    word_idx = {k: _normalize_words(v, opts) for k, v in raw_lower.items()}
    for leaf in _collect_terms(parsed):
        # Where to look
        if isinstance(leaf, _Phrase):
            tgt = leaf.field or "_all"
            needle = _maybe_fold(leaf.text, opts)
            if needle and needle in raw_lower.get(tgt, ""):
                _mark(seen, tgt, leaf.field)
            continue
        # Term — check the declared field if any, else any field
        if leaf.field:
            if _eval_term(leaf, raw_lower, word_idx, opts):
                _mark(seen, leaf.field, leaf.field)
            continue
        # Wildcard / fuzzy on _all → find a contributing field
        for fname in text_fields:
            if fname.startswith("_"):
                continue
            sub = _Term(text=leaf.text, field=fname, fuzzy=leaf.fuzzy,
                        wildcard=leaf.wildcard)
            if _eval_term(sub, raw_lower, word_idx, opts):
                _mark(seen, fname, None)
                break
    return seen


def _mark(acc: list[str], field_name: str, _explicit: str | None) -> None:
    if field_name and field_name not in acc and field_name != "_all":
        acc.append(field_name)


def _make_highlights(parsed: ParsedQuery,
                     doc: dict[str, Any],
                     fields: list[str],
                     opts: QueryOptions,
                     window: int = 80) -> dict[str, str]:
    """Build short ``**term**``-wrapped snippets per matched field."""
    if parsed is None or not fields:
        return {}
    raw_terms = {
        _term_text(t) for t in _collect_terms(parsed)
        if isinstance(t, (_Term, _Phrase)) and t.text
        and not getattr(t, "wildcard", False)
    }
    expanded: set[str] = set(raw_terms)
    if opts.expand_synonyms:
        for rt in raw_terms:
            expanded.update(SYNONYMS.get(rt, ()))
    terms = sorted(expanded, key=len, reverse=True)
    if not terms:
        return {}
    out: dict[str, str] = {}
    for fname in fields:
        raw = str(doc.get(fname) or "")
        if not raw:
            continue
        lo = raw.lower()
        # Locate the first matching term to centre the window
        idx = -1
        hit_term = ""
        for t in terms:
            i = lo.find(t)
            if 0 <= i and (idx < 0 or i < idx):
                idx = i
                hit_term = t
        if idx < 0:
            continue
        start = max(0, idx - window // 3)
        end = min(len(raw), start + window)
        snippet = ("…" if start > 0 else "") + raw[start:end] \
                  + ("…" if end < len(raw) else "")
        # Bold every term occurrence — single alternation regex, with
        # the longest alternative listed first so re picks it greedily
        # and avoids nesting (e.g. ``maths``/``math``/``mathematics``).
        pattern = "(" + "|".join(
            re.escape(t) for t in terms if t) + ")"
        snippet = re.sub(pattern, r"**\1**", snippet, flags=re.IGNORECASE)
        out[fname] = snippet
        _ = hit_term
    return out


def _score_hit(parsed: ParsedQuery,
               doc: dict[str, Any],
               matched_fields: list[str],
               ctx: FilterContext,
               opts: QueryOptions,
               recency_boost: bool) -> float:
    if parsed is None:
        return 0.0
    total = max(1, len(_collect_terms(parsed)))
    base = len(matched_fields) / total
    field_w = sum(_FIELD_WEIGHTS.get(f, 0.8) for f in matched_fields)
    score = base * (1.0 + 0.15 * field_w)
    # 35. Recent-activity boost
    if recency_boost:
        d = doc.get("_date")
        if d:
            iso = _iso(str(d))
            try:
                when = _dt.date.fromisoformat(iso[:10])
                today = ctx.today or _dt.date.today()
                age = (today - when).days
                if 0 <= age <= 365:
                    score += 0.25 * (1.0 - age / 365.0)
            except ValueError:
                pass
    return round(score, 4)

"""Query language for Advanced Search: folding, AST nodes, stemming,
tokenizer/parser, macros, scope directives, aggregates, cross-scope joins,
did-you-mean.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .models import (  # noqa: F401
    ALL_SCOPES,
    QueryOptions,
    SCOPE_LABELS,
    ValidationError,
)
from ._db import (  # noqa: F401
    logger,
)


# ══════════════════════════════════════════════════════════════════
# Query language
# ══════════════════════════════════════════════════════════════════

STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
    "is", "are", "was", "were", "be", "at", "by", "with", "from",
    "as", "it", "this", "that",
})

SYNONYMS: dict[str, tuple[str, ...]] = {
    "maths":       ("mathematics", "math"),
    "mathematics": ("maths", "math"),
    "math":        ("maths", "mathematics"),
    "sen":         ("send", "accommodations", "accessibility"),
    "send":        ("sen", "accommodations", "accessibility"),
    "phys":        ("physics",),
    "physics":     ("phys",),
    "chem":        ("chemistry",),
    "chemistry":   ("chem",),
    "bio":         ("biology",),
    "biology":     ("bio",),
    "lit":         ("literature",),
    "literature":  ("lit",),
    "eng":         ("english",),
    "english":     ("eng",),
    "geog":        ("geography",),
    "geography":   ("geog",),
    "psych":       ("psychology",),
    "psychology":  ("psych",),
}

# Canonical doc field names that field-scoped terms can target.
# A `field:value` token will look for `value` only inside that field
# (or "_all" if the field is unknown for this scope).
_KNOWN_FIELDS: frozenset[str] = frozenset({
    "id", "name", "email", "phone", "subject", "code", "title",
    "role", "dept", "department", "category", "status", "type",
    "level", "reason", "description", "notes", "body", "summary",
    "action", "location", "direction", "tutor", "author",
    # Student record fields (see sources._student_doc).
    "preferred", "personal_email", "dob", "gender", "pronouns", "address",
    "postcode", "previous_school", "ethnicity", "nationality", "language",
    "start", "left", "leaving_reason", "upn", "uln", "uci", "candidate",
    "year", "tutor_group", "contact",
})

_FIELD_ALIASES: dict[str, str] = {
    "desc": "description",
    "descr": "description",
    "note": "notes",
    "subj": "subject",
    "cat": "category",
    "dept": "department",
    "tg": "tutor_group",
    "form": "tutor_group",
    "birth": "dob",
    "school": "previous_school",
}

# Letter grade ranks (×3 so +/- modifiers fit between).
_GRADE_BASE: dict[str, int] = {
    "U": 0, "E": 1, "D": 2, "C": 3, "B": 4, "A": 5,
}


def _grade_rank(g: str) -> int | None:
    g = (g or "").strip().upper()
    if not g:
        return None
    if g == "A*":
        return _GRADE_BASE["A"] * 3 + 2
    if g in _GRADE_BASE:
        return _GRADE_BASE[g] * 3
    if len(g) == 2 and g[0] in _GRADE_BASE and g[1] in "+-":
        return _GRADE_BASE[g[0]] * 3 + (1 if g[1] == "+" else -1)
    return None


# ── Diacritic folding (item 19) ───────────────────────────────────

def _fold(s: str) -> str:
    """Strip accents/diacritics so ``Zoë`` ≡ ``Zoe``. NFKD-decompose and
    drop combining marks; returns the string unchanged on any failure."""
    if not s:
        return s
    try:
        return "".join(
            c for c in unicodedata.normalize("NFKD", s)
            if not unicodedata.combining(c)
        )
    except (TypeError, ValueError):
        return s


# Relative-comparison field aliases (item 14) → reserved doc keys. Both
# sides of a bare ``a<b`` comparison must resolve here for it to parse as
# a relative comparison rather than a plain term.
_REL_FIELDS: dict[str, str] = {
    "predicted":    "_grade",
    "grade":        "_grade",
    "target":       "_target",
    "mte":          "_target",
    "aspirational": "_aspirational",
    "current":      "_current",
    "attendance":   "_attendance",
}

# Functions allowed in aggregate terms (item 13).
_AGG_FUNCS: frozenset[str] = frozenset({"count", "avg", "min", "max", "sum"})

# Max depth when expanding @macros (item 18) to stop self-reference loops.
_MACRO_MAX_DEPTH: int = 8


# ── AST node types ────────────────────────────────────────────────

@dataclass
class _Term:
    text: str                # raw lowercased
    field: str | None        # None ⇒ _all
    fuzzy: int = 0           # 0 ⇒ no fuzzy
    wildcard: bool = False


@dataclass
class _Phrase:
    text: str
    field: str | None
    proximity: int = 0       # 0 ⇒ exact substring; N ⇒ words within N (item 15)


@dataclass
class _Compare:
    field: str               # "date" | "grade" | "attendance" | other num
    op: str                  # one of <, <=, >, >=, =, !=
    value: str


@dataclass
class _Range:                # item 12 — inclusive low..high
    field: str               # "date" | "grade" | "attendance"
    lo: str
    hi: str


@dataclass
class _Regex:                # item 16 — raw regular-expression term
    pattern: str
    field: str | None
    ignore_case: bool = False


@dataclass
class _RelCompare:           # item 14 — compare two same-record fields
    left: str                # logical name from _REL_FIELDS
    op: str
    right: str               # logical name from _REL_FIELDS


@dataclass
class _Aggregate:            # item 13 — per-student aggregate constraint
    func: str                # count | avg | min | max | sum
    scope: str               # a searchable scope key
    field: str | None        # numeric field for avg/min/max/sum (None ⇒ count)
    op: str
    value: float


@dataclass
class _Has:                  # item 11 — cross-scope existence join
    scope: str               # a student-keyed scope key
    term: str | None         # optional inner term matched against scope rows
    negate: bool = False     # missing(...) ⇒ True


@dataclass
class _Cohort:               # item 12 — membership of a saved cohort
    name: str


@dataclass
class _Not:
    child: Any


@dataclass
class _And:
    children: list[Any]


@dataclass
class _Or:
    children: list[Any]


ParsedQuery = Any  # _Term | _Phrase | _Compare | _Not | _And | _Or | None


# ── Stemming & Levenshtein ────────────────────────────────────────

def _stem(w: str) -> str:
    """Tiny Porter-lite suffix stripper."""
    out = w
    if len(out) > 4 and out.endswith("ies"):
        out = out[:-3] + "y"
    elif len(out) > 4 and out.endswith("ing"):
        out = out[:-3]
    elif len(out) > 3 and out.endswith("ed"):
        out = out[:-2]
    elif len(out) > 4 and out.endswith("es") and not out.endswith("ses"):
        out = out[:-2]
    elif len(out) > 3 and out.endswith("s") and not out.endswith("ss"):
        out = out[:-1]
    elif len(out) > 4 and out.endswith("ly"):
        out = out[:-2]
    # Collapse a doubled trailing consonant after stripping (run-ning → runn → run).
    if (len(out) > 2 and out[-1] == out[-2]
            and out[-1] not in "lsz" and out[-1].isalpha()):
        out = out[:-1]
    return out


def _lev(a: str, b: str, max_d: int = 2) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_d:
        return max_d + 1
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    cur = [0] * (len(a) + 1)
    for j, cb in enumerate(b, 1):
        cur[0] = j
        best = cur[0]
        for i, ca in enumerate(a, 1):
            cur[i] = min(
                prev[i] + 1,
                cur[i - 1] + 1,
                prev[i - 1] + (0 if ca == cb else 1),
            )
            if cur[i] < best:
                best = cur[i]
        if best > max_d:
            return max_d + 1
        prev, cur = cur, prev
    return prev[len(a)]


# ── Tokenizer ─────────────────────────────────────────────────────

_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<rel>(?:has|missing)\([A-Za-z_][A-Za-z0-9_:.\-]*\))       |
        (?P<agg>[A-Za-z]+\([A-Za-z_.:]*\)(?:<=|>=|!=|=|<|>)[^\s()"]+) |
        (?P<lparen>\()                                              |
        (?P<rparen>\))                                              |
        (?P<regex>(?:[A-Za-z_][\w.]*:)?/(?:\\.|[^/\\])+/[A-Za-z]*)  |
        (?P<phrase>(?:[A-Za-z_][\w.]*:)?"[^"]*"(?:~\d+)?)           |
        (?P<minus>-(?=\S))                                          |
        (?P<word>[^\s()"]+)
    )
    """,
    re.VERBOSE,
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        m = _TOKEN_RE.match(text, i)
        if not m:
            break
        i = m.end()
        if m.group("rel"):
            # has(scope) / missing(scope) join — handled as a WORD so
            # _term_from_word can decode it into a _Has node.
            out.append(("WORD", m.group("rel")))
        elif m.group("agg"):
            # Aggregate term, e.g. count(behaviour)>3 — handled as a WORD
            # so _term_from_word can decode it into an _Aggregate node.
            out.append(("WORD", m.group("agg")))
        elif m.group("lparen"):
            out.append(("LP", "("))
        elif m.group("rparen"):
            out.append(("RP", ")"))
        elif m.group("regex"):
            # Keep the raw token (optional ``field:`` prefix + ``/…/flags``);
            # the parser decodes it into a _Regex node.
            out.append(("REGEX", m.group("regex")))
        elif m.group("phrase"):
            # Keep the raw token (optional ``field:`` prefix, quotes and
            # ``~N`` proximity); the parser decodes it into a _Phrase node.
            out.append(("PHRASE", m.group("phrase")))
        elif m.group("minus"):
            out.append(("NOT", "-"))
        else:
            w = m.group("word")
            up = w.upper()
            if up in ("AND", "OR", "NOT"):
                out.append((up, up))
            else:
                out.append(("WORD", w))
    return out


# ── Parser (recursive descent) ────────────────────────────────────

class _Parser:
    def __init__(self, tokens: list[tuple[str, str]], opts: QueryOptions):
        self.tokens = tokens
        self.pos = 0
        self.opts = opts

    def _peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _eat(self) -> tuple[str, str]:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def parse(self) -> ParsedQuery:
        node = self._parse_or()
        if self._peek() is not None:
            raise ValidationError(
                f"Unexpected token near {self._peek()[1]!r}")
        return node

    def _parse_or(self) -> ParsedQuery:
        left = self._parse_and()
        children = [left]
        while True:
            t = self._peek()
            if t is None or t[0] != "OR":
                break
            self._eat()
            children.append(self._parse_and())
        return children[0] if len(children) == 1 else _Or(children)

    def _parse_and(self) -> ParsedQuery:
        children = [self._parse_unary()]
        while True:
            t = self._peek()
            if t is None or t[0] in ("OR", "RP"):
                break
            if t[0] == "AND":
                self._eat()
            children.append(self._parse_unary())
        return children[0] if len(children) == 1 else _And(children)

    def _parse_unary(self) -> ParsedQuery:
        t = self._peek()
        if t is None:
            raise ValidationError("Unexpected end of query")
        if t[0] in ("NOT",):
            self._eat()
            return _Not(self._parse_unary())
        if t[0] == "LP":
            self._eat()
            inner = self._parse_or()
            t2 = self._peek()
            if t2 is None or t2[0] != "RP":
                raise ValidationError("Missing closing parenthesis")
            self._eat()
            return inner
        return self._parse_term()

    def _parse_term(self) -> ParsedQuery:
        t = self._eat()
        if t[0] == "PHRASE":
            return _phrase_from_raw(t[1])
        if t[0] == "REGEX":
            return _regex_from_raw(t[1])
        if t[0] != "WORD":
            raise ValidationError(f"Unexpected token {t[1]!r}")
        return _term_from_word(t[1], self.opts)


_CMP_RE = re.compile(r"^(<=|>=|!=|=|<|>)(.+)$")

# field:"phrase with spaces"~N   (item 11 + item 15)
_PHRASE_RAW_RE = re.compile(
    r'^(?:([A-Za-z_][\w.]*):)?"([^"]*)"(?:~(\d+))?$')
# field:/pattern/flags           (item 16)
_REGEX_RAW_RE = re.compile(
    r"^(?:([A-Za-z_][\w.]*):)?/(.+)/([A-Za-z]*)$")
# func(scope) or func(scope.field) op value   (item 13)
_AGG_RE = re.compile(
    r"^([A-Za-z]+)\(([A-Za-z_]+)(?:[.:]([A-Za-z_]+))?\)"
    r"(<=|>=|!=|=|<|>)(.+)$")
# bare  left op right            (item 14)
_REL_RE = re.compile(r"^([A-Za-z_]+)(<=|>=|!=|=|<|>)([A-Za-z_]+)$")
# has(scope) / missing(scope[:term])   (item 11)
_HAS_RE = re.compile(r"^(has|missing)\(([A-Za-z_]+)(?::(.+))?\)$",
                     re.IGNORECASE)


def _resolve_field(name: str | None) -> str | None:
    """Normalize a field token to a known field, else None (⇒ _all)."""
    if not name:
        return None
    n = _FIELD_ALIASES.get(name.lower(), name.lower())
    return n if n in _KNOWN_FIELDS else None


def _phrase_from_raw(raw: str) -> _Phrase:
    m = _PHRASE_RAW_RE.match(raw)
    if not m:                       # defensive — tokenizer shouldn't allow
        return _Phrase(text=raw.strip('"').lower(), field=None)
    fld, text, prox = m.group(1), m.group(2), m.group(3)
    return _Phrase(
        text=text.lower(),
        field=_resolve_field(fld),
        proximity=int(prox) if prox else 0,
    )


def _regex_from_raw(raw: str) -> _Regex:
    m = _REGEX_RAW_RE.match(raw)
    if not m:
        raise ValidationError(f"Malformed regex term {raw!r}")
    fld, pattern, flags = m.group(1), m.group(2), (m.group(3) or "")
    ic = "i" in flags.lower()
    try:
        re.compile(pattern, re.IGNORECASE if ic else 0)
    except re.error as e:
        raise ValidationError(f"Invalid regex {pattern!r}: {e}") from None
    return _Regex(pattern=pattern, field=_resolve_field(fld), ignore_case=ic)


def _term_from_word(raw: str, opts: QueryOptions) -> ParsedQuery:
    """Convert a WORD token into a term/phrase/compare/range/aggregate node."""
    from .matching import _STUDENT_KEYED_SCOPES  # late: avoids import cycle
    # has()/missing() cross-scope join  (item 11)
    hm = _HAS_RE.match(raw)
    if hm:
        scope = hm.group(2).lower()
        if scope not in _STUDENT_KEYED_SCOPES:
            raise ValidationError(
                f"has()/missing() needs a student-keyed scope, not {scope!r}. "
                f"Valid: {', '.join(sorted(_STUDENT_KEYED_SCOPES))}")
        return _Has(scope=scope,
                    term=(hm.group(3) or None),
                    negate=hm.group(1).lower() == "missing")
    # Aggregate — count(behaviour)>3, avg(attendance)<85  (item 13)
    am = _AGG_RE.match(raw)
    if am and am.group(1).lower() in _AGG_FUNCS:
        return _aggregate_from_match(am)
    # Relative comparison — predicted<target, current>=mte  (item 14)
    rm = _REL_RE.match(raw)
    if rm and rm.group(1).lower() in _REL_FIELDS \
            and rm.group(3).lower() in _REL_FIELDS:
        return _RelCompare(left=rm.group(1).lower(), op=rm.group(2),
                           right=rm.group(3).lower())
    fld: str | None = None
    val = raw
    if ":" in raw:
        head, _, tail = raw.partition(":")
        head_n = _FIELD_ALIASES.get(head.lower(), head.lower())
        # Cohort membership — cohort:year12_at_risk  (item 12)
        if head_n == "cohort" and tail:
            return _Cohort(name=tail)
        # Range — attendance:80..90, grade:C..A, date:lo..hi  (item 12)
        if ".." in tail and head_n in ("date", "grade", "attendance"):
            return _parse_range(head_n, tail)
        # Comparator on dedicated structured fields
        if head_n in ("date", "grade", "attendance") or head_n == "last":
            return _parse_compare(head_n, tail, opts)
        # Field-scoped term
        if head_n in _KNOWN_FIELDS:
            fld = head_n
            val = tail
        # else: treat as bare term (e.g. "url:http" — keep as text)
    # Quoted value after field:?
    if val.startswith('"') and val.endswith('"') and len(val) >= 2:
        return _Phrase(text=val[1:-1].lower(), field=fld)
    # Fuzzy suffix
    fuzzy = 0
    m = re.search(r"~(\d+)?$", val)
    if m:
        fuzzy = int(m.group(1)) if m.group(1) else 1
        val = val[: m.start()]
    # Wildcard detection
    wildcard = "*" in val or "?" in val
    return _Term(
        text=val.lower(),
        field=fld,
        fuzzy=fuzzy if not wildcard else 0,
        wildcard=wildcard,
    )


def _parse_compare(field_name: str,
                   tail: str,
                   opts: QueryOptions) -> _Compare:
    if field_name == "last":
        # last:30d  → date >= today - 30d
        m = re.match(r"^(\d+)([dwmy])$", tail.strip().lower())
        if not m:
            raise ValidationError(
                f"Invalid 'last' value {tail!r}; expected e.g. 30d, 6m, 1y")
        n, unit = int(m.group(1)), m.group(2)
        today = opts.today or _dt.date.today()
        days = n * {"d": 1, "w": 7, "m": 30, "y": 365}[unit]
        cutoff = (today - _dt.timedelta(days=days)).isoformat()
        return _Compare(field="date", op=">=", value=cutoff)
    m = _CMP_RE.match(tail)
    if m:
        op, val = m.group(1), m.group(2).strip()
    else:
        op, val = "=", tail.strip()
    return _Compare(field=field_name, op=op, value=val)


def _parse_range(field_name: str, tail: str) -> _Range:
    lo, _, hi = tail.partition("..")
    lo, hi = lo.strip(), hi.strip()
    if not lo or not hi:
        raise ValidationError(
            f"Range {tail!r} needs both ends, e.g. 80..90")
    if field_name == "grade":
        if _grade_rank(lo) is None or _grade_rank(hi) is None:
            raise ValidationError(f"Invalid grade range {tail!r}")
    elif field_name == "attendance":
        try:
            float(lo); float(hi)
        except ValueError:
            raise ValidationError(
                f"Invalid numeric range {tail!r}") from None
    return _Range(field=field_name, lo=lo, hi=hi)


# Bare metric → representative student-keyed scope carrying it, so the
# ergonomic ``avg(attendance)<85`` form (no explicit scope) resolves.
_METRIC_DEFAULT_SCOPE: dict[str, str] = {
    "attendance": "progress_reviews",
}


def _aggregate_from_match(m: re.Match) -> _Aggregate:
    func = m.group(1).lower()
    inner = m.group(2).lower()
    fld = (m.group(3) or "").lower() or None
    op, raw_val = m.group(4), m.group(5).strip()
    scope = inner
    if scope not in ALL_SCOPES:
        # Bare-metric shorthand: avg(attendance) ⇒ avg(progress_reviews.attendance)
        if fld is None and inner in _METRIC_DEFAULT_SCOPE:
            scope = _METRIC_DEFAULT_SCOPE[inner]
            fld = inner
        else:
            raise ValidationError(
                f"Unknown aggregate scope {inner!r}. "
                f"Valid: {', '.join(ALL_SCOPES)}")
    if func != "count" and fld is None:
        raise ValidationError(
            f"{func}(...) needs a field, e.g. {func}({scope}.attendance)")
    try:
        value = float(raw_val)
    except ValueError:
        raise ValidationError(
            f"Aggregate threshold {raw_val!r} must be numeric") from None
    return _Aggregate(func=func, scope=scope, field=fld, op=op, value=value)


def parse_query(text: str,
                opts: QueryOptions | None = None) -> ParsedQuery | None:
    opts = opts or QueryOptions()
    s = (text or "").strip()
    if not s:
        return None
    tokens = _tokenize(s)
    if opts.ignore_stopwords:
        tokens = [
            t for t in tokens
            if not (t[0] == "WORD" and t[1].lower() in STOP_WORDS
                    and ":" not in t[1] and "~" not in t[1]
                    and "*" not in t[1] and "?" not in t[1])
        ]
    if not tokens:
        return None
    parser = _Parser(tokens, opts)
    return parser.parse()


# ── Query preprocessing: macros (18) & scope directives (17) ───────

_MACRO_RE = re.compile(r"@([A-Za-z0-9_./-]+)")
_SCOPE_DIR_RE = re.compile(
    r"(?<!\S)(-?)(?:scope|in):([A-Za-z_][A-Za-z0-9_,]*)(?!\S)",
    re.IGNORECASE)


def expand_macros(query: str, *,
                  _depth: int = 0,
                  _seen: frozenset[str] = frozenset()) -> str:
    """Expand ``@saved_name`` tokens to the saved search's query text,
    parenthesised, recursively (item 18). Unknown names are left as-is;
    self/mutual references are broken by a depth + seen-set guard."""
    from .history import get_saved_search_by_name  # late: avoids import cycle
    if not query or "@" not in query or _depth >= _MACRO_MAX_DEPTH:
        return query

    def repl(m: re.Match) -> str:
        name = m.group(1)
        key = name.lower()
        if key in _seen:
            return ""                       # cycle — drop
        try:
            s = get_saved_search_by_name(name)
        except Exception:
            s = None
        if s is None or not (s.query or "").strip():
            return m.group(0)               # unknown ⇒ leave literal
        inner = expand_macros(
            s.query.strip(), _depth=_depth + 1, _seen=_seen | {key})
        return f"({inner})"

    return _MACRO_RE.sub(repl, query)


def _extract_scope_directives(
        query: str) -> tuple[str, list[str], list[str]]:
    """Pull ``scope:``/``in:`` (include) and ``-scope:`` (exclude) tokens
    out of the query (item 17). Returns (clean_query, include, exclude)."""
    include: list[str] = []
    exclude: list[str] = []

    def repl(m: re.Match) -> str:
        neg = m.group(1) == "-"
        names = [n for n in m.group(2).lower().split(",") if n]
        (exclude if neg else include).extend(names)
        return " "

    clean = _SCOPE_DIR_RE.sub(repl, query)
    return re.sub(r"\s+", " ", clean).strip(), include, exclude


# ── Aggregates (item 13) ──────────────────────────────────────────

def _collect_aggregates(node: ParsedQuery) -> list[_Aggregate]:
    out: list[_Aggregate] = []

    def walk(n: Any) -> None:
        if isinstance(n, _Aggregate):
            out.append(n)
        elif isinstance(n, _Not):
            walk(n.child)
        elif isinstance(n, (_And, _Or)):
            for c in n.children:
                walk(c)

    if node is not None:
        walk(node)
    return out


def _agg_field_value(doc: dict[str, Any], field_name: str) -> float | None:
    for key in (f"_{field_name}", field_name):
        if key in doc and doc[key] not in (None, ""):
            v = doc[key]
            try:
                return float(v)
            except (TypeError, ValueError):
                r = _grade_rank(str(v))
                return float(r) if r is not None else None
    return None


def _agg_metric(agg: _Aggregate, count: int,
                vals: list[float]) -> float | None:
    if agg.func == "count":
        return float(count)
    if not vals:
        return None
    if agg.func == "avg":
        return sum(vals) / len(vals)
    if agg.func == "min":
        return min(vals)
    if agg.func == "max":
        return max(vals)
    if agg.func == "sum":
        return sum(vals)
    return None


def _aggregate_ok_students(aggs: list[_Aggregate],
                           opts: QueryOptions) -> set[str]:
    """Student ids satisfying ALL aggregate constraints. Counts/means are
    computed over every row of the named scope, keyed by student id."""
    from .matching import _cmp  # late: avoids import cycle
    from .sources import _ADAPTERS  # late: avoids import cycle
    result: set[str] | None = None
    for agg in aggs:
        adapter = _ADAPTERS.get(agg.scope)
        if adapter is None:
            return set()
        _require_scope_access(agg.scope, f"{agg.func}()")
        try:
            hits = adapter(None, opts, {})
        except Exception:
            logger.exception("aggregate adapter %s failed", agg.scope)
            return set()
        counts: dict[str, int] = {}
        vals: dict[str, list[float]] = {}
        for h in hits:
            doc = (h.extra or {}).get("_doc") or {}
            sid = _doc_student_id(agg.scope, doc)
            if not sid:
                continue
            counts[sid] = counts.get(sid, 0) + 1
            if agg.field:
                v = _agg_field_value(doc, agg.field)
                if v is not None:
                    vals.setdefault(sid, []).append(v)
        ok: set[str] = set()
        for sid in set(counts) | set(vals):
            metric = _agg_metric(agg, counts.get(sid, 0), vals.get(sid, []))
            if metric is not None and _cmp(metric, agg.op, agg.value):
                ok.add(sid)
        result = ok if result is None else (result & ok)
    return result or set()


# ── Cross-scope joins & cohort membership (items 11, 12) ──────────

def _doc_student_id(scope: str, doc: dict[str, Any]) -> str:
    """The student id a doc refers to. Adapters put it in ``_sid``; older
    docs fall back to ``id`` for the ``students`` scope and ``name`` for
    every other student-keyed scope."""
    sid = doc.get("_sid")
    if sid:
        return str(sid).strip()
    if scope == "students":
        return str(doc.get("id") or "").strip()
    return str(doc.get("name") or "").strip()


def _require_scope_access(scope: str, what: str) -> None:
    """Refuse a student-level predicate over a scope the signed-in account
    may not search: otherwise ``missing(safeguarding)`` would reveal who
    has a concern without ever showing the concern."""
    from .matching import SCOPE_CAPABILITIES  # late: avoids import cycle
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    cap = SCOPE_CAPABILITIES.get(scope)
    if cap and not access.current().can(cap):
        raise ValidationError(
            f"{what} uses {scope!r} records, which your account cannot search.")


def _all_student_ids(opts: QueryOptions) -> set[str]:
    from .sources import _ADAPTERS  # late: avoids import cycle
    try:
        hits = _ADAPTERS["students"](None, opts, {})
    except Exception:
        logger.exception("students adapter failed for predicate")
        return set()
    out: set[str] = set()
    for h in hits:
        doc = (h.extra or {}).get("_doc") or {}
        sid = _doc_student_id("students", doc)
        if sid:
            out.add(sid)
    return out


def _has_students(node: _Has, opts: QueryOptions) -> set[str]:
    from .matching import _doc_match  # late: avoids import cycle
    from .sources import _ADAPTERS  # late: avoids import cycle
    adapter = _ADAPTERS.get(node.scope)
    if adapter is None:
        return set()
    _require_scope_access(node.scope,
                          "missing()" if node.negate else "has()")
    try:
        hits = adapter(None, opts, {})
    except Exception:
        logger.exception("has() adapter %s failed", node.scope)
        return set()
    inner = parse_query(node.term, opts) if node.term else None
    matched: set[str] = set()
    for h in hits:
        doc = (h.extra or {}).get("_doc") or {}
        sid = _doc_student_id(node.scope, doc)
        if not sid:
            continue
        if inner is None or _doc_match(inner, doc, opts):
            matched.add(sid)
    if node.negate:
        return _all_student_ids(opts) - matched
    return matched


_StudentPredicate = Any   # _Aggregate | _Has | _Cohort


def _collect_student_predicates(node: ParsedQuery) -> list[_StudentPredicate]:
    out: list[_StudentPredicate] = []

    def walk(n: Any) -> None:
        if isinstance(n, (_Aggregate, _Has, _Cohort)):
            out.append(n)
        elif isinstance(n, _Not):
            walk(n.child)
        elif isinstance(n, (_And, _Or)):
            for c in n.children:
                walk(c)

    if node is not None:
        walk(node)
    return out


def _resolve_student_predicates(preds: list[_StudentPredicate],
                                opts: QueryOptions) -> dict[int, set[str]]:
    """The student set each student-level predicate (aggregate / has /
    missing / cohort) implies, keyed by ``id(node)``. The engine evaluates
    the query with these, so predicates combine with AND, OR and NOT like
    any other term (item 11 join semantics)."""
    from .history import _cohort_member_ids  # late: avoids import cycle
    result: dict[int, set[str]] = {}
    for p in preds:
        if isinstance(p, _Aggregate):
            ok = _aggregate_ok_students([p], opts)
        elif isinstance(p, _Has):
            ok = _has_students(p, opts)
        elif isinstance(p, _Cohort):
            ok = set(_cohort_member_ids(p.name))
        else:
            continue
        result[id(p)] = ok
    return result


# ── Did-you-mean (item 20) ────────────────────────────────────────

def _suggest_vocab() -> set[str]:
    from .history import list_history, list_saved_searches  # late: avoids import cycle
    vocab: set[str] = set(SYNONYMS.keys()) | {
        f for f in _KNOWN_FIELDS if len(f) >= 3}
    for lbl in SCOPE_LABELS.values():
        vocab.update(re.findall(r"[a-z]{3,}", lbl.lower()))
    try:
        for h in list_history(limit=40):
            vocab.update(re.findall(r"[a-z]{3,}", (h.query or "").lower()))
        for s in list_saved_searches():
            vocab.update(re.findall(r"[a-z]{3,}", (s.query or "").lower()))
            vocab.update(re.findall(r"[a-z]{3,}", (s.name or "").lower()))
    except Exception:
        logger.debug("did_you_mean: vocab gather failed")
    return {_fold(w) for w in vocab if len(w) >= 3}


def did_you_mean(query: str,
                 opts: QueryOptions | None = None,
                 *, limit: int = 3) -> list[str]:
    """Return up to ``limit`` edit-distance-corrected query strings, or an
    empty list when nothing close is found (item 20)."""
    from .matching import _collect_terms  # late: avoids import cycle
    opts = opts or QueryOptions()
    try:
        parsed = parse_query(query, opts)
    except ValidationError:
        return []
    if parsed is None:
        return []
    terms = [t.text for t in _collect_terms(parsed)
             if isinstance(t, _Term) and not t.wildcard and not t.fuzzy
             and t.text and len(t.text) >= 3]
    if not terms:
        return []
    term_set = {_fold(t.lower()) for t in terms}
    vocab = _suggest_vocab() - term_set
    if not vocab:
        return []
    replacements: dict[str, str] = {}
    for term in dict.fromkeys(terms):           # preserve order, dedupe
        tl = _fold(term.lower())
        if any(tl in w or w in tl for w in vocab):
            continue                            # already plausible
        best: str | None = None
        best_d = 3
        for w in vocab:
            if abs(len(w) - len(tl)) > 2:
                continue
            d = _lev(tl, w, 2)
            if d < best_d or (d == best_d and best and len(w) > len(best)):
                best_d, best = d, w
        if best and best_d <= 2 and best != tl:
            replacements[term] = best
    if not replacements:
        return []
    suggestion = query
    for term, repl in replacements.items():
        suggestion = re.sub(
            rf"(?<!\w){re.escape(term)}(?!\w)", repl,
            suggestion, flags=re.IGNORECASE)
    if suggestion.strip().lower() == query.strip().lower():
        return []
    return [suggestion][:limit]

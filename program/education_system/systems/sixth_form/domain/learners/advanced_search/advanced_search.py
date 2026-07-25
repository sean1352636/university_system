"""Advanced Search — cross-domain query layer for the Sixth Form System.

Searches a keyword (or a structured query) across many of the system's
tables (students, staff, courses, subjects, class groups, behaviour log,
absence requests, attendance concerns, accommodations, safeguarding,
notices, messages).

Persistent tables:

* ``saved_searches`` — named query presets the user can re-run.
* ``search_history`` — a small ring of the most recent runs.

Query language
--------------
The query string supports:

1. Booleans:        ``AND``, ``OR``, ``NOT``, ``( )`` and a leading ``-``
                    for negation. Implicit operator between bare terms is
                    ``AND``.
2. Phrases:         ``"merit award"`` matches the exact substring.
3. Fields:          ``name:smith``, ``subject:maths``, ``email:@school``
                    restrict a term to a named field.
4. Wildcards:       ``smi*`` (zero+ chars), ``?ones`` (single char).
5. Fuzzy:           ``smith~`` (distance 1) or ``smith~2`` (distance 2)
                    using Levenshtein.
6. Stemming:        ``running`` matches ``runs``/``run`` (toggle via
                    ``QueryOptions.use_stemming``).
7. Synonyms:        ``maths`` ⇄ ``mathematics``; tunable dict.
8. Stop-words:      common filler words ignored by default
                    (``QueryOptions.ignore_stopwords``).
9. Date ranges:     ``date:>=2026-01-01`` or shorthand ``last:30d``,
                    ``last:6m``, ``last:1y`` — applied to the scope's
                    primary date.
10. Numeric/grade:  ``attendance:<85``, ``grade:>=B``.
11. Field phrases:  ``tutor:"john smith"`` — a quoted phrase scoped to a
                    single field (handles spaces inside the value).
12. Ranges:         ``attendance:80..90``, ``grade:C..A``,
                    ``date:2026-01-01..2026-03-31`` (inclusive both ends).
13. Aggregates:     ``count(behaviour)>3``, ``avg(attendance)<85`` —
                    per-student counts/means across a scope.
14. Relative cmp:   ``predicted<target``, ``current>=mte`` — compare two
                    grade/number fields on the same record.
15. Proximity:      ``"merit award"~5`` — the phrase's words within N words
                    of each other (loose phrase).
16. Regex:          ``/S1\\d{4}/`` or field-scoped ``id:/S1\\d{4}/`` —
                    raw regular-expression term (append ``i`` for
                    case-insensitive: ``/foo/i``).
17. Scope filter:   ``scope:students``/``in:staff`` to restrict, or
                    ``-scope:audit_logs`` to exclude, inline in the query.
18. Macros:         ``@at_risk`` expands to the query of a saved search of
                    that name (recursively, with a depth guard).
19. Diacritics:     matching folds accents by default (``zoë`` ≡ ``zoe``);
                    toggle via ``QueryOptions.fold_diacritics``.
20. Did-you-mean:   zero-result runs return ``SearchResults.suggestions``
                    with edit-distance-corrected query alternatives.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable
from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.ADVANCED_SEARCH_DB

DEFAULT_LIMIT_PER_SCOPE: int = 50
MAX_HISTORY_ROWS: int = 50


# Operator cheat-sheet shared by the CLI and GUI help screens.
QUERY_SYNTAX_HELP: str = """\
Query syntax
────────────
Booleans      smith AND maths      foo OR bar      NOT closed      -closed
Phrases       "merit award"
Fields        name:smith   email:@school   status:open
Field phrase  tutor:"john smith"            (quoted value, keeps spaces)
Wildcards     smi*    ?ones                 Fuzzy   smith~   smith~2
Dates         date:>=2026-01-01   last:30d  last:6m   last:1y
Numeric/grade attendance:<85      grade:>=B
Ranges        attendance:80..90   grade:C..A   date:2026-01-01..2026-03-31
Aggregates    count(behaviour)>3            avg(attendance)<85
              avg(progress_reviews.attendance)>=90
Relative      predicted<target   current>=mte   (grade/number vs grade/number)
Proximity     "merit award"~5               (words within N of each other)
Regex         /C\\d{4,}/         id:/^C5/    /foo/i   (append i = ignore case)
Scope filter  scope:students    in:staff    -scope:audit_logs
Macros        @saved_name                   (expands a saved search's query)
Joins         has(safeguarding)   missing(ucas)   has(behaviour:fighting)
Cohorts       cohort:year12_at_risk         (membership of a saved cohort)
Notes         accents fold (zoë≡zoe); zero hits suggest a 'did you mean'.
              Joins/aggregates/cohorts filter to the matching students."""


SCOPE_LABELS: dict[str, str] = {
    "students":             "Students",
    "staff":                "Staff",
    "courses":              "Courses",
    "subjects":             "Subjects",
    "class_groups":         "Class groups",
    "behaviour":            "Behaviour log",
    "absence_requests":     "Absence requests",
    "attendance_concerns":  "Attendance concerns",
    "accommodations":       "Accommodations",
    "safeguarding":         "Safeguarding",
    "notices":              "Notices",
    "messages":             "Messages",
    "predicted_grades":     "Predicted grades",
    "homework":             "Homework",
    "timetable":            "Timetable",
    "parents_evenings":     "Parents' evenings",
    "progress_reviews":     "Progress reviews",
    "surveys":              "Surveys",
    "ucas":                 "UCAS & references",
    "alumni":               "Alumni",
    "finance":              "Finance (fees & bursaries)",
    "library":              "Library catalogue",
    "documents":            "Document hub",
    "audit_logs":           "Audit / system logs",
}
ALL_SCOPES: tuple[str, ...] = tuple(SCOPE_LABELS.keys())
DEFAULT_SCOPES: tuple[str, ...] = ALL_SCOPES


_SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_searches (
    saved_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    query        TEXT NOT NULL DEFAULT '',
    scopes       TEXT NOT NULL DEFAULT '',
    filters      TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_history (
    history_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    query        TEXT NOT NULL,
    scopes       TEXT NOT NULL DEFAULT '',
    actor        TEXT,
    result_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sh_ts ON search_history(ts DESC);

CREATE TABLE IF NOT EXISTS pinned_results (
    pin_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    actor        TEXT NOT NULL,
    scope        TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    label        TEXT NOT NULL DEFAULT '',
    note         TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE (actor, scope, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_pr_actor ON pinned_results(actor);

CREATE TABLE IF NOT EXISTS scheduled_searches (
    schedule_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    saved_id         INTEGER NOT NULL,
    cron             TEXT NOT NULL DEFAULT 'daily',
    notify_actor     TEXT,
    last_run_at      TEXT,
    last_count       INTEGER NOT NULL DEFAULT 0,
    new_since_last   INTEGER NOT NULL DEFAULT 0,
    enabled          INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (saved_id) REFERENCES saved_searches(saved_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ss_saved ON scheduled_searches(saved_id);

CREATE TABLE IF NOT EXISTS subscription_notifications (
    notif_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id   INTEGER NOT NULL,
    actor         TEXT NOT NULL,
    delta         INTEGER NOT NULL DEFAULT 0,
    total         INTEGER NOT NULL DEFAULT 0,
    sample_scope  TEXT,
    sample_label  TEXT,
    sample_entity TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    read_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_sn_actor
    ON subscription_notifications(actor, read_at);

CREATE TABLE IF NOT EXISTS search_index_meta (
    scope          TEXT PRIMARY KEY,
    indexed_rows   INTEGER NOT NULL DEFAULT 0,
    last_refresh   TEXT
);

CREATE TABLE IF NOT EXISTS cohorts (
    cohort_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    owner_actor  TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cohort_members (
    cohort_id    INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    added_at     TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (cohort_id, student_id),
    FOREIGN KEY (cohort_id) REFERENCES cohorts(cohort_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cm_cohort ON cohort_members(cohort_id);

CREATE TABLE IF NOT EXISTS dashboards (
    dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    owner_actor  TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dashboard_items (
    dashboard_id INTEGER NOT NULL,
    saved_id     INTEGER NOT NULL,
    position     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (dashboard_id, saved_id),
    FOREIGN KEY (dashboard_id) REFERENCES dashboards(dashboard_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS search_audit (
    audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts               TEXT NOT NULL,
    actor            TEXT,
    role             TEXT,
    query            TEXT NOT NULL DEFAULT '',
    scopes           TEXT NOT NULL DEFAULT '',
    sensitive_scopes TEXT NOT NULL DEFAULT '',
    break_glass      INTEGER NOT NULL DEFAULT 0,
    reason           TEXT
);
CREATE INDEX IF NOT EXISTS idx_sa_ts ON search_audit(ts DESC);
"""


# Columns added to search_history over time (telemetry).
_SEARCH_HISTORY_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("elapsed_ms_json",   "TEXT"),
    ("result_count_json", "TEXT"),
    ("zero_result",       "INTEGER NOT NULL DEFAULT 0"),
)


# Columns added to saved_searches over time. Applied as ALTER TABLE
# at init_db() so existing DBs upgrade transparently.
_SAVED_SEARCH_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("owner_actor", "TEXT"),
    ("visibility",  "TEXT NOT NULL DEFAULT 'private'"),
    ("role_acl",    "TEXT"),
    ("folder",      "TEXT"),
    ("tags",        "TEXT"),
)

# Columns added to scheduled_searches (thresholds + delta snapshots).
_SCHEDULED_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("threshold",     "INTEGER NOT NULL DEFAULT 0"),
    ("last_keys_json", "TEXT"),
)

# Columns added to subscription_notifications (snooze).
_NOTIF_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("snoozed_until", "TEXT"),
)


@dataclass
class Hit:
    scope: str
    entity_id: str
    label: str
    sublabel: str = ""
    matched_field: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    matched_fields: list[str] = field(default_factory=list)
    highlights: dict[str, str] = field(default_factory=dict)
    pinned: bool = False
    cluster_count: int = 0   # 0 ⇒ not a cluster head


@dataclass
class SearchResults:
    query: str
    scopes: list[str]
    hits_by_scope: dict[str, list[Hit]]
    total: int
    ranked_hits: list[Hit] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)  # did-you-mean (item 20)

    def all_hits(self) -> list[Hit]:
        return [h for hits in self.hits_by_scope.values() for h in hits]


@dataclass
class SavedSearch:
    saved_id: int
    name: str
    query: str
    scopes: list[str]
    filters: dict[str, Any]
    notes: str | None
    created_at: str
    updated_at: str
    owner_actor: str | None = None
    visibility: str = "private"     # "private" | "role" | "public"
    role_acl: list[str] = field(default_factory=list)
    folder: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ScheduledSearch:
    schedule_id: int
    saved_id: int
    cron: str                       # cron expression or "daily"/"hourly"
    notify_actor: str | None
    last_run_at: str | None
    last_count: int
    new_since_last: int
    enabled: bool
    created_at: str
    threshold: int = 0              # only alert when total ≥ threshold (item 26)


@dataclass
class PinnedResult:
    pin_id: int
    actor: str
    scope: str
    entity_id: str
    label: str
    note: str | None
    created_at: str


@dataclass
class HistoryEntry:
    history_id: int
    ts: str
    query: str
    scopes: list[str]
    actor: str | None
    result_count: int


@dataclass
class Cohort:                 # item 12 — a named, reusable student set
    cohort_id: int
    name: str
    owner_actor: str | None
    notes: str | None
    created_at: str
    updated_at: str
    member_count: int = 0
    members: list[str] = field(default_factory=list)


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        existing = {r["name"] for r in conn.execute(
            "PRAGMA table_info(saved_searches)").fetchall()}
        for col, ddl in _SAVED_SEARCH_EXTRA_COLS:
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE saved_searches ADD COLUMN {col} {ddl}")
        existing_h = {r["name"] for r in conn.execute(
            "PRAGMA table_info(search_history)").fetchall()}
        for col, ddl in _SEARCH_HISTORY_EXTRA_COLS:
            if col not in existing_h:
                conn.execute(
                    f"ALTER TABLE search_history ADD COLUMN {col} {ddl}")
        for table, cols in (("scheduled_searches", _SCHEDULED_EXTRA_COLS),
                            ("subscription_notifications", _NOTIF_EXTRA_COLS)):
            have = {r["name"] for r in conn.execute(
                f"PRAGMA table_info({table})").fetchall()}
            for col, ddl in cols:
                if col not in have:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        conn.commit()
    _ensure_fts_index()
    logger.debug("Advanced-search schema ready at %s", DB_PATH)
    _DB_READY = True


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


_NAME_RE = re.compile(r"^[A-Za-z0-9 _/.\-]{1,48}$")


def _validate_scopes(scopes: Any) -> list[str]:
    if scopes is None:
        return list(DEFAULT_SCOPES)
    if isinstance(scopes, str):
        scopes = [s.strip() for s in scopes.split(",") if s.strip()]
    if not isinstance(scopes, (list, tuple)):
        raise ValidationError("scopes must be a list of scope keys")
    out: list[str] = []
    for s in scopes:
        s2 = str(s).strip()
        if s2 not in ALL_SCOPES:
            raise ValidationError(
                f"Unknown scope {s2!r}. Valid: {', '.join(ALL_SCOPES)}")
        if s2 not in out:
            out.append(s2)
    return out or list(DEFAULT_SCOPES)


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
})

_FIELD_ALIASES: dict[str, str] = {
    "desc": "description",
    "descr": "description",
    "note": "notes",
    "subj": "subject",
    "cat": "category",
    "dept": "department",
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


@dataclass
class QueryOptions:
    fuzzy_default: int = 0
    use_stemming: bool = True
    ignore_stopwords: bool = True
    expand_synonyms: bool = True
    fold_diacritics: bool = True
    today: _dt.date | None = None


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
    result: set[str] | None = None
    for agg in aggs:
        adapter = _ADAPTERS.get(agg.scope)
        if adapter is None:
            return set()
        try:
            hits = adapter(None, opts, {})
        except Exception:
            logger.exception("aggregate adapter %s failed", agg.scope)
            return set()
        counts: dict[str, int] = {}
        vals: dict[str, list[float]] = {}
        for h in hits:
            doc = (h.extra or {}).get("_doc") or {}
            sid = str(doc.get("name") or "").strip()
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
    """The student id a doc refers to. The ``students`` scope stores it in
    ``id`` (``name`` holds the full name); every other student-keyed scope
    stores the student id in ``name``."""
    if scope == "students":
        return str(doc.get("id") or "").strip()
    return str(doc.get("name") or "").strip()


def _all_student_ids(opts: QueryOptions) -> set[str]:
    try:
        hits = _ADAPTERS["students"](None, opts, {})
    except Exception:
        logger.exception("students adapter failed for predicate")
        return set()
    out: set[str] = set()
    for h in hits:
        doc = (h.extra or {}).get("_doc") or {}
        sid = str(doc.get("id") or doc.get("name") or "").strip()
        if sid:
            out.add(sid)
    return out


def _has_students(node: _Has, opts: QueryOptions) -> set[str]:
    adapter = _ADAPTERS.get(node.scope)
    if adapter is None:
        return set()
    try:
        hits = adapter(None, opts, {})
    except Exception:
        logger.exception("has() adapter %s failed", node.scope)
        return set()
    inner = parse_query(node.term, opts) if node.term else None
    matched: set[str] = set()
    for h in hits:
        doc = (h.extra or {}).get("_doc") or {}
        sid = str(doc.get("name") or "").strip()
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
                                opts: QueryOptions) -> set[str]:
    """Intersect the student sets implied by every student-level predicate
    (aggregate / has / missing / cohort) — item 11 join semantics."""
    result: set[str] | None = None
    for p in preds:
        if isinstance(p, _Aggregate):
            ok = _aggregate_ok_students([p], opts)
        elif isinstance(p, _Has):
            ok = _has_students(p, opts)
        elif isinstance(p, _Cohort):
            ok = set(_cohort_member_ids(p.name))
        else:
            continue
        result = ok if result is None else (result & ok)
    return result if result is not None else set()


# ── Did-you-mean (item 20) ────────────────────────────────────────

def _suggest_vocab() -> set[str]:
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


# ══════════════════════════════════════════════════════════════════
# Cohorts — named, reusable student sets (item 12)
# ══════════════════════════════════════════════════════════════════

def _cohort_from_row(r: sqlite3.Row, members: list[str]) -> Cohort:
    return Cohort(
        cohort_id=r["cohort_id"], name=r["name"],
        owner_actor=r["owner_actor"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        member_count=len(members), members=members,
    )


def _resolve_cohort_id(name_or_id: str | int) -> int | None:
    with _connect() as conn:
        if isinstance(name_or_id, int) or str(name_or_id).isdigit():
            r = conn.execute(
                "SELECT cohort_id FROM cohorts WHERE cohort_id = ?",
                (int(name_or_id),)).fetchone()
        else:
            r = conn.execute(
                "SELECT cohort_id FROM cohorts WHERE name = ?",
                (str(name_or_id).strip(),)).fetchone()
    return r["cohort_id"] if r else None


def _clean_student_ids(student_ids: Any) -> list[str]:
    if isinstance(student_ids, str):
        student_ids = re.split(r"[\s,]+", student_ids)
    out: list[str] = []
    for s in (student_ids or []):
        s2 = str(s).strip()
        if s2 and s2 not in out:
            out.append(s2)
    return out


def create_cohort(name: str, student_ids: Any, *,
                  owner_actor: str | None = None,
                  notes: str | None = None) -> Cohort:
    init_db()
    name = (name or "").strip()
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Cohort name must be 1–48 chars (letters, digits, space, _ . / -)")
    ids = _clean_student_ids(student_ids)
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM cohorts WHERE name = ?",
                        (name,)).fetchone():
            raise ValidationError(f"A cohort named {name!r} already exists")
        cur = conn.execute(
            "INSERT INTO cohorts (name, owner_actor, notes) VALUES (?, ?, ?)",
            (name, (owner_actor or None), (notes or None)))
        cid = cur.lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO cohort_members (cohort_id, student_id) "
            "VALUES (?, ?)", [(cid, s) for s in ids])
        conn.commit()
    logger.info("Created cohort #%d %r with %d member(s)", cid, name, len(ids))
    out = get_cohort(cid)
    assert out is not None
    return out


def create_cohort_from_results(name: str, results: SearchResults, *,
                               owner_actor: str | None = None,
                               notes: str | None = None) -> Cohort:
    """Build a cohort from the student ids present in a result set."""
    return create_cohort(name, _student_ids_from_results(results),
                         owner_actor=owner_actor, notes=notes)


def _student_ids_from_results(results: SearchResults) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for h in results.all_hits():
        sid = ""
        if h.scope == "students":
            sid = h.entity_id
        elif h.scope in _STUDENT_KEYED_SCOPES:
            doc = (h.extra or {}).get("_doc") or {}
            sid = str(doc.get("name") or "").strip() or _extract_student_id(h)
        sid = str(sid).strip()
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


def get_cohort(cohort_id: int) -> Cohort | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM cohorts WHERE cohort_id = ?",
                         (cohort_id,)).fetchone()
        if r is None:
            return None
        members = [row["student_id"] for row in conn.execute(
            "SELECT student_id FROM cohort_members WHERE cohort_id = ? "
            "ORDER BY student_id", (cohort_id,)).fetchall()]
    return _cohort_from_row(r, members)


def get_cohort_by_name(name: str) -> Cohort | None:
    cid = _resolve_cohort_id(name)
    return get_cohort(cid) if cid else None


def list_cohorts() -> list[Cohort]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT c.*, COUNT(m.student_id) AS n FROM cohorts c "
            "LEFT JOIN cohort_members m ON m.cohort_id = c.cohort_id "
            "GROUP BY c.cohort_id ORDER BY c.name ASC").fetchall()
    out: list[Cohort] = []
    for r in rows:
        c = _cohort_from_row(r, [])
        c.member_count = r["n"] or 0
        out.append(c)
    return out


def cohort_members(name_or_id: str | int) -> list[str]:
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        return []
    c = get_cohort(cid)
    return c.members if c else []


def _cohort_member_ids(name: str) -> list[str]:
    return cohort_members(name)


def add_to_cohort(name_or_id: str | int, student_ids: Any) -> int:
    init_db()
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        raise ValidationError(f"No cohort {name_or_id!r}")
    ids = _clean_student_ids(student_ids)
    with _connect() as conn:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM cohort_members WHERE cohort_id = ?",
            (cid,)).fetchone()["n"]
        conn.executemany(
            "INSERT OR IGNORE INTO cohort_members (cohort_id, student_id) "
            "VALUES (?, ?)", [(cid, s) for s in ids])
        conn.execute("UPDATE cohorts SET updated_at = datetime('now') "
                     "WHERE cohort_id = ?", (cid,))
        after = conn.execute(
            "SELECT COUNT(*) AS n FROM cohort_members WHERE cohort_id = ?",
            (cid,)).fetchone()["n"]
        conn.commit()
    return after - before


def remove_from_cohort(name_or_id: str | int, student_ids: Any) -> int:
    init_db()
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        raise ValidationError(f"No cohort {name_or_id!r}")
    ids = _clean_student_ids(student_ids)
    with _connect() as conn:
        cur = conn.executemany(
            "DELETE FROM cohort_members WHERE cohort_id = ? AND student_id = ?",
            [(cid, s) for s in ids])
        conn.execute("UPDATE cohorts SET updated_at = datetime('now') "
                     "WHERE cohort_id = ?", (cid,))
        conn.commit()
        return cur.rowcount


def delete_cohort(name_or_id: str | int) -> bool:
    init_db()
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM cohort_members WHERE cohort_id = ?", (cid,))
        cur = conn.execute("DELETE FROM cohorts WHERE cohort_id = ?", (cid,))
        conn.commit()
    return cur.rowcount > 0


# ══════════════════════════════════════════════════════════════════
# Relational reports (items 13–17)
# ══════════════════════════════════════════════════════════════════

@dataclass
class Relative:
    student_id: str
    full_name: str
    basis: str               # why they're linked (shared contact / surname)


@dataclass
class GroupRollup:
    group_id: int
    group_name: str
    member_count: int
    avg_attendance: float | None
    behaviour_points: int
    behaviour_count: int
    open_concerns: int
    members: list[str] = field(default_factory=list)


@dataclass
class UcasPeer:
    student_id: str
    university: str
    course_code: str | None
    course_name: str
    status: str


@dataclass
class UcasCluster:
    university: str
    course_code: str | None
    student_ids: list[str]


@dataclass
class Clash:
    kind: str                # "room" | "student"
    day: int
    period: int
    detail: str              # room name or student id
    group_ids: list[int]


@dataclass
class SimilarStudent:
    student_id: str
    full_name: str
    score: float
    shared: list[str]        # human-readable shared traits


def _norm_phone(p: str | None) -> str:
    return re.sub(r"\D", "", p or "")


# ── 13. Family / sibling linkage ──────────────────────────────────

def find_relatives(student_id: str) -> list[Relative]:
    """Students likely related to ``student_id`` — shared emergency-contact
    phone or name, or a shared surname with a shared contact. No address
    field exists on the model, so contact details are the linkage signal."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as m,
    )
    target = m.get_student(student_id)
    if target is None:
        raise ValidationError(f"No student {student_id!r}")
    t_phone = _norm_phone(getattr(target, "emergency_contact_phone", ""))
    t_name = (getattr(target, "emergency_contact_name", "") or "").strip().lower()
    t_last = (getattr(target, "last_name", "") or "").strip().lower()
    out: list[Relative] = []
    for s in m.list_students():
        if s.student_id == target.student_id:
            continue
        reasons: list[str] = []
        if t_phone and _norm_phone(
                getattr(s, "emergency_contact_phone", "")) == t_phone:
            reasons.append("shared emergency contact phone")
        s_name = (getattr(s, "emergency_contact_name", "") or "").strip().lower()
        if t_name and s_name == t_name:
            reasons.append("shared emergency contact name")
        # Shared surname is corroborating evidence, not a link on its own.
        s_last = (getattr(s, "last_name", "") or "").strip().lower()
        if reasons and t_last and s_last == t_last:
            reasons.append("shared surname")
        if reasons:
            out.append(Relative(
                student_id=s.student_id, full_name=s.full_name,
                basis=", ".join(dict.fromkeys(reasons))))
    return out


# ── 14. Teaching-group rollups ────────────────────────────────────

def group_rollup(group_id: int) -> GroupRollup:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    grp = cg.get_group(group_id)
    if grp is None:
        raise ValidationError(f"No class group #{group_id}")
    members = list(cg.list_members(group_id))
    att_vals: list[float] = []
    points = 0
    bcount = 0
    open_concerns = 0
    try:
        from education_system.systems.sixth_form.domain.operations.reporting.progress import (
            progress as pr,
        )
        for sid in members:
            revs = pr.reviews_for_student(sid)
            latest = next((r for r in revs
                           if getattr(r, "attendance_pct", None) is not None),
                          None)
            if latest is not None and latest.attendance_pct is not None:
                att_vals.append(float(latest.attendance_pct))
    except Exception:
        logger.debug("group_rollup: progress unavailable")
    try:
        from education_system.systems.sixth_form.domain.pastoral.behaviour import (
            behaviour as bh,
        )
        for sid in members:
            for e in bh.entries_for_student(sid):
                points += int(getattr(e, "points", 0) or 0)
                bcount += 1
    except Exception:
        logger.debug("group_rollup: behaviour unavailable")
    try:
        from education_system.systems.sixth_form.domain.pastoral.attendance_concerns import (
            attendance_concerns as ac,
        )
        for sid in members:
            for c in ac.concerns_for_student(sid):
                if (c.status or "").strip().lower() not in (
                        "closed", "resolved"):
                    open_concerns += 1
    except Exception:
        logger.debug("group_rollup: concerns unavailable")
    avg_att = round(sum(att_vals) / len(att_vals), 1) if att_vals else None
    return GroupRollup(
        group_id=group_id,
        group_name=getattr(grp, "group_name", f"Group #{group_id}"),
        member_count=len(members), avg_attendance=avg_att,
        behaviour_points=points, behaviour_count=bcount,
        open_concerns=open_concerns, members=members)


# ── 15. UCAS choice matching ──────────────────────────────────────

def ucas_peers(university: str,
               course_code: str | None = None) -> list[UcasPeer]:
    """Students with a UCAS choice at ``university`` (substring, case-
    insensitive), optionally narrowed to a course code."""
    uni = (university or "").strip().lower()
    if not uni:
        raise ValidationError("university is required")
    cc = (course_code or "").strip().lower() or None
    out: list[UcasPeer] = []
    from education_system.systems.sixth_form.domain.progression.ucas import (
        ucas as u,
    )
    for app in u.list_applications():
        for ch in u.list_choices(app.application_id):
            if uni not in (ch.university or "").lower():
                continue
            if cc and cc != (ch.course_code or "").lower():
                continue
            out.append(UcasPeer(
                student_id=app.student_id, university=ch.university,
                course_code=ch.course_code, course_name=ch.course_name,
                status=ch.decision_status or app.status or ""))
    return out


def ucas_choice_clusters(*, by_course: bool = False,
                         min_size: int = 2) -> list[UcasCluster]:
    """Group students by shared UCAS university (and optionally course)."""
    from education_system.systems.sixth_form.domain.progression.ucas import (
        ucas as u,
    )
    buckets: dict[tuple[str, str | None], list[str]] = {}
    for app in u.list_applications():
        for ch in u.list_choices(app.application_id):
            uni = (ch.university or "").strip()
            if not uni:
                continue
            key = (uni, (ch.course_code or None) if by_course else None)
            ids = buckets.setdefault(key, [])
            if app.student_id not in ids:
                ids.append(app.student_id)
    out = [UcasCluster(university=k[0], course_code=k[1], student_ids=v)
           for k, v in buckets.items() if len(v) >= min_size]
    out.sort(key=lambda c: (-len(c.student_ids), c.university))
    return out


# ── 16. Timetable clashes ─────────────────────────────────────────

def timetable_clashes() -> list[Clash]:
    """Detect room double-bookings and per-student timetable conflicts."""
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as tt,
    )
    slots = tt.list_slots()
    out: list[Clash] = []
    # Room clashes: same (day, period, room) used by >1 distinct group.
    by_room: dict[tuple[int, int, str], list[int]] = {}
    for s in slots:
        if not s.room:
            continue
        key = (s.day, s.period, s.room)
        ids = by_room.setdefault(key, [])
        if s.group_id not in ids:
            ids.append(s.group_id)
    for (day, period, room), gids in by_room.items():
        if len(gids) > 1:
            out.append(Clash("room", day, period, room, sorted(gids)))
    # Student clashes: a student whose groups meet at the same (day, period).
    try:
        from education_system.systems.sixth_form.domain.academics.class_groups import (
            class_groups as cg,
        )
        slots_by_group: dict[int, list] = {}
        for s in slots:
            slots_by_group.setdefault(s.group_id, []).append(s)
        student_groups: dict[str, list[int]] = {}
        for g in cg.list_groups():
            for sid in cg.list_members(g.group_id):
                student_groups.setdefault(sid, []).append(g.group_id)
        for sid, gids in student_groups.items():
            seen: dict[tuple[int, int], list[int]] = {}
            for gid in gids:
                for s in slots_by_group.get(gid, []):
                    seen.setdefault((s.day, s.period), [])
                    if gid not in seen[(s.day, s.period)]:
                        seen[(s.day, s.period)].append(gid)
            for (day, period), clash_gids in seen.items():
                if len(clash_gids) > 1:
                    out.append(Clash("student", day, period, sid,
                                     sorted(clash_gids)))
    except Exception:
        logger.debug("timetable_clashes: student pass unavailable")
    return out


# ── 17. Similar students ──────────────────────────────────────────

def similar_students(student_id: str, *,
                     limit: int = 10) -> list[SimilarStudent]:
    """Rank other students by overlap of subjects and tutor group/year."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as m,
    )
    target = m.get_student(student_id)
    if target is None:
        raise ValidationError(f"No student {student_id!r}")
    t_subjects = {s.strip().lower() for s in (target.subjects or []) if s}
    t_year = _student_year(target.student_id)
    t_tg = _student_tutor_group(target.student_id)
    ranked: list[SimilarStudent] = []
    for s in m.list_students():
        if s.student_id == target.student_id:
            continue
        shared: list[str] = []
        score = 0.0
        subj = {x.strip().lower() for x in (s.subjects or []) if x}
        common = t_subjects & subj
        if common:
            score += 2.0 * len(common)
            shared.append(f"subjects: {', '.join(sorted(common))}")
        tg = _student_tutor_group(s.student_id)
        if t_tg and tg == t_tg:
            score += 1.5
            shared.append(f"tutor group {tg}")
        elif t_year is not None and _student_year(s.student_id) == t_year:
            score += 0.5
            shared.append(f"year {t_year}")
        if score > 0:
            ranked.append(SimilarStudent(
                student_id=s.student_id, full_name=s.full_name,
                score=round(score, 2), shared=shared))
    ranked.sort(key=lambda x: (-x.score, x.student_id))
    return ranked[:limit]


def student_group_index() -> dict[str, tuple[int | None, str | None]]:
    """Map every student id → (year_group, tutor_group_name) in one pass.

    Used by the GUI to group results by year/tutor without an O(N) query
    per row. Students with no tutor group are absent from the map."""
    out: dict[str, tuple[int | None, str | None]] = {}
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as tg,
        )
        for g in tg.list_groups():
            for sid in tg.list_members(g.tutor_group_id):
                out[sid] = (g.year_group, g.name)
    except Exception:
        logger.debug("student_group_index unavailable")
    return out


def _student_year(student_id: str) -> int | None:
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as tg,
        )
        for g in tg.list_groups():
            if student_id in tg.list_members(g.tutor_group_id):
                return g.year_group
    except Exception:
        logger.debug("_student_year failed")
    return None


def _student_tutor_group(student_id: str) -> str | None:
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as tg,
        )
        for g in tg.list_groups():
            if student_id in tg.list_members(g.tutor_group_id):
                return g.name
    except Exception:
        logger.debug("_student_tutor_group failed")
    return None


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
          opts: QueryOptions) -> bool:
    if isinstance(node, _And):
        return all(_eval(c, raw, words, doc, opts) for c in node.children)
    if isinstance(node, _Or):
        return any(_eval(c, raw, words, doc, opts) for c in node.children)
    if isinstance(node, _Not):
        return not _eval(node.child, raw, words, doc, opts)
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
        # Student-level predicates: post-filters applied per-student in
        # run_search; during per-record evaluation they never exclude a row.
        return True
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
    hit.extra["_doc"] = doc
    out.append(hit)


def _search_students(parsed: ParsedQuery,
                     opts: QueryOptions,
                     _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as m,
    )
    rows = m.list_students()
    out: list[Hit] = []
    for s in rows:
        subjects = ", ".join(getattr(s, "subjects", []) or [])
        doc = {
            "id":      s.student_id,
            "name":    s.full_name,
            "email":   s.email or "",
            "phone":   s.phone or "",
            "subject": subjects,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="students",
            entity_id=s.student_id,
            label=f"{s.student_id} — {s.full_name}",
            sublabel=_trim(f"{s.email or '—'}  ·  {subjects}", 100),
        ))
    return out


def _search_staff(parsed: ParsedQuery,
                  opts: QueryOptions,
                  _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.staff import (
        staff as m,
    )
    rows = m.list_staff()
    out: list[Hit] = []
    for s in rows:
        full = f"{s.first_name} {s.last_name}".strip()
        doc = {
            "id":         s.staff_id,
            "name":       full,
            "email":      getattr(s, "email", "") or "",
            "role":       getattr(s, "role", "") or "",
            "department": getattr(s, "department", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="staff",
            entity_id=s.staff_id,
            label=f"{s.staff_id} — {full}",
            sublabel=_trim(
                f"{doc['role'] or '—'}  ·  {doc['email'] or '—'}", 100),
        ))
    return out


def _search_courses(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as m,
    )
    rows = m.list_courses()
    out: list[Hit] = []
    for c in rows:
        doc = {
            "code":        getattr(c, "course_code", "") or "",
            "title":       getattr(c, "title", "") or "",
            "level":       getattr(c, "level", "") or "",
            "description": getattr(c, "description", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="courses",
            entity_id=str(c.course_id),
            label=f"{doc['code']} — {doc['title']}",
            sublabel=_trim(doc["level"], 80),
        ))
    return out


def _search_subjects(parsed: ParsedQuery,
                     opts: QueryOptions,
                     _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as m,
    )
    rows = m.list_subjects()
    out: list[Hit] = []
    for s in rows:
        doc = {
            "name":     s.name,
            "subject":  s.name,
            "category": getattr(s, "qualification", "") or "",
            "code":     getattr(s, "exam_board", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="subjects",
            entity_id=str(s.subject_id),
            label=s.name,
            sublabel=_trim(
                f"{doc['category'] or '—'}  ·  {doc['code'] or '—'}", 80),
        ))
    return out


def _search_class_groups(parsed: ParsedQuery,
                         opts: QueryOptions,
                         _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as m,
    )
    rows = m.list_groups()
    out: list[Hit] = []
    for g in rows:
        bits = []
        for fld in ("code", "name", "label", "group_code"):
            v = getattr(g, fld, None)
            if v:
                bits.append(str(v))
        title = " · ".join(bits) or f"Group #{g.group_id}"
        doc = {
            "id":    str(g.group_id),
            "code":  _first_attr(g, "code", "group_code"),
            "name":  _first_attr(g, "name", "label"),
            "title": title,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="class_groups",
            entity_id=str(g.group_id),
            label=title,
            sublabel=_trim(f"course_id={getattr(g, 'course_id', '—')}", 60),
        ))
    return out


def _search_behaviour(parsed: ParsedQuery,
                      opts: QueryOptions,
                      _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as m,
    )
    rows = m.list_entries()
    out: list[Hit] = []
    for e in rows:
        doc = {
            "id":          str(e.entry_id),
            "name":        e.student_id or "",
            "type":        e.entry_type or "",
            "category":    e.category or "",
            "description": e.description or "",
            "location":    e.location or "",
            "action":      e.action_taken or "",
            "_date":       getattr(e, "entry_date", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="behaviour",
            entity_id=str(e.entry_id),
            label=f"#{e.entry_id} {e.student_id} · {e.entry_type}"
                  f" · {e.category}",
            sublabel=_trim(
                f"{e.entry_date}  ·  {e.description or ''}", 110),
        ))
    return out


def _search_absence_requests(parsed: ParsedQuery,
                             opts: QueryOptions,
                             _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.absence_requests import (
        absence_requests as m,
    )
    rows = m.list_requests()
    out: list[Hit] = []
    for r in rows:
        doc = {
            "id":          str(r.request_id),
            "name":        r.student_id or "",
            "reason":      r.reason or "",
            "description": r.description or "",
            "status":      r.status or "",
            "author":      r.submitted_by or "",
            "notes":       r.notes or "",
            "_date":       getattr(r, "start_date", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="absence_requests",
            entity_id=str(r.request_id),
            label=f"#{r.request_id} {r.student_id} · {r.reason}"
                  f" · {r.status}",
            sublabel=_trim(
                f"{r.start_date} → {r.end_date}  ·  "
                f"{r.description or ''}", 110),
        ))
    return out


def _search_attendance_concerns(parsed: ParsedQuery,
                                opts: QueryOptions,
                                _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.attendance_concerns import (
        attendance_concerns as m,
    )
    rows = m.list_concerns()
    out: list[Hit] = []
    for c in rows:
        att = getattr(c, "attendance_pct", None)
        doc = {
            "id":          str(c.concern_id),
            "name":        c.student_id or "",
            "level":       c.level or "",
            "status":      c.status or "",
            "reason":      c.reason or "",
            "description": c.description or "",
            "action":      c.action_taken or "",
            "notes":       c.notes or "",
            "author":      c.raised_by or "",
            "_date":       getattr(c, "raised_date", "") or "",
            "_attendance": att,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="attendance_concerns",
            entity_id=str(c.concern_id),
            label=f"#{c.concern_id} {c.student_id} · "
                  f"{c.level} · {c.status}",
            sublabel=_trim(
                f"{c.raised_date}  ·  {c.reason}  ·  "
                f"{c.description or ''}", 110),
        ))
    return out


def _search_accommodations(parsed: ParsedQuery,
                           opts: QueryOptions,
                           _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.accessibility import (
        accessibility as m,
    )
    rows = m.list_accommodations()
    out: list[Hit] = []
    for a in rows:
        doc = {
            "id":          str(a.accommodation_id),
            "name":        a.name or "",
            "description": a.description or "",
            "category":    a.category or "",
            "status":      a.status or "",
            "author":      a.approved_by or "",
            "notes":       a.notes or "",
            "_date":       getattr(a, "start_date", "")
                          or getattr(a, "created_at", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="accommodations",
            entity_id=str(a.accommodation_id),
            label=f"#{a.accommodation_id} {a.student_id} · {a.name}",
            sublabel=_trim(
                f"{a.category}  ·  {a.status}  ·  "
                f"{a.description or ''}", 110),
        ))
    return out


def _search_safeguarding(parsed: ParsedQuery,
                         opts: QueryOptions,
                         _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.safeguarding import (
        safeguarding as m,
    )
    rows = m.list_concerns()
    out: list[Hit] = []
    for c in rows:
        sid = getattr(c, "student_id", "") or ""
        doc = {
            "id":          str(getattr(c, "concern_id", "")),
            "name":        sid,
            "summary":     getattr(c, "summary", "") or "",
            "description": getattr(c, "description", "") or "",
            "category":    getattr(c, "category", "") or "",
            "status":      getattr(c, "status", "") or "",
            "author":      getattr(c, "raised_by", "") or "",
            "notes":       getattr(c, "notes", "") or "",
            "_date":       getattr(c, "raised_date", "")
                          or getattr(c, "created_at", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        label_bits = [
            f"#{getattr(c, 'concern_id', '?')}",
            sid or "—",
            doc["category"], doc["status"],
        ]
        _emit(out, doc, Hit(
            scope="safeguarding",
            entity_id=str(getattr(c, "concern_id", "")),
            label=" · ".join(b for b in label_bits if b),
            sublabel=_trim(doc["summary"] or doc["description"], 110),
        ))
    return out


def _search_notices(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.operations.communications.notices import (
        notices as m,
    )
    rows = m.list_notices()
    out: list[Hit] = []
    for n in rows:
        doc = {
            "id":     str(n.notice_id),
            "title":  getattr(n, "title", "") or "",
            "body":   getattr(n, "body", "") or "",
            "author": getattr(n, "author", "")
                      or getattr(n, "posted_by", "") or "",
            "_date":  getattr(n, "posted_at", "")
                     or getattr(n, "created_at", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="notices",
            entity_id=str(n.notice_id),
            label=f"#{n.notice_id} {doc['title']}",
            sublabel=_trim(doc["body"], 110),
        ))
    return out


def _search_messages(parsed: ParsedQuery,
                     opts: QueryOptions,
                     _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as m,
    )
    rows = m.list_messages()
    out: list[Hit] = []
    for msg in rows:
        when = (msg.sent_at or msg.received_at or msg.created_at or "")
        doc = {
            "id":        str(msg.message_id),
            "direction": msg.direction or "",
            "title":     msg.subject or "",
            "body":      msg.body or "",
            "email":     msg.to_address or "",
            "name":      msg.to_name or "",
            "_date":     when,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="messages",
            entity_id=str(msg.message_id),
            label=f"#{msg.message_id} {msg.direction or '—'} · "
                  f"{msg.subject}",
            sublabel=_trim(
                f"{when}  ·  to {msg.to_address or msg.to_name or '—'}"
                f"  ·  {msg.body or ''}", 110),
        ))
    return out


def _search_predicted_grades(parsed: ParsedQuery,
                             opts: QueryOptions,
                             _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
        predicted_grades as m,
    )
    rows = m.list_predictions()
    # Best-effort map of (student, subject) → target grades so relative
    # comparisons like ``predicted<target`` (item 14) have something to
    # compare against. Missing module ⇒ empty map (relative cmp ⇒ no match).
    targets: dict[tuple[str, str], Any] = {}
    try:
        from education_system.systems.sixth_form.domain.assessment.target_setting import (
            target_setting as _ts,
        )
        for t in _ts.list_targets():
            targets[(t.student_id, t.subject_name)] = t
    except Exception:
        logger.debug("target_setting unavailable for predicted_grades adapter")
    out: list[Hit] = []
    for p in rows:
        tgt = targets.get((p.student_id or "", p.subject or ""))
        doc = {
            "id":          str(p.prediction_id),
            "name":        p.student_id or "",
            "subject":     p.subject or "",
            "category":    p.confidence or "",
            "notes":       p.notes or "",
            "author":      p.predicted_by or "",
            "_date":       getattr(p, "predicted_at", "") or "",
            "_grade":      p.grade or "",
            "_target":      (getattr(tgt, "mte_grade", "") or "") if tgt else "",
            "_aspirational": (getattr(tgt, "aspirational_grade", "") or "")
                             if tgt else "",
            "_current":     (getattr(tgt, "current_grade", "") or "") if tgt else "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="predicted_grades",
            entity_id=str(p.prediction_id),
            label=f"#{p.prediction_id} {p.student_id} · {p.subject} "
                  f"· {p.grade}",
            sublabel=_trim(
                f"{p.confidence or '—'}  ·  {p.notes or ''}", 110),
        ))
    return out


def _search_homework(parsed: ParsedQuery,
                     opts: QueryOptions,
                     _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.homework import (
        homework as m,
    )
    rows = m.list_assignments()
    out: list[Hit] = []
    for a in rows:
        doc = {
            "id":          str(a.assignment_id),
            "title":       a.title or "",
            "type":        a.type or "",
            "description": a.description or "",
            "notes":       a.notes or "",
            "code":        f"group:{a.group_id}",
            "_date":       a.due_date or a.set_date or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="homework",
            entity_id=str(a.assignment_id),
            label=f"#{a.assignment_id} {a.title} · {a.type}",
            sublabel=_trim(
                f"group {a.group_id}  ·  set {a.set_date}  ·  "
                f"due {a.due_date}", 110),
        ))
    return out


def _search_timetable(parsed: ParsedQuery,
                      opts: QueryOptions,
                      _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as m,
    )
    rows = m.list_slots()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    out: list[Hit] = []
    for s in rows:
        day_lbl = days[s.day - 1] if 1 <= s.day <= 7 else f"day{s.day}"
        doc = {
            "id":       str(s.slot_id),
            "code":     f"group:{s.group_id}",
            "location": s.room or "",
            "notes":    s.notes or "",
            "type":     day_lbl,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="timetable",
            entity_id=str(s.slot_id),
            label=f"#{s.slot_id} {day_lbl} P{s.period} · group {s.group_id}"
                  f" · {s.room or '—'}",
            sublabel=_trim(
                f"{s.start_time or '—'}–{s.end_time or '—'}  ·  "
                f"{s.notes or ''}", 110),
        ))
    return out


def _search_parents_evenings(parsed: ParsedQuery,
                             opts: QueryOptions,
                             _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.operations.communications.parents_evenings import (
        parents_evenings as m,
    )
    rows = m.list_events()
    out: list[Hit] = []
    for e in rows:
        doc = {
            "id":       str(e.event_id),
            "name":     e.name or "",
            "title":    e.name or "",
            "level":    e.year_group or "",
            "location": e.location or "",
            "status":   e.status or "",
            "notes":    e.notes or "",
            "_date":    e.event_date or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="parents_evenings",
            entity_id=str(e.event_id),
            label=f"#{e.event_id} {e.name} · {e.event_date} · "
                  f"{e.year_group}",
            sublabel=_trim(
                f"{e.start_time}–{e.end_time}  ·  "
                f"{e.location or '—'}  ·  {e.status}", 110),
        ))
    return out


def _search_progress_reviews(parsed: ParsedQuery,
                             opts: QueryOptions,
                             _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.operations.reporting.progress import (
        progress as m,
    )
    rows = m.list_reviews()
    out: list[Hit] = []
    for r in rows:
        doc = {
            "id":          str(r.review_id),
            "name":        r.student_id or "",
            "type":        r.period or "",
            "level":       r.risk_level or "",
            "status":      r.status or "",
            "description": (r.academic_summary or "")
                           + " " + (r.behaviour_summary or ""),
            "notes":       (r.next_steps or "")
                           + " " + (r.notes or ""),
            "author":      r.reviewer_staff_id or "",
            "_date":       r.review_date or "",
            "_attendance": r.attendance_pct,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="progress_reviews",
            entity_id=str(r.review_id),
            label=f"#{r.review_id} {r.student_id} · {r.period} · "
                  f"{r.status}",
            sublabel=_trim(
                f"{r.review_date}  ·  risk {r.risk_level}  ·  "
                f"{(r.academic_summary or r.behaviour_summary or '')}", 110),
        ))
    return out


def _search_surveys(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.surveys import (
        surveys as m,
    )
    rows = m.list_surveys()
    out: list[Hit] = []
    for s in rows:
        prompts = " ".join(q.prompt for q in (s.questions or [])
                           if getattr(q, "prompt", None))
        doc = {
            "id":          str(s.survey_id),
            "name":        s.name or "",
            "title":       s.name or "",
            "description": s.description or "",
            "level":       s.audience or "",
            "status":      s.status or "",
            "notes":       s.notes or "",
            "author":      s.created_by or "",
            "body":        prompts,
            "_date":       s.open_on or s.created_on or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="surveys",
            entity_id=str(s.survey_id),
            label=f"#{s.survey_id} {s.name} · {s.audience} · {s.status}",
            sublabel=_trim(
                f"{len(s.questions or [])} questions  ·  "
                f"{s.description or ''}", 110),
        ))
    return out


def _search_ucas(parsed: ParsedQuery,
                 opts: QueryOptions,
                 _filters: dict) -> list[Hit]:
    out: list[Hit] = []
    try:
        from education_system.systems.sixth_form.domain.progression.ucas import (
            ucas as u,
        )
        for a in u.list_applications():
            choices_text = ""
            try:
                ch = u.list_choices(a.application_id)
                choices_text = " ".join(
                    f"{c.university} {c.course_code or ''} {c.course_name or ''}"
                    for c in ch)
            except Exception:
                pass
            doc = {
                "id":          f"app:{a.application_id}",
                "name":        a.student_id or "",
                "code":        a.ucas_id or "",
                "status":      a.status or "",
                "description": choices_text,
                "body":        a.personal_statement or "",
                "notes":       a.notes or "",
                "_date":       a.submitted_at or a.created_at or "",
            }
            if not _filter_match(parsed, opts, doc):
                continue
            _emit(out, doc, Hit(
                scope="ucas",
                entity_id=f"app:{a.application_id}",
                label=f"App #{a.application_id} {a.student_id} · "
                      f"cycle {a.cycle_year} · {a.status}",
                sublabel=_trim(choices_text or a.notes or "", 110),
            ))
    except Exception:
        logger.exception("UCAS adapter (applications) failed")
    try:
        from education_system.systems.sixth_form.domain.progression.references import (
            references as r,
        )
        for ref in r.list_references():
            doc = {
                "id":          f"ref:{ref.reference_id}",
                "name":        ref.student_id or "",
                "author":      ref.referee or "",
                "role":        ref.referee_role or "",
                "title":       ref.title or "",
                "status":      ref.status or "",
                "body":        ref.body or "",
                "notes":       ref.notes or "",
                "_date":       ref.submitted_at or ref.requested_at
                                or ref.created_at or "",
            }
            if not _filter_match(parsed, opts, doc):
                continue
            _emit(out, doc, Hit(
                scope="ucas",
                entity_id=f"ref:{ref.reference_id}",
                label=f"Ref #{ref.reference_id} {ref.student_id} · "
                      f"{ref.referee} · {ref.status}",
                sublabel=_trim(
                    f"{ref.title or '—'}  ·  {ref.word_count}w  ·  "
                    f"{ref.body or ''}", 110),
            ))
    except Exception:
        logger.exception("UCAS adapter (references) failed")
    return out


def _search_alumni(parsed: ParsedQuery,
                   opts: QueryOptions,
                   _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.learners.alumni import (
        alumni as m,
    )
    rows = m.list_alumni()
    out: list[Hit] = []
    for a in rows:
        full = a.full_name
        doc = {
            "id":          str(a.alumni_id),
            "name":        full,
            "email":       a.email or "",
            "phone":       a.phone or "",
            "role":        a.current_role or "",
            "department":  a.current_employer or "",
            "category":    a.current_sector or "",
            "location":    a.current_location
                           or a.country or a.region or "",
            "level":       a.leaving_year or "",
            "status":      a.status or "",
            "description": a.bio or "",
            "notes":       a.notes or "",
            "_date":       a.leaving_date or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        bits = [full]
        if a.leaving_year:
            bits.append(f"leaver {a.leaving_year}")
        if a.current_role:
            bits.append(a.current_role)
        if a.current_employer:
            bits.append(f"@ {a.current_employer}")
        _emit(out, doc, Hit(
            scope="alumni",
            entity_id=str(a.alumni_id),
            label=f"#{a.alumni_id} {full}",
            sublabel=_trim(" · ".join(bits[1:]) or (a.bio or ""), 110),
        ))
    return out


def _search_finance(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    out: list[Hit] = []
    try:
        from education_system.systems.sixth_form.domain.finance.fees import (
            fees as f,
        )
        for it in f.list_items():
            doc = {
                "id":          f"fee:{it.fee_id}",
                "name":        it.student_id or "",
                "title":       it.description or "",
                "category":    it.category or "",
                "status":      it.stored_status or "",
                "level":       it.academic_year or "",
                "notes":       it.notes or "",
                "_date":       it.issued_date or "",
            }
            if not _filter_match(parsed, opts, doc):
                continue
            _emit(out, doc, Hit(
                scope="finance",
                entity_id=f"fee:{it.fee_id}",
                label=f"Fee #{it.fee_id} {it.student_id} · "
                      f"{it.category} · £{it.amount:.2f}",
                sublabel=_trim(
                    f"{it.description}  ·  due {it.due_date or '—'}  ·  "
                    f"{it.stored_status or '—'}", 110),
            ))
    except Exception:
        logger.exception("Finance adapter (fees) failed")
    try:
        from education_system.systems.sixth_form.domain.finance.bursaries import (
            bursaries as b,
        )
        for app in b.list_applications():
            doc = {
                "id":          f"burs:{app.application_id}",
                "name":        app.student_id or "",
                "category":    app.bursary_type or "",
                "status":      app.status or "",
                "reason":      app.reason or "",
                "level":       app.academic_year or "",
                "notes":       (app.decision_note or "")
                               + " " + (app.notes or ""),
                "author":      app.assessed_by or "",
                "_date":       app.application_date or "",
            }
            if not _filter_match(parsed, opts, doc):
                continue
            awarded = (f"£{app.amount_awarded:.2f}"
                        if app.amount_awarded is not None else "—")
            _emit(out, doc, Hit(
                scope="finance",
                entity_id=f"burs:{app.application_id}",
                label=f"Burs #{app.application_id} {app.student_id} · "
                      f"{app.bursary_type} · {app.status}",
                sublabel=_trim(
                    f"awarded {awarded}  ·  {app.reason or ''}", 110),
            ))
    except Exception:
        logger.exception("Finance adapter (bursaries) failed")
    return out


def _search_library(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.library import (
        library as m,
    )
    rows = m.list_books()
    out: list[Hit] = []
    for b in rows:
        doc = {
            "id":          str(b.book_id),
            "title":       b.title or "",
            "author":      b.author or "",
            "code":        b.isbn or "",
            "subject":     b.subject_area or "",
            "category":    b.item_type or "",
            "status":      b.status or "",
            "location":    b.location or "",
            "description": b.description or "",
            "notes":       (b.keywords or "")
                           + " " + (b.notes or ""),
            "_date":       getattr(b, "created_at", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="library",
            entity_id=str(b.book_id),
            label=f"#{b.book_id} {b.title}"
                  + (f" — {b.author}" if b.author else ""),
            sublabel=_trim(
                f"{b.item_type}  ·  {b.copies_available}/{b.copies_total}"
                f"  ·  {b.location or '—'}", 110),
        ))
    return out


def _search_documents(parsed: ParsedQuery,
                      opts: QueryOptions,
                      _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.operations.document_hub import (
        document_hub as m,
    )
    rows = m.list_documents()
    out: list[Hit] = []
    for d in rows:
        doc = {
            "id":          str(d.document_id),
            "title":       d.title or "",
            "description": d.description or "",
            "category":    d.category or "",
            "level":       d.audience or "",
            "status":      d.status or "",
            "code":        d.version or "",
            "author":      d.author or "",
            "department":  d.owner_department or "",
            "notes":       (d.keywords or "")
                           + " " + (d.notes or ""),
            "_date":       d.issued_on or d.created_on or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="documents",
            entity_id=str(d.document_id),
            label=f"#{d.document_id} {d.title} · v{d.version}",
            sublabel=_trim(
                f"{d.category}  ·  {d.audience}  ·  {d.status}  ·  "
                f"{d.description or ''}", 110),
        ))
    return out


def _search_audit_logs(parsed: ParsedQuery,
                       opts: QueryOptions,
                       _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.infrastructure import log_store as m
    rows = m.list_logs(limit=500)
    out: list[Hit] = []
    for r in rows:
        doc = {
            "id":          str(r.log_id),
            "level":       r.level or "",
            "name":        r.student_id or "",
            "code":        r.logger_name or "",
            "title":       (r.module or "") + " · " + (r.func_name or ""),
            "body":        r.message or "",
            "description": r.exc_text or "",
            "notes":       r.extra_json or "",
            "_date":       r.ts or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="audit_logs",
            entity_id=str(r.log_id),
            label=f"[{r.level}] #{r.log_id} {r.logger_name}",
            sublabel=_trim(
                f"{r.ts}  ·  {r.message}", 130),
        ))
    return out


_ADAPTERS: dict[str, Callable[
    [ParsedQuery, QueryOptions, dict], list[Hit]]] = {
    "students":             _search_students,
    "staff":                _search_staff,
    "courses":              _search_courses,
    "subjects":             _search_subjects,
    "class_groups":         _search_class_groups,
    "behaviour":            _search_behaviour,
    "absence_requests":     _search_absence_requests,
    "attendance_concerns":  _search_attendance_concerns,
    "accommodations":       _search_accommodations,
    "safeguarding":         _search_safeguarding,
    "notices":              _search_notices,
    "messages":             _search_messages,
    "predicted_grades":     _search_predicted_grades,
    "homework":             _search_homework,
    "timetable":            _search_timetable,
    "parents_evenings":     _search_parents_evenings,
    "progress_reviews":     _search_progress_reviews,
    "surveys":              _search_surveys,
    "ucas":                 _search_ucas,
    "alumni":               _search_alumni,
    "finance":              _search_finance,
    "library":              _search_library,
    "documents":            _search_documents,
    "audit_logs":           _search_audit_logs,
}


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

# Fields masked when redaction is on (item 31). Label/id are kept; the
# free-text detail (which carries the sensitive content) is masked.
SENSITIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "safeguarding":   ("summary", "description", "notes"),
    "accommodations": ("description", "notes"),
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


def _build_filter_context(filters: dict[str, Any],
                          opts: QueryOptions) -> FilterContext:
    """Translate raw filter dict into an effective FilterContext."""
    ctx = FilterContext(
        role=(filters.get("role") or None),
        actor=(filters.get("actor") or filters.get("owned_by_staff") or None),
        include_archived=bool(filters.get("include_archived", False)),
        postcode_prefix=(filters.get("postcode_prefix") or "").strip()
                         or None,
        today=opts.today,
        redact=bool(filters.get("redact", False)),
        break_glass_reason=(filters.get("break_glass") or "").strip() or None,
    )

    # 32. Per-scope role ACL. Break-glass (item 35) bypasses the drop but is
    # audited in run_search; otherwise gated scopes are silently dropped.
    for scope, allowed in SCOPE_ACL.items():
        if ctx.role and ctx.role not in allowed and not ctx.break_glass_reason:
            ctx.drop_scopes.add(scope)

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
            alumni as al,
        )
        wanted: set[int] = set()
        first = True
        for t in tags:
            try:
                ids = {a.alumni_id for a in al.list_alumni(tag=t)}
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
        if st in _ARCHIVED_STATUSES:
            return False
    # Student-id-keyed scopes use doc["name"] for the student_id.
    if ctx.allowed_student_ids is not None and scope in _STUDENT_KEYED_SCOPES:
        sid = str(doc.get("name") or "").strip()
        if sid and sid not in ctx.allowed_student_ids:
            return False
    # Alumni tag set
    if scope == "alumni" and ctx.allowed_alumni_ids is not None:
        try:
            aid = int(str(doc.get("id") or "0"))
        except ValueError:
            aid = 0
        if aid not in ctx.allowed_alumni_ids:
            return False
    # Postcode prefix — only alumni has anything resembling an address
    if ctx.postcode_prefix and scope == "alumni":
        addr = str(doc.get("location") or "")
        if ctx.postcode_prefix.upper() not in addr.upper():
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


# ── Search audit trail (item 33) ──────────────────────────────────

@dataclass
class SearchAuditEntry:
    audit_id: int
    ts: str
    actor: str | None
    role: str | None
    query: str
    scopes: list[str]
    sensitive_scopes: list[str]
    break_glass: bool
    reason: str | None


def _record_search_audit(actor: str | None, role: str | None, query: str,
                         scopes: list[str], sensitive: list[str],
                         break_glass: bool, reason: str | None) -> None:
    ts = _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    try:
        with _connect() as conn:
            conn.execute(
                """INSERT INTO search_audit
                       (ts, actor, role, query, scopes, sensitive_scopes,
                        break_glass, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (ts, actor, role, query, ",".join(scopes),
                 ",".join(sensitive), 1 if break_glass else 0, reason))
            conn.commit()
    except Exception:
        logger.exception("search audit write failed")


def list_search_audit(*, limit: int = 100, actor: str | None = None,
                      sensitive_only: bool = False
                      ) -> list[SearchAuditEntry]:
    init_db()
    sql = "SELECT * FROM search_audit"
    clauses: list[str] = []
    args: list[Any] = []
    if actor:
        clauses.append("actor = ?")
        args.append(actor)
    if sensitive_only:
        clauses.append("sensitive_scopes <> ''")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY audit_id DESC LIMIT ?"
    args.append(int(limit))
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [SearchAuditEntry(
        audit_id=r["audit_id"], ts=r["ts"], actor=r["actor"],
        role=r["role"], query=r["query"],
        scopes=[s for s in (r["scopes"] or "").split(",") if s],
        sensitive_scopes=[s for s in (r["sensitive_scopes"]
                                       or "").split(",") if s],
        break_glass=bool(r["break_glass"]), reason=r["reason"])
            for r in rows]


# Scopes whose docs use `doc["name"]` to mean "student_id" (set by the
# adapters above). Filters that constrain by student id apply to these.
_STUDENT_KEYED_SCOPES: frozenset[str] = frozenset({
    "students", "behaviour", "absence_requests", "attendance_concerns",
    "accommodations", "safeguarding", "predicted_grades",
    "progress_reviews", "ucas", "finance",
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


# ── Pinning (item 36) ─────────────────────────────────────────────

def pin_result(actor: str, scope: str, entity_id: str,
               label: str = "", note: str | None = None) -> PinnedResult:
    init_db()
    if scope not in ALL_SCOPES:
        raise ValidationError(f"Unknown scope {scope!r}")
    actor = (actor or "").strip()
    if not actor:
        raise ValidationError("actor is required")
    entity_id = (entity_id or "").strip()
    if not entity_id:
        raise ValidationError("entity_id is required")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO pinned_results
                   (actor, scope, entity_id, label, note, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT (actor, scope, entity_id) DO UPDATE
                   SET label = excluded.label,
                       note  = excluded.note""",
            (actor, scope, entity_id, label or "", note),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = _get_pin(new_id) or _get_pin_for(actor, scope, entity_id)
    assert out is not None
    return out


def unpin_result(actor: str, scope: str, entity_id: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM pinned_results "
            "WHERE actor = ? AND scope = ? AND entity_id = ?",
            (actor, scope, entity_id),
        )
        conn.commit()
        return cur.rowcount > 0


def list_pinned(actor: str | None = None) -> list[PinnedResult]:
    init_db()
    with _connect() as conn:
        if actor is None:
            rows = conn.execute(
                "SELECT * FROM pinned_results "
                "ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pinned_results WHERE actor = ? "
                "ORDER BY created_at DESC", (actor,)).fetchall()
    return [_pin_from_row(r) for r in rows]


def _pin_from_row(r: sqlite3.Row) -> PinnedResult:
    return PinnedResult(
        pin_id=r["pin_id"], actor=r["actor"], scope=r["scope"],
        entity_id=r["entity_id"], label=r["label"] or "",
        note=r["note"], created_at=r["created_at"],
    )


def _get_pin(pin_id: int) -> PinnedResult | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM pinned_results WHERE pin_id = ?",
            (pin_id,)).fetchone()
        return _pin_from_row(r) if r else None


def _get_pin_for(actor: str, scope: str,
                 entity_id: str) -> PinnedResult | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM pinned_results "
            "WHERE actor = ? AND scope = ? AND entity_id = ?",
            (actor, scope, entity_id)).fetchone()
        return _pin_from_row(r) if r else None


# ── Clustering (item 37) ──────────────────────────────────────────

def _cluster_by_student(hits: list[Hit]) -> list[Hit]:
    """Group same-student hits into one cluster head per student.

    Cluster head's ``extra['cluster_children']`` lists the absorbed
    hits. Non-student hits pass through unchanged.
    """
    buckets: dict[tuple[str, str], list[Hit]] = {}
    order: list[tuple[str, str] | Hit] = []
    for h in hits:
        sid = ""
        if h.scope in _STUDENT_KEYED_SCOPES:
            sid = h.extra.get("__sid") or _extract_student_id(h)
        if sid:
            key = ("student", sid)
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(h)
        else:
            order.append(h)
    out: list[Hit] = []
    for item in order:
        if isinstance(item, tuple):
            group = buckets[item]
            head = group[0]
            if len(group) > 1:
                head.cluster_count = len(group)
                head.extra = dict(head.extra)
                head.extra["cluster_children"] = group[1:]
                head.extra["cluster_scopes"] = sorted(
                    {g.scope for g in group})
            out.append(head)
        else:
            out.append(item)
    return out


_STUDENT_ID_RE = re.compile(r"(S\d{3,}|[A-Z]\d{4,})")


def _extract_student_id(h: Hit) -> str:
    """Best-effort: pull a student id out of label / entity_id."""
    for src in (h.entity_id, h.label):
        m = _STUDENT_ID_RE.search(src or "")
        if m:
            return m.group(1)
    return ""


# ══════════════════════════════════════════════════════════════════
# Saved searches — ACL, folders (items 38, 40)
# ══════════════════════════════════════════════════════════════════

VALID_VISIBILITIES: tuple[str, ...] = ("private", "role", "public")


def _saved_acl_allows(s: SavedSearch, actor: str | None,
                      role: str | None) -> bool:
    if s.visibility == "public":
        return True
    if s.visibility == "private":
        return actor is not None and actor == s.owner_actor
    if s.visibility == "role":
        if not role:
            return False
        return role in (s.role_acl or [])
    return False


# ══════════════════════════════════════════════════════════════════
# Scheduled searches (item 39)
# ══════════════════════════════════════════════════════════════════

def _sched_from_row(r: sqlite3.Row) -> ScheduledSearch:
    keys = r.keys()
    return ScheduledSearch(
        schedule_id=r["schedule_id"], saved_id=r["saved_id"],
        cron=r["cron"] or "daily", notify_actor=r["notify_actor"],
        last_run_at=r["last_run_at"], last_count=r["last_count"],
        new_since_last=r["new_since_last"],
        enabled=bool(r["enabled"]), created_at=r["created_at"],
        threshold=(r["threshold"] if "threshold" in keys else 0) or 0,
    )


def schedule_saved_search(saved_id: int, *,
                          cron: str = "daily",
                          notify_actor: str | None = None,
                          enabled: bool = True,
                          threshold: int = 0) -> ScheduledSearch:
    init_db()
    if get_saved_search(saved_id) is None:
        raise ValidationError(f"No saved search #{saved_id}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO scheduled_searches
                   (saved_id, cron, notify_actor, enabled, threshold,
                    created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (saved_id, cron or "daily", notify_actor, 1 if enabled else 0,
             int(threshold)),
        )
        conn.commit()
        sid = cur.lastrowid
        r = conn.execute(
            "SELECT * FROM scheduled_searches WHERE schedule_id = ?",
            (sid,)).fetchone()
    return _sched_from_row(r)


def list_scheduled_searches(*,
                             enabled_only: bool = False
                             ) -> list[ScheduledSearch]:
    init_db()
    sql = "SELECT * FROM scheduled_searches"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY schedule_id"
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [_sched_from_row(r) for r in rows]


def delete_scheduled_search(schedule_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM scheduled_searches WHERE schedule_id = ?",
            (schedule_id,))
        conn.commit()
        return cur.rowcount > 0


def run_scheduled_search(schedule_id: int) -> SearchResults:
    """Run one scheduled saved-search and record delta count."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM scheduled_searches WHERE schedule_id = ?",
            (schedule_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No scheduled search #{schedule_id}")
        sched = _sched_from_row(r)
    if not sched.enabled:
        raise ValidationError("Scheduled search is disabled")
    saved = get_saved_search(sched.saved_id)
    if saved is None:
        raise ValidationError(f"Saved search #{sched.saved_id} missing")
    results = run_search(
        saved.query, scopes=saved.scopes, filters=saved.filters,
        record_history=True, actor=sched.notify_actor,
    )
    new_since = max(0, results.total - sched.last_count)
    with _connect() as conn:
        conn.execute(
            """UPDATE scheduled_searches SET
                   last_run_at = datetime('now'),
                   last_count = ?, new_since_last = ?, last_keys_json = ?
               WHERE schedule_id = ?""",
            (results.total, new_since,
             json.dumps(_result_keys(results)), schedule_id),
        )
        conn.commit()
    return results


def _result_keys(results: SearchResults) -> list[str]:
    return [f"{h.scope}#{h.entity_id}" for h in results.all_hits()]


@dataclass
class ScheduleDelta:
    schedule_id: int
    total: int
    added: list[str]
    removed: list[str]


def schedule_delta(schedule_id: int) -> ScheduleDelta:
    """Run a scheduled saved-search now and report which result keys are
    new or gone since its last recorded run — without updating it (item 28)."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM scheduled_searches WHERE schedule_id = ?",
            (schedule_id,)).fetchone()
    if r is None:
        raise ValidationError(f"No scheduled search #{schedule_id}")
    sched = _sched_from_row(r)
    saved = get_saved_search(sched.saved_id)
    if saved is None:
        raise ValidationError(f"Saved search #{sched.saved_id} missing")
    results = run_search(saved.query, scopes=saved.scopes,
                         filters=saved.filters, record_history=False)
    prev_raw = r["last_keys_json"] if "last_keys_json" in r.keys() else None
    try:
        prev = set(json.loads(prev_raw)) if prev_raw else set()
    except (TypeError, ValueError):
        prev = set()
    now_keys = set(_result_keys(results))
    return ScheduleDelta(
        schedule_id=schedule_id, total=results.total,
        added=sorted(now_keys - prev), removed=sorted(prev - now_keys))


# ══════════════════════════════════════════════════════════════════
# FTS5 mirror index (item 47)
# ══════════════════════════════════════════════════════════════════

_FTS_AVAILABLE: bool | None = None
_FTS_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS search_index_fts "
    "USING fts5(scope UNINDEXED, entity_id UNINDEXED, text, "
    "tokenize='porter unicode61')")


def _fts_available() -> bool:
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is not None:
        return _FTS_AVAILABLE
    try:
        with _connect() as conn:
            conn.execute(_FTS_DDL)
            conn.commit()
        _FTS_AVAILABLE = True
    except sqlite3.OperationalError:
        logger.warning("SQLite FTS5 not available — falling back to LIKE")
        _FTS_AVAILABLE = False
    return _FTS_AVAILABLE


def _ensure_fts_index() -> None:
    # Create the virtual table idempotently in the *current* DB. The
    # availability flag is cached process-wide, but the table itself lives
    # per-file — so always (re)issue the DDL when FTS is available.
    if _fts_available():
        try:
            with _connect() as conn:
                conn.execute(_FTS_DDL)
                conn.commit()
        except sqlite3.OperationalError:
            pass


def _doc_to_index_text(doc: dict[str, Any]) -> str:
    parts = []
    for k, v in doc.items():
        if k.startswith("_") and k != "_all":
            continue
        if v:
            parts.append(str(v))
    return " ".join(parts)


@dataclass
class IndexStatus:
    scope: str
    indexed_rows: int
    current_rows: int
    last_refresh: str | None
    stale: bool


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
    except sqlite3.OperationalError:
        return None


# ══════════════════════════════════════════════════════════════════
# Cache (item 48)
# ══════════════════════════════════════════════════════════════════

_CACHE: dict[tuple, tuple[float, SearchResults]] = {}
CACHE_TTL_SECONDS: float = 30.0
_CACHE_MAX_ENTRIES: int = 64
_CACHE_HITS: int = 0
_CACHE_MISSES: int = 0


def _cache_key(query: str, scopes: list[str],
               filters: dict[str, Any], opts: QueryOptions,
               actor: str | None, flags: tuple) -> tuple:
    return (
        query, tuple(scopes), repr(sorted(filters.items())),
        (opts.fuzzy_default, opts.use_stemming, opts.ignore_stopwords,
         opts.expand_synonyms,
         opts.today.isoformat() if opts.today else None),
        actor or "", flags,
    )


def _cache_get(key: tuple) -> SearchResults | None:
    global _CACHE_HITS, _CACHE_MISSES
    rec = _CACHE.get(key)
    if rec is None:
        _CACHE_MISSES += 1
        return None
    ts, r = rec
    if _now() - ts > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        _CACHE_MISSES += 1
        return None
    _CACHE_HITS += 1
    return r


def _cache_put(key: tuple, r: SearchResults) -> None:
    if len(_CACHE) >= _CACHE_MAX_ENTRIES:
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _CACHE.pop(oldest, None)
    _CACHE[key] = (_now(), r)


def clear_cache() -> None:
    global _CACHE_HITS, _CACHE_MISSES
    _CACHE.clear()
    _CACHE_HITS = 0
    _CACHE_MISSES = 0


def cache_stats() -> dict[str, Any]:
    """Live session cache counters (item 43)."""
    total = _CACHE_HITS + _CACHE_MISSES
    return {
        "entries": len(_CACHE),
        "max_entries": _CACHE_MAX_ENTRIES,
        "ttl_seconds": CACHE_TTL_SECONDS,
        "hits": _CACHE_HITS,
        "misses": _CACHE_MISSES,
        "hit_rate": round(_CACHE_HITS / total, 3) if total else 0.0,
    }


# ══════════════════════════════════════════════════════════════════
# Data quality — duplicates & gaps (items 44, 45)
# ══════════════════════════════════════════════════════════════════

@dataclass
class DuplicateGroup:
    reason: str               # email | surname+dob | name
    key: str
    student_ids: list[str]


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


@dataclass
class DataGap:
    scope: str
    entity_id: str
    label: str
    missing: list[str]


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


@dataclass
class Facet:
    field: str
    values: list[tuple[str, int]]


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


@dataclass
class TrendPoint:
    ts: str
    count: int


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


def _now() -> float:
    import time as _t
    return _t.monotonic()


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
# Telemetry (item 50)
# ══════════════════════════════════════════════════════════════════

@dataclass
class TelemetrySummary:
    total_searches: int
    zero_result: int
    top_queries: list[tuple[str, int]]
    slowest_scopes_ms: dict[str, float]
    zero_result_queries: list[str]


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
# Subscriptions (item 41)
# ══════════════════════════════════════════════════════════════════

def poll_subscriptions(*,
                       only_actor: str | None = None
                       ) -> list[ScheduledSearch]:
    """Run all enabled scheduled searches and enqueue a notification row
    for each that returned more hits than its last_count.

    Returns the schedules that emitted a notification this poll. If the
    sixth-form notifications module is available, an in-app
    notification is also dispatched; otherwise the row in
    ``subscription_notifications`` is the queue.
    """
    init_db()
    fired: list[ScheduledSearch] = []
    for sched in list_scheduled_searches(enabled_only=True):
        if only_actor and sched.notify_actor != only_actor:
            continue
        if not sched.notify_actor:
            continue
        try:
            results = run_scheduled_search(sched.schedule_id)
        except ValidationError:
            continue
        if results.total <= sched.last_count:
            continue
        # Threshold alert (item 26): suppress until the running total meets
        # the configured floor (e.g. only ping once ≥5 open concerns).
        if sched.threshold and results.total < sched.threshold:
            continue
        delta = results.total - sched.last_count
        sample = results.ranked_hits[0] if results.ranked_hits else None
        with _connect() as conn:
            conn.execute(
                """INSERT INTO subscription_notifications
                       (schedule_id, actor, delta, total,
                        sample_scope, sample_label, sample_entity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sched.schedule_id, sched.notify_actor, delta,
                 results.total,
                 sample.scope if sample else None,
                 sample.label if sample else None,
                 sample.entity_id if sample else None),
            )
            conn.commit()
        _try_push_notification(sched, delta, sample)
        fired.append(sched)
    return fired


def _try_push_notification(sched: ScheduledSearch, delta: int,
                           sample: Hit | None) -> None:
    """Best-effort dispatch to the in-app notifications module."""
    try:
        from education_system.systems.sixth_form.domain.operations.communications.notifications import (
            notifications as _notif,
        )
        title = f"Search '{sched.cron}' has {delta} new hit(s)"
        body = (f"{sample.label} ({sample.scope})"
                if sample else "")
        for fn in ("create_notification", "create", "notify"):
            f = getattr(_notif, fn, None)
            if callable(f):
                try:
                    f({
                        "recipient": sched.notify_actor,
                        "title": title, "body": body,
                        "source": "advanced_search",
                    })
                    return
                except TypeError:
                    pass
    except Exception:
        pass


def list_subscription_notifications(actor: str, *,
                                    unread_only: bool = False,
                                    include_snoozed: bool = False
                                    ) -> list[dict[str, Any]]:
    init_db()
    sql = ("SELECT * FROM subscription_notifications WHERE actor = ?")
    args: list[Any] = [actor]
    if unread_only:
        sql += " AND read_at IS NULL"
    if not include_snoozed:
        # Hide rows snoozed into the future (item 30).
        sql += (" AND (snoozed_until IS NULL "
                "OR snoozed_until <= datetime('now'))")
    sql += " ORDER BY notif_id DESC LIMIT 100"
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def mark_notification_read(notif_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE subscription_notifications SET read_at = "
            "datetime('now') WHERE notif_id = ? AND read_at IS NULL",
            (notif_id,))
        conn.commit()
    return cur.rowcount > 0


def snooze_notification(notif_id: int, *, hours: int = 24) -> bool:
    """Hide a subscription notification until ``hours`` from now (item 30)."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE subscription_notifications "
            "SET snoozed_until = datetime('now', ?) WHERE notif_id = ?",
            (f"+{int(hours)} hours", notif_id))
        conn.commit()
    return cur.rowcount > 0


# ── Digests (item 27) ─────────────────────────────────────────────

@dataclass
class DigestLine:
    schedule_id: int
    saved_name: str
    total: int
    new_since_last: int
    last_run_at: str | None


@dataclass
class Digest:
    actor: str | None
    lines: list[DigestLine]
    total_new: int


def build_digest(actor: str | None = None) -> Digest:
    """Roll up every scheduled search (optionally for one actor) into a
    single summary of current totals and deltas since last run."""
    init_db()
    lines: list[DigestLine] = []
    total_new = 0
    for sched in list_scheduled_searches():
        if actor and sched.notify_actor != actor:
            continue
        saved = get_saved_search(sched.saved_id)
        name = saved.name if saved else f"#{sched.saved_id}"
        lines.append(DigestLine(
            schedule_id=sched.schedule_id, saved_name=name,
            total=sched.last_count, new_since_last=sched.new_since_last,
            last_run_at=sched.last_run_at))
        total_new += sched.new_since_last
    lines.sort(key=lambda x: -x.new_since_last)
    return Digest(actor=actor, lines=lines, total_new=total_new)


# ══════════════════════════════════════════════════════════════════
# Dashboards — bundles of saved searches (item 29)
# ══════════════════════════════════════════════════════════════════

@dataclass
class Dashboard:
    dashboard_id: int
    name: str
    owner_actor: str | None
    notes: str | None
    created_at: str
    saved_ids: list[int] = field(default_factory=list)


@dataclass
class DashboardPanel:
    saved_id: int
    name: str
    query: str
    total: int


def _resolve_dashboard_id(name_or_id: str | int) -> int | None:
    with _connect() as conn:
        if isinstance(name_or_id, int) or str(name_or_id).isdigit():
            r = conn.execute(
                "SELECT dashboard_id FROM dashboards WHERE dashboard_id = ?",
                (int(name_or_id),)).fetchone()
        else:
            r = conn.execute(
                "SELECT dashboard_id FROM dashboards WHERE name = ?",
                (str(name_or_id).strip(),)).fetchone()
    return r["dashboard_id"] if r else None


def create_dashboard(name: str, saved_ids: list[int] | None = None, *,
                     owner_actor: str | None = None,
                     notes: str | None = None) -> Dashboard:
    init_db()
    name = (name or "").strip()
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Dashboard name must be 1–48 chars (letters, digits, "
            "space, _ . / -)")
    ids = [int(s) for s in (saved_ids or [])]
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM dashboards WHERE name = ?",
                        (name,)).fetchone():
            raise ValidationError(f"A dashboard named {name!r} already exists")
        cur = conn.execute(
            "INSERT INTO dashboards (name, owner_actor, notes) "
            "VALUES (?, ?, ?)", (name, owner_actor or None, notes or None))
        did = cur.lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO dashboard_items "
            "(dashboard_id, saved_id, position) VALUES (?, ?, ?)",
            [(did, sid, i) for i, sid in enumerate(ids)])
        conn.commit()
    out = get_dashboard(did)
    assert out is not None
    return out


def get_dashboard(dashboard_id: int) -> Dashboard | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM dashboards WHERE dashboard_id = ?",
                         (dashboard_id,)).fetchone()
        if r is None:
            return None
        ids = [row["saved_id"] for row in conn.execute(
            "SELECT saved_id FROM dashboard_items WHERE dashboard_id = ? "
            "ORDER BY position, saved_id", (dashboard_id,)).fetchall()]
    return Dashboard(
        dashboard_id=r["dashboard_id"], name=r["name"],
        owner_actor=r["owner_actor"], notes=r["notes"],
        created_at=r["created_at"], saved_ids=ids)


def list_dashboards() -> list[Dashboard]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT dashboard_id FROM dashboards ORDER BY name").fetchall()
    return [d for d in (get_dashboard(r["dashboard_id"]) for r in rows)
            if d is not None]


def add_to_dashboard(name_or_id: str | int, saved_ids: list[int]) -> int:
    init_db()
    did = _resolve_dashboard_id(name_or_id)
    if did is None:
        raise ValidationError(f"No dashboard {name_or_id!r}")
    with _connect() as conn:
        start = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS p "
            "FROM dashboard_items WHERE dashboard_id = ?", (did,)).fetchone()["p"]
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM dashboard_items WHERE dashboard_id = ?",
            (did,)).fetchone()["n"]
        conn.executemany(
            "INSERT OR IGNORE INTO dashboard_items "
            "(dashboard_id, saved_id, position) VALUES (?, ?, ?)",
            [(did, int(sid), start + i) for i, sid in enumerate(saved_ids)])
        after = conn.execute(
            "SELECT COUNT(*) AS n FROM dashboard_items WHERE dashboard_id = ?",
            (did,)).fetchone()["n"]
        conn.commit()
    return after - before


def delete_dashboard(name_or_id: str | int) -> bool:
    init_db()
    did = _resolve_dashboard_id(name_or_id)
    if did is None:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM dashboard_items WHERE dashboard_id = ?",
                     (did,))
        cur = conn.execute("DELETE FROM dashboards WHERE dashboard_id = ?",
                           (did,))
        conn.commit()
    return cur.rowcount > 0


def run_dashboard(name_or_id: str | int, *,
                  actor: str | None = None,
                  role: str | None = None) -> list[DashboardPanel]:
    """Run every saved search in a dashboard and return per-panel counts."""
    init_db()
    did = _resolve_dashboard_id(name_or_id)
    if did is None:
        raise ValidationError(f"No dashboard {name_or_id!r}")
    dash = get_dashboard(did)
    assert dash is not None
    out: list[DashboardPanel] = []
    for sid in dash.saved_ids:
        saved = get_saved_search(sid)
        if saved is None:
            continue
        filters = dict(saved.filters or {})
        if role:
            filters.setdefault("role", role)
        try:
            res = run_search(saved.query, scopes=saved.scopes,
                             filters=filters, actor=actor,
                             record_history=False)
            total = res.total
        except ValidationError:
            total = -1
        out.append(DashboardPanel(saved_id=sid, name=saved.name,
                                  query=saved.query, total=total))
    return out


# ══════════════════════════════════════════════════════════════════
# Export / import saved searches (item 42)
# ══════════════════════════════════════════════════════════════════

EXPORT_FORMAT_VERSION = 1


def export_saved_searches(*,
                          include_schedules: bool = True) -> str:
    """Serialize all saved searches (and optionally their schedules)
    to a JSON string suitable for backup or migration."""
    init_db()
    items = []
    for s in list_saved_searches():
        items.append({
            "name": s.name, "query": s.query, "scopes": s.scopes,
            "filters": s.filters, "notes": s.notes,
            "owner_actor": s.owner_actor, "visibility": s.visibility,
            "role_acl": s.role_acl, "folder": s.folder, "tags": s.tags,
        })
    schedules = []
    if include_schedules:
        # Schedule rows keyed by saved-search name for portability
        by_id = {s.saved_id: s.name for s in list_saved_searches()}
        for sch in list_scheduled_searches():
            if sch.saved_id not in by_id:
                continue
            schedules.append({
                "saved_name": by_id[sch.saved_id],
                "cron": sch.cron, "notify_actor": sch.notify_actor,
                "enabled": sch.enabled,
            })
    return json.dumps(
        {"version": EXPORT_FORMAT_VERSION,
         "saved_searches": items, "schedules": schedules},
        indent=2, ensure_ascii=False)


def import_saved_searches(json_text: str, *,
                          overwrite: bool = False) -> dict[str, int]:
    """Load saved searches from a JSON export. Returns counts."""
    init_db()
    try:
        data = json.loads(json_text)
    except ValueError as e:
        raise ValidationError(f"Invalid JSON: {e}") from None
    if not isinstance(data, dict):
        raise ValidationError("Export payload must be a JSON object")
    items = data.get("saved_searches") or []
    created = 0
    updated = 0
    skipped = 0
    saved_ids_by_name: dict[str, int] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        name = (raw.get("name") or "").strip()
        if not name:
            skipped += 1
            continue
        existing = get_saved_search_by_name(name)
        if existing and not overwrite:
            saved_ids_by_name[name] = existing.saved_id
            skipped += 1
            continue
        try:
            if existing and overwrite:
                update_saved_search(existing.saved_id, raw)
                saved_ids_by_name[name] = existing.saved_id
                updated += 1
            else:
                s = create_saved_search(raw)
                saved_ids_by_name[name] = s.saved_id
                created += 1
        except ValidationError:
            skipped += 1
    sched_created = 0
    for sch in (data.get("schedules") or []):
        sname = (sch.get("saved_name") or "").strip()
        sid = saved_ids_by_name.get(sname)
        if not sid:
            continue
        try:
            schedule_saved_search(
                sid, cron=sch.get("cron") or "daily",
                notify_actor=sch.get("notify_actor"),
                enabled=bool(sch.get("enabled", True)))
            sched_created += 1
        except ValidationError:
            pass
    return {"created": created, "updated": updated,
            "skipped": skipped, "schedules": sched_created}


# ══════════════════════════════════════════════════════════════════
# Suggestions (item 43)
# ══════════════════════════════════════════════════════════════════

def suggest(prefix: str, *, limit: int = 8,
            actor: str | None = None) -> list[str]:
    """Type-ahead suggestions mixed from saved-search names, recent
    history, and a sampling of entity labels."""
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
    for h in list_history(limit=40):
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
        except sqlite3.OperationalError:
            pass
    return out[:limit]


# ══════════════════════════════════════════════════════════════════
# Drill-through + bulk export (items 45, 46)
# ══════════════════════════════════════════════════════════════════

# Scope → callable to open an entity in a GUI editor. GUI code calls
# ``register_open_handler('students', fn)`` at import time; the
# advanced-search view uses ``open_hit`` to dispatch.
OPEN_HANDLERS: dict[str, Callable[[Hit], Any]] = {}


def register_open_handler(scope: str,
                          fn: Callable[[Hit], Any]) -> None:
    if scope not in ALL_SCOPES:
        raise ValidationError(f"Unknown scope {scope!r}")
    OPEN_HANDLERS[scope] = fn


def open_hit(hit: Hit) -> Any:
    """Invoke the GUI handler registered for the hit's scope. Returns
    None when no handler is wired up — caller can show a default
    'no editor' message."""
    fn = OPEN_HANDLERS.get(hit.scope)
    if fn is None:
        logger.debug("open_hit: no handler for scope %s", hit.scope)
        return None
    try:
        return fn(hit)
    except Exception:
        logger.exception("open_hit handler for %s failed", hit.scope)
        return None


def export_results_csv(results: SearchResults) -> str:
    """Return a CSV string for the result set (one row per hit).

    Columns: scope, entity_id, score, label, sublabel, matched_fields."""
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["scope", "entity_id", "score", "label", "sublabel",
                "matched_fields"])
    seq = results.ranked_hits or [
        h for hits in results.hits_by_scope.values() for h in hits]
    for h in seq:
        w.writerow([
            h.scope, h.entity_id, f"{h.score:.4f}",
            h.label, h.sublabel,
            "|".join(h.matched_fields),
        ])
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════
# Multi-format export + column selection (item 36)
# ══════════════════════════════════════════════════════════════════

EXPORT_TEXT_FORMATS: tuple[str, ...] = ("csv", "tsv", "json", "html", "md")
EXPORT_FILE_FORMATS: tuple[str, ...] = EXPORT_TEXT_FORMATS + ("xlsx", "pdf")
EXPORT_COLUMNS: tuple[str, ...] = (
    "scope", "entity_id", "score", "label", "sublabel", "matched_fields")


def _export_rows(results: SearchResults,
                 columns: list[str] | None) -> tuple[list[str], list[list[str]]]:
    cols = [c for c in (columns or EXPORT_COLUMNS) if c in EXPORT_COLUMNS] \
        or list(EXPORT_COLUMNS)
    seq = results.ranked_hits or results.all_hits()

    def cell(h: Hit, c: str) -> str:
        if c == "score":
            return f"{h.score:.4f}"
        if c == "matched_fields":
            return "|".join(h.matched_fields)
        return str(getattr(h, c, "") or "")

    return cols, [[cell(h, c) for c in cols] for h in seq]


def export_results(results: SearchResults, *,
                   fmt: str = "csv",
                   columns: list[str] | None = None) -> str:
    """Serialise a result set to a text format (csv/tsv/json/html/md)."""
    fmt = (fmt or "csv").lower()
    cols, rows = _export_rows(results, columns)
    if fmt == "json":
        return json.dumps([dict(zip(cols, r)) for r in rows],
                          indent=2, ensure_ascii=False)
    if fmt in ("csv", "tsv"):
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        w = _csv.writer(buf, delimiter="\t" if fmt == "tsv" else ",")
        w.writerow(cols)
        w.writerows(rows)
        return buf.getvalue()
    if fmt == "md":
        out = ["| " + " | ".join(cols) + " |",
               "| " + " | ".join("---" for _ in cols) + " |"]
        for r in rows:
            out.append("| " + " | ".join(
                x.replace("|", "\\|").replace("\n", " ") for x in r) + " |")
        return "\n".join(out)
    if fmt in ("html", "pdf"):
        return _results_html(results, cols, rows)
    raise ValidationError(
        f"Unknown export format {fmt!r}. One of: "
        f"{', '.join(EXPORT_FILE_FORMATS)}")


def _results_html(results: SearchResults, cols: list[str],
                  rows: list[list[str]]) -> str:
    import html as _h
    th = "".join(f"<th>{_h.escape(c)}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{_h.escape(x)}</td>" for x in r) + "</tr>"
        for r in rows)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>body{font-family:sans-serif;margin:24px}"
        "table{border-collapse:collapse}"
        "td,th{border:1px solid #999;padding:4px 8px;font-size:12px}"
        "th{background:#eef}</style></head><body>"
        f"<h2>Advanced search — {_h.escape(results.query or '(all)')}</h2>"
        f"<p>{results.total} result(s)</p>"
        f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"
        "</body></html>")


def _path_fmt(path: str) -> str | None:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext if ext in EXPORT_FILE_FORMATS else None


def export_results_file(results: SearchResults, path: str, *,
                        fmt: str | None = None,
                        columns: list[str] | None = None) -> str:
    """Write a result set to ``path`` in any supported format. xlsx/pdf are
    produced when openpyxl/reportlab are installed (else raises)."""
    fmt = (fmt or _path_fmt(path) or "csv").lower()
    if fmt == "xlsx":
        _write_xlsx(results, path, columns)
    elif fmt == "pdf":
        _write_pdf(results, path, columns)
    else:
        text = export_results(results, fmt=fmt, columns=columns)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return path


def _write_xlsx(results: SearchResults, path: str,
                columns: list[str] | None) -> None:
    try:
        from openpyxl import Workbook
    except ImportError:
        raise ValidationError(
            "xlsx export needs openpyxl (pip install openpyxl)") from None
    cols, rows = _export_rows(results, columns)
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(cols)
    for r in rows:
        ws.append(r)
    wb.save(path)


def _write_pdf(results: SearchResults, path: str,
               columns: list[str] | None) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError:
        raise ValidationError(
            "pdf export needs reportlab (pip install reportlab)") from None
    cols, rows = _export_rows(results, columns)
    styles = getSampleStyleSheet()
    data = [cols] + [[(x[:58] + "…") if len(x) > 58 else x for x in r]
                     for r in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    doc = SimpleDocTemplate(path, pagesize=landscape(A4))
    doc.build([
        Paragraph(f"Advanced search — {results.query or '(all)'}",
                  styles["Title"]),
        Spacer(1, 8), table])


# ══════════════════════════════════════════════════════════════════
# Mail-merge, cohort export, contact sheet (items 37–39)
# ══════════════════════════════════════════════════════════════════

def mailmerge_results(results: SearchResults, *,
                      subject: str, body: str,
                      sender_staff_id: str | None = None,
                      send: bool = False) -> dict[str, Any]:
    """Create (or send) one message per student in the result set via the
    messaging module's bulk_send (item 37)."""
    ids = _student_ids_from_results(results)
    if not ids:
        raise ValidationError("No students in the results to message")
    if not (subject or "").strip():
        raise ValidationError("subject is required")
    from education_system.systems.sixth_form.domain.operations.communications.messages import (
        messages as msg,
    )
    res = msg.bulk_send(
        subject=subject, body=body, student_ids=ids,
        sender_staff_id=sender_staff_id,
        status="Sent" if send else "Draft")
    return {
        "recipients": len(ids),
        "created": len(getattr(res, "created", []) or []),
        "failed": len(getattr(res, "failed", []) or []),
        "thread_id": getattr(res, "thread_id", None),
        "status": "Sent" if send else "Draft",
    }


def export_cohort(name_or_id: str | int, *, fmt: str = "json") -> str:
    """Serialise a cohort (with student names/emails) for hand-off to the
    reports/UCAS/messaging modules (item 38)."""
    cid = _resolve_cohort_id(name_or_id)
    if cid is None:
        raise ValidationError(f"No cohort {name_or_id!r}")
    c = get_cohort(cid)
    assert c is not None
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    students = []
    for sid in c.members:
        s = sm.get_student(sid)
        students.append({
            "student_id": sid,
            "full_name": s.full_name if s else None,
            "email": s.email if s else None,
        })
    fmt = (fmt or "json").lower()
    if fmt == "json":
        return json.dumps(
            {"cohort": c.name, "notes": c.notes, "count": c.member_count,
             "students": students}, indent=2, ensure_ascii=False)
    if fmt in ("csv", "tsv"):
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        w = _csv.writer(buf, delimiter="\t" if fmt == "tsv" else ",")
        w.writerow(["student_id", "full_name", "email"])
        for st in students:
            w.writerow([st["student_id"], st["full_name"] or "",
                        st["email"] or ""])
        return buf.getvalue()
    raise ValidationError(f"Unknown cohort export format {fmt!r}")


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0].upper() for p in parts[:2]) or "?"


def contact_sheet(results: SearchResults, *, fmt: str = "html") -> str:
    """Printable contact sheet (one card per student) for a result set —
    no photo field exists, so initials stand in for an avatar (item 39)."""
    ids = _student_ids_from_results(results)
    idx = student_group_index()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    cards = []
    for sid in ids:
        s = sm.get_student(sid)
        if s is None:
            continue
        yr, tg = idx.get(sid, (None, None))
        cards.append({
            "id": sid, "name": s.full_name, "email": s.email or "",
            "phone": s.phone or "", "subjects": ", ".join(s.subjects or []),
            "year": yr, "tutor": tg, "initials": _initials(s.full_name),
        })
    if fmt == "text":
        lines = [f"Contact sheet — {len(cards)} student(s)", ""]
        for c in cards:
            lines += [
                f"{c['name']}  ({c['id']})",
                f"  {c['email']}  ·  {c['phone'] or '—'}",
                f"  {c['subjects'] or '—'}",
                f"  year {c['year'] or '—'} · tutor {c['tutor'] or '—'}",
                "",
            ]
        return "\n".join(lines)
    import html as _h
    cells = ""
    for c in cards:
        cells += (
            "<div class='card'>"
            f"<div class='av'>{_h.escape(c['initials'])}</div>"
            f"<div class='nm'>{_h.escape(c['name'])}</div>"
            f"<div class='id'>{_h.escape(c['id'])}</div>"
            f"<div>{_h.escape(c['email'])}</div>"
            f"<div>{_h.escape(c['phone'] or '—')}</div>"
            f"<div>{_h.escape(c['subjects'] or '—')}</div>"
            f"<div>year {c['year'] or '—'} · tutor "
            f"{_h.escape(str(c['tutor'] or '—'))}</div>"
            "</div>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "body{font-family:sans-serif;margin:18px}"
        ".grid{display:flex;flex-wrap:wrap;gap:10px}"
        ".card{border:1px solid #aaa;border-radius:8px;padding:10px;"
        "width:230px;font-size:12px}"
        ".av{width:42px;height:42px;border-radius:50%;background:#5577aa;"
        "color:#fff;display:flex;align-items:center;justify-content:center;"
        "font-weight:bold;margin-bottom:6px}"
        ".nm{font-weight:bold;font-size:14px}.id{color:#666}"
        "</style></head><body>"
        f"<h2>Contact sheet — {len(cards)} student(s)</h2>"
        f"<div class='grid'>{cells}</div></body></html>")


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

    # Student-level predicates — aggregates (13), has/missing joins (11),
    # cohort membership (12) → intersected per-student post-filter set.
    predicates = _collect_student_predicates(parsed)
    pred_students: set[str] | None = None
    if predicates:
        pred_students = _resolve_student_predicates(predicates, opts)

    ctx = _build_filter_context(filters, opts)
    active_scopes = [s for s in scopes_use if s not in ctx.drop_scopes]

    # Sensitive-access audit (items 33, 35): log whenever a role-gated scope
    # is actually searched, or accessed under break-glass.
    sensitive_active = [s for s in active_scopes if s in SCOPE_ACL]
    if sensitive_active and (actor or ctx.break_glass_reason):
        _record_search_audit(
            actor, ctx.role, raw_q, active_scopes, sensitive_active,
            bool(ctx.break_glass_reason), ctx.break_glass_reason)

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

    # FTS5 pre-filter (item 47) — only when query is simple
    fts_candidates = _fts_candidates(parsed, active_scopes) \
                     if filters.get("use_index", True) else None

    # Async fan-out (item 49) with per-scope timing
    raw_by_scope, elapsed_ms = _fanout(
        active_scopes, parsed, opts, filters,
        max_workers=int(filters.get("max_workers", 8)))

    hits_by_scope: dict[str, list[Hit]] = {}
    total = 0
    for scope in scopes_use:
        if scope in ctx.drop_scopes:
            hits_by_scope[scope] = []
            continue
        raw_hits = raw_by_scope.get(scope, [])
        if fts_candidates is not None and scope in fts_candidates:
            allow = fts_candidates[scope]
            if allow:
                raw_hits = [h for h in raw_hits if h.entity_id in allow]
        kept: list[Hit] = []
        for h, doc in _zip_hits_with_docs(raw_hits, scope, parsed, opts,
                                          ctx, filters):
            if not _ctx_allows(scope, doc, ctx):
                continue
            # Student-predicate post-filter (items 11–13): keep only
            # student-keyed rows whose student satisfies every predicate.
            if pred_students is not None:
                if scope not in _STUDENT_KEYED_SCOPES:
                    continue
                if _doc_student_id(scope, doc) not in pred_students:
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

    if record_history:
        try:
            _record_history(raw_q, scopes_use, actor, total,
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
    )
    if filters.get("use_cache", True):
        _cache_put(cache_key, out)
    return out


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


# ── History ───────────────────────────────────────────────────────

def _record_history(query: str, scopes: list[str],
                    actor: str | None, count: int,
                    *,
                    elapsed_ms: dict[str, float] | None = None,
                    result_counts: dict[str, int] | None = None,
                    ) -> None:
    ts = _dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO search_history
                   (ts, query, scopes, actor, result_count,
                    elapsed_ms_json, result_count_json, zero_result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, query, ",".join(scopes), actor or None, int(count),
             json.dumps(elapsed_ms) if elapsed_ms else None,
             json.dumps(result_counts) if result_counts else None,
             1 if int(count) == 0 else 0),
        )
        conn.execute(
            """DELETE FROM search_history
                WHERE history_id NOT IN (
                    SELECT history_id FROM search_history
                    ORDER BY ts DESC, history_id DESC
                    LIMIT ?
                )""",
            (MAX_HISTORY_ROWS,))
        conn.commit()


def list_history(limit: int = 20) -> list[HistoryEntry]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM search_history "
            "ORDER BY ts DESC, history_id DESC LIMIT ?",
            (int(limit),)).fetchall()
    out: list[HistoryEntry] = []
    for r in rows:
        out.append(HistoryEntry(
            history_id=r["history_id"], ts=r["ts"],
            query=r["query"],
            scopes=[s for s in (r["scopes"] or "").split(",") if s],
            actor=r["actor"], result_count=r["result_count"],
        ))
    return out


def clear_history() -> int:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM search_history")
        conn.commit()
    return cur.rowcount


# ── Saved searches ────────────────────────────────────────────────

def _saved_from_row(r: sqlite3.Row) -> SavedSearch:
    try:
        filters = json.loads(r["filters"]) if r["filters"] else {}
    except (TypeError, ValueError):
        filters = {}
    keys = r.keys()
    try:
        role_acl = (json.loads(r["role_acl"])
                    if "role_acl" in keys and r["role_acl"] else [])
    except (TypeError, ValueError):
        role_acl = []
    try:
        tags_raw = r["tags"] if "tags" in keys else None
        tags = json.loads(tags_raw) if tags_raw else []
    except (TypeError, ValueError):
        tags = []
    return SavedSearch(
        saved_id=r["saved_id"], name=r["name"], query=r["query"],
        scopes=[s for s in (r["scopes"] or "").split(",") if s],
        filters=filters, notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        owner_actor=(r["owner_actor"] if "owner_actor" in keys else None),
        visibility=((r["visibility"]
                     if "visibility" in keys else None) or "private"),
        role_acl=role_acl,
        folder=(r["folder"] if "folder" in keys else None),
        tags=tags,
    )


def _validate_saved_payload(payload: dict[str, Any]) -> dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValidationError("Name is required")
    if not _NAME_RE.match(name):
        raise ValidationError(
            "Name must be 1–48 chars (letters, digits, space, _ . / -)")
    scopes = _validate_scopes(payload.get("scopes"))
    filters = payload.get("filters") or {}
    if isinstance(filters, str):
        s = filters.strip()
        if s:
            try:
                filters = json.loads(s)
            except ValueError as e:
                raise ValidationError(
                    f"filters is not valid JSON: {e}") from None
        else:
            filters = {}
    if not isinstance(filters, dict):
        raise ValidationError("filters must be a JSON object")
    visibility = (payload.get("visibility") or "private").strip().lower()
    if visibility not in VALID_VISIBILITIES:
        raise ValidationError(
            f"visibility must be one of {', '.join(VALID_VISIBILITIES)}")
    role_acl = payload.get("role_acl") or []
    if isinstance(role_acl, str):
        role_acl = [r.strip() for r in role_acl.split(",") if r.strip()]
    if not isinstance(role_acl, (list, tuple)):
        raise ValidationError("role_acl must be a list of role names")
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, (list, tuple)):
        raise ValidationError("tags must be a list")
    folder = (payload.get("folder") or "").strip() or None
    owner = (payload.get("owner_actor") or "").strip() or None
    return {
        "name": name,
        "query": (payload.get("query") or "").strip(),
        "scopes": scopes,
        "filters": json.dumps(filters) if filters else None,
        "notes": (payload.get("notes") or "").strip() or None,
        "owner_actor": owner,
        "visibility": visibility,
        "role_acl": json.dumps(list(role_acl)) if role_acl else None,
        "folder": folder,
        "tags": json.dumps(list(tags)) if tags else None,
    }


def create_saved_search(payload: dict[str, Any]) -> SavedSearch:
    init_db()
    p = _validate_saved_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM saved_searches WHERE name = ?",
                (p["name"],)).fetchone():
            raise ValidationError(
                f"A saved search named {p['name']!r} already exists")
        cur = conn.execute(
            """INSERT INTO saved_searches
                   (name, query, scopes, filters, notes,
                    owner_actor, visibility, role_acl, folder, tags,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["query"], ",".join(p["scopes"]),
             p["filters"], p["notes"],
             p["owner_actor"], p["visibility"], p["role_acl"],
             p["folder"], p["tags"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_saved_search(new_id)
    assert out is not None
    logger.info("Created saved search #%d %r", new_id, p["name"])
    return out


def get_saved_search(saved_id: int) -> SavedSearch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM saved_searches WHERE saved_id = ?",
            (saved_id,)).fetchone()
        return _saved_from_row(r) if r else None


def get_saved_search_by_name(name: str) -> SavedSearch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM saved_searches WHERE name = ?",
            (name.strip(),)).fetchone()
        return _saved_from_row(r) if r else None


def list_saved_searches(
    *,
    folder: str | None = None,
    actor: str | None = None,
    role: str | None = None,
    include_public: bool = True,
) -> list[SavedSearch]:
    """List saved searches.

    When ``actor`` or ``role`` are provided, results are filtered by ACL
    so callers only see private/role/public entries they're entitled to.
    Without either, all rows are returned (for admin tools)."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM saved_searches ORDER BY name ASC").fetchall()
    out = [_saved_from_row(r) for r in rows]
    if folder is not None:
        out = [s for s in out if (s.folder or "") == folder]
    if actor is None and role is None:
        return out
    return [s for s in out
            if (include_public and s.visibility == "public")
            or _saved_acl_allows(s, actor, role)]


def list_saved_folders() -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT folder FROM saved_searches "
            "WHERE folder IS NOT NULL AND folder <> '' "
            "ORDER BY folder ASC").fetchall()
    return [r["folder"] for r in rows]


def update_saved_search(saved_id: int,
                        payload: dict[str, Any]) -> SavedSearch:
    init_db()
    existing = get_saved_search(saved_id)
    if existing is None:
        raise ValidationError(f"No saved search #{saved_id}")
    merged = {
        "name":        payload.get("name", existing.name),
        "query":       payload.get("query", existing.query),
        "scopes":      payload.get("scopes", existing.scopes),
        "filters":     payload.get("filters", existing.filters),
        "notes":       payload.get("notes", existing.notes),
        "owner_actor": payload.get("owner_actor", existing.owner_actor),
        "visibility":  payload.get("visibility", existing.visibility),
        "role_acl":    payload.get("role_acl", existing.role_acl),
        "folder":      payload.get("folder", existing.folder),
        "tags":        payload.get("tags", existing.tags),
    }
    p = _validate_saved_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT saved_id FROM saved_searches WHERE name = ?",
            (p["name"],)).fetchone()
        if row and row["saved_id"] != saved_id:
            raise ValidationError(
                f"A saved search named {p['name']!r} already exists")
        conn.execute(
            """UPDATE saved_searches SET
                   name = ?, query = ?, scopes = ?, filters = ?,
                   notes = ?, owner_actor = ?, visibility = ?,
                   role_acl = ?, folder = ?, tags = ?,
                   updated_at = datetime('now')
               WHERE saved_id = ?""",
            (p["name"], p["query"], ",".join(p["scopes"]),
             p["filters"], p["notes"],
             p["owner_actor"], p["visibility"], p["role_acl"],
             p["folder"], p["tags"], saved_id),
        )
        conn.commit()
    out = get_saved_search(saved_id)
    assert out is not None
    logger.info("Updated saved search #%d %r", saved_id, p["name"])
    return out


def delete_saved_search(saved_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM saved_searches WHERE saved_id = ?",
            (saved_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted saved search #%d", saved_id)
            return True
        return False


def run_saved_search(saved_id: int, *,
                     actor: str | None = None) -> SearchResults:
    s = get_saved_search(saved_id)
    if s is None:
        raise ValidationError(f"No saved search #{saved_id}")
    return run_search(
        s.query, scopes=s.scopes, filters=s.filters,
        actor=actor,
    )

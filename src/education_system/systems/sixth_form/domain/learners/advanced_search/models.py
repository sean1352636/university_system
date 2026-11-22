"""Constants, dataclasses and ValidationError for Advanced Search.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Any


DEFAULT_LIMIT_PER_SCOPE: int = 50
MAX_HISTORY_ROWS: int = 50


# Operator cheat-sheet shared by the CLI and GUI help screens.
QUERY_SYNTAX_HELP: str = """\
Query syntax
────────────
Booleans      smith AND maths      foo OR bar      NOT closed      -closed
Phrases       "merit award"
Fields        name:smith   email:@school   status:open
Student       upn:  uln:  uci:  dob:2008  postcode:OX2  year:12  tutor_group:12A
              preferred:  gender:  nationality:  language:  previous_school:
              start:2025  left:2026  leaving_reason:  contact: (emergency)
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
              Joins/aggregates/cohorts combine with AND / OR / NOT like any
              other term, over the students each row is about.
              Left / withdrawn records are hidden unless "include archived"."""


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
    "attendance":           "Attendance registers",
    "exam_results":         "Exam results",
    "enrolments":           "Enrolments (learning aims)",
    "medical":              "Medical records",
}
ALL_SCOPES: tuple[str, ...] = tuple(SCOPE_LABELS.keys())
DEFAULT_SCOPES: tuple[str, ...] = ALL_SCOPES


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
    #: Matches before the per-scope cap; ``total`` counts what was returned.
    matched_by_scope: dict[str, int] = field(default_factory=dict)
    matched_total: int = 0

    @property
    def truncated(self) -> bool:
        return self.matched_total > self.total

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


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


@dataclass
class QueryOptions:
    fuzzy_default: int = 0
    use_stemming: bool = True
    ignore_stopwords: bool = True
    expand_synonyms: bool = True
    fold_diacritics: bool = True
    today: _dt.date | None = None


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
    action: str = "search"           # search | export | message | …
    record_count: int | None = None


@dataclass
class ScheduleDelta:
    schedule_id: int
    total: int
    added: list[str]
    removed: list[str]


@dataclass
class IndexStatus:
    scope: str
    indexed_rows: int
    current_rows: int
    last_refresh: str | None
    stale: bool


# ══════════════════════════════════════════════════════════════════
# Data quality — duplicates & gaps (items 44, 45)
# ══════════════════════════════════════════════════════════════════

@dataclass
class DuplicateGroup:
    reason: str               # email | surname+dob | name
    key: str
    student_ids: list[str]


@dataclass
class DataGap:
    scope: str
    entity_id: str
    label: str
    missing: list[str]


@dataclass
class Facet:
    field: str
    values: list[tuple[str, int]]


@dataclass
class TrendPoint:
    ts: str
    count: int


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

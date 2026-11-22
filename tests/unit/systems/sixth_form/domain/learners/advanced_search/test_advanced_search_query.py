"""Query-language tests for Sixth Form Advanced Search (features 1–10).

These exercise the parser + per-document matcher directly (no DB needed)
for the matching features, and a tmp-DB fixture for the two features that
read persisted state (``@macros`` and did-you-mean vocabulary).
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.learners.advanced_search import (
    _db as search_db,
    history as search_history,
    matching as search_matching,
    models as search_models,
    query as search_query,
)


def _match(query: str, doc: dict, **opt_kw) -> bool:
    opts = search_models.QueryOptions(**opt_kw)
    return search_matching._doc_match(search_query.parse_query(query, opts), doc, opts)


# ── tmp-DB fixture for the persistence-backed features ────────────

@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(search_db, "DB_PATH", str(tmp_path / "adv.db"))
    monkeypatch.setattr(search_db, "_DB_READY", False)
    search_db.init_db()


# ── 1. Field-prefixed phrases (spaces inside the value) ───────────

def test_field_phrase_with_spaces():
    assert _match('tutor:"john smith"', {"tutor": "Mr John Smith"})
    assert not _match('tutor:"john smith"', {"tutor": "John Q Smith"})


def test_plain_field_term_still_works():
    assert _match("name:smith", {"name": "Smith"})
    assert not _match("name:smith", {"name": "Jones"})


# ── 2. Range syntax ────────────────────────────────────────────────

def test_attendance_range_inclusive():
    assert _match("attendance:80..90", {"_attendance": 80})
    assert _match("attendance:80..90", {"_attendance": 90})
    assert not _match("attendance:80..90", {"_attendance": 91})


def test_grade_range_order_insensitive():
    assert _match("grade:C..A", {"_grade": "B"})
    assert _match("grade:A..C", {"_grade": "B"})
    assert not _match("grade:C..A", {"_grade": "U"})


def test_date_range():
    assert _match("date:2026-01-01..2026-03-31", {"_date": "2026-02-10"})
    assert not _match("date:2026-01-01..2026-03-31", {"_date": "2026-09-10"})


def test_bad_range_raises():
    with pytest.raises(search_models.ValidationError):
        search_query.parse_query("grade:Z..Q", search_models.QueryOptions())


# ── 3. Aggregates ──────────────────────────────────────────────────

def test_aggregate_count_parses():
    node = search_query.parse_query("count(behaviour)>3", search_models.QueryOptions())
    assert isinstance(node, search_query._Aggregate)
    assert (node.func, node.scope, node.op, node.value) == (
        "count", "behaviour", ">", 3.0)


def test_aggregate_bare_metric_shorthand():
    node = search_query.parse_query("avg(attendance)<85", search_models.QueryOptions())
    assert node.func == "avg" and node.field == "attendance"
    assert node.scope == "progress_reviews"


def test_aggregate_scoped_field():
    node = search_query.parse_query("avg(progress_reviews.attendance)>=90",
                         search_models.QueryOptions())
    assert node.scope == "progress_reviews" and node.field == "attendance"


def test_aggregate_unknown_scope_raises():
    with pytest.raises(search_models.ValidationError):
        search_query.parse_query("count(nope)>1", search_models.QueryOptions())


def test_aggregate_metric_helpers():
    agg = search_query._Aggregate("avg", "progress_reviews", "attendance", "<", 85.0)
    assert search_query._agg_metric(agg, 0, [80.0, 90.0]) == 85.0
    cnt = search_query._Aggregate("count", "behaviour", None, ">", 2.0)
    assert search_query._agg_metric(cnt, 5, []) == 5.0


# ── 4. Relative comparisons ────────────────────────────────────────

def test_relative_grade_compare():
    assert _match("predicted<target", {"_grade": "C", "_target": "A"})
    assert not _match("predicted<target", {"_grade": "A", "_target": "C"})


def test_relative_needs_both_sides():
    assert not _match("predicted<target", {"_grade": "C"})


def test_relative_current_vs_mte():
    assert _match("current>=mte", {"_current": "B", "_target": "C"})


# ── 5. Proximity ───────────────────────────────────────────────────

def test_proximity_within_window():
    assert _match('"merit award"~3', {"body": "merit special award"})


def test_proximity_zero_is_adjacent_only():
    assert _match('"merit award"~0', {"body": "merit award here"})
    assert not _match('"merit award"~0', {"body": "merit special award"})


# ── 6. Regex ───────────────────────────────────────────────────────

def test_regex_case_sensitive_by_default():
    assert _match(r"/S1\d{3}/", {"id": "S1234"})
    assert not _match(r"/S1\d{3}/", {"id": "s1234"})


def test_regex_ignore_case_flag():
    assert _match(r"/s1\d{3}/i", {"id": "S1234"})


def test_regex_field_scoped():
    assert _match("id:/^S/", {"id": "S9", "name": "no"})
    assert not _match("id:/^S/", {"id": "X9", "name": "Smith"})


def test_invalid_regex_raises():
    with pytest.raises(search_models.ValidationError):
        search_query.parse_query("/(unclosed/", search_models.QueryOptions())


# ── 7. Inline scope directives ─────────────────────────────────────

def test_scope_directive_extraction():
    clean, inc, exc = search_query._extract_scope_directives(
        "maths scope:students,staff -scope:audit_logs in:notices")
    assert clean == "maths"
    assert inc == ["students", "staff", "notices"]
    assert exc == ["audit_logs"]


def test_scope_directive_none():
    clean, inc, exc = search_query._extract_scope_directives("just a query")
    assert clean == "just a query" and inc == [] and exc == []


# ── 8. Macros ──────────────────────────────────────────────────────

def test_macro_expands_saved_query(fresh_db):
    search_history.create_saved_search(
        {"name": "at_risk", "query": "attendance:<85", "scopes": ["students"]})
    assert search_query.expand_macros("@at_risk and maths") == \
        "(attendance:<85) and maths"


def test_macro_unknown_left_literal(fresh_db):
    assert search_query.expand_macros("@nope foo") == "@nope foo"


def test_macro_cycle_guarded(fresh_db):
    search_history.create_saved_search(
        {"name": "a_loop", "query": "@a_loop x", "scopes": ["students"]})
    # Must terminate (depth/seen guard) and not raise.
    out = search_query.expand_macros("@a_loop")
    assert isinstance(out, str)


# ── 9. Diacritic folding ───────────────────────────────────────────

def test_diacritics_folded_by_default():
    assert _match("zoe", {"name": "Zoë Smith"})
    assert _match("zoë", {"name": "Zoe Smith"})


def test_diacritics_can_be_disabled():
    assert not _match("zoe", {"name": "Zoë"}, fold_diacritics=False)


# ── 10. Did-you-mean ───────────────────────────────────────────────

def test_did_you_mean_corrects_typo(fresh_db):
    # "studetn" is one transposition from the scope-label word "students".
    out = search_query.did_you_mean("studetn")
    assert out and "student" in out[0].lower()


def test_did_you_mean_empty_for_good_term(fresh_db):
    assert search_query.did_you_mean("students") == []


# ── Regression: booleans / wildcards / fuzzy unaffected ───────────

def test_booleans_and_wildcards_intact():
    assert _match("smith AND maths",
                  {"name": "Smith", "subject": "Maths"})
    assert _match("smi*", {"name": "Smith"})
    assert _match("smith~1", {"name": "smyth"})
    assert _match("-closed", {"status": "open"})

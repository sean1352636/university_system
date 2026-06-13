"""Cross-entity / relational tests for Advanced Search (features 11–17).

Parsing and cohort/join semantics are tested hermetically against a
tmp advanced-search DB. The relational report functions are smoke-tested
against the seeded domain data (return types + error handling).
"""

from __future__ import annotations

import pytest

from education_system.sixthform_system.modules.domain.students.advanced_search import (
    advanced_search as A,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "DB_PATH", str(tmp_path / "adv.db"))
    monkeypatch.setattr(A, "_DB_READY", False)
    A.init_db()
    return A


def _first_student_id() -> str | None:
    from education_system.sixthform_system.modules.domain.students.students import (
        students as sm,
    )
    rows = sm.list_students()
    return rows[0].student_id if rows else None


# ── 11. has() / missing() join parsing ─────────────────────────────

def test_has_parses():
    node = A.parse_query("has(safeguarding)", A.QueryOptions())
    assert isinstance(node, A._Has)
    assert node.scope == "safeguarding" and node.negate is False


def test_missing_parses():
    node = A.parse_query("missing(ucas)", A.QueryOptions())
    assert isinstance(node, A._Has) and node.negate is True


def test_has_with_inner_term():
    node = A.parse_query("has(behaviour:fighting)", A.QueryOptions())
    assert node.scope == "behaviour" and node.term == "fighting"


def test_has_non_student_scope_raises():
    with pytest.raises(A.ValidationError):
        A.parse_query("has(courses)", A.QueryOptions())


def test_missing_returns_all_when_empty(fresh_db):
    # No safeguarding rows for the seeded students ⇒ missing(safeguarding)
    # should return every student, not zero (regression: student-id key).
    r = fresh_db.run_search("missing(safeguarding)", scopes=["students"],
                            limit_per_scope=1000)
    all_students = fresh_db.run_search("", scopes=["students"],
                                       limit_per_scope=1000)
    assert r.total == all_students.total
    assert r.total > 0


# ── 12. Cohorts ────────────────────────────────────────────────────

def test_cohort_crud(fresh_db):
    c = fresh_db.create_cohort("year12_test", ["C1", "C2", "C2", " C3 "])
    assert c.member_count == 3
    assert fresh_db.cohort_members("year12_test") == ["C1", "C2", "C3"]
    assert fresh_db.add_to_cohort("year12_test", ["C3", "C4"]) == 1
    assert fresh_db.remove_from_cohort("year12_test", ["C1"]) == 1
    assert set(fresh_db.cohort_members(c.cohort_id)) == {"C2", "C3", "C4"}
    assert any(x.name == "year12_test" for x in fresh_db.list_cohorts())
    assert fresh_db.delete_cohort("year12_test") is True
    assert fresh_db.get_cohort_by_name("year12_test") is None


def test_cohort_duplicate_name_raises(fresh_db):
    fresh_db.create_cohort("dup", ["C1"])
    with pytest.raises(A.ValidationError):
        fresh_db.create_cohort("dup", ["C2"])


def test_cohort_query_filters(fresh_db):
    sid = _first_student_id()
    if sid is None:
        pytest.skip("no seeded students")
    fresh_db.create_cohort("just_one", [sid])
    r = fresh_db.run_search("cohort:just_one", scopes=["students"],
                            limit_per_scope=100)
    ids = [h.entity_id for h in r.all_hits()]
    assert ids == [sid]


def test_create_cohort_from_results(fresh_db):
    r = fresh_db.run_search("", scopes=["students"], limit_per_scope=1000)
    if r.total == 0:
        pytest.skip("no seeded students")
    c = fresh_db.create_cohort_from_results("from_results", r)
    assert c.member_count == r.total


def test_cohort_parse():
    node = A.parse_query("cohort:my_set", A.QueryOptions())
    assert isinstance(node, A._Cohort) and node.name == "my_set"


# ── 13–17. Relational reports (smoke + error handling) ────────────

def test_find_relatives_unknown_raises():
    with pytest.raises(A.ValidationError):
        A.find_relatives("NOPE-DOES-NOT-EXIST")


def test_find_relatives_returns_list():
    sid = _first_student_id()
    if sid is None:
        pytest.skip("no seeded students")
    rels = A.find_relatives(sid)
    assert isinstance(rels, list)
    assert all(isinstance(r, A.Relative) for r in rels)
    assert sid not in [r.student_id for r in rels]   # never self


def test_group_rollup_unknown_raises():
    with pytest.raises(A.ValidationError):
        A.group_rollup(-999)


def test_ucas_peers_requires_university():
    with pytest.raises(A.ValidationError):
        A.ucas_peers("")


def test_ucas_clusters_returns_list():
    cl = A.ucas_choice_clusters()
    assert isinstance(cl, list)
    assert all(isinstance(c, A.UcasCluster) and len(c.student_ids) >= 2
               for c in cl)


def test_timetable_clashes_returns_list():
    out = A.timetable_clashes()
    assert isinstance(out, list)
    assert all(isinstance(c, A.Clash) and c.kind in ("room", "student")
               for c in out)


def test_similar_students_unknown_raises():
    with pytest.raises(A.ValidationError):
        A.similar_students("NOPE")


def test_similar_students_ranked():
    sid = _first_student_id()
    if sid is None:
        pytest.skip("no seeded students")
    sim = A.similar_students(sid, limit=5)
    assert isinstance(sim, list) and len(sim) <= 5
    scores = [s.score for s in sim]
    assert scores == sorted(scores, reverse=True)   # descending
    assert sid not in [s.student_id for s in sim]


def test_student_group_index_shape():
    idx = A.student_group_index()
    assert isinstance(idx, dict)
    for sid, val in list(idx.items())[:3]:
        assert isinstance(sid, str) and isinstance(val, tuple) and len(val) == 2

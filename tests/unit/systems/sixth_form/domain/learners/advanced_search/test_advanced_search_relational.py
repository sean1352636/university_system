"""Cross-entity / relational tests for Advanced Search (features 11–17).

Parsing and cohort/join semantics are tested hermetically against a
tmp advanced-search DB. The relational report functions are smoke-tested
against the seeded domain data (return types + error handling).
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.learners.advanced_search import (
    _db as search_db,
    engine as search_engine,
    history as search_history,
    models as search_models,
    query as search_query,
    sources as search_sources,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(search_db, "DB_PATH", str(tmp_path / "adv.db"))
    monkeypatch.setattr(search_db, "_DB_READY", False)
    search_db.init_db()


def _first_student_id() -> str | None:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    rows = sm.list_students()
    return rows[0].student_id if rows else None


# ── 11. has() / missing() join parsing ─────────────────────────────

def test_has_parses():
    node = search_query.parse_query("has(safeguarding)", search_models.QueryOptions())
    assert isinstance(node, search_query._Has)
    assert node.scope == "safeguarding" and node.negate is False


def test_missing_parses():
    node = search_query.parse_query("missing(ucas)", search_models.QueryOptions())
    assert isinstance(node, search_query._Has) and node.negate is True


def test_has_with_inner_term():
    node = search_query.parse_query("has(behaviour:fighting)", search_models.QueryOptions())
    assert node.scope == "behaviour" and node.term == "fighting"


def test_has_non_student_scope_raises():
    with pytest.raises(search_models.ValidationError):
        search_query.parse_query("has(courses)", search_models.QueryOptions())


def _sign_in(monkeypatch, username="dsl1", capabilities=None):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.Principal(username=username, user_id=None, role="staff",
                         capabilities=frozenset(capabilities if capabilities
                                                is not None else
                                                access.ALL_CAPABILITIES))
    monkeypatch.setattr(access, "_current", p)
    monkeypatch.setattr(access, "log_sensitive_access",
                        lambda *a, **k: None)   # keep off the students DB
    return p


def test_missing_returns_all_when_empty(fresh_db, monkeypatch):
    # No safeguarding rows for the seeded students ⇒ missing(safeguarding)
    # should return every student, not zero (regression: student-id key).
    _sign_in(monkeypatch)
    r = search_engine.run_search("missing(safeguarding)", scopes=["students"],
                            limit_per_scope=1000)
    all_students = search_engine.run_search("", scopes=["students"],
                                       limit_per_scope=1000)
    assert r.total == all_students.total
    assert r.total > 0


def test_join_over_gated_scope_refused(fresh_db, monkeypatch):
    # missing(safeguarding) would reveal who has a concern without showing
    # it, so an account that cannot search safeguarding is refused.
    _sign_in(monkeypatch, "teacher1", {"students.view", "teaching"})
    with pytest.raises(search_models.ValidationError):
        search_engine.run_search("missing(safeguarding)", scopes=["students"],
                                 filters={"use_cache": False})


def test_predicates_combine_with_or_and_not(fresh_db):
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    on_roll = [s for s in sm.list_students() if s.status != "Left"]
    if len(on_roll) < 2:
        pytest.skip("needs two seeded students")
    a, b = on_roll[0].student_id, on_roll[1].student_id
    search_history.create_cohort("only_a", [a])
    f = {"use_cache": False}

    def ids(q):
        r = search_engine.run_search(q, scopes=["students"], filters=f,
                                     limit_per_scope=10_000,
                                     record_history=False)
        return {h.entity_id for h in r.all_hits()}

    everyone = ids("")
    assert ids("cohort:only_a") == {a}
    assert ids("NOT cohort:only_a") == everyone - {a}
    assert ids(f"cohort:only_a OR id:{b}") == {a, b}


def test_year_filter_keeps_students(fresh_db):
    # Regression: the student-id filter compared the student's *name*
    # with the allowed ids, so any year/tutor filter dropped every student.
    idx = search_sources.student_group_index()
    if not idx:
        pytest.skip("no tutor groups seeded")
    sid, (year, _tg) = next(iter(idx.items()))
    r = search_engine.run_search("", scopes=["students"], limit_per_scope=10_000,
                                 filters={"year_group": year, "use_cache": False,
                                          "include_archived": True})
    assert sid in {h.entity_id for h in r.all_hits()}


def test_student_fields_searchable(fresh_db):
    from education_system.systems.sixth_form.domain.learners.students import (
        students as sm,
    )
    s = next((s for s in sm.list_students() if s.status), None)
    if s is None:
        pytest.skip("no seeded students")
    r = search_engine.run_search(f"id:{s.student_id} status:{s.status.lower()}",
                                 scopes=["students"],
                                 filters={"use_cache": False,
                                          "include_archived": True})
    assert [h.entity_id for h in r.all_hits()] == [s.student_id]
    doc = r.all_hits()[0].extra["_doc"]
    for field in ("dob", "upn", "postcode", "year", "tutor_group"):
        assert field in doc


# ── 12. Cohorts ────────────────────────────────────────────────────

def test_cohort_crud(fresh_db):
    c = search_history.create_cohort("year12_test", ["C1", "C2", "C2", " C3 "])
    assert c.member_count == 3
    assert search_history.cohort_members("year12_test") == ["C1", "C2", "C3"]
    assert search_history.add_to_cohort("year12_test", ["C3", "C4"]) == 1
    assert search_history.remove_from_cohort("year12_test", ["C1"]) == 1
    assert set(search_history.cohort_members(c.cohort_id)) == {"C2", "C3", "C4"}
    assert any(x.name == "year12_test" for x in search_history.list_cohorts())
    assert search_history.delete_cohort("year12_test") is True
    assert search_history.get_cohort_by_name("year12_test") is None


def test_cohort_duplicate_name_raises(fresh_db):
    search_history.create_cohort("dup", ["C1"])
    with pytest.raises(search_models.ValidationError):
        search_history.create_cohort("dup", ["C2"])


def test_cohort_query_filters(fresh_db):
    sid = _first_student_id()
    if sid is None:
        pytest.skip("no seeded students")
    search_history.create_cohort("just_one", [sid])
    r = search_engine.run_search("cohort:just_one", scopes=["students"],
                            limit_per_scope=100)
    ids = [h.entity_id for h in r.all_hits()]
    assert ids == [sid]


def test_create_cohort_from_results(fresh_db):
    r = search_engine.run_search("", scopes=["students"], limit_per_scope=1000)
    if r.total == 0:
        pytest.skip("no seeded students")
    c = search_history.create_cohort_from_results("from_results", r)
    assert c.member_count == r.total


def test_cohort_parse():
    node = search_query.parse_query("cohort:my_set", search_models.QueryOptions())
    assert isinstance(node, search_query._Cohort) and node.name == "my_set"


# ── 13–17. Relational reports (smoke + error handling) ────────────

def test_find_relatives_unknown_raises():
    with pytest.raises(search_models.ValidationError):
        search_sources.find_relatives("NOPE-DOES-NOT-EXIST")


def test_find_relatives_returns_list():
    sid = _first_student_id()
    if sid is None:
        pytest.skip("no seeded students")
    rels = search_sources.find_relatives(sid)
    assert isinstance(rels, list)
    assert all(isinstance(r, search_models.Relative) for r in rels)
    assert sid not in [r.student_id for r in rels]   # never self


def test_group_rollup_unknown_raises():
    with pytest.raises(search_models.ValidationError):
        search_sources.group_rollup(-999)


def test_ucas_peers_requires_university():
    with pytest.raises(search_models.ValidationError):
        search_sources.ucas_peers("")


def test_ucas_clusters_returns_list():
    cl = search_sources.ucas_choice_clusters()
    assert isinstance(cl, list)
    assert all(isinstance(c, search_models.UcasCluster) and len(c.student_ids) >= 2
               for c in cl)


def test_timetable_clashes_returns_list():
    out = search_sources.timetable_clashes()
    assert isinstance(out, list)
    assert all(isinstance(c, search_models.Clash) and c.kind in ("room", "student")
               for c in out)


def test_similar_students_unknown_raises():
    with pytest.raises(search_models.ValidationError):
        search_sources.similar_students("NOPE")


def test_similar_students_ranked():
    sid = _first_student_id()
    if sid is None:
        pytest.skip("no seeded students")
    sim = search_sources.similar_students(sid, limit=5)
    assert isinstance(sim, list) and len(sim) <= 5
    scores = [s.score for s in sim]
    assert scores == sorted(scores, reverse=True)   # descending
    assert sid not in [s.student_id for s in sim]


def test_student_group_index_shape():
    idx = search_sources.student_group_index()
    assert isinstance(idx, dict)
    for sid, val in list(idx.items())[:3]:
        assert isinstance(sid, str) and isinstance(val, tuple) and len(val) == 2

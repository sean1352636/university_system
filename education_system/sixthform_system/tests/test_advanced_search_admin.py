"""Tests for Advanced Search features 26–50 (alerts, security, export,
data-quality, analytics). Hermetic against a tmp advanced-search DB; a few
smoke-test against seeded domain data.
"""

from __future__ import annotations

import json
import os

import pytest

from education_system.sixthform_system.modules.domain.students.advanced_search import (
    advanced_search as A,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "DB_PATH", str(tmp_path / "adv.db"))
    monkeypatch.setattr(A, "_DB_READY", False)
    A.clear_cache()
    A.init_db()
    return A


def _mk_saved(db, name="sv", query="", scopes=("students",)):
    return db.create_saved_search(
        {"name": name, "query": query, "scopes": list(scopes)})


# ── 26. Threshold alerts ──────────────────────────────────────────

def test_schedule_threshold_stored(fresh_db):
    s = _mk_saved(fresh_db)
    sc = fresh_db.schedule_saved_search(s.saved_id, notify_actor="t",
                                        threshold=5)
    assert sc.threshold == 5
    assert fresh_db.list_scheduled_searches()[0].threshold == 5


def test_threshold_suppresses_poll(fresh_db):
    total = fresh_db.run_search("", scopes=["students"]).total
    if total == 0:
        pytest.skip("no seeded students")
    s = _mk_saved(fresh_db, name="all_students", scopes=("students",))
    fresh_db.schedule_saved_search(s.saved_id, notify_actor="t",
                                   threshold=total + 100)
    fired = fresh_db.poll_subscriptions()
    assert fired == []   # total below threshold ⇒ no alert


# ── 27. Digest ────────────────────────────────────────────────────

def test_build_digest(fresh_db):
    s = _mk_saved(fresh_db)
    sc = fresh_db.schedule_saved_search(s.saved_id, notify_actor="t")
    fresh_db.run_scheduled_search(sc.schedule_id)
    dg = fresh_db.build_digest("t")
    assert len(dg.lines) == 1 and dg.lines[0].saved_name == "sv"


# ── 28. Delta view ────────────────────────────────────────────────

def test_schedule_delta(fresh_db):
    s = _mk_saved(fresh_db, query="", scopes=("students",))
    sc = fresh_db.schedule_saved_search(s.saved_id, notify_actor="t")
    fresh_db.run_scheduled_search(sc.schedule_id)
    d = fresh_db.schedule_delta(sc.schedule_id)
    # Nothing changed between the recorded run and now.
    assert d.added == [] and d.removed == []


# ── 29. Dashboards ────────────────────────────────────────────────

def test_dashboard_crud_and_run(fresh_db):
    s1 = _mk_saved(fresh_db, name="d_one", query="", scopes=("students",))
    s2 = _mk_saved(fresh_db, name="d_two", query="zzzznotfound",
                   scopes=("students",))
    dash = fresh_db.create_dashboard("dash", [s1.saved_id])
    assert fresh_db.add_to_dashboard("dash", [s2.saved_id]) == 1
    panels = fresh_db.run_dashboard("dash")
    assert {p.name for p in panels} == {"d_one", "d_two"}
    assert any(p.name == "d_two" and p.total == 0 for p in panels)
    assert fresh_db.delete_dashboard("dash") is True


# ── 30. Snooze ────────────────────────────────────────────────────

def test_snooze_hides_notification(fresh_db):
    with A._connect() as conn:
        conn.execute(
            "INSERT INTO subscription_notifications "
            "(schedule_id, actor, delta, total) VALUES (1, 'me', 1, 1)")
        conn.commit()
        nid = conn.execute(
            "SELECT notif_id FROM subscription_notifications").fetchone()[0]
    assert fresh_db.list_subscription_notifications("me")
    fresh_db.snooze_notification(nid, hours=24)
    assert fresh_db.list_subscription_notifications("me") == []
    assert fresh_db.list_subscription_notifications(
        "me", include_snoozed=True)


# ── 31. Field redaction ───────────────────────────────────────────

def test_redact_hit_masks_sensitive():
    h = A.Hit(scope="safeguarding", entity_id="1",
              label="#1 C1 · concern", sublabel="child disclosed X",
              extra={"_doc": {"summary": "secret", "name": "C1"}})
    A._redact_hit(h, "safeguarding")
    assert h.sublabel == A.REDACTION_MASK
    assert h.extra["_doc"]["summary"] == A.REDACTION_MASK
    assert h.extra["_doc"]["name"] == "C1"   # non-sensitive kept


# ── 32 + 35. Scope ACL + break-glass ──────────────────────────────

def test_scope_acl_drop_and_breakglass():
    teacher = A._build_filter_context({"role": "teacher"}, A.QueryOptions())
    assert "safeguarding" in teacher.drop_scopes
    dsl = A._build_filter_context({"role": "dsl"}, A.QueryOptions())
    assert "safeguarding" not in dsl.drop_scopes
    bg = A._build_filter_context(
        {"role": "teacher", "break_glass": "incident"}, A.QueryOptions())
    assert "safeguarding" not in bg.drop_scopes
    assert bg.break_glass_reason == "incident"


# ── 33. Audit trail ───────────────────────────────────────────────

def test_audit_records_sensitive_access(fresh_db):
    fresh_db.run_search("a", scopes=["safeguarding"],
                        filters={"role": "dsl"}, actor="u1")
    rows = fresh_db.list_search_audit(sensitive_only=True)
    assert rows and rows[0].actor == "u1"
    assert "safeguarding" in rows[0].sensitive_scopes


# ── 34. Consent filter ────────────────────────────────────────────

def test_consent_filter_no_crash(fresh_db):
    excluded = fresh_db._students_without_consent("Third-Party Sharing")
    assert isinstance(excluded, set)
    r = fresh_db.run_search(
        "", scopes=["students"],
        filters={"require_consent": "Third-Party Sharing"})
    assert r.total >= 0


# ── 36. Multi-format export ───────────────────────────────────────

def test_export_formats(fresh_db, tmp_path):
    r = fresh_db.run_search("", scopes=["students"], limit_per_scope=5)
    assert A.export_results(r, fmt="json").lstrip().startswith("[")
    assert A.export_results(r, fmt="md").startswith("| scope")
    assert "<table>" in A.export_results(r, fmt="html")
    with pytest.raises(A.ValidationError):
        A.export_results(r, fmt="bogus")
    for ext in ("csv", "tsv", "json", "html", "md", "xlsx", "pdf"):
        p = tmp_path / f"out.{ext}"
        A.export_results_file(r, str(p))
        assert p.exists() and p.stat().st_size > 0


def test_export_columns_subset(fresh_db):
    r = fresh_db.run_search("", scopes=["students"], limit_per_scope=2)
    head = A.export_results(r, fmt="csv", columns=["entity_id", "label"]
                            ).splitlines()[0]
    assert head == "entity_id,label"


# ── 37. Mail-merge ────────────────────────────────────────────────

def test_mailmerge_drafts(fresh_db):
    r = fresh_db.run_search("", scopes=["students"], limit_per_scope=3)
    if r.total == 0:
        pytest.skip("no seeded students")
    out = fresh_db.mailmerge_results(r, subject="Hi", body="Body")
    assert out["recipients"] == r.total
    assert out["status"] == "Draft"


def test_mailmerge_requires_students(fresh_db):
    r = fresh_db.run_search("zzznotfound", scopes=["courses"])
    with pytest.raises(A.ValidationError):
        fresh_db.mailmerge_results(r, subject="x", body="y")


# ── 38. Cohort export ─────────────────────────────────────────────

def test_export_cohort(fresh_db):
    r = fresh_db.run_search("", scopes=["students"], limit_per_scope=5)
    if r.total == 0:
        pytest.skip("no seeded students")
    fresh_db.create_cohort_from_results("cx", r)
    payload = json.loads(fresh_db.export_cohort("cx"))
    assert payload["cohort"] == "cx" and payload["count"] == r.total
    assert "student_id" in fresh_db.export_cohort("cx", fmt="csv")


# ── 39. Contact sheet ─────────────────────────────────────────────

def test_contact_sheet(fresh_db):
    r = fresh_db.run_search("", scopes=["students"], limit_per_scope=3)
    html = fresh_db.contact_sheet(r)
    assert "<html" in html.lower()
    assert "Contact sheet" in fresh_db.contact_sheet(r, fmt="text")


# ── 40. API blueprint ─────────────────────────────────────────────

def test_api_blueprint_routes():
    flask = pytest.importorskip("flask")
    from education_system.shared.api.sixthform.routes import advanced_search_bp
    app = flask.Flask(__name__)
    app.register_blueprint(advanced_search_bp)
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/sixthform/advanced-search/saved" in rules
    assert "/api/sixthform/advanced-search/run" in rules
    assert "/api/sixthform/advanced-search/cohorts" in rules


# ── 41. Index status / incremental ────────────────────────────────

def test_index_status_and_stale(fresh_db):
    st = fresh_db.index_status(["students"])
    assert st and st[0].scope == "students"
    assert st[0].stale is True   # never indexed yet
    if fresh_db._fts_available():
        fresh_db.refresh_index(["students"])
        st2 = fresh_db.index_status(["students"])
        assert st2[0].stale is False


# ── 43. Cache stats ───────────────────────────────────────────────

def test_cache_stats(fresh_db):
    fresh_db.run_search("a", scopes=["students"])
    fresh_db.run_search("a", scopes=["students"])
    st = fresh_db.cache_stats()
    assert st["hits"] >= 1 and st["entries"] >= 1


# ── 44. Duplicate detection ───────────────────────────────────────

def test_find_duplicates_returns_groups():
    groups = A.find_duplicate_students()
    assert isinstance(groups, list)
    assert all(isinstance(g, A.DuplicateGroup) and len(g.student_ids) > 1
               for g in groups)


# ── 45. Data-gap search ───────────────────────────────────────────

def test_find_data_gaps():
    gaps = A.find_data_gaps("students")
    assert isinstance(gaps, list)
    assert all(isinstance(g, A.DataGap) and g.missing for g in gaps)
    with pytest.raises(A.ValidationError):
        A.find_data_gaps("nope")


# ── 46. Search volume ─────────────────────────────────────────────

def test_search_volume(fresh_db):
    fresh_db.run_search("a", scopes=["students"])
    vol = fresh_db.search_volume_by_day()
    assert vol and isinstance(vol[0], tuple) and vol[0][1] >= 1


# ── 47. Facets ────────────────────────────────────────────────────

def test_facets_shape(fresh_db):
    r = fresh_db.run_search("", scopes=["students", "courses"],
                            limit_per_scope=50)
    fcs = fresh_db.facets(r)
    assert isinstance(fcs, list)
    assert all(isinstance(f, A.Facet) for f in fcs)


# ── 48. Query trend ───────────────────────────────────────────────

def test_query_trend(fresh_db):
    fresh_db.run_search("trendq", scopes=["students"])
    fresh_db.run_search("trendq", scopes=["students"])
    pts = fresh_db.query_trend("trendq")
    assert len(pts) >= 1 and all(isinstance(p, A.TrendPoint) for p in pts)


# ── 49. Natural-language query ────────────────────────────────────

def test_nl_to_query():
    q = A.nl_to_query("students under 85% attendance with a behaviour log "
                      "doing maths")
    assert "attendance:<85" in q
    assert "has(behaviour)" in q
    assert "subject:maths" in q
    q2 = A.nl_to_query("students with no ucas and predicted below target")
    assert "missing(ucas)" in q2 and "predicted<target" in q2
    # Output must be a runnable query.
    assert A.parse_query(q, A.QueryOptions()) is not None


# ── 50. Query examples ────────────────────────────────────────────

def test_query_examples_parse():
    ex = A.query_examples()
    assert len(ex) >= 8
    for _desc, q in ex:
        # Every advertised example must parse without error.
        A.parse_query(q, A.QueryOptions())

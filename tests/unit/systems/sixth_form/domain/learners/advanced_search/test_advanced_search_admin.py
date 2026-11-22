"""Tests for Advanced Search features 26–50 (alerts, security, export,
data-quality, analytics). Hermetic against a tmp advanced-search DB; a few
smoke-test against seeded domain data.
"""

from __future__ import annotations

import json
import os

import pytest

from education_system.systems.sixth_form.domain.learners.advanced_search import (
    _db as search_db,
    engine as search_engine,
    exports as search_exports,
    history as search_history,
    insights as search_insights,
    matching as search_matching,
    models as search_models,
    query as search_query,
)


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(search_db, "DB_PATH", str(tmp_path / "adv.db"))
    monkeypatch.setattr(search_db, "_DB_READY", False)
    search_db.clear_cache()
    search_db.init_db()


def _mk_saved(db, name="sv", query="", scopes=("students",)):
    return search_history.create_saved_search(
        {"name": name, "query": query, "scopes": list(scopes)})


# ── 26. Threshold alerts ──────────────────────────────────────────

def test_schedule_threshold_stored(fresh_db):
    s = _mk_saved(fresh_db)
    sc = search_history.schedule_saved_search(s.saved_id, notify_actor="t",
                                        threshold=5)
    assert sc.threshold == 5
    assert search_history.list_scheduled_searches()[0].threshold == 5


def test_threshold_suppresses_poll(fresh_db):
    total = search_engine.run_search("", scopes=["students"]).total
    if total == 0:
        pytest.skip("no seeded students")
    s = _mk_saved(fresh_db, name="all_students", scopes=("students",))
    search_history.schedule_saved_search(s.saved_id, notify_actor="t",
                                   threshold=total + 100)
    fired = search_history.poll_subscriptions()
    assert fired == []   # total below threshold ⇒ no alert


# ── 27. Digest ────────────────────────────────────────────────────

def test_build_digest(fresh_db):
    s = _mk_saved(fresh_db)
    sc = search_history.schedule_saved_search(s.saved_id, notify_actor="t")
    search_history.run_scheduled_search(sc.schedule_id)
    dg = search_history.build_digest("t")
    assert len(dg.lines) == 1 and dg.lines[0].saved_name == "sv"


# ── 28. Delta view ────────────────────────────────────────────────

def test_schedule_delta(fresh_db):
    s = _mk_saved(fresh_db, query="", scopes=("students",))
    sc = search_history.schedule_saved_search(s.saved_id, notify_actor="t")
    search_history.run_scheduled_search(sc.schedule_id)
    d = search_history.schedule_delta(sc.schedule_id)
    # Nothing changed between the recorded run and now.
    assert d.added == [] and d.removed == []


# ── 29. Dashboards ────────────────────────────────────────────────

def test_dashboard_crud_and_run(fresh_db):
    s1 = _mk_saved(fresh_db, name="d_one", query="", scopes=("students",))
    s2 = _mk_saved(fresh_db, name="d_two", query="zzzznotfound",
                   scopes=("students",))
    dash = search_history.create_dashboard("dash", [s1.saved_id])
    assert search_history.add_to_dashboard("dash", [s2.saved_id]) == 1
    panels = search_history.run_dashboard("dash")
    assert {p.name for p in panels} == {"d_one", "d_two"}
    assert any(p.name == "d_two" and p.total == 0 for p in panels)
    assert search_history.delete_dashboard("dash") is True


# ── 30. Snooze ────────────────────────────────────────────────────

def test_snooze_hides_notification(fresh_db):
    with search_db._connect() as conn:
        conn.execute(
            "INSERT INTO subscription_notifications "
            "(schedule_id, actor, delta, total) VALUES (1, 'me', 1, 1)")
        conn.commit()
        nid = conn.execute(
            "SELECT notif_id FROM subscription_notifications").fetchone()[0]
    assert search_history.list_subscription_notifications("me")
    search_history.snooze_notification(nid, hours=24)
    assert search_history.list_subscription_notifications("me") == []
    assert search_history.list_subscription_notifications(
        "me", include_snoozed=True)


# ── 31. Field redaction ───────────────────────────────────────────

def test_redact_hit_masks_sensitive():
    h = search_models.Hit(scope="safeguarding", entity_id="1",
              label="#1 C1 · concern", sublabel="child disclosed X",
              extra={"_doc": {"summary": "secret", "name": "C1"}})
    search_matching._redact_hit(h, "safeguarding")
    assert h.sublabel == search_matching.REDACTION_MASK
    assert h.extra["_doc"]["summary"] == search_matching.REDACTION_MASK
    assert h.extra["_doc"]["name"] == "C1"   # non-sensitive kept


# ── 32 + 35. Scope ACL + break-glass ──────────────────────────────

def test_scope_acl_drop_and_breakglass():
    teacher = search_matching._build_filter_context({"role": "teacher"}, search_models.QueryOptions())
    assert "safeguarding" in teacher.drop_scopes
    dsl = search_matching._build_filter_context({"role": "dsl"}, search_models.QueryOptions())
    assert "safeguarding" not in dsl.drop_scopes
    bg = search_matching._build_filter_context(
        {"role": "teacher", "break_glass": "incident"}, search_models.QueryOptions())
    assert "safeguarding" not in bg.drop_scopes
    assert bg.break_glass_reason == "incident"


# ── 33. Audit trail ───────────────────────────────────────────────

def _sign_in(monkeypatch, username, capabilities=None, role="staff"):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.Principal(username=username, user_id=None, role=role,
                         capabilities=frozenset(capabilities if capabilities
                                                is not None else
                                                access.ALL_CAPABILITIES))
    monkeypatch.setattr(access, "_current", p)
    monkeypatch.setattr(access, "log_sensitive_access",
                        lambda *a, **k: None)   # keep off the students DB
    return p


def test_audit_records_sensitive_access(fresh_db, monkeypatch):
    # The actor is the signed-in account, not a caller-supplied name.
    _sign_in(monkeypatch, "u1")
    search_engine.run_search("a", scopes=["safeguarding"],
                        filters={"role": "dsl"}, actor="someone-else")
    rows = search_history.list_search_audit(sensitive_only=True)
    assert rows and rows[0].actor == "u1"
    assert "safeguarding" in rows[0].sensitive_scopes


# ── 34. Consent filter ────────────────────────────────────────────

def test_consent_filter_no_crash(fresh_db):
    excluded = search_matching._students_without_consent("Third-Party Sharing")
    assert isinstance(excluded, set)
    r = search_engine.run_search(
        "", scopes=["students"],
        filters={"require_consent": "Third-Party Sharing"})
    assert r.total >= 0


# ── 36. Multi-format export ───────────────────────────────────────

def test_export_formats(fresh_db, tmp_path):
    r = search_engine.run_search("", scopes=["students"], limit_per_scope=5)
    assert search_exports.export_results(r, fmt="json").lstrip().startswith("[")
    assert search_exports.export_results(r, fmt="md").startswith("| scope")
    assert "<table>" in search_exports.export_results(r, fmt="html")
    with pytest.raises(search_models.ValidationError):
        search_exports.export_results(r, fmt="bogus")
    for ext in ("csv", "tsv", "json", "html", "md", "xlsx", "pdf"):
        p = tmp_path / f"out.{ext}"
        search_exports.export_results_file(r, str(p))
        assert p.exists() and p.stat().st_size > 0


def test_export_columns_subset(fresh_db):
    r = search_engine.run_search("", scopes=["students"], limit_per_scope=2)
    head = search_exports.export_results(r, fmt="csv", columns=["entity_id", "label"]
                            ).splitlines()[0]
    assert head == "entity_id,label"


# ── 37. Mail-merge ────────────────────────────────────────────────

def test_mailmerge_drafts(fresh_db):
    r = search_engine.run_search("", scopes=["students"], limit_per_scope=3)
    if r.total == 0:
        pytest.skip("no seeded students")
    out = search_exports.mailmerge_results(r, subject="Hi", body="Body")
    assert out["recipients"] == r.total
    assert out["status"] == "Draft"


def test_mailmerge_requires_students(fresh_db):
    r = search_engine.run_search("zzznotfound", scopes=["courses"])
    with pytest.raises(search_models.ValidationError):
        search_exports.mailmerge_results(r, subject="x", body="y")


# ── 38. Cohort export ─────────────────────────────────────────────

def test_export_cohort(fresh_db):
    r = search_engine.run_search("", scopes=["students"], limit_per_scope=5)
    if r.total == 0:
        pytest.skip("no seeded students")
    search_history.create_cohort_from_results("cx", r)
    payload = json.loads(search_exports.export_cohort("cx"))
    assert payload["cohort"] == "cx" and payload["count"] == r.total
    assert "student_id" in search_exports.export_cohort("cx", fmt="csv")


# ── 39. Contact sheet ─────────────────────────────────────────────

def test_contact_sheet(fresh_db):
    r = search_engine.run_search("", scopes=["students"], limit_per_scope=3)
    html = search_exports.contact_sheet(r)
    assert "<html" in html.lower()
    assert "Contact sheet" in search_exports.contact_sheet(r, fmt="text")


# ── 40. API blueprint ─────────────────────────────────────────────

def test_api_blueprint_routes():
    flask = pytest.importorskip("flask")
    from education_system.api.sixth_form.routes import advanced_search_bp
    app = flask.Flask(__name__)
    app.register_blueprint(advanced_search_bp)
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/advanced-search/saved" in rules
    assert "/api/advanced-search/run" in rules
    assert "/api/advanced-search/cohorts" in rules


# ── 41. Index status / incremental ────────────────────────────────

def test_index_status_and_stale(fresh_db):
    st = search_insights.index_status(["students"])
    assert st and st[0].scope == "students"
    assert st[0].stale is True   # never indexed yet
    if search_db._fts_available():
        search_insights.refresh_index(["students"])
        st2 = search_insights.index_status(["students"])
        assert st2[0].stale is False


# ── 43. Cache stats ───────────────────────────────────────────────

def test_cache_stats(fresh_db):
    search_engine.run_search("a", scopes=["students"])
    search_engine.run_search("a", scopes=["students"])
    st = search_db.cache_stats()
    assert st["hits"] >= 1 and st["entries"] >= 1


# ── 44. Duplicate detection ───────────────────────────────────────

def test_find_duplicates_returns_groups():
    groups = search_insights.find_duplicate_students()
    assert isinstance(groups, list)
    assert all(isinstance(g, search_models.DuplicateGroup) and len(g.student_ids) > 1
               for g in groups)


# ── 45. Data-gap search ───────────────────────────────────────────

def test_find_data_gaps():
    gaps = search_insights.find_data_gaps("students")
    assert isinstance(gaps, list)
    assert all(isinstance(g, search_models.DataGap) and g.missing for g in gaps)
    with pytest.raises(search_models.ValidationError):
        search_insights.find_data_gaps("nope")


# ── 46. Search volume ─────────────────────────────────────────────

def test_search_volume(fresh_db):
    search_engine.run_search("a", scopes=["students"])
    vol = search_insights.search_volume_by_day()
    assert vol and isinstance(vol[0], tuple) and vol[0][1] >= 1


# ── 47. Facets ────────────────────────────────────────────────────

def test_facets_shape(fresh_db):
    r = search_engine.run_search("", scopes=["students", "courses"],
                            limit_per_scope=50)
    fcs = search_insights.facets(r)
    assert isinstance(fcs, list)
    assert all(isinstance(f, search_models.Facet) for f in fcs)


# ── 48. Query trend ───────────────────────────────────────────────

def test_query_trend(fresh_db):
    search_engine.run_search("trendq", scopes=["students"])
    search_engine.run_search("trendq", scopes=["students"])
    pts = search_insights.query_trend("trendq")
    assert len(pts) >= 1 and all(isinstance(p, search_models.TrendPoint) for p in pts)


# ── 49. Natural-language query ────────────────────────────────────

def test_nl_to_query():
    q = search_insights.nl_to_query("students under 85% attendance with a behaviour log "
                      "doing maths")
    assert "attendance:<85" in q
    assert "has(behaviour)" in q
    assert "subject:maths" in q
    q2 = search_insights.nl_to_query("students with no ucas and predicted below target")
    assert "missing(ucas)" in q2 and "predicted<target" in q2
    # Output must be a runnable query.
    assert search_query.parse_query(q, search_models.QueryOptions()) is not None


# ── 50. Query examples ────────────────────────────────────────────

def test_query_examples_parse():
    ex = search_insights.query_examples()
    assert len(ex) >= 8
    for _desc, q in ex:
        # Every advertised example must parse without error.
        search_query.parse_query(q, search_models.QueryOptions())


# ── Signed-in identity, ownership and per-user state ──────────────

def test_signed_in_role_overrides_filter(fresh_db, monkeypatch):
    _sign_in(monkeypatch, "teacher1", {"students.view", "teaching"},
             role="teacher")
    ctx = search_matching._build_filter_context(
        {"role": "dsl", "actor": "dsl1"}, search_models.QueryOptions())
    assert ctx.actor == "teacher1" and ctx.role == "teacher"
    assert "safeguarding" in ctx.drop_scopes
    assert "medical" in ctx.drop_scopes


def test_history_is_per_user(fresh_db, monkeypatch):
    _sign_in(monkeypatch, "alice")
    search_engine.run_search("aliceq", scopes=["students"],
                             filters={"use_cache": False})
    _sign_in(monkeypatch, "bob", {"students.view"})
    search_engine.run_search("bobq", scopes=["students"],
                             filters={"use_cache": False})
    assert [h.query for h in search_history.list_history(10)] == ["bobq"]
    with pytest.raises(search_models.ValidationError):
        search_history.list_history(10, all_users=True)
    assert search_history.clear_history() == 1
    _sign_in(monkeypatch, "alice")
    assert [h.query for h in search_history.list_history(10)] == ["aliceq"]


def test_saved_search_owner_and_visibility(fresh_db, monkeypatch):
    _sign_in(monkeypatch, "alice", {"students.view"})
    s = _mk_saved(None, name="alice_private", query="x")
    assert s.owner_actor == "alice" and s.visibility == "private"
    _sign_in(monkeypatch, "bob", {"students.view"})
    assert all(x.saved_id != s.saved_id
               for x in search_history.list_saved_searches())
    assert search_history.get_saved_search_by_name("alice_private") is None
    assert search_query.expand_macros("@alice_private") == "@alice_private"
    with pytest.raises(search_models.ValidationError):
        search_history.delete_saved_search(s.saved_id)
    with pytest.raises(search_models.ValidationError):
        search_history.update_saved_search(s.saved_id, {"query": "y"})
    with pytest.raises(search_models.ValidationError):
        search_history.run_saved_search(s.saved_id)
    _sign_in(monkeypatch, "alice", {"students.view"})
    search_history.update_saved_search(
        s.saved_id, {"visibility": "role", "role_acl": ["Tutor"]})
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    monkeypatch.setattr(access, "_current", access.Principal(
        username="bob", user_id=None, role="staff", job_role="Tutor",
        capabilities=frozenset({"students.view"})))
    assert any(x.saved_id == s.saved_id
               for x in search_history.list_saved_searches())


def test_scheduled_alert_reaches_inbox(fresh_db, monkeypatch):
    from education_system.systems.sixth_form.domains.communications.domain.notifications import (
        notifications as notif,
    )
    sent = []
    monkeypatch.setattr(notif, "create_notification", sent.append)
    s = _mk_saved(None, name="alert_me")
    sc = search_history.schedule_saved_search(s.saved_id, notify_actor="t")
    search_history._try_push_notification(sc, 3, None)
    assert sent and sent[0]["recipient_id"] == "t"
    assert sent[0]["recipient_type"] == "Staff"
    assert "alert_me" in sent[0]["title"]


def test_annotations_round_trip(fresh_db, monkeypatch):
    from education_system.systems.sixth_form.domain.learners.advanced_search import (
        annotations,
    )
    monkeypatch.setattr(annotations, "_IMPORTED", True)   # skip JSON import
    store = annotations.load_all()
    store["students:S1"] = {"tags": ["x"]}
    annotations.save_all(store)
    assert annotations.get("students", "S1") == {"tags": ["x"]}
    store.pop("students:S1")
    annotations.save_all(store)
    assert annotations.get("students", "S1") == {}
    annotations.log_action("export", "t", 2)
    assert annotations.list_actions(5)[-1]["action"] == "export"


def test_bulk_status_needs_manage(fresh_db, monkeypatch):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    from education_system.systems.sixth_form.domain.learners.advanced_search import (
        actions,
    )
    _sign_in(monkeypatch, "viewer", {"students.view"})
    with pytest.raises(access.AccessDenied):
        actions.bulk_set_status(["S1"], "Inactive")
    _sign_in(monkeypatch, "admin1")
    with pytest.raises(search_models.ValidationError):
        actions.bulk_set_status(["S1"], "Left")       # Left needs a reason

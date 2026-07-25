"""Tests for the cross-system backbone features (items 5-10):

* bus_drainer / bus_consumers — real-time draining plumbing
* safeguarding alert_service — flags follow the learner
* staff_directory — one HR identity across systems
* analytics warehouse — read-only cross-DB reporting
* parent_overview — unified parent view
* journey_cli — CLI helper for journey + promote
"""

import sqlite3

import pytest

from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.platform.cross_system import identity_service


@pytest.fixture()
def auth_db(tmp_path):
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    identity_service._initialised.discard(path)
    return path


# ── 6: Safeguarding alerts ───────────────────────────────────────────────

def test_safeguarding_raise_and_get(auth_db):
    from education_system.platform.governance.safeguarding import alert_service
    alert_service._initialised.discard(auth_db)

    jid = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2010-01-01",
        system="secondary", student_id="Y9", db_path=auth_db)

    aid = alert_service.raise_flag(
        jid, source_system="secondary", category="welfare",
        severity="high", summary="Concern X", raised_by="DSL", db_path=auth_db)
    assert aid

    alerts = alert_service.get_alerts(jid, db_path=auth_db)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "high"
    assert alerts[0]["source_system"] == "secondary"

    # Visible cross-system: the same journey resolves the flag from college.
    open_only = alert_service.get_alerts(jid, status="open", db_path=auth_db)
    assert len(open_only) == 1

    # A bus event was published (broadcast) for live notification.
    conn = sqlite3.connect(auth_db)
    n = conn.execute(
        "SELECT COUNT(*) FROM cross_system_event_outbox "
        "WHERE event_name='safeguarding.flag.raised' AND journey_id=?",
        (jid,)).fetchone()[0]
    conn.close()
    assert n == 1


def test_safeguarding_for_local_concern_resolves_journey(auth_db):
    from education_system.platform.governance.safeguarding import alert_service
    alert_service._initialised.discard(auth_db)
    jid = identity_service.get_or_create_journey(
        first_name="Grace", last_name="Hopper", date_of_birth="2009-12-09",
        system="secondary", student_id="Y10", db_path=auth_db)
    aid = alert_service.raise_flag_for_local_concern(
        "secondary", "Y10", category="behaviour", db_path=auth_db)
    assert aid
    assert alert_service.get_alerts(jid, db_path=auth_db)[0]["category"] == "behaviour"


def test_safeguarding_local_concern_no_journey(auth_db):
    from education_system.platform.governance.safeguarding import alert_service
    alert_service._initialised.discard(auth_db)
    # Unknown pupil → no journey → returns None, never raises.
    assert alert_service.raise_flag_for_local_concern(
        "secondary", "ZZZ", db_path=auth_db) is None


# ── 8: Staff directory ───────────────────────────────────────────────────

def test_staff_directory_links_one_person_across_systems(auth_db):
    from education_system.platform.identity.staff_directory import staff_directory_service as sd
    sd._initialised.discard(auth_db)

    spid = sd.register_staff(
        "secondary", staff_id="T100", first_name="Jane", last_name="Doe",
        email="jane@school", role="Teacher", db_path=auth_db)
    # Same person employed by the sixth form too → same directory record.
    spid2 = sd.register_staff(
        "sixth_form", staff_id="C55", first_name="Jane", last_name="Doe",
        email="jane@college", role="Lecturer", db_path=auth_db)
    assert spid == spid2

    assert sd.get_by_staff("secondary", "T100", db_path=auth_db)["staff_person_id"] == spid
    assert sd.systems_for(spid, db_path=auth_db) == {
        "secondary": "T100", "sixth_form": "C55"}


def test_staff_directory_register_local_never_raises(auth_db):
    from education_system.platform.identity.staff_directory import staff_directory_service as sd
    sd._initialised.discard(auth_db)
    # Missing name → register_staff would raise; the local wrapper swallows it.
    assert sd.register_local_staff(
        "secondary", staff_id="T1", first_name="", last_name="",
        db_path=auth_db) is None


# ── 9: Reporting warehouse ───────────────────────────────────────────────

@pytest.fixture()
def warehouse_dbs(tmp_path, auth_db):
    """Two system DBs + journeys spanning the funnel."""
    nursery = tmp_path / "nursery.db"
    c = sqlite3.connect(str(nursery))
    c.execute("CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, first_name TEXT)")
    c.executemany("INSERT INTO pupils VALUES (?,?)",
                  [("N1", "A"), ("N2", "B"), ("N3", "C")])
    c.commit(); c.close()

    uni = tmp_path / "uni.db"
    c = sqlite3.connect(str(uni))
    c.execute("CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT)")
    c.execute("INSERT INTO students VALUES ('U1','A')")
    c.commit(); c.close()

    # Journeys: one full nursery→university, two nursery-only.
    j = identity_service.get_or_create_journey(
        first_name="A", last_name="One", date_of_birth="2005-01-01",
        system="nursery", student_id="N1", db_path=auth_db)
    identity_service.link_system(j, "university", student_id="U1", db_path=auth_db)
    identity_service.get_or_create_journey(
        first_name="B", last_name="Two", date_of_birth="2006-01-01",
        system="nursery", student_id="N2", db_path=auth_db)
    identity_service.get_or_create_journey(
        first_name="C", last_name="Three", date_of_birth="2007-01-01",
        system="nursery", student_id="N3", db_path=auth_db)
    return {"nursery": nursery, "university": uni}, auth_db


def test_warehouse_headcount_and_funnel(warehouse_dbs):
    from education_system.platform.features.analytics.warehouse import Warehouse
    db_paths, auth_db = warehouse_dbs
    wh = Warehouse(db_paths=db_paths, auth_db=auth_db)

    heads = wh.headcount_by_system()
    assert heads["nursery"]["headcount"] == 3
    assert heads["university"]["headcount"] == 1

    funnel = wh.retention_funnel()
    assert funnel["_total_journeys"] == 3
    assert funnel["nursery"]["reached"] == 3
    assert funnel["university"]["reached"] == 1

    rates = wh.progression_rates()
    # No journey reached sixth form, so sixth_form->university is guarded to 0.0.
    assert rates["sixth_form->university"] == 0.0
    assert rates["nursery->primary"] == 0.0  # none reached primary
    summary = wh.summary()
    assert "nursery" in summary["attached_systems"]


# ── 7: Parent overview ───────────────────────────────────────────────────

def test_parent_overview_aggregates_children(auth_db):
    from education_system.platform.services.parent_child_link import (
        ParentChildLinkService,
    )
    from education_system.platform.services import parent_overview

    # Two children, each with a journey.
    j1 = identity_service.get_or_create_journey(
        first_name="Kid", last_name="One", date_of_birth="2012-01-01",
        system="primary", student_id="P1", db_path=auth_db)
    j2 = identity_service.get_or_create_journey(
        first_name="Kid", last_name="Two", date_of_birth="2008-01-01",
        system="secondary", student_id="Y1", db_path=auth_db)

    svc = ParentChildLinkService(auth_db)
    svc.link_child(parent_user_id=7, child_student_id="P1",
                   child_system_key="primary")
    svc.link_child(parent_user_id=7, child_student_id="Y1",
                   child_system_key="secondary")

    overviews = parent_overview.get_children_overviews(7, auth_db=auth_db)
    assert len(overviews) == 2
    journeys = {o["journey_id"] for o in overviews}
    assert journeys == {j1, j2}


def test_parent_link_across_journey(auth_db):
    from education_system.platform.services.parent_child_link import (
        ParentChildLinkService,
    )
    from education_system.platform.services import parent_overview

    j = identity_service.get_or_create_journey(
        first_name="Multi", last_name="Phase", date_of_birth="2008-01-01",
        system="secondary", student_id="Y1", db_path=auth_db)
    identity_service.link_system(j, "sixth_form", student_id="C1", db_path=auth_db)

    created = parent_overview.link_parent_across_journey(9, j, auth_db=auth_db)
    assert len(created) == 2  # school + college slots
    svc = ParentChildLinkService(auth_db)
    kids = svc.get_children(9)
    assert {(k["child_system_key"], k["child_student_id"]) for k in kids} == {
        ("secondary", "Y1"), ("sixth_form", "C1")}


# ── 5 & 10: drainer plumbing + CLI helper ────────────────────────────────

def test_bus_drainer_thread_is_suppressible():
    from education_system.platform.integrations.external import bus_drainer
    d = bus_drainer.BackgroundDrainer("secondary", interval=5)
    assert d.name == bus_drainer.DRAINER_THREAD_NAME
    assert d.daemon is True


def test_register_consumers_runs():
    from education_system.platform.integrations.external.bus_consumers import register_consumers
    # At least the shared safeguarding consumer registers for any system.
    assert register_consumers("nursery") >= 1


def test_journey_cli_helpers(auth_db, monkeypatch):
    from education_system.platform.cross_system import journey_cli, student_view

    assert journey_cli.next_phase_label("secondary") == "sixth_form"
    assert journey_cli.promote_kind("secondary") == "subjects"
    assert journey_cli.promote_kind("nursery") == "plain"
    assert journey_cli.promote_kind("university") is None

    # show_journey renders the overview text for a built journey.
    j = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2005-01-01",
        system="secondary", student_id="Y1", db_path=auth_db)
    monkeypatch.setattr(
        student_view, "build_overview_for_student",
        lambda sysk, sid, **k: student_view.build_overview(j, auth_db=auth_db))
    text = journey_cli.show_journey("secondary", "Y1")
    assert "Ada Lovelace" in text


def test_journey_cli_dispatch_routes(auth_db, monkeypatch):
    from education_system.platform.cross_system import journey_cli, student_view

    j = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2005-01-01",
        system="secondary", student_id="Y1", db_path=auth_db)
    monkeypatch.setattr(
        student_view, "build_overview_for_student",
        lambda sysk, sid, **k: student_view.build_overview(j, auth_db=auth_db))

    out_lines = []
    handled = journey_cli.dispatch(
        "Student Journey", "secondary",
        input_fn=lambda _p="": "Y1", output_fn=out_lines.append)
    assert handled is True
    assert any("Ada Lovelace" in line for line in out_lines)

    # Unknown label is not handled.
    assert journey_cli.dispatch("Nope", "secondary") is False


def test_warehouse_api_role_gating(monkeypatch):
    from flask import Flask

    from education_system.platform.features.analytics import warehouse as wh_mod
    from education_system.platform.delivery.api import auth as api_auth
    from education_system.platform.delivery.api.warehouse_routes import warehouse_bp

    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-for-warehouse-api-0123456789abcdef")

    class _FakeWH:
        def summary(self):
            return {"attached_systems": ["nursery"], "headcount": {},
                    "retention_funnel": {}, "progression_rates": {}}

    monkeypatch.setattr(wh_mod, "Warehouse", _FakeWH)

    app = Flask(__name__)
    app.register_blueprint(warehouse_bp, url_prefix="/api/v1/warehouse")
    client = app.test_client()

    def _auth(role):
        tok = api_auth.generate_token(
            1, "t", [{"system_key": "university", "role": role}])
        return {"Authorization": f"Bearer {tok}"}

    # Unauthenticated → 401.
    assert client.get("/api/v1/warehouse/summary").status_code == 401
    # Student / parent → 403.
    for role in ("student", "parent"):
        assert client.get("/api/v1/warehouse/summary",
                          headers=_auth(role)).status_code == 403
    # Staff → 200 with the summary payload.
    r = client.get("/api/v1/warehouse/summary", headers=_auth("staff"))
    assert r.status_code == 200
    assert r.get_json()["attached_systems"] == ["nursery"]


def test_k12_clis_expose_cross_system_menu():
    """Each K-12 CLI surfaces the Student Journey item."""
    from education_system.systems.nursery import menu as nursery_menu
    from education_system.systems.primary import cli_main as primary_cli
    from education_system.systems.secondary import cli_main as secondary_cli
    from education_system.systems.sixth_form.interfaces.cli import (
        cli_main as college_cli,
    )

    def _labels(categories):
        out = []
        for _cat, items in categories:
            out.extend(items)
        return out

    assert "Student Journey" in _labels(nursery_menu.NAV_CATEGORIES)
    for cli in (primary_cli, secondary_cli, college_cli):
        labels = _labels(cli.CATEGORIES)
        assert "Student Journey" in labels
        assert "Promote to Next System" in labels

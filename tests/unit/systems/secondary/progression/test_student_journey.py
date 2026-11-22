"""A pupil's learner journey (modules.progression.domain.student_journey).

The platform's identity registry, transfer queue and Learner 360 run for
real against a temporary auth.db (passed as ``db_path`` and patched as the
platform default); Learner 360 reads only this test's secondary database.
The merge itself is the platform's and would re-stamp records in other
systems' databases, so it is replaced by a recorder here.
"""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import identity_service as IDS
from education_system.platform.cross_system import transitions as T
from education_system.systems.secondary.modules.progression.domain import student_journey as SJ
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")
ODD = Principal(username="who", role="caretaker")
PARENT = Principal(username="mum", role="parent")


@pytest.fixture
def env(tmp_path, monkeypatch):
    from education_system.platform.identity.auth import db as auth_db
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    platform_db = str(tmp_path / "platform_auth.db")
    monkeypatch.setattr(auth_db, "PLATFORM_AUTH_DB_FILE", platform_db)
    initialise_auth_db(platform_db)
    yield {"db": platform_db, "paths": {"secondary": str(tmp_path / "secondary.db")}}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _pupil(first="Ava", last="Stone", dob="2012-03-04", upn=None):
    return P.create_pupil({"legal_first_name": first, "legal_last_name": last,
                           "date_of_birth": dob, "gender": "Female", "year_group": 9,
                           "admission_date": "2023-09-01", "upn": upn}, actor=ADMIN)


def test_unlinked_pupil_shows_possible_journeys_then_links(env):
    db = env["db"]
    p = _pupil()
    jid = IDS.get_or_create_journey(first_name="Ava", last_name="Stone",
                                    date_of_birth="2012-03-04", system="primary",
                                    student_id="P7", db_path=db)
    j = SJ.journey(p.pupil_id, actor=TEACHER, db_path=db)
    assert not j.linked and j.candidates[0]["journey_id"] == jid
    assert j.candidates[0]["_reason"] == "same name and date of birth"
    with pytest.raises(SJ.PermissionDenied):
        SJ.link(p.pupil_id, jid, actor=TEACHER, db_path=db)
    SJ.link(p.pupil_id, jid, actor=ADMIN, db_path=db)
    j = SJ.journey(p.admission_no, actor=TEACHER, db_path=db)
    assert j.journey_id == jid
    held = {s.system: s for s in j.systems}
    assert held["primary"].student_ids == ("P7",) and held["secondary"].held
    assert not held["university"].held
    assert [s.system for s in j.systems][:3] == ["nursery", "primary", "secondary"]
    assert SJ.history(p.pupil_id)[0]["action"] == "link"
    assert "Primary School" in SJ.journey_text(j)


def test_register_and_wrong_dob_refused(env):
    db = env["db"]
    p = _pupil(first="Ben", last="Cole", dob="2011-01-01")
    other = IDS.get_or_create_journey(first_name="Ben", last_name="Cole",
                                      date_of_birth="2011-02-02", system="primary",
                                      student_id="P8", db_path=db)
    with pytest.raises(SJ.ValidationError, match="date of birth"):
        SJ.link(p.pupil_id, other, actor=ADMIN, db_path=db)
    jid = SJ.register(p.pupil_id, actor=ADMIN, db_path=db)
    assert jid != other and SJ.journey_id_for(p.pupil_id, db_path=db) == jid
    assert SJ.register(p.pupil_id, actor=ADMIN, db_path=db) == jid     # idempotent


def test_learner_360_is_tiered_and_unknown_roles_fail_closed(env):
    db = env["db"]
    p = _pupil()
    SJ.register(p.pupil_id, actor=ADMIN, db_path=db)
    staff = SJ.learner_view(p.pupil_id, actor=TEACHER, db_path=db, db_paths=env["paths"])
    assert staff["found"] and staff["viewer"]["tier"] == "staff"
    assert staff["support"] is not None and staff["lineage"] is not None
    assert any(r["system"] == "secondary" for r in staff["records"])
    assert SJ.viewer_role(Principal("x", None)) == "unknown"
    # an unknown role never gets the internal (everything) view
    from education_system.platform.cross_system import learner_360
    v = learner_360.build_learner_360(SJ.journey_id_for(p.pupil_id, db_path=db),
                                      viewer_role=SJ.viewer_role(ODD), auth_db=db,
                                      db_paths=env["paths"])
    assert v["viewer"]["tier"] == "external" and v["support"] is None
    with pytest.raises(SJ.PermissionDenied):
        SJ.learner_view(p.pupil_id, actor=ODD, db_path=db, db_paths=env["paths"])
    with pytest.raises(SJ.PermissionDenied):
        SJ.learner_view(p.pupil_id, actor=PARENT, db_path=db, db_paths=env["paths"])
    unlinked = _pupil(first="Cy", last="Dee", dob="2012-05-05")
    assert SJ.learner_view(unlinked.pupil_id, actor=TEACHER, db_path=db)["found"] is False
    assert "Ava Stone" in SJ.learner_text(staff)


def test_transfers_in_and_out(env):
    db = env["db"]
    p = _pupil()
    jid = SJ.register(p.pupil_id, actor=ADMIN, db_path=db)
    T.start_transition(journey_id=jid, source_system="primary", destination_system="secondary",
                       db_path=db)
    out = T.start_transition(journey_id=jid, source_system="secondary",
                             destination_system="sixth_form", db_path=db)
    T.cancel(out["transition_id"], reason="changed mind", db_path=db)
    rows = SJ.transfers(p.pupil_id, actor=TEACHER, db_path=db)
    assert [(r.direction, r.status) for r in rows] == [("in", "expected"), ("out", "cancelled")]
    assert rows[0].label == "Primary School -> Secondary School"
    ev = SJ.transfer_events(rows[1].transition_id, actor=TEACHER, db_path=db)
    assert [e["step"] for e in ev][-1] == "cancelled"


def test_duplicates_admin_only_merge_and_dismiss(env, monkeypatch):
    db = env["db"]
    p = _pupil()
    jid = SJ.register(p.pupil_id, actor=ADMIN, db_path=db)
    # the same child registered by primary with a typo in the first name
    dup = IDS.get_or_create_journey(first_name="Avah", last_name="Stone",
                                    date_of_birth="2012-03-04", system="primary",
                                    student_id="P9", db_path=db)
    with pytest.raises(SJ.PermissionDenied):
        SJ.duplicates(p.pupil_id, actor=TEACHER, db_path=db)
    rows = SJ.duplicates(p.pupil_id, actor=ADMIN, db_path=db)
    assert rows and {rows[0]["journey_id"], rows[0]["duplicate_id"]} == {jid, dup}
    calls = []
    monkeypatch.setattr(IDS, "merge_journeys", lambda *a, **k: calls.append((a, k)) or {})
    with pytest.raises(SJ.ValidationError):
        SJ.merge(jid, dup, actor=ADMIN, reason=" ", db_path=db)
    SJ.merge(jid, dup, actor=ADMIN, reason="same child, typo", db_path=db)
    (args, kw), = calls
    assert args == (jid, dup) and kw["actor"] == "admin2" and kw["db_path"] == db
    assert kw["audit_db_path"].endswith("audit.db") and kw["audit_db_path"].startswith(
        db.rsplit("/", 1)[0])
    with pytest.raises(SJ.PermissionDenied):
        SJ.merge(jid, dup, actor=TEACHER, reason="x", db_path=db)
    SJ.not_duplicate(jid, dup, actor=ADMIN, reason="twins", db_path=db)
    assert SJ.duplicates(p.pupil_id, actor=ADMIN, db_path=db) == []
    assert [h["action"] for h in SJ.history()][:2] == ["not_duplicate", "merge"]

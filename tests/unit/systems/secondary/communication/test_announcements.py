"""Announcements (modules.communication.domain.announcements)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.communication.domain import announcements as AN
from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
HEAD = Principal(username="head", role="teacher")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("head", "Mr Head"))]
TODAY = dt.date.today()


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: LOGINS)
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _pupil(year=9, form="9A"):
    return P.create_pupil({
        "legal_first_name": f"Kid{year}{form}", "legal_last_name": "Notice",
        "date_of_birth": "2012-01-15", "gender": "Male", "year_group": year,
        "form_group": form, "admission_date": "2023-09-01"}, actor=ADMIN)


def _draft(actor=ANN, **extra):
    return AN.create({"title": "Sports day", "body": "Bring a water bottle.",
                      "audiences": "year 9", **extra}, actor=actor)


def test_old_fields_rules_lists_and_summary():
    a = _draft(priority="4", category="Sport", pinned=True)
    assert (a.status, a.priority_label, a.audience_text, a.author) == (
        "Draft", "High", "Year 9", "ann")
    assert a.pinned and not a.is_live
    with pytest.raises(AN.ValidationError) as e:
        AN.create({"title": "", "body": "", "audiences": "aliens", "priority": "9",
                   "publish_on": "2026-02-01", "expires_on": "2026-01-01"}, actor=ANN)
    text = " ".join(e.value.problems)
    for bit in ("Title is required", "empty", "Unknown audience", "Priority must be",
                "expire before"):
        assert bit in text
    assert AN.parse_audiences("All staff, parents, form 9a, year 7", []) == [
        "staff", "parents", "form:9A", "year:7"]
    with pytest.raises(AN.PermissionDenied):
        AN.create({"title": "x", "body": "y", "audiences": "staff"},
                  actor=Principal(username="kid", role="student"))
    pub = AN.publish(a.announcement_id, actor=ADMIN)
    assert pub.status == "Published" and pub.is_live and pub.published_on == TODAY.isoformat()
    later = AN.schedule(_draft().announcement_id,
                        (TODAY + dt.timedelta(days=3)).isoformat(), actor=ADMIN)
    assert later.status == "Scheduled" and not later.is_live
    assert [x.announcement_id for x in AN.list_announcements(scope="scheduled")] == [
        later.announcement_id]
    assert [x.announcement_id for x in AN.list_announcements(scope="pinned")] == [
        a.announcement_id]
    AN.toggle_banner(a.announcement_id, actor=ADMIN)
    assert AN.list_announcements(scope="banners")[0].announcement_id == a.announcement_id
    old = AN.publish(_draft(expires_on=(TODAY + dt.timedelta(days=1)).isoformat())
                     .announcement_id, actor=ADMIN)
    with database.connect() as conn:   # its expiry date passes
        conn.execute("UPDATE announcements SET expires_on = ? WHERE announcement_id = ?",
                     ((TODAY - dt.timedelta(days=1)).isoformat(), old.announcement_id))
    assert AN.get(old.announcement_id).is_expired
    assert AN.auto_expire(actor=ADMIN) == 1
    assert AN.get(old.announcement_id).status == "Expired"
    assert AN.list_announcements(search="water bottle", scope="live")[0].pinned
    s = AN.summary()
    assert s.total == 3 and s.live_now == 1 and s.scheduled == 1 and s.pinned == 1
    assert AN.withdraw(a.announcement_id, actor=ADMIN).status == "Withdrawn"
    assert AN.archive(a.announcement_id, actor=ADMIN).status == "Archived"
    copy = AN.duplicate(a.announcement_id, actor=ANN)
    assert copy.status == "Draft" and copy.title.startswith("Copy of")
    assert AN.delete(copy.announcement_id, actor=ANN)


def test_who_publishes_head_of_year_and_drafts():
    d = _draft()
    with pytest.raises(AN.PermissionDenied):
        AN.publish(d.announcement_id, actor=ANN)       # plain staff draft only
    AN.update(d.announcement_id, {"body": "Changed"}, actor=ANN)   # own draft
    with pytest.raises(AN.PermissionDenied):
        AN.update(d.announcement_id, {"body": "x"}, actor=HEAD)
    YG.update(9, {"head_of_year": "Mr Head"}, actor=ADMIN)
    _pupil(9, "9A")
    assert AN.can_publish(HEAD, ["year:9", "form:9A"])
    assert not AN.can_publish(HEAD, ["year:9", "staff"])
    assert AN.publish(d.announcement_id, actor=HEAD).status == "Published"
    school = _draft(audiences="parents")
    with pytest.raises(AN.PermissionDenied):
        AN.publish(school.announcement_id, actor=HEAD)
    with pytest.raises(AN.PermissionDenied):
        AN.delete(d.announcement_id, actor=ANN)        # published: editors only
    with pytest.raises(AN.ValidationError):
        AN.update(d.announcement_id, {"audiences": "parents"}, actor=HEAD)


def test_audiences_read_receipts_and_portal_feed():
    ava = _pupil(9, "9A")
    _pupil(8, "8B")
    C.add_contact(ava.pupil_id, {"full_name": "Mum Notice", "relationship": "Mother",
                                 "email": "mum@home.org"}, actor=ADMIN)
    mum = Principal(username=PA.links_for_pupil(ava.pupil_id)[0].username, role="parent")
    staff = AN.publish(_draft(audiences="staff", requires_acknowledgement=True)
                       .announcement_id, actor=ADMIN)
    y9 = AN.publish(_draft(audiences="year 9").announcement_id, actor=ADMIN)
    y8 = AN.publish(_draft(audiences="form 8B").announcement_id, actor=ADMIN)
    assert [a.announcement_id for a in AN.active_for(ANN)] == [staff.announcement_id]
    assert [a.announcement_id for a in AN.active_for(mum)] == [y9.announcement_id]
    assert y8.announcement_id not in [a.announcement_id for a in AN.active_for(mum)]
    assert AN.mark_read(y9.announcement_id, mum) is True
    assert AN.mark_read(y9.announcement_id, mum) is False      # counted once
    assert AN.mark_read(y8.announcement_id, mum) is False      # not for her
    assert AN.get(y9.announcement_id).view_count == 1
    assert AN.unread_for(mum) == []
    assert [a.announcement_id for a in AN.needs_acknowledgement(ANN)] == [
        staff.announcement_id]
    AN.acknowledge(staff.announcement_id, ANN)
    assert AN.needs_acknowledgement(ANN) == []
    r = AN.receipts(staff.announcement_id, actor=ADMIN)
    assert r["acknowledged"] == 1 and r["read"][0]["name"] == "Ann Teacher"
    assert r["staff_not_read"] == ["Mr Head"]
    assert [a.announcement_id for a in AN.feed_for_audience("staff")] == [
        staff.announcement_id]


def test_email_to_audience_and_export(tmp_path):
    ava = _pupil(9, "9A")
    C.add_contact(ava.pupil_id, {"full_name": "Mum Notice", "relationship": "Mother",
                                 "email": "mum@home.org"}, actor=ADMIN)
    d = _draft(audiences="staff, year 9")
    with pytest.raises(AN.ValidationError):
        AN.email_audience(d.announcement_id, actor=ADMIN)   # not published yet
    AN.publish(d.announcement_id, actor=ADMIN)
    with pytest.raises(AN.PermissionDenied):
        AN.email_audience(d.announcement_id, actor=ANN)
    res = AN.email_audience(d.announcement_id, actor=ADMIN)
    assert res["emails"] == 3                    # two staff and mum
    with database.connect() as conn:
        rows = conn.execute("SELECT address, body FROM email_recipients WHERE message_id = ?",
                            (res["message_id"],)).fetchall()
    assert {r[0] for r in rows} == {"ann@school.org", "head@school.org", "mum@home.org"}
    assert all("Bring a water bottle." in r[1] for r in rows)
    assert AN.get(d.announcement_id).emailed_at
    out = tmp_path / "a.csv"
    assert AN.export_csv(out, actor=ADMIN) == 1
    assert list(csv.reader(out.open()))[0][1] == "title"
    assert {h["action"] for h in AN.history(d.announcement_id)} >= {"create", "publish", "email"}

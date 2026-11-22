"""Letters home (modules.communication.domain.letters)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.communication.domain import letters as L
from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
LOGINS = [{"username": "ann", "display_name": "Ann Teacher", "email": "ann@school.org",
           "role": "teacher"}]
TODAY = dt.date.today()
LATER = (TODAY + dt.timedelta(days=7)).isoformat()


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


_n = 0


def _pupil(year=8, form="8A"):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Kid{_n}", "legal_last_name": f"Letter{_n:03d}",
        "date_of_birth": "2013-01-15", "gender": "Female", "year_group": year,
        "form_group": form, "admission_date": "2024-09-01"}, actor=ADMIN)


@pytest.fixture
def family():
    ava, ben, cal = _pupil(), _pupil(), _pupil(form="8B")
    for p in (ava, ben):   # siblings
        C.add_contact(p.pupil_id, {"full_name": "Mum Letter", "relationship": "Mother",
                                   "email": "mum@home.org"}, actor=ADMIN)
    C.add_contact(cal.pupil_id, {"full_name": "Dad Paper", "relationship": "Father",
                                 "phone": "01234 567890"}, actor=ADMIN)
    return {"ava": ava, "ben": ben, "cal": cal}


def _template(actor=ADMIN, **extra):
    return L.create_template({
        "name": "Trip consent", "category": "Trip / Visit", "status": "Active",
        "subject_line": "Trip for {first_name}",
        "body": "Dear {parent_name},\n\n{pupil_name} ({form}) is invited on the {trip} "
                "trip on {{trip_date}}. Please reply by {reply_by}.",
        "merge_fields": "trip, trip_date", "reply_slip": True,
        "reply_question": "May your child go on the trip?", **extra}, actor=actor)


def test_template_library_old_actions_and_merge_rules():
    t = _template()
    assert t.custom_fields == ["trip", "trip_date"]
    assert t.detected_placeholders[:3] == ["first_name", "parent_name", "pupil_name"]
    with pytest.raises(L.ValidationError) as e:
        L.create_template({"name": "Trip consent", "subject_line": "", "body": "Hi {nmae}",
                           "reply_slip": True}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("already exists", "Subject line is required", "Unknown merge field",
                "needs its yes/no question"):
        assert bit in text
    with pytest.raises(L.ValidationError):        # staff draft only
        L.create_template({"name": "Mine", "subject_line": "x", "body": "y",
                           "status": "Active"}, actor=ANN)
    mine = L.create_template({"name": "Mine", "subject_line": "x", "body": "y"}, actor=ANN)
    L.update_template(mine.template_id, {"body": "z"}, actor=ANN)
    with pytest.raises(L.PermissionDenied):
        L.activate(mine.template_id, actor=ANN)
    assert L.activate(mine.template_id, actor=ADMIN).status == "Active"
    with pytest.raises(L.PermissionDenied):
        L.update_template(mine.template_id, {"body": "q"}, actor=ANN)   # no longer a draft
    copy = L.duplicate(t.template_id, actor=ANN)
    assert copy.status == "Draft" and copy.name == "Trip consent (copy)"
    assert L.retire(copy.template_id, actor=ADMIN).status == "Retired"
    assert [x.template_id for x in L.list_templates(scope="archived")] == [copy.template_id]
    r = L.render(t, {"first_name": "Ava", "trip": "Zoo"})
    assert r.subject == "Trip for Ava" and "pupil_name" in r.missing
    assert L.record_use(t.template_id, actor=ANN).use_count == 1
    s = L.summary()
    assert s.total == 3 and s.active == 2 and s.retired == 1 and s.with_reply_slip == 2
    assert L.delete_template(copy.template_id, actor=ADMIN)


def test_mail_merge_preview_send_and_print_copies(family):
    ava, ben, cal = family["ava"], family["ben"], family["cal"]
    t = _template()
    pv = L.preview(t.template_id, ava.pupil_id, {"trip": "Zoo", "trip_date": "1 May"},
                   reply_by=LATER)
    assert pv.subject == f"Trip for {ava.legal_first_name}"
    assert "Dear Mum Letter" in pv.body and "REPLY SLIP" in pv.body and "8A" in pv.body
    with pytest.raises(L.ValidationError) as e:
        L.send(t.template_id, actor=ADMIN, form="8A", custom={"trip": "Zoo"})
    assert "Fill in: trip_date" in " ".join(e.value.problems)
    with pytest.raises(L.PermissionDenied):
        L.send(t.template_id, actor=ANN, year=8, custom={"trip": "Zoo", "trip_date": "1 May"},
               reply_by=LATER)
    chk = L.check_send(t.template_id, actor=ADMIN, year=8, reply_by=LATER,
                       custom={"trip": "Zoo", "trip_date": "1 May"})
    assert chk["with_email"] == 2 and chk["emails"] == 1 and chk["no_email"] == [cal]
    res = L.send(t.template_id, actor=ADMIN, year=8, reply_by=LATER,
                 custom={"trip": "Zoo", "trip_date": "1 May"})
    assert res["letters"] == 3 and res["emails"] == 1
    assert [p.pupil_id for p in res["no_email"]] == [cal.pupil_id]
    with database.connect() as conn:
        body = conn.execute("SELECT body FROM email_recipients WHERE message_id = ?",
                            (res["message_id"],)).fetchone()[0]
    # One e-mail for the sibling pair, both letters in it.
    assert ava.legal_first_name in body and ben.legal_first_name in body
    assert "Zoo trip on 1 May" in body and "Reply needed" in body
    text = L.print_copies(res["send_id"], actor=ADMIN)
    assert cal.legal_first_name in text and "Dear Dad Paper" in text and "REPLY SLIP" in text
    assert ava.legal_first_name not in text
    assert L.recipients(res["send_id"], no_email_only=True)[0].printed_at
    hist = L.for_pupil(ava.pupil_id)
    assert len(hist) == 1 and hist[0].template_name == "Trip consent"
    assert L.get_template(t.template_id).use_count == 3
    # Any member of staff can send to pupils they choose.
    own = L.send(t.template_id, actor=ANN, pupil_ids=[ava.admission_no], reply_by=LATER,
                 custom={"trip": "Zoo", "trip_date": "1 May"})
    assert own["letters"] == 1


def test_reply_slips_portal_reply_chase_and_export(family, tmp_path):
    ava, ben, cal = family["ava"], family["ben"], family["cal"]
    t = _template()
    res = L.send(t.template_id, actor=ADMIN, form="8A", reply_by=LATER,
                 custom={"trip": "Zoo", "trip_date": "1 May"})
    rows = {r.pupil_id: r for r in L.recipients(res["send_id"])}
    mum = Principal(username=PA.links_for_pupil(ava.pupil_id)[0].username, role="parent")
    assert L.reply_for_family(mum, rows[ava.pupil_id].recipient_id, "yes").reply == "Yes"
    with pytest.raises(L.PermissionDenied):
        L.reply_for_family(Principal(username="stranger", role="parent"),
                           rows[ben.pupil_id].recipient_id, "no")
    assert [r.pupil_id for r in L.chase_list(res["send_id"])] == [ben.pupil_id]
    ch = L.chase(res["send_id"], actor=ADMIN)
    assert ch["emails"] == 1
    with database.connect() as conn:
        body = conn.execute("SELECT body FROM email_recipients WHERE message_id = ?",
                            (ch["message_id"],)).fetchone()[0]
    assert "May your child go on the trip?" in body and ben.legal_first_name in body
    assert L.get_recipient(rows[ben.pupil_id].recipient_id).chase_count == 1
    L.record_reply(rows[ben.pupil_id].recipient_id, "No", actor=ANN, note="Phoned")
    assert L.reply_summary(res["send_id"]) == {"letters": 2, "yes": 1, "no": 1,
                                               "no_reply": 0, "rate": 100}
    with pytest.raises(L.ValidationError):
        L.chase(res["send_id"], actor=ADMIN)
    with pytest.raises(L.ValidationError):
        L.record_reply(rows[ben.pupil_id].recipient_id, "maybe", actor=ANN)
    out = tmp_path / "replies.csv"
    assert L.export_csv(res["send_id"], out, actor=ADMIN) == 2
    assert list(csv.reader(out.open()))[0][8] == "reply"
    assert {h["action"] for h in L.history(send_id=res["send_id"])} >= {"send", "reply",
                                                                         "chase"}
    assert cal.pupil_id not in rows

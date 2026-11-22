"""Alumni office rules: roles and access, opt-in directory and what it
shows, consent and suppression, deaths, data export and erasure (Gift Aid
retention), the graduate-to-alumnus transition, newsletters with
unsubscribe, gifts / Gift Aid declarations and claims / refunds / pledges,
chapters, mentor vetting and matching with student consent and concerns,
and moderation. Temporary databases only."""

import sqlite3

import pytest

from education_system.systems.university.application.alumni import access as aa
from education_system.systems.university.application.alumni import comms as ac
from education_system.systems.university.application.alumni import community as acm
from education_system.systems.university.application.alumni import giving as ag
from education_system.systems.university.application.alumni import records as ar

#: The university's existing alumni tables, before migration e6a8c0d2f4b7.
EXISTING = [
'CREATE TABLE alumni ( alumni_id TEXT PRIMARY KEY, student_id TEXT, email_address TEXT, title TEXT, first_name TEXT, middle_name TEXT, last_name TEXT, gender TEXT, dob TEXT, graduation_year INTEGER, degree_earned TEXT, current_employer TEXT, job_title TEXT, industry TEXT, address TEXT, city TEXT, country TEXT, phone TEXT, linkedin_url TEXT, date_registered TEXT, is_donor BOOLEAN, is_mentor BOOLEAN, is_board_member BOOLEAN, profile_photo TEXT, bio TEXT, skills TEXT, achievements TEXT, privacy_level INTEGER DEFAULT 1, engagement_score INTEGER DEFAULT 0, last_activity TEXT, social_media_links TEXT, is_ambassador BOOLEAN DEFAULT 0 )',
'CREATE TABLE alumni_directory_settings ( alumni_id TEXT PRIMARY KEY, show_contact_info BOOLEAN DEFAULT 1, show_employment BOOLEAN DEFAULT 1, show_education BOOLEAN DEFAULT 1, searchable BOOLEAN DEFAULT 1, networking_available BOOLEAN DEFAULT 1, mentor_available BOOLEAN DEFAULT 0 )',
'CREATE TABLE donations ( donation_id INTEGER PRIMARY KEY AUTOINCREMENT, alumni_id TEXT, amount REAL, donation_date TEXT, campaign TEXT, campaign_id INTEGER, payment_method TEXT, is_recurring BOOLEAN, recurring_frequency TEXT, receipt_sent BOOLEAN, notes TEXT, donation_type TEXT DEFAULT \'general\', tribute_type TEXT, tribute_name TEXT, employer_match_eligible BOOLEAN DEFAULT 0, employer_match_amount REAL DEFAULT 0.0, recognition_level TEXT, is_gift_aided INTEGER DEFAULT 0, "campaign_name" TEXT, "goal_amount" REAL, "donor_name" TEXT )',
'CREATE TABLE alumni_donations ( donation_id INTEGER PRIMARY KEY AUTOINCREMENT, alumni_id INTEGER NOT NULL, donation_amount REAL NOT NULL, donation_date TEXT DEFAULT CURRENT_DATE, donation_type TEXT NOT NULL, fund_designation TEXT, campaign_id INTEGER, payment_method TEXT, is_recurring BOOLEAN DEFAULT 0, recurrence_frequency TEXT, tax_receipt_sent BOOLEAN DEFAULT 0, acknowledgment_sent BOOLEAN DEFAULT 0, "amount" REAL, "payment_status" TEXT, "purpose" TEXT, "user_id" INTEGER )',
'CREATE TABLE fundraising_campaigns ( campaign_id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_name TEXT, description TEXT, goal_amount REAL, current_amount REAL DEFAULT 0.0, start_date TEXT, end_date TEXT, created_by TEXT, created_date TEXT, status TEXT DEFAULT \'active\', category TEXT, is_featured BOOLEAN DEFAULT 0 , "id" INTEGER, "target_amount" DECIMAL(10,2))',
"CREATE TABLE regional_chapters ( chapter_id INTEGER PRIMARY KEY AUTOINCREMENT, chapter_name TEXT, location TEXT, coordinator_id TEXT, description TEXT, created_date TEXT, member_count INTEGER DEFAULT 0, coordinator_name TEXT, contact_email TEXT, created_by TEXT, status TEXT DEFAULT 'active' )",
"CREATE TABLE chapter_memberships ( membership_id INTEGER PRIMARY KEY AUTOINCREMENT, chapter_id INTEGER, alumni_id TEXT, join_date TEXT, role TEXT DEFAULT 'member' )",
"CREATE TABLE chapter_members ( membership_id INTEGER PRIMARY KEY AUTOINCREMENT, chapter_id INTEGER, member_id TEXT, role TEXT DEFAULT 'member', join_date TEXT DEFAULT (datetime('now')), status TEXT DEFAULT 'active' )",
'CREATE TABLE mentorships ( mentorship_id INTEGER PRIMARY KEY AUTOINCREMENT, mentor_id TEXT, mentee_id TEXT, start_date TEXT, end_date TEXT, status TEXT, focus_area TEXT, notes TEXT, match_score REAL DEFAULT 0.0, meeting_frequency TEXT, communication_preference TEXT, goals TEXT )',
'CREATE TABLE alumni_forum ( post_id INTEGER PRIMARY KEY AUTOINCREMENT, author_id TEXT, title TEXT, content TEXT, category TEXT, post_date TEXT, last_updated TEXT, reply_count INTEGER DEFAULT 0, view_count INTEGER DEFAULT 0, is_pinned BOOLEAN DEFAULT 0 )',
'CREATE TABLE forum_replies ( reply_id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, author_id TEXT, content TEXT, reply_date TEXT, parent_reply_id INTEGER, "author_name" TEXT, "created_date" TEXT )',
'CREATE TABLE alumni_stories ( story_id INTEGER PRIMARY KEY AUTOINCREMENT, alumni_id TEXT, title TEXT, content TEXT, story_type TEXT, publish_date TEXT, is_featured BOOLEAN DEFAULT 0, view_count INTEGER DEFAULT 0, category TEXT )',
'CREATE TABLE "photo_gallery" ( photo_id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, uploaded_by TEXT, photo_path TEXT, caption TEXT, upload_date TEXT, is_featured BOOLEAN DEFAULT 0, "status" TEXT )',
"CREATE TABLE newsletters ( newsletter_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, template_id INTEGER, target_audience TEXT, send_date TEXT, created_date TEXT, created_by TEXT, status TEXT DEFAULT 'draft', open_rate REAL DEFAULT 0.0, click_rate REAL DEFAULT 0.0 )",
"CREATE TABLE alumni_transition_steps ( student_id TEXT NOT NULL, step_name TEXT NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}', completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(student_id, step_name) )",
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, "
    "email_address TEXT, status TEXT)",
    "CREATE TABLE staff (id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, email TEXT, "
    "role TEXT, status TEXT DEFAULT 'active')",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT, service_account INTEGER DEFAULT 0)",
    "CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER, "
    "subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)",
]
GRADS = ("G1", "G2", "G3")


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in EXISTING:
        c.execute(ddl)
    for n, sid in enumerate(GRADS + ("S1",), 1):
        c.execute("INSERT INTO students VALUES (?, ?, 'Person', ?, ?)",
                  (sid, f"First{n}", f"{sid.lower()}@uni.test",
                   "Active" if sid == "S1" else "Completed"))
        c.execute("INSERT INTO users (username, role, student_id) VALUES (?, ?, ?)",
                  (sid, "student" if sid == "S1" else "alumni", sid))
    for username in ("office", "fund", "coord", "mod", "lecturer"):
        c.execute("INSERT INTO staff (username, name, role) VALUES (?, ?, 'staff')",
                  (username, username.title()))
        c.execute("INSERT INTO users (username, role) VALUES (?, 'staff')", (username,))
    c.execute("INSERT INTO users (username, role) VALUES ('admin', 'admin')")
    aa.ensure(c)
    admin = who(c, "admin", "admin")
    for username, role in (("office", "alumni_office"), ("fund", "fundraising"),
                           ("coord", "mentoring_coordinator"), ("mod", "moderator")):
        aa.grant_role(c, admin, username, role)
    for sid in GRADS:
        ar.register(c, admin, sid, {"graduation_year": 2025, "degree_earned": "BSc"})
    c.commit()
    yield c
    c.close()


def who(c, username, role="staff"):
    return aa.user(c, username, role)


def grad(c, sid):
    return aa.user(c, sid, "alumni")


def refused(fn, *args, **kwargs) -> str:
    with pytest.raises((ValueError, PermissionError)) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _consent(c, sid, email=True):
    if email:
        ar.update_profile(c, grad(c, sid), sid, {"email_address": f"{sid.lower()}@home.test"})
    ar.set_consent(c, grad(c, sid), sid, True)


# ── access ──────────────────────────────────────────────────────────────


def test_roles(conn):
    lecturer = who(conn, "lecturer")
    assert not lecturer.is_staff_role and not lecturer.is_alumnus
    assert refused(ar.listing, conn, lecturer)
    assert refused(aa.grant_role, conn, who(conn, "fund"), "lecturer", "moderator")
    assert who(conn, "office").is_fundraiser and who(conn, "office").is_moderator
    assert grad(conn, "G1").alumni_id == "G1"
    assert who(conn, "S1", "student").alumni_id is None


# ── directory and profile ───────────────────────────────────────────────


def test_directory_is_opt_in_and_shows_only_what_was_chosen(conn):
    g1, g2 = grad(conn, "G1"), grad(conn, "G2")
    assert ar.search_directory(conn, g2) == []
    ar.update_profile(conn, g1, "G1", {"phone": "0700", "current_employer": "Acme",
                                        "address": "1 Home Road"})
    ar.save_directory_settings(conn, g1, "G1", {"searchable": 1, "show_employment": 1})
    [entry] = ar.search_directory(conn, g2)
    assert entry["current_employer"] == "Acme"
    assert "phone" not in entry and "address" not in entry and "dob" not in entry
    assert refused(ar.save_directory_settings, conn, who(conn, "office"), "G1", {})
    with pytest.raises(PermissionError):
        ar.profile(conn, g1, "G2")
    assert refused(ar.update_profile, conn, g2, "G1", {"bio": "x"})


# ── consent, death, data rights ─────────────────────────────────────────


def test_consent_needs_a_source_when_staff_record_it(conn):
    assert "How the consent" in refused(ar.set_consent, conn, who(conn, "office"), "G1", True)
    ar.set_consent(conn, who(conn, "office"), "G1", True, "phone call")
    assert conn.execute("SELECT consent_source FROM alumni WHERE alumni_id = 'G1'").fetchone()[
        0] == "phone call"


def test_death_suppresses_everything(conn):
    office = who(conn, "office")
    _consent(conn, "G1")
    ar.save_directory_settings(conn, grad(conn, "G1"), "G1", {"searchable": 1})
    pledge = ag.create_pledge(conn, grad(conn, "G1"), "G1", 10, "monthly", 6)
    ar.record_deceased(conn, office, "G1", "2026-09-01", "family letter")
    assert ar.search_directory(conn, grad(conn, "G2")) == []
    assert ac.suppression_reason(aa.alumnus(conn, "G1")) == "deceased"
    assert conn.execute("SELECT status FROM donation_pledges WHERE pledge_id = ?",
                        (pledge,)).fetchone()[0] == "cancelled"


def test_export_and_erasure(conn):
    g1 = grad(conn, "G1")
    data = ar.export(conn, g1, "G1")
    assert data["profile"]["alumni_id"] == "G1" and "gifts" in data
    assert refused(ar.export, conn, grad(conn, "G2"), "G1")
    ar.request_erasure(conn, g1, "G1")
    assert refused(ar.erase, conn, g1, "G1", "x")
    result = ar.erase(conn, who(conn, "office"), "G1", "subject request")
    row = aa.alumnus(conn, "G1")
    assert row["last_name"] == "Erased" and row["email_address"] is None
    assert result["gift_aid_kept_until"] is None
    assert ar.data_requests(conn, who(conn, "office")) == []


def test_erasure_keeps_gift_aid_records_six_years(conn):
    fund = who(conn, "fund")
    ag.add_declaration(conn, grad(conn, "G1"), "G1", full_name="G One", house="1",
                       postcode="ab1 2cd", taxpayer_confirmed=True)
    ag.record_gift(conn, fund, "G1", 100, gift_date="2026-03-01", gift_aid=True)
    claim = ag.build_claim(conn, fund, "2026-01-01", "2026-06-30")
    ag.submit_claim(conn, fund, claim["claim_id"], "HMRC-1")
    result = ar.erase(conn, who(conn, "office"), "G1", "request")
    assert result["gift_aid_kept_until"] == "2032-06-28"
    assert conn.execute("SELECT full_name FROM gift_aid_declarations").fetchone()[0] == "G One"


def test_transition_steps_on_conferral(conn):
    ar.on_conferral(conn, "G1", "2026-07-15")
    steps = ar.transition_status(conn, "G1")
    assert all(s["done"] for s in steps)
    assert aa.alumnus(conn, "G1")["graduate_outcomes_due"] == "2027-10-15"


# ── newsletters ─────────────────────────────────────────────────────────


def test_newsletters_go_only_to_consenting_unsuppressed_alumni(conn):
    office = who(conn, "office")
    _consent(conn, "G1")
    _consent(conn, "G2")
    ar.set_do_not_contact(conn, office, "G2", True, "asked by phone")
    preview = ac.preview(conn, office, {})
    assert preview["will_send"] == 1
    assert preview["suppressed"] == {"do not contact": 1, "consent not asked": 1}
    nid = ac.create(conn, office, "News", "Hello", {"year_from": 2020})
    result = ac.send(conn, office, nid)
    assert [e[0] for e in result["emails"]] == ["g1@home.test"]
    assert "Unsubscribe" in result["emails"][0][2]
    assert refused(ac.send, conn, office, nid)
    token = result["emails"][0][2].rsplit("/", 1)[1]
    stored = conn.execute("SELECT token_hash FROM alumni_unsubscribe_tokens").fetchone()[0]
    assert stored != token
    assert ac.unsubscribe(conn, token)["ok"]
    assert aa.alumnus(conn, "G1")["marketing_consent"] == 0
    assert not ac.unsubscribe(conn, "nonsense")["ok"]


def test_audience_filters_are_not_sql(conn):
    office = who(conn, "office")
    _consent(conn, "G1")
    preview = ac.preview(conn, office, {"degree_contains": "x' OR '1'='1", "nope": 1})
    assert preview["matching"] == 0


# ── giving ──────────────────────────────────────────────────────────────


def test_gift_aid_needs_a_covering_declaration(conn):
    fund = who(conn, "fund")
    assert "declaration" in refused(ag.record_gift, conn, fund, "G1", 50, gift_aid=True)
    assert "Tax" in refused(ag.add_declaration, conn, grad(conn, "G1"), "G1", full_name="G",
                            house="1", postcode="x")
    ag.add_declaration(conn, grad(conn, "G1"), "G1", full_name="G One", house="1",
                       postcode="ab1 2cd", made_on="2026-05-01", covers_past_four_years=False,
                       taxpayer_confirmed=True)
    assert "declaration" in refused(ag.record_gift, conn, fund, "G1", 50,
                                    gift_date="2026-04-01", gift_aid=True)
    result = ag.record_gift(conn, fund, "G1", 50, gift_date="2026-05-02", gift_aid=True)
    assert result["gift_aided"] and result["receipt_number"].startswith("GIFT-")
    assert refused(ag.record_gift, conn, grad(conn, "G1"), "G1", 5)


def test_claims_and_refund_adjustments(conn):
    fund = who(conn, "fund")
    ag.add_declaration(conn, grad(conn, "G1"), "G1", full_name="G One", house="1",
                       postcode="ab1 2cd", taxpayer_confirmed=True)
    first = ag.record_gift(conn, fund, "G1", 100, gift_date="2026-03-01", gift_aid=True)
    ag.record_gift(conn, fund, "G1", 40, gift_date="2026-03-02", gift_aid=True)
    claim = ag.build_claim(conn, fund, "2026-01-01", "2026-06-30")
    assert claim["claim_total"] == 35.0
    assert "draft" in refused(ag.build_claim, conn, fund, "2026-07-01", "2026-07-31")
    ag.submit_claim(conn, fund, claim["claim_id"], "HMRC-1")
    assert ag.refund_gift(conn, fund, first["donation_id"], "chargeback")["gift_aid_to_repay"] \
        == 25.0
    ag.record_gift(conn, fund, "G1", 20, gift_date="2026-08-01", gift_aid=True)
    second = ag.build_claim(conn, fund, "2026-07-01", "2026-12-31")
    assert second["adjustments"] == 25.0 and second["claim_total"] == -20.0


def test_campaign_totals_come_from_gifts(conn):
    fund = who(conn, "fund")
    cid = ag.save_campaign(conn, fund, {"campaign_name": "Bursaries", "goal_amount": 1000,
                                        "start_date": "2026-01-01"})
    gift = ag.record_gift(conn, fund, "G1", 250, campaign_id=cid)
    [campaign] = ag.campaigns(conn)
    assert campaign["raised"] == 250 and campaign["progress_pct"] == 25.0
    ag.refund_gift(conn, fund, gift["donation_id"], "mistake")
    assert ag.campaigns(conn)[0]["raised"] == 0


def test_pledges(conn):
    fund = who(conn, "fund")
    pid = ag.create_pledge(conn, grad(conn, "G1"), "G1", 10, "monthly", 2, start="2026-01-15")
    first = ag.record_pledge_payment(conn, fund, pid, paid_on="2026-01-15")
    assert first["next_due"] == "2026-02-15" and not first["pledge_completed"]
    assert ag.record_pledge_payment(conn, fund, pid, paid_on="2026-02-15")["pledge_completed"]
    assert refused(ag.record_pledge_payment, conn, fund, pid)
    summary = ag.donor_summary(conn, grad(conn, "G1"), "G1")
    assert summary["total"] == 20 and summary["recognition"] == "Friend"


# ── chapters and mentoring ──────────────────────────────────────────────


def test_chapters(conn):
    office = who(conn, "office")
    cid = acm.save_chapter(conn, office, {"chapter_name": "Leeds"})
    acm.join(conn, grad(conn, "G1"), cid)
    acm.join(conn, grad(conn, "G2"), cid)
    assert "already" in refused(acm.join, conn, grad(conn, "G1"), cid)
    assert refused(acm.members, conn, grad(conn, "G2"), cid)
    acm.set_leader(conn, office, cid, "G1")
    assert [m["alumni_id"] for m in acm.members(conn, grad(conn, "G1"), cid)][0] == "G1"
    acm.leave(conn, grad(conn, "G2"), cid)
    assert acm.chapters(conn)[0]["members"] == 1


def test_mentoring_needs_vetting_and_student_consent(conn):
    coord = who(conn, "coord")
    acm.offer_to_mentor(conn, grad(conn, "G1"), "accounting careers")
    assert "vetted" in refused(acm.propose_match, conn, coord, "G1", "S1")
    assert "training" in refused(acm.vet, conn, coord, "G1", True)
    acm.vet(conn, coord, "G1", True, training_completed=True)
    assert "current students" in refused(acm.propose_match, conn, coord, "G1", "G2")
    mid = acm.propose_match(conn, coord, "G1", "S1")
    assert acm.mentorships(conn, grad(conn, "G1")) == []          # not until accepted
    student = who(conn, "S1", "student")
    assert refused(acm.respond, conn, grad(conn, "G1"), mid, True)
    acm.respond(conn, student, mid, True)
    assert [m["status"] for m in acm.mentorships(conn, grad(conn, "G1"))] == ["active"]


def test_concerns_pause_and_escalation_ends_and_unvets(conn):
    coord = who(conn, "coord")
    acm.offer_to_mentor(conn, grad(conn, "G1"), "x")
    acm.vet(conn, coord, "G1", True, training_completed=True)
    mid = acm.propose_match(conn, coord, "G1", "S1")
    acm.respond(conn, who(conn, "S1", "student"), mid, True)
    assert refused(acm.raise_concern, conn, grad(conn, "G2"), mid, "x")
    concern = acm.raise_concern(conn, who(conn, "S1", "student"), mid, "made me uneasy")
    assert acm.mentorship(conn, mid)["status"] == "paused"
    acm.handle_concern(conn, coord, concern, "escalate", "referred to safeguarding")
    assert acm.mentorship(conn, mid)["status"] == "ended"
    assert not acm.vetted(conn, "G1")


# ── moderation ──────────────────────────────────────────────────────────


def test_stories_need_consent_and_approval_and_can_be_reported(conn):
    mod = who(conn, "mod")
    assert "Confirm" in refused(acm.submit_story, conn, grad(conn, "G1"), "T", "body")
    sid = acm.submit_story(conn, grad(conn, "G1"), "My path", "body", consent=True)
    assert acm.stories(conn) == []
    acm.review_story(conn, mod, sid, True)
    assert [s["story_id"] for s in acm.stories(conn)] == [sid]
    report = acm.report(conn, grad(conn, "G2"), "story", sid, "has my phone number")
    assert refused(acm.resolve, conn, grad(conn, "G2"), report, True)
    acm.resolve(conn, mod, report, True, "personal data")
    assert acm.stories(conn) == []


def test_photos_need_consent_before_featuring(conn):
    mod = who(conn, "mod")
    pid = conn.execute("INSERT INTO photo_gallery (uploaded_by, photo_path) VALUES ('G1', "
                       "'a.jpg')").lastrowid
    assert "consent" in refused(acm.feature_photo, conn, mod, pid)
    acm.confirm_photo_consent(conn, mod, pid)
    acm.feature_photo(conn, mod, pid)
    assert conn.execute("SELECT is_featured FROM photo_gallery").fetchone()[0] == 1

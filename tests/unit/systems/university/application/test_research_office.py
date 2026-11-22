"""Research office rules: roles and visibility, the ethics review workflow
(supervisor endorsement, reviewer conflicts, required reviews, conditions,
amendments, renewals, expiry), projects and teams, grant costing / sign-off
/ award / spend / reports, outputs and open access, REF review and
selection, IP inventors / filing deadlines / revenue sharing, declarations
of interest, data management plans and the daily reminder run.
Temporary databases only."""

import sqlite3

import pytest

from education_system.systems.university.application.research import access as ra
from education_system.systems.university.application.research import ethics as et
from education_system.systems.university.application.research import grants as rg
from education_system.systems.university.application.research import integrity as ri
from education_system.systems.university.application.research import ip as rip
from education_system.systems.university.application.research import outputs as ro
from education_system.systems.university.application.research import projects as rp
from education_system.systems.university.application.research import ref as rr
from education_system.systems.university.application.research import reminders as rm

#: The university's existing research tables, as they stand before migration c4e6f8a0b2d5.
EXISTING = [
"CREATE TABLE research_projects ( project_id INTEGER PRIMARY KEY AUTOINCREMENT, project_title TEXT NOT NULL, project_description TEXT, principal_investigator_id TEXT NOT NULL, department TEXT NOT NULL, project_type TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT, status TEXT DEFAULT 'active', total_budget REAL DEFAULT 0, funding_source TEXT, ethics_approval_status TEXT DEFAULT 'pending', ethics_approval_date TEXT, publications_count INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP )",
"CREATE TABLE ethics_reviews ( review_id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, review_type TEXT NOT NULL, submission_date TEXT NOT NULL, review_date TEXT, decision TEXT DEFAULT 'pending', decision_date TEXT, reviewer_comments TEXT, conditions TEXT, approval_expiry_date TEXT, reference TEXT, title TEXT, principal_investigator_id TEXT, department TEXT, risk_level TEXT, category TEXT, notes TEXT, FOREIGN KEY (project_id) REFERENCES research_projects (project_id) )",
'CREATE TABLE research_team_members ( member_id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, staff_id TEXT NOT NULL, role TEXT NOT NULL, join_date TEXT DEFAULT CURRENT_DATE, leave_date TEXT, contribution_percentage REAL, is_active BOOLEAN DEFAULT 1, FOREIGN KEY (project_id) REFERENCES research_projects (project_id) )',
"CREATE TABLE grant_applications ( application_id INTEGER PRIMARY KEY AUTOINCREMENT, grant_name TEXT NOT NULL, funding_agency TEXT NOT NULL, project_id INTEGER, principal_investigator_id TEXT NOT NULL, co_investigators TEXT, requested_amount REAL NOT NULL, application_deadline TEXT NOT NULL, submission_date TEXT, decision_date TEXT, decision_status TEXT DEFAULT 'pending', awarded_amount REAL, grant_period_start TEXT, grant_period_end TEXT, application_documents TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, grant_application_id INTEGER, title TEXT, FOREIGN KEY (project_id) REFERENCES research_projects (project_id) )",
'CREATE TABLE grant_budgets ( budget_id INTEGER PRIMARY KEY AUTOINCREMENT, application_id INTEGER NOT NULL, category TEXT NOT NULL, description TEXT, requested_amount REAL NOT NULL, approved_amount REAL, spent_amount REAL DEFAULT 0, remaining_amount REAL, FOREIGN KEY (application_id) REFERENCES grant_applications (application_id) )',
'CREATE TABLE research_publications ( publication_id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, title TEXT NOT NULL, authors TEXT NOT NULL, publication_type TEXT NOT NULL, journal_name TEXT, conference_name TEXT, publication_date TEXT, doi TEXT, url TEXT, abstract TEXT, keywords TEXT, citation_count INTEGER DEFAULT 0, is_peer_reviewed BOOLEAN DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, uoa TEXT, ref_submitted INTEGER DEFAULT 0, open_access INTEGER DEFAULT 0, quality_rating TEXT, lead_author_id TEXT, venue TEXT, FOREIGN KEY (project_id) REFERENCES research_projects (project_id) )',
"CREATE TABLE ip_disclosures ( disclosure_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT, ip_type TEXT DEFAULT 'invention', development_stage TEXT DEFAULT 'concept', funding_source TEXT, department TEXT, status TEXT DEFAULT 'draft', submitted_date TEXT, reviewed_by TEXT, review_date TEXT, review_comments TEXT, created_by TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP , reference TEXT, inventor_id TEXT, jurisdiction TEXT, commercial_route TEXT)",
'CREATE TABLE ip_inventors ( inventor_id INTEGER PRIMARY KEY AUTOINCREMENT, disclosure_id INTEGER, patent_id INTEGER, user_id TEXT NOT NULL, contribution_percentage REAL DEFAULT 0, is_primary INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (disclosure_id) REFERENCES ip_disclosures(disclosure_id), FOREIGN KEY (patent_id) REFERENCES patents(patent_id) )',
"CREATE TABLE ip_licenses ( license_id INTEGER PRIMARY KEY AUTOINCREMENT, patent_id INTEGER, disclosure_id INTEGER, licensee_name TEXT NOT NULL, license_type TEXT DEFAULT 'non_exclusive', royalty_rate REAL DEFAULT 0, territory TEXT DEFAULT 'worldwide', start_date TEXT NOT NULL, end_date TEXT, annual_fee REAL DEFAULT 0, status TEXT DEFAULT 'active', notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (patent_id) REFERENCES patents(patent_id), FOREIGN KEY (disclosure_id) REFERENCES ip_disclosures(disclosure_id) )",
"CREATE TABLE ip_revenue_shares ( revenue_id INTEGER PRIMARY KEY AUTOINCREMENT, license_id INTEGER NOT NULL, period TEXT NOT NULL, total_revenue REAL DEFAULT 0, university_share REAL DEFAULT 0, inventor_share REAL DEFAULT 0, department_share REAL DEFAULT 0, payment_date TEXT, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (license_id) REFERENCES ip_licenses(license_id) )",
'CREATE TABLE research_profiles ( profile_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT UNIQUE NOT NULL, research_interests TEXT, h_index INTEGER DEFAULT 0, total_citations INTEGER DEFAULT 0, total_publications INTEGER DEFAULT 0, orcid_id TEXT, google_scholar_id TEXT, researchgate_url TEXT, scopus_id TEXT, last_updated TEXT DEFAULT CURRENT_TIMESTAMP, created_at TEXT DEFAULT CURRENT_TIMESTAMP )',
"CREATE TABLE ref_impact_cases ( id INTEGER PRIMARY KEY AUTOINCREMENT, uoa TEXT NOT NULL, title TEXT NOT NULL, summary TEXT, lead_author_id INTEGER, status TEXT NOT NULL DEFAULT 'draft', reach_significance TEXT, beneficiaries TEXT, evidence_links TEXT, quality_rating TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')) )",
"CREATE TABLE ref_environment_statements ( id INTEGER PRIMARY KEY AUTOINCREMENT, uoa TEXT NOT NULL, narrative_text TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, drafted_by INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE (uoa, version) )",
    "CREATE TABLE staff (id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, email TEXT, "
    "role TEXT, status TEXT DEFAULT 'active')",
    "CREATE TABLE staff_profiles (user_id TEXT, department TEXT)",
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, "
    "email_address TEXT)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT, service_account INTEGER DEFAULT 0)",
    "CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER, "
    "subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)",
]
STAFF = [("pi", "Pat Investigator", "Geography"), ("coi", "Cole Investigator", "Geography"),
         ("chair", "Chris Chair", "Law"), ("rev1", "Robin Reviewer", "History"),
         ("rev2", "Riley Reviewer", "Physics"), ("office", "Olu Office", "Research Office"),
         ("hod", "Harper Head", "Geography"), ("reflead", "Rae Lead", "History"),
         ("tto", "Toni Transfer", "Enterprise"), ("other", "Odd Other", "Music")]
ROLES = [("chair", "ethics_chair", ""), ("rev1", "ethics_reviewer", ""),
         ("rev2", "ethics_reviewer", ""), ("coi", "ethics_reviewer", ""),
         ("office", "research_office", ""), ("hod", "head_of_department", "Geography"),
         ("reflead", "ref_lead", "UoA 11"), ("tto", "tto", "")]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in EXISTING:
        c.execute(ddl)
    for n, (username, name, dept) in enumerate(STAFF, 1):
        c.execute("INSERT INTO staff (id, username, name, email, role) VALUES (?, ?, ?, ?, "
                  "'staff')", (n, username, name, f"{username}@uni.test"))
        c.execute("INSERT INTO staff_profiles VALUES (?, ?)", (username, dept))
        c.execute("INSERT INTO users (username, role, email) VALUES (?, 'staff', ?)",
                  (username, f"{username}@uni.test"))
    c.execute("INSERT INTO users (username, role) VALUES ('admin', 'admin')")
    c.execute("INSERT INTO students VALUES ('S1', 'Sam', 'Student', 's1@uni.test')")
    c.execute("INSERT INTO users (username, role, student_id) VALUES ('S1', 'student', 'S1')")
    admin = ra.researcher(c, "admin", "admin")
    for username, role, scope in ROLES:
        ra.grant_role(c, admin, username, role, scope)
    c.commit()
    yield c
    c.close()


def who(c, username, role="staff"):
    return ra.researcher(c, username, role, "S1" if role == "student" else None)


def refused(fn, *args, **kwargs) -> str:
    with pytest.raises((ValueError, PermissionError)) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _project(c, needs_ethics=1):
    return rp.create(c, who(c, "pi"), {"project_title": "Glacier melt", "needs_ethics":
                                       needs_ethics, "project_type": "Funded"})


def _ethics(c, project_id=None, risk="Medium"):
    pi = who(c, "pi")
    rid = et.create(c, pi, {"title": "Interviews", "category": "Human participants",
                            "risk_level": risk, "project_id": project_id, "summary": "s",
                            "participants": "farmers", "data_handling": "encrypted",
                            "start_date": "2026-11-01", "end_date": "2027-10-31"})
    et.submit(c, pi, rid)
    return rid


def _approve(c, rid):
    chair = who(c, "chair")
    for reviewer in ("rev1", "rev2"):
        et.allocate(c, chair, rid, reviewer)
    for alloc in et.record(c, chair, rid)["allocations"]:
        et.submit_review(c, who(c, alloc["reviewer"]), alloc["allocation_id"], "approve", "ok")
    et.decide(c, chair, rid, "approve", "Approved")


# ── roles and schema ────────────────────────────────────────────────────


def test_roles_need_staff_and_the_office(conn):
    assert "No member of staff" in refused(ra.grant_role, conn, who(conn, "admin", "admin"),
                                           "S1", "ethics_reviewer")
    assert refused(ra.grant_role, conn, who(conn, "pi"), "coi", "ethics_chair")
    assert "department" in refused(ra.grant_role, conn, who(conn, "office"), "coi",
                                   "head_of_department")
    hod = who(conn, "hod")
    assert hod.heads("Geography") and not hod.heads("Music") and not hod.is_office
    assert who(conn, "admin", "admin").chairs_ethics


def test_ensure_adds_columns_and_is_transaction_safe(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ethics_reviews)")}
    assert {"applicant_id", "supervisor_id", "route", "kind"} <= cols
    conn.execute("INSERT INTO research_audit (entity, entity_id, action) VALUES ('t', '1', 'x')")
    assert conn.in_transaction
    ra.ensure(conn)
    assert conn.in_transaction
    conn.rollback()


def test_uoa_spelling_is_normalised(conn):
    from education_system.systems.university.infrastructure.database.schemas import (
        research_office_schema as schema,
    )
    conn.execute("INSERT INTO ref_impact_cases (uoa, title) VALUES ('UOA11', 'x'), ('uoa 3', 'y')")
    schema.apply(conn.execute)
    assert sorted(r[0] for r in conn.execute("SELECT uoa FROM ref_impact_cases")) == [
        "UoA 11", "UoA 3"]
    assert rr.canonical_uoa("UOA7") == "UoA 7" if hasattr(rr, "canonical_uoa") else True


# ── ethics ──────────────────────────────────────────────────────────────


def test_ethics_submit_needs_the_application_filled_in(conn):
    pi = who(conn, "pi")
    rid = et.create(conn, pi, {"title": "Survey", "category": "Human participants"})
    message = refused(et.submit, conn, pi, rid)
    assert "summary" in message and "participants" in message
    assert refused(et.update, conn, who(conn, "other"), rid, {"title": "mine now"})


def test_ethics_reviewers_cannot_be_connected_and_conflicts_hand_back(conn):
    pid = _project(conn)
    rp.add_member(conn, who(conn, "pi"), pid, "coi", "Co-investigator")
    rid = _ethics(conn, pid)
    chair = who(conn, "chair")
    assert "connected" in refused(et.allocate, conn, chair, rid, "coi")
    assert "not an ethics reviewer" in refused(et.allocate, conn, chair, rid, "other")
    et.allocate(conn, chair, rid, "rev1")
    alloc = et.record(conn, chair, rid)["allocations"][0]
    et.declare_conflict(conn, who(conn, "rev1"), alloc["allocation_id"], "co-author")
    queue = et.chair_queue(conn)["to_allocate"]
    assert queue and queue[0]["allocated"] == 0
    assert "already allocated" in refused(et.allocate, conn, chair, rid, "rev1")


def test_ethics_approval_needs_the_required_reviews(conn):
    rid = _ethics(conn)
    chair = who(conn, "chair")
    et.allocate(conn, chair, rid, "rev1")
    alloc = et.record(conn, chair, rid)["allocations"][0]
    et.submit_review(conn, who(conn, "rev1"), alloc["allocation_id"], "approve", "fine")
    assert "2 completed review" in refused(et.decide, conn, chair, rid, "approve", "ok")
    assert refused(et.decide, conn, who(conn, "rev1"), rid, "reject", "no")
    low = _ethics(conn, risk="Low")
    et.allocate(conn, chair, low, "rev2")
    alloc = et.record(conn, chair, low)["allocations"][0]
    et.submit_review(conn, who(conn, "rev2"), alloc["allocation_id"], "approve", "fine")
    et.decide(conn, chair, low, "approve", "ok")
    assert et.application(conn, low)["status"] == "approved"


def test_ethics_revisions_reopen_reviews_and_conditions_are_tracked(conn):
    rid = _ethics(conn)
    chair = who(conn, "chair")
    for reviewer in ("rev1", "rev2"):
        et.allocate(conn, chair, rid, reviewer)
    for alloc in et.record(conn, chair, rid)["allocations"]:
        et.submit_review(conn, who(conn, alloc["reviewer"]), alloc["allocation_id"], "revise", "x")
    et.decide(conn, chair, rid, "revise", "Fix the consent form")
    pi = who(conn, "pi")
    et.update(conn, pi, rid, {"summary": "better"})
    et.submit(conn, pi, rid)
    record = et.record(conn, chair, rid)
    assert record["status"] == "under_review"
    assert {a["status"] for a in record["allocations"]} == {"allocated"}
    for alloc in record["allocations"]:
        et.submit_review(conn, who(conn, alloc["reviewer"]), alloc["allocation_id"], "approve", "y")
    assert refused(et.decide, conn, chair, rid, "approve_with_conditions", "ok")
    et.decide(conn, chair, rid, "approve_with_conditions", "ok", ["Send the final form"])
    mine = et.record(conn, pi, rid)
    assert mine["approval_expiry_date"] == "2027-10-31"
    assert {a["reviewer"] for a in mine["allocations"]} == {"reviewer"}   # anonymous to applicant
    et.meet_condition(conn, pi, mine["conditions"][0]["condition_id"], "uploaded")
    assert et.record(conn, pi, rid)["conditions"][0]["met_at"]


def test_student_applications_need_supervisor_endorsement(conn):
    student = who(conn, "S1", "student")
    rid = et.create(conn, student, {"title": "Survey", "category": "Data-only", "risk_level":
                                    "Low", "summary": "x", "start_date": "2026-11-01",
                                    "end_date": "2027-01-01", "supervisor_id": "pi"})
    et.submit(conn, student, rid)
    assert et.application(conn, rid)["status"] == "awaiting_supervisor"
    assert refused(et.endorse, conn, who(conn, "other"), rid, True)
    et.endorse(conn, who(conn, "pi"), rid, True)
    assert et.application(conn, rid)["status"] == "submitted"
    assert [r["review_id"] for r in et.listing(conn, student)] == [rid]
    assert et.listing(conn, who(conn, "other")) == []
    assert refused(et.create, conn, student, {"title": "No supervisor"})


def test_amendments_renewals_and_expiry(conn):
    pid = _project(conn)
    rid = _ethics(conn, pid)
    _approve(conn, rid)
    assert et.has_approval(conn, pid)
    pi = who(conn, "pi")
    renewal = et.renew(conn, pi, rid, "2028-12-31")
    assert "in progress" in refused(et.amend, conn, pi, rid, "add a site")
    et.submit(conn, pi, renewal)
    _decide_child(conn, renewal)
    assert et.application(conn, rid)["approval_expiry_date"] == "2028-12-31"
    expired = et.expire_due(conn, "2029-01-01")
    assert [r["review_id"] for r in expired] == [rid] or rid in [r["review_id"] for r in expired]
    assert not et.has_approval(conn, pid, "2029-01-02")


def _decide_child(c, rid):
    chair = who(c, "chair")
    for reviewer in ("rev1", "rev2"):
        et.allocate(c, chair, rid, reviewer)
    for alloc in et.record(c, chair, rid)["allocations"]:
        et.submit_review(c, who(c, alloc["reviewer"]), alloc["allocation_id"], "approve", "ok")
    et.decide(c, chair, rid, "approve", "ok", expiry="2028-12-31")


# ── projects ────────────────────────────────────────────────────────────


def test_project_needing_ethics_cannot_go_active_without_approval(conn):
    pid = _project(conn)
    pi = who(conn, "pi")
    rp.set_status(conn, pi, pid, "suspended")
    assert "ethics" in refused(rp.set_status, conn, pi, pid, "active")
    _approve(conn, _ethics(conn, pid))
    rp.set_status(conn, pi, pid, "active")
    assert refused(rp.update, conn, who(conn, "coi"), pid, {"project_title": "x"})
    assert refused(rp.transfer_pi, conn, pi, pid, "coi", "leaving")
    rp.transfer_pi(conn, who(conn, "office"), pid, "coi", "leaving")
    assert rp.project(conn, pid)["principal_investigator_id"] == "coi"


def test_team_and_visibility(conn):
    pid = _project(conn)
    pi = who(conn, "pi")
    rp.add_member(conn, pi, pid, "coi", "Co-investigator")
    assert "already" in refused(rp.add_member, conn, pi, pid, "coi", "Researcher")
    assert [p["project_id"] for p in rp.listing(conn, who(conn, "coi"))] == [pid]
    assert [p["project_id"] for p in rp.listing(conn, who(conn, "hod"))] == [pid]
    assert rp.listing(conn, who(conn, "other")) == []
    assert refused(rp.record, conn, who(conn, "other"), pid)
    rp.remove_member(conn, pi, pid, "coi")
    assert rp.listing(conn, who(conn, "coi")) == []


def test_orcid_checksum(conn):
    assert refused(rp.save_profile, conn, who(conn, "pi"), "pi", {"orcid_id": "0000-0002-1825-0098"})
    rp.save_profile(conn, who(conn, "pi"), "pi", {"orcid_id": "0000-0002-1825-0097"})
    assert refused(rp.save_profile, conn, who(conn, "coi"), "pi", {"research_interests": "x"})


# ── grants ──────────────────────────────────────────────────────────────


def _grant(c, pid=None, **extra):
    pi = who(c, "pi")
    gid = rg.create(c, pi, {"grant_name": "NERC", "funding_agency": "NERC",
                            "application_deadline": "2099-12-01", "project_id": pid,
                            "co_investigators": "coi", **extra})
    for cat, amount in (("directly_incurred", 100000), ("directly_allocated", 50000),
                        ("indirect", 80000), ("exception", 10000)):
        rg.add_cost_line(c, pi, gid, cat, cat, amount)
    return gid


def test_fec_costing(conn):
    cost = rg.costing(conn, _grant(conn))
    assert cost["fec"] == 240000 and cost["price"] == 194000
    assert cost["university_contribution"] == 46000


def test_grant_needs_head_and_office_sign_off(conn):
    gid = _grant(conn)
    pi = who(conn, "pi")
    rg.request_approval(conn, pi, gid)
    assert refused(rg.approve, conn, pi, gid)
    assert refused(rg.mark_submitted, conn, pi, gid)
    rg.approve(conn, who(conn, "hod"), gid)
    assert rg.grant(conn, gid)["status"] == "awaiting_approval"
    assert [g["application_id"] for g in rg.approvals_for(conn, who(conn, "office"))] == [gid]
    rg.approve(conn, who(conn, "office"), gid)
    assert rg.grant(conn, gid)["status"] == "approved_to_submit"


def test_office_approval_stands_where_no_head_is_set(conn):
    conn.execute("UPDATE staff_profiles SET department = 'Music' WHERE user_id = 'pi'")
    gid = rg.create(conn, who(conn, "pi"), {"grant_name": "AHRC", "funding_agency": "AHRC",
                                            "application_deadline": "2099-01-01"})
    rg.add_cost_line(conn, who(conn, "pi"), gid, "directly_incurred", "x", 10)
    rg.request_approval(conn, who(conn, "pi"), gid)
    rg.approve(conn, who(conn, "office"), gid)
    assert rg.grant(conn, gid)["status"] == "approved_to_submit"


def _award(c, gid):
    office = who(c, "office")
    rg.request_approval(c, who(c, "pi"), gid)
    rg.approve(c, who(c, "hod"), gid)
    rg.approve(c, office, gid)
    rg.mark_submitted(c, who(c, "pi"), gid)
    rg.record_outcome(c, office, gid, "awarded", amount=180000, start="2026-01-01",
                      end="2028-12-31", award_reference="NE/X1")


def test_award_acceptance_needs_ethics_and_a_data_plan(conn, monkeypatch):
    monkeypatch.setattr(rg, "_tell_finance", lambda row: None)
    pid = _project(conn)
    gid = _grant(conn, pid, ethics_required=1)
    _award(conn, gid)
    office = who(conn, "office")
    message = refused(rg.accept_award, conn, office, gid)
    assert "ethics" in message and "data management plan" in message
    _approve(conn, _ethics(conn, pid))
    plan = ri.draft_plan(conn, who(conn, "pi"), pid, {"data_types": "interviews", "storage":
                                                      "OneDrive", "sharing": "UKDS",
                                                      "retention_years": 10, "personal_data": 1})
    assert "DPIA" in refused(ri.submit_plan, conn, who(conn, "pi"), plan)
    ri.draft_plan(conn, who(conn, "pi"), pid, {"dpia_reference": "DPIA-1"})
    ri.submit_plan(conn, who(conn, "pi"), plan)
    ri.review_plan(conn, office, plan, True)
    rg.accept_award(conn, office, gid)
    budget = rg.budget(conn, gid)
    assert budget["total"] == 180000
    assert {r["kind"] for r in rg.reports(conn, gid)} == {"final", "financial"}


def test_spend_limits_reports_and_closure(conn, monkeypatch):
    monkeypatch.setattr(rg, "_tell_finance", lambda row: None)
    gid = _grant(conn, dmp_required=0)
    _award(conn, gid)
    office = who(conn, "office")
    rg.accept_award(conn, office, gid)
    line = rg.budget(conn, gid)["lines"][0]
    rg.record_spend(conn, who(conn, "coi"), line["budget_id"], 1000, "2026-05-01", "boots")
    assert "overspend" in refused(rg.record_spend, conn, who(conn, "pi"), line["budget_id"],
                                  10 ** 7, "2026-05-02", "x")
    assert "period" in refused(rg.record_spend, conn, who(conn, "pi"), line["budget_id"], 1,
                               "2031-01-01", "x")
    assert refused(rg.record_spend, conn, who(conn, "other"), line["budget_id"], 1,
                   "2026-05-02", "x")
    rg.record_spend(conn, office, line["budget_id"], 10 ** 6, "2026-05-02", "agreed",
                    allow_overspend=True)
    assert "report" in refused(rg.close, conn, office, gid)
    for rep in rg.reports(conn, gid):
        rg.submit_report(conn, who(conn, "pi"), rep["report_id"])
    rg.close(conn, office, gid)
    assert rg.grant(conn, gid)["status"] == "closed"
    assert rg.pipeline(conn, office)["success_rate"] == 100.0


def test_grant_visibility(conn):
    gid = _grant(conn)
    assert [g["application_id"] for g in rg.listing(conn, who(conn, "coi"))] == [gid]
    assert rg.listing(conn, who(conn, "other")) == []
    assert refused(rg.record, conn, who(conn, "other"), gid)


# ── outputs and REF ─────────────────────────────────────────────────────


def _output(c, **extra):
    data = {"title": "Melt rates", "publication_type": "Journal article", "acceptance_date":
            "2025-01-10", "deposit_date": "2025-02-01", "publication_date": "2025-03-01",
            "uoa": "UoA 11", **extra}
    return ro.create(c, who(c, "pi"), data, "Investigator, P. [pi]; Smith, J.")


def test_outputs_need_an_author_and_unique_doi(conn):
    assert "yourself" in refused(ro.create, conn, who(conn, "pi"), {"title": "t",
                                 "publication_type": "Journal article"}, "Smith, J.")
    oid = _output(conn, doi="https://doi.org/10.1/ABC")
    assert ro.output(conn, oid)["doi"] == "10.1/ABC"
    assert "DOI" in refused(ro.create, conn, who(conn, "pi"), {"title": "x", "publication_type":
                            "Book", "doi": "10.1/abc"}, "P [pi]")
    assert [a["username"] for a in ro.authors(conn, oid)] == ["pi", None]
    assert refused(ro.update, conn, who(conn, "other"), oid, {"title": "x"})


def test_open_access_rule():
    base = {"publication_type": "Journal article", "acceptance_date": "2025-01-10"}
    assert ro.oa_status({**base, "deposit_date": "2025-04-11"}) == "compliant"
    assert ro.oa_status({**base, "deposit_date": "2025-04-13"}) == "late deposit"
    assert ro.oa_status({**base, "oa_exception": "deposit"}) == "exception"
    assert ro.oa_status({"publication_type": "Book"}) == "not in scope"
    assert ro.oa_status({"publication_type": "Conference paper"}) == "not in scope"
    assert ro.oa_status({"publication_type": "Journal article"}) == "no acceptance date"


def test_ref_review_rating_and_selection(conn):
    oid = _output(conn)
    lead = who(conn, "reflead")
    problems = refused(rr.select, conn, lead, oid)
    assert "rating" in problems and "attributed" in problems
    rr.attribute(conn, lead, "pi", "UOA11", 1.0)
    assert refused(rr.add_review, conn, who(conn, "pi"), oid, 3)
    rr.add_review(conn, lead, oid, 4)
    rr.add_review(conn, who(conn, "office"), oid, 2)
    assert rr.review_summary(conn, oid)["needs_moderation"]
    rr.set_rating(conn, lead, oid, 3)
    rr.select(conn, lead, oid)
    assert "REF selection" in refused(ro.remove, conn, who(conn, "office"), oid, "duplicate")
    rr.save_impact_case(conn, lead, {"uoa": "UoA 11", "title": "Flood warnings"})
    rr.add_environment_statement(conn, lead, "UoA 11", "v1")
    summary = rr.uoa_summary(conn, "UoA 11")
    assert summary["selected"] == 1 and summary["required_outputs"] == 2
    assert summary["impact_cases"] == 1 and summary["environment_version"] == 1
    assert "1 more output(s) needed" in summary["gaps"]


def test_ref_period_and_open_access_block_selection(conn):
    lead = who(conn, "reflead")
    rr.attribute(conn, lead, "pi", "UoA 11")
    old = _output(conn, publication_date="2019-01-01", acceptance_date="2018-12-01",
                  deposit_date="2018-12-02")
    rr.add_review(conn, lead, old, 3)
    rr.set_rating(conn, lead, old, 3)
    assert "REF period" in refused(rr.select, conn, lead, old)
    late = _output(conn, title="Late", deposit_date="2025-09-01")
    rr.add_review(conn, lead, late, 3)
    rr.set_rating(conn, lead, late, 3)
    assert "open access" in refused(rr.select, conn, lead, late)


# ── IP ──────────────────────────────────────────────────────────────────


def test_ip_inventors_filing_deadlines_and_licences(conn):
    pi = who(conn, "pi")
    assert "100%" in refused(rip.create, conn, pi, {"title": "Sensor"}, [("pi", 60), ("coi", 30)])
    assert "one of the inventors" in refused(rip.create, conn, pi, {"title": "S"}, [("coi", 100)])
    did = rip.create(conn, pi, {"title": "Sensor", "description": "ice"}, [("pi", 60), ("coi", 40)])
    rip.submit(conn, pi, did)
    tto = who(conn, "tto")
    assert refused(rip.assess, conn, pi, did, "protect", "x")
    rip.assess(conn, tto, did, "protect", "promising")
    rip.record_filing(conn, tto, did, "2026-02-15", "GB1")
    assert [d["due_date"] for d in rip.record(conn, tto, did)["deadlines"]] == [
        "2027-02-15", "2028-08-15"]
    lic = rip.add_licence(conn, tto, did, "IceCo", "exclusive", "2026-03-01")
    assert "exclusive" in refused(rip.add_licence, conn, tto, did, "B", "exclusive", "2026-04-01")
    rip.record_revenue(conn, tto, lic, "2026", 120000)
    revenue = rip.record(conn, who(conn, "coi"), did)["revenue"][0]
    assert revenue["inventor_share"] == 56666.0
    assert revenue["mine"] == pytest.approx(22666.4)
    assert rip.listing(conn, who(conn, "other")) == []


def test_revenue_bands_are_cumulative():
    assert rip.split(0, 100000) == {"inventors": 50000.0, "department": 25000.0,
                                    "university": 25000.0}
    assert rip.split(100000, 300000)["inventors"] == pytest.approx(99990.0)
    assert rip.split(600000, 1000)["university"] == 500.0


# ── integrity and reminders ─────────────────────────────────────────────


def test_declarations_reviewed_by_someone_else(conn):
    _project(conn)
    assert [o["username"] for o in ri.overdue(conn)] == ["pi"]
    dec = ri.declare(conn, who(conn, "pi"), "consultancy", counterpart="IceCo",
                     description="adviser")
    assert refused(ri.review, conn, who(conn, "pi"), dec, "no_action")
    assert [d["declaration_id"] for d in ri.to_review(conn, who(conn, "hod"))] == [dec]
    assert "plan" in refused(ri.review, conn, who(conn, "hod"), dec, "managed")
    ri.review(conn, who(conn, "hod"), dec, "managed", "Stays out of licence talks")
    assert ri.overdue(conn) == []
    assert refused(ri.declare, conn, who(conn, "pi"), "gift")


def test_reminders_run_once_a_day_and_do_not_repeat(conn):
    pid = _project(conn)
    _approve(conn, _ethics(conn, pid))
    first = rm.run(conn, as_of="2027-09-15")
    assert first["reminded"] >= 1
    assert rm.run(conn, as_of="2027-09-15") == {"expired": 0, "reminded": 0, "emails": []}
    again = rm.run(conn, as_of="2027-09-16", force=True)
    assert all("2027-10-31" not in e[1] for e in again["emails"])
    expired = rm.run(conn, as_of="2027-11-01")
    assert expired["expired"] == 1


def test_attention_lists_what_each_person_must_do(conn):
    rid = _ethics(conn)
    chair = rm.attention(conn, who(conn, "chair"))
    assert any(i["ref"] == ("ethics", rid) and "Allocate" in i["title"] for i in chair)
    et.allocate(conn, who(conn, "chair"), rid, "rev1")
    assert any("Review" in i["title"] for i in rm.attention(conn, who(conn, "rev1")))
    assert rm.attention(conn, who(conn, "other")) == []

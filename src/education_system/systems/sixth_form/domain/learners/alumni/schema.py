"""Sixth-form alumni — Every DDL string and column-migration list (base schema + the five extension schemas).

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations


_SCHEMA = """
CREATE TABLE IF NOT EXISTS alumni (
    alumni_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    original_student_id  TEXT,
    first_name           TEXT NOT NULL,
    last_name            TEXT NOT NULL,
    preferred_name       TEXT,
    pronouns             TEXT,
    gender               TEXT,
    dob                  TEXT,
    leaving_year         TEXT,
    leaving_date         TEXT,
    leaving_reason       TEXT,
    destination_type     TEXT NOT NULL DEFAULT 'Unknown',
    destination_detail   TEXT,
    current_role         TEXT,
    current_employer     TEXT,
    current_sector       TEXT,
    current_location     TEXT,
    country              TEXT,
    region               TEXT,
    email                TEXT,
    phone                TEXT,
    address              TEXT,
    linkedin             TEXT,
    other_social         TEXT,
    photo_path           TEXT,
    bio                  TEXT,
    opt_in_contact       INTEGER NOT NULL DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'Active',
    last_contacted       TEXT,
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alm_last_name      ON alumni(last_name);
CREATE INDEX IF NOT EXISTS idx_alm_leaving_year   ON alumni(leaving_year);
CREATE INDEX IF NOT EXISTS idx_alm_destination    ON alumni(destination_type);
CREATE INDEX IF NOT EXISTS idx_alm_status         ON alumni(status);
CREATE INDEX IF NOT EXISTS idx_alm_original       ON alumni(original_student_id);

CREATE TABLE IF NOT EXISTS alumni_education (
    education_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    qualification  TEXT NOT NULL,
    subject        TEXT,
    institution    TEXT NOT NULL,
    start_date     TEXT,
    end_date       TEXT,
    grade          TEXT,
    status         TEXT NOT NULL DEFAULT 'In Progress',
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aedu_alumni ON alumni_education(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_career (
    career_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    role           TEXT NOT NULL,
    employer       TEXT NOT NULL,
    sector         TEXT,
    country        TEXT,
    location       TEXT,
    start_date     TEXT,
    end_date       TEXT,
    is_current     INTEGER NOT NULL DEFAULT 0,
    salary_band    TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_acar_alumni ON alumni_career(alumni_id);
CREATE INDEX IF NOT EXISTS idx_acar_sector ON alumni_career(sector);

CREATE TABLE IF NOT EXISTS alumni_emails (
    email_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    email       TEXT NOT NULL,
    label       TEXT NOT NULL DEFAULT 'Personal',
    is_primary  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aeml_alumni ON alumni_emails(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_phones (
    phone_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    phone       TEXT NOT NULL,
    label       TEXT NOT NULL DEFAULT 'Mobile',
    is_primary  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aphn_alumni ON alumni_phones(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_tags (
    tag_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS alumni_tag_links (
    alumni_id   INTEGER NOT NULL,
    tag_id      INTEGER NOT NULL,
    PRIMARY KEY (alumni_id, tag_id),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)    REFERENCES alumni_tags(tag_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_atag_tag ON alumni_tag_links(tag_id);

CREATE TABLE IF NOT EXISTS alumni_achievements (
    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    date           TEXT,
    title          TEXT NOT NULL,
    category       TEXT,
    description    TEXT,
    url            TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aach_alumni ON alumni_achievements(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_channel_prefs (
    alumni_id     INTEGER PRIMARY KEY,
    opt_in_email  INTEGER NOT NULL DEFAULT 1,
    opt_in_post   INTEGER NOT NULL DEFAULT 1,
    opt_in_phone  INTEGER NOT NULL DEFAULT 1,
    opt_in_sms    INTEGER NOT NULL DEFAULT 1,
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_consent (
    consent_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    scope         TEXT NOT NULL,
    version       TEXT NOT NULL,
    granted_at    TEXT NOT NULL,
    withdrawn_at  TEXT,
    source        TEXT,
    notes         TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_acon_alumni ON alumni_consent(alumni_id);
CREATE INDEX IF NOT EXISTS idx_acon_scope  ON alumni_consent(scope);

CREATE TABLE IF NOT EXISTS alumni_portal_tokens (
    token       TEXT PRIMARY KEY,
    alumni_id   INTEGER NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_atok_alumni ON alumni_portal_tokens(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    event_type  TEXT NOT NULL DEFAULT 'Reunion',
    event_date  TEXT,
    end_date    TEXT,
    location    TEXT,
    capacity    INTEGER,
    cost_pence  INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'Planning',
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_aevt_date   ON alumni_events(event_date);
CREATE INDEX IF NOT EXISTS idx_aevt_status ON alumni_events(status);

CREATE TABLE IF NOT EXISTS alumni_event_rsvps (
    rsvp_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    INTEGER NOT NULL,
    alumni_id   INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Invited',
    attended    INTEGER NOT NULL DEFAULT 0,
    guests      INTEGER NOT NULL DEFAULT 0,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(event_id, alumni_id),
    FOREIGN KEY (event_id)  REFERENCES alumni_events(event_id) ON DELETE CASCADE,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_arsvp_alumni ON alumni_event_rsvps(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_mentorships (
    mentorship_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    mentor_alumni_id  INTEGER NOT NULL,
    mentee_student_id TEXT NOT NULL,
    topic             TEXT,
    started_on        TEXT NOT NULL,
    ended_on          TEXT,
    status            TEXT NOT NULL DEFAULT 'Active',
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mentor_alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_amen_mentor ON alumni_mentorships(mentor_alumni_id);
CREATE INDEX IF NOT EXISTS idx_amen_mentee ON alumni_mentorships(mentee_student_id);

CREATE TABLE IF NOT EXISTS alumni_mentor_sessions (
    session_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    mentorship_id    INTEGER NOT NULL,
    session_date     TEXT NOT NULL,
    duration_minutes INTEGER,
    format           TEXT,
    summary          TEXT,
    mentor_feedback  TEXT,
    mentee_feedback  TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mentorship_id) REFERENCES alumni_mentorships(mentorship_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_amses_mship ON alumni_mentor_sessions(mentorship_id);

CREATE TABLE IF NOT EXISTS alumni_speakers (
    alumni_id           INTEGER PRIMARY KEY,
    topics              TEXT,
    year_groups         TEXT,
    availability_notes  TEXT,
    last_confirmed_at   TEXT,
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_work_exp_offers (
    offer_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    employer        TEXT,
    sector          TEXT,
    location        TEXT,
    duration_weeks  INTEGER,
    start_window    TEXT,
    vacancy_count   INTEGER NOT NULL DEFAULT 1,
    requirements    TEXT,
    deadline        TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_awxo_alumni ON alumni_work_exp_offers(alumni_id);
CREATE INDEX IF NOT EXISTS idx_awxo_status ON alumni_work_exp_offers(status);

CREATE TABLE IF NOT EXISTS alumni_work_exp_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id       INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    applied_on     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Submitted',
    outcome_notes  TEXT,
    UNIQUE(offer_id, student_id),
    FOREIGN KEY (offer_id) REFERENCES alumni_work_exp_offers(offer_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_references (
    reference_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    staff_id      TEXT,
    ref_type      TEXT NOT NULL DEFAULT 'Job',
    requested_on  TEXT,
    sent_on       TEXT,
    target_name   TEXT,
    target_url    TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aref_alumni ON alumni_references(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_volunteer_hours (
    volunteer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    activity_date  TEXT NOT NULL,
    hours          REAL NOT NULL,
    activity_type  TEXT NOT NULL DEFAULT 'Other',
    event_id       INTEGER,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (event_id)  REFERENCES alumni_events(event_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_avol_alumni ON alumni_volunteer_hours(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_campaigns (
    campaign_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description   TEXT,
    target_pence  INTEGER,
    start_on      TEXT,
    end_on        TEXT,
    status        TEXT NOT NULL DEFAULT 'Active',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_donations (
    donation_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    campaign_id    INTEGER,
    donation_date  TEXT NOT NULL,
    amount_pence   INTEGER NOT NULL,
    gift_aid       INTEGER NOT NULL DEFAULT 0,
    payment_method TEXT,
    anonymous      INTEGER NOT NULL DEFAULT 0,
    restricted_to  TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id)   REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES alumni_campaigns(campaign_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_adon_alumni   ON alumni_donations(alumni_id);
CREATE INDEX IF NOT EXISTS idx_adon_campaign ON alumni_donations(campaign_id);
CREATE INDEX IF NOT EXISTS idx_adon_date     ON alumni_donations(donation_date);

CREATE TABLE IF NOT EXISTS alumni_pledges (
    pledge_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    campaign_id   INTEGER,
    pledged_on    TEXT NOT NULL,
    amount_pence  INTEGER NOT NULL,
    due_by        TEXT,
    status        TEXT NOT NULL DEFAULT 'Open',
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id)   REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES alumni_campaigns(campaign_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_apld_alumni   ON alumni_pledges(alumni_id);
CREATE INDEX IF NOT EXISTS idx_apld_campaign ON alumni_pledges(campaign_id);

CREATE TABLE IF NOT EXISTS alumni_audit_log (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    field       TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    changed_by  TEXT,
    changed_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aaud_alumni ON alumni_audit_log(alumni_id);
CREATE INDEX IF NOT EXISTS idx_aaud_when   ON alumni_audit_log(changed_at);

CREATE TABLE IF NOT EXISTS alumni_saved_searches (
    search_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description      TEXT,
    filters_json     TEXT NOT NULL,
    owner_staff_id   TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_surveys (
    survey_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    description    TEXT,
    questions_json TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Draft',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_survey_invitations (
    invitation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id      INTEGER NOT NULL,
    alumni_id      INTEGER NOT NULL,
    token          TEXT NOT NULL UNIQUE,
    sent_at        TEXT,
    completed_at   TEXT,
    expires_at     TEXT NOT NULL,
    UNIQUE(survey_id, alumni_id),
    FOREIGN KEY (survey_id) REFERENCES alumni_surveys(survey_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asinv_alumni ON alumni_survey_invitations(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_survey_responses (
    response_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    invitation_id  INTEGER NOT NULL UNIQUE,
    answers_json   TEXT NOT NULL,
    submitted_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (invitation_id)
        REFERENCES alumni_survey_invitations(invitation_id)
        ON DELETE CASCADE
);
"""

# Columns added after the initial release. Each entry is
# (column_name, "TYPE [DEFAULT ...]") — applied with ALTER TABLE on
# existing databases.
_ALUMNI_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("pronouns",       "TEXT"),
    ("gender",         "TEXT"),
    ("current_sector", "TEXT"),
    ("country",        "TEXT"),
    ("region",         "TEXT"),
    ("photo_path",     "TEXT"),
    ("bio",            "TEXT"),
    ("bounce_count",   "INTEGER NOT NULL DEFAULT 0"),
    ("deleted_at",     "TEXT"),
)


# ════════════════════════════════════════════════════════════════════
# Engagement extensions — social handles, connections, chapters,
# engagement score, re-engagement worklist, milestones, lost-contact
# queue, and public directory listing.
# ════════════════════════════════════════════════════════════════════

_SCHEMA_ENGAGEMENT = """
CREATE TABLE IF NOT EXISTS alumni_social_handles (
    handle_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    platform    TEXT NOT NULL,
    handle      TEXT NOT NULL,
    url         TEXT,
    verified    INTEGER NOT NULL DEFAULT 0,
    verified_at TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(alumni_id, platform, handle),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asoc_alumni
    ON alumni_social_handles(alumni_id);
CREATE INDEX IF NOT EXISTS idx_asoc_platform
    ON alumni_social_handles(platform);

CREATE TABLE IF NOT EXISTS alumni_connections (
    connection_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    a_id           INTEGER NOT NULL,
    b_id           INTEGER NOT NULL,
    kind           TEXT NOT NULL DEFAULT 'Friend',
    since          TEXT,
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(a_id, b_id),
    CHECK (a_id < b_id),
    FOREIGN KEY (a_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (b_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_acon_a ON alumni_connections(a_id);
CREATE INDEX IF NOT EXISTS idx_acon_b ON alumni_connections(b_id);

CREATE TABLE IF NOT EXISTS alumni_chapters (
    chapter_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    kind        TEXT NOT NULL DEFAULT 'Regional',
    region      TEXT,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'Active',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_chapter_members (
    chapter_id  INTEGER NOT NULL,
    alumni_id   INTEGER NOT NULL,
    role        TEXT NOT NULL DEFAULT 'Member',
    joined_on   TEXT,
    left_on     TEXT,
    PRIMARY KEY (chapter_id, alumni_id),
    FOREIGN KEY (chapter_id) REFERENCES alumni_chapters(chapter_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id)  REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_achm_alumni
    ON alumni_chapter_members(alumni_id);
"""


_SCHEMA_CAREER_EXT = """
CREATE TABLE IF NOT EXISTS alumni_skills (
    skill_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category   TEXT
);

CREATE TABLE IF NOT EXISTS alumni_skill_links (
    alumni_id    INTEGER NOT NULL,
    skill_id     INTEGER NOT NULL,
    proficiency  TEXT NOT NULL DEFAULT 'Intermediate',
    years        REAL,
    notes        TEXT,
    PRIMARY KEY (alumni_id, skill_id),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE,
    FOREIGN KEY (skill_id)  REFERENCES alumni_skills(skill_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_askl_skill
    ON alumni_skill_links(skill_id);

CREATE TABLE IF NOT EXISTS alumni_job_title_soc (
    pattern    TEXT PRIMARY KEY COLLATE NOCASE,
    soc_code   TEXT NOT NULL,
    soc_label  TEXT NOT NULL,
    naics_code TEXT
);

CREATE TABLE IF NOT EXISTS alumni_employers (
    employer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    sector         TEXT,
    website        TEXT,
    country        TEXT,
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_employer_aliases (
    alias          TEXT PRIMARY KEY COLLATE NOCASE,
    employer_id    INTEGER NOT NULL,
    FOREIGN KEY (employer_id) REFERENCES alumni_employers(employer_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aalias_eid
    ON alumni_employer_aliases(employer_id);

CREATE TABLE IF NOT EXISTS alumni_jobs (
    job_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    title         TEXT NOT NULL,
    employer      TEXT,
    sector        TEXT,
    location      TEXT,
    job_type      TEXT NOT NULL DEFAULT 'Graduate',
    salary_band   TEXT,
    description   TEXT,
    apply_url     TEXT,
    deadline      TEXT,
    status        TEXT NOT NULL DEFAULT 'Open',
    posted_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ajob_alumni ON alumni_jobs(alumni_id);
CREATE INDEX IF NOT EXISTS idx_ajob_status ON alumni_jobs(status);

CREATE TABLE IF NOT EXISTS alumni_job_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         INTEGER NOT NULL,
    applicant_kind TEXT NOT NULL DEFAULT 'Alumnus',
    applicant_id   TEXT NOT NULL,
    applied_on     TEXT NOT NULL DEFAULT (date('now')),
    status         TEXT NOT NULL DEFAULT 'Submitted',
    notes          TEXT,
    UNIQUE(job_id, applicant_kind, applicant_id),
    FOREIGN KEY (job_id) REFERENCES alumni_jobs(job_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_internships (
    internship_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    employer        TEXT,
    sector          TEXT,
    location        TEXT,
    duration_weeks  INTEGER,
    paid            INTEGER NOT NULL DEFAULT 0,
    hourly_pence    INTEGER,
    start_window    TEXT,
    requirements    TEXT,
    apply_url       TEXT,
    deadline        TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    posted_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aint_alumni ON alumni_internships(alumni_id);
CREATE INDEX IF NOT EXISTS idx_aint_status ON alumni_internships(status);

CREATE TABLE IF NOT EXISTS alumni_internship_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id  INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    applied_on     TEXT NOT NULL DEFAULT (date('now')),
    status         TEXT NOT NULL DEFAULT 'Submitted',
    notes          TEXT,
    UNIQUE(internship_id, student_id),
    FOREIGN KEY (internship_id)
        REFERENCES alumni_internships(internship_id) ON DELETE CASCADE
);
"""


_SCHEMA_COMMS_EXT = """
CREATE TABLE IF NOT EXISTS alumni_mentor_profiles (
    alumni_id        INTEGER PRIMARY KEY,
    max_mentees      INTEGER NOT NULL DEFAULT 3,
    available_from   TEXT,
    available_until  TEXT,
    paused           INTEGER NOT NULL DEFAULT 0,
    bio              TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_mentor_safeguarding (
    alumni_id        INTEGER PRIMARY KEY,
    dbs_reference    TEXT,
    dbs_issued_on    TEXT,
    dbs_expires_on   TEXT,
    training_done_on TEXT,
    training_expires_on TEXT,
    status           TEXT NOT NULL DEFAULT 'Pending',
    notes            TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_email_templates (
    template_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL COLLATE NOCASE,
    version      INTEGER NOT NULL DEFAULT 1,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    category     TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS alumni_drip_campaigns (
    drip_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'Draft',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_drip_steps (
    step_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    drip_id        INTEGER NOT NULL,
    position       INTEGER NOT NULL,
    delay_days     INTEGER NOT NULL DEFAULT 0,
    template_id    INTEGER,
    subject        TEXT,
    body           TEXT,
    UNIQUE(drip_id, position),
    FOREIGN KEY (drip_id)      REFERENCES alumni_drip_campaigns(drip_id)
        ON DELETE CASCADE,
    FOREIGN KEY (template_id)  REFERENCES alumni_email_templates(template_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS alumni_drip_enrollments (
    enrollment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    drip_id        INTEGER NOT NULL,
    alumni_id      INTEGER NOT NULL,
    enrolled_at    TEXT NOT NULL DEFAULT (datetime('now')),
    next_send_at   TEXT,
    current_step   INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'Active',
    UNIQUE(drip_id, alumni_id),
    FOREIGN KEY (drip_id)   REFERENCES alumni_drip_campaigns(drip_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_ab_tests (
    test_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description  TEXT,
    filters_json TEXT,
    sent_at      TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_ab_variants (
    variant_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id      INTEGER NOT NULL,
    label        TEXT NOT NULL,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    sent_count   INTEGER NOT NULL DEFAULT 0,
    open_count   INTEGER NOT NULL DEFAULT 0,
    click_count  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(test_id, label),
    FOREIGN KEY (test_id) REFERENCES alumni_ab_tests(test_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_ab_assignments (
    test_id     INTEGER NOT NULL,
    alumni_id   INTEGER NOT NULL,
    variant_id  INTEGER NOT NULL,
    PRIMARY KEY (test_id, alumni_id),
    FOREIGN KEY (test_id)    REFERENCES alumni_ab_tests(test_id)
        ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES alumni_ab_variants(variant_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id)  REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_sms_messages (
    sms_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    body        TEXT NOT NULL,
    sent_at     TEXT NOT NULL DEFAULT (datetime('now')),
    status      TEXT NOT NULL DEFAULT 'Sent',
    error       TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asms_alumni ON alumni_sms_messages(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_postal_letters (
    letter_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    pdf_path    TEXT,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_newsletters (
    newsletter_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    issue          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    title          TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Draft',
    published_at   TEXT,
    distribution_filters_json TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_newsletter_sections (
    section_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id  INTEGER NOT NULL,
    position       INTEGER NOT NULL,
    heading        TEXT NOT NULL,
    body           TEXT NOT NULL,
    UNIQUE(newsletter_id, position),
    FOREIGN KEY (newsletter_id)
        REFERENCES alumni_newsletters(newsletter_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_track_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    token       TEXT NOT NULL,
    alumni_id   INTEGER,
    kind        TEXT NOT NULL,
    payload     TEXT,
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_atrk_token ON alumni_track_events(token);
CREATE INDEX IF NOT EXISTS idx_atrk_alumni ON alumni_track_events(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_track_links (
    token        TEXT PRIMARY KEY,
    alumni_id    INTEGER,
    kind         TEXT NOT NULL DEFAULT 'click',
    target_url   TEXT,
    campaign_ref TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
"""

_MENTOR_SESSION_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("mentor_rating", "INTEGER"),  # 1..5 from mentee
    ("mentee_rating", "INTEGER"),  # 1..5 from mentor
)


_SCHEMA_EVENTS_EXT = """
CREATE TABLE IF NOT EXISTS alumni_event_refunds (
    refund_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER NOT NULL,
    alumni_id    INTEGER NOT NULL,
    amount_pence INTEGER NOT NULL,
    reason       TEXT,
    refunded_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (event_id)  REFERENCES alumni_events(event_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aerf_event
    ON alumni_event_refunds(event_id);
"""

_SCHEMA_FUNDRAISING_EXT = """
CREATE TABLE IF NOT EXISTS alumni_gift_aid_declarations (
    declaration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    valid_from     TEXT NOT NULL,
    valid_until    TEXT,
    full_name      TEXT NOT NULL,
    address        TEXT NOT NULL,
    postcode       TEXT NOT NULL,
    signed_at      TEXT NOT NULL DEFAULT (datetime('now')),
    withdrawn_at   TEXT,
    notes          TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aga_alumni
    ON alumni_gift_aid_declarations(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_recurring_donations (
    schedule_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    campaign_id    INTEGER,
    amount_pence   INTEGER NOT NULL,
    frequency      TEXT NOT NULL DEFAULT 'Monthly',
    next_charge_on TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Active',
    failure_count  INTEGER NOT NULL DEFAULT 0,
    fund_code      TEXT,
    payment_method TEXT,
    started_on     TEXT NOT NULL DEFAULT (date('now')),
    cancelled_on   TEXT,
    notes          TEXT,
    FOREIGN KEY (alumni_id)   REFERENCES alumni(alumni_id)
        ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES alumni_campaigns(campaign_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_arec_alumni
    ON alumni_recurring_donations(alumni_id);
CREATE INDEX IF NOT EXISTS idx_arec_next
    ON alumni_recurring_donations(next_charge_on);

CREATE TABLE IF NOT EXISTS alumni_donor_pipeline (
    alumni_id     INTEGER PRIMARY KEY,
    stage         TEXT NOT NULL DEFAULT 'Identification',
    owner_staff_id TEXT,
    next_action   TEXT,
    next_action_on TEXT,
    capacity_pence INTEGER,
    notes         TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_donor_pipeline_log (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    from_stage    TEXT,
    to_stage      TEXT NOT NULL,
    changed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    changed_by    TEXT,
    notes         TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_funds (
    fund_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name         TEXT NOT NULL,
    restricted   INTEGER NOT NULL DEFAULT 0,
    description  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_bequests (
    bequest_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    estimated_pence INTEGER,
    will_mention   INTEGER NOT NULL DEFAULT 1,
    executor_name  TEXT,
    executor_email TEXT,
    executor_phone TEXT,
    confirmed_on   TEXT,
    realised_on    TEXT,
    status         TEXT NOT NULL DEFAULT 'Pledged',
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_abq_alumni
    ON alumni_bequests(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_matched_giving_schemes (
    scheme_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    employer     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    multiplier   REAL NOT NULL DEFAULT 1.0,
    cap_pence    INTEGER,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SCHEMA_OUTCOMES_EXT = """
CREATE TABLE IF NOT EXISTS alumni_neet_checks (
    check_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    months_after  INTEGER NOT NULL,
    checked_on    TEXT NOT NULL DEFAULT (date('now')),
    status        TEXT NOT NULL DEFAULT 'Unknown',
    notes         TEXT,
    UNIQUE(alumni_id, months_after),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aneet_alumni
    ON alumni_neet_checks(alumni_id);
"""

_RSVP_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("amount_paid_pence", "INTEGER NOT NULL DEFAULT 0"),
    ("checkin_token",     "TEXT"),
    ("checkin_at",        "TEXT"),
    ("waitlisted",        "INTEGER NOT NULL DEFAULT 0"),
)

_DONATION_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("fund_code",         "TEXT"),
    ("matched_pence",     "INTEGER NOT NULL DEFAULT 0"),
    ("matched_scheme_id", "INTEGER"),
)

_ALUMNI_NEW_COLUMNS_V2: tuple[tuple[str, str], ...] = (
    ("first_gen_he", "INTEGER NOT NULL DEFAULT 0"),
)

_PROTECTED_CHAR_COLS: tuple[tuple[str, str], ...] = (
    ("send",        "INTEGER NOT NULL DEFAULT 0"),
    ("fsm_ever_6",  "INTEGER NOT NULL DEFAULT 0"),
    ("eal",         "INTEGER NOT NULL DEFAULT 0"),
    ("looked_after", "INTEGER NOT NULL DEFAULT 0"),
    ("ethnicity",    "TEXT"),
)


_SCHEMA_FINAL_EXT = """
CREATE TABLE IF NOT EXISTS alumni_hesa_benchmarks (
    benchmark_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    leaving_year   TEXT NOT NULL,
    metric         TEXT NOT NULL,
    rate_pct       REAL NOT NULL,
    source         TEXT,
    UNIQUE(leaving_year, metric)
);

CREATE TABLE IF NOT EXISTS alumni_erasure_requests (
    request_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    requested_at   TEXT NOT NULL DEFAULT (datetime('now')),
    requested_by   TEXT,
    reason         TEXT,
    status         TEXT NOT NULL DEFAULT 'Requested',
    reviewer       TEXT,
    reviewed_at    TEXT,
    review_notes   TEXT,
    completed_at   TEXT,
    confirmation_sent_at TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aer_alumni
    ON alumni_erasure_requests(alumni_id);
CREATE INDEX IF NOT EXISTS idx_aer_status
    ON alumni_erasure_requests(status);

CREATE TABLE IF NOT EXISTS alumni_webhooks (
    webhook_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL,
    secret       TEXT,
    event_types  TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_webhook_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type   TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    queued_at    TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT,
    last_error   TEXT
);
CREATE INDEX IF NOT EXISTS idx_awhe_type
    ON alumni_webhook_events(event_type);

CREATE TABLE IF NOT EXISTS alumni_custom_fields (
    field_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    label        TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT 'text',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_custom_values (
    alumni_id   INTEGER NOT NULL,
    field_id    INTEGER NOT NULL,
    value       TEXT,
    PRIMARY KEY (alumni_id, field_id),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE,
    FOREIGN KEY (field_id)  REFERENCES alumni_custom_fields(field_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_media (
    media_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id    INTEGER NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'photo',
    file_path    TEXT NOT NULL,
    caption      TEXT,
    consent_granted INTEGER NOT NULL DEFAULT 0,
    exif_stripped   INTEGER NOT NULL DEFAULT 0,
    is_profile      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_amedia_alumni
    ON alumni_media(alumni_id);
"""

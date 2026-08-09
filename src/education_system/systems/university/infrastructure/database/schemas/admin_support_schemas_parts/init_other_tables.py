"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_other_tables():
    """Initialize other system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="other"))

        # Create academic_goals table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_goals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        parent_id TEXT,
                        goal_title TEXT,
                        description TEXT,
                        target_grade TEXT,
                        target_date TEXT,
                        current_progress TEXT,
                        status TEXT DEFAULT 'active',
                        created_date TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                    )
        ''')

        # Create academic_years table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_years (
                            id TEXT PRIMARY KEY,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            date_added TEXT NOT NULL,
                            CONSTRAINT valid_dates CHECK (start_date < end_date)
                        )
        ''')

        # Create achievement_badges table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievement_badges (
                    badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    badge_name TEXT,
                    badge_description TEXT,
                    points_required INTEGER,
                    badge_icon TEXT,
                    category TEXT
                )
        ''')

        # Create advanced_detection_results table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS advanced_detection_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        temporal_analysis TEXT,
                        citation_analysis TEXT,
                        behavioral_analysis TEXT,
                        multimodal_analysis TEXT,
                        adversarial_analysis TEXT,
                        ensemble_prediction TEXT,
                        risk_prediction TEXT,
                        bias_adjusted_score REAL,
                        blockchain_hash TEXT,
                        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
                    )
        ''')

        # Create allergies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS allergies (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            allergen TEXT,
                            severity TEXT,
                            reaction_description TEXT,
                            diagnosed_date TEXT,
                            provider TEXT,
                            verified INTEGER DEFAULT 0,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create assessment_competencies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_competencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id INTEGER NOT NULL,
                    competency_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
                    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
                )
        ''')

        # Create assessment_outcomes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id INTEGER NOT NULL,
                    outcome_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
                    FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
                )
        ''')

        # Create assessments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
                    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_name TEXT NOT NULL,
                    assessment_type TEXT NOT NULL,
                    module_code TEXT NOT NULL,
                    max_points REAL NOT NULL,
                    weight REAL NOT NULL,
                    due_date TEXT,
                    date_created TEXT DEFAULT (datetime('now')),
                    description TEXT,
                    rubric TEXT,
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create business_directory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_directory (
                    business_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    business_name TEXT,
                    business_description TEXT,
                    industry TEXT,
                    website TEXT,
                    contact_email TEXT,
                    services_offered TEXT,
                    location TEXT,
                    created_date TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create care_plans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS care_plans (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            condition_id INTEGER,
                            plan_name TEXT,
                            description TEXT,
                            start_date TEXT,
                            end_date TEXT,
                            provider TEXT,
                            status TEXT DEFAULT 'active',
                            goals TEXT,
                            interventions TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id),
                            FOREIGN KEY (condition_id) REFERENCES medical_conditions (id)
                        )
        ''')

        # Create collection_agencies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_agencies (
                    agency_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agency_name TEXT NOT NULL,
                    contact_email TEXT,
                    contact_phone TEXT,
                    commission_rate DECIMAL(5,2),
                    minimum_amount DECIMAL(10,2),
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create collection_cases table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_cases (
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    agency_id INTEGER,
                    total_debt DECIMAL(10,2) NOT NULL,
                    case_status TEXT DEFAULT 'new', -- new, assigned, in_progress, resolved, closed
                    assigned_date TEXT,
                    resolution_date TEXT,
                    amount_collected DECIMAL(10,2) DEFAULT 0,
                    commission_paid DECIMAL(10,2) DEFAULT 0,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (agency_id) REFERENCES collection_agencies (agency_id)
                )
        ''')

        # Create competencies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competencies (
                    competency_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT
                )
        ''')

        # Create competency_levels table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competency_levels (
                    level_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competency_id INTEGER NOT NULL,
                    level_name TEXT NOT NULL,
                    level_value INTEGER NOT NULL,
                    description TEXT,
                    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
                )
        ''')

        # Create competition_participants table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competition_participants (
                    participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competition_id INTEGER,
                    club_id INTEGER,
                    student_id TEXT,
                    registration_date TEXT,
                    score REAL DEFAULT 0.0,
                    rank_position INTEGER,
                    FOREIGN KEY (competition_id) REFERENCES club_competitions (competition_id),
                    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create currency_settings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS currency_settings (
                    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_currency TEXT DEFAULT 'GBP',
                    auto_update_rates BOOLEAN DEFAULT 1,
                    rate_update_frequency INTEGER DEFAULT 24, -- hours
                    last_rate_update TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create data_retention table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_retention (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        data_type TEXT NOT NULL,
                        retention_period INTEGER NOT NULL,
                        deletion_date TEXT,
                        status TEXT DEFAULT 'active'
                    )
        ''')

        # Create data_retention_policies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_retention_policies (
                    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT NOT NULL,
                    retention_period_months INTEGER NOT NULL,
                    deletion_method TEXT DEFAULT 'soft', -- 'soft', 'hard', 'anonymize'
                    last_cleanup_date TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create donor_recognition table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS donor_recognition (
                    recognition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    recognition_level TEXT,
                    total_donated REAL,
                    recognition_date TEXT,
                    benefits TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create emergency_contacts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            contact_name TEXT,
                            relationship TEXT,
                            phone_primary TEXT,
                            phone_secondary TEXT,
                            email TEXT,
                            address TEXT,
                            priority_order INTEGER,
                            medical_decision_maker INTEGER DEFAULT 0,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create engagement_points table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_points (
                    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    activity_type TEXT,
                    points_earned INTEGER,
                    activity_date TEXT,
                    description TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create equipment_checkouts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment_checkouts (
                    checkout_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER,
                    borrower_id TEXT,
                    club_id INTEGER,
                    checkout_date TEXT,
                    expected_return TEXT,
                    actual_return TEXT,
                    condition_out TEXT,
                    condition_in TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'checked_out',
                    FOREIGN KEY (equipment_id) REFERENCES union_equipment (equipment_id),
                    FOREIGN KEY (borrower_id) REFERENCES students (student_id),
                    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
                )
        ''')

        # Create exchange_rates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rates (
                    rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_currency TEXT NOT NULL,
                    to_currency TEXT NOT NULL,
                    exchange_rate DECIMAL(10,6) NOT NULL,
                    rate_date TEXT NOT NULL,
                    source TEXT, -- 'manual', 'api', 'bank'
                    created_at TEXT
                )
        ''')

        # Create extension_requests table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS extension_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    new_due_date TIMESTAMP NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reviewed_by INTEGER,
                    reviewed_date TIMESTAMP,
                    review_comments TEXT,
                    FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (reviewed_by) REFERENCES users (id)
                )
        ''')

        # Create extracurricular_activities table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS extracurricular_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        activity_name TEXT,
                        description TEXT,
                        supervisor TEXT,
                        meeting_schedule TEXT,
                        location TEXT,
                        max_participants INTEGER,
                        fee DECIMAL(10,2) DEFAULT 0.00,
                        status TEXT DEFAULT 'active'
                    )
        ''')

        # Create graduation_requirements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS graduation_requirements (
                            id TEXT PRIMARY KEY,
                            requirement_name TEXT NOT NULL,
                            requirement_type TEXT NOT NULL,
                            credits_required INTEGER,
                            course_category TEXT,
                            deadline_date TEXT,
                            is_mandatory BOOLEAN DEFAULT TRUE,
                            created_at TEXT NOT NULL
                        )
        ''')

        # holiday_calendars removed — folded into the single canonical
        # academic_calendar_events table (event_type='holiday_calendar').

        # Create holidays table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS holidays (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        holiday_name TEXT,
                        start_date DATE,
                        end_date DATE,
                        description TEXT,
                        recurring BOOLEAN DEFAULT 0
                    )
        ''')

        # Create institutions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS institutions (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        type TEXT,
                        country TEXT,
                        created_at TEXT NOT NULL
                    )
        ''')

        # Create intervention_types table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS intervention_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    description TEXT
                )
        ''')

        # Create kb_articles table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS kb_articles (
                    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    category TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    author_id TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    updated_datetime TEXT,
                    published_datetime TEXT,
                    is_published BOOLEAN DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    helpful_votes INTEGER DEFAULT 0,
                    not_helpful_votes INTEGER DEFAULT 0,
                    search_keywords TEXT,  -- Space-separated keywords for search
                    related_articles TEXT  -- JSON array of related article IDs
                )
        ''')

        # Create knowledge_base table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_base (
                    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT,
                    tags TEXT,
                    author_id INTEGER,
                    status TEXT DEFAULT 'draft',
                    views INTEGER DEFAULT 0,
                    helpful_votes INTEGER DEFAULT 0,
                    unhelpful_votes INTEGER DEFAULT 0,
                    search_keywords TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (author_id) REFERENCES users (id)
                )
        ''')

        # Create learning_outcomes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_outcomes (
                    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    outcome_code TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT,
                    level INTEGER
                )
        ''')

        # Create networking_connections table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS networking_connections (
                    connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requester_id TEXT,
                    recipient_id TEXT,
                    connection_date TEXT,
                    status TEXT DEFAULT 'pending',
                    message TEXT,
                    FOREIGN KEY (requester_id) REFERENCES alumni (alumni_id),
                    FOREIGN KEY (recipient_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create newsletters table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS newsletters (
                    newsletter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT,
                    template_id INTEGER,
                    target_audience TEXT,
                    send_date TEXT,
                    created_date TEXT,
                    created_by TEXT,
                    status TEXT DEFAULT 'draft',
                    open_rate REAL DEFAULT 0.0,
                    click_rate REAL DEFAULT 0.0
                )
        ''')

        # Create outcome_results table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS outcome_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    outcome_id INTEGER NOT NULL,
                    achievement_level REAL,
                    assessment_date TEXT,
                    evidence TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
                )
        ''')

        # Create photo_gallery table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS photo_gallery (
                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    uploaded_by TEXT,
                    photo_path TEXT,
                    caption TEXT,
                    upload_date TEXT,
                    is_featured BOOLEAN DEFAULT 0,
                    FOREIGN KEY (event_id) REFERENCES alumni_events (event_id),
                    FOREIGN KEY (uploaded_by) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create privacy_consent table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS privacy_consent (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        consent_type TEXT NOT NULL,
                        granted INTEGER NOT NULL,
                        granted_at TEXT NOT NULL,
                        expires_at TEXT,
                        version TEXT NOT NULL,
                        UNIQUE(student_id, consent_type)
                    )
        ''')

        # Create processing_queue table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS processing_queue (
                        id TEXT PRIMARY KEY,
                        submission_data TEXT NOT NULL,
                        priority INTEGER DEFAULT 1,
                        status TEXT DEFAULT 'queued',
                        created_at TEXT NOT NULL,
                        processed_at TEXT
                    )
        ''')

        # Create project_milestones table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_milestones (
                            id TEXT PRIMARY KEY,
                            project_name TEXT NOT NULL,
                            milestone_name TEXT NOT NULL,
                            due_date TEXT NOT NULL,
                            completion_percentage REAL DEFAULT 0.0,
                            status TEXT DEFAULT 'pending',
                            course_id TEXT,
                            student_id TEXT,
                            description TEXT,
                            created_at TEXT NOT NULL,
                            last_updated TEXT,
                            FOREIGN KEY (course_id) REFERENCES courses (id),
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create provider_schedules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS provider_schedules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            provider_name TEXT,
                            day_of_week INTEGER,
                            start_time TEXT,
                            end_time TEXT,
                            max_appointments INTEGER DEFAULT 10,
                            specialty TEXT,
                            location TEXT,
                            active INTEGER DEFAULT 1,
                            created_at TEXT
                        )
        ''')

        # Create ranked_votes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ranked_votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    election_id INTEGER,
                    voter_id TEXT,
                    candidate_preferences TEXT,  -- JSON string of ranked preferences
                    vote_time TEXT,
                    FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
                    FOREIGN KEY (voter_id) REFERENCES students (student_id)
                )
        ''')

        # Create recommended_interventions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recommended_interventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    risk_factor_id INTEGER,
                    intervention_type_id INTEGER,
                    recommended_date TEXT,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (risk_factor_id) REFERENCES admin_risk_factors (id),
                    FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (id)
                )
        ''')

        # Create referrals table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            referring_provider TEXT,
                            specialist_provider TEXT,
                            specialty TEXT,
                            reason TEXT,
                            urgency TEXT,
                            referral_date TEXT,
                            appointment_date TEXT,
                            status TEXT DEFAULT 'pending',
                            notes TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create resources table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS resources (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            type TEXT NOT NULL,
                            capacity INTEGER,
                            location TEXT,
                            equipment TEXT,
                            status TEXT DEFAULT 'available',
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create risk_assessments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_assessments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            assessment_type TEXT,
                            risk_score INTEGER,
                            risk_factors TEXT,
                            recommendations TEXT,
                            assessed_date TEXT,
                            assessed_by TEXT,
                            follow_up_date TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create admin_risk_factors table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_risk_factors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    factor_name TEXT,
                    factor_value REAL,
                    assessment_id INTEGER,
                    date_calculated TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
                )
        ''')

        # Create rubric_criteria table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rubric_criteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rubric_id INTEGER NOT NULL,
                    criteria_name TEXT NOT NULL,
                    description TEXT,
                    max_points REAL NOT NULL,
                    weight REAL DEFAULT 1.0,
                    display_order INTEGER DEFAULT 0,
                    FOREIGN KEY (rubric_id) REFERENCES rubrics (id) ON DELETE CASCADE
                )
        ''')

        # Create rubrics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rubrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    total_points REAL NOT NULL DEFAULT 100,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        # Create schedule_conflicts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule_conflicts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conflict_type TEXT,
                        description TEXT,
                        affected_schedules TEXT,
                        resolved BOOLEAN DEFAULT 0,
                        resolution_notes TEXT,
                        detected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_date TIMESTAMP
                    )
        ''')

        # Create schedule_history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_id INTEGER,
                        action TEXT,
                        old_values TEXT,
                        new_values TEXT,
                        changed_by TEXT,
                        change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        # school_calendar removed — folded into the single canonical
        # academic_calendar_events table (event_type='school_event').

        # Create screening_schedules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS screening_schedules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            screening_type TEXT,
                            due_date TEXT,
                            completed_date TEXT,
                            status TEXT DEFAULT 'due',
                            provider TEXT,
                            results TEXT,
                            next_due_date TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create search_presets table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_presets (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            user_id TEXT NOT NULL,
                            filters TEXT NOT NULL,
                            date_added TEXT NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE
                        )
        ''')

        # Create shared_resources table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_resources (
                    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uploader_id TEXT,
                    resource_title TEXT,
                    resource_type TEXT,
                    subject TEXT,
                    file_path TEXT,
                    description TEXT,
                    upload_date TEXT,
                    downloads INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    FOREIGN KEY (uploader_id) REFERENCES students (student_id)
                )
        ''')

        # Create sla_policies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sla_policies (
                    sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    priority TEXT,
                    impact TEXT,
                    urgency TEXT,
                    first_response_hours INTEGER,
                    resolution_hours INTEGER,
                    escalation_hours INTEGER,
                    business_hours_only BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create staff_schedules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_schedules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_id TEXT NOT NULL,
                        shift_date DATE NOT NULL,
                        start_time TIME NOT NULL,
                        end_time TIME NOT NULL,
                        position TEXT NOT NULL,
                        status TEXT DEFAULT 'scheduled',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        # Create survey_responses table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    survey_id INTEGER,
                    alumni_id TEXT,
                    responses TEXT,
                    submission_date TEXT,
                    FOREIGN KEY (survey_id) REFERENCES event_surveys (survey_id),
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="other"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="other", error=str(e)))
        if 'conn' in locals():
            conn.close()

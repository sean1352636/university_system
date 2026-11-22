"""The health portal's schema — one declaration of every health table.

Applied by migration ``a0d2f4b6c8e1`` and, once per database file, by
:func:`apply_to_connection` (the CLI menu, the GUI window, the dental clinic,
the integration/security screens and the templates all call it instead of
declaring tables themselves). The definitions are the live column sets of
``student_records.db``; :func:`apply` creates a missing table and adds any
column an older table lacks, and never drops or rewrites anything. It also
applies the sibling modules (``first_aid_schema``, ``workflow_schema``,
``accommodation_schema``), so one call stands the whole health portal up.

Where each fact lives
---------------------
* **Health profile** (blood type, GP / doctor, insurance, summary of regular
  medications, conditions and allergies): ``medical_info``, one row per
  student (unique index) — ``application/health/profile``. The parent
  portal's form and the sixth-form import write it too.
* **Allergies**, one row each with severity (what the prescribing screen
  reads): ``allergies``. **Diagnoses / conditions**: ``medical_conditions``.
  **Prescriptions**: ``prescriptions`` (health centre) and
  ``dentist_prescriptions`` (dental clinic); both are screened by
  ``application/health/prescribing``.
* **Visits and clinical notes**: ``health_records`` (description sealed when
  confidential; soft-deleted via ``archived``). Its ``allergies`` /
  ``blood_type`` / ``conditions`` / ``medications`` / ``insurance_*`` /
  ``last_updated`` columns are a retired copy of the profile: no writer, and
  migration ``a0d2f4b6c8e1`` moved any values into ``medical_info``.
* **Emergency contacts**: ``emergency_contacts`` (``contact_name`` /
  ``phone_primary``; ``name`` / ``phone`` are the folded-in legacy layout).
  ``students.emergency_contact`` is the registry's single free-text field,
  not a health record.
* **Dental intake**: ``dentist_patients.medical_history`` / ``allergies`` stay
  the clinic's own sealed intake text (the prescribing screen reads them).
* ``student_medical_info`` (parent portal, ``core_schemas``) is a different
  thing — the in-school medication-administration plan (dose, time, expiry)
  — and is not declared here.
* **Personal metrics** a student logs for themselves (weight, sleep, mood…):
  ``personal_health_metrics``.

Appointments are not merged
---------------------------
``health_appointments`` (health centre), ``dentist_appointments`` (FK target
of ``dentist_treatments``; keyed on ``dentist_patients``), and the wellbeing
domain's ``counseling_appointments`` / ``mental_health_appointments`` stay
separate tables. Counselling and mental-health notes are sealed and readable
only by that area's practitioners (``access.scope_area``); one physical table
would put them a missing ``WHERE`` away from every health-centre query, and a
merged table could not keep the dental foreign keys. They are read together
only through ``application/health/diary.appointments``, which applies each
area's scope. The two wellbeing tables belong to the wellbeing schema
(``wellness_service`` / ``health_wellness_schemas``) and are not declared
here.

Tables the portal uses but does not own (``SHARED_TABLES``: audit trail,
security settings, backups, RBAC, security incidents, encryption keys) are
declared with their live definitions so the portal can stand up on a bare
database; their owners' schemas are authoritative.
"""

from __future__ import annotations

import sqlite3

TABLES = (
    # -- Profile, allergies, conditions, prescriptions and visits
    """CREATE TABLE IF NOT EXISTS medical_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        blood_type TEXT,
        allergies TEXT,
        medications TEXT,
        conditions TEXT,
        doctor_name TEXT,
        doctor_phone TEXT,
        insurance_provider TEXT,
        insurance_policy TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS allergies (
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
    )""",
    """CREATE TABLE IF NOT EXISTS medical_conditions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        condition_name TEXT,
        icd_code TEXT,
        severity TEXT,
        diagnosed_date TEXT,
        status TEXT DEFAULT 'active',
        provider TEXT,
        notes TEXT,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        medication_name TEXT,
        dosage TEXT,
        frequency TEXT,
        prescribed_date TEXT,
        start_date TEXT,
        end_date TEXT,
        prescriber TEXT,
        pharmacy TEXT,
        status TEXT DEFAULT 'active',
        notes TEXT,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS health_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        record_type TEXT,
        record_date TEXT,
        description TEXT,
        provider TEXT,
        confidential INTEGER DEFAULT 0,
        created_at TEXT,
        encrypted_data TEXT,
        -- Retired: a second copy of the profile (application/health/profile,
        -- medical_info). Nothing writes these; kept so old rows still read.
        allergies TEXT,
        blood_type TEXT,
        conditions TEXT,
        insurance_policy_number TEXT,
        insurance_provider TEXT,
        last_updated TIMESTAMP,
        medications TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS vital_signs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        measurement_date TEXT,
        blood_pressure_systolic INTEGER,
        blood_pressure_diastolic INTEGER,
        heart_rate INTEGER,
        temperature REAL,
        weight REAL,
        height REAL,
        bmi REAL,
        recorded_by TEXT,
        notes TEXT,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS care_plans (
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
    )""",
    """CREATE TABLE IF NOT EXISTS referrals (
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
    )""",
    """CREATE TABLE IF NOT EXISTS screening_schedules (
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
    )""",
    """CREATE TABLE IF NOT EXISTS risk_assessments (
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
    )""",
    """CREATE TABLE IF NOT EXISTS vaccination_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        vaccine_name TEXT,
        administered_date TEXT,
        expiry_date TEXT,
        lot_number TEXT,
        manufacturer TEXT,
        administered_by TEXT,
        location TEXT,
        adverse_reaction INTEGER DEFAULT 0,
        reaction_description TEXT,
        verified INTEGER DEFAULT 0,
        verified_by TEXT,
        verified_date TEXT,
        created_at TEXT,
        last_vaccination_date TEXT,
        next_due_date TEXT,
        vaccine_type TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS lab_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        test_name TEXT,
        test_code TEXT,
        result_value TEXT,
        reference_range TEXT,
        units TEXT,
        status TEXT,
        ordered_date TEXT,
        collected_date TEXT,
        resulted_date TEXT,
        ordering_provider TEXT,
        lab_name TEXT,
        abnormal_flag TEXT,
        created_at TEXT,
        date_performed TEXT,
        normal_range TEXT,
        reviewed INTEGER DEFAULT 0,
        test_type TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS insurance_information (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        insurance_provider TEXT,
        policy_number TEXT,
        group_number TEXT,
        subscriber_name TEXT,
        relationship_to_subscriber TEXT,
        effective_date TEXT,
        expiry_date TEXT,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS emergency_contacts (
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
        is_primary INTEGER DEFAULT 0,
        name TEXT,
        phone TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    # -- Appointments and clinic schedules
    """CREATE TABLE IF NOT EXISTS health_appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        appointment_type TEXT,
        appointment_date TEXT,
        appointment_time TEXT,
        provider TEXT,
        reason TEXT,
        status TEXT DEFAULT 'scheduled',
        notes TEXT,
        scheduled_at TEXT,
        department TEXT,
        has_conflict INTEGER DEFAULT 0,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS provider_schedules (
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
    )""",
    # -- Population health and programmes
    """CREATE TABLE IF NOT EXISTS wellness_participation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        program_name TEXT,
        enrollment_date TEXT,
        completion_date TEXT,
        status TEXT DEFAULT 'enrolled',
        progress_score INTEGER DEFAULT 0,
        goals_met INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS health_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_name TEXT,
        campaign_type TEXT,
        start_date TEXT,
        end_date TEXT,
        target_population TEXT,
        description TEXT,
        goals TEXT,
        status TEXT DEFAULT 'planned',
        budget REAL,
        created_by TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS disease_surveillance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disease_name TEXT,
        case_date TEXT,
        student_id TEXT,
        symptoms TEXT,
        severity TEXT,
        status TEXT DEFAULT 'under_investigation',
        contact_tracing_needed INTEGER DEFAULT 0,
        contact_tracing_completed INTEGER DEFAULT 0,
        contacts_identified INTEGER DEFAULT 0,
        reported_to_health_dept INTEGER DEFAULT 0,
        isolation_required INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS health_advisories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        advisory_type TEXT,
        content TEXT,
        priority TEXT,
        target_audience TEXT,
        effective_date TEXT,
        expiry_date TEXT,
        issued_by TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS health_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_name TEXT,
        metric_value REAL,
        measurement_date TEXT,
        category TEXT,
        subcategory TEXT,
        metadata TEXT,
        calculated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS quality_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_name TEXT,
        metric_category TEXT,
        target_value REAL,
        actual_value REAL,
        measurement_period TEXT,
        measured_date TEXT,
        status TEXT,
        improvement_needed INTEGER DEFAULT 0,
        created_at TEXT
    )""",
    # -- Dental clinic (FKs to dentist_patients / treatments)
    """CREATE TABLE IF NOT EXISTS dentist_patients (
        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_number TEXT UNIQUE NOT NULL,
        user_id TEXT NOT NULL,
        user_name TEXT NOT NULL,
        user_email TEXT,
        user_phone TEXT,
        date_of_birth DATE,
        address TEXT,
        emergency_contact TEXT,
        emergency_phone TEXT,
        medical_history TEXT,
        allergies TEXT,
        insurance_provider TEXT,
        insurance_number TEXT,
        last_visit DATE,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS dentist_appointments (
        appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_ref TEXT UNIQUE NOT NULL,
        patient_id INTEGER NOT NULL,
        dentist_id TEXT NOT NULL,
        dentist_name TEXT NOT NULL,
        appointment_date DATE NOT NULL,
        appointment_time TEXT NOT NULL,
        duration_minutes INTEGER DEFAULT 30,
        treatment_type TEXT NOT NULL,
        status TEXT DEFAULT 'scheduled',
        notes TEXT,
        reminder_sent INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT,
        patient_name TEXT,
        fee REAL,
        FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
    )""",
    """CREATE TABLE IF NOT EXISTS dentist_treatments (
        treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id INTEGER,
        patient_id INTEGER NOT NULL,
        dentist_id TEXT NOT NULL,
        dentist_name TEXT NOT NULL,
        treatment_type TEXT NOT NULL,
        treatment_date DATE NOT NULL,
        tooth_number TEXT,
        description TEXT,
        fee DECIMAL(10,2) NOT NULL,
        payment_status TEXT DEFAULT 'pending',
        notes TEXT,
        follow_up_required INTEGER DEFAULT 0,
        follow_up_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        procedure_notes TEXT,
        diagnosis TEXT,
        FOREIGN KEY (appointment_id) REFERENCES dentist_appointments(appointment_id),
        FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
    )""",
    """CREATE TABLE IF NOT EXISTS dentist_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        record_type TEXT NOT NULL,
        record_date DATE NOT NULL,
        description TEXT,
        file_path TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
    )""",
    """CREATE TABLE IF NOT EXISTS dentist_prescriptions (
        prescription_id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        dentist_id TEXT NOT NULL,
        dentist_name TEXT NOT NULL,
        treatment_id INTEGER,
        medication TEXT NOT NULL,
        dosage TEXT NOT NULL,
        frequency TEXT NOT NULL,
        duration TEXT NOT NULL,
        instructions TEXT,
        prescribed_date DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id),
        FOREIGN KEY (treatment_id) REFERENCES dentist_treatments(treatment_id)
    )""",
    # -- Integrations, privacy, templates
    """CREATE TABLE IF NOT EXISTS integration_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT,                          -- e.g., 'insurance','lab','hl7','fhir'
        system   TEXT,                          -- optional: vendor/system name
        event_type TEXT,
        status TEXT,                            -- success, error, pending
        message TEXT,
        correlation_id TEXT,
        http_status INTEGER,
        duration_ms INTEGER,
        endpoint TEXT,
        payload TEXT,
        response TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS insurance_integration_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id TEXT,
        patient_id TEXT,
        event_type TEXT,                        -- submitted/approved/denied/cancelled
        status TEXT,
        external_id TEXT,
        correlation_id TEXT,
        payload TEXT,
        response TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS lab_integration_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        patient_id TEXT,
        test_code TEXT,
        event_type TEXT,                        -- order_sent/result_received/ack/error
        status TEXT,
        external_id TEXT,
        correlation_id TEXT,
        payload TEXT,
        response TEXT,
        result_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        queue_name TEXT,                        -- optional: 'default','labs','claims'
        entity_type TEXT,                       -- e.g., 'student','claim','lab_order'
        entity_id TEXT,
        operation TEXT,                         -- upsert/delete/sync
        payload TEXT,
        priority INTEGER DEFAULT 5,
        attempts INTEGER DEFAULT 0,
        next_attempt_at TEXT,
        last_error TEXT,
        status TEXT,                            -- pending/locked/failed/done
        locked_by TEXT,
        locked_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS data_privacy_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        policy_key TEXT UNIQUE NOT NULL,
        value TEXT,
        description TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        policy_name TEXT,
        status TEXT,
        last_updated TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS data_retention_policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_type TEXT,
        retention_period_days INTEGER,
        auto_archive INTEGER DEFAULT 0,
        auto_delete INTEGER DEFAULT 0,
        created_at TEXT,
        retention_period_months INTEGER,
        deletion_method TEXT DEFAULT 'soft',
        last_cleanup_date TEXT,
        is_active BOOLEAN DEFAULT 1,
        updated_at TEXT,
        policy_id INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS failed_logins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        ip_address TEXT,
        reason TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT,
        body TEXT NOT NULL,
        created_by TEXT,
        is_shared INTEGER DEFAULT 0,            -- 0/1
        version INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )""",
)

SHARED_TABLES = (
    """CREATE TABLE IF NOT EXISTS audit_trail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        action TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT,
        user_id INTEGER,
        username TEXT,
        ip_address TEXT,
        details TEXT,
        function_name TEXT,
        module_name TEXT,
        success INTEGER DEFAULT 1,
        error_message TEXT,
        data_hash TEXT,
        old_values TEXT,
        new_values TEXT,
        user_agent TEXT,
        duration REAL,
        audit_id INTEGER,
        table_name TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS security_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_name TEXT UNIQUE,
        setting_value TEXT,
        updated_at TEXT,
        updated_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS backup_history (
        id TEXT PRIMARY KEY,
        backup_type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER,
        backup_time TEXT NOT NULL,
        status TEXT NOT NULL,
        notes TEXT,
        created_at TEXT,
        size_bytes INTEGER,
        backup_filename TEXT,
        backup_size_mb REAL,
        created_by TEXT,
        timestamp TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        permission_name TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_id INTEGER NOT NULL,
        permission_id INTEGER NOT NULL,
        FOREIGN KEY (role_id) REFERENCES roles (id),
        FOREIGN KEY (permission_id) REFERENCES permissions (id),
        UNIQUE(role_id, permission_id)
    )""",
    """CREATE TABLE IF NOT EXISTS security_incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT UNIQUE,                -- human-friendly ref (e.g., INC-2025-0001)
        summary TEXT,
        description TEXT,
        severity TEXT,                          -- low/medium/high/critical
        status TEXT,                            -- open/contained/eradicated/monitoring/closed
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
        reported_by TEXT,
        assigned_to TEXT,
        category TEXT,                          -- phishing, malware, policy_violation, etc.
        source TEXT,                            -- system/user/external
        affected_user TEXT,
        containment TEXT,
        eradication TEXT,
        recovery TEXT,
        resolved_at TEXT,
        root_cause TEXT,
        tags TEXT,
        title TEXT,
        opened_at TEXT,
        closed_at TEXT,
        priority TEXT,
        resolution_notes TEXT,
        created_at TIMESTAMP DEFAULT NULL,
        detected_by INTEGER,
        incident_type TEXT,
        resolution TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS security_incident_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_pk INTEGER NOT NULL,           -- FK to security_incidents.id
        event_time TEXT DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT,                        -- note, containment, escalation, closure, etc.
        details TEXT,
        actor TEXT,
        incident_id INTEGER,
        description TEXT,
        performed_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS encryption_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_id TEXT UNIQUE NOT NULL,
        public_key TEXT,
        private_key_encrypted TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        rotated_at TEXT,
        is_active INTEGER DEFAULT 1,
        algorithm TEXT,
        status TEXT,
        encrypted_key TEXT,
        key_type TEXT DEFAULT 'fernet',
        version INTEGER DEFAULT 1
    )""",
)

INDEXES = (
    'CREATE INDEX IF NOT EXISTS idx_health_records_record_date ON health_records(record_date)',
    'CREATE INDEX IF NOT EXISTS idx_health_records_record_type ON health_records(record_type)',
    'CREATE INDEX IF NOT EXISTS idx_health_records_student_id ON health_records(student_id)',
    'CREATE INDEX IF NOT EXISTS idx_il_correlation ON integration_logs(correlation_id)',
    'CREATE INDEX IF NOT EXISTS idx_il_created ON integration_logs(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_il_event_type ON integration_logs(event_type)',
    'CREATE INDEX IF NOT EXISTS idx_il_provider ON integration_logs(provider)',
    'CREATE INDEX IF NOT EXISTS idx_ins_claim ON insurance_integration_events(claim_id)',
    'CREATE INDEX IF NOT EXISTS idx_ins_created ON insurance_integration_events(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_ins_status ON insurance_integration_events(status)',
    'CREATE INDEX IF NOT EXISTS idx_lab_created ON lab_integration_events(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_lab_order ON lab_integration_events(order_id)',
    'CREATE INDEX IF NOT EXISTS idx_lab_status ON lab_integration_events(status)',
    'CREATE INDEX IF NOT EXISTS idx_sq_next_attempt ON sync_queue(next_attempt_at)',
    'CREATE INDEX IF NOT EXISTS idx_sq_priority ON sync_queue(priority)',
    'CREATE INDEX IF NOT EXISTS idx_sq_status ON sync_queue(status)',
    'CREATE INDEX IF NOT EXISTS idx_audit_trail_action ON audit_trail(action, timestamp DESC)',
    'CREATE INDEX IF NOT EXISTS idx_audit_trail_resource ON audit_trail(resource_type, resource_id)',
    'CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp ON audit_trail(timestamp DESC)',
    'CREATE INDEX IF NOT EXISTS idx_audit_trail_user ON audit_trail(user_id, timestamp DESC)',
    'CREATE INDEX IF NOT EXISTS idx_inc_detected ON security_incidents(detected_at)',
    'CREATE INDEX IF NOT EXISTS idx_inc_severity ON security_incidents(severity)',
    'CREATE INDEX IF NOT EXISTS idx_inc_status ON security_incidents(status)',
    'CREATE INDEX IF NOT EXISTS idx_incidents_status ON security_incidents(status, detected_at)',
)

NEW_TABLES = (
    """CREATE TABLE IF NOT EXISTS personal_health_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL REFERENCES students (student_id),
        metric TEXT NOT NULL,
        value REAL NOT NULL,
        value2 REAL,
        unit TEXT,
        notes TEXT,
        recorded_on TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
)

EXTRA_INDEXES = (
    # One profile row per student (migration a0d2f4b6c8e1 merges any duplicates first).
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_medical_info_student ON medical_info(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_allergies_student ON allergies(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_medical_conditions_student ON medical_conditions(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_prescriptions_student ON prescriptions(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_health_appointments_student ON health_appointments(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category)",
    "CREATE INDEX IF NOT EXISTS ix_personal_health_metrics ON personal_health_metrics "
    "(student_id, metric, recorded_on)",
)

# When an older table gains one of these alias columns, fill it from the
# column it mirrors (the integration / security screens read either name).
# A value is the UPDATE, or ``(UPDATE, column it needs)``.
BACKFILLS = {
    ("data_privacy_settings", "policy_name"):
        "UPDATE data_privacy_settings SET policy_name = policy_key WHERE policy_name IS NULL",
    ("data_privacy_settings", "status"):
        "UPDATE data_privacy_settings SET status = CASE WHEN LOWER(COALESCE(value, '')) IN "
        "('1','true','on','enabled','enable') THEN 'enabled' WHEN LOWER(COALESCE(value, '')) "
        "IN ('0','false','off','disabled','disable') THEN 'disabled' ELSE value END "
        "WHERE status IS NULL",
    ("data_privacy_settings", "last_updated"):
        "UPDATE data_privacy_settings SET last_updated = updated_at WHERE last_updated IS NULL",
    ("encryption_keys", "algorithm"):
        "UPDATE encryption_keys SET algorithm = COALESCE(algorithm, 'unknown')",
    ("encryption_keys", "status"):
        "UPDATE encryption_keys SET status = CASE COALESCE(is_active, 0) WHEN 1 THEN 'active' "
        "ELSE 'inactive' END WHERE status IS NULL",
    ("security_incidents", "title"):
        "UPDATE security_incidents SET title = COALESCE(title, summary)",
    ("security_incidents", "opened_at"):
        "UPDATE security_incidents SET opened_at = detected_at WHERE opened_at IS NULL",
    ("security_incidents", "closed_at"):
        "UPDATE security_incidents SET closed_at = resolved_at WHERE closed_at IS NULL",
    ("security_incidents", "priority"):
        "UPDATE security_incidents SET priority = CASE LOWER(COALESCE(severity, '')) "
        "WHEN 'critical' THEN 'p0' WHEN 'high' THEN 'p1' WHEN 'medium' THEN 'p2' "
        "WHEN 'low' THEN 'p3' ELSE NULL END WHERE priority IS NULL",
    # (only when the old ``content`` column is there to copy from)
    ("templates", "body"): ("UPDATE templates SET body = COALESCE(body, content)", "content"),
}

# Seeded only into an empty table.
RETENTION_POLICIES = (
    ("health_records", 2555, 1, 0),        # 7 years
    ("vaccination_records", 2555, 1, 0),
    ("appointments", 1095, 1, 0),          # 3 years
    ("audit_trail", 2555, 0, 0),           # 7 years, never auto-deleted
    ("prescriptions", 1825, 1, 0),         # 5 years
    ("lab_results", 2555, 1, 0),
    ("vital_signs", 1095, 1, 0),
)
SECURITY_SETTINGS = (
    ("session_timeout_minutes", "30"),
    ("max_failed_login_attempts", "3"),
    ("password_expiry_days", "90"),
    ("require_2fa_for_providers", "0"),    # not enforced here: 2FA is platform sign-in
    ("encryption_enabled", "1"),
    ("audit_logging_enabled", "1"),
    ("ip_restriction_enabled", "0"),
    ("allowed_ip_ranges", ""),
)

_EXPECTED: dict | None = None


def _expected_columns() -> dict:
    """``table -> [(column, declaration)]`` for every declared table, read
    from the declarations themselves (built once in memory), so the column
    list is never written down twice. Columns that ``ALTER TABLE`` cannot add
    (primary keys, UNIQUE, NOT NULL without a default) are left out; every
    such column is in the original definition of its table."""
    global _EXPECTED
    if _EXPECTED is None:
        mem = sqlite3.connect(":memory:")
        try:
            for ddl in TABLES + NEW_TABLES + SHARED_TABLES:
                mem.execute(ddl)
            found = {}
            for (table,) in mem.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                        "AND name NOT LIKE 'sqlite_%'").fetchall():
                unique = set()
                for idx in mem.execute(f'PRAGMA index_list("{table}")').fetchall():
                    if idx[2]:
                        unique |= {r[2] for r in mem.execute(
                            f'PRAGMA index_info("{idx[1]}")').fetchall()}
                cols = []
                for _cid, name, ctype, notnull, default, pk in mem.execute(
                        f'PRAGMA table_info("{table}")').fetchall():
                    if pk or name in unique or (notnull and default is None):
                        continue
                    decl = ctype or ""
                    if notnull:
                        decl += " NOT NULL"
                    if default is not None:
                        decl += f" DEFAULT {default}"
                    cols.append((name, decl.strip()))
                found[table] = cols
        finally:
            mem.close()
        _EXPECTED = found
    return _EXPECTED


def _columns(execute, table) -> set:
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def _medical_info_duplicates(execute) -> bool:
    return bool(execute("SELECT 1 FROM medical_info GROUP BY student_id HAVING COUNT(*) > 1 "
                        "LIMIT 1").fetchone())


def _students_dob(execute) -> None:
    """The university reads ``students.dob``. A database that has only
    ``date_of_birth`` gains ``dob`` (copied across); one that has ``dob`` is
    left alone — the second column the old runtime fix added would only
    drift (``records/analytics/population._dob_column`` reads either)."""
    cols = _columns(execute, "students")
    if cols and "dob" not in cols and "date_of_birth" in cols:
        execute('ALTER TABLE students ADD COLUMN dob TEXT')
        execute("UPDATE students SET dob = date_of_birth WHERE dob IS NULL OR dob = ''")


def _seed(execute) -> None:
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not execute("SELECT 1 FROM data_retention_policies LIMIT 1").fetchone():
        for row in RETENTION_POLICIES:
            execute("INSERT INTO data_retention_policies (data_type, retention_period_days, "
                    "auto_archive, auto_delete, created_at) VALUES (?, ?, ?, ?, ?)", (*row, now))
    if not execute("SELECT 1 FROM security_settings LIMIT 1").fetchone():
        for name, value in SECURITY_SETTINGS:
            execute("INSERT INTO security_settings (setting_name, setting_value, updated_at) "
                    "VALUES (?, ?, ?)", (name, value, now))


def apply(execute) -> None:
    """Create / complete every health table (idempotent; never drops)."""
    for ddl in TABLES + NEW_TABLES + SHARED_TABLES:
        execute(ddl)
    for table, columns in _expected_columns().items():
        existing = _columns(execute, table)
        for column, decl in columns:
            if existing and column not in existing:
                execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
                backfill = BACKFILLS.get((table, column))
                if isinstance(backfill, tuple):
                    backfill = backfill[0] if backfill[1] in existing else None
                if backfill:
                    execute(backfill)
    for ddl in INDEXES + EXTRA_INDEXES:
        if ddl.startswith("CREATE UNIQUE INDEX") and _medical_info_duplicates(execute):
            # Merged by migration a0d2f4b6c8e1; until it has run, don't fail
            # every health screen on the index.
            continue
        execute(ddl)
    _students_dob(execute)
    _seed(execute)
    from education_system.systems.university.domains.health.infrastructure.health import (
        accommodation_schema, first_aid_schema, workflow_schema,
    )
    first_aid_schema.apply(execute)
    workflow_schema.apply(execute)
    accommodation_schema.apply(execute)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file; inside a caller's open
    transaction it applies without committing or caching."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        # A file recreated under the same name (tests, a restore) must not
        # be taken as done: one cheap look for the newest table.
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                        "AND name = 'personal_health_metrics'").fetchone():
            return
        _APPLIED.discard(key)
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
        # The sibling modules need not run again on this file either.
        from education_system.systems.university.domains.health.infrastructure.health import (
            accommodation_schema, first_aid_schema, workflow_schema,
        )
        for module in (accommodation_schema, first_aid_schema, workflow_schema):
            module._APPLIED.add(key)


def ensure() -> None:
    """:func:`apply_to_connection` on the university database (for screens
    that have no connection of their own yet)."""
    from education_system.systems.university.domains.health.infrastructure.health.storage import (
        get_connection,
    )
    conn = get_connection()
    try:
        apply_to_connection(conn)
    finally:
        conn.close()

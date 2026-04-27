CREATE TABLE IF NOT EXISTS exam_integrity_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            randomize_questions INTEGER DEFAULT 0,
            randomize_answers INTEGER DEFAULT 0,
            question_count INTEGER,
            time_limit_minutes INTEGER,
            auto_submit INTEGER DEFAULT 1,
            browser_lockdown INTEGER DEFAULT 0,
            proctoring_provider TEXT,
            ip_restriction_enabled INTEGER DEFAULT 0,
            allowed_ips_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
        );

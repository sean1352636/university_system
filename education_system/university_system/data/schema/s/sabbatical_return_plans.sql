CREATE TABLE IF NOT EXISTS sabbatical_return_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    return_date TEXT NOT NULL,
                    transition_period_weeks INTEGER DEFAULT 4,
                    research_outputs TEXT,
                    knowledge_sharing_plan TEXT,
                    meeting_scheduled INTEGER DEFAULT 0,
                    meeting_date TEXT,
                    status TEXT DEFAULT 'draft',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (application_id) REFERENCES sabbatical_applications(application_id)
                );

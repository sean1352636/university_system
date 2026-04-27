CREATE TABLE IF NOT EXISTS graduation_requirements (
                    id TEXT PRIMARY KEY,
                    requirement_name TEXT NOT NULL,
                    requirement_type TEXT NOT NULL,
                    credits_required INTEGER,
                    course_category TEXT,
                    deadline_date TEXT,
                    is_mandatory BOOLEAN DEFAULT TRUE,
                    created_at TEXT NOT NULL
                );

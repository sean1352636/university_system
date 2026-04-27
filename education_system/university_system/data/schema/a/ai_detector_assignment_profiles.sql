CREATE TABLE IF NOT EXISTS ai_detector_assignment_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT UNIQUE NOT NULL,
                    course_code TEXT NOT NULL,
                    assignment_name TEXT NOT NULL,
                    assignment_type TEXT NOT NULL,
                    word_count_min INTEGER,
                    word_count_max INTEGER,
                    references_required INTEGER DEFAULT 0,
                    technical_terms TEXT,
                    allow_collaboration INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    created_by TEXT,
                    baseline_set INTEGER DEFAULT 0
                );

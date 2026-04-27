CREATE TABLE IF NOT EXISTS "public_profiles" (
                            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL UNIQUE,
                            public_url TEXT NOT NULL UNIQUE,
                            visibility TEXT DEFAULT 'private' CHECK(visibility IN (
                                'public', 'private', 'unlisted'
                            )),
                            show_contact BOOLEAN DEFAULT 0,
                            show_gpa BOOLEAN DEFAULT 0,
                            show_courses BOOLEAN DEFAULT 1,
                            show_projects BOOLEAN DEFAULT 1,
                            show_skills BOOLEAN DEFAULT 1,
                            show_endorsements BOOLEAN DEFAULT 1,
                            custom_sections TEXT,
                            theme TEXT DEFAULT 'professional',
                            view_count INTEGER DEFAULT 0,
                            last_viewed TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );

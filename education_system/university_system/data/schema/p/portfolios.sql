CREATE TABLE IF NOT EXISTS "portfolios" (
                        portfolio_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        bio TEXT,
                        headline TEXT,
                        profile_image_url TEXT,
                        is_public BOOLEAN DEFAULT 0,
                        public_url TEXT UNIQUE,
                        linkedin_url TEXT,
                        github_url TEXT,
                        personal_website TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

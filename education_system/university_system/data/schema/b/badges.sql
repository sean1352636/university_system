CREATE TABLE IF NOT EXISTS "badges" (
                            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL,
                            badge_type TEXT NOT NULL CHECK(badge_type IN (
                                'deans_list', 'club_officer', 'volunteer_hours',
                                'certification', 'competition_winner', 'scholarship',
                                'research_publication', 'leadership', 'academic_excellence',
                                'community_service', 'skill_mastery', 'innovation'
                            )),
                            badge_name TEXT NOT NULL,
                            description TEXT,
                            issuer TEXT NOT NULL,
                            issue_date DATE NOT NULL,
                            expiry_date DATE,
                            verification_status TEXT DEFAULT 'verified' CHECK(verification_status IN (
                                'pending', 'verified', 'expired', 'revoked'
                            )),
                            verification_code TEXT,
                            metadata TEXT,
                            icon_url TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );

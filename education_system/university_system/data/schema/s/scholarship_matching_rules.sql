CREATE TABLE IF NOT EXISTS scholarship_matching_rules (
                        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rule_name TEXT NOT NULL,
                        rule_category TEXT CHECK(rule_category IN ('academic', 'demographic', 'financial', 'activity', 'geographic', 'special')),
                        rule_weight REAL DEFAULT 1.0,
                        rule_logic TEXT NOT NULL,
                        is_required BOOLEAN DEFAULT 0,
                        description TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

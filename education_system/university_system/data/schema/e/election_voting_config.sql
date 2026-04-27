CREATE TABLE IF NOT EXISTS election_voting_config (
                    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_name TEXT NOT NULL,
                    voting_method TEXT NOT NULL,
                    allow_abstain INTEGER DEFAULT 0,
                    require_ranked INTEGER DEFAULT 0,
                    max_choices INTEGER DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                );

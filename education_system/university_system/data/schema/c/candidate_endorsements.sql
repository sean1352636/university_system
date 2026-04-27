CREATE TABLE IF NOT EXISTS candidate_endorsements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        candidate_name TEXT,
                        endorser_username TEXT,
                        visibility TEXT,
                        message TEXT,
                        endorsed_date TEXT
                    );

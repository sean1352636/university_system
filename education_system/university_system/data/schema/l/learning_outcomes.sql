CREATE TABLE IF NOT EXISTS learning_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            outcome_code TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT,
            level INTEGER
        , course TEXT, importance INTEGER, "programme_id" INTEGER, "module_code" TEXT, "code" TEXT, "bloom_level" TEXT DEFAULT 'understand', "outcome_type" TEXT DEFAULT 'programme', "created_at" TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS federated_learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                model_update BLOB NOT NULL,
                update_round INTEGER NOT NULL,
                accuracy_metric REAL,
                privacy_budget REAL,
                created_at TEXT NOT NULL
            );

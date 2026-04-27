CREATE TABLE IF NOT EXISTS ai_detector_model_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version TEXT UNIQUE NOT NULL,
                        model_path TEXT NOT NULL,
                        accuracy REAL,
                        precision_score REAL,
                        recall_score REAL,
                        f1_score REAL,
                        training_samples INTEGER,
                        is_active INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL
                    );

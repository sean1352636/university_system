CREATE TABLE IF NOT EXISTS advanced_detection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                temporal_analysis TEXT,
                citation_analysis TEXT,
                behavioral_analysis TEXT,
                multimodal_analysis TEXT,
                adversarial_analysis TEXT,
                ensemble_prediction TEXT,
                risk_prediction TEXT,
                bias_adjusted_score REAL,
                blockchain_hash TEXT,
                FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
            );

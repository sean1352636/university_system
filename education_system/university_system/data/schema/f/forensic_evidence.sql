CREATE TABLE IF NOT EXISTS forensic_evidence (
                evidence_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                description TEXT,
                file_path TEXT,
                hash_md5 TEXT,
                hash_sha1 TEXT,
                hash_sha256 TEXT,
                hash_sha512 TEXT,
                state TEXT NOT NULL DEFAULT 'ACQUIRED',
                collected_by INTEGER,
                collected_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (case_id) REFERENCES forensic_cases(case_id),
                FOREIGN KEY (collected_by) REFERENCES users(id)
            );

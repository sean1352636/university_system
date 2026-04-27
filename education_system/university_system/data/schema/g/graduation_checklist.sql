CREATE TABLE IF NOT EXISTS graduation_checklist (
                checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                program_id INTEGER NOT NULL,
                all_requirements_met INTEGER DEFAULT 0,
                gpa_requirement_met INTEGER DEFAULT 0,
                credit_requirement_met INTEGER DEFAULT 0,
                residency_requirement_met INTEGER DEFAULT 0,
                financial_clearance INTEGER DEFAULT 0,
                conferral_status TEXT DEFAULT 'pending',
                graduation_date TEXT,
                last_checked TEXT NOT NULL DEFAULT (datetime('now')), audit_date TIMESTAMP DEFAULT NULL,
                FOREIGN KEY (program_id) REFERENCES degree_programs(program_id),
                UNIQUE(student_id, program_id)
            );

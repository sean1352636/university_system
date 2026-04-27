CREATE TABLE IF NOT EXISTS practice_questions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        module_code TEXT NOT NULL,
                        source_material TEXT,
                        question_text TEXT NOT NULL,
                        answer TEXT,
                        question_type TEXT NOT NULL,
                        generated_at TEXT NOT NULL
                    );

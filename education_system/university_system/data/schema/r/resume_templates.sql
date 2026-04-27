CREATE TABLE IF NOT EXISTS resume_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT NOT NULL,
                    template_type TEXT CHECK(template_type IN (
                        'traditional', 'modern', 'creative', 'technical', 'academic'
                    )),
                    template_data TEXT NOT NULL,
                    is_default BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

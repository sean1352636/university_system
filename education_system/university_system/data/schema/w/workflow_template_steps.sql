CREATE TABLE IF NOT EXISTS workflow_template_steps (
                step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER,
                step_name TEXT,
                step_order INTEGER,
                assigned_to TEXT,
                is_required BOOLEAN,
                FOREIGN KEY (template_id) REFERENCES workflow_templates (template_id)
            );

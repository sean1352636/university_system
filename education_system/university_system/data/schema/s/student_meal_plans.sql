CREATE TABLE IF NOT EXISTS student_meal_plans (
                        student_id TEXT PRIMARY KEY,
                        student_name TEXT,
                        plan_type TEXT,
                        balance REAL,
                        plan_start_date DATE,
                        plan_end_date DATE,
                        is_active BOOLEAN DEFAULT 1
                    );

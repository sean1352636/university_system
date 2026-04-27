CREATE TABLE IF NOT EXISTS student_quick_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    link_title TEXT NOT NULL,
                    link_url TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );

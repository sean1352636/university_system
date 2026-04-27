CREATE TABLE IF NOT EXISTS staff_noticeboard (
                notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                category TEXT DEFAULT 'general',
                posted_by TEXT NOT NULL,
                posted_by_name TEXT,
                contact_info TEXT,
                post_date TEXT DEFAULT CURRENT_TIMESTAMP,
                expiry_date TEXT,
                is_active INTEGER DEFAULT 1,
                view_count INTEGER DEFAULT 0
            );

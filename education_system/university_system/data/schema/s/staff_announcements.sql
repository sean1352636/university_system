CREATE TABLE IF NOT EXISTS staff_announcements (
                announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                target_audience TEXT DEFAULT 'all',
                target_departments TEXT,
                target_roles TEXT,
                posted_by TEXT NOT NULL,
                posted_by_name TEXT,
                post_date TEXT DEFAULT CURRENT_TIMESTAMP,
                expiry_date TEXT,
                is_pinned INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                view_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

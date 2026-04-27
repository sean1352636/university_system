CREATE TABLE IF NOT EXISTS dependency_vulnerabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_name TEXT NOT NULL,
                installed_version TEXT NOT NULL,
                vulnerability_id TEXT,  -- CVE ID
                severity TEXT NOT NULL,
                description TEXT,
                fixed_version TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                patched BOOLEAN DEFAULT 0,
                patched_at TIMESTAMP
            );

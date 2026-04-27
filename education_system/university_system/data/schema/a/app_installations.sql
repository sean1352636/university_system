CREATE TABLE IF NOT EXISTS app_installations (
                installation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_id INTEGER,
                app_version TEXT,
                installation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP, installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, uninstalled_at TIMESTAMP, "install_id" INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
            );

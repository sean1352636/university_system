from education_system.systems.university.infrastructure.database.db import get_connection


class SettingsMixin:
    def update_system_setting(self, key, value):
        """Update a system setting"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE scheduling_system_settings
        SET value = ?, last_modified = CURRENT_TIMESTAMP
        WHERE key = ?
        ''', (value, key))

        if cursor.rowcount == 0:
            # Setting doesn't exist, create it
            cursor.execute('''
            INSERT INTO scheduling_system_settings (key, value, description)
            VALUES (?, ?, ?)
            ''', (key, value, f"Custom setting: {key}"))

        conn.commit()
        conn.close()

        print(f"System setting '{key}' updated to '{value}'")

    def get_system_setting(self, key, default=None):
        """Get a system setting value"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('SELECT value FROM scheduling_system_settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else default

    def list_system_settings(self):
        """List all system settings"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT key, value, description, last_modified
        FROM scheduling_system_settings
        ORDER BY key
        ''')

        settings = cursor.fetchall()
        conn.close()

        print("\nSystem Settings:")
        print("=" * 80)
        print(f"{'Key':<25} {'Value':<20} {'Description':<30}")
        print("-" * 80)

        for setting in settings:
            key, value, desc, modified = setting
            print(f"{key:<25} {value:<20} {desc:<30}")

        print("=" * 80)

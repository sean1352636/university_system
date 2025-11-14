#!/usr/bin/env python3
"""
Script to update foreign key references after user ID reorganization.
Maps old user IDs to new user IDs and updates all referencing tables.
"""

import sqlite3
import sys

# ID mapping: old_id -> new_id
ID_MAPPING = {
    1: 3,      # Default student S12345: 1 -> 3
    193: 2,    # Staff: 193 -> 2
    196: 1,    # Admin: 196 -> 1
}

# Add mappings for all shifted IDs (2-192 become 4-194, 194-195 become 196-197)
for old_id in range(2, 193):
    if old_id not in ID_MAPPING:
        ID_MAPPING[old_id] = old_id + 2

for old_id in range(194, 196):
    ID_MAPPING[old_id] = old_id + 2


def get_tables_with_user_fk(conn):
    """Get all tables that have foreign keys to users table."""
    cursor = conn.cursor()

    # Get all table schemas
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
    tables = cursor.fetchall()

    user_fk_tables = []
    for table_name, sql in tables:
        if sql and 'FOREIGN KEY' in sql.upper() and 'users' in sql:
            # Parse to find column names that reference users
            user_fk_tables.append(table_name)

    return user_fk_tables


def get_user_fk_columns(conn, table_name):
    """Get column names that are foreign keys to users table."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    result = cursor.fetchone()

    if not result:
        return []

    sql = result[0]
    columns = []

    # Look for patterns like "FOREIGN KEY (user_id) REFERENCES users"
    import re
    pattern = r'FOREIGN KEY \((\w+)\)\s+REFERENCES\s+users'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    columns.extend(matches)

    return columns


def update_table_references(conn, table_name, columns):
    """Update foreign key references in a table."""
    cursor = conn.cursor()

    for column in columns:
        try:
            # Check if table has any rows
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]

            if count == 0:
                print(f"  {table_name}.{column}: No rows to update")
                continue

            # Update each mapped ID
            updates = 0
            for old_id, new_id in ID_MAPPING.items():
                cursor.execute(f"""
                    UPDATE {table_name}
                    SET {column} = ?
                    WHERE {column} = ?
                """, (new_id, old_id))

                if cursor.rowcount > 0:
                    updates += cursor.rowcount

            if updates > 0:
                print(f"  {table_name}.{column}: Updated {updates} rows")
            else:
                print(f"  {table_name}.{column}: No matching rows to update")

        except Exception as e:
            print(f"  ERROR updating {table_name}.{column}: {e}")


def main():
    db_path = "university_system/data/db_files/student_records.db"

    print("Connecting to database...")
    conn = sqlite3.connect(db_path)

    try:
        print("\nFinding tables with foreign keys to users...")
        fk_tables = get_tables_with_user_fk(conn)
        print(f"Found {len(fk_tables)} tables with user foreign keys")

        print("\nUpdating foreign key references...")
        for table_name in fk_tables:
            columns = get_user_fk_columns(conn, table_name)
            if columns:
                update_table_references(conn, table_name, columns)

        conn.commit()
        print("\nAll updates completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

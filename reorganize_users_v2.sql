-- Reorganize users table to have default admin at ID 1, staff at ID 2, student at ID 3
-- All other users will be shifted accordingly

BEGIN TRANSACTION;

-- Step 1: Create new users table with reorganized IDs
CREATE TABLE users_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL,
    student_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login TEXT,
    FOREIGN KEY (student_id) REFERENCES students (student_id)
);

-- Step 2: Insert admin as ID 1 (previously ID 196)
INSERT INTO users_new (id, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login)
SELECT 1, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login
FROM users WHERE id = 196;

-- Step 3: Insert staff as ID 2 (previously ID 193)
INSERT INTO users_new (id, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login)
SELECT 2, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login
FROM users WHERE id = 193;

-- Step 4: Insert default student as ID 3 (previously ID 1 - S12345)
INSERT INTO users_new (id, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login)
SELECT 3, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login
FROM users WHERE id = 1;

-- Step 5: Insert all other users with shifted IDs
-- Users with ID 2-192 become ID 4-194
INSERT INTO users_new (id, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login)
SELECT
    id + 2 as id,  -- Shift by 2 to make room for admin and staff
    username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login
FROM users
WHERE id >= 2 AND id <= 192 AND id NOT IN (193);

-- Users with ID 194-195 become ID 196-197
INSERT INTO users_new (id, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login)
SELECT
    id + 2 as id,  -- Shift by 2
    username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login
FROM users
WHERE id >= 194 AND id <= 195;

-- Step 6: Drop old table and rename new one
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

COMMIT;

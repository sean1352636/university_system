-- Reorganize users table to have default admin at ID 1, staff at ID 2, student at ID 3
BEGIN TRANSACTION;

-- Step 1: Create a temporary table to hold the data we want to reorganize
CREATE TEMPORARY TABLE temp_default_users AS
SELECT * FROM users WHERE id IN (1, 193, 196);

-- Step 2: Store the data for the three default users
-- ID 196: admin (system_teessideuniversity)
-- ID 193: staff (1952392)
-- ID 1: student (S12345)

-- Step 3: Delete the old records
DELETE FROM users WHERE id IN (1, 193, 196);

-- Step 4: Insert admin as ID 1 (previously ID 196)
INSERT INTO users (id, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login)
SELECT 1, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login
FROM temp_default_users WHERE id = 196;

-- Step 5: Insert staff as ID 2 (previously ID 193)
INSERT INTO users (id, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login)
SELECT 2, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login
FROM temp_default_users WHERE id = 193;

-- Step 6: Insert student as ID 3 (previously ID 1)
INSERT INTO users (id, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login)
SELECT 3, username, first_name, last_name, email, role, student_id, created_at, updated_at, last_login
FROM temp_default_users WHERE id = 1;

-- Step 7: Drop the temporary table
DROP TABLE temp_default_users;

COMMIT;

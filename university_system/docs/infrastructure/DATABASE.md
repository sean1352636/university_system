# Database Schema Documentation

## Overview

The University Management System uses a relational database to store all application data. By default, the system uses SQLite for ease of deployment, but supports PostgreSQL and MySQL for production environments.

## Table of Contents

- [Database Configuration](#database-configuration)
- [Connection Management](#connection-management)
- [Schema Overview](#schema-overview)
- [Core Tables](#core-tables)
- [Academic Tables](#academic-tables)
- [Financial Tables](#financial-tables)
- [Student Affairs Tables](#student-affairs-tables)
- [Health Services Tables](#health-services-tables)
- [Relationships](#relationships)
- [Indexes](#indexes)
- [Constraints](#constraints)
- [Migrations](#migrations)
- [Backup and Recovery](#backup-and-recovery)

## Database Configuration

### Default Configuration (SQLite)

```python
# infrastructure/database/db.py
DEFAULT_DB_PATH = 'data/db_files/university_system.db'
```

### PostgreSQL Configuration

```python
# .env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=university_system
DB_USER=db_user
DB_PASSWORD=secure_password
```

### MySQL Configuration

```python
# .env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=university_system
DB_USER=db_user
DB_PASSWORD=secure_password
```

## Connection Management

### DatabaseManager Class

The `DatabaseManager` class provides centralized database access:

```python
from infrastructure.database.db import DatabaseManager

# Create instance
db_manager = DatabaseManager(db_path='data/db_files/university_system.db')

# Get connection
conn = db_manager.get_connection()

# Execute query
cursor = conn.cursor()
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
result = cursor.fetchone()

# Close connection
db_manager.close()
```

### Transaction Management

Use transactions for data modifications:

```python
from infrastructure.database.db import get_db_transaction

# Automatic transaction management
with get_db_transaction() as (conn, cursor):
    cursor.execute("INSERT INTO courses (...) VALUES (?)", data)
    cursor.execute("INSERT INTO enrollments (...) VALUES (?)", enrollment_data)
    # Automatically commits on success, rolls back on exception
```

### Read-Only Connections

For read operations, use read-only connections:

```python
db_manager = DatabaseManager(db_path='path/to/db', read_only=True)
```

## Schema Overview

### Entity Relationship Diagram

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│    Users    │────────>│  Enrollments │<────────│   Courses   │
└─────────────┘         └──────────────┘         └─────────────┘
      │                        │                         │
      │                        │                         │
      v                        v                         v
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Roles     │         │    Grades    │         │ Assignments │
└─────────────┘         └──────────────┘         └─────────────┘
      │                        │                         │
      │                        │                         │
      v                        v                         v
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│Permissions  │         │ Attendance   │         │Submissions  │
└─────────────┘         └──────────────┘         └─────────────┘
```

## Core Tables

### users

Stores all system users (students, faculty, staff, administrators).

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'faculty', 'student', 'staff')),
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMP
);

-- Indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_active ON users(active);
```

**Columns:**
- `id`: Unique user identifier
- `username`: Login username (unique)
- `password_hash`: PBKDF2-SHA256 hash of password
- `salt`: Unique salt for password hashing
- `email`: User's email address (unique)
- `first_name`, `last_name`: User's name
- `role`: User role (admin/faculty/student/staff)
- `active`: Account status (1=active, 0=inactive)
- `created_at`: Account creation timestamp
- `updated_at`: Last update timestamp
- `last_login`: Last successful login
- `failed_login_attempts`: Count of failed login attempts
- `account_locked_until`: Lockout expiration time

### roles

Defines system roles and their permissions.

```sql
CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    permissions TEXT,  -- JSON array of permission strings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### sessions

Tracks active user sessions.

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
```

### audit_log

Records security-sensitive operations.

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    event_type TEXT NOT NULL,
    event_description TEXT,
    ip_address TEXT,
    success BOOLEAN,
    metadata TEXT,  -- JSON object with additional data
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_event_type ON audit_log(event_type);
```

## Academic Tables

### courses

Stores course information.

```sql
CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    credits INTEGER NOT NULL,
    department TEXT,
    instructor_id INTEGER,
    semester TEXT,
    year INTEGER,
    capacity INTEGER,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instructor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_courses_code ON courses(code);
CREATE INDEX idx_courses_instructor ON courses(instructor_id);
CREATE INDEX idx_courses_semester ON courses(semester, year);
```

### enrollments

Links students to courses.

```sql
CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'enrolled' CHECK(status IN ('enrolled', 'dropped', 'completed', 'failed')),
    final_grade REAL,
    letter_grade TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE(student_id, course_id)
);

CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
CREATE INDEX idx_enrollments_status ON enrollments(status);
```

### assignments

Stores course assignments.

```sql
CREATE TABLE assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    due_date TIMESTAMP NOT NULL,
    points_possible INTEGER NOT NULL,
    assignment_type TEXT CHECK(assignment_type IN ('homework', 'exam', 'project', 'quiz', 'lab')),
    group_assignment BOOLEAN DEFAULT 0,
    allow_late_submissions BOOLEAN DEFAULT 0,
    late_penalty_percent REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

CREATE INDEX idx_assignments_course ON assignments(course_id);
CREATE INDEX idx_assignments_due_date ON assignments(due_date);
```

### submissions

Tracks assignment submissions.

```sql
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT,
    content TEXT,
    status TEXT DEFAULT 'submitted' CHECK(status IN ('submitted', 'graded', 'returned', 'late')),
    score REAL,
    feedback TEXT,
    graded_by INTEGER,
    graded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (graded_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(assignment_id, student_id)
);

CREATE INDEX idx_submissions_assignment ON submissions(assignment_id);
CREATE INDEX idx_submissions_student ON submissions(student_id);
CREATE INDEX idx_submissions_status ON submissions(status);
```

### grades

Stores individual grade entries.

```sql
CREATE TABLE grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL,
    assignment_id INTEGER,
    points_earned REAL NOT NULL,
    points_possible REAL NOT NULL,
    percentage REAL,
    letter_grade TEXT,
    grade_type TEXT CHECK(grade_type IN ('assignment', 'midterm', 'final', 'participation')),
    comments TEXT,
    recorded_by INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE SET NULL,
    FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_grades_enrollment ON grades(enrollment_id);
CREATE INDEX idx_grades_assignment ON grades(assignment_id);
```

### attendance

Tracks class attendance.

```sql
CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    date DATE NOT NULL,
    status TEXT CHECK(status IN ('present', 'absent', 'late', 'excused')),
    notes TEXT,
    recorded_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(course_id, student_id, date)
);

CREATE INDEX idx_attendance_course ON attendance(course_id);
CREATE INDEX idx_attendance_student ON attendance(student_id);
CREATE INDEX idx_attendance_date ON attendance(date);
```

## Financial Tables

### invoices

Student billing and invoices.

```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    invoice_number TEXT UNIQUE NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    description TEXT,
    due_date DATE NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'paid', 'overdue', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_invoices_student ON invoices(student_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_due_date ON invoices(due_date);
```

### payments

Payment records.

```sql
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT CHECK(payment_method IN ('cash', 'credit_card', 'debit_card', 'bank_transfer', 'check')),
    transaction_id TEXT UNIQUE,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    processed_by INTEGER,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (processed_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_payments_invoice ON payments(invoice_id);
CREATE INDEX idx_payments_date ON payments(payment_date);
```

### scholarships

Scholarship and financial aid.

```sql
CREATE TABLE scholarships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    type TEXT CHECK(type IN ('merit', 'need-based', 'athletic', 'departmental')),
    renewable BOOLEAN DEFAULT 0,
    criteria TEXT,
    deadline DATE,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scholarships_type ON scholarships(type);
CREATE INDEX idx_scholarships_deadline ON scholarships(deadline);
```

### scholarship_applications

Scholarship application records.

```sql
CREATE TABLE scholarship_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholarship_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'awarded')),
    amount_awarded REAL,
    decision_date TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (scholarship_id) REFERENCES scholarships(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(scholarship_id, student_id)
);

CREATE INDEX idx_scholarship_apps_student ON scholarship_applications(student_id);
CREATE INDEX idx_scholarship_apps_status ON scholarship_applications(status);
```

## Student Affairs Tables

### clubs

Student clubs and organizations.

```sql
CREATE TABLE clubs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    category TEXT,
    president_id INTEGER,
    advisor_id INTEGER,
    founded_date DATE,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (president_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (advisor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_clubs_category ON clubs(category);
CREATE INDEX idx_clubs_active ON clubs(active);
```

### club_memberships

Club membership records.

```sql
CREATE TABLE club_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role TEXT DEFAULT 'member' CHECK(role IN ('member', 'officer', 'president', 'vice_president', 'treasurer', 'secretary')),
    active BOOLEAN DEFAULT 1,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(club_id, student_id)
);

CREATE INDEX idx_club_members_club ON club_memberships(club_id);
CREATE INDEX idx_club_members_student ON club_memberships(student_id);
```

### events

Campus events.

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    event_date TIMESTAMP NOT NULL,
    location TEXT,
    capacity INTEGER,
    organizer_id INTEGER,
    club_id INTEGER,
    category TEXT,
    registration_required BOOLEAN DEFAULT 0,
    registration_deadline TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE SET NULL
);

CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_organizer ON events(organizer_id);
CREATE INDEX idx_events_club ON events(club_id);
```

### event_registrations

Event registration records.

```sql
CREATE TABLE event_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    attended BOOLEAN DEFAULT 0,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(event_id, user_id)
);

CREATE INDEX idx_event_regs_event ON event_registrations(event_id);
CREATE INDEX idx_event_regs_user ON event_registrations(user_id);
```

## Health Services Tables

### medical_records

Student medical records (HIPAA-compliant).

```sql
CREATE TABLE medical_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    record_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    record_type TEXT CHECK(record_type IN ('visit', 'vaccination', 'allergy', 'prescription', 'physical')),
    diagnosis TEXT,
    treatment TEXT,
    notes TEXT,
    provider_id INTEGER,
    confidential BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_medical_records_student ON medical_records(student_id);
CREATE INDEX idx_medical_records_date ON medical_records(record_date);
```

### appointments

Health service appointments.

```sql
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    provider_id INTEGER,
    appointment_date TIMESTAMP NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    reason TEXT,
    status TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_appointments_student ON appointments(student_id);
CREATE INDEX idx_appointments_provider ON appointments(provider_id);
CREATE INDEX idx_appointments_date ON appointments(appointment_date);
```

## Relationships

### One-to-Many Relationships

1. **Users → Enrollments**: One user (student) can have many enrollments
2. **Courses → Enrollments**: One course can have many enrollments
3. **Courses → Assignments**: One course can have many assignments
4. **Users → Submissions**: One user can have many submissions
5. **Assignments → Submissions**: One assignment can have many submissions
6. **Users → Invoices**: One student can have many invoices
7. **Clubs → Memberships**: One club can have many members

### Many-to-Many Relationships

1. **Students ↔ Courses** (through enrollments)
2. **Students ↔ Clubs** (through club_memberships)
3. **Users ↔ Events** (through event_registrations)

### Foreign Key Constraints

All foreign keys use appropriate referential actions:
- `ON DELETE CASCADE`: Delete dependent records when parent is deleted
- `ON DELETE SET NULL`: Set to NULL when parent is deleted (for optional relationships)

## Indexes

Indexes are created on:
- Primary keys (automatic)
- Foreign keys
- Frequently queried columns
- Columns used in WHERE clauses
- Columns used in JOIN conditions
- Columns used in ORDER BY clauses

## Constraints

### Check Constraints

Validate data at the database level:
```sql
CHECK(role IN ('admin', 'faculty', 'student', 'staff'))
CHECK(status IN ('enrolled', 'dropped', 'completed', 'failed'))
```

### Unique Constraints

Ensure data uniqueness:
```sql
UNIQUE(username)
UNIQUE(email)
UNIQUE(course_code)
UNIQUE(student_id, course_id)  -- Composite unique
```

### Not Null Constraints

Enforce required fields:
```sql
username TEXT NOT NULL
email TEXT NOT NULL
```

## Migrations

### Migration Strategy

1. **Version Control**: All schema changes are versioned
2. **Forward Only**: Migrations always move forward
3. **Data Preservation**: Never drop data without backup
4. **Testing**: Test migrations on copy before production

### Example Migration

```python
# infrastructure/database/migrations/001_add_account_lockout.py

def upgrade(conn):
    """Add account lockout fields to users table."""
    cursor = conn.cursor()

    # Add new columns
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN failed_login_attempts INTEGER DEFAULT 0
    """)

    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN account_locked_until TIMESTAMP
    """)

    conn.commit()

def downgrade(conn):
    """Remove account lockout fields (SQLite doesn't support column drop)."""
    # For SQLite, would need to recreate table
    # For PostgreSQL/MySQL:
    # cursor.execute("ALTER TABLE users DROP COLUMN failed_login_attempts")
    # cursor.execute("ALTER TABLE users DROP COLUMN account_locked_until")
    pass
```

### Running Migrations

```bash
# Run all pending migrations
python -m infrastructure.database.migrate

# Check migration status
python -m infrastructure.database.migrate --status

# Rollback last migration (if supported)
python -m infrastructure.database.migrate --rollback
```

## Backup and Recovery

### Automated Backups

```bash
# Daily backup (cron job)
0 2 * * * /path/to/backup_database.sh

# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/path/to/backups/database"
DB_PATH="/path/to/data/db_files/university_system.db"

# Create backup
sqlite3 $DB_PATH ".backup $BACKUP_DIR/backup_$DATE.db"

# Compress backup
gzip $BACKUP_DIR/backup_$DATE.db

# Remove backups older than 30 days
find $BACKUP_DIR -name "backup_*.db.gz" -mtime +30 -delete
```

### Manual Backup

```python
from infrastructure.database.db import DatabaseManager

def backup_database(source_path: str, backup_path: str):
    """Create a database backup."""
    source_db = DatabaseManager(source_path)
    source_conn = source_db.get_connection()

    # Create backup connection
    backup_conn = sqlite3.connect(backup_path)

    # Perform backup
    source_conn.backup(backup_conn)

    # Close connections
    backup_conn.close()
    source_db.close()
```

### Recovery

```bash
# Restore from backup
cp backups/database/backup_YYYYMMDD.db data/db_files/university_system.db

# Or using Python
python -m infrastructure.database.restore --file backups/database/backup_YYYYMMDD.db
```

### Disaster Recovery

1. **Regular Backups**: Automated daily backups
2. **Off-site Storage**: Store backups in separate location
3. **Test Restores**: Regularly test backup restoration
4. **Point-in-Time Recovery**: Use WAL mode for continuous backup

```python
# Enable WAL mode for continuous backup
conn.execute("PRAGMA journal_mode = WAL")
```

## Best Practices

1. **Use Transactions**: Always use transactions for data modifications
2. **Parameterized Queries**: Never concatenate user input into SQL
3. **Connection Pooling**: Reuse connections when possible
4. **Proper Indexing**: Create indexes for frequently queried columns
5. **Regular Backups**: Automate and test backups
6. **Monitor Performance**: Track slow queries and optimize
7. **Data Validation**: Validate data before database operations
8. **Error Handling**: Always handle database exceptions properly

## Troubleshooting

### Common Issues

**Database Locked**
```python
# Increase timeout
conn = sqlite3.connect(db_path, timeout=30.0)

# Enable WAL mode
conn.execute("PRAGMA journal_mode = WAL")
```

**Foreign Key Violations**
```python
# Enable foreign key checking
conn.execute("PRAGMA foreign_keys = ON")

# Check for violations
cursor.execute("PRAGMA foreign_key_check")
```

**Performance Issues**
```sql
-- Analyze query performance
EXPLAIN QUERY PLAN SELECT ...;

-- Update statistics
ANALYZE;

-- Vacuum database
VACUUM;
```

## References

- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [Database Normalization](https://en.wikipedia.org/wiki/Database_normalization)
- [ACID Properties](https://en.wikipedia.org/wiki/ACID)

---

For questions or issues related to the database, contact the development team or open an issue on GitHub.

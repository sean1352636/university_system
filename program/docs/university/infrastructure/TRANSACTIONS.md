# Transaction Usage Guide

## Overview

Database transactions are critical for maintaining data integrity in the University Management System. This guide explains how to properly use transactions to ensure ACID compliance (Atomicity, Consistency, Isolation, Durability).

## Table of Contents

- [What Are Transactions?](#what-are-transactions)
- [When to Use Transactions](#when-to-use-transactions)
- [Transaction Helpers](#transaction-helpers)
- [Usage Examples](#usage-examples)
- [Transaction Isolation](#transaction-isolation)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)
- [Performance Considerations](#performance-considerations)
- [Troubleshooting](#troubleshooting)

## What Are Transactions?

A database transaction is a unit of work that is either completed entirely or not at all. Transactions ensure that your database remains in a consistent state even when errors occur.

### ACID Properties

- **Atomicity**: All operations in a transaction succeed or all fail
- **Consistency**: Transactions bring the database from one valid state to another
- **Isolation**: Concurrent transactions don't interfere with each other
- **Durability**: Committed changes are permanent

### Example Scenario

Consider enrolling a student in a course:

```
1. Insert enrollment record
2. Update course enrollment count
3. Update student's enrolled courses count
4. Create audit log entry
```

Without a transaction, if step 3 fails, steps 1 and 2 would still be committed, leaving the database in an inconsistent state. With a transaction, if any step fails, ALL changes are rolled back.

## When to Use Transactions

### Always Use Transactions For:

1. **Multiple Related Writes**: When you need to write to multiple tables
2. **Updates Based on Reads**: When you read data and make decisions based on it
3. **Consistency Requirements**: When data must remain consistent across tables
4. **Business Logic Constraints**: When enforcing business rules across operations

### Examples Requiring Transactions:

```python
# Student enrollment (multiple tables)
- Insert into enrollments
- Update course capacity
- Update student course count

# Payment processing (multiple tables)
- Insert payment record
- Update invoice status
- Update student account balance

# Grade submission (multiple tables)
- Insert grade record
- Update enrollment final grade
- Recalculate GPA
```

### Read-Only Operations

Read-only operations generally don't need transactions, but can use them for consistency:

```python
# These don't need transactions
get_user_by_id(user_id)
list_all_courses()

# But these might benefit from transaction isolation
generate_report_with_calculations()
check_and_reserve_slot()
```

## Transaction Helpers

The system provides convenient transaction helpers in `infrastructure/database/db.py`.

### get_db_transaction()

Context manager for automatic transaction handling:

```python
from infrastructure.database.db import get_db_transaction

def enroll_student(student_id: int, course_id: int):
    """Enroll student in course using transaction."""
    with get_db_transaction() as (conn, cursor):
        # All operations within this block are in a transaction
        cursor.execute(
            "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
            (student_id, course_id)
        )

        cursor.execute(
            "UPDATE courses SET enrolled_count = enrolled_count + 1 WHERE id = ?",
            (course_id,)
        )

        # Transaction automatically commits on success
        # Automatically rolls back on exception
```

**Features:**
- Automatic commit on success
- Automatic rollback on exception
- Proper connection cleanup
- Returns both connection and cursor

### execute_in_transaction()

Helper function for single-operation transactions:

```python
from infrastructure.database.db import execute_in_transaction

def update_student_email(student_id: int, new_email: str):
    """Update student email in a transaction."""
    result = execute_in_transaction(
        "UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_email, student_id)
    )
    return result
```

**Features:**
- Simple one-liner for single operations
- Returns cursor for accessing results
- Automatic commit/rollback
- Proper error handling

### Manual Transaction Control

For complex scenarios requiring fine-grained control:

```python
from infrastructure.database.db import DatabaseManager

def complex_operation():
    """Example of manual transaction control."""
    db = DatabaseManager()
    conn = db.get_connection()

    try:
        # Start transaction (implicit in SQLite)
        cursor = conn.cursor()

        # Perform operations
        cursor.execute("INSERT INTO ...")
        cursor.execute("UPDATE ...")

        # Explicitly commit
        conn.commit()

    except Exception as e:
        # Rollback on error
        conn.rollback()
        raise

    finally:
        # Clean up
        db.close()
```

## Usage Examples

### Example 1: Student Enrollment

```python
from infrastructure.database.db import get_db_transaction
from infrastructure.exceptions import EnrollmentException, DatabaseException

def enroll_student_in_course(student_id: int, course_id: int) -> dict:
    """
    Enroll a student in a course.

    This operation:
    1. Checks course capacity
    2. Creates enrollment record
    3. Updates course enrollment count
    4. Logs the enrollment

    Args:
        student_id: Student ID
        course_id: Course ID

    Returns:
        Enrollment record

    Raises:
        EnrollmentException: If course is full
        DatabaseException: If database operation fails
    """
    try:
        with get_db_transaction() as (conn, cursor):
            # Check current enrollment
            cursor.execute("""
                SELECT capacity, enrolled_count
                FROM courses
                WHERE id = ?
            """, (course_id,))

            result = cursor.fetchone()
            if not result:
                raise ResourceNotFoundException('Course', course_id)

            capacity, enrolled = result
            if enrolled >= capacity:
                raise EnrollmentException(
                    f"Course {course_id} is full",
                    details={'capacity': capacity, 'enrolled': enrolled}
                )

            # Create enrollment
            cursor.execute("""
                INSERT INTO enrollments (student_id, course_id, enrollment_date, status)
                VALUES (?, ?, CURRENT_TIMESTAMP, 'enrolled')
            """, (student_id, course_id))

            enrollment_id = cursor.lastrowid

            # Update course enrollment count
            cursor.execute("""
                UPDATE courses
                SET enrolled_count = enrolled_count + 1
                WHERE id = ?
            """, (course_id,))

            # Log the enrollment
            cursor.execute("""
                INSERT INTO audit_log (event_type, event_description, metadata)
                VALUES ('enrollment.created', 'Student enrolled in course', ?)
            """, (json.dumps({
                'student_id': student_id,
                'course_id': course_id,
                'enrollment_id': enrollment_id
            }),))

            # Return enrollment details
            cursor.execute("""
                SELECT * FROM enrollments WHERE id = ?
            """, (enrollment_id,))

            return cursor.fetchone()

            # Transaction commits automatically here

    except EnrollmentException:
        # Re-raise business logic exceptions
        raise

    except Exception as e:
        # Log and wrap database errors
        logger.error(f"Database error during enrollment: {e}", exc_info=True)
        raise DatabaseException("Failed to enroll student")
```

### Example 2: Payment Processing

```python
def process_payment(invoice_id: int, amount: float, payment_method: str) -> dict:
    """
    Process a payment for an invoice.

    This operation:
    1. Validates invoice exists and amount matches
    2. Creates payment record
    3. Updates invoice status
    4. Updates student account balance
    5. Logs the transaction

    Args:
        invoice_id: Invoice to pay
        amount: Payment amount
        payment_method: Payment method

    Returns:
        Payment record

    Raises:
        ValidationException: If validation fails
        DatabaseException: If database operation fails
    """
    with get_db_transaction() as (conn, cursor):
        # Get invoice details
        cursor.execute("""
            SELECT id, student_id, amount, status
            FROM invoices
            WHERE id = ?
        """, (invoice_id,))

        invoice = cursor.fetchone()
        if not invoice:
            raise ResourceNotFoundException('Invoice', invoice_id)

        inv_id, student_id, invoice_amount, status = invoice

        # Validate amount
        if amount != invoice_amount:
            raise ValidationException(
                f"Payment amount {amount} doesn't match invoice amount {invoice_amount}"
            )

        # Validate invoice status
        if status == 'paid':
            raise BusinessLogicException("Invoice already paid")

        # Create payment record
        transaction_id = generate_transaction_id()
        cursor.execute("""
            INSERT INTO payments (
                invoice_id, amount, payment_method,
                transaction_id, payment_date
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (invoice_id, amount, payment_method, transaction_id))

        payment_id = cursor.lastrowid

        # Update invoice status
        cursor.execute("""
            UPDATE invoices
            SET status = 'paid', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (invoice_id,))

        # Update student balance
        cursor.execute("""
            UPDATE student_accounts
            SET balance = balance - ?
            WHERE student_id = ?
        """, (amount, student_id))

        # Log the payment
        cursor.execute("""
            INSERT INTO audit_log (
                user_id, event_type, event_description, metadata
            )
            VALUES (?, 'payment.processed', 'Payment processed', ?)
        """, (
            student_id,
            json.dumps({
                'payment_id': payment_id,
                'invoice_id': invoice_id,
                'amount': amount,
                'transaction_id': transaction_id
            })
        ))

        return {
            'payment_id': payment_id,
            'transaction_id': transaction_id,
            'amount': amount,
            'status': 'completed'
        }
```

### Example 3: Grade Submission

```python
def submit_final_grades(course_id: int, grades: List[dict], submitted_by: int):
    """
    Submit final grades for a course.

    This operation:
    1. Validates all students are enrolled
    2. Records individual grades
    3. Updates enrollment records
    4. Recalculates GPAs
    5. Logs the submission

    Args:
        course_id: Course ID
        grades: List of {student_id, grade, comments}
        submitted_by: Instructor ID

    Raises:
        ValidationException: If validation fails
        DatabaseException: If database operation fails
    """
    with get_db_transaction() as (conn, cursor):
        # Validate course exists
        cursor.execute("SELECT id FROM courses WHERE id = ?", (course_id,))
        if not cursor.fetchone():
            raise ResourceNotFoundException('Course', course_id)

        submitted_grades = []

        for grade_data in grades:
            student_id = grade_data['student_id']
            grade = grade_data['grade']
            comments = grade_data.get('comments', '')

            # Validate enrollment
            cursor.execute("""
                SELECT id FROM enrollments
                WHERE course_id = ? AND student_id = ? AND status = 'enrolled'
            """, (course_id, student_id))

            enrollment = cursor.fetchone()
            if not enrollment:
                raise EnrollmentException(
                    f"Student {student_id} not enrolled in course {course_id}"
                )

            enrollment_id = enrollment[0]

            # Insert grade record
            cursor.execute("""
                INSERT INTO grades (
                    enrollment_id, points_earned, points_possible,
                    percentage, letter_grade, grade_type, comments,
                    recorded_by, recorded_at
                )
                VALUES (?, ?, 100, ?, ?, 'final', ?, ?, CURRENT_TIMESTAMP)
            """, (
                enrollment_id,
                grade,
                grade,
                calculate_letter_grade(grade),
                comments,
                submitted_by
            ))

            # Update enrollment final grade
            cursor.execute("""
                UPDATE enrollments
                SET final_grade = ?,
                    letter_grade = ?,
                    status = 'completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (grade, calculate_letter_grade(grade), enrollment_id))

            submitted_grades.append({
                'student_id': student_id,
                'grade': grade,
                'letter_grade': calculate_letter_grade(grade)
            })

        # Recalculate GPAs for all students
        for grade_data in submitted_grades:
            recalculate_gpa(cursor, grade_data['student_id'])

        # Log the submission
        cursor.execute("""
            INSERT INTO audit_log (
                user_id, event_type, event_description, metadata
            )
            VALUES (?, 'grades.submitted', 'Final grades submitted', ?)
        """, (
            submitted_by,
            json.dumps({
                'course_id': course_id,
                'grades_count': len(submitted_grades)
            })
        ))

        return submitted_grades
```

## Transaction Isolation

### Isolation Levels

SQLite uses the following isolation:

- **Default**: Serializable (highest isolation)
- **WAL Mode**: Allows concurrent reads during writes

```python
# Enable WAL mode for better concurrency
conn.execute("PRAGMA journal_mode = WAL")
```

### Read Consistency

Within a transaction, reads see a consistent snapshot:

```python
with get_db_transaction() as (conn, cursor):
    # First read
    cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
    balance1 = cursor.fetchone()[0]

    # Even if another transaction updates the balance,
    # this read will see the same value
    cursor.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
    balance2 = cursor.fetchone()[0]

    # balance1 == balance2 (within same transaction)
```

## Error Handling

### Automatic Rollback

The transaction context manager automatically rolls back on exceptions:

```python
try:
    with get_db_transaction() as (conn, cursor):
        cursor.execute("INSERT INTO ...")  # Operation 1
        cursor.execute("UPDATE ...")       # Operation 2
        raise Exception("Something went wrong!")  # Trigger rollback
        cursor.execute("DELETE FROM ...")  # This never executes
        # Automatic rollback occurs here
except Exception as e:
    # Handle the error
    logger.error(f"Transaction failed: {e}")
```

### Explicit Error Handling

```python
from infrastructure.exceptions import DatabaseException, TransactionException

def safe_transaction_example():
    """Example with explicit error handling."""
    try:
        with get_db_transaction() as (conn, cursor):
            # Perform operations
            cursor.execute("INSERT INTO ...")

            # Validate result
            if cursor.rowcount == 0:
                raise TransactionException("Insert failed")

            cursor.execute("UPDATE ...")

            # Check for constraint violations
            if conn.execute("PRAGMA foreign_key_check").fetchone():
                raise IntegrityException("Foreign key violation detected")

    except sqlite3.IntegrityError as e:
        logger.error(f"Integrity error: {e}", exc_info=True)
        raise IntegrityException("Data integrity violation")

    except sqlite3.OperationalError as e:
        logger.error(f"Operational error: {e}", exc_info=True)
        raise DatabaseException("Database operation failed")

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise TransactionException("Transaction failed")
```

## Best Practices

### 1. Keep Transactions Short

**DO:**
```python
with get_db_transaction() as (conn, cursor):
    # Quick database operations only
    cursor.execute("INSERT ...")
    cursor.execute("UPDATE ...")
```

**DON'T:**
```python
with get_db_transaction() as (conn, cursor):
    cursor.execute("INSERT ...")

    # Long-running operations
    send_email()  # Network I/O
    process_image()  # CPU intensive
    time.sleep(10)  # Delays

    cursor.execute("UPDATE ...")
```

### 2. Acquire Locks in Consistent Order

Avoid deadlocks by always acquiring locks in the same order:

**DO:**
```python
# Always lock accounts in ascending ID order
account_ids = sorted([account1_id, account2_id])

with get_db_transaction() as (conn, cursor):
    for account_id in account_ids:
        cursor.execute("SELECT * FROM accounts WHERE id = ? FOR UPDATE", (account_id,))
    # Perform operations
```

### 3. Don't Nest Transactions

SQLite doesn't support nested transactions:

**DON'T:**
```python
with get_db_transaction() as (conn1, cursor1):
    cursor1.execute("INSERT ...")

    with get_db_transaction() as (conn2, cursor2):  # This creates a NEW connection!
        cursor2.execute("UPDATE ...")  # Won't see cursor1's changes
```

### 4. Validate Before Write Operations

**DO:**
```python
with get_db_transaction() as (conn, cursor):
    # Validate first
    cursor.execute("SELECT status FROM courses WHERE id = ?", (course_id,))
    status = cursor.fetchone()[0]

    if status != 'active':
        raise ValidationException("Course is not active")

    # Then write
    cursor.execute("INSERT INTO enrollments ...")
```

### 5. Use Savepoints for Complex Logic

For complex operations needing partial rollback:

```python
with get_db_transaction() as (conn, cursor):
    # Main work
    cursor.execute("INSERT INTO courses ...")

    # Create savepoint
    conn.execute("SAVEPOINT sp1")

    try:
        # Risky operation
        cursor.execute("INSERT INTO experimental_data ...")
    except Exception:
        # Rollback to savepoint (keeps main work)
        conn.execute("ROLLBACK TO SAVEPOINT sp1")

    # Continue with main work
    cursor.execute("UPDATE courses ...")
```

## Common Patterns

### Pattern 1: Check-Then-Act

```python
def check_and_enroll(student_id: int, course_id: int):
    """Check prerequisites then enroll."""
    with get_db_transaction() as (conn, cursor):
        # Check prerequisites
        cursor.execute("""
            SELECT prerequisite_id FROM course_prerequisites
            WHERE course_id = ?
        """, (course_id,))

        prerequisites = [row[0] for row in cursor.fetchall()]

        for prereq_id in prerequisites:
            cursor.execute("""
                SELECT 1 FROM enrollments
                WHERE student_id = ? AND course_id = ? AND letter_grade >= 'C'
            """, (student_id, prereq_id))

            if not cursor.fetchone():
                raise EnrollmentException(f"Prerequisite {prereq_id} not met")

        # All checks passed, now enroll
        cursor.execute("""
            INSERT INTO enrollments (student_id, course_id)
            VALUES (?, ?)
        """, (student_id, course_id))
```

### Pattern 2: Bulk Operations

```python
def bulk_grade_update(grades: List[dict]):
    """Update multiple grades in one transaction."""
    with get_db_transaction() as (conn, cursor):
        for grade in grades:
            cursor.execute("""
                UPDATE enrollments
                SET final_grade = ?, letter_grade = ?
                WHERE student_id = ? AND course_id = ?
            """, (
                grade['score'],
                grade['letter'],
                grade['student_id'],
                grade['course_id']
            ))

        # All or nothing - if any update fails, all rollback
```

### Pattern 3: Conditional Updates

```python
def conditional_enrollment(student_id: int, course_id: int, max_courses: int = 5):
    """Enroll only if student isn't overloaded."""
    with get_db_transaction() as (conn, cursor):
        # Count current enrollments
        cursor.execute("""
            SELECT COUNT(*) FROM enrollments
            WHERE student_id = ? AND status = 'enrolled'
        """, (student_id,))

        current_count = cursor.fetchone()[0]

        if current_count >= max_courses:
            raise EnrollmentException(
                f"Student is enrolled in {current_count} courses (max: {max_courses})"
            )

        # Safe to enroll
        cursor.execute("""
            INSERT INTO enrollments (student_id, course_id)
            VALUES (?, ?)
        """, (student_id, course_id))
```

### Pattern 4: Audit Trail

```python
def update_with_audit(table: str, record_id: int, updates: dict, user_id: int):
    """Update record and create audit trail."""
    with get_db_transaction() as (conn, cursor):
        # Get current values
        cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,))
        old_values = dict(cursor.fetchone())

        # Update record
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [record_id]

        cursor.execute(
            f"UPDATE {table} SET {set_clause} WHERE id = ?",
            values
        )

        # Create audit trail
        cursor.execute("""
            INSERT INTO audit_log (
                user_id, event_type, event_description, metadata
            )
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            f'{table}.updated',
            f'Updated {table} record',
            json.dumps({
                'record_id': record_id,
                'old_values': old_values,
                'new_values': updates
            })
        ))
```

## Performance Considerations

### 1. Transaction Size

- **Small transactions**: Better concurrency, less lock contention
- **Large transactions**: Better atomicity, worse performance

```python
# GOOD: Small, focused transaction
with get_db_transaction() as (conn, cursor):
    cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user_id))

# BAD: Huge transaction processing thousands of records
with get_db_transaction() as (conn, cursor):
    for record in huge_list:  # Could take minutes!
        cursor.execute("INSERT ...", record)
```

### 2. Batch Operations

Use executemany for bulk operations:

```python
# GOOD: Single transaction, executemany
with get_db_transaction() as (conn, cursor):
    cursor.executemany(
        "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
        [(sid, cid) for sid, cid in enrollment_pairs]
    )

# BAD: Multiple small transactions
for student_id, course_id in enrollment_pairs:
    with get_db_transaction() as (conn, cursor):
        cursor.execute("INSERT INTO enrollments ...", (student_id, course_id))
```

### 3. WAL Mode

Enable Write-Ahead Logging for better concurrency:

```python
conn.execute("PRAGMA journal_mode = WAL")
```

Benefits:
- Readers don't block writers
- Writers don't block readers
- Better performance for concurrent access

## Troubleshooting

### Database Locked Error

**Problem:**
```
sqlite3.OperationalError: database is locked
```

**Solutions:**

1. **Increase timeout:**
```python
conn = sqlite3.connect(db_path, timeout=30.0)
```

2. **Enable WAL mode:**
```python
conn.execute("PRAGMA journal_mode = WAL")
```

3. **Close connections properly:**
```python
# Always use context managers
with get_db_transaction() as (conn, cursor):
    # Operations
    pass  # Connection automatically closed
```

### Transaction Deadlock

**Problem:** Two transactions waiting for each other

**Solution:** Acquire locks in consistent order

```python
# Always lock resources in sorted order
def transfer(from_id, to_id, amount):
    account_ids = sorted([from_id, to_id])

    with get_db_transaction() as (conn, cursor):
        # Lock in order
        for account_id in account_ids:
            cursor.execute(
                "SELECT balance FROM accounts WHERE id = ?",
                (account_id,)
            )
        # Perform transfer
```

### Foreign Key Violations

**Problem:** Foreign key constraint violation

**Solution:** Enable foreign key checking and validate

```python
with get_db_transaction() as (conn, cursor):
    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON")

    # Validate before insert
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        raise ResourceNotFoundException('User', user_id)

    # Now insert
    cursor.execute("INSERT INTO enrollments ...")
```

## Summary Checklist

- [ ] Use transactions for all write operations
- [ ] Keep transactions as short as possible
- [ ] Use `get_db_transaction()` context manager
- [ ] Handle exceptions and let transactions rollback
- [ ] Don't perform I/O or long operations in transactions
- [ ] Validate data before performing writes
- [ ] Log transaction errors appropriately
- [ ] Test transaction rollback scenarios
- [ ] Enable WAL mode for better concurrency
- [ ] Use executemany for bulk operations

---

For questions or issues related to transactions, contact the development team or consult the [Database Documentation](DATABASE.md).

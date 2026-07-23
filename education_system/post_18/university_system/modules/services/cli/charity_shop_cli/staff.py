"""
Staff management: registration, performance, shifts, tasks, volunteers.
"""

from education_system.post_18.university_system.modules.services.cli.charity_shop_cli._imports import (
    sqlite3, logger, datetime, timedelta,
    get_connection, List, Dict, Any, Optional,
    STAFF_TABLE, SALES_TABLE, SHIFTS_TABLE, TASKS_TABLE,
    ACTIVITY_LOGGER_AVAILABLE, log_activity, log_create,
)


def staff_performance_tracker(staff_id: int = None, period_days: int = 30) -> Any:
    """Monitor sales per staff member."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    if staff_id:
        cursor.execute(f"""
            SELECT st.name, st.role,
                   COUNT(sl.id) as sales_count,
                   SUM(sl.total_amount) as total_sales,
                   AVG(sl.total_amount) as avg_sale
            FROM {STAFF_TABLE} st
            LEFT JOIN {SALES_TABLE} sl ON st.id = sl.staff_id AND DATE(sl.sale_date) >= ?
            WHERE st.id = ?
            GROUP BY st.id
        """, (start_date, staff_id))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'name': row[0],
                'role': row[1],
                'sales_count': row[2] or 0,
                'total_sales': row[3] or 0,
                'average_sale': row[4] or 0
            }
        return None

    else:
        cursor.execute(f"""
            SELECT st.id, st.name, st.role,
                   COUNT(sl.id) as sales_count,
                   SUM(sl.total_amount) as total_sales
            FROM {STAFF_TABLE} st
            LEFT JOIN {SALES_TABLE} sl ON st.id = sl.staff_id AND DATE(sl.sale_date) >= ?
            WHERE st.is_active = 1
            GROUP BY st.id
            ORDER BY total_sales DESC
        """, (start_date,))

        staff = []
        for row in cursor.fetchall():
            staff.append({
                'id': row[0],
                'name': row[1],
                'role': row[2],
                'sales_count': row[3] or 0,
                'total_sales': row[4] or 0
            })
        conn.close()
        return staff


def shift_scheduling(action: str, **kwargs) -> Any:
    """Manage volunteer/staff schedules."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'add':
        staff_id = kwargs.get('staff_id')
        shift_date = kwargs.get('date')
        start_time = kwargs.get('start_time')
        end_time = kwargs.get('end_time')
        notes = kwargs.get('notes', '')

        # Calculate hours
        try:
            start = datetime.strptime(start_time, "%H:%M")
            end = datetime.strptime(end_time, "%H:%M")
            hours = (end - start).seconds / 3600
        except (ValueError, TypeError):
            hours = 0

        cursor.execute(f"""
            INSERT INTO {SHIFTS_TABLE} (staff_id, shift_date, start_time, end_time, hours_worked, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (staff_id, shift_date, start_time, end_time, hours, notes))

        conn.commit()
        conn.close()
        return True

    elif action == 'view_date':
        date = kwargs.get('date')
        cursor.execute(f"""
            SELECT sh.*, st.name as staff_name
            FROM {SHIFTS_TABLE} sh
            JOIN {STAFF_TABLE} st ON sh.staff_id = st.id
            WHERE sh.shift_date = ?
            ORDER BY sh.start_time
        """, (date,))

        shifts = []
        for row in cursor.fetchall():
            shifts.append({
                'id': row[0],
                'staff_id': row[1],
                'staff_name': row[7] if len(row) > 7 else '',
                'date': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'hours': row[5]
            })
        conn.close()
        return shifts

    elif action == 'view_staff':
        staff_id = kwargs.get('staff_id')
        cursor.execute(f"""
            SELECT * FROM {SHIFTS_TABLE}
            WHERE staff_id = ?
            ORDER BY shift_date DESC
            LIMIT 30
        """, (staff_id,))

        shifts = []
        for row in cursor.fetchall():
            shifts.append({
                'id': row[0],
                'date': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'hours': row[5]
            })
        conn.close()
        return shifts

    conn.close()
    return None


def task_assignment_system(action: str, **kwargs) -> Any:
    """Assign daily tasks to staff."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'create':
        title = kwargs.get('title')
        description = kwargs.get('description', '')
        assigned_to = kwargs.get('assigned_to')
        priority = kwargs.get('priority', 'medium')
        due_date = kwargs.get('due_date')

        cursor.execute(f"""
            INSERT INTO {TASKS_TABLE}
            (title, description, assigned_to, priority, status, due_date, created_date)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (title, description, assigned_to, priority, due_date,
              datetime.now().strftime("%Y-%m-%d")))

        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    elif action == 'update_status':
        task_id = kwargs.get('task_id')
        status = kwargs.get('status')  # pending, in_progress, completed

        completed_date = datetime.now().strftime("%Y-%m-%d") if status == 'completed' else None

        cursor.execute(f"""
            UPDATE {TASKS_TABLE}
            SET status = ?, completed_date = ?
            WHERE id = ?
        """, (status, completed_date, task_id))

        conn.commit()
        conn.close()
        return True

    elif action == 'view_staff':
        staff_id = kwargs.get('staff_id')
        cursor.execute(f"""
            SELECT * FROM {TASKS_TABLE}
            WHERE assigned_to = ? AND status != 'completed'
            ORDER BY priority, due_date
        """, (staff_id,))

        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'priority': row[4],
                'status': row[5],
                'due_date': row[6]
            })
        conn.close()
        return tasks

    elif action == 'view_all':
        status_filter = kwargs.get('status', 'pending')
        cursor.execute(f"""
            SELECT t.*, st.name as staff_name
            FROM {TASKS_TABLE} t
            LEFT JOIN {STAFF_TABLE} st ON t.assigned_to = st.id
            WHERE t.status = ?
            ORDER BY t.priority, t.due_date
        """, (status_filter,))

        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'assigned_to': row[3],
                'staff_name': row[9] if len(row) > 9 else 'Unassigned',
                'priority': row[4],
                'status': row[5],
                'due_date': row[6]
            })
        conn.close()
        return tasks

    conn.close()
    return None


def volunteer_hours_tracker(staff_id: int, period: str = 'month') -> Dict:
    """Log volunteer time."""
    conn = get_connection()
    cursor = conn.cursor()

    if period == 'week':
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == 'month':
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period == 'year':
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    else:
        start_date = '1900-01-01'

    cursor.execute(f"""
        SELECT st.name, st.role,
               SUM(sh.hours_worked) as total_hours,
               COUNT(sh.id) as shift_count,
               AVG(sh.hours_worked) as avg_hours
        FROM {STAFF_TABLE} st
        LEFT JOIN {SHIFTS_TABLE} sh ON st.id = sh.staff_id AND sh.shift_date >= ?
        WHERE st.id = ?
        GROUP BY st.id
    """, (start_date, staff_id))

    row = cursor.fetchone()

    # Get recent shifts
    cursor.execute(f"""
        SELECT shift_date, start_time, end_time, hours_worked
        FROM {SHIFTS_TABLE}
        WHERE staff_id = ? AND shift_date >= ?
        ORDER BY shift_date DESC
        LIMIT 10
    """, (staff_id, start_date))

    recent_shifts = [{'date': r[0], 'start': r[1], 'end': r[2], 'hours': r[3]}
                    for r in cursor.fetchall()]

    conn.close()

    if row:
        return {
            'name': row[0],
            'role': row[1],
            'total_hours': row[2] or 0,
            'shift_count': row[3] or 0,
            'average_hours': row[4] or 0,
            'period': period,
            'recent_shifts': recent_shifts
        }
    return {}


def opening_closing_checklist(action: str, checklist_type: str = 'opening') -> Any:
    """Daily procedures checklist."""
    # Predefined checklists
    opening_items = [
        'Unlock doors and disable alarm',
        'Turn on lights and displays',
        'Check cash float and count opening balance',
        'Power on POS system and verify connection',
        'Check voicemail and emails',
        'Review scheduled staff for the day',
        'Inspect store floor and tidy displays',
        'Check stock levels of fast-moving items',
        'Review any pending layaways due today',
        'Set out any new donations received'
    ]

    closing_items = [
        'Announce store closing 15 minutes prior',
        'Ensure all customers have left',
        'Count and reconcile cash register',
        'Complete daily sales report',
        'Secure cash in safe',
        'Power off POS system',
        'Check fitting rooms and clear items',
        'Tidy store floor and straighten displays',
        'Take out trash and recycling',
        'Turn off lights and set alarm',
        'Lock all doors and check security'
    ]

    items = opening_items if checklist_type == 'opening' else closing_items

    if action == 'get':
        return {
            'type': checklist_type,
            'items': [{'id': i+1, 'task': item, 'completed': False} for i, item in enumerate(items)]
        }

    elif action == 'log':
        # In production, would save to database
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity(f'{checklist_type}_checklist', 'charity_shop_operations',
                        completed=True, date=datetime.now().strftime("%Y-%m-%d"))
        return True

    return None


def cash_register_reconciliation(opening_float: float, expected_total: float,
                                actual_total: float, notes: str = "") -> Dict:
    """End-of-day cash counting."""
    difference = actual_total - expected_total
    status = 'balanced' if abs(difference) < 0.01 else ('over' if difference > 0 else 'short')

    result = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'opening_float': opening_float,
        'expected_total': expected_total,
        'actual_total': actual_total,
        'difference': difference,
        'status': status,
        'notes': notes
    }

    if ACTIVITY_LOGGER_AVAILABLE:
        log_activity('cash_reconciliation', 'charity_shop_operations',
                    status=status, difference=difference)

    return result


def register_staff(name: str, email: str = None, phone: str = None, role: str = 'volunteer') -> Optional[int]:
    """Register a new staff member or volunteer."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            INSERT INTO {STAFF_TABLE} (name, email, phone, role, date_joined, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (name, email, phone, role, datetime.now().strftime("%Y-%m-%d")))

        staff_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_staff', staff_id=staff_id, name=name, role=role)

        return staff_id
    except sqlite3.Error as e:
        logger.error(f"Error registering staff: {e}")
        return None


def get_all_staff(active_only: bool = True) -> List[Dict]:
    """Get all staff members."""
    conn = get_connection()
    cursor = conn.cursor()

    query = f"SELECT * FROM {STAFF_TABLE}"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY name"

    cursor.execute(query)

    staff = []
    for row in cursor.fetchall():
        staff.append({
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'phone': row[3],
            'role': row[4],
            'date_joined': row[5],
            'is_active': row[6],
            'total_hours': row[7],
            'total_sales': row[8],
            'sales_count': row[9]
        })

    conn.close()
    return staff

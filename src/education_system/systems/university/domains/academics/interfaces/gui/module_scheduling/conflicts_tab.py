
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.systems.university.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.systems.university.infrastructure.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from education_system.systems.university.domains.academics.interfaces.gui.module_scheduling._dialogs import messagebox
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path
from education_system.systems.university.infrastructure.database.db import sqlite3
# This ensures full backward compatibility
try:
    from education_system.systems.university.domains.academics.domain.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']

    # Import the ModuleScheduler class from the document
    try:
        from education_system.systems.university.domains.academics.domain.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from education_system.systems.university.domains.academics.interfaces.gui.module_scheduling.main_gui import ModuleSchedulingGUI
import tkinter.simpledialog  # noqa: F401 - registers tk.simpledialog

def create_conflicts_tab(self):
    """Create the conflicts management tab"""
    conflicts_frame = ttk.Frame(self.notebook)
    self.notebook.add(conflicts_frame, text=_t("scheduling.tabs.conflicts"))

    # Controls frame
    controls_frame = ttk.Frame(conflicts_frame)
    controls_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(controls_frame, text=_t("scheduling.detect_all_conflicts"),
              command=self.detect_all_conflicts).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("scheduling.resolve_selected"),
              command=self.resolve_selected_conflict).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame,
              text=_t("scheduling.resolve_all", default="Resolve All"),
              command=self.resolve_all_conflicts).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.refresh"),
              command=self.refresh_conflicts).pack(side=tk.LEFT, padx=5)

    # Conflicts treeview
    tree_frame = ttk.Frame(conflicts_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ("ID", "Type", "Description", "Status", "Detected Date")
    self.conflicts_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                       style='Data.Treeview', selectmode="extended")

    for col in columns:
        self.conflicts_tree.heading(col, text=col)
        if col == "Description":
            self.conflicts_tree.column(col, width=400)
        else:
            self.conflicts_tree.column(col, width=120)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.conflicts_tree.yview)
    self.conflicts_tree.configure(yscrollcommand=v_scrollbar.set)

    self.conflicts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

ModuleSchedulingGUI.create_conflicts_tab = create_conflicts_tab

def refresh_conflicts(self):
    """Refresh the conflicts treeview"""
    try:
        # Clear existing items
        for item in self.conflicts_tree.get_children():
            self.conflicts_tree.delete(item)

        conflicts = self.scheduler._get_all_conflicts()

        for conflict in conflicts:
            status = "Resolved" if conflict['resolved'] else "Active"
            detected_date = conflict['detected_date'][:19] if conflict['detected_date'] else "Unknown"

            self.conflicts_tree.insert("", tk.END, values=(
                conflict['id'], conflict['type'], conflict['description'], status, detected_date
            ))

    except Exception as e:
        messagebox.showerror(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.error', default="Error"), f"Failed to refresh conflicts: {str(e)}", parent=self.root)

ModuleSchedulingGUI.refresh_conflicts = refresh_conflicts

def detect_all_conflicts(self):
    """Detect all types of scheduling conflicts"""
    conflicts = []

    # Room conflicts
    room_conflicts = self._detect_room_conflicts()
    conflicts.extend(room_conflicts)

    # Instructor conflicts
    instructor_conflicts = self._detect_instructor_conflicts()
    conflicts.extend(instructor_conflicts)

    # Student conflicts
    student_conflicts = self._detect_student_conflicts()
    conflicts.extend(student_conflicts)

    # Room-capacity overflow conflicts
    capacity_conflicts = self._detect_capacity_conflicts()
    conflicts.extend(capacity_conflicts)

    # Save conflicts to database
    self._save_conflicts_to_db(conflicts)

    # Refresh the conflicts display
    self.refresh_conflicts()

    # Show summary to user
    room_count = len(room_conflicts)
    instr_count = len(instructor_conflicts)
    student_count = len(student_conflicts)
    capacity_count = len(capacity_conflicts)
    total = len(conflicts)

    if total == 0:
        messagebox.showinfo(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.conflict_detection', default="Conflict Detection"), _t('gui.academics.module_scheduling.conflicts_tab.dialogs.no_scheduling_conflicts_detected', default="No scheduling conflicts detected."), parent=self.root)
    else:
        messagebox.showwarning(
            _t('gui.academics.module_scheduling.conflicts_tab.dialogs.conflict_detection', default="Conflict Detection"),
            f"Detected {total} conflict(s):\n\n"
            f"  Room conflicts: {room_count}\n"
            f"  Instructor conflicts: {instr_count}\n"
            f"  Student conflicts: {student_count}\n"
            f"  Over-capacity rooms: {capacity_count}",
            parent=self.root
        )

    return conflicts

ModuleSchedulingGUI.detect_all_conflicts = detect_all_conflicts

def _conflict_row(self, conflict_id):
    """The stored conflict, with its affected schedule ids decoded."""
    import json
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, conflict_type, description, affected_schedules "
            "  FROM schedule_conflicts WHERE id = ?", (conflict_id,)).fetchone()
    if not row:
        return None
    try:
        affected = json.loads(row[3]) if row[3] else []
    except (TypeError, ValueError):
        affected = []
    return {"id": row[0], "type": row[1], "description": row[2],
            "affected": [a for a in affected if a is not None]}


def _find_replacement_room(self, conn, schedule_id, min_capacity=0):
    """A room free for this session's day and time, big enough for it.

    Returns ``(room_id, label)`` or ``(None, None)``. "Free" means no other
    session overlaps it in that room on that day.
    """
    session = conn.execute(
        "SELECT day_of_week, start_time, end_time, room_id, enrolled "
        "  FROM module_schedule WHERE id = ?", (schedule_id,)).fetchone()
    if not session:
        return None, None
    day, start, end, current_room, enrolled = session
    needed = max(int(min_capacity or 0), int(enrolled or 0))

    candidates = conn.execute(
        """SELECT r.id, r.building, r.room_number, r.capacity
             FROM rooms r
            WHERE COALESCE(r.is_active, 1) = 1
              AND r.id <> COALESCE(?, -1)
              AND COALESCE(r.capacity, 0) >= ?
              AND NOT EXISTS (
                    SELECT 1 FROM module_schedule ms
                     WHERE ms.room_id = r.id
                       AND ms.day_of_week = ?
                       AND ms.id <> ?
                       AND ms.start_time < ?
                       AND ms.end_time > ?)
            ORDER BY COALESCE(r.capacity, 0)""",
        (current_room, needed, day, schedule_id, end, start)).fetchall()
    if not candidates:
        return None, None
    room_id, building, number, capacity = candidates[0]
    return room_id, f"{building}-{number} (capacity {capacity})"


def _auto_resolve_conflict(self, conflict):
    """Actually change the schedule so the conflict stops existing.

    Marking a conflict "resolved" with a note left the double-booking in
    place — the row was hidden, the clash was not fixed, and the next
    detection run found it again.

    Room double-bookings and over-capacity rooms have a well-defined fix:
    move one session into a room that is free at that time and big enough.
    Instructor and student clashes are a timetabling decision with no single
    right answer, so those are reported rather than guessed at.

    Returns ``(resolved, note)``.
    """
    kind = (conflict.get("type") or "").lower()
    affected = conflict.get("affected") or []

    if kind not in ("room_conflict", "capacity_conflict") or not affected:
        return False, ""

    # For a double-booking move the later session; for a capacity problem
    # there is only one session to move.
    schedule_id = affected[-1]
    try:
        with transaction() as conn:
            min_capacity = 0
            if kind == "capacity_conflict":
                row = conn.execute(
                    "SELECT COALESCE(enrolled, 0) FROM module_schedule WHERE id = ?",
                    (schedule_id,)).fetchone()
                min_capacity = row[0] if row else 0

            room_id, label = self._find_replacement_room(conn, schedule_id, min_capacity)
            if not room_id:
                return False, ""

            before = conn.execute(
                "SELECT module_code, day_of_week, start_time FROM module_schedule "
                " WHERE id = ?", (schedule_id,)).fetchone()
            conn.execute(
                "UPDATE module_schedule SET room_id = ?, "
                "       modified_date = CURRENT_TIMESTAMP WHERE id = ?",
                (room_id, schedule_id))
    except Exception as exc:
        logger.warning("auto-resolve failed for conflict %s: %s",
                       conflict.get("id"), exc)
        return False, ""

    module = before[0] if before else schedule_id
    when = f"{before[1]} {before[2]}" if before else ""
    return True, f"Moved {module} ({when}) to room {label}."


def resolve_selected_conflict(self):
    """Resolve the selected conflict, changing the schedule where it can."""
    selected = self.conflicts_tree.selection()
    if not selected:
        messagebox.showwarning(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.warning', default="Warning"), _t('gui.academics.module_scheduling.conflicts_tab.dialogs.please_select_a_conflict_to_resolve', default="Please select a conflict to resolve."), parent=self.root)
        return

    conflict_id = self.conflicts_tree.item(selected[0])['values'][0]
    conflict = self._conflict_row(conflict_id)
    if not conflict:
        messagebox.showerror(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.error', default="Error"),
                             "That conflict no longer exists.", parent=self.root)
        return

    resolved, note = self._auto_resolve_conflict(conflict)

    if not resolved:
        # Nothing safe to change automatically — fall back to recording how a
        # person dealt with it, which is what this always used to do.
        note = tk.simpledialog.askstring(
            "Resolve Conflict",
            "This conflict needs a scheduling decision that cannot be made "
            "automatically.\n\nDescribe how it was resolved:",
            parent=self.root)
        if not note:
            return

    try:
        self.scheduler.resolve_conflict(conflict_id, note)
        self.detect_all_conflicts()
        self.refresh_dashboard()
        self.update_activity_log(f"Resolved conflict {conflict_id}: {note}")
        messagebox.showinfo(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.success', default="Success"),
                            note, parent=self.root)
    except Exception as e:
        messagebox.showerror(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.error', default="Error"), f"Failed to resolve conflict: {str(e)}", parent=self.root)

ModuleSchedulingGUI._conflict_row = _conflict_row
ModuleSchedulingGUI._find_replacement_room = _find_replacement_room
ModuleSchedulingGUI._auto_resolve_conflict = _auto_resolve_conflict
ModuleSchedulingGUI.resolve_selected_conflict = resolve_selected_conflict


def resolve_all_conflicts(self):
    """Fix every conflict that can be fixed automatically."""
    import json
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, conflict_type, description, affected_schedules "
                "  FROM schedule_conflicts WHERE resolved = 0 ORDER BY id").fetchall()
    except Exception as exc:
        messagebox.showerror(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.error', default="Error"),
                             f"Could not read conflicts: {exc}", parent=self.root)
        return

    if not rows:
        messagebox.showinfo(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.info', default="Info"),
                            "There are no unresolved conflicts.", parent=self.root)
        return

    if not messagebox.askyesno(
            _t('gui.academics.module_scheduling.conflicts_tab.dialogs.resolve_all', default="Resolve All"),
            f"Attempt to resolve {len(rows)} conflict(s)?\n\n"
            f"Room double-bookings and over-capacity rooms are fixed by moving "
            f"a session to a free, large-enough room. Instructor and student "
            f"clashes need a person and will be left for you.",
            parent=self.root):
        return

    fixed, skipped = [], []
    for row in rows:
        try:
            affected = json.loads(row[3]) if row[3] else []
        except (TypeError, ValueError):
            affected = []
        conflict = {"id": row[0], "type": row[1], "description": row[2],
                    "affected": [a for a in affected if a is not None]}
        resolved, note = self._auto_resolve_conflict(conflict)
        if resolved:
            try:
                self.scheduler.resolve_conflict(row[0], note)
                fixed.append(note)
            except Exception as exc:
                skipped.append(f"{row[2]} — could not record: {exc}")
        else:
            skipped.append(row[2])

    self.detect_all_conflicts()
    self.refresh_dashboard()
    self.update_activity_log(f"Resolve all: fixed {len(fixed)}, left {len(skipped)}")

    lines = [f"Fixed {len(fixed)} of {len(rows)} conflict(s)."]
    if fixed:
        lines += [""] + [f"  \u2713 {n}" for n in fixed[:10]]
    if skipped:
        lines += ["", f"Left for a person ({len(skipped)}):"]
        lines += [f"  \u2014 {n}" for n in skipped[:10]]
    messagebox.showinfo(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.resolve_all', default="Resolve All"),
                        "\n".join(lines), parent=self.root)

ModuleSchedulingGUI.resolve_all_conflicts = resolve_all_conflicts

def _detect_room_conflicts(self):
    """Detect room scheduling conflicts"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT ms1.id, ms1.module_code, ms1.day_of_week, ms1.start_time, ms1.end_time,
               ms2.id, ms2.module_code, ms2.day_of_week, ms2.start_time, ms2.end_time,
               r.building, r.room_number
        FROM module_schedule ms1
        JOIN module_schedule ms2 ON ms1.room_id = ms2.room_id AND ms1.id < ms2.id
        JOIN rooms r ON ms1.room_id = r.id
        WHERE ms1.day_of_week = ms2.day_of_week
        AND ((ms1.start_time < ms2.end_time AND ms1.end_time > ms2.start_time))
        ''')

        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'type': 'room_conflict',
                'description': f"Room {row[10]}-{row[11]} double-booked on {row[2]} between {row[8]} modules {row[1]} and {row[6]}",
                'affected_schedules': [row[0], row[5]],
                'severity': 'high'
            })

        return conflicts

ModuleSchedulingGUI._detect_room_conflicts = _detect_room_conflicts

def _detect_instructor_conflicts(self):
    """Detect instructor scheduling conflicts"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT ms1.id, ms1.module_code, ms1.day_of_week, ms1.start_time, ms1.end_time,
               ms2.id, ms2.module_code, ms2.day_of_week, ms2.start_time, ms2.end_time,
               i.first_name, i.last_name
        FROM module_schedule ms1
        JOIN module_schedule ms2 ON ms1.instructor_id = ms2.instructor_id AND ms1.id < ms2.id
        JOIN instructors i ON ms1.instructor_id = i.id
        WHERE ms1.day_of_week = ms2.day_of_week
        AND ((ms1.start_time < ms2.end_time AND ms1.end_time > ms2.start_time))
        ''')

        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'type': 'instructor_conflict',
                'description': f"Instructor {row[10]} {row[11]} double-booked on {row[2]} between modules {row[1]} and {row[6]}",
                'affected_schedules': [row[0], row[5]],
                'severity': 'high'
            })

        return conflicts

ModuleSchedulingGUI._detect_instructor_conflicts = _detect_instructor_conflicts

def _detect_student_conflicts(self):
    """Detect student scheduling conflicts"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get all students and their enrolled modules
        cursor.execute('SELECT DISTINCT student_id FROM student_modules')
        students = [row[0] for row in cursor.fetchall()]

        conflicts = []
        for student_id in students:
            student_conflicts = self._get_student_conflicts(student_id)
            for conflict in student_conflicts:
                conflicts.append({
                    'type': 'student_conflict',
                    'description': f"Student {student_id} has overlapping classes: {conflict['module1']['code']} and {conflict['module2']['code']} on {conflict['module1']['day']}",
                    'affected_schedules': [],  # Would need schedule IDs
                    'severity': 'medium',
                    'student_id': student_id
                })

        return conflicts

ModuleSchedulingGUI._detect_student_conflicts = _detect_student_conflicts

def _detect_capacity_conflicts(self):
    """Detect sessions whose enrolled headcount exceeds the assigned
    room's capacity. A room can be free (no double-booking) yet still
    be too small for the class scheduled into it."""
    with get_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute('''
            SELECT ms.id, ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number, r.capacity,
                   (SELECT COUNT(*) FROM student_modules sm
                    WHERE sm.module_code = ms.module_code) AS enrolled
            FROM module_schedule ms
            JOIN rooms r ON ms.room_id = r.id
            WHERE r.capacity IS NOT NULL AND r.capacity > 0
            ''')
        except Exception:
            # Missing tables (e.g. student_modules) → nothing to check.
            return []

        conflicts = []
        for row in cursor.fetchall():
            (sched_id, module_code, day, start, end,
             building, room_number, capacity, enrolled) = row
            if enrolled is not None and enrolled > capacity:
                conflicts.append({
                    'type': 'capacity_conflict',
                    'description': (
                        f"Room {building}-{room_number} over capacity for "
                        f"{module_code} on {day} {start}-{end}: "
                        f"{enrolled} enrolled / {capacity} seats"
                    ),
                    'affected_schedules': [sched_id],
                    'severity': 'high',
                })

        return conflicts

ModuleSchedulingGUI._detect_capacity_conflicts = _detect_capacity_conflicts

def _save_conflicts_to_db(self, conflicts):
    """Save detected conflicts to database"""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Clear existing unresolved conflicts
            cursor.execute('DELETE FROM schedule_conflicts WHERE resolved = 0')

            for conflict in conflicts:
                import json
                cursor.execute('''
                INSERT INTO schedule_conflicts
                (conflict_type, description, affected_schedules, resolved)
                VALUES (?, ?, ?, 0)
                ''', (conflict['type'], conflict['description'],
                      json.dumps(conflict['affected_schedules'])))
    except Exception as e:
        print(f"Error saving conflicts: {e}")

ModuleSchedulingGUI._save_conflicts_to_db = _save_conflicts_to_db

def resolve_conflict(self, conflict_id, resolution_notes=""):
    """Mark a conflict as resolved"""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE schedule_conflicts
            SET resolved = 1, resolution_notes = ?, resolved_date = CURRENT_TIMESTAMP
            WHERE id = ?
            ''', (resolution_notes, conflict_id))

            messagebox.showinfo(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.success', default="Success"), f"Conflict {conflict_id} marked as resolved.", parent=self.root)
    except Exception as e:
        messagebox.showerror(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.error', default="Error"), f"Failed to resolve conflict: {str(e)}", parent=self.root)

ModuleSchedulingGUI.resolve_conflict = resolve_conflict

def _get_all_conflicts(self):
    """Get all conflicts from database"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, conflict_type, description, resolved, detected_date, resolution_notes
        FROM schedule_conflicts
        ORDER BY detected_date DESC
        ''')

        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'id': row[0],
                'type': row[1],
                'description': row[2],
                'resolved': bool(row[3]),
                'detected_date': row[4],
                'resolution_notes': row[5]
            })

        return conflicts

ModuleSchedulingGUI._get_all_conflicts = _get_all_conflicts

def _get_student_conflicts(self, student_id):
    """Check for scheduling conflicts in a student's timetable"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check if student exists
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            return []

        # Get modules the student is enrolled in
        cursor.execute('''
        SELECT module_code FROM student_modules WHERE student_id = ?
        ''', (student_id,))

        enrolled_modules = [row[0] for row in cursor.fetchall()]

        if not enrolled_modules:
            return []

        # Get schedule for the enrolled modules
        placeholders = ','.join(['?'] * len(enrolled_modules))
        query = f'''
        SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.module_code IN ({placeholders})
        ORDER BY ms.day_of_week, ms.start_time
        '''

        cursor.execute(query, enrolled_modules)
        schedules = cursor.fetchall()

        # Check for conflicts
        conflicts = []

        for i, schedule1 in enumerate(schedules):
            id1, code1, name1, day1, start1, end1, building1, room1 = schedule1
            room1_str = f"{building1}-{room1}" if building1 and room1 else "TBA"

            for j, schedule2 in enumerate(schedules):
                if i >= j:  # Skip comparing the same schedule or already compared pairs
                    continue

                id2, code2, name2, day2, start2, end2, building2, room2 = schedule2
                room2_str = f"{building2}-{room2}" if building2 and room2 else "TBA"

                # Check if days match and times overlap
                if day1 == day2 and (
                    (start1 <= start2 < end1) or
                    (start1 < end2 <= end1) or
                    (start2 <= start1 < end2) or
                    (start2 < end1 <= end2)
                ):
                    conflicts.append({
                        'module1': {
                            'code': code1,
                            'name': name1,
                            'day': day1,
                            'time': f"{start1}-{end1}",
                            'room': room1_str
                        },
                        'module2': {
                            'code': code2,
                            'name': name2,
                            'day': day2,
                            'time': f"{start2}-{end2}",
                            'room': room2_str
                        }
                    })

        return conflicts

ModuleSchedulingGUI._get_student_conflicts = _get_student_conflicts

def _check_student_conflicts(self, student_id, day_of_week, start_time, end_time, except_module=None):
    """Internal student conflict checker"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get modules the student is enrolled in
        cursor.execute('''
        SELECT module_code FROM student_modules WHERE student_id = ?
        ''', (student_id,))

        enrolled_modules = [row[0] for row in cursor.fetchall()]

        if not enrolled_modules:
            return []

        # Build query to check for conflicts
        query = '''
        SELECT ms.id, ms.module_code, ms.start_time, ms.end_time
        FROM module_schedule ms
        WHERE ms.module_code IN ({}) AND ms.day_of_week = ? AND
        ((ms.start_time < ? AND ms.end_time > ?) OR
        (ms.start_time < ? AND ms.end_time > ?) OR
        (ms.start_time >= ? AND ms.end_time <= ?))
        '''.format(','.join(['?'] * len(enrolled_modules)))

        params = enrolled_modules + [day_of_week, end_time, start_time,
                                    end_time, start_time, start_time, end_time]

        # Exclude a specific module if needed (for updates)
        if except_module:
            query += " AND ms.module_code != ?"
            params.append(except_module)

        cursor.execute(query, params)
        conflicts = cursor.fetchall()

        return conflicts

ModuleSchedulingGUI._check_student_conflicts = _check_student_conflicts

def _check_room_conflicts(self, room_id, day, start_time, end_time, exclude_id=None):
    """Check for room conflicts"""
    with get_connection() as conn:
        cursor = conn.cursor()

        query = '''
        SELECT id, module_code, start_time, end_time
        FROM module_schedule
        WHERE room_id = ? AND day_of_week = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
        '''
        params = [room_id, day, end_time, start_time, end_time, start_time, start_time, end_time]

        if exclude_id:
            query += ' AND id != ?'
            params.append(exclude_id)

        cursor.execute(query, params)
        conflicts = cursor.fetchall()

    return conflicts

ModuleSchedulingGUI._check_room_conflicts = _check_room_conflicts

def _check_instructor_conflicts(self, instructor_id, day, start_time, end_time, exclude_id=None):
    """Check for instructor conflicts"""
    with get_connection() as conn:
        cursor = conn.cursor()

        query = '''
        SELECT id, module_code, start_time, end_time
        FROM module_schedule
        WHERE instructor_id = ? AND day_of_week = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
        '''
        params = [instructor_id, day, end_time, start_time, end_time, start_time, start_time, end_time]

        if exclude_id:
            query += ' AND id != ?'
            params.append(exclude_id)

        cursor.execute(query, params)
        conflicts = cursor.fetchall()

    return conflicts

ModuleSchedulingGUI._check_instructor_conflicts = _check_instructor_conflicts

def display_student_conflicts(self, student_id=None):
    """Display conflicts for a specific student"""
    if not student_id:
        # Show dialog to enter student ID
        student_id = tk.simpledialog.askstring("Student ID", "Enter Student ID:")
        if not student_id:
            return

    conflicts = self._get_student_conflicts(student_id)

    if not conflicts:
        messagebox.showinfo(_t('gui.academics.module_scheduling.conflicts_tab.dialogs.no_conflicts', default="No Conflicts"), f"No scheduling conflicts found for student {student_id}", parent=self.root)
        return

    # Create dialog to show conflicts
    dialog = tk.Toplevel(self.root)
    dialog.title(f"Schedule Conflicts for Student {student_id}")
    dialog.geometry("1000x400")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Module 1', 'Time 1', 'Room 1', 'Module 2', 'Time 2', 'Room 2', 'Day')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    for conflict in conflicts:
        m1 = conflict['module1']
        m2 = conflict['module2']
        tree.insert('', tk.END, values=(
            m1['code'], m1['time'], m1['room'],
            m2['code'], m2['time'], m2['room'],
            m1['day']
        ), tags=('conflict',))

    # Color code conflicts
    tree.tag_configure('conflict', background='#ffcccc')

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Warning label
    warning_frame = ttk.Frame(dialog)
    warning_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Label(warning_frame, text=f"⚠ Found {len(conflicts)} conflict(s) for student {student_id}",
             foreground='red', font=('Arial', 10, 'bold')).pack()

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text=_t('gui.academics.module_scheduling.conflicts_tab.buttons.close', default="Close"), command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.display_student_conflicts = display_student_conflicts


"""Exam seating plans — room layout, candidate allocation, invigilator zones.

Pass 1: data model + service + auto-allocation policies. No GUI yet; the CLI
in academics/cli/exam_seating_cli.py wraps these functions.

Tables
------
exam_room_layouts          one row per room — the grid dimensions
exam_seats                 one row per individual desk with attribute flags
exam_seat_allocations      candidate → seat for a specific exam sitting
exam_invigilator_zones     who covers which part of the room during a sitting

The exams.room column is free-text (e.g. "Old Library"); a layout is bound to
the canonical rooms.id, so allocations look up rooms by exams.room → rooms by
name. If no layout is registered for the exam's room, auto_allocate returns
an error rather than guessing.

Accommodations
--------------
Honours rows from exam_accommodations for the same exam_id:
  * separate_room=1 → student excluded from main hall; flagged in warnings.
  * assistive_technology contains "wheelchair" / "mobility" → accessible seat first.
  * assistive_technology contains "left-hand" → left-handed seat first.
"""

import csv as _csv
import datetime as _dt
import json as _json
import logging
import random as _random
import sqlite3

from education_system.post_18.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


POLICIES = ('alphabetical', 'random', 'spaced')


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_seating_db():
    """Create seating tables if missing. Idempotent."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS exam_room_layouts (
                layout_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id     INTEGER NOT NULL UNIQUE,
                rows_n      INTEGER NOT NULL,
                cols_n      INTEGER NOT NULL,
                seats_total INTEGER NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS exam_seats (
                seat_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                layout_id      INTEGER NOT NULL,
                seat_label     TEXT NOT NULL,
                row_n          INTEGER NOT NULL,
                col_n          INTEGER NOT NULL,
                is_accessible  INTEGER NOT NULL DEFAULT 0,
                is_left_handed INTEGER NOT NULL DEFAULT 0,
                is_disabled    INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT NOT NULL,
                UNIQUE(layout_id, seat_label),
                FOREIGN KEY (layout_id) REFERENCES exam_room_layouts (layout_id)
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS exam_seat_allocations (
                allocation_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id            INTEGER NOT NULL,
                student_id         TEXT NOT NULL,
                seat_id            INTEGER NOT NULL,
                accommodation_notes TEXT,
                created_at         TEXT NOT NULL,
                UNIQUE(exam_id, student_id),
                UNIQUE(exam_id, seat_id),
                FOREIGN KEY (seat_id) REFERENCES exam_seats (seat_id)
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS exam_invigilator_zones (
                zone_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id     INTEGER NOT NULL,
                invigilator TEXT NOT NULL,
                zone_label  TEXT NOT NULL,
                row_start   INTEGER,
                row_end     INTEGER,
                col_start   INTEGER,
                col_end     INTEGER,
                created_at  TEXT NOT NULL
            )
        ''')
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _row_letter(n):
    """1 → 'A', 26 → 'Z', 27 → 'AA' (rare for exam halls)."""
    out = ''
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(ord('A') + r) + out
    return out


def _resolve_room_id(cur, exam_id):
    """Return (room_id, room_label) for an exam row, or (None, label)."""
    cur.execute('SELECT room FROM exams WHERE id = ?', (exam_id,))
    row = cur.fetchone()
    if not row:
        return None, None
    label = row[0]
    if not label:
        return None, None
    cur.execute('''
        SELECT id FROM rooms
        WHERE room_name = ? OR room_number = ?
        LIMIT 1
    ''', (label, label))
    r = cur.fetchone()
    return (r[0] if r else None), label


def _load_enrolled_students(cur, exam_id):
    """Return list of student_id strings enrolled in the exam."""
    cur.execute(
        'SELECT enrolled_student_ids FROM exams WHERE id = ?', (exam_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return []
    raw = row[0]
    try:
        parsed = _json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, _json.JSONDecodeError):
        return []
    return [str(s) for s in (parsed or [])]


def summarise_accommodations(scheduler_exam_id, student_ids=None):
    """Return a summary dict for the accommodations affecting an exam.

    Looks up exam_accommodations for the given scheduler exam_id; intersects
    with `student_ids` when provided so callers can also report on a draft
    enrolment list. Returns:
        {
          'total_affected': int,
          'separate_room': int,
          'reader_scribe': int,
          'extended_time_count': int,
          'extended_time_max': int,    # minutes
          'assistive_count': int,
          'examples': [str, ...]       # short human-readable lines (first 5)
        }
    Returns zeros if exam_accommodations doesn't exist or no rows match.
    """
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute('''
                SELECT student_id, separate_room, reader_scribe, extended_time,
                       assistive_technology
                FROM exam_accommodations
                WHERE (exam_id = ? OR exam_id IS NULL) AND status = 'active'
            ''', (scheduler_exam_id,))
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            return {'total_affected': 0, 'separate_room': 0, 'reader_scribe': 0,
                    'extended_time_count': 0, 'extended_time_max': 0,
                    'assistive_count': 0, 'examples': []}
    finally:
        conn.close()

    allowed = None
    if student_ids is not None:
        allowed = {str(s) for s in student_ids}

    affected = set()
    separate = scribe = ext_count = assistive = 0
    ext_max = 0
    examples = []
    for sid, sep, scr, ext, assist in rows:
        sid_str = str(sid)
        if allowed is not None and sid_str not in allowed:
            try:
                if int(sid_str) not in {int(s) for s in allowed if str(s).isdigit()}:
                    continue
            except ValueError:
                continue
        affected.add(sid_str)
        bits = []
        if sep:
            separate += 1
            bits.append('separate room')
        if scr:
            scribe += 1
            bits.append('reader/scribe')
        if ext:
            ext_count += 1
            ext_max = max(ext_max, int(ext))
            bits.append(f"+{int(ext)} min")
        if assist:
            assistive += 1
            bits.append(f"assistive: {assist}")
        if bits and len(examples) < 5:
            examples.append(f"  - {sid_str}: {', '.join(bits)}")
    return {
        'total_affected': len(affected),
        'separate_room': separate,
        'reader_scribe': scribe,
        'extended_time_count': ext_count,
        'extended_time_max': ext_max,
        'assistive_count': assistive,
        'examples': examples,
    }


def format_accommodation_summary(summary):
    """Pretty-print summarise_accommodations() output."""
    if not summary or not summary.get('total_affected'):
        return None
    lines = [f"{summary['total_affected']} student(s) have active accommodations:"]
    if summary['separate_room']:
        lines.append(f"  · {summary['separate_room']} need a separate room")
    if summary['reader_scribe']:
        lines.append(f"  · {summary['reader_scribe']} need a reader/scribe")
    if summary['extended_time_count']:
        lines.append(f"  · {summary['extended_time_count']} get extra time "
                     f"(up to +{summary['extended_time_max']} min)")
    if summary['assistive_count']:
        lines.append(f"  · {summary['assistive_count']} use assistive technology")
    if summary['examples']:
        lines.append("Examples:")
        lines.extend(summary['examples'])
    return "\n".join(lines)


def _accommodations_for(cur, exam_id):
    """Return dict student_id_str → {'separate_room', 'assistive', 'reader_scribe', 'extended_time'}."""
    try:
        cur.execute('''
            SELECT student_id, separate_room, assistive_technology, reader_scribe,
                   extended_time
            FROM exam_accommodations
            WHERE exam_id = ? AND status = 'active'
        ''', (exam_id,))
    except sqlite3.OperationalError:
        return {}
    out = {}
    for sid, sep, assistive, reader, ext in cur.fetchall():
        out[str(sid)] = {
            'separate_room': bool(sep),
            'assistive': (assistive or '').lower(),
            'reader_scribe': bool(reader),
            'extended_time': int(ext or 0),
        }
    return out


# ---------------------------------------------------------------------------
# Layout management
# ---------------------------------------------------------------------------

def define_room_layout(room_id, rows_n, cols_n, *,
                       accessible_seats=None,
                       left_handed_seats=None,
                       disabled_seats=None):
    """Create or replace a layout for a room.

    Seat labels are auto-generated as '<row letter><col number>'. Caller can
    pass sets/lists of labels in accessible_seats / left_handed_seats /
    disabled_seats to set attribute flags. Returns layout_id.
    """
    if rows_n <= 0 or cols_n <= 0:
        raise ValueError("rows and cols must be positive")
    if rows_n > 26 * 26:
        raise ValueError("too many rows")
    accessible = set(accessible_seats or [])
    left_handed = set(left_handed_seats or [])
    disabled = set(disabled_seats or [])

    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        ts = _now()

        # Replace any existing layout for the room.
        cur.execute('SELECT layout_id, rows_n, cols_n FROM exam_room_layouts '
                    'WHERE room_id = ?', (room_id,))
        existing = cur.fetchone()
        if existing:
            old_layout_id, old_rows_n, old_cols_n = existing

            # If the grid geometry is unchanged, only seat attribute flags are
            # being edited. Update them in place so seat_ids — and therefore any
            # existing allocations — stay valid, instead of destroying the layout.
            if old_rows_n == rows_n and old_cols_n == cols_n:
                total = rows_n * cols_n - len(disabled)
                for r in range(1, rows_n + 1):
                    for c in range(1, cols_n + 1):
                        label = f"{_row_letter(r)}{c}"
                        cur.execute('''
                            UPDATE exam_seats
                            SET is_accessible = ?, is_left_handed = ?, is_disabled = ?
                            WHERE layout_id = ? AND seat_label = ?
                        ''', (
                            1 if label in accessible else 0,
                            1 if label in left_handed else 0,
                            1 if label in disabled else 0,
                            old_layout_id, label,
                        ))
                cur.execute('''
                    UPDATE exam_room_layouts
                    SET seats_total = ?, updated_at = ?
                    WHERE layout_id = ?
                ''', (total, ts, old_layout_id))
                conn.commit()
                return old_layout_id

            # Geometry changed — the old seats (and their ids) are invalidated,
            # so a full replace is required. Refuse if allocations reference them.
            cur.execute('''
                SELECT COUNT(*) FROM exam_seat_allocations a
                JOIN exam_seats s ON a.seat_id = s.seat_id
                WHERE s.layout_id = ?
            ''', (old_layout_id,))
            if cur.fetchone()[0] > 0:
                raise RuntimeError(
                    "Cannot resize layout — exam allocations still reference its seats. "
                    "Clear allocations first."
                )
            cur.execute('DELETE FROM exam_seats WHERE layout_id = ?', (old_layout_id,))
            cur.execute('DELETE FROM exam_room_layouts WHERE layout_id = ?', (old_layout_id,))

        total = rows_n * cols_n - len(disabled)
        cur.execute('''
            INSERT INTO exam_room_layouts
            (room_id, rows_n, cols_n, seats_total, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (room_id, rows_n, cols_n, total, ts, ts))
        layout_id = cur.lastrowid

        rows = []
        for r in range(1, rows_n + 1):
            for c in range(1, cols_n + 1):
                label = f"{_row_letter(r)}{c}"
                rows.append((
                    layout_id, label, r, c,
                    1 if label in accessible else 0,
                    1 if label in left_handed else 0,
                    1 if label in disabled else 0,
                    ts,
                ))
        cur.executemany('''
            INSERT INTO exam_seats
            (layout_id, seat_label, row_n, col_n, is_accessible, is_left_handed,
             is_disabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', rows)
        conn.commit()
        return layout_id
    finally:
        conn.close()


def delete_room_layout(room_id):
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT layout_id FROM exam_room_layouts WHERE room_id = ?', (room_id,))
        row = cur.fetchone()
        if not row:
            return False
        layout_id = row[0]
        cur.execute('''
            SELECT COUNT(*) FROM exam_seat_allocations a
            JOIN exam_seats s ON a.seat_id = s.seat_id
            WHERE s.layout_id = ?
        ''', (layout_id,))
        if cur.fetchone()[0] > 0:
            raise RuntimeError("Layout has active allocations.")
        cur.execute('DELETE FROM exam_seats WHERE layout_id = ?', (layout_id,))
        cur.execute('DELETE FROM exam_room_layouts WHERE layout_id = ?', (layout_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def get_layout(room_id):
    """Return {'layout_id', 'rows_n', 'cols_n', 'seats': [...]} or None."""
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT layout_id, rows_n, cols_n, seats_total '
            'FROM exam_room_layouts WHERE room_id = ?', (room_id,))
        row = cur.fetchone()
        if not row:
            return None
        layout_id, rows_n, cols_n, total = row
        cur.execute('''
            SELECT seat_id, seat_label, row_n, col_n,
                   is_accessible, is_left_handed, is_disabled
            FROM exam_seats WHERE layout_id = ?
            ORDER BY row_n, col_n
        ''', (layout_id,))
        seats = [
            {'seat_id': s[0], 'seat_label': s[1], 'row_n': s[2], 'col_n': s[3],
             'is_accessible': bool(s[4]), 'is_left_handed': bool(s[5]),
             'is_disabled': bool(s[6])}
            for s in cur.fetchall()
        ]
        return {'layout_id': layout_id, 'room_id': room_id,
                'rows_n': rows_n, 'cols_n': cols_n,
                'seats_total': total, 'seats': seats}
    finally:
        conn.close()


def list_layouts():
    """Return rooms with a registered layout."""
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT l.layout_id, l.room_id,
                   COALESCE(r.room_name, r.room_number),
                   r.building, l.rows_n, l.cols_n, l.seats_total
            FROM exam_room_layouts l
            LEFT JOIN rooms r ON r.id = l.room_id
            ORDER BY r.building, r.room_name
        ''')
        return [
            {'layout_id': row[0], 'room_id': row[1], 'room_name': row[2],
             'building': row[3], 'rows_n': row[4], 'cols_n': row[5],
             'seats_total': row[6]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def clear_allocation(exam_id):
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM exam_seat_allocations WHERE exam_id = ?', (exam_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def _order_students(students_ids, policy):
    if policy == 'alphabetical':
        return sorted(students_ids, key=lambda s: s.lower())
    if policy == 'random':
        out = list(students_ids)
        _random.shuffle(out)
        return out
    if policy == 'spaced':
        # Same as alphabetical — spacing is applied at seat selection.
        return sorted(students_ids, key=lambda s: s.lower())
    raise ValueError(f"Unknown policy: {policy}")


def _select_seats(layout, policy):
    """Return ordered list of usable seats per the policy.

    Disabled seats are skipped. 'spaced' picks every other seat in row-major
    order — yields ~half the capacity but gives candidates more elbow room.
    """
    usable = [s for s in layout['seats'] if not s['is_disabled']]
    usable.sort(key=lambda s: (s['row_n'], s['col_n']))
    if policy == 'spaced':
        return usable[::2]
    return usable


def auto_allocate(exam_id, policy='alphabetical'):
    """Assign enrolled students to seats.

    Returns:
        {
          'allocated': int,
          'unallocated': [(student_id, reason), ...],
          'policy': str,
          'room_id': int|None,
          'room_label': str|None,
          'warnings': [str, ...],
        }
    """
    if policy not in POLICIES:
        raise ValueError(f"Policy must be one of {POLICIES}")

    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        room_id, room_label = _resolve_room_id(cur, exam_id)
        if room_id is None:
            return {
                'allocated': 0, 'unallocated': [],
                'policy': policy, 'room_id': None, 'room_label': room_label,
                'warnings': [f"Exam {exam_id} has no resolvable room "
                             f"(room field: {room_label!r})."],
            }
        layout = get_layout(room_id)
        if not layout:
            return {
                'allocated': 0, 'unallocated': [],
                'policy': policy, 'room_id': room_id, 'room_label': room_label,
                'warnings': [f"Room {room_label!r} has no seating layout — "
                             f"run Define Room Layout first."],
            }

        students = _load_enrolled_students(cur, exam_id)
        if not students:
            return {
                'allocated': 0, 'unallocated': [],
                'policy': policy, 'room_id': room_id, 'room_label': room_label,
                'warnings': ["Exam has no enrolled students recorded."],
            }

        accommodations = _accommodations_for(cur, exam_id)
        warnings = []
        unallocated = []

        # Wipe prior allocations so re-running is deterministic.
        cur.execute('DELETE FROM exam_seat_allocations WHERE exam_id = ?', (exam_id,))

        usable_seats = _select_seats(layout, policy)
        # Separate by attribute for targeted assignment.
        accessible_pool = [s for s in usable_seats if s['is_accessible']]
        left_handed_pool = [s for s in usable_seats if s['is_left_handed']]
        general_pool = [s for s in usable_seats
                        if not s['is_accessible'] and not s['is_left_handed']]

        def _pop_seat_for(student_id):
            """Pick the best seat for a student given their accommodation needs."""
            needs = accommodations.get(student_id, {})
            assistive = needs.get('assistive', '')
            if 'wheelchair' in assistive or 'mobility' in assistive:
                if accessible_pool:
                    return accessible_pool.pop(0), 'wheelchair-accessible'
            if 'left-hand' in assistive or 'left hand' in assistive:
                if left_handed_pool:
                    return left_handed_pool.pop(0), 'left-handed desk'
            # Fall through to general pool. Accessible/left-handed seats are
            # held back unless the general pool is empty — keep specialist seats
            # for the candidates who actually need them.
            if general_pool:
                return general_pool.pop(0), None
            if accessible_pool:
                return accessible_pool.pop(0), 'using accessible seat (overflow)'
            if left_handed_pool:
                return left_handed_pool.pop(0), 'using left-handed seat (overflow)'
            return None, None

        ts = _now()
        allocated = 0
        ordered = _order_students(students, policy)
        for sid in ordered:
            needs = accommodations.get(sid, {})
            if needs.get('separate_room'):
                unallocated.append((sid, 'requires separate room — allocate manually'))
                continue
            seat, note = _pop_seat_for(sid)
            if not seat:
                unallocated.append((sid, 'no seat available'))
                continue
            extra = []
            if note:
                extra.append(note)
            if needs.get('reader_scribe'):
                extra.append('reader/scribe required')
            if needs.get('extended_time'):
                extra.append(f"+{needs['extended_time']} min extra time")
            acc_note = '; '.join(extra) if extra else None
            cur.execute('''
                INSERT INTO exam_seat_allocations
                (exam_id, student_id, seat_id, accommodation_notes, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (exam_id, sid, seat['seat_id'], acc_note, ts))
            allocated += 1

        capacity = len(usable_seats) - len(accessible_pool) - len(left_handed_pool) - len(general_pool)
        if unallocated and 'no seat available' in {r for _, r in unallocated}:
            warnings.append(
                f"Room capacity exceeded by {sum(1 for _, r in unallocated if 'no seat' in r)} "
                f"candidate(s) under policy '{policy}'."
            )
        conn.commit()
        return {
            'allocated': allocated,
            'unallocated': unallocated,
            'policy': policy,
            'room_id': room_id,
            'room_label': room_label,
            'warnings': warnings,
            'capacity_used': capacity,
        }
    finally:
        conn.close()


def list_allocations(exam_id):
    """Return [{'student_id', 'seat_label', 'row_n', 'col_n', 'accommodation_notes'}]."""
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT a.student_id, s.seat_label, s.row_n, s.col_n,
                   a.accommodation_notes
            FROM exam_seat_allocations a
            JOIN exam_seats s ON a.seat_id = s.seat_id
            WHERE a.exam_id = ?
            ORDER BY s.row_n, s.col_n
        ''', (exam_id,))
        return [
            {'student_id': r[0], 'seat_label': r[1], 'row_n': r[2],
             'col_n': r[3], 'accommodation_notes': r[4]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Charts + export
# ---------------------------------------------------------------------------

def seating_chart(exam_id):
    """Return a multi-line ASCII chart showing the grid + allocations."""
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        room_id, room_label = _resolve_room_id(cur, exam_id)
        if room_id is None:
            return f"(no resolvable room for exam {exam_id})"
        layout = get_layout(room_id)
        if not layout:
            return f"(no layout for room {room_label!r})"
        cur.execute('''
            SELECT s.row_n, s.col_n, s.seat_label, s.is_accessible,
                   s.is_left_handed, s.is_disabled, a.student_id,
                   a.accommodation_notes
            FROM exam_seats s
            LEFT JOIN exam_seat_allocations a
                ON a.seat_id = s.seat_id AND a.exam_id = ?
            WHERE s.layout_id = ?
            ORDER BY s.row_n, s.col_n
        ''', (exam_id, layout['layout_id']))
        cells = cur.fetchall()
    finally:
        conn.close()

    grid = {}
    for row_n, col_n, label, acc, lh, dis, sid, notes in cells:
        grid[(row_n, col_n)] = {
            'label': label, 'accessible': bool(acc),
            'left_handed': bool(lh), 'disabled': bool(dis),
            'student_id': sid, 'notes': notes,
        }
    rows_n, cols_n = layout['rows_n'], layout['cols_n']

    # Width: enough for student_id or "—" or "X" plus markers
    col_w = 14
    lines = [f"Seating for exam {exam_id} — {room_label} ({rows_n}×{cols_n})"]
    lines.append("Legend: ♿ accessible · ✋ left-handed · X disabled · — unassigned")
    header = "    " + "".join(f"{c:^{col_w}}" for c in range(1, cols_n + 1))
    lines.append(header)
    for r in range(1, rows_n + 1):
        line = f" {_row_letter(r):>2} "
        for c in range(1, cols_n + 1):
            cell = grid.get((r, c))
            if not cell:
                line += "?".center(col_w)
                continue
            if cell['disabled']:
                token = "X"
            elif cell['student_id']:
                token = cell['student_id']
            else:
                token = "—"
            markers = ''
            if cell['accessible']:
                markers += '♿'
            if cell['left_handed']:
                markers += '✋'
            display = f"{token}{markers}"[:col_w - 2]
            line += display.center(col_w)
        lines.append(line)
    return "\n".join(lines)


def export_chart_csv(exam_id, filepath):
    """Write a per-seat CSV: seat_label, row, col, attrs, student_id, notes."""
    init_seating_db()
    rows = []
    conn = get_connection()
    try:
        cur = conn.cursor()
        room_id, room_label = _resolve_room_id(cur, exam_id)
        if room_id is None:
            raise RuntimeError("No resolvable room for this exam.")
        layout = get_layout(room_id)
        if not layout:
            raise RuntimeError(f"No layout for room {room_label!r}.")
        cur.execute('''
            SELECT s.seat_label, s.row_n, s.col_n,
                   s.is_accessible, s.is_left_handed, s.is_disabled,
                   a.student_id, a.accommodation_notes
            FROM exam_seats s
            LEFT JOIN exam_seat_allocations a
                ON a.seat_id = s.seat_id AND a.exam_id = ?
            WHERE s.layout_id = ?
            ORDER BY s.row_n, s.col_n
        ''', (exam_id, layout['layout_id']))
        rows = cur.fetchall()
    finally:
        conn.close()

    with open(filepath, 'w', newline='', encoding='utf-8') as fp:
        w = _csv.writer(fp)
        w.writerow(['Seat', 'Row', 'Col', 'Accessible', 'LeftHanded',
                    'Disabled', 'StudentID', 'AccommodationNotes'])
        for label, r, c, acc, lh, dis, sid, notes in rows:
            w.writerow([label, r, c,
                        'Y' if acc else '',
                        'Y' if lh else '',
                        'Y' if dis else '',
                        sid or '',
                        notes or ''])
    return len(rows)


# ---------------------------------------------------------------------------
# Invigilator zones
# ---------------------------------------------------------------------------

def assign_invigilator_zone(exam_id, invigilator, zone_label, *,
                            row_start=None, row_end=None,
                            col_start=None, col_end=None):
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO exam_invigilator_zones
            (exam_id, invigilator, zone_label, row_start, row_end,
             col_start, col_end, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (exam_id, invigilator, zone_label,
              row_start, row_end, col_start, col_end, _now()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_zones(exam_id):
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT zone_id, invigilator, zone_label,
                   row_start, row_end, col_start, col_end
            FROM exam_invigilator_zones
            WHERE exam_id = ?
            ORDER BY zone_id
        ''', (exam_id,))
        return [
            {'zone_id': r[0], 'invigilator': r[1], 'zone_label': r[2],
             'row_start': r[3], 'row_end': r[4],
             'col_start': r[5], 'col_end': r[6]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def clear_zones(exam_id):
    init_seating_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM exam_invigilator_zones WHERE exam_id = ?', (exam_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()

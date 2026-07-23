"""CLI handlers for integrations (LMS, calendar, import/export)."""

import datetime
import uuid
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.paths import EXPORTS_DIR


def handle_lms_integration():
    """Export attendance as an LMS-importable CSV (Moodle / Canvas gradebook).

    Produces a standards-based CSV whose columns map onto the fields Moodle and
    Canvas gradebook imports expect (student identifier, name, module/course
    code, session date, status). The file is written under the shared exports
    directory so it can be uploaded directly to the LMS.
    """
    import pandas as pd
    print("\n🔗 LMS INTEGRATION")
    print("Exporting attendance in an LMS-importable format...")

    try:
        conn = get_connection()

        query = '''
        SELECT ar.student_id AS student_id,
               TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) AS name,
               s.email_address AS email,
               ar.module_code AS module_code,
               ar.date AS session_date,
               ar.session_id AS session_id,
               ar.status AS status
        FROM attendance_records ar
        LEFT JOIN students s ON ar.student_id = s.student_id
        ORDER BY ar.date DESC, ar.module_code, ar.student_id
        '''

        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print("No attendance data available to export.")
            return

        export_dir = EXPORTS_DIR / "lms"
        export_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = export_dir / f"lms_attendance_{stamp}.csv"

        # A standard, comma-separated file with a header row: this is the shape
        # Moodle ("Import > CSV") and Canvas ("Gradebook > Import") both accept.
        df.to_csv(output_path, index=False, lineterminator="\n")

        print(f"✅ Exported {len(df)} attendance rows to:")
        print(f"   {output_path}")
        print("Import this CSV via Moodle (Import > CSV) or the Canvas gradebook importer.")
        print("Note: a live API push (Moodle web-service / Canvas REST) additionally")
        print("requires configured LMS base URL and API token credentials.")

    except Exception as e:  # noqa: BLE001 - surface any export failure to the CLI user
        print(f"Error exporting attendance for LMS: {e}")


def _ics_escape(text):
    """Escape a text value for an iCalendar property (RFC 5545 §3.3.11)."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _ics_datetime(value):
    """Format a stored date/datetime string as an iCalendar value.

    Returns a ``(property_suffix, value)`` tuple, e.g. ``("", "20260617T090000")``
    for a timestamp or ``(";VALUE=DATE", "20260617")`` for an all-day date.
    Returns ``None`` when *value* cannot be parsed.
    """
    if not value:
        return None
    raw = str(value).strip().replace("T", " ")
    for fmt, is_dt in (
        ("%Y-%m-%d %H:%M:%S", True),
        ("%Y-%m-%d %H:%M", True),
        ("%Y-%m-%d", False),
    ):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if is_dt:
            return ("", dt.strftime("%Y%m%dT%H%M%S"))
        return (";VALUE=DATE", dt.strftime("%Y%m%d"))
    return None


def handle_calendar_sync():
    """Export the academic calendar as an RFC 5545 .ics file.

    The generated VCALENDAR/VEVENT file is directly importable by Google
    Calendar, Outlook and Apple Calendar, so no live API access is required.
    """
    print("\n📅 CALENDAR SYNC")
    print("Generating an iCalendar (.ics) file from the academic calendar...")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Discover which datetime columns actually exist before selecting them.
        cols = {row[1] for row in cursor.execute("PRAGMA table_info(academic_calendar_events)")}
        if not cols:
            conn.close()
            print("No academic_calendar_events table found; nothing to sync.")
            return

        cursor.execute(
            """
            SELECT id, name, date, date_start, date_end, start_time, end_time,
                   location, description
            FROM academic_calendar_events
            ORDER BY COALESCE(date, date_start)
            """
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print("No calendar events available to export.")
            return

        now_utc = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//University System//Academic Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        exported = 0
        for r in rows:
            (
                eid, name, date_only, date_start, date_end,
                start_time, end_time, location, description,
            ) = r

            # Prefer explicit start/end; fall back to the all-day `date` column,
            # optionally combined with a separate time column.
            start_source = date_start or date_only
            if start_source and start_time and " " not in str(start_source):
                start_source = f"{start_source} {start_time}"
            start = _ics_datetime(start_source)
            if start is None:
                continue

            end_source = date_end
            if end_source and end_time and " " not in str(end_source):
                end_source = f"{end_source} {end_time}"
            end = _ics_datetime(end_source)

            uid = f"{eid or uuid.uuid4().hex}@university-system"
            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:{uid}")
            lines.append(f"DTSTAMP:{now_utc}")
            lines.append(f"DTSTART{start[0]}:{start[1]}")
            if end is not None:
                lines.append(f"DTEND{end[0]}:{end[1]}")
            lines.append(f"SUMMARY:{_ics_escape(name or 'Untitled event')}")
            if description:
                lines.append(f"DESCRIPTION:{_ics_escape(description)}")
            if location:
                lines.append(f"LOCATION:{_ics_escape(location)}")
            lines.append("END:VEVENT")
            exported += 1

        lines.append("END:VCALENDAR")

        if exported == 0:
            print("No events had a parseable date; nothing to export.")
            return

        export_dir = EXPORTS_DIR / "calendar"
        export_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = export_dir / f"academic_calendar_{stamp}.ics"

        # RFC 5545 requires CRLF line endings between content lines.
        output_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")

        print(f"✅ Exported {exported} events to iCalendar file:")
        print(f"   {output_path}")
        print("Import this .ics directly into Google Calendar, Outlook or Apple Calendar.")

    except Exception as e:  # noqa: BLE001 - surface any export failure to the CLI user
        print(f"Error generating calendar export: {e}")


def handle_import_export():
    """Handle data import/export"""
    import pandas as pd
    print("\n📁 IMPORT/EXPORT DATA")
    print("1. Export Attendance Data")
    print("2. Import Student Data")
    print("3. Backup Database")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        print("Exporting attendance data...")

        try:
            conn = get_connection()

            query = '''
            SELECT ar.student_id, s.first_name, s.last_name, ar.module_code,
                   ar.date, ar.status, ar.notes, ar.check_in_method, ar.recorded_at
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            ORDER BY ar.date DESC, ar.student_id
            '''

            df = pd.read_sql_query(query, conn)
            conn.close()

            if not df.empty:
                output_path = f"attendance_export_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
                df.to_excel(output_path, index=False)
                print(f"✅ Attendance data exported to: {output_path}")
            else:
                print("No attendance data to export.")

        except Exception as e:
            print(f"Error exporting data: {e}")


def handle_audit_logs():
    """Handle audit logs viewing"""
    print("\n📋 AUDIT LOGS")
    print("1. View Recent Logs")
    print("2. Search Logs")
    print("3. Export Logs")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT user_id, action, table_name, record_id, timestamp
            FROM attendance_audit_log
            ORDER BY timestamp DESC
            LIMIT 50
            ''')

            logs = cursor.fetchall()
            conn.close()

            if logs:
                print("\n📋 RECENT AUDIT LOGS")
                print("=" * 80)
                print(f"{'User':<15} {'Action':<20} {'Table':<20} {'Record ID':<15} {'Timestamp'}")
                print("-" * 80)

                for log in logs:
                    user_id, action, table_name, record_id, timestamp = log
                    timestamp_display = timestamp.split('T')[0] + ' ' + timestamp.split('T')[1][:8]
                    print(f"{user_id:<15} {action:<20} {table_name:<20} {record_id:<15} {timestamp_display}")
            else:
                print("No audit logs found.")

        except Exception as e:
            print(f"Error retrieving audit logs: {e}")

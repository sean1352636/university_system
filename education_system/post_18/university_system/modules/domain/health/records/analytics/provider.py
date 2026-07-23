from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.post_18.university_system.modules.domain.health.records.db.audit import log_audit_event


def analyze_provider_workload(auth):
    """Workload by provider: last 30d, next 7d, status mix, simple capacity util if schedules exist."""
    if hasattr(auth, "check_permission") and not auth.check_permission("view_health_analytics"):
        print("You don't have permission to view analytics.")
        return

    conn = get_connection()
    try:
        c = conn.cursor()

        # Detect appointments table
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='health_appointments'")
        table = "health_appointments" if c.fetchone() else "appointments"

        # Introspect columns
        c.execute("PRAGMA table_info([" + table + "])")
        cols = [row[1] for row in c.fetchall()]

        provider_col = next((x for x in ("provider", "provider_id", "practitioner_id", "staff_id") if x in cols), None)
        status_col   = next((x for x in ("status", "appointment_status") if x in cols), None)

        # Datetime expression (prefer date+time, else appointment_datetime, else date only)
        if "appointment_date" in cols and "appointment_time" in cols:
            dt_expr = table + ".appointment_date||' '||" + table + ".appointment_time"
        elif "appointment_datetime" in cols:
            dt_expr = table + ".appointment_datetime"
        elif "date" in cols:
            dt_expr = table + ".date"
        elif "scheduled_time" in cols:
            dt_expr = table + ".scheduled_time"
        else:
            dt_expr = None  # fall back to whole-table counts

        print("\n===== Provider Workload Analysis =====")
        if not provider_col:
            print("No provider column found on the appointments table. Nothing to analyze.")
            return

        # Last 30 days per provider
        where_30 = "WHERE datetime(" + dt_expr + ") >= datetime('now','localtime','-30 day')" if dt_expr else ""
        c.execute(
            "SELECT [" + provider_col + "] AS provider, COUNT(*) AS n"
            " FROM [" + table + "] " + where_30 +
            " GROUP BY [" + provider_col + "]"
            " ORDER BY n DESC"
        )
        rows_30 = c.fetchall()
        if rows_30:
            print("\nLast 30 days (booked/completed/cancelled mixed):")
            for prov, n in rows_30[:10]:
                print(f" - {prov or 'UNKNOWN'}: {n}")

        # Upcoming 7 days (scheduled/pending only)
        where_up = "WHERE 1=1"
        if dt_expr:
            where_up += " AND datetime(" + dt_expr + ") >= datetime('now','localtime') AND datetime(" + dt_expr + ") < datetime('now','localtime','+7 day')"
        if status_col:
            where_up += " AND ([" + status_col + "] IN ('scheduled','booked','pending') OR [" + status_col + "] IS NULL)"
        c.execute(
            "SELECT [" + provider_col + "] AS provider, COUNT(*) AS n"
            " FROM [" + table + "] " + where_up +
            " GROUP BY [" + provider_col + "]"
            " ORDER BY n DESC"
        )
        rows_up = c.fetchall()
        print("\nUpcoming 7 days (scheduled/pending):")
        if rows_up:
            for prov, n in rows_up[:10]:
                print(f" - {prov or 'UNKNOWN'}: {n}")
        else:
            print(" - No upcoming appointments found (or no datetime column).")

        # Status mix (last 30d)
        if status_col:
            c.execute(
                "SELECT [" + provider_col + "] AS provider, [" + status_col + "] AS status, COUNT(*) AS n"
                " FROM [" + table + "] " + where_30 +
                " GROUP BY [" + provider_col + "], [" + status_col + "]"
                " ORDER BY [" + provider_col + "], n DESC"
            )
            rows_mix = c.fetchall()
            if rows_mix:
                print("\nStatus breakdown (last 30 days):")
                current = None
                for prov, status, n in rows_mix:
                    if prov != current:
                        current = prov
                        print(f" {prov or 'UNKNOWN'}:")
                    print(f"    {status or 'UNKNOWN'}: {n}")
        else:
            print("\nNo status column; skipping status breakdown.")

        # Average/day per provider (last 30d)
        if dt_expr and rows_30:
            c.execute(
                "SELECT [" + provider_col + "] AS provider, ROUND(COUNT(*)/30.0, 2) AS per_day"
                " FROM [" + table + "] " + where_30 +
                " GROUP BY [" + provider_col + "]"
                " ORDER BY per_day DESC"
            )
            rows_avg = c.fetchall()
            print("\nAverage appointments per day (last 30 days):")
            for prov, per_day in rows_avg[:10]:
                print(f" - {prov or 'UNKNOWN'}: {per_day}")

        # Simple capacity/utilization if provider_schedules exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='provider_schedules'")
        if c.fetchone() and dt_expr:
            # Weekly capacity by provider from schedules
            c.execute("""
                SELECT provider_name, COALESCE(SUM(max_appointments),0) AS weekly_capacity
                FROM provider_schedules
                WHERE active = 1
                GROUP BY provider_name
            """)
            cap = {row[0]: row[1] for row in c.fetchall()}

            # Last 28 days workload by provider
            c.execute(
                "SELECT [" + provider_col + "] AS provider, COUNT(*) AS n"
                " FROM [" + table + "]"
                " WHERE datetime(" + dt_expr + ") >= datetime('now','localtime','-28 day')"
                " GROUP BY [" + provider_col + "]"
            )
            util = {}
            for prov, n in c.fetchall():
                weekly = cap.get(prov, 0)
                capacity_28 = weekly * 4  # approx 4 weeks
                util[prov] = (n, capacity_28, (n / capacity_28 * 100.0) if capacity_28 else None)

            if util:
                print("\nUtilization (last 28 days vs schedule capacity):")
                for prov, (n, cap28, pct) in sorted(util.items(), key=lambda x: (x[1][2] or -1), reverse=True)[:10]:
                    if pct is None:
                        print(f" - {prov or 'UNKNOWN'}: {n} booked; no schedule capacity found")
                    else:
                        print(f" - {prov or 'UNKNOWN'}: {n}/{cap28} ({pct:.1f}%)")
        else:
            print("\nNo provider_schedules table or no datetime column; skipping capacity/utilization.")

        # Audit (reuse open conn if your signature supports it)
        try:
            log_audit_event(auth.current_user['id'], 'analyze_provider_workload', 'appointments', 'analytics', conn=conn)
        except TypeError:
            log_audit_event(auth.current_user['id'], 'analyze_provider_workload', 'appointments', 'analytics')

    except Exception as e:
        print(f"Workload analysis error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        input("\nPress Enter to return...")



def show_appointment_utilization_stats(auth):
    """
    Console analytics for appointments with graceful fallbacks.
    Looks only at the 'appointments' table and auto-detects columns.
    """
    if hasattr(auth, "check_permission") and not auth.check_permission("view_health_analytics"):
        print("You don't have permission to view analytics.")
        return

    conn = get_connection()
    try:
        c = conn.cursor()

        # Ensure table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appointments'")
        if not c.fetchone():
            print("No 'appointments' table found. Nothing to analyze.")
            return

        # Introspect columns
        c.execute("PRAGMA table_info(appointments)")
        cols = [row[1] for row in c.fetchall()]

        VALID_STATUS_COLS = {"status", "appointment_status"}
        VALID_PROVIDER_COLS = {"provider_id", "practitioner_id", "staff_id"}
        VALID_DT_COLS = {
            "start_time", "scheduled_time", "appointment_datetime", "appointment_time",
            "appointment_date", "date", "datetime", "start_at", "created_at",
        }
        VALID_MODIFIERS = {"-30 day", "-7 day", "start of day"}

        status_col   = next((x for x in ("status", "appointment_status") if x in cols and x in VALID_STATUS_COLS), None)
        provider_col = next((x for x in ("provider_id", "practitioner_id", "staff_id") if x in cols and x in VALID_PROVIDER_COLS), None)
        dt_candidates = [x for x in (
            "start_time", "scheduled_time", "appointment_datetime", "appointment_time",
            "appointment_date", "date", "datetime", "start_at", "created_at"
        ) if x in cols and x in VALID_DT_COLS]
        dt_col = dt_candidates[0] if dt_candidates else None

        print("\n===== Appointment Utilization =====")

        # Windowed counts
        if dt_col:
            windows = [
                ("Last 30 days", "-30 day"),
                ("Last 7 days",  "-7 day"),
                ("Today",        "start of day"),
            ]
            for label, mod in windows:
                if mod not in VALID_MODIFIERS:
                    continue
                if mod == "start of day":
                    c.execute("SELECT COUNT(*) FROM appointments WHERE datetime([" + dt_col + "]) >= datetime('now','localtime','start of day')")
                else:
                    c.execute("SELECT COUNT(*) FROM appointments WHERE datetime([" + dt_col + "]) >= datetime('now','localtime','" + mod + "')")
                total = c.fetchone()[0]
                print(f"{label}: {total} appointments")
        else:
            c.execute("SELECT COUNT(*) FROM appointments")
            total = c.fetchone()[0]
            print(f"Total appointments: {total} (no datetime column detected; skipping time windows)")

        # Status breakdown
        if status_col:
            c.execute("SELECT [" + status_col + "], COUNT(*) FROM appointments GROUP BY [" + status_col + "] ORDER BY COUNT(*) DESC")
            rows = c.fetchall()
            if rows:
                print("\nBy status:")
                for s, n in rows:
                    print(f" - {s or 'UNKNOWN'}: {n}")
        else:
            print("\nStatus column not found; skipping status breakdown.")

        # Top providers (last 30d if datetime available)
        if provider_col:
            if dt_col:
                c.execute(
                    "SELECT [" + provider_col + "], COUNT(*) AS n"
                    " FROM appointments"
                    " WHERE datetime([" + dt_col + "]) >= datetime('now','localtime','-30 day')"
                    " GROUP BY [" + provider_col + "]"
                    " ORDER BY n DESC"
                    " LIMIT 5"
                )
            else:
                c.execute(
                    "SELECT [" + provider_col + "], COUNT(*) AS n"
                    " FROM appointments"
                    " GROUP BY [" + provider_col + "]"
                    " ORDER BY n DESC"
                    " LIMIT 5"
                )
            rows = c.fetchall()
            if rows:
                print("\nTop providers (by booked count):")
                for pid, n in rows:
                    print(f" - {pid}: {n}")
        else:
            print("\nProvider column not found; skipping provider breakdown.")

        # Hour-of-day and weekday distributions
        if dt_col:
            c.execute(
                "SELECT strftime('%H', datetime([" + dt_col + "])) AS hh, COUNT(*)"
                " FROM appointments"
                " WHERE [" + dt_col + "] IS NOT NULL"
                " GROUP BY hh"
                " ORDER BY hh"
            )
            hours = c.fetchall()
            if hours:
                print("\nBy hour of day:")
                for hh, n in hours:
                    print(f" {hh}:00 -> {n}")

            c.execute(
                "SELECT strftime('%w', datetime([" + dt_col + "])) AS dow, COUNT(*)"
                " FROM appointments"
                " WHERE [" + dt_col + "] IS NOT NULL"
                " GROUP BY dow"
                " ORDER BY dow"
            )
            dows = {'0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed', '4': 'Thu', '5': 'Fri', '6': 'Sat'}
            rows = c.fetchall()
            if rows:
                print("\nBy weekday:")
                for dow, n in rows:
                    label = dows.get(dow or '', dow or '?')
                    print(f" {label}: {n}")
        else:
            print("\nNo datetime column; skipping hour/weekday distributions.")

        # Audit (reuse conn if your signature supports it)
        try:
            log_audit_event(auth.current_user['id'], 'view_appointment_utilization', 'appointments', 'analytics', conn=conn)
        except TypeError:
            log_audit_event(auth.current_user['id'], 'view_appointment_utilization', 'appointments', 'analytics')

    except Exception as e:
        print(f"Analytics error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        input("\nPress Enter to return...")




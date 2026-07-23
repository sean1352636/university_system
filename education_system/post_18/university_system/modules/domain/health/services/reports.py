from __future__ import annotations

import logging

from education_system.post_18.university_system.modules.domain.health.services.audit import log_audit_event
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.core.i18n import get_text

logger = logging.getLogger(__name__)

def generate_student_health_summary(auth):
    """Summary for a single student: vaccinations, upcoming appts, latest vitals, recent records."""
    conn = get_connection()
    c = conn.cursor()
    try:
        sid = input(get_text("health.reports.enter_student_id")).strip()
        if not sid:
            print(get_text("health.reports.student_id_required"))
            return

        # Student name
        c.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (sid,))
        row = c.fetchone()
        name = f"{(row[0] or '').strip()} {(row[1] or '').strip()}".strip() if row else sid

        print("\n" + get_text("health.reports.student_summary_title", name=name, sid=sid))

        # Vaccinations
        c.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN verified=1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN adverse_reaction=1 THEN 1 ELSE 0 END)
            FROM vaccination_records WHERE student_id = ?
        """, (sid,))
        total, verified, adverse = c.fetchone()
        print(get_text("health.reports.vaccinations_summary", total=total or 0, verified=verified or 0, adverse=adverse or 0))

        # Upcoming appointments (next 30 days)
        # health_appointments schema: appointment_date TEXT, appointment_time TEXT, provider, status
        c.execute("""
            SELECT appointment_date, appointment_time, provider, status, appointment_type
            FROM health_appointments
            WHERE student_id = ?
              AND appointment_date IS NOT NULL
              AND date(appointment_date) >= date('now','localtime')
              AND date(appointment_date) <  date('now','localtime','+30 day')
            ORDER BY appointment_date, appointment_time
        """, (sid,))
        appts = c.fetchall()
        if appts:
            print("\n" + get_text("health.reports.upcoming_appointments_header"))
            for d, t, prov, status, atype in appts[:10]:
                t_disp = t or "--:--"
                print(get_text("health.reports.appointment_item", date=d, time=t_disp, provider=prov or get_text("common.unknown").upper(), atype=atype or "general", status=status or "scheduled"))
        else:
            print("\n" + get_text("health.reports.upcoming_appointments_none"))

        # Latest vitals
        c.execute("""
            SELECT measurement_date, blood_pressure_systolic, blood_pressure_diastolic, heart_rate, bmi, weight, height
            FROM vital_signs
            WHERE student_id = ?
            ORDER BY date(measurement_date) DESC, id DESC
            LIMIT 1
        """, (sid,))
        v = c.fetchone()
        if v:
            mdate, sys, dia, hr, bmi, w, h = v
            bp = f"{sys}/{dia}" if sys and dia else get_text("common.na")
            print("\n" + get_text("health.reports.latest_vitals_header"))
            print(get_text("health.reports.vitals_date", date=mdate or "-"))
            print(get_text("health.reports.vitals_bp_hr_bmi", bp=bp, hr=hr or "-", bmi=round(bmi, 1) if bmi else "-"))
            if w or h:
                print(get_text("health.reports.vitals_weight_height", weight=w or "-", height=h or "-"))
        else:
            print("\n" + get_text("health.reports.latest_vitals_none"))

        # Recent health records (last 90 days)
        c.execute("""
            SELECT record_type, COUNT(*)
            FROM health_records
            WHERE student_id = ? AND record_date IS NOT NULL
              AND date(record_date) >= date('now','localtime','-90 day')
            GROUP BY record_type
            ORDER BY COUNT(*) DESC
        """, (sid,))
        recs = c.fetchall()
        if recs:
            print("\n" + get_text("health.reports.recent_records_header"))
            for rtype, n in recs:
                print(get_text("health.reports.record_item", rtype=rtype or get_text("health.reports.unspecified"), count=n))
        else:
            print("\n" + get_text("health.reports.recent_records_none"))

        # Audit
        try:
            log_audit_event(auth.current_user['id'], 'generate_student_health_summary', 'student', sid)
        except TypeError:
            # in case signature differs elsewhere
            log_audit_event(auth.current_user['id'], 'generate_student_health_summary', 'student', sid)
    finally:
        try:
            conn.close()
        except Exception as e:
            logger.debug(f"Could not close database connection: {e}")
    input("\n" + get_text("health.reports.press_enter_return"))

def generate_vaccination_status_report(auth):
    """Vaccination coverage/verification/adverse reactions; optional filter by vaccine."""
    conn = get_connection()
    c = conn.cursor()
    try:
        vaccine = input(get_text("health.reports.filter_by_vaccine")).strip()

        where = ""
        params = ()
        if vaccine:
            where = "WHERE vaccine_name LIKE ?"
            params = (f"%{escape_like(vaccine)}%",)

        # Totals
        c.execute(
            "SELECT COUNT(*),"
            " SUM(CASE WHEN verified=1 THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN adverse_reaction=1 THEN 1 ELSE 0 END)"
            " FROM vaccination_records " + where,
            params)
        total, verified, adverse = c.fetchone()
        total = total or 0; verified = verified or 0; adverse = adverse or 0

        print("\n" + get_text("health.reports.vaccination_status_title"))
        if vaccine: print(get_text("health.reports.vaccine_filter", vaccine=vaccine))
        print(get_text("health.reports.vaccination_totals", total=total, verified=verified, adverse=adverse))

        # Expired / expiring soon
        c.execute(
            "SELECT COUNT(*) FROM vaccination_records "
            + ('WHERE' if not where else where + ' AND') +
            " (expiry_date IS NOT NULL AND date(expiry_date) < date('now','localtime'))",
            params)
        expired = c.fetchone()[0] or 0

        c.execute(
            "SELECT COUNT(*) FROM vaccination_records "
            + ('WHERE' if not where else where + ' AND') +
            " (expiry_date IS NOT NULL AND date(expiry_date) BETWEEN date('now','localtime') AND date('now','localtime','+30 day'))",
            params)
        expiring_30 = c.fetchone()[0] or 0

        print(get_text("health.reports.expired_expiring", expired=expired, expiring_30=expiring_30))

        # Top vaccines
        c.execute(
            "SELECT vaccine_name, COUNT(*) as n"
            " FROM vaccination_records " + where +
            " GROUP BY vaccine_name"
            " ORDER BY n DESC"
            " LIMIT 10",
            params)
        rows = c.fetchall()
        if rows:
            print("\n" + get_text("health.reports.top_vaccines_header"))
            for vname, n in rows:
                print(get_text("health.reports.vaccine_count_item", vname=vname or get_text("health.reports.unknown"), count=n))

        try:
            log_audit_event(auth.current_user['id'], 'generate_vaccination_status_report', 'vaccination_records', 'report')
        except TypeError:
            log_audit_event(auth.current_user['id'], 'generate_vaccination_status_report', 'vaccination_records', 'report')
    finally:
        try:
            conn.close()
        except Exception as e:
            logger.debug(f"Could not close database connection: {e}")
    input("\n" + get_text("health.reports.press_enter_return"))

def generate_appointment_schedule_report(auth):
    """Schedules/loads for a date range, grouped by provider and status."""
    conn = get_connection()
    c = conn.cursor()
    try:
        start = input("Start date (YYYY-MM-DD, default today): ").strip() or None
        end   = input("End date (YYYY-MM-DD, default +7 days): ").strip() or None
        if not start: start = None
        if not end:   end   = None

        print("\n===== Appointment Schedule Report =====")
        table = "health_appointments"  # this exists in your schema

        # Guard: if table absent
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not c.fetchone():
            print("No 'health_appointments' table found.")
            return

        # Group by provider/status in window
        where = "WHERE 1=1"
        params = []
        if start:
            where += " AND date(appointment_date) >= date(?)"; params.append(start)
        else:
            where += " AND date(appointment_date) >= date('now','localtime')"
        if end:
            where += " AND date(appointment_date) <= date(?)"; params.append(end)
        else:
            where += " AND date(appointment_date) <= date('now','localtime','+7 day')"

        c.execute(
            "SELECT provider, status, COUNT(*) AS n"
            " FROM [" + table + "] "
            + where +
            " GROUP BY provider, status"
            " ORDER BY provider, n DESC",
            tuple(params))
        rows = c.fetchall()
        if not rows:
            print("No appointments in the selected window.")
        else:
            current = None
            for prov, status, n in rows:
                if prov != current:
                    current = prov
                    print(f"\nProvider: {prov or 'UNKNOWN'}")
                print(f"  - {status or 'scheduled'}: {n}")

        try:
            log_audit_event(auth.current_user['id'], 'generate_appointment_schedule_report', 'health_appointments', f"{start or 'today'}..{end or '+7d'}")
        except TypeError:
            log_audit_event(auth.current_user['id'], 'generate_appointment_schedule_report', 'health_appointments', f"{start or 'today'}..{end or '+7d'}")
    finally:
        try:
            conn.close()
        except Exception as e:
            logger.debug(f"Could not close database connection: {e}")
    input("\nPress Enter to return...")

def generate_health_condition_analysis(auth):
    """Analyze health_records by record_type and trends over 90 days."""
    conn = get_connection()
    c = conn.cursor()
    try:
        # Guard: table
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='health_records'")
        if not c.fetchone():
            print("No 'health_records' table found.")
            return

        print("\n===== Health Condition Analysis =====")

        # Counts by type
        c.execute("""
            SELECT record_type, COUNT(*) AS n
            FROM health_records
            GROUP BY record_type
            ORDER BY n DESC
        """)
        rows = c.fetchall()
        if rows:
            print("\nBy record type:")
            for rtype, n in rows[:20]:
                print(f" - {rtype or 'unspecified'}: {n}")
        else:
            print("\nNo health records found.")

        # 90-day trend
        c.execute("""
            SELECT strftime('%Y-%m', date(record_date)) AS ym, COUNT(*) AS n
            FROM health_records
            WHERE record_date IS NOT NULL
              AND date(record_date) >= date('now','localtime','-180 day')
            GROUP BY ym
            ORDER BY ym
        """)
        trend = c.fetchall()
        if trend:
            print("\nTrend (last 6 months):")
            for ym, n in trend:
                print(f" {ym}: {n}")

        try:
            log_audit_event(auth.current_user['id'], 'generate_health_condition_analysis', 'health_records', 'summary')
        except TypeError:
            log_audit_event(auth.current_user['id'], 'generate_health_condition_analysis', 'health_records', 'summary')
    finally:
        try:
            conn.close()
        except Exception as e:
            logger.debug(f"Could not close database connection: {e}")
    input("\nPress Enter to return...")

def generate_provider_performance_report(auth):
    """Simple provider performance: 30d totals, completions, cancellations, avg/day."""
    conn = get_connection()
    c = conn.cursor()
    try:
        print("\n===== Provider Performance Report (last 30 days) =====")
        table = "health_appointments"
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not c.fetchone():
            print("No 'health_appointments' table found.")
            return

        # Totals per provider
        c.execute(
            "SELECT provider,"
            " COUNT(*) AS total,"
            " SUM(CASE WHEN status IN ('completed','done') THEN 1 ELSE 0 END) AS completed,"
            " SUM(CASE WHEN status IN ('cancelled','canceled') THEN 1 ELSE 0 END) AS cancelled"
            " FROM [" + table + "]"
            " WHERE date(appointment_date) >= date('now','localtime','-30 day')"
            " GROUP BY provider"
            " ORDER BY total DESC"
        )
        rows = c.fetchall()
        if not rows:
            print("No appointments in last 30 days.")
            return

        for prov, total, comp, canc in rows:
            total = total or 0; comp = comp or 0; canc = canc or 0
            avg_per_day = round(total / 30.0, 2)
            completion_rate = f"{(comp/total*100):.1f}%" if total else "n/a"
            cancel_rate = f"{(canc/total*100):.1f}%" if total else "n/a"
            print(f"\nProvider: {prov or 'UNKNOWN'}")
            print(f" - Total: {total} | Avg/day: {avg_per_day}")
            print(f" - Completed: {comp} ({completion_rate}) | Cancelled: {canc} ({cancel_rate})")

        try:
            log_audit_event(auth.current_user['id'], 'generate_provider_performance_report', 'health_appointments', '30d')
        except TypeError:
            log_audit_event(auth.current_user['id'], 'generate_provider_performance_report', 'health_appointments', '30d')
    finally:
        try:
            conn.close()
        except Exception as e:
            logger.debug(f"Could not close database connection: {e}")
    input("\nPress Enter to return...")

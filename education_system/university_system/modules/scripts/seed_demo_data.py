"""Seed Data Population Script.

Populates empty tables with realistic demo/test data for:
  - Attendance (sessions, records, analytics, alerts, policies, predictions, gamification)
  - Financial Aid (student financial aid, scholarships, payment plans, disbursements)
  - Housing/Accommodation (inspections, inventory, maintenance, assignments)
  - Alumni (profiles, donations, achievements, events, registrations)
  - Health Services (records, appointments, vaccinations, conditions, prescriptions,
    vitals, lab results, campaigns, metrics)

Usage:
    python -m university_system.modules.scripts.seed_demo_data
"""

import random
from education_system.university_system.infrastructure.database.db import sqlite3
import sys
from datetime import datetime, timedelta

# Attempt to resolve the DB path from the project's central config.
try:
    from education_system.university_system.modules.shared.constants import paths
    DB_PATH = str(paths.DEFAULT_DB_PATH)
except Exception:
    DB_PATH = "university_system/data/db_files/student_records.db"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rand_date(start_str: str, end_str: str) -> str:
    """Return a random date string between two YYYY-MM-DD dates."""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    delta = (end - start).days
    if delta <= 0:
        return start_str
    return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")

def _rand_datetime(start_str: str, end_str: str) -> str:
    """Return a random datetime string."""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    delta = int((end - start).total_seconds())
    if delta <= 0:
        return start_str + " 09:00:00"
    return (start + timedelta(seconds=random.randint(0, delta))).strftime("%Y-%m-%d %H:%M:%S")

def _rand_time(start_hour: int = 8, end_hour: int = 18) -> str:
    h = random.randint(start_hour, end_hour)
    m = random.choice([0, 15, 30, 45])
    return f"{h:02d}:{m:02d}"

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Reference data
STUDENT_IDS = ["S12345", "9310648", "6845289"]
MODULE_CODES = [
    "CIS0001", "CIS0002", "CIS1001", "CIS1002", "CIS1003",
    "CIS1004", "CIS2001", "CIS2002", "CIS2003", "CIS2004",
    "CIS3001", "CIS3002", "CIS3003", "CIS3004",
]
BUILDING_IDS = ["B001", "B002", "B003", "B004"]
PROVIDERS = ["Dr. Smith", "Dr. Patel", "Dr. Johnson", "Dr. Williams", "Nurse Roberts"]
FIRST_NAMES = [
    "James", "Olivia", "Liam", "Emma", "Noah", "Ava", "Elijah", "Sophia",
    "Lucas", "Isabella", "Mason", "Mia", "Ethan", "Charlotte", "Aiden",
]
LAST_NAMES = [
    "Thompson", "Garcia", "Wilson", "Anderson", "Taylor", "Thomas",
    "Jackson", "White", "Harris", "Martin", "Lee", "Clark", "Lewis",
]

# ---------------------------------------------------------------------------
# Seeding Functions
# ---------------------------------------------------------------------------

def seed_attendance(cursor: sqlite3.Cursor) -> int:
    """Populate attendance-related tables. Returns rows inserted."""
    count = 0
    now = _now()

    # --- attendance_sessions ---
    sessions = []
    for i in range(1, 31):
        mc = random.choice(MODULE_CODES)
        d = _rand_date("2025-09-01", "2026-02-10")
        st = _rand_time(9, 16)
        et_h = int(st.split(":")[0]) + 1
        et = f"{et_h:02d}:{st.split(':')[1]}"
        sid = f"SESS-{i:04d}"
        sessions.append((
            sid, mc, d, st, et, f"Room {random.randint(100, 400)}",
            54.57, -1.23, 50, f"QR-{sid}", None,
            random.choice(["lecture", "lab", "tutorial", "seminar"]),
            random.randint(20, 60), "staff", now, "completed",
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO attendance_sessions "
        "(session_id, module_code, date, start_time, end_time, location_name, "
        "latitude, longitude, geofence_radius, qr_code_data, qr_code_expires, "
        "session_type, max_capacity, created_by, created_at, status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", sessions
    )
    count += len(sessions)

    # --- attendance_records ---
    records = []
    statuses = ["present", "present", "present", "present", "late", "absent", "excused"]
    methods = ["qr_code", "manual", "facial_recognition", "beacon"]
    for sess in sessions:
        sess_id = sess[0]
        mc = sess[1]
        d = sess[2]
        for sid in STUDENT_IDS:
            status = random.choice(statuses)
            records.append((
                sid, mc, d, status, None,
                "staff", now, random.choice(methods),
                None, "127.0.0.1", sess_id, None, "verified",
            ))
    cursor.executemany(
        "INSERT OR IGNORE INTO attendance_records "
        "(student_id, module_code, date, status, notes, recorded_by, recorded_at, "
        "check_in_method, location_data, ip_address, session_id, makeup_for_date, verification_status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", records
    )
    count += len(records)

    # --- attendance_analytics ---
    analytics = []
    for sid in STUDENT_IDS:
        pct = round(random.uniform(65.0, 99.0), 1)
        consec = random.randint(0, 3)
        analytics.append((sid, pct, consec))
    cursor.executemany(
        "INSERT OR IGNORE INTO attendance_analytics "
        "(student_id, attendance_percentage, consecutive_absences) VALUES (?,?,?)",
        analytics,
    )
    count += len(analytics)

    # --- attendance_alerts ---
    alerts = []
    for i in range(1, 9):
        sid = random.choice(STUDENT_IDS)
        mc = random.choice(MODULE_CODES)
        alerts.append((
            f"ALT-{i:04d}", sid, mc,
            random.choice(["low_attendance", "consecutive_absence", "at_risk"]),
            random.choice(["low", "medium", "high"]),
            f"Attendance alert for student {sid} in {mc}",
            now, now, None, random.choice(["sent", "acknowledged"]),
            f"{sid}@example.com", None,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO attendance_alerts "
        "(alert_id, student_id, module_code, alert_type, severity, message, "
        "created_at, sent_at, acknowledged_at, status, recipient_email, recipient_phone) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", alerts
    )
    count += len(alerts)

    # --- attendance_policies ---
    policies = []
    for i, mc in enumerate(MODULE_CODES[:5], 1):
        policies.append((
            f"POL-{i:04d}", f"Attendance Policy for {mc}",
            "Standard attendance policy requiring minimum attendance.",
            mc, "CS", 75.0, 3, 10, 1, 50.0, 7,
            "2025-09-01", "2026-06-30", "admin", now, "active",
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO attendance_policies "
        "(policy_id, name, description, module_code, course, min_attendance_percentage, "
        "max_consecutive_absences, late_tolerance_minutes, makeup_allowed, "
        "auto_fail_threshold, grace_period_days, effective_from, effective_until, "
        "created_by, created_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        policies,
    )
    count += len(policies)

    # --- attendance_predictions ---
    preds = []
    for sid in STUDENT_IDS:
        for mc in random.sample(MODULE_CODES, 4):
            preds.append((
                sid, mc, _rand_date("2026-02-01", "2026-02-10"),
                round(random.uniform(60.0, 98.0), 1),
                random.choice(["low", "medium", "high"]),
                round(random.uniform(0.6, 0.95), 2),
                '{"gpa": 3.2, "prior_attendance": 85}',
                "Maintain current study habits.",
                "v1.0", now,
            ))
    cursor.executemany(
        "INSERT OR IGNORE INTO attendance_predictions "
        "(student_id, module_code, prediction_date, predicted_attendance_rate, "
        "risk_level, confidence_score, factors, recommendations, model_version, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", preds
    )
    count += len(preds)

    # --- attendance_gamification ---
    gam = []
    for sid in STUDENT_IDS:
        gam.append((
            sid, random.randint(50, 500), random.randint(1, 10),
            '["early_bird","consistent"]', '["10_day_streak"]',
            random.randint(1, 30), random.randint(5, 45),
            _rand_date("2026-01-15", "2026-02-10"),
            random.randint(0, 5), now, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO attendance_gamification "
        "(student_id, points, level, badges, achievements, streak_days, "
        "best_streak, last_attendance_date, total_rewards, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", gam
    )
    count += len(gam)

    return count

def seed_financial_aid(cursor: sqlite3.Cursor) -> int:
    """Populate financial aid tables. Returns rows inserted."""
    count = 0
    now = _now()

    # --- student_financial_aid ---
    aid_rows = []
    for sid in STUDENT_IDS:
        for aid_type in random.sample(range(6, 17), 2):
            amount = round(random.uniform(500, 5000), 2)
            disbursed = round(amount * random.uniform(0.0, 1.0), 2)
            aid_rows.append((
                sid, aid_type, amount, disbursed, round(amount - disbursed, 2),
                "GBP", random.choice(["approved", "pending", "disbursed"]),
                _rand_date("2025-08-01", "2025-10-01"),
                _rand_date("2025-10-01", "2025-11-01"),
                "quarterly", None, None, None, "admin",
                f"Financial aid for {sid}", now, now,
            ))
    cursor.executemany(
        "INSERT OR IGNORE INTO student_financial_aid "
        "(student_id, aid_type_id, awarded_amount, disbursed_amount, remaining_amount, "
        "currency, status, application_date, approval_date, disbursement_schedule, "
        "repayment_start_date, monthly_payment_amount, total_repaid, approved_by, "
        "notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        aid_rows,
    )
    count += len(aid_rows)

    # --- student_scholarships ---
    schol_rows = []
    scholarship_ids = list(range(5, 16))
    for sid in STUDENT_IDS:
        sch_id = random.choice(scholarship_ids)
        amt = round(random.uniform(500, 3000), 2)
        schol_rows.append((
            sid, sch_id, amt,
            random.choice(["awarded", "pending", "accepted"]),
            _rand_date("2025-09-01", "2025-12-01"), now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO student_scholarships "
        "(student_id, scholarship_id, amount, status, awarded_date, created_at) "
        "VALUES (?,?,?,?,?,?)", schol_rows
    )
    count += len(schol_rows)

    # --- scholarship_applications ---
    app_rows = []
    for i, sid in enumerate(STUDENT_IDS, 1):
        sch_id = random.choice(scholarship_ids)
        app_rows.append((
            sid, sch_id, _rand_date("2025-07-01", "2025-09-01"),
            random.choice(["submitted", "under_review", "approved", "rejected"]),
            "My passion for computer science drives me to excel...",
            None, "admin", _rand_date("2025-09-15", "2025-10-15"),
            "Strong candidate.", _rand_date("2025-10-15", "2025-11-01"),
            round(random.uniform(500, 3000), 2),
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO scholarship_applications "
        "(student_id, scholarship_id, application_date, status, essay, "
        "additional_documents, reviewer_id, review_date, review_notes, "
        "decision_date, award_amount) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        app_rows,
    )
    count += len(app_rows)

    # --- student_payment_plans ---
    plan_rows = []
    for sid in STUDENT_IDS:
        total = round(random.uniform(3000, 9000), 2)
        remaining = round(total * random.uniform(0.3, 0.8), 2)
        plan_rows.append((
            sid, random.randint(1, 5), total, remaining, "GBP",
            random.choice(["active", "completed"]),
            _rand_date("2025-09-01", "2025-10-01"),
            _rand_date("2026-01-01", "2026-03-01"),
            1, 0, None, None, now, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO student_payment_plans "
        "(student_id, template_id, total_amount, remaining_amount, currency, "
        "status, start_date, next_due_date, setup_fee_paid, auto_payment_enabled, "
        "payment_method_id, notes, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", plan_rows
    )
    count += len(plan_rows)

    return count

def seed_housing(cursor: sqlite3.Cursor) -> int:
    """Populate housing tables. Returns rows inserted."""
    count = 0
    now = _now()

    # Get some room IDs
    rooms = cursor.execute("SELECT room_id, building_id FROM housing_rooms LIMIT 20").fetchall()
    if not rooms:
        rooms = [("B001-101", "B001"), ("B001-102", "B001"), ("B002-201", "B002")]

    # --- housing_assignments ---
    assign_rows = []
    for i, sid in enumerate(STUDENT_IDS):
        room = rooms[i % len(rooms)]
        assign_rows.append((
            f"HA-{i + 1:04d}", f"APP-{i + 1:04d}", sid, room[0],
            "2025-09-01", "2026-06-30", None,
            f"CTR-{random.randint(10000, 99999)}",
            round(random.uniform(400, 1200), 2),
            "active", "admin", now, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO housing_assignments "
        "(assignment_id, application_id, student_id, room_id, move_in_date, "
        "planned_move_out_date, actual_move_out_date, contract_number, "
        "monthly_rent, status, assigned_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", assign_rows
    )
    count += len(assign_rows)

    # --- housing_inspections ---
    insp_rows = []
    for i in range(1, 11):
        room = random.choice(rooms)
        insp_rows.append((
            f"INSP-{i:04d}", room[0],
            random.choice(["Maintenance Staff", "Housing Officer", "Fire Safety"]),
            _rand_date("2025-09-01", "2026-02-10"),
            random.choice(["routine", "safety", "move_in", "move_out"]),
            random.choice(["passed", "minor_issues", "action_required"]),
            "All fixtures in working order." if i % 3 != 0 else "Minor wall damage noted.",
            "None" if i % 3 != 0 else "Repair wall damage",
            _rand_date("2026-02-15", "2026-03-15") if i % 3 == 0 else None,
            now, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO housing_inspections "
        "(inspection_id, room_id, inspector, inspection_date, inspection_type, "
        "status, findings, action_required, follow_up_date, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", insp_rows
    )
    count += len(insp_rows)

    # --- housing_inventory ---
    inv_rows = []
    items = [
        ("Single Bed", "furniture"), ("Desk", "furniture"), ("Chair", "furniture"),
        ("Wardrobe", "furniture"), ("Desk Lamp", "electrical"), ("Mattress", "bedding"),
        ("Curtains", "furnishing"), ("Smoke Detector", "safety"), ("Fire Extinguisher", "safety"),
    ]
    for i, room in enumerate(rooms[:8]):
        item = items[i % len(items)]
        inv_rows.append((
            f"INV-{i + 1:04d}", room[0], item[0], item[1],
            random.choice(["good", "fair", "new"]),
            _rand_date("2023-01-01", "2025-09-01"),
            "in_use", None, now, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO housing_inventory "
        "(item_id, room_id, item_name, item_type, condition, "
        "acquisition_date, status, notes, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", inv_rows
    )
    count += len(inv_rows)

    # --- housing_maintenance_requests ---
    maint_rows = []
    issues = [
        ("plumbing", "Leaking faucet in bathroom"),
        ("electrical", "Light bulb needs replacing"),
        ("furniture", "Desk drawer broken"),
        ("heating", "Radiator not working"),
        ("pest_control", "Possible pest sighting"),
        ("cleaning", "Deep clean requested"),
    ]
    for i in range(1, 9):
        sid = random.choice(STUDENT_IDS)
        room = random.choice(rooms)
        issue = random.choice(issues)
        maint_rows.append((
            f"MR-{i:04d}", room[0], sid,
            _rand_date("2025-10-01", "2026-02-10"),
            issue[0], issue[1],
            random.choice(["low", "medium", "high", "urgent"]),
            random.choice(["open", "in_progress", "completed", "scheduled"]),
            "Maintenance Team",
            _rand_date("2026-02-11", "2026-02-28"),
            None, None, now, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO housing_maintenance_requests "
        "(request_id, room_id, student_id, request_date, issue_type, description, "
        "priority, status, assigned_to, scheduled_date, completion_date, "
        "feedback, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        maint_rows,
    )
    count += len(maint_rows)

    return count

def seed_alumni(cursor: sqlite3.Cursor) -> int:
    """Populate alumni tables. Returns rows inserted."""
    count = 0
    now = _now()

    # --- alumni ---
    alumni_rows = []
    employers = [
        "Google", "Microsoft", "Amazon", "Meta", "Apple",
        "IBM", "Deloitte", "PwC", "NHS Digital", "BT Group",
    ]
    industries = [
        "Technology", "Finance", "Healthcare", "Consulting", "Education",
    ]
    degrees = [
        "BSc Computer Science", "BSc Software Engineering", "MSc Data Science",
        "BSc Information Technology", "MSc Cybersecurity",
    ]
    for i in range(1, 16):
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        grad_year = random.randint(2018, 2025)
        alumni_rows.append((
            f"ALM-{i:04d}", f"STU-{1000 + i}",
            f"{fn.lower()}.{ln.lower()}@alumni.university.ac.uk",
            random.choice(["Mr", "Ms", "Dr"]),
            fn, None, ln,
            random.choice(["male", "female"]),
            _rand_date("1990-01-01", "2002-12-31"),
            grad_year, random.choice(degrees),
            random.choice(employers),
            random.choice(["Software Engineer", "Data Analyst", "Product Manager",
                          "Consultant", "Systems Architect", "Research Scientist"]),
            random.choice(industries),
            f"{random.randint(1, 200)} {random.choice(['High St', 'Park Rd', 'Station Ln'])}",
            random.choice(["London", "Manchester", "Edinburgh", "Bristol", "Leeds"]),
            "United Kingdom",
            f"+44 7{random.randint(100, 999)} {random.randint(100000, 999999)}",
            f"https://linkedin.com/in/{fn.lower()}{ln.lower()}{grad_year}",
            _rand_date("2020-01-01", "2025-12-01"),
            1 if i % 3 == 0 else 0,  # is_donor
            1 if i % 4 == 0 else 0,  # is_mentor
            0,  # is_board_member
            None, f"Graduated in {grad_year} with {random.choice(degrees)}.",
            "Python,Java,SQL,Cloud", None,
            random.choice([1, 2, 3]),  # privacy_level
            random.randint(10, 100),  # engagement_score
            _rand_date("2025-06-01", "2026-02-10"),
            None, 0,  # is_ambassador
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO alumni "
        "(alumni_id, student_id, email_address, title, first_name, middle_name, "
        "last_name, gender, dob, graduation_year, degree_earned, current_employer, "
        "job_title, industry, address, city, country, phone, linkedin_url, "
        "date_registered, is_donor, is_mentor, is_board_member, profile_photo, bio, "
        "skills, achievements, privacy_level, engagement_score, last_activity, "
        "social_media_links, is_ambassador) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        alumni_rows,
    )
    count += len(alumni_rows)

    # --- alumni_profiles ---
    profile_rows = []
    for i, alum in enumerate(alumni_rows, 1):
        profile_rows.append((
            alum[1],  # student_id
            alum[9],  # graduation_year
            alum[10],  # degree_earned
            "Computer Science",
            alum[11],  # employer
            alum[12],  # job_title
            alum[13],  # industry
            random.choice(["London, UK", "Manchester, UK", "Edinburgh, UK"]),
            alum[18],  # linkedin
            None,
            alum[24],  # bio
            1 if i % 4 == 0 else 0,
            1 if i % 5 == 0 else 0,
            "public", now, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO alumni_profiles "
        "(student_id, graduation_year, degree_earned, major, current_employer, "
        "current_position, current_industry, current_location, linkedin_url, "
        "personal_website, biography, willing_to_mentor, willing_to_recruit, "
        "privacy_level, profile_updated_at, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", profile_rows
    )
    count += len(profile_rows)

    # --- alumni_donations ---
    donation_rows = []
    for i in range(1, 11):
        donation_rows.append((
            random.randint(1, 15),  # alumni_id (integer FK)
            round(random.uniform(25, 5000), 2),
            _rand_date("2024-01-01", "2026-02-10"),
            random.choice(["one_time", "recurring", "major_gift"]),
            random.choice(["general_fund", "scholarship_fund", "research", "library"]),
            None,
            random.choice(["credit_card", "bank_transfer", "paypal"]),
            1 if i % 3 == 0 else 0,
            "monthly" if i % 3 == 0 else None,
            1, 1,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO alumni_donations "
        "(alumni_id, donation_amount, donation_date, donation_type, "
        "fund_designation, campaign_id, payment_method, is_recurring, "
        "recurrence_frequency, tax_receipt_sent, acknowledgment_sent) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", donation_rows
    )
    count += len(donation_rows)

    # --- alumni_achievements ---
    ach_rows = []
    achievements = [
        ("Published Research Paper", "Published in IEEE journal on AI security."),
        ("Industry Award", "Received Best Newcomer Award at TechCon 2024."),
        ("Patent Filed", "Filed patent for novel data compression algorithm."),
        ("Startup Founded", "Co-founded a health-tech startup."),
        ("Community Service", "Led coding workshops for underprivileged youth."),
        ("PhD Completed", "Completed PhD in Machine Learning."),
    ]
    for i, (title, desc) in enumerate(achievements):
        ach_rows.append((
            f"ALM-{random.randint(1, 15):04d}",
            title, desc,
            _rand_date("2022-01-01", "2025-12-01"),
            random.choice(["academic", "professional", "community", "innovation"]),
            random.choice(["verified", "pending"]),
            "admin",
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO alumni_achievements "
        "(alumni_id, achievement_title, achievement_description, achievement_date, "
        "category, verification_status, verified_by) VALUES (?,?,?,?,?,?,?)",
        ach_rows,
    )
    count += len(ach_rows)

    # --- unified_events (alumni source_type) ---
    event_rows = []
    events = [
        ("Annual Alumni Gala", "social", "Grand Hall, University Campus"),
        ("Tech Industry Networking Night", "networking", "Innovation Centre"),
        ("Class of 2020 Reunion", "reunion", "Student Union Building"),
        ("Career Mentorship Workshop", "workshop", "Online"),
        ("Homecoming Weekend", "social", "University Stadium"),
        ("Alumni Research Showcase", "academic", "Science Building"),
    ]
    for i, (name, etype, loc) in enumerate(events, 1):
        d = _rand_date("2026-03-01", "2026-09-30")
        event_rows.append((
            name, d, loc,
            f"Annual {name} event for alumni and current students.",
            1, random.randint(50, 300),
            round(random.uniform(0, 50), 2),
            1 if i % 2 == 0 else 0,
            etype,
            "https://meet.uni.ac.uk/event" if loc == "Online" else None,
            None, "admin", now,
            _rand_date("2026-02-01", d),
            1 if i > 3 else 0,
            "alumni",
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO unified_events "
        "(title, start_datetime, location, description, "
        "registration_required, max_capacity, event_fee, payment_required, "
        "event_type, virtual_link, qr_code_path, created_by, created_date, "
        "registration_deadline, waitlist_enabled, source_type) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", event_rows
    )
    count += len(event_rows)

    # --- alumni_event_registrations ---
    reg_rows = []
    for i in range(1, 13):
        reg_rows.append((
            random.randint(1, len(events)),
            random.randint(1, 15),
            random.randint(0, 2),
            _rand_date("2026-02-01", "2026-03-01"),
            random.choice(["paid", "pending", "free"]),
            None,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO unified_event_registrations "
        "(event_id, user_id, num_guests, registration_date, payment_status, attendance_status, user_type) "
        "VALUES (?,?,?,?,?,?,?)", [(r[0], str(r[1]), r[2], r[3], r[4], 'attended' if r[5] else 'registered', 'alumni') for r in reg_rows]
    )
    count += len(reg_rows)

    return count

def seed_health(cursor: sqlite3.Cursor) -> int:
    """Populate health service tables. Returns rows inserted."""
    count = 0
    now = _now()

    # --- health_records ---
    hr_rows = []
    record_types = ["checkup", "consultation", "emergency", "follow_up", "screening"]
    for sid in STUDENT_IDS:
        for j in range(3):
            hr_rows.append((
                sid, random.choice(record_types),
                _rand_date("2025-09-01", "2026-02-10"),
                f"Routine {random.choice(record_types)} visit.",
                random.choice(PROVIDERS), 0, now, None,
            ))
    cursor.executemany(
        "INSERT OR IGNORE INTO health_records "
        "(student_id, record_type, record_date, description, provider, "
        "confidential, created_at, encrypted_data) VALUES (?,?,?,?,?,?,?,?)",
        hr_rows,
    )
    count += len(hr_rows)

    # --- health_appointments ---
    appt_rows = []
    appt_types = ["general", "dental", "mental_health", "physiotherapy", "vaccination"]
    for sid in STUDENT_IDS:
        for j in range(2):
            appt_rows.append((
                sid, random.choice(appt_types),
                _rand_date("2026-02-01", "2026-04-30"),
                _rand_time(9, 16),
                random.choice(PROVIDERS),
                random.choice(["Annual checkup", "Follow-up", "New complaint", "Vaccination"]),
                random.choice(["scheduled", "completed", "cancelled"]),
                None, now,
            ))
    cursor.executemany(
        "INSERT OR IGNORE INTO health_appointments "
        "(student_id, appointment_type, appointment_date, appointment_time, "
        "provider, reason, status, notes, scheduled_at) VALUES (?,?,?,?,?,?,?,?,?)",
        appt_rows,
    )
    count += len(appt_rows)

    # --- vaccination_records ---
    vacc_rows = []
    vaccines = [
        ("COVID-19 Booster", "Pfizer-BioNTech"), ("Influenza", "Sanofi Pasteur"),
        ("MMR", "Merck"), ("Meningitis ACWY", "GlaxoSmithKline"),
        ("Hepatitis B", "GlaxoSmithKline"), ("Tetanus/Diphtheria", "Sanofi Pasteur"),
    ]
    for sid in STUDENT_IDS:
        for vacc, mfr in random.sample(vaccines, 3):
            admin_date = _rand_date("2024-01-01", "2026-01-15")
            vacc_rows.append((
                sid, vacc, admin_date,
                _rand_date("2027-01-01", "2030-12-31"),
                f"LOT-{random.randint(10000, 99999)}", mfr,
                random.choice(PROVIDERS),
                "University Health Centre", 0, None, 1,
                "admin", _rand_date(admin_date, "2026-02-10"), now,
            ))
    cursor.executemany(
        "INSERT OR IGNORE INTO vaccination_records "
        "(student_id, vaccine_name, administered_date, expiry_date, lot_number, "
        "manufacturer, administered_by, location, adverse_reaction, "
        "reaction_description, verified, verified_by, verified_date, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vacc_rows
    )
    count += len(vacc_rows)

    # --- medical_conditions ---
    cond_rows = []
    conditions = [
        ("Asthma", "J45.9", "mild"), ("Migraine", "G43.9", "moderate"),
        ("Eczema", "L30.9", "mild"), ("Anxiety Disorder", "F41.9", "moderate"),
        ("Seasonal Allergies", "J30.2", "mild"),
    ]
    for sid in STUDENT_IDS:
        cond = random.choice(conditions)
        cond_rows.append((
            sid, cond[0], cond[1], cond[2],
            _rand_date("2020-01-01", "2025-06-01"),
            "active", random.choice(PROVIDERS),
            f"Diagnosed with {cond[0]}. Currently managed.", now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO medical_conditions "
        "(student_id, condition_name, icd_code, severity, diagnosed_date, "
        "status, provider, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        cond_rows,
    )
    count += len(cond_rows)

    # --- prescriptions ---
    rx_rows = []
    medications = [
        ("Salbutamol Inhaler", "2 puffs", "as needed"),
        ("Cetirizine 10mg", "1 tablet", "once daily"),
        ("Ibuprofen 400mg", "1 tablet", "three times daily"),
        ("Amoxicillin 500mg", "1 capsule", "three times daily for 7 days"),
    ]
    for sid in STUDENT_IDS:
        med = random.choice(medications)
        start = _rand_date("2025-10-01", "2026-02-01")
        rx_rows.append((
            sid, med[0], med[1], med[2],
            start, start,
            _rand_date("2026-03-01", "2026-06-30"),
            random.choice(PROVIDERS),
            "University Pharmacy",
            random.choice(["active", "completed"]),
            None, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO prescriptions "
        "(student_id, medication_name, dosage, frequency, prescribed_date, "
        "start_date, end_date, prescriber, pharmacy, status, notes, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rx_rows
    )
    count += len(rx_rows)

    # --- vital_signs ---
    vs_rows = []
    for sid in STUDENT_IDS:
        for j in range(3):
            weight = round(random.uniform(55, 95), 1)
            height = round(random.uniform(1.55, 1.95), 2)
            bmi = round(weight / (height ** 2), 1)
            vs_rows.append((
                sid, _rand_date("2025-09-01", "2026-02-10"),
                random.randint(110, 135), random.randint(65, 85),
                random.randint(58, 90), round(random.uniform(36.2, 37.2), 1),
                weight, height, bmi,
                random.choice(PROVIDERS), None, now,
            ))
    cursor.executemany(
        "INSERT OR IGNORE INTO vital_signs "
        "(student_id, measurement_date, blood_pressure_systolic, "
        "blood_pressure_diastolic, heart_rate, temperature, weight, "
        "height, bmi, recorded_by, notes, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", vs_rows
    )
    count += len(vs_rows)

    # --- lab_results ---
    lab_rows = []
    tests = [
        ("CBC", "CBC-001", "Normal", "4.5-11.0", "10^9/L"),
        ("Iron Studies", "IRON-01", "32", "12-150", "ng/mL"),
        ("Vitamin D", "VITD-01", "45", "30-100", "ng/mL"),
        ("Cholesterol", "CHOL-01", "185", "<200", "mg/dL"),
    ]
    for sid in STUDENT_IDS:
        test = random.choice(tests)
        ordered = _rand_date("2025-10-01", "2026-01-15")
        collected = _rand_date(ordered, "2026-01-20")
        lab_rows.append((
            sid, test[0], test[1], test[2], test[3], test[4],
            "final", ordered, collected,
            _rand_date(collected, "2026-02-01"),
            random.choice(PROVIDERS), "University Lab",
            "normal", now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO lab_results "
        "(student_id, test_name, test_code, result_value, reference_range, "
        "units, status, ordered_date, collected_date, resulted_date, "
        "ordering_provider, lab_name, abnormal_flag, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", lab_rows
    )
    count += len(lab_rows)

    # --- health_campaigns ---
    camp_rows = [
        ("Flu Vaccination Drive", "vaccination", "2026-01-15", "2026-02-28",
         "all_students", "Annual flu vaccination campaign for students and staff.",
         "Vaccinate 80% of student population.", "active", 5000.0, "admin", now),
        ("Mental Health Awareness Week", "awareness", "2026-03-10", "2026-03-16",
         "all_students", "Week-long event promoting mental health resources.",
         "Increase counselling sign-ups by 20%.", "planned", 2000.0, "admin", now),
        ("Sexual Health Screening", "screening", "2026-02-01", "2026-04-30",
         "all_students", "Free confidential screening available at health centre.",
         "Screen 500 students.", "active", 3000.0, "admin", now),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO health_campaigns "
        "(campaign_name, campaign_type, start_date, end_date, target_population, "
        "description, goals, status, budget, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", camp_rows
    )
    count += len(camp_rows)

    # --- health_metrics ---
    metric_rows = []
    metrics = [
        ("appointment_utilization", 78.5, "service_usage", "appointments"),
        ("vaccination_coverage", 62.3, "vaccination", "flu"),
        ("mental_health_referrals", 45, "mental_health", "counselling"),
        ("average_wait_time_minutes", 12.5, "service_quality", "appointments"),
        ("patient_satisfaction_score", 4.2, "service_quality", "feedback"),
        ("emergency_visits_per_month", 8, "service_usage", "emergency"),
    ]
    for name, value, cat, sub in metrics:
        metric_rows.append((
            name, value, _rand_date("2026-01-01", "2026-02-10"),
            cat, sub, None, now,
        ))
    cursor.executemany(
        "INSERT OR IGNORE INTO health_metrics "
        "(metric_name, metric_value, measurement_date, category, "
        "subcategory, metadata, calculated_at) VALUES (?,?,?,?,?,?,?)",
        metric_rows,
    )
    count += len(metric_rows)

    return count

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed_s12345_modules(cursor: sqlite3.Cursor) -> int:
    """Enrol demo student S12345 (course=CS) in 2 compulsory + 2 optional + 2 CS modules.

    Idempotent — uses INSERT OR IGNORE on (student_id, module_code).
    Assumes the module catalog has been seeded by Alembic migration d1bde3fa4179.
    """
    enrolments = [
        ("CIS0001", "python programming", "compulsory"),
        ("CIS0002", "data structures and algorithms", "compulsory"),
        ("CIS1001", "Computational Thinking", "optional"),
        ("CIS1002", "Design Patterns", "optional"),
        ("CIS2001", "software quality assurance principles", "course"),
        ("CIS2002", "software reliabilities", "course"),
    ]

    cursor.execute(
        "UPDATE students SET course = 'CS' "
        "WHERE student_id = 'S12345' AND (course IS NULL OR course = '')"
    )
    inserted = 0
    for code, name, mtype in enrolments:
        cursor.execute(
            "INSERT OR IGNORE INTO student_modules "
            "(student_id, module_code, module_id, module_name, module_type, status, enrollment_date) "
            "VALUES ('S12345', ?, ?, ?, ?, 'enrolled', date('now'))",
            (code, code, name, mtype),
        )
        inserted += cursor.rowcount
    return inserted


def run_seed(db_path: str = None):
    """Run all seed functions inside a single transaction."""
    path = db_path or DB_PATH
    print(f"Seeding database: {path}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    total = 0
    try:
        print("  Seeding attendance data...")
        n = seed_attendance(cursor)
        print(f"    -> {n} rows")
        total += n

        print("  Seeding financial aid data...")
        n = seed_financial_aid(cursor)
        print(f"    -> {n} rows")
        total += n

        print("  Seeding housing data...")
        n = seed_housing(cursor)
        print(f"    -> {n} rows")
        total += n

        print("  Seeding alumni data...")
        n = seed_alumni(cursor)
        print(f"    -> {n} rows")
        total += n

        print("  Seeding health services data...")
        n = seed_health(cursor)
        print(f"    -> {n} rows")
        total += n

        print("  Enroling S12345 in demo modules...")
        n = seed_s12345_modules(cursor)
        print(f"    -> {n} rows")
        total += n

        conn.commit()
        print(f"\nDone! Total rows inserted: {total}")

    except Exception as e:
        conn.rollback()
        print(f"\nError during seeding: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_seed()

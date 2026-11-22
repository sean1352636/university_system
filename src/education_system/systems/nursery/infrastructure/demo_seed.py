"""Demo data seeded into an empty nursery.db by init_db().

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3

# Same logger name as before the split, so log routing is unchanged.
logger = logging.getLogger("education_system.systems.nursery.infrastructure.database")


# ── Demo seed (dev/demo only) ────────────────────────────────────────────────
# A handful of rows so the superadmin dashboard shows live nursery counts.
# Only inserted when both tables are empty.

_DEMO_STAFF = [
    ("NST001", "Hannah", "Brooks", "Ms", "Nursery Manager", "Whole Setting",
     "Full-time", "hannah.brooks@nursery.local", "01234 567001", 1, 1, 1,
     "EYITT, Level 6 Early Years"),
    ("NST002", "Priya", "Sharma", "Miss", "Room Leader", "Toddler Room",
     "Full-time", "priya.sharma@nursery.local", "01234 567002", 0, 1, 1,
     "Level 3 Early Years Educator"),
    ("NST003", "Daniel", "Okafor", "Mr", "Nursery Practitioner", "Preschool Room",
     "Part-time", "daniel.okafor@nursery.local", "01234 567003", 0, 1, 1,
     "Level 3 Early Years Educator"),
    ("NST004", "Megan", "Lewis", "Miss", "Nursery Practitioner", "Baby Room",
     "Full-time", "megan.lewis@nursery.local", "01234 567004", 0, 0, 1,
     "Level 2 Early Years Practitioner"),
]

_DEMO_PUPILS = [
    ("NCH001", "Oliver", "Hughes", "2022-03-14", "Toddler Room", "NST002",
     "30 hours", "2024-09-02", "Sarah Hughes", "07700 900101",
     "sarah.hughes@example.com", "None", ""),
    ("NCH002", "Amelia", "Patel", "2021-11-02", "Preschool Room", "NST003",
     "15 hours", "2024-09-02", "Raj Patel", "07700 900102",
     "raj.patel@example.com", "Peanuts", "EpiPen kept in office"),
    ("NCH003", "Noah", "Campbell", "2023-06-21", "Baby Room", "NST004",
     "2-year-old funding", "2025-01-06", "Emma Campbell", "07700 900103",
     "emma.campbell@example.com", "None", ""),
    ("NCH004", "Isla", "Murphy", "2022-01-09", "Toddler Room", "NST002",
     "30 hours", "2024-09-02", "Liam Murphy", "07700 900104",
     "liam.murphy@example.com", "Dairy", ""),
    ("NCH005", "Leo", "Bennett", "2021-08-30", "Preschool Room", "NST003",
     "15 hours", "2024-09-02", "Chloe Bennett", "07700 900105",
     "chloe.bennett@example.com", "None", ""),
]


# Age-banded rooms matching the demo children's room names. Ratios follow the
# EYFS statutory minimums for each age band.
_DEMO_ROOMS = [
    ("NRM001", "Baby Room", "Birth to 2 years", 0, 24, 12, "1:3", "NST004",
     "Ground floor", "Sleep room and bottle-prep area attached."),
    ("NRM002", "Toddler Room", "2 to 3 years", 24, 36, 16, "1:4", "NST002",
     "Ground floor", "Direct access to the toddler garden."),
    ("NRM003", "Preschool Room", "3 to 5 years", 36, 60, 24, "1:8", "NST003",
     "First floor", "School-readiness focus for the pre-school year."),
]

# A small waiting list / application pipeline for the demo dashboard.
_DEMO_ADMISSIONS = [
    ("NADM001", "Freya", "Walsh", "2023-02-18", "Hannah Walsh", "07700 900201",
     "hannah.walsh@example.com", "Baby Room", "2025-09-01", "2-year-old funding",
     "Mon,Tue,Wed", "2025-03-10", "sibling", "waiting", None,
     "Older sibling already attends.", None),
    ("NADM002", "Jacob", "Reid", "2022-07-05", "Sara Reid", "07700 900202",
     "sara.reid@example.com", "Toddler Room", "2025-09-01", "15 hours",
     "Mon,Tue,Wed,Thu,Fri", "2025-03-12", "standard", "waiting", None,
     "", None),
    ("NADM003", "Maya", "Osei", "2021-12-20", "Grace Osei", "07700 900203",
     "grace.osei@example.com", "Preschool Room", "2025-04-21", "30 hours",
     "Mon,Tue,Wed,Thu,Fri", "2025-02-01", "looked-after", "offered",
     "2025-03-01", "Place offered, awaiting acceptance.", None),
]


def _last_weekdays(n: int) -> list[_dt.date]:
    """Return the most recent ``n`` weekdays (Mon–Fri), oldest first."""
    out: list[_dt.date] = []
    day = _dt.date.today()
    while len(out) < n:
        if day.weekday() < 5:  # 0=Mon … 4=Fri
            out.append(day)
        day -= _dt.timedelta(days=1)
    return list(reversed(out))


def _seed_attendance(conn: sqlite3.Connection) -> None:
    """Seed an all-day register for active demo children over recent weekdays.

    Deterministic (no randomness): a fixed pattern of late / absent / sick days
    is sprinkled in so the Attendance Report's rates and breakdowns are non-trivial.
    """
    children = conn.execute(
        "SELECT pupil_id, room FROM pupils WHERE status = 'active' "
        "ORDER BY pupil_id").fetchall()
    days = _last_weekdays(10)
    # (child index, day index) -> (status, absence_reason)
    overrides: dict[tuple[int, int], tuple[str, str | None]] = {
        (0, 2): ("late", None),
        (1, 5): ("absent", "Family holiday"),
        (2, 7): ("sick", "Temperature — kept home"),
        (3, 4): ("late", None),
        (1, 8): ("late", None),
        (4, 6): ("absent", "Medical appointment"),
    }
    rows: list[tuple] = []
    for ci, child in enumerate(children):
        for di, day in enumerate(days):
            status, reason = overrides.get((ci, di), ("present", None))
            arrival = departure = None
            if status in ("present", "late"):
                arrival = "09:15" if status == "late" else "08:30"
                departure = "15:30"
            rows.append((
                f"NATT{ci + 1:02d}{di + 1:02d}", child["pupil_id"],
                day.isoformat(), child["room"], "all-day", status,
                arrival, departure, reason, None,
            ))
    conn.executemany(
        "INSERT INTO attendance_records (record_id, pupil_id, attend_date, room, "
        "session, status, arrival_time, departure_time, absence_reason, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _seed_demo_data(conn: sqlite3.Connection) -> None:
    staff_n = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
    pupils_n = conn.execute("SELECT COUNT(*) FROM pupils").fetchone()[0]
    rooms_n = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    admissions_n = conn.execute("SELECT COUNT(*) FROM admissions").fetchone()[0]

    if not (staff_n or pupils_n):
        conn.executemany(
            "INSERT INTO staff (staff_id, first_name, last_name, title, role, room, "
            "employment_status, email, work_phone, is_dsl, is_paediatric_first_aider, "
            "dbs_checked, qualifications) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DEMO_STAFF,
        )
        conn.executemany(
            "INSERT INTO pupils (pupil_id, first_name, last_name, date_of_birth, room, "
            "key_person, funded_hours, start_date, parent_name, parent_phone, "
            "parent_email, allergies, medical_notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DEMO_PUPILS,
        )
        logger.info("Seeded nursery demo data: %d staff, %d children",
                    len(_DEMO_STAFF), len(_DEMO_PUPILS))

    if not rooms_n:
        conn.executemany(
            "INSERT INTO rooms (room_id, name, age_group, min_age_months, "
            "max_age_months, capacity, staff_ratio, room_leader, location, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DEMO_ROOMS,
        )
        logger.info("Seeded nursery demo rooms: %d", len(_DEMO_ROOMS))

    if not admissions_n:
        conn.executemany(
            "INSERT INTO admissions (application_id, child_first_name, "
            "child_last_name, date_of_birth, parent_name, parent_phone, "
            "parent_email, requested_room, requested_start, funded_hours, "
            "days_required, date_applied, priority, status, offer_date, notes, "
            "pupil_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _DEMO_ADMISSIONS,
        )
        logger.info("Seeded nursery demo admissions: %d", len(_DEMO_ADMISSIONS))

    # Light seeds for the Children & Admissions sub-features so their screens
    # show live data against the demo children. Each guarded independently.
    if not conn.execute("SELECT COUNT(*) FROM funded_hours_records").fetchone()[0]:
        conn.executemany(
            "INSERT INTO funded_hours_records (record_id, pupil_id, entitlement, "
            "funded_hours_pw, additional_hours, eligibility_code, "
            "eligibility_start, eligibility_end, funding_period, stretched, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NFH001", "NCH001", "30 hours", 30.0, 5.0, "50012345678",
                 "2024-09-01", "2025-08-31", "2024/25", 0, "Code reconfirmed each term."),
                ("NFH002", "NCH002", "15 hours", 15.0, 0.0, None,
                 "2024-09-01", "2025-08-31", "2024/25", 0, ""),
                ("NFH003", "NCH003", "2-year-old funding", 15.0, 0.0, "ABC123456",
                 "2025-01-06", "2025-08-31", "2024/25", 0, "DWP-eligible 2yo funding."),
            ],
        )
        logger.info("Seeded nursery demo funded-hours records")

    if not conn.execute("SELECT COUNT(*) FROM settling_in").fetchone()[0]:
        conn.executemany(
            "INSERT INTO settling_in (session_id, pupil_id, session_date, "
            "session_type, duration_minutes, key_person, settled_rating, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NSI001", "NCH003", "2025-01-02", "Home visit", 60, "NST004",
                 "Settling", "Met family at home; child shy but engaged."),
                ("NSI002", "NCH003", "2025-01-06", "First session", 120, "NST004",
                 "Settled", "Separated from parent with minimal upset."),
            ],
        )
        logger.info("Seeded nursery demo settling-in sessions")

    if not conn.execute("SELECT COUNT(*) FROM transitions").fetchone()[0]:
        conn.executemany(
            "INSERT INTO transitions (transition_id, pupil_id, destination_school, "
            "expected_start, transition_report_sent, report_sent_date, "
            "teacher_visit, activities, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NTR001", "NCH002", "St Mary's Primary School", "2025-09-03",
                 0, None, 0, "Reception teacher visit booked for July.",
                 "in_progress", "Leaving for Reception in September."),
            ],
        )
        logger.info("Seeded nursery demo transitions")

    if not conn.execute("SELECT COUNT(*) FROM staff_training").fetchone()[0]:
        conn.executemany(
            "INSERT INTO staff_training (record_id, staff_id, course, level, "
            "awarding_body, completed_date, expiry_date, certificate_ref, status, "
            "notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NQT001", "NST001", "Safeguarding & Child Protection", "Level 3",
                 "Local Safeguarding Partnership", "2024-09-15", "2026-09-15",
                 "DSL-2024-001", "valid", "Designated Safeguarding Lead training."),
                ("NQT002", "NST002", "Food Hygiene", "Level 2",
                 "Highfield", "2024-05-02", "2027-05-02", "FH-2024-220", "valid", ""),
                ("NQT003", "NST003", "SENCO Award", "Level 3",
                 "nasen", "2023-11-10", None, "SENCO-2023-3", "valid",
                 "Setting SENCO."),
            ],
        )
        logger.info("Seeded nursery demo training records")

    if not conn.execute("SELECT COUNT(*) FROM paediatric_first_aid").fetchone()[0]:
        conn.executemany(
            "INSERT INTO paediatric_first_aid (record_id, staff_id, "
            "certificate_type, awarding_body, issue_date, expiry_date, "
            "certificate_ref, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NPF001", "NST001", "Full PFA (12 hour)", "St John Ambulance",
                 "2023-06-01", "2026-06-01", "PFA-23-1001", ""),
                ("NPF002", "NST002", "Full PFA (12 hour)", "Red Cross",
                 "2024-03-12", "2027-03-12", "PFA-24-2210", ""),
                ("NPF003", "NST003", "Full PFA (12 hour)", "St John Ambulance",
                 "2024-01-20", "2027-01-20", "PFA-24-1180", ""),
            ],
        )
        logger.info("Seeded nursery demo paediatric first-aid certificates")

    if not conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]:
        conn.executemany(
            "INSERT INTO invoices (invoice_id, pupil_id, period, issue_date, "
            "due_date, hours_billed, hourly_rate, gross_amount, funded_deduction, "
            "discount_amount, total_amount, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NINV001", "NCH001", "June 2025", "2025-06-01", "2025-06-15",
                 50.0, 6.50, 325.0, 195.0, 0.0, 130.0, "issued",
                 "30 funded hours deducted."),
                ("NINV002", "NCH002", "June 2025", "2025-06-01", "2025-06-15",
                 40.0, 6.50, 260.0, 97.50, 26.0, 136.50, "part_paid",
                 "Sibling discount applied."),
                ("NINV003", "NCH004", "June 2025", "2025-06-01", "2025-06-15",
                 45.0, 6.50, 292.50, 195.0, 0.0, 97.50, "paid", ""),
            ],
        )
        logger.info("Seeded nursery demo invoices")

    if not conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]:
        conn.executemany(
            "INSERT INTO payments (payment_id, pupil_id, invoice_id, amount, "
            "method, payment_date, reference, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NPAY001", "NCH002", "NINV002", 50.0, "Tax-Free Childcare",
                 "2025-06-08", "TFC-558201", "Part payment."),
                ("NPAY002", "NCH004", "NINV003", 97.50, "Bank transfer",
                 "2025-06-10", "BACS-90233", "Paid in full."),
            ],
        )
        logger.info("Seeded nursery demo payments")

    if not conn.execute("SELECT COUNT(*) FROM funding_claims").fetchone()[0]:
        conn.executemany(
            "INSERT INTO funding_claims (claim_id, pupil_id, funding_period, "
            "entitlement, funded_hours, weeks, hourly_rate, claim_amount, "
            "headcount_date, status, submitted_date, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NFC001", "NCH001", "Summer 2025", "30 hours", 30.0, 13.0, 5.20,
                 2028.0, "2025-05-15", "submitted", "2025-05-20",
                 "Headcount return submitted to LA."),
                ("NFC002", "NCH003", "Summer 2025", "2-year-old funding", 15.0,
                 13.0, 6.00, 1170.0, "2025-05-15", "draft", None, ""),
            ],
        )
        logger.info("Seeded nursery demo funding claims")

    if not conn.execute("SELECT COUNT(*) FROM childcare_vouchers").fetchone()[0]:
        conn.executemany(
            "INSERT INTO childcare_vouchers (voucher_id, pupil_id, scheme, "
            "provider, account_ref, expected_amount, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NVCH001", "NCH002", "Tax-Free Childcare", "NS&I", "TFC-558201",
                 200.0, "active", "Government top-up scheme."),
                ("NVCH002", "NCH005", "Childcare voucher (employer)", "Edenred",
                 "EDR-77120", 243.0, "active", "Legacy employer scheme."),
            ],
        )
        logger.info("Seeded nursery demo voucher arrangements")

    if not conn.execute("SELECT COUNT(*) FROM fee_discounts").fetchone()[0]:
        conn.executemany(
            "INSERT INTO fee_discounts (discount_id, pupil_id, discount_type, "
            "percentage, fixed_amount, reason, start_date, end_date, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDIS001", "NCH002", "Sibling", 10.0, None,
                 "Second child in family", "2024-09-02", None, "active",
                 "10% off fees while sibling attends."),
            ],
        )
        logger.info("Seeded nursery demo fee discounts")

    # ── Parents & Communication seeds ─────────────────────────────────────────
    if not conn.execute("SELECT COUNT(*) FROM parent_contacts").fetchone()[0]:
        conn.executemany(
            "INSERT INTO parent_contacts (contact_id, pupil_id, full_name, "
            "relationship, phone, email, address, is_primary, "
            "parental_responsibility, can_collect, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NPC001", "NCH001", "Sarah Hughes", "Mother", "07700 900101",
                 "sarah.hughes@example.com", "12 Oak Lane, Bristol", 1, 1, 1,
                 "Primary day-to-day contact."),
                ("NPC002", "NCH001", "Mark Hughes", "Father", "07700 900111",
                 "mark.hughes@example.com", "12 Oak Lane, Bristol", 0, 1, 1, ""),
                ("NPC003", "NCH002", "Raj Patel", "Father", "07700 900102",
                 "raj.patel@example.com", "4 Elm Court, Bristol", 1, 1, 1, ""),
                ("NPC004", "NCH003", "Emma Campbell", "Mother", "07700 900103",
                 "emma.campbell@example.com", "88 Hill Road, Bristol", 1, 1, 1,
                 "Prefers contact by app."),
            ],
        )
        logger.info("Seeded nursery demo parent contacts")

    if not conn.execute("SELECT COUNT(*) FROM emergency_contacts").fetchone()[0]:
        conn.executemany(
            "INSERT INTO emergency_contacts (contact_id, pupil_id, full_name, "
            "relationship, phone_primary, phone_alt, priority, can_collect, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEC001", "NCH001", "Margaret Hughes", "Grandmother",
                 "07700 900131", "0117 496 0001", 1, 1, "Lives nearby."),
                ("NEC002", "NCH002", "Anita Patel", "Grandmother",
                 "07700 900132", None, 1, 1, ""),
                ("NEC003", "NCH002", "David Reed", "Family friend",
                 "07700 900133", None, 2, 0, "Call only if parents unreachable."),
                ("NEC004", "NCH003", "Tom Campbell", "Uncle",
                 "07700 900134", None, 1, 1, ""),
            ],
        )
        logger.info("Seeded nursery demo emergency contacts")

    if not conn.execute("SELECT COUNT(*) FROM consents").fetchone()[0]:
        conn.executemany(
            "INSERT INTO consents (consent_id, pupil_id, consent_type, status, "
            "date_recorded, expiry_date, recorded_by, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NCO001", "NCH001", "Photographs", "granted", "2024-09-02",
                 None, "NST001", "For learning journeys and displays."),
                ("NCO002", "NCH001", "Local outings", "granted", "2024-09-02",
                 None, "NST002", ""),
                ("NCO003", "NCH001", "Social media", "refused", "2024-09-02",
                 None, "NST001", "Parents declined social media use."),
                ("NCO004", "NCH002", "Photographs", "granted", "2024-09-02",
                 None, "NST001", ""),
                ("NCO005", "NCH002", "Sun cream application", "granted",
                 "2025-04-01", "2025-09-30", "NST003", "Parents supply own cream."),
                ("NCO006", "NCH003", "Emergency medical treatment", "granted",
                 "2025-01-06", None, "NST004", "Including ambulance if required."),
            ],
        )
        logger.info("Seeded nursery demo consents")

    if not conn.execute("SELECT COUNT(*) FROM parent_messages").fetchone()[0]:
        conn.executemany(
            "INSERT INTO parent_messages (message_id, pupil_id, direction, "
            "channel, subject, body, message_date, staff_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NMS001", "NCH001", "outgoing", "App", "Settling in well",
                 "Oliver had a lovely morning and enjoyed water play.",
                 "2025-06-02", "NST002", "read"),
                ("NMS002", "NCH002", "incoming", "App", "Running late",
                 "We'll be about 15 minutes late for pick-up today, thank you.",
                 "2025-06-03", None, "replied"),
                ("NMS003", "NCH002", "outgoing", "Email",
                 "Sun cream reminder",
                 "Please could you send in a named bottle of sun cream this week.",
                 "2025-06-04", "NST003", "sent"),
                ("NMS004", "NCH003", "outgoing", "App", "Photo shared",
                 "We've added new photos to Noah's learning journey today.",
                 "2025-06-05", "NST004", "sent"),
            ],
        )
        logger.info("Seeded nursery demo parent messages")

    if not conn.execute("SELECT COUNT(*) FROM daily_updates").fetchone()[0]:
        conn.executemany(
            "INSERT INTO daily_updates (update_id, pupil_id, update_date, mood, "
            "meals, sleep, nappies, activities, notes, staff_id, shared) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDU001", "NCH001", "2025-06-06", "Happy",
                 "Ate all of lunch; tried the broccoli.", "Napped 12:30–13:45",
                 "3 changes, all fine", "Water play, story time, garden.",
                 "Great day — very chatty.", "NST002", 1),
                ("NDU002", "NCH003", "2025-06-06", "Settled",
                 "Had a full bottle mid-morning.", "Two short naps",
                 "4 changes", "Treasure baskets and tummy time.",
                 "Enjoyed the sensory tray.", "NST004", 1),
                ("NDU003", "NCH002", "2025-06-06", "Tired",
                 "Ate half of lunch.", "Did not nap",
                 "Used the toilet independently twice.",
                 "Painting and outdoor play.", "A little tired by home time.",
                 "NST003", 0),
            ],
        )
        logger.info("Seeded nursery demo daily updates")

    if not conn.execute("SELECT COUNT(*) FROM newsletters").fetchone()[0]:
        conn.executemany(
            "INSERT INTO newsletters (newsletter_id, title, issue_date, audience, "
            "body, author, status, published_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NNL001", "June Newsletter", "2025-06-01", "Whole setting",
                 "Welcome to June! This month we're exploring 'Minibeasts'. "
                 "Please send in wellies for garden days.", "NST001",
                 "published", "2025-06-01"),
                ("NNL002", "Preschool Room — Summer Term",
                 "2025-06-03", "Preschool Room",
                 "Our school-readiness focus continues. Reception visits are "
                 "being arranged for our leavers.", "NST003", "published",
                 "2025-06-03"),
                ("NNL003", "Summer Fair — Save the Date", "2025-07-01",
                 "Whole setting",
                 "Our summer fair will be held in July. More details to follow.",
                 "NST001", "draft", None),
            ],
        )
        logger.info("Seeded nursery demo newsletters")

    if not conn.execute("SELECT COUNT(*) FROM parent_meetings").fetchone()[0]:
        conn.executemany(
            "INSERT INTO parent_meetings (meeting_id, pupil_id, meeting_date, "
            "meeting_time, meeting_type, staff_id, location, status, summary, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NPM001", "NCH003", "2025-02-10", "15:30", "Settling review",
                 "NST004", "Baby Room", "completed",
                 "Noah has settled well; agreed to extend sessions.", ""),
                ("NPM002", "NCH002", "2025-06-20", "16:00",
                 "Progress meeting", "NST003", "Preschool Room", "scheduled",
                 "", "Discuss school readiness ahead of transition."),
                ("NPM003", "NCH003", "2025-07-05", "15:45",
                 "2-year progress check", "NST004", "Baby Room", "scheduled",
                 "", "Statutory 2-year-old progress check review."),
            ],
        )
        logger.info("Seeded nursery demo parent meetings")

    # ── Daily register (attendance) ───────────────────────────────────────────
    # Generated against the last 10 weekdays so the Attendance Report shows live
    # data whenever the demo DB is first created. Mostly present, with a few
    # late / absent / sick rows so the rates and breakdowns aren't trivially 100%.
    if not conn.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0]:
        _seed_attendance(conn)
        logger.info("Seeded nursery demo attendance register")

    # ── Accident / incident register ──────────────────────────────────────────
    if not conn.execute("SELECT COUNT(*) FROM accident_records").fetchone()[0]:
        conn.executemany(
            "INSERT INTO accident_records (record_id, pupil_id, record_type, "
            "occurred_date, occurred_time, location, description, injury, "
            "body_part, treatment, first_aider, severity, parent_informed, "
            "parent_signed, riddor_reportable, action_taken, recorded_by, "
            "status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NAC001", "NCH001", "accident",
                 (_dt.date.today() - _dt.timedelta(days=6)).isoformat(), "10:25",
                 "Toddler garden", "Tripped on the path while running.",
                 "Grazed knee", "Left knee",
                 "Cleaned with a wipe and a plaster applied.", "NST002", "minor",
                 1, 1, 0, "Reminded children to walk on the path.", "NST002",
                 "closed", ""),
                ("NAC002", "NCH004", "accident",
                 (_dt.date.today() - _dt.timedelta(days=3)).isoformat(), "14:10",
                 "Toddler Room", "Bumped head on the edge of the play table.",
                 "Small bump", "Forehead",
                 "Cold compress applied; monitored for the afternoon.", "NST002",
                 "moderate", 1, 1, 0,
                 "Padded the table corner.", "NST002", "closed",
                 "Head-bump letter given to parent."),
                ("NAC003", "NCH002", "incident",
                 (_dt.date.today() - _dt.timedelta(days=2)).isoformat(), "11:40",
                 "Preschool Room", "Two children disagreed over a toy.",
                 "None", None, "Supported to share and take turns.", "NST003",
                 "minor", 1, 0, 0, "Circle-time on sharing planned.", "NST003",
                 "closed", ""),
                ("NAC004", "NCH003", "near-miss",
                 (_dt.date.today() - _dt.timedelta(days=1)).isoformat(), "09:15",
                 "Baby Room", "Low shelf was unstable; spotted before use.",
                 "None", None, "", "NST004", "minor", 0, 0, 0,
                 "Shelf secured to the wall by the caretaker.", "NST004",
                 "open", "Logged as a near-miss for the risk assessment review."),
            ],
        )
        logger.info("Seeded nursery demo accident/incident records")

    # ── EYFS Learning & Development seeds ─────────────────────────────────────
    if not conn.execute("SELECT COUNT(*) FROM eyfs_profiles").fetchone()[0]:
        conn.executemany(
            "INSERT INTO eyfs_profiles (profile_id, pupil_id, assessment_date, "
            "term, communication_language, physical_development, pse_development, "
            "literacy, mathematics, understanding_world, expressive_arts, summary, "
            "assessor, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEP001", "NCH002", "2025-05-30", "Summer 2025", "Expected",
                 "Expected", "Expected", "Emerging", "Expected", "Expected",
                 "Exceeding",
                 "On track across most areas; literacy emerging. Ready for "
                 "Reception in September.", "NST003", "finalised"),
                ("NEP002", "NCH005", "2025-05-30", "Summer 2025", "Expected",
                 "Exceeding", "Expected", "Expected", "Expected", "Expected",
                 "Expected", "Confident learner, strong physical development.",
                 "NST003", "draft"),
            ],
        )
        logger.info("Seeded nursery demo EYFS profiles")

    if not conn.execute("SELECT COUNT(*) FROM development_tracking").fetchone()[0]:
        conn.executemany(
            "INSERT INTO development_tracking (record_id, pupil_id, area, aspect, "
            "age_band, judgement, assessment_date, assessor, next_steps, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDT001", "NCH001", "Communication and Language", "Listening and Attention",
                 "22 to 36 months", "Developing", "2025-05-12", "NST002",
                 "Encourage turn-taking in conversation.", ""),
                ("NDT002", "NCH001", "Physical Development", "Moving and Handling",
                 "22 to 36 months", "Secure", "2025-05-12", "NST002", "", ""),
                ("NDT003", "NCH002", "Literacy", "Reading",
                 "30 to 50 months", "Emerging", "2025-05-14", "NST003",
                 "Share more rhyming books to build phonological awareness.", ""),
                ("NDT004", "NCH002", "Mathematics", "Numbers",
                 "30 to 50 months", "Developing", "2025-05-14", "NST003", "", ""),
            ],
        )
        logger.info("Seeded nursery demo development tracking")

    if not conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]:
        conn.executemany(
            "INSERT INTO observations (observation_id, pupil_id, observation_date, "
            "observation_type, area, title, description, context, next_step, staff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NOB001", "NCH001", "2025-06-02", "Spontaneous",
                 "Communication and Language", "Water play chatter",
                 "Oliver described pouring water 'up and over' to a friend.",
                 "Water tray, free play",
                 "Model positional language during play.", "NST002"),
                ("NOB002", "NCH002", "2025-06-03", "Planned", "Mathematics",
                 "Counting cars", "Amelia counted six cars accurately, "
                 "matching one number name to each.", "Adult-led small group",
                 "Extend to counting out a given number.", "NST003"),
                ("NOB003", "NCH003", "2025-06-04", "Focused",
                 "Physical Development", "Tummy-time reaching",
                 "Noah reached and grasped a rattle during tummy time.",
                 "Baby room floor play", "Offer varied textures to grasp.",
                 "NST004"),
            ],
        )
        logger.info("Seeded nursery demo observations")

    if not conn.execute("SELECT COUNT(*) FROM learning_journeys").fetchone()[0]:
        conn.executemany(
            "INSERT INTO learning_journeys (entry_id, pupil_id, entry_date, title, "
            "area, description, wow_moment, shared_with_parent, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NLJ001", "NCH001", "2025-05-20", "First full sentence",
                 "Communication and Language",
                 "Oliver said 'I want the red one please' — his first clear "
                 "full sentence at nursery.", 1, 1, "NST002", ""),
                ("NLJ002", "NCH002", "2025-05-28", "Wrote her name",
                 "Literacy", "Amelia wrote the first letter of her name "
                 "independently.", 1, 1, "NST003", ""),
                ("NLJ003", "NCH003", "2025-06-01", "Sat unaided",
                 "Physical Development",
                 "Noah sat without support for the first time.", 1, 0,
                 "NST004", "Share with parents at pick-up."),
            ],
        )
        logger.info("Seeded nursery demo learning journeys")

    if not conn.execute("SELECT COUNT(*) FROM next_steps").fetchone()[0]:
        conn.executemany(
            "INSERT INTO next_steps (step_id, pupil_id, area, description, "
            "planned_date, target_date, status, achieved_date, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NNS001", "NCH001", "Communication and Language",
                 "Use positional language (up, over, under) in play.",
                 "2025-06-02", "2025-07-04", "in_progress", None, "NST002", ""),
                ("NNS002", "NCH002", "Literacy",
                 "Recognise and join in with rhyming strings.",
                 "2025-05-14", "2025-06-30", "planned", None, "NST003", ""),
                ("NNS003", "NCH002", "Mathematics",
                 "Count out a given number of objects up to 5.",
                 "2025-05-14", "2025-06-13", "achieved", "2025-06-10",
                 "NST003", "Achieved earlier than targeted."),
            ],
        )
        logger.info("Seeded nursery demo next steps")

    if not conn.execute("SELECT COUNT(*) FROM progress_check_2yr").fetchone()[0]:
        conn.executemany(
            "INSERT INTO progress_check_2yr (check_id, pupil_id, check_date, "
            "age_months, comm_language, physical_development, pse_development, "
            "summary, strengths, areas_of_concern, shared_with_parents, "
            "shared_with_hv, staff_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NP2001", "NCH003", "2025-06-05", 24,
                 "Developing — babbling and beginning to use single words.",
                 "Secure — crawling confidently, pulling to stand.",
                 "Developing — forming a strong bond with key person.",
                 "Noah is making good progress across the prime areas.",
                 "Physical development; strong attachment to key person.",
                 "None identified at this stage.", 1, 0, "NST004", "finalised"),
            ],
        )
        logger.info("Seeded nursery demo 2-year progress checks")

    if not conn.execute("SELECT COUNT(*) FROM effective_learning").fetchone()[0]:
        conn.executemany(
            "INSERT INTO effective_learning (record_id, pupil_id, observation_date, "
            "characteristic, aspect, description, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEL001", "NCH001", "2025-06-02", "Playing and Exploring",
                 "Finding out and exploring",
                 "Oliver investigated how water moved through the guttering.",
                 "NST002", ""),
                ("NEL002", "NCH002", "2025-06-03", "Creating and Thinking Critically",
                 "Making links",
                 "Amelia predicted which cup would hold the most water.",
                 "NST003", ""),
                ("NEL003", "NCH005", "2025-06-04", "Active Learning",
                 "Persistence",
                 "Leo kept trying to complete the puzzle despite difficulty.",
                 "NST003", ""),
            ],
        )
        logger.info("Seeded nursery demo characteristics of effective learning")

    if not conn.execute("SELECT COUNT(*) FROM curriculum_planning").fetchone()[0]:
        conn.executemany(
            "INSERT INTO curriculum_planning (plan_id, title, plan_date, room, "
            "area, theme, learning_intention, activities, resources, staff_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NCP001", "Minibeasts week", "2025-06-09", "Preschool Room",
                 "Understanding the World", "Minibeasts",
                 "To explore and name common minibeasts and their habitats.",
                 "Bug hunt in the garden; making a wormery; minibeast songs.",
                 "Magnifying glasses, bug pots, non-fiction books.", "NST003",
                 "planned"),
                ("NCP002", "Heuristic play", "2025-06-02", "Baby Room",
                 "Physical Development", "Treasure baskets",
                 "To develop grasping and exploration through natural materials.",
                 "Treasure basket exploration; texture trays.",
                 "Wooden objects, fabrics, natural materials.", "NST004",
                 "delivered"),
            ],
        )
        logger.info("Seeded nursery demo curriculum plans")

    if not conn.execute("SELECT COUNT(*) FROM cohort_tracking").fetchone()[0]:
        conn.executemany(
            "INSERT INTO cohort_tracking (cohort_id, cohort_name, room, term, area, "
            "total_children, below_count, on_track_count, above_count, "
            "assessment_date, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NCT001", "Preschool Summer 2025", "Preschool Room",
                 "Summer 2025", "Communication and Language", 24, 3, 18, 3,
                 "2025-05-30", "NST003", "Three children below tracked for support."),
                ("NCT002", "Preschool Summer 2025", "Preschool Room",
                 "Summer 2025", "Literacy", 24, 6, 16, 2, "2025-05-30",
                 "NST003", "Literacy the priority area for the cohort."),
                ("NCT003", "Toddler Summer 2025", "Toddler Room",
                 "Summer 2025", "Personal, Social and Emotional Development",
                 16, 2, 12, 2, "2025-05-30", "NST002", ""),
            ],
        )
        logger.info("Seeded nursery demo cohort tracking")

    if not conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]:
        conn.executemany(
            "INSERT INTO evidence (evidence_id, pupil_id, capture_date, title, "
            "evidence_type, area, file_ref, description, shared_with_parent, staff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEV001", "NCH001", "2025-06-02", "Water play photo", "Photo",
                 "Communication and Language", "photos/nch001_waterplay.jpg",
                 "Oliver describing the water flow to a friend.", 1, "NST002"),
                ("NEV002", "NCH002", "2025-05-28", "Name writing sample",
                 "Work sample", "Literacy", "samples/nch002_name.jpg",
                 "First attempt at writing her name.", 1, "NST003"),
                ("NEV003", "NCH003", "2025-06-01", "Sitting unaided video",
                 "Video", "Physical Development", "videos/nch003_sitting.mp4",
                 "Noah sitting without support.", 0, "NST004"),
            ],
        )
        logger.info("Seeded nursery demo evidence")

    # ── Daily Care & Routines seeds ───────────────────────────────────────────
    _today = _dt.date.today().isoformat()
    _yest = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()

    if not conn.execute("SELECT COUNT(*) FROM sign_in_out_log").fetchone()[0]:
        conn.executemany(
            "INSERT INTO sign_in_out_log (event_id, pupil_id, event_date, "
            "event_time, direction, person_name, relationship, recorded_by, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NSO001", "NCH001", _today, "08:32", "in", "Sarah Hughes",
                 "Mother", "NST002", ""),
                ("NSO002", "NCH004", _today, "08:45", "in", "Liam Murphy",
                 "Father", "NST002", ""),
                ("NSO003", "NCH002", _today, "09:05", "in", "Raj Patel",
                 "Father", "NST003", "Arrived a little late."),
                ("NSO004", "NCH001", _yest, "15:28", "out", "Margaret Hughes",
                 "Grandmother", "NST002", "On the authorised collection list."),
            ],
        )
        logger.info("Seeded nursery demo sign in/out events")

    if not conn.execute("SELECT COUNT(*) FROM daily_diary").fetchone()[0]:
        conn.executemany(
            "INSERT INTO daily_diary (entry_id, pupil_id, entry_date, mood, "
            "activities, highlights, notes, staff_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDD001", "NCH001", _today, "Happy",
                 "Water play, story time, garden.",
                 "Counted to ten unprompted at snack time.",
                 "Very chatty today.", "NST002"),
                ("NDD002", "NCH003", _today, "Settled",
                 "Treasure baskets and tummy time.",
                 "Sat unaided for a few seconds.",
                 "Enjoyed the sensory tray.", "NST004"),
            ],
        )
        logger.info("Seeded nursery demo daily diary entries")

    if not conn.execute("SELECT COUNT(*) FROM sleep_log").fetchone()[0]:
        conn.executemany(
            "INSERT INTO sleep_log (sleep_id, pupil_id, sleep_date, start_time, "
            "end_time, duration_minutes, location, checks, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NSL001", "NCH003", _today, "12:30", "13:45", 75, "Cot", 8,
                 "NST004", "Settled quickly; checked every 10 minutes."),
                ("NSL002", "NCH001", _today, "12:40", "13:30", 50, "Sleep mat", 5,
                 "NST002", ""),
            ],
        )
        logger.info("Seeded nursery demo sleep log")

    if not conn.execute("SELECT COUNT(*) FROM toileting_log").fetchone()[0]:
        conn.executemany(
            "INSERT INTO toileting_log (record_id, pupil_id, log_date, log_time, "
            "type, cream_applied, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NTL001", "NCH003", _today, "09:50", "nappy - wet", 0, "NST004", ""),
                ("NTL002", "NCH003", _today, "13:50", "nappy - soiled", 1, "NST004",
                 "Barrier cream applied."),
                ("NTL003", "NCH001", _today, "10:15", "toilet", 0, "NST002",
                 "Used the toilet independently."),
            ],
        )
        logger.info("Seeded nursery demo toileting log")

    if not conn.execute("SELECT COUNT(*) FROM meals").fetchone()[0]:
        conn.executemany(
            "INSERT INTO meals (meal_id, pupil_id, meal_date, meal_type, menu, "
            "amount_eaten, drink, allergy_safe, staff_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NML001", "NCH001", _today, "Lunch",
                 "Cottage pie with vegetables", "all", "Water", 1, "NST002", ""),
                ("NML002", "NCH002", _today, "Lunch",
                 "Cottage pie (nut-free kitchen)", "most", "Milk", 1, "NST003",
                 "Peanut allergy — meal checked against care plan."),
                ("NML003", "NCH004", _today, "Lunch",
                 "Cottage pie (dairy-free portion)", "some", "Water", 1, "NST002",
                 "Dairy intolerance — dairy-free option served."),
            ],
        )
        logger.info("Seeded nursery demo meals")

    if not conn.execute("SELECT COUNT(*) FROM bottle_feeds").fetchone()[0]:
        conn.executemany(
            "INSERT INTO bottle_feeds (feed_id, pupil_id, feed_date, feed_time, "
            "milk_type, offered_ml, taken_ml, temperature_checked, winded, "
            "staff_id, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NBF001", "NCH003", _today, "10:30", "Formula", 180, 160, 1, 1,
                 "NST004", "Took most of the bottle."),
                ("NBF002", "NCH003", _today, "14:15", "Formula", 180, 120, 1, 1,
                 "NST004", "A little unsettled; winded well."),
            ],
        )
        logger.info("Seeded nursery demo bottle feeds")

    if not conn.execute("SELECT COUNT(*) FROM dietary_requirements").fetchone()[0]:
        conn.executemany(
            "INSERT INTO dietary_requirements (record_id, pupil_id, category, "
            "allergen, severity, reaction, action_required, epipen_required, "
            "care_plan_ref, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NDR001", "NCH002", "allergy", "Peanuts", "anaphylaxis",
                 "Swelling, difficulty breathing",
                 "Administer EpiPen and call 999.", 1, "CP-NCH002-001",
                 "active", "EpiPen kept in the office."),
                ("NDR002", "NCH004", "intolerance", "Dairy", "moderate",
                 "Stomach upset", "Serve dairy-free alternatives.", 0,
                 "CP-NCH004-001", "active", ""),
            ],
        )
        logger.info("Seeded nursery demo dietary requirements")

    if not conn.execute("SELECT COUNT(*) FROM existing_injuries").fetchone()[0]:
        conn.executemany(
            "INSERT INTO existing_injuries (record_id, pupil_id, observed_date, "
            "observed_time, body_part, description, explanation, observed_by, "
            "parent_informed, parent_signed, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NEI001", "NCH004", _today, "08:46", "Left shin",
                 "Small bruise", "Fell off scooter at home over the weekend.",
                 "NST002", 1, 1, "Logged on arrival; parent signed."),
            ],
        )
        logger.info("Seeded nursery demo existing injuries")

    if not conn.execute("SELECT COUNT(*) FROM medication_log").fetchone()[0]:
        conn.executemany(
            "INSERT INTO medication_log (record_id, pupil_id, medication_name, "
            "dose, route, reason, administered_date, administered_time, "
            "administered_by, witnessed_by, parent_consent, expiry_date, status, "
            "notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NMD001", "NCH002", "Piriton (antihistamine)", "2.5 ml", "Oral",
                 "Mild hayfever symptoms", _today, "11:00", "NST003", "NST001",
                 1, "2026-04-30", "administered",
                 "Written parental consent on file."),
                ("NMD002", "NCH001", "Calpol (paracetamol)", "5 ml", "Oral",
                 "Temperature after lunch", _yest, "13:15", "NST002", "NST001",
                 1, "2026-08-31", "administered", "Parent informed at collection."),
            ],
        )
        logger.info("Seeded nursery demo medication log")

    # Contracted weekly patterns — the booking calendar the day view resolves.
    # 0=Mon … 4=Fri; the demo children are on a mix of full-time, part-week and
    # morning-only contracts so ratios and occupancy vary across the week.
    if not conn.execute("SELECT COUNT(*) FROM booking_patterns").fetchone()[0]:
        _term_start = (_dt.date.today() - _dt.timedelta(days=120)).isoformat()
        _patterns = []
        _contracts = [
            ("NCH001", (0, 1, 2, 3, 4), "all-day", "Toddler Room", "funded"),
            ("NCH002", (0, 1, 2), "am", "Preschool Room", "funded"),
            ("NCH003", (1, 3), "all-day", "Baby Room", "funded"),
            ("NCH004", (0, 1, 2, 3, 4), "all-day", "Toddler Room", "mixed"),
            ("NCH005", (2, 3, 4), "pm", "Preschool Room", "funded"),
        ]
        _seq = 1
        for pupil, days, session, room, funding in _contracts:
            start, end = {"am": ("08:00", "13:00"), "pm": ("13:00", "18:00"),
                          "all-day": ("08:00", "18:00")}[session]
            for weekday in days:
                _patterns.append((f"NBP{_seq:03d}", pupil, weekday, session,
                                  start, end, room, funding, _term_start, None,
                                  "active", ""))
                _seq += 1
        conn.executemany(
            "INSERT INTO booking_patterns (pattern_id, pupil_id, weekday, "
            "session_type, start_time, end_time, room, funding, start_date, "
            "end_date, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _patterns,
        )
        logger.info("Seeded nursery demo booking patterns")

    if not conn.execute("SELECT COUNT(*) FROM session_bookings").fetchone()[0]:
        _next_week = (_dt.date.today() + _dt.timedelta(days=7)).isoformat()
        conn.executemany(
            "INSERT INTO session_bookings (booking_id, pupil_id, session_date, "
            "session_type, kind, start_time, end_time, room, chargeable, "
            "notice_days, reason, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NSB001", "NCH003", _next_week, "all-day", "extra", "08:00",
                 "18:00", "Baby Room", 1, 5,
                 "Parent working an extra shift", "confirmed", ""),
                ("NSB002", "NCH002", _next_week, "am", "cancellation", None,
                 None, "Preschool Room", 0, 7, "Family holiday", "confirmed",
                 "Notice given in writing."),
            ],
        )
        logger.info("Seeded nursery demo session bookings")

    if not conn.execute("SELECT COUNT(*) FROM setting_closures").fetchone()[0]:
        _inset = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
        _xmas_year = _dt.date.today().year
        conn.executemany(
            "INSERT INTO setting_closures (closure_id, name, start_date, "
            "end_date, closure_type, room, chargeable, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NCL001", "Staff training day", _inset, _inset, "inset", None,
                 1, "Whole setting closed for safeguarding training."),
                ("NCL002", "Christmas closure", f"{_xmas_year}-12-24",
                 f"{_xmas_year + 1}-01-02", "holiday", None, 0, ""),
            ],
        )
        logger.info("Seeded nursery demo closures")

    # Authorised collectors. Passwords are seeded as PBKDF2 hashes of the demo
    # phrases noted below, never in the clear — the collections domain hashes
    # any new ones the same way.
    if not conn.execute(
            "SELECT COUNT(*) FROM authorised_collectors").fetchone()[0]:
        from education_system.systems.nursery.domain.operations.daily_care.collections import (
            collections as _collections,
        )
        conn.executemany(
            "INSERT INTO authorised_collectors (collector_id, pupil_id, "
            "full_name, relationship, phone, password_hash, photo_on_file, "
            "id_checked, is_escalation_contact, valid_from, valid_until, "
            "status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                # Demo collection password: "bluebell"
                ("NAC001", "NCH001", "Sarah Hughes", "Parent", "07700 900101",
                 _collections.hash_password("bluebell"), 1, 1, 0, None, None,
                 "active", ""),
                ("NAC002", "NCH001", "Margaret Hughes", "Grandparent",
                 "07700 900151", None, 1, 1, 1, None, None, "active",
                 "Collects on Fridays."),
                # Demo collection password: "seahorse"
                ("NAC003", "NCH002", "Raj Patel", "Parent", "07700 900102",
                 _collections.hash_password("seahorse"), 1, 1, 0, None, None,
                 "active", ""),
                ("NAC004", "NCH003", "Emma Campbell", "Parent", "07700 900103",
                 None, 0, 0, 0, None, None, "active",
                 "Photo ID still to be checked."),
            ],
        )
        logger.info("Seeded nursery demo authorised collectors")

    if not conn.execute("SELECT COUNT(*) FROM late_collections").fetchone()[0]:
        conn.executemany(
            "INSERT INTO late_collections (record_id, pupil_id, event_date, "
            "due_time, collected_time, minutes_late, collected_by, "
            "collector_id, fee_amount, fee_status, escalation_stage, "
            "escalated_to, parent_contacted, safeguarding_referral, "
            "recorded_by, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("NLC001", "NCH004", _yest, "18:00", "18:25", 25,
                 "Liam Murphy", None, 10.0, "invoiced", "parent-called", None,
                 1, 0, "NST001", "Traffic on the ring road; parent called at "
                 "18:05."),
            ],
        )
        logger.info("Seeded nursery demo late collections")

    conn.commit()

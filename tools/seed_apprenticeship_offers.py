"""Seed employers, their primary contacts, and apprenticeship programmes.

Run against a database path given on the command line so it can be proven on
a copy before touching the live one.
"""
import sqlite3
import sys
from datetime import datetime

EMPLOYERS = [
    # name, company_number, sector, size, headcount, postcode, contact
    ("Northgate Engineering Ltd", "04182233", "Engineering & Manufacturing",
     "Large", 2400, "TS1 4AB",
     ("Priya Raman", "Early Careers Manager", "priya.raman@northgate-eng.co.uk")),
    ("Tees Digital Systems", "07711204", "Digital & Technology",
     "Medium", 180, "TS18 3TX",
     ("Daniel Okoye", "Head of Talent", "daniel.okoye@teesdigital.co.uk")),
    ("Riverside NHS Foundation Trust", "RC000412", "Health & Science",
     "Large", 6100, "TS4 3BW",
     ("Sister Anne Whitfield", "Apprenticeship Lead", "anne.whitfield@riverside-nhs.uk")),
    ("Cleveland Construction Group", "03998210", "Construction",
     "Medium", 340, "TS6 9AA",
     ("Mark Ellison", "Training Coordinator", "mark.ellison@clevelandcg.co.uk")),
    ("Harbour Financial Services", "06620145", "Business & Administration",
     "Medium", 275, "TS1 2NN",
     ("Sofia Marchetti", "People Development Partner", "sofia.marchetti@harbourfs.co.uk")),
]

# reference, title, level, funding_band, duration_months, epa_methods, sector
PROGRAMMES = [
    ("ST0119", "Digital and Technology Solutions Professional", 6, 25000.0, 48,
     "Project report; Professional discussion", "Digital & Technology"),
    ("ST0116", "Software Developer", 4, 15000.0, 24,
     "Portfolio; Practical assessment; Interview", "Digital & Technology"),
    ("ST0457", "Data Analyst", 4, 15000.0, 24,
     "Project with report; Professional discussion", "Digital & Technology"),
    ("ST0154", "Manufacturing Engineer (Degree)", 6, 27000.0, 48,
     "Work-based project; Presentation", "Engineering & Manufacturing"),
    ("ST0384", "Registered Nurse (Degree)", 6, 26000.0, 48,
     "Practice assessment; OSCE", "Health & Science"),
    ("ST0043", "Civil Engineering Site Management", 4, 21000.0, 36,
     "Portfolio; Professional discussion", "Construction"),
    ("ST0070", "Chartered Manager (Degree)", 6, 22000.0, 48,
     "Project presentation; Professional discussion", "Business & Administration"),
    ("ST0620", "Accountancy or Taxation Professional", 7, 21000.0, 36,
     "Case study; Project report", "Business & Administration"),
]


def seed(db_path: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    added_e = added_m = added_p = 0
    try:
        with conn:
            for (name, number, sector, size, headcount, postcode, contact) in EMPLOYERS:
                existing = conn.execute(
                    "SELECT employer_id FROM employers WHERE name = ?", (name,)
                ).fetchone()
                if existing:
                    employer_id = existing["employer_id"]
                else:
                    cur = conn.execute(
                        "INSERT INTO employers (name, company_number, sector, size, "
                        " headcount, postcode, status, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'Active', ?, ?)",
                        (name, number, sector, size, headcount, postcode, now, now),
                    )
                    employer_id = cur.lastrowid
                    added_e += 1

                full_name, job_title, email = contact
                has_contact = conn.execute(
                    "SELECT 1 FROM employer_managers WHERE employer_id = ? AND email = ?",
                    (employer_id, email),
                ).fetchone()
                if not has_contact:
                    conn.execute(
                        "INSERT INTO employer_managers (employer_id, full_name, "
                        " job_title, email, is_primary, active, created_at) "
                        "VALUES (?, ?, ?, ?, 1, 1, ?)",
                        (employer_id, full_name, job_title, email, now),
                    )
                    added_m += 1

            for (ref, title, level, band, months, epa, sector) in PROGRAMMES:
                if conn.execute(
                    "SELECT 1 FROM programmes WHERE reference = ?", (ref,)
                ).fetchone():
                    continue
                conn.execute(
                    "INSERT INTO programmes (reference, title, level, funding_band, "
                    " duration_months, epa_methods, sector, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)",
                    (ref, title, level, band, months, epa, sector, now, now),
                )
                added_p += 1
    finally:
        conn.close()

    print(f"employers added:  {added_e}")
    print(f"contacts added:   {added_m}")
    print(f"programmes added: {added_p}")


if __name__ == "__main__":
    seed(sys.argv[1])

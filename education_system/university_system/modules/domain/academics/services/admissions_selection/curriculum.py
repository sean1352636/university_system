"""Per-course curriculum: the 18 modules a student studies (6 per year x 3).

Each course has an ordered list of 18 modules split across years 1-3. The two
built-in programmes (Computer Science, Data Science) have named curricula;
any other course (e.g. one created via course management) gets 18 modules
auto-generated on first use so the create flow always has something to enrol.
"""

from __future__ import annotations

import re
from datetime import datetime

from education_system.university_system.infrastructure.database.db import (
    get_connection,
    sqlite3,
)
from education_system.university_system.modules.domain.academics.services.admissions_selection.schema import (
    ensure_selection_schema,
)

MODULES_PER_YEAR = 6
YEARS = 3
TOTAL_MODULES = MODULES_PER_YEAR * YEARS  # 18

# Named curricula for the built-in programmes. 6 modules per year, years 1-3.
SEED_CURRICULA: dict[str, list[list[str]]] = {
    "CS": [
        [  # Year 1
            "Programming Fundamentals",
            "Mathematics for Computing",
            "Computer Systems & Architecture",
            "Web Development Fundamentals",
            "Discrete Mathematics",
            "Introduction to Databases",
        ],
        [  # Year 2
            "Data Structures & Algorithms",
            "Object-Oriented Software Engineering",
            "Operating Systems",
            "Computer Networks",
            "Human-Computer Interaction",
            "Design Patterns",
        ],
        [  # Year 3
            "Software Quality Assurance",
            "Formal Methods for System Verification",
            "Algorithm Complexity",
            "Distributed Systems",
            "Cyber Security Principles",
            "Final Year Project",
        ],
    ],
    "DS": [
        [  # Year 1
            "Programming Fundamentals",
            "Mathematics for Data Science",
            "Introduction to Statistics",
            "Data Wrangling & Databases",
            "Computational Thinking",
            "Foundations of Data Science",
        ],
        [  # Year 2
            "Statistical Methods",
            "Machine Learning Foundations",
            "Data Visualisation",
            "SQL & Relational Databases",
            "Probability & Inference",
            "Data Mining",
        ],
        [  # Year 3
            "Introduction to Artificial Intelligence",
            "Deep Learning",
            "Big Data Engineering",
            "Natural Language Processing",
            "Ethics in Data Science",
            "Final Year Data Science Project",
        ],
    ],
    "SE": [
        [
            "Programming Fundamentals",
            "Software Development Lifecycle",
            "Mathematics for Computing",
            "Web Technologies",
            "Database Systems",
            "Computer Systems",
        ],
        [
            "Object-Oriented Design",
            "Software Architecture",
            "Agile Methodologies",
            "Testing & Quality Assurance",
            "Data Structures & Algorithms",
            "Human-Computer Interaction",
        ],
        [
            "DevOps & Continuous Delivery",
            "Distributed Systems",
            "Software Project Management",
            "Secure Software Development",
            "Cloud Computing",
            "Final Year Project",
        ],
    ],
    "CYB": [
        [
            "Programming Fundamentals",
            "Introduction to Cyber Security",
            "Computer Networks",
            "Mathematics for Computing",
            "Operating Systems",
            "Information Security Foundations",
        ],
        [
            "Cryptography",
            "Network Security",
            "Ethical Hacking",
            "Digital Forensics",
            "Secure Software Development",
            "Risk Management",
        ],
        [
            "Penetration Testing",
            "Malware Analysis",
            "Incident Response",
            "Security Operations",
            "Cyber Law & Ethics",
            "Final Year Project",
        ],
    ],
    "AI": [
        [
            "Programming Fundamentals",
            "Mathematics for AI",
            "Introduction to Artificial Intelligence",
            "Data Structures & Algorithms",
            "Logic & Reasoning",
            "Statistics for AI",
        ],
        [
            "Machine Learning",
            "Neural Networks",
            "Knowledge Representation",
            "Search & Optimisation",
            "Computer Vision Foundations",
            "Probabilistic Modelling",
        ],
        [
            "Deep Learning",
            "Natural Language Processing",
            "Reinforcement Learning",
            "AI Ethics & Society",
            "Robotics",
            "Final Year Project",
        ],
    ],
    "BUS": [
        [
            "Principles of Management",
            "Introduction to Marketing",
            "Financial Accounting",
            "Business Economics",
            "Organisational Behaviour",
            "Business Statistics",
        ],
        [
            "Operations Management",
            "Human Resource Management",
            "Corporate Finance",
            "Marketing Management",
            "Business Law",
            "Management Information Systems",
        ],
        [
            "Strategic Management",
            "International Business",
            "Entrepreneurship",
            "Leadership & Change",
            "Business Ethics",
            "Final Year Project",
        ],
    ],
    "ACC": [
        [
            "Financial Accounting",
            "Management Accounting",
            "Principles of Finance",
            "Business Economics",
            "Quantitative Methods",
            "Business Law",
        ],
        [
            "Corporate Finance",
            "Financial Reporting",
            "Taxation",
            "Auditing",
            "Cost Accounting",
            "Investment Analysis",
        ],
        [
            "Advanced Financial Reporting",
            "Financial Management",
            "Audit & Assurance",
            "International Accounting Standards",
            "Risk Management",
            "Final Year Project",
        ],
    ],
    "ECON": [
        [
            "Microeconomics",
            "Macroeconomics",
            "Mathematics for Economics",
            "Statistics for Economics",
            "Economic History",
            "Principles of Finance",
        ],
        [
            "Intermediate Microeconomics",
            "Intermediate Macroeconomics",
            "Econometrics",
            "Public Economics",
            "Labour Economics",
            "International Trade",
        ],
        [
            "Advanced Econometrics",
            "Development Economics",
            "Behavioural Economics",
            "Monetary Economics",
            "Game Theory",
            "Final Year Project",
        ],
    ],
    "MKT": [
        [
            "Introduction to Marketing",
            "Consumer Behaviour",
            "Principles of Management",
            "Business Economics",
            "Marketing Communications",
            "Business Statistics",
        ],
        [
            "Digital Marketing",
            "Brand Management",
            "Market Research",
            "Marketing Analytics",
            "Services Marketing",
            "Sales Management",
        ],
        [
            "Strategic Marketing",
            "International Marketing",
            "Marketing Strategy & Planning",
            "Social Media Marketing",
            "Marketing Ethics",
            "Final Year Project",
        ],
    ],
    "LAW": [
        [
            "Contract Law",
            "Criminal Law",
            "Constitutional & Administrative Law",
            "Legal System & Method",
            "Tort Law",
            "Legal Research & Writing",
        ],
        [
            "Land Law",
            "Equity & Trusts",
            "European Union Law",
            "Company Law",
            "Employment Law",
            "Human Rights Law",
        ],
        [
            "Jurisprudence",
            "Commercial Law",
            "Intellectual Property Law",
            "Evidence",
            "Family Law",
            "Final Year Dissertation",
        ],
    ],
    "PSY": [
        [
            "Introduction to Psychology",
            "Biological Psychology",
            "Cognitive Psychology",
            "Social Psychology",
            "Developmental Psychology",
            "Research Methods & Statistics",
        ],
        [
            "Personality & Individual Differences",
            "Abnormal Psychology",
            "Perception & Attention",
            "Memory & Learning",
            "Quantitative Research Methods",
            "Qualitative Research Methods",
        ],
        [
            "Clinical Psychology",
            "Forensic Psychology",
            "Neuropsychology",
            "Health Psychology",
            "Psychology of Wellbeing",
            "Final Year Project",
        ],
    ],
    "ENG": [
        [
            "Engineering Mathematics",
            "Statics & Dynamics",
            "Thermodynamics",
            "Materials Science",
            "Engineering Design",
            "Electrical Principles",
        ],
        [
            "Fluid Mechanics",
            "Solid Mechanics",
            "Manufacturing Processes",
            "Control Systems",
            "Engineering Mathematics II",
            "Dynamics of Machines",
        ],
        [
            "Heat Transfer",
            "Mechanical Design",
            "Finite Element Analysis",
            "Robotics & Automation",
            "Engineering Management",
            "Final Year Project",
        ],
    ],
    "EEE": [
        [
            "Engineering Mathematics",
            "Circuit Analysis",
            "Digital Electronics",
            "Analogue Electronics",
            "Programming for Engineers",
            "Electromagnetism",
        ],
        [
            "Signals & Systems",
            "Microprocessors & Embedded Systems",
            "Electrical Machines",
            "Control Systems",
            "Communication Systems",
            "Engineering Mathematics II",
        ],
        [
            "Digital Signal Processing",
            "Power Systems",
            "VLSI Design",
            "Wireless Communications",
            "Power Electronics",
            "Final Year Project",
        ],
    ],
    "CIV": [
        [
            "Engineering Mathematics",
            "Statics",
            "Materials & Structures",
            "Surveying",
            "Engineering Geology",
            "Fluid Mechanics",
        ],
        [
            "Structural Analysis",
            "Geotechnical Engineering",
            "Hydraulics",
            "Concrete & Steel Design",
            "Transportation Engineering",
            "Engineering Mathematics II",
        ],
        [
            "Structural Design",
            "Construction Management",
            "Environmental Engineering",
            "Water Resources Engineering",
            "Geotechnical Design",
            "Final Year Project",
        ],
    ],
    "MED": [
        [
            "Human Anatomy",
            "Physiology",
            "Biochemistry",
            "Cell Biology",
            "Medical Ethics & Law",
            "Foundations of Clinical Practice",
        ],
        [
            "Pharmacology",
            "Pathology",
            "Microbiology & Immunology",
            "Clinical Skills",
            "Cardiovascular & Respiratory Systems",
            "Neuroscience",
        ],
        [
            "Internal Medicine",
            "Surgery",
            "Pathophysiology",
            "Clinical Pharmacology",
            "Evidence-Based Medicine",
            "Clinical Placement",
        ],
    ],
    "NUR": [
        [
            "Foundations of Nursing",
            "Human Anatomy & Physiology",
            "Health Assessment",
            "Nursing Ethics & Law",
            "Communication in Healthcare",
            "Introduction to Pharmacology",
        ],
        [
            "Adult Nursing",
            "Mental Health Nursing",
            "Pathophysiology",
            "Clinical Skills & Practice",
            "Evidence-Based Care",
            "Pharmacology for Nursing",
        ],
        [
            "Acute & Critical Care Nursing",
            "Community Nursing",
            "Leadership in Nursing",
            "Public Health & Promotion",
            "Professional Practice",
            "Final Year Project",
        ],
    ],
    "BIO": [
        [
            "Cell Biology",
            "Genetics",
            "Biochemistry",
            "Ecology",
            "Evolution",
            "Laboratory Skills",
        ],
        [
            "Molecular Biology",
            "Microbiology",
            "Physiology",
            "Immunology",
            "Bioinformatics",
            "Research Methods",
        ],
        [
            "Developmental Biology",
            "Genomics",
            "Conservation Biology",
            "Neurobiology",
            "Biotechnology",
            "Final Year Project",
        ],
    ],
    "CHEM": [
        [
            "Inorganic Chemistry",
            "Organic Chemistry",
            "Physical Chemistry",
            "Mathematics for Chemists",
            "Analytical Chemistry",
            "Laboratory Skills",
        ],
        [
            "Organic Synthesis",
            "Coordination Chemistry",
            "Thermodynamics & Kinetics",
            "Spectroscopy",
            "Quantum Chemistry",
            "Inorganic Materials",
        ],
        [
            "Advanced Organic Chemistry",
            "Computational Chemistry",
            "Medicinal Chemistry",
            "Electrochemistry",
            "Catalysis",
            "Final Year Project",
        ],
    ],
    "PHYS": [
        [
            "Classical Mechanics",
            "Mathematics for Physics",
            "Electricity & Magnetism",
            "Waves & Optics",
            "Thermal Physics",
            "Laboratory Skills",
        ],
        [
            "Quantum Mechanics",
            "Electromagnetism",
            "Statistical Mechanics",
            "Mathematical Methods",
            "Condensed Matter Physics",
            "Computational Physics",
        ],
        [
            "Particle Physics",
            "Astrophysics",
            "Advanced Quantum Mechanics",
            "Nuclear Physics",
            "General Relativity",
            "Final Year Project",
        ],
    ],
    "ENGL": [
        [
            "Introduction to Literary Studies",
            "Poetry & Poetics",
            "Shakespeare",
            "The Novel",
            "Critical Theory",
            "Academic Writing",
        ],
        [
            "Renaissance Literature",
            "Romantic Literature",
            "Victorian Literature",
            "Modernism",
            "Drama & Performance",
            "Postcolonial Literature",
        ],
        [
            "Contemporary Literature",
            "Literary Criticism",
            "American Literature",
            "Gender & Literature",
            "Creative Writing",
            "Final Year Dissertation",
        ],
    ],
}


def _prefix(course_code: str) -> str:
    """Sanitised code prefix for generated module codes (e.g. 'CS', 'CYB')."""
    p = re.sub(r"[^A-Z0-9]", "", (course_code or "").upper())
    return p[:6] or "GEN"


def module_code(course_code: str, year: int, idx: int) -> str:
    """Stable per-course module code, e.g. 'CS-Y1-3'."""
    return f"{_prefix(course_code)}-Y{year}-{idx}"


def _build_entries(course_code: str, course_name: str) -> list[dict]:
    """Build the 18 curriculum rows for a course (seeded or auto-generated)."""
    seed = SEED_CURRICULA.get((course_code or "").upper())
    entries: list[dict] = []
    for year in range(1, YEARS + 1):
        for idx in range(1, MODULES_PER_YEAR + 1):
            if seed:
                name = seed[year - 1][idx - 1]
            else:
                name = f"{course_name} Year {year} Module {idx}"
            entries.append({
                "year": year,
                "module_code": module_code(course_code, year, idx),
                "module_name": name,
            })
    return entries


def _module_exists(cursor, code: str) -> bool:
    cursor.execute("SELECT 1 FROM modules WHERE module_code = ? LIMIT 1", (code,))
    return cursor.fetchone() is not None


def _get_or_build_on_cursor(cursor, course_code: str, course_name: str) -> list[dict]:
    """Return the 18-module curriculum, creating + persisting it if absent."""
    ensure_selection_schema(cursor)

    cursor.execute(
        "SELECT year, module_code, module_name FROM course_curriculum "
        "WHERE course_code = ? ORDER BY year, id",
        (course_code,),
    )
    rows = cursor.fetchall()
    if len(rows) == TOTAL_MODULES:
        return [{"year": r[0], "module_code": r[1], "module_name": r[2]} for r in rows]

    # Partial / missing -> rebuild cleanly.
    cursor.execute("DELETE FROM course_curriculum WHERE course_code = ?", (course_code,))
    entries = _build_entries(course_code, course_name)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for e in entries:
        cursor.execute(
            "INSERT INTO course_curriculum (course_code, year, module_code, module_name) "
            "VALUES (?, ?, ?, ?)",
            (course_code, e["year"], e["module_code"], e["module_name"]),
        )
        if not _module_exists(cursor, e["module_code"]):
            cursor.execute(
                "INSERT INTO modules (module_id, module_code, module_name, module_type, "
                "course, year) VALUES (?, ?, ?, ?, ?, ?)",
                (e["module_code"], e["module_code"], e["module_name"],
                 "Core", course_code, str(e["year"])),
            )
    return entries


def get_or_create_curriculum(course_code: str, course_name: str = "") -> list[dict]:
    """Public helper: 18-module curriculum for a course (own connection)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        entries = _get_or_build_on_cursor(cur, course_code, course_name or course_code)
        conn.commit()
        return entries
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def enrol_student_in_curriculum(cursor, student_id: str, course_code: str,
                                course_name: str = "") -> list[dict]:
    """Enrol a student in all 18 curriculum modules, on the given cursor.

    Inserts rows into ``student_modules`` and returns the curriculum so the
    caller can display what was enrolled. Runs entirely on ``cursor`` so it is
    atomic with the surrounding student-create transaction.
    """
    entries = _get_or_build_on_cursor(cursor, course_code, course_name or course_code)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.executemany(
        "INSERT INTO student_modules (student_id, module_code, module_name, "
        "module_type, year, status, enrollment_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(student_id, e["module_code"], e["module_name"], "Core",
          str(e["year"]), "Enrolled", now) for e in entries],
    )
    return entries

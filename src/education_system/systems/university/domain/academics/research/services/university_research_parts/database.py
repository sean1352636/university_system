"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class Database:
    """Wraps the central `student_records.db` via the shared
    `get_connection`. All tables are prefixed `research_*` to avoid
    colliding with generic table names elsewhere in the system."""

    def __init__(self, db_path=None):
        from education_system.systems.university.infrastructure.database.db import get_connection
        self.conn = get_connection()
        self.conn.row_factory = sqlite3.Row
        # Foreign keys reference research_people / research_theses
        # which we own — enabling FK enforcement is safe here.
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.seed_if_empty()

    def create_tables(self):
        cur = self.conn.cursor()

        # People (researchers, supervisors, students, examiners)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                role TEXT NOT NULL,           -- 'staff', 'student', 'examiner', 'external'
                department TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Research Ethics / IRB
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_ethics_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                principal_investigator_id INTEGER,
                department TEXT,
                risk_level TEXT,              -- 'Low', 'Medium', 'High'
                category TEXT,                -- 'Human participants', 'Animal', 'Data-only', etc.
                submitted_date TEXT,
                decision_date TEXT,
                status TEXT NOT NULL,         -- 'Draft','Submitted','Under Review','Approved','Rejected','Revisions Required','Expired'
                approval_expiry TEXT,
                notes TEXT,
                FOREIGN KEY (principal_investigator_id) REFERENCES research_people(id)
            )
        """)

        # REF submissions / research outputs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                output_type TEXT NOT NULL,    -- 'Journal article','Conference paper','Book','Book chapter','Dataset','Software','Other'
                authors TEXT,                 -- comma separated
                lead_author_id INTEGER,
                venue TEXT,                   -- journal/conference/publisher
                publication_date TEXT,
                doi TEXT,
                uoa TEXT,                     -- Unit of Assessment
                ref_submitted INTEGER DEFAULT 0,  -- boolean 0/1
                open_access INTEGER DEFAULT 0,
                quality_rating TEXT,          -- '1*','2*','3*','4*', or ''
                abstract TEXT,
                FOREIGN KEY (lead_author_id) REFERENCES research_people(id)
            )
        """)

        # IP / Tech-transfer / Commercialisation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_ip_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                ip_type TEXT NOT NULL,        -- 'Patent','Copyright','Trademark','Know-how','Software','Design'
                inventor_id INTEGER,
                disclosure_date TEXT,
                filing_date TEXT,
                grant_date TEXT,
                jurisdiction TEXT,
                status TEXT NOT NULL,         -- 'Disclosed','Evaluating','Filed','Granted','Licensed','Abandoned'
                commercial_route TEXT,        -- 'License','Spin-out','Assignment','None yet'
                licensee TEXT,
                revenue_to_date REAL DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (inventor_id) REFERENCES research_people(id)
            )
        """)

        # Theses / dissertations
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_theses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                degree TEXT NOT NULL,         -- 'PhD','MPhil','MRes','Masters'
                department TEXT,
                primary_supervisor_id INTEGER,
                secondary_supervisor_id INTEGER,
                start_date TEXT,
                expected_submission TEXT,
                submission_date TEXT,
                viva_date TEXT,
                internal_examiner_id INTEGER,
                external_examiner_id INTEGER,
                status TEXT NOT NULL,         -- 'Active','Submitted','Under Examination','Viva Scheduled','Passed','Minor Corrections','Major Corrections','Failed','Withdrawn'
                outcome TEXT,
                FOREIGN KEY (student_id) REFERENCES research_people(id),
                FOREIGN KEY (primary_supervisor_id) REFERENCES research_people(id),
                FOREIGN KEY (secondary_supervisor_id) REFERENCES research_people(id),
                FOREIGN KEY (internal_examiner_id) REFERENCES research_people(id),
                FOREIGN KEY (external_examiner_id) REFERENCES research_people(id)
            )
        """)

        # Thesis milestones
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research_thesis_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thesis_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                due_date TEXT,
                completed_date TEXT,
                status TEXT NOT NULL,         -- 'Pending','Completed','Overdue','Missed'
                notes TEXT,
                FOREIGN KEY (thesis_id) REFERENCES research_theses(id) ON DELETE CASCADE
            )
        """)

        self.conn.commit()

    def seed_if_empty(self):
        """Populate with sample data on first run so the UI is not empty."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM research_people")
        if cur.fetchone()[0] > 0:
            return

        now = datetime.now().isoformat()
        people = [
            ("Prof. Eleanor Ashworth", "e.ashworth@uni.ac.uk", "staff", "Computer Science"),
            ("Dr. Marcus Chen", "m.chen@uni.ac.uk", "staff", "Biological Sciences"),
            ("Dr. Priya Raman", "p.raman@uni.ac.uk", "staff", "Engineering"),
            ("Prof. James O'Sullivan", "j.osullivan@uni.ac.uk", "staff", "Physics"),
            ("Sarah Nakamura", "s.nakamura@student.uni.ac.uk", "student", "Computer Science"),
            ("Thomas Bergstrom", "t.bergstrom@student.uni.ac.uk", "student", "Engineering"),
            ("Aisha Patel", "a.patel@student.uni.ac.uk", "student", "Biological Sciences"),
            ("Prof. Helen Warburton", "h.warburton@external.ac.uk", "external", "External"),
            ("Prof. David Kowalski", "d.kowalski@oxbridge.ac.uk", "external", "External"),
        ]
        # The seed data below references people/theses by their 1-based
        # position in these lists. We must resolve those to the actual
        # auto-generated ids: research_people uses AUTOINCREMENT, so if the
        # table was seeded once and later cleared, sqlite_sequence has
        # advanced and re-seeded rows do NOT start at id 1 — hard-coding
        # 1,2,3 then trips the foreign keys.
        people_ids = []
        for p in people:
            cur.execute(
                "INSERT INTO research_people(name,email,role,department,created_at) VALUES(?,?,?,?,?)",
                (*p, now),
            )
            people_ids.append(cur.lastrowid)

        def _pid(ref):
            return people_ids[ref - 1] if ref else None

        # Ethics applications
        ethics = [
            ("ETH-2025-001", "Behavioural study of HCI interfaces for older adults", 1,
             "Computer Science", "Medium", "Human participants",
             "2025-01-12", "2025-02-08", "Approved", "2026-02-08",
             "Approved with standard conditions."),
            ("ETH-2025-014", "Gene expression in zebrafish larvae", 2,
             "Biological Sciences", "High", "Animal",
             "2025-02-20", None, "Under Review", None,
             "Awaiting AWERB panel feedback."),
            ("ETH-2025-022", "Retrospective analysis of anonymised clinical data", 2,
             "Biological Sciences", "Low", "Data-only",
             "2025-03-05", "2025-03-19", "Approved", "2028-03-19",
             ""),
            ("ETH-2026-003", "Survey on AI tool adoption in SMEs", 3,
             "Engineering", "Low", "Human participants",
             "2026-01-15", None, "Revisions Required", None,
             "Revise consent form language."),
        ]
        for e in ethics:
            row = list(e)
            row[2] = _pid(row[2])  # principal_investigator_id
            cur.execute("""INSERT INTO research_ethics_applications
                (reference,title,principal_investigator_id,department,risk_level,category,
                 submitted_date,decision_date,status,approval_expiry,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", row)

        # Research outputs
        outputs = [
            ("Accessible Interface Design Patterns for Cognitive Decline", "Journal article",
             "Ashworth, E.; Nakamura, S.", 1, "ACM Transactions on Accessible Computing",
             "2025-06-15", "10.1145/example.2025.001", "UoA 11 - Computer Science",
             1, 1, "4*", "A study of design patterns supporting users with mild cognitive impairment."),
            ("Quantum error correction via topological codes: a review", "Journal article",
             "O'Sullivan, J.", 4, "Reviews of Modern Physics",
             "2025-09-01", "10.1103/example.2025.002", "UoA 9 - Physics",
             1, 1, "4*", ""),
            ("CRISPR-based screening identifies novel regulators of neural crest migration",
             "Journal article", "Chen, M.; Patel, A.", 2, "Nature Cell Biology",
             "2025-11-04", "10.1038/example.2025.003", "UoA 5 - Biological Sciences",
             0, 1, "4*", ""),
            ("Edge AI for predictive maintenance in rotating machinery",
             "Conference paper", "Raman, P.; Bergstrom, T.", 3,
             "Proceedings of IEEE ICRA 2026", "2026-05-20", "10.1109/example.2026.004",
             "UoA 12 - Engineering", 0, 0, "3*", ""),
        ]
        for o in outputs:
            row = list(o)
            row[3] = _pid(row[3])  # lead_author_id
            cur.execute("""INSERT INTO research_outputs
                (title,output_type,authors,lead_author_id,venue,publication_date,doi,
                 uoa,ref_submitted,open_access,quality_rating,abstract)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", row)

        # IP assets
        ip = [
            ("IP-2024-007", "Adaptive UI framework for accessibility",
             "Software", 1, "2024-09-10", "2025-01-20", None, "UK/EU",
             "Filed", "License", None, 0, ""),
            ("IP-2025-002", "Novel catalyst composition for hydrogen production",
             "Patent", 3, "2025-02-14", "2025-06-30", None, "UK/US/EU",
             "Filed", "Spin-out", None, 0, "Evaluating spin-out company formation."),
            ("IP-2023-019", "Method for targeted gene delivery",
             "Patent", 2, "2023-05-01", "2023-11-12", "2025-08-04", "US",
             "Licensed", "License", "BioNova Therapeutics", 125000,
             "Exclusive license, 5% royalty."),
            ("IP-2026-001", "Vibration-analysis algorithm (know-how disclosure)",
             "Know-how", 3, "2026-01-08", None, None, "N/A",
             "Disclosed", "None yet", None, 0, ""),
        ]
        for item in ip:
            row = list(item)
            row[3] = _pid(row[3])  # inventor_id
            cur.execute("""INSERT INTO research_ip_assets
                (reference,title,ip_type,inventor_id,disclosure_date,filing_date,grant_date,
                 jurisdiction,status,commercial_route,licensee,revenue_to_date,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)

        # Theses
        theses = [
            (5, "Human-computer interaction for ageing populations", "PhD",
             "Computer Science", 1, 4, "2023-09-25", "2026-09-25", None, None,
             None, None, "Active", None),
            (6, "Machine learning for industrial condition monitoring", "PhD",
             "Engineering", 3, 1, "2022-10-01", "2025-10-01", "2025-11-30",
             "2026-03-18", 1, 8, "Viva Scheduled", None),
            (7, "Transcriptional regulation in vertebrate development", "PhD",
             "Biological Sciences", 2, 4, "2021-09-20", "2024-09-20", "2024-12-15",
             "2025-04-10", 4, 9, "Minor Corrections",
             "Minor corrections to be submitted within 3 months."),
        ]
        thesis_ids = []
        for t in theses:
            row = list(t)
            for i in (0, 4, 5, 10, 11):  # student / supervisors / examiners
                row[i] = _pid(row[i])
            cur.execute("""INSERT INTO research_theses
                (student_id,title,degree,department,primary_supervisor_id,secondary_supervisor_id,
                 start_date,expected_submission,submission_date,viva_date,
                 internal_examiner_id,external_examiner_id,status,outcome)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)
            thesis_ids.append(cur.lastrowid)

        def _tid(ref):
            return thesis_ids[ref - 1] if ref else None

        # Milestones
        milestones = [
            # Sarah - active PhD
            (1, "Confirmation of Registration (Year 1 review)", "2024-09-25", "2024-09-18", "Completed", ""),
            (1, "Annual Progress Review Y2", "2025-09-25", "2025-09-22", "Completed", ""),
            (1, "Annual Progress Review Y3", "2026-09-25", None, "Pending", ""),
            (1, "Thesis submission", "2026-09-25", None, "Pending", ""),
            # Thomas - viva scheduled
            (2, "Confirmation of Registration", "2023-10-01", "2023-09-28", "Completed", ""),
            (2, "Annual Progress Review Y2", "2024-10-01", "2024-09-30", "Completed", ""),
            (2, "Thesis submission", "2025-10-01", "2025-11-30", "Completed", "Extension granted."),
            (2, "Viva voce examination", "2026-03-18", None, "Pending", ""),
            # Aisha - minor corrections
            (3, "Confirmation of Registration", "2022-09-20", "2022-09-15", "Completed", ""),
            (3, "Thesis submission", "2024-09-20", "2024-12-15", "Completed", "Extension granted."),
            (3, "Viva voce examination", "2025-04-10", "2025-04-10", "Completed", "Minor corrections."),
            (3, "Corrections submission", "2025-07-10", None, "Pending", ""),
        ]
        for m in milestones:
            row = list(m)
            row[0] = _tid(row[0])  # thesis_id
            cur.execute("""INSERT INTO research_thesis_milestones
                (thesis_id,name,due_date,completed_date,status,notes)
                VALUES(?,?,?,?,?,?)""", row)

        self.conn.commit()

    # ----- generic query helpers --------------------------------------------
    def query(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur.lastrowid

    def close(self):
        self.conn.close()

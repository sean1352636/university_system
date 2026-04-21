"""Seed 50 subjects into the secondary school database."""

from education_system.secondary_school.infrastructure.database.schema import initialise_database, seed_default_users
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService

SUBJECTS = [
    # Core subjects — KS3
    ("MATH01", "Mathematics", "Maths", "KS3", True, 30, "Mr Thompson", "M1"),
    ("ENG01", "English Language", "English", "KS3", True, 30, "Mrs Clarke", "E1"),
    ("ENG02", "English Literature", "English", "KS3", True, 30, "Mrs Clarke", "E2"),
    ("SCI01", "Science", "Science", "KS3", True, 30, "Dr Patel", "S1"),
    ("PE01", "Physical Education", "PE", "KS3", True, 30, "Mr Davies", "GYM"),
    ("PSHE01", "PSHE & Citizenship", "PSHE", "KS3", True, 30, "Ms Green", "P1"),
    ("RE01", "Religious Education", "RE", "KS3", True, 30, "Mr Ahmed", "R1"),
    ("ICT01", "ICT & Computing", "Computing", "KS3", True, 30, "Mr Wilson", "IT1"),
    # Core subjects — KS4
    ("MATH02", "GCSE Mathematics", "Maths", "KS4", True, 30, "Mr Thompson", "M2"),
    ("ENG03", "GCSE English Language", "English", "KS4", True, 30, "Mrs Clarke", "E1"),
    ("ENG04", "GCSE English Literature", "English", "KS4", True, 30, "Ms Bennett", "E3"),
    ("SCI02", "GCSE Combined Science", "Science", "KS4", True, 30, "Dr Patel", "S2"),
    ("SCI03", "GCSE Biology", "Science", "KS4", False, 28, "Dr Patel", "S1"),
    ("SCI04", "GCSE Chemistry", "Science", "KS4", False, 28, "Mrs Shaw", "S3"),
    ("SCI05", "GCSE Physics", "Science", "KS4", False, 28, "Mr Newton", "S4"),
    ("PE02", "GCSE Physical Education", "PE", "KS4", False, 25, "Mr Davies", "GYM"),
    # Option subjects — KS3
    ("HIS01", "History", "Humanities", "KS3", False, 30, "Mr Brown", "H1"),
    ("GEO01", "Geography", "Humanities", "KS3", False, 30, "Ms Taylor", "G1"),
    ("FRE01", "French", "MFL", "KS3", False, 30, "Mme Dupont", "L1"),
    ("SPA01", "Spanish", "MFL", "KS3", False, 30, "Sr Garcia", "L2"),
    ("GER01", "German", "MFL", "KS3", False, 30, "Frau Müller", "L3"),
    ("ART01", "Art & Design", "Art", "KS3", False, 28, "Ms Rivera", "A1"),
    ("MUS01", "Music", "Music", "KS3", False, 28, "Mr Lloyd", "MU1"),
    ("DRA01", "Drama", "Performing Arts", "KS3", False, 28, "Ms Harper", "DR1"),
    ("DT01", "Design & Technology", "Technology", "KS3", False, 25, "Mr Carter", "DT1"),
    ("FD01", "Food Technology", "Technology", "KS3", False, 24, "Mrs Baker", "FD1"),
    # Option subjects — KS4 (GCSE)
    ("HIS02", "GCSE History", "Humanities", "KS4", False, 30, "Mr Brown", "H2"),
    ("GEO02", "GCSE Geography", "Humanities", "KS4", False, 30, "Ms Taylor", "G2"),
    ("FRE02", "GCSE French", "MFL", "KS4", False, 28, "Mme Dupont", "L1"),
    ("SPA02", "GCSE Spanish", "MFL", "KS4", False, 28, "Sr Garcia", "L2"),
    ("GER02", "GCSE German", "MFL", "KS4", False, 28, "Frau Müller", "L3"),
    ("ART02", "GCSE Art & Design", "Art", "KS4", False, 25, "Ms Rivera", "A1"),
    ("MUS02", "GCSE Music", "Music", "KS4", False, 25, "Mr Lloyd", "MU1"),
    ("DRA02", "GCSE Drama", "Performing Arts", "KS4", False, 25, "Ms Harper", "DR1"),
    ("DT02", "GCSE Design & Technology", "Technology", "KS4", False, 25, "Mr Carter", "DT1"),
    ("FD02", "GCSE Food Preparation & Nutrition", "Technology", "KS4", False, 24, "Mrs Baker", "FD1"),
    ("CS01", "GCSE Computer Science", "Computing", "KS4", False, 28, "Mr Wilson", "IT1"),
    ("BUS01", "GCSE Business Studies", "Business", "KS4", False, 28, "Mrs Knight", "B1"),
    ("ECO01", "GCSE Economics", "Business", "KS4", False, 28, "Mrs Knight", "B2"),
    ("SOC01", "GCSE Sociology", "Humanities", "KS4", False, 28, "Ms Green", "H3"),
    ("PSY01", "GCSE Psychology", "Humanities", "KS4", False, 28, "Dr Ellis", "H4"),
    ("RE02", "GCSE Religious Studies", "RE", "KS4", False, 28, "Mr Ahmed", "R1"),
    ("PHO01", "GCSE Photography", "Art", "KS4", False, 22, "Ms Rivera", "A2"),
    ("TEX01", "GCSE Textiles", "Art", "KS4", False, 22, "Mrs Price", "A3"),
    ("MED01", "GCSE Media Studies", "English", "KS4", False, 28, "Ms Bennett", "E4"),
    ("HEA01", "BTEC Health & Social Care", "Health", "KS4", False, 25, "Mrs Foster", "HC1"),
    ("SPO01", "BTEC Sport", "PE", "KS4", False, 25, "Mr Davies", "GYM"),
    ("ITA01", "GCSE Italian", "MFL", "KS4", False, 25, "Sig Rossi", "L4"),
    ("AST01", "GCSE Astronomy", "Science", "KS4", False, 25, "Mr Newton", "S5"),
    ("STA01", "GCSE Statistics", "Maths", "KS4", False, 28, "Mr Thompson", "M3"),
]


def seed_subjects(db_path=None):
    initialise_database(db_path)
    seed_default_users(db_path)
    svc = SubjectService(db_path)

    created = 0
    skipped = 0
    for code, title, dept, ks, core, cap, teacher, room in SUBJECTS:
        existing = svc.get_subject_by_code(code)
        if existing:
            skipped += 1
            continue
        svc.create_subject(
            subject_code=code, title=title, department=dept,
            key_stage=ks, is_core=core, capacity=cap,
            teacher=teacher, room=room,
        )
        created += 1

    print(f"Subjects seeded: {created} created, {skipped} already existed")
    print(f"Total subjects: {len(svc.list_subjects(limit=200))}")


if __name__ == "__main__":
    seed_subjects()

"""Seed the subjects table with National Curriculum primary school subjects."""

import sqlite3
import logging

logger = logging.getLogger(__name__)

SUBJECTS = [
    # Core subjects
    ("ENG01", "English", "Reading, writing, spelling, grammar and spoken language", 1, "All"),
    ("MAT01", "Mathematics", "Number, measurement, geometry, statistics", 1, "All"),
    ("SCI01", "Science", "Working scientifically, biology, chemistry, physics", 1, "All"),
    # Foundation subjects
    ("ART01", "Art and Design", "Drawing, painting, sculpture, printing", 0, "All"),
    ("COM01", "Computing", "Coding, digital literacy, online safety", 0, "All"),
    ("DT01", "Design and Technology", "Design, make, evaluate, cooking and nutrition", 0, "All"),
    ("GEO01", "Geography", "Locational knowledge, human and physical geography, fieldwork", 0, "All"),
    ("HIS01", "History", "Chronological understanding, historical enquiry", 0, "All"),
    ("MFL01", "Modern Foreign Languages", "Listening, speaking, reading and writing in a foreign language", 0, "KS2"),
    ("MUS01", "Music", "Performing, composing, listening and appraising", 0, "All"),
    ("PE01", "Physical Education", "Games, gymnastics, dance, athletics, swimming", 0, "All"),
    ("RE01", "Religious Education", "Christianity and other world faiths", 0, "All"),
    ("PSHE01", "PSHE", "Personal, social, health and economic education", 0, "All"),
    # EYFS specific areas
    ("EYFS_CL", "Communication and Language", "Listening, attention, understanding, speaking", 0, "EYFS"),
    ("EYFS_PD", "Physical Development", "Moving and handling, health and self-care", 0, "EYFS"),
    ("EYFS_PSE", "Personal, Social and Emotional Development", "Self-confidence, managing feelings, relationships", 0, "EYFS"),
    ("EYFS_UW", "Understanding the World", "People and communities, the world, technology", 0, "EYFS"),
    ("EYFS_EAD", "Expressive Arts and Design", "Exploring media and materials, being imaginative", 0, "EYFS"),
    ("EYFS_LIT", "Literacy", "Reading and writing in the Early Years", 0, "EYFS"),
    ("EYFS_MAT", "Mathematics (EYFS)", "Numbers, shape, space and measure", 0, "EYFS"),
]


def seed_subjects(db_path):
    """Insert default subjects if none exist."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM subjects")
        if cursor.fetchone()[0] > 0:
            return  # Already seeded

        for code, title, desc, is_core, ks in SUBJECTS:
            cursor.execute(
                "INSERT INTO subjects (subject_code, title, description, is_core, key_stage) "
                "VALUES (?, ?, ?, ?, ?)",
                (code, title, desc, is_core, ks),
            )
        conn.commit()
        logger.info("Seeded %d subjects", len(SUBJECTS))
    finally:
        conn.close()

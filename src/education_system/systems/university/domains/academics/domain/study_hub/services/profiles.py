"""The one study profile, shared by every part of the Study Hub.

There used to be two. ``study_matching`` created ``study_profiles`` and
scored peer compatibility from it; ``study_recommendations`` wrote to
the *same table* with a different vocabulary and a different meaning for
``interests_json``. Saving a recommendations profile therefore:

* replaced ``study_style`` "Visual" with "reading" — matching compares
  the two styles for equality, so the student stopped matching anyone;
* overwrote the interests list with a dict of hours/strengths/weaknesses,
  which matching also scores on.

Between them those two fields carry 35% of the compatibility weight, so
using one feature silently degraded the other. One profile, one
vocabulary, and the recommendation fields get columns of their own.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "STUDY_STYLES", "PREFERRED_TIMES", "GROUP_SIZES", "COMMUNICATION_STYLES",
    "NOISE_PREFERENCES", "normalise_style", "ProfileService",
]

#: The canonical vocabulary. Matching compared styles for equality while
#: recommendations wrote lowercase words from a different list, so the
#: two could never agree; everything is normalised onto these.
STUDY_STYLES = ("Visual", "Auditory", "Reading", "Kinesthetic")
PREFERRED_TIMES = ("Morning", "Afternoon", "Evening", "Night")
GROUP_SIZES = ("Solo", "Pair", "Small", "Large")
COMMUNICATION_STYLES = ("Collaborative", "Independent", "Mixed")
NOISE_PREFERENCES = ("Silent", "Quiet", "Moderate", "Lively")

#: Legacy spellings seen in the two old services.
_STYLE_ALIASES = {
    "visual": "Visual", "auditory": "Auditory", "aural": "Auditory",
    "reading": "Reading", "reading/writing": "Reading", "read": "Reading",
    "writing": "Reading", "kinesthetic": "Kinesthetic",
    "kinaesthetic": "Kinesthetic", "practical": "Kinesthetic",
}


def normalise_style(value: Optional[str]) -> str:
    """Map any recorded spelling onto the canonical vocabulary."""
    if not value:
        return STUDY_STYLES[0]
    return _STYLE_ALIASES.get(str(value).strip().lower(), str(value).strip().title()) \
        if str(value).strip().lower() in _STYLE_ALIASES else (
            str(value).strip() if str(value).strip() in STUDY_STYLES else STUDY_STYLES[0])


class ProfileService:
    """Read and write the single ``study_profiles`` row per student."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.ensure_schema()

    # -- infrastructure -------------------------------------------------
    def _transaction(self):
        from education_system.systems.university.infrastructure.database.db import (
            transaction,
        )
        return transaction(self.db_path) if self.db_path else transaction()

    def _connect(self):
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
        return get_connection(self.db_path) if self.db_path else get_connection()

    def ensure_schema(self) -> None:
        """Create the table, and add the recommendation columns to an
        existing one — they used to be crammed into ``interests_json``."""
        try:
            with self._transaction() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS study_profiles (
                        profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL UNIQUE,
                        study_style TEXT DEFAULT 'Visual',
                        preferred_time TEXT DEFAULT 'Evening',
                        group_size_preference TEXT DEFAULT 'Small',
                        communication_style TEXT DEFAULT 'Collaborative',
                        noise_preference TEXT DEFAULT 'Quiet',
                        availability_json TEXT,
                        interests_json TEXT,
                        hours_per_week REAL DEFAULT 0,
                        strengths TEXT,
                        weaknesses TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                existing = {r[1] for r in conn.execute("PRAGMA table_info(study_profiles)")}
                for column, ddl in (("hours_per_week", "REAL DEFAULT 0"),
                                    ("strengths", "TEXT"),
                                    ("weaknesses", "TEXT")):
                    if column not in existing:
                        conn.execute(
                            f"ALTER TABLE study_profiles ADD COLUMN {column} {ddl}")
                conn.commit()
        except Exception:
            logger.exception("Could not ensure study_profiles schema")

    # -- reads ----------------------------------------------------------
    def get(self, student_id: str) -> Optional[Dict[str, Any]]:
        """The student's profile as a dict, with ``interests`` decoded."""
        if not student_id:
            return None
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM study_profiles WHERE student_id = ?",
                    (str(student_id),)).fetchone()
        except Exception:
            logger.exception("Could not read study profile for %s", student_id)
            return None
        if row is None:
            return None

        profile = dict(row)
        profile["study_style"] = normalise_style(profile.get("study_style"))
        profile["interests"] = self._decode_interests(profile.pop("interests_json", None))
        profile["availability"] = self._decode_json(profile.pop("availability_json", None), {})
        return profile

    @staticmethod
    def _decode_interests(raw) -> List[str]:
        """Interests as a list, tolerating the dict the old recommendation
        service used to write into this column."""
        value = ProfileService._decode_json(raw, [])
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, dict):
            # A profile written by the old recommendations path: it had no
            # interests, so report none rather than its private fields.
            return []
        return []

    @staticmethod
    def _decode_json(raw, default):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return default

    # -- writes ---------------------------------------------------------
    def save(self, student_id: str, **fields: Any) -> Optional[int]:
        """Create or update a profile, touching only the fields given.

        Partial by design: the matching screen sets style and interests,
        the recommendations screen sets hours and strengths, and neither
        should erase the other's answers.
        """
        if not student_id:
            return None

        columns: Dict[str, Any] = {}
        if "study_style" in fields:
            columns["study_style"] = normalise_style(fields["study_style"])
        for name in ("preferred_time", "group_size_preference",
                     "communication_style", "noise_preference",
                     "strengths", "weaknesses"):
            if name in fields and fields[name] is not None:
                columns[name] = fields[name]
        if "hours_per_week" in fields and fields["hours_per_week"] is not None:
            try:
                columns["hours_per_week"] = float(fields["hours_per_week"])
            except (TypeError, ValueError):
                pass
        if "interests" in fields:
            columns["interests_json"] = json.dumps(list(fields["interests"] or []))
        if "availability" in fields:
            columns["availability_json"] = json.dumps(fields["availability"] or {})

        now = datetime.now().isoformat()
        try:
            with self._transaction() as conn:
                row = conn.execute(
                    "SELECT profile_id FROM study_profiles WHERE student_id = ?",
                    (str(student_id),)).fetchone()
                if row:
                    if columns:
                        sets = ", ".join(f"{c} = ?" for c in columns)
                        conn.execute(
                            f"UPDATE study_profiles SET {sets}, updated_at = ? "
                            "WHERE student_id = ?",
                            (*columns.values(), now, str(student_id)))
                    profile_id = row[0]
                else:
                    columns.setdefault("study_style", STUDY_STYLES[0])
                    cols = ["student_id", *columns, "created_at", "updated_at"]
                    conn.execute(
                        f"INSERT INTO study_profiles ({', '.join(cols)}) "
                        f"VALUES ({', '.join('?' * len(cols))})",
                        (str(student_id), *columns.values(), now, now))
                    profile_id = conn.execute(
                        "SELECT profile_id FROM study_profiles WHERE student_id = ?",
                        (str(student_id),)).fetchone()[0]
                conn.commit()
            return profile_id
        except Exception:
            logger.exception("Could not save study profile for %s", student_id)
            return None

    def all_profiles(self, exclude_student: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every profile, for peer matching."""
        sql = "SELECT * FROM study_profiles"
        params: tuple = ()
        if exclude_student:
            sql += " WHERE student_id != ?"
            params = (str(exclude_student),)
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        except Exception:
            logger.exception("Could not list study profiles")
            return []
        out = []
        for row in rows:
            profile = dict(row)
            profile["study_style"] = normalise_style(profile.get("study_style"))
            profile["interests"] = self._decode_interests(profile.pop("interests_json", None))
            profile["availability"] = self._decode_json(profile.pop("availability_json", None), {})
            out.append(profile)
        return out

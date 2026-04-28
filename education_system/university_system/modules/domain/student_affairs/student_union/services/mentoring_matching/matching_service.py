"""Mentoring matching service.

Additive layer over the existing university student-union mentorship module.
Introduces structured profiles/preferences, a scoring-based recommender, and
post-pairing outcome capture — all in NEW tables keyed off the existing
mentor_id / mentee_id values used by ``mentorship_relationships``.

Existing tables are NOT modified.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class MentoringMatchingError(Exception):
    """Raised on validation failure or invalid state transition."""


def _norm_course(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _parse_csv(value: Optional[str]) -> List[str]:
    """Split a comma-separated string, trim, drop empties, lower-case."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [t.strip().lower() for t in str(value).split(",") if t.strip()]


def _overlap(a: List[str], b: List[str]) -> List[str]:
    sa = set(a)
    return [x for x in dict.fromkeys(b) if x in sa]


class MentoringMatchingService:
    """Structured matching + outcome capture for peer mentoring."""

    PROFILE_FIELDS = (
        "year_of_study", "course", "strengths_csv",
        "availability_csv", "languages_csv", "max_mentees", "bio",
    )
    PREF_FIELDS = (
        "course", "learning_goals_csv", "preferred_languages_csv",
        "availability_csv", "preferred_year_min",
    )

    def __init__(
        self,
        db_path: Optional[str] = None,
        count_active_mentees: Optional[Callable[[int], int]] = None,
    ) -> None:
        # When no path is given, use the central student_records.db via
        # the shared `get_connection()` so mentoring data persists
        # alongside the rest of the system. `:memory:` is preserved as
        # an explicit option for tests.
        self.db_path = db_path  # may be None, ":memory:", or a real path
        self._count_active_mentees = count_active_mentees or (lambda _mid: 0)
        self._mem_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
        self._init_schema()

    # ---------- connection helpers ----------
    def _conn(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        if self.db_path is None:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn: sqlite3.Connection) -> None:
        if self._mem_conn is None:
            conn.close()

    def _init_schema(self) -> None:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS mentor_profiles (
                    mentor_id INTEGER PRIMARY KEY,
                    year_of_study INTEGER,
                    course TEXT,
                    strengths_csv TEXT,
                    availability_csv TEXT,
                    languages_csv TEXT,
                    max_mentees INTEGER DEFAULT 3,
                    bio TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS mentee_preferences (
                    mentee_id INTEGER PRIMARY KEY,
                    course TEXT,
                    learning_goals_csv TEXT,
                    preferred_languages_csv TEXT,
                    availability_csv TEXT,
                    preferred_year_min INTEGER,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS mentor_match_recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mentee_id INTEGER NOT NULL,
                    mentor_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    reasons_json TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'suggested'
                );
                CREATE TABLE IF NOT EXISTS mentoring_outcomes (
                    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_id INTEGER NOT NULL,
                    confidence_pre INTEGER,
                    confidence_post INTEGER,
                    goals_met INTEGER,
                    satisfaction INTEGER,
                    would_recommend INTEGER,
                    narrative TEXT,
                    recorded_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mmr_mentee
                    ON mentor_match_recommendations(mentee_id);
                CREATE INDEX IF NOT EXISTS idx_outcomes_pair
                    ON mentoring_outcomes(pair_id);
                """
            )
            conn.commit()
        finally:
            self._close(conn)

    # ---------- profile / preference upserts ----------
    def upsert_mentor_profile(self, mentor_id: int, **fields: Any) -> None:
        if not isinstance(mentor_id, int) or mentor_id <= 0:
            raise MentoringMatchingError("mentor_id must be a positive integer")
        unknown = set(fields) - set(self.PROFILE_FIELDS)
        if unknown:
            raise MentoringMatchingError(f"Unknown mentor profile fields: {unknown}")

        if "course" in fields:
            fields["course"] = _norm_course(fields["course"])
        for k in ("strengths_csv", "availability_csv", "languages_csv"):
            if k in fields and fields[k] is not None and not isinstance(fields[k], str):
                fields[k] = ",".join(str(v) for v in fields[k])
        if "max_mentees" in fields and fields["max_mentees"] is not None:
            try:
                fields["max_mentees"] = int(fields["max_mentees"])
            except (TypeError, ValueError) as exc:
                raise MentoringMatchingError("max_mentees must be int") from exc
            if fields["max_mentees"] < 0:
                raise MentoringMatchingError("max_mentees must be >= 0")

        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT mentor_id FROM mentor_profiles WHERE mentor_id = ?",
                (mentor_id,),
            )
            now = datetime.utcnow().isoformat()
            if cur.fetchone():
                if fields:
                    sets = ", ".join(f"{k} = ?" for k in fields)
                    params = list(fields.values()) + [now, mentor_id]
                    cur.execute(
                        f"UPDATE mentor_profiles SET {sets}, updated_at = ? "
                        f"WHERE mentor_id = ?",
                        params,
                    )
            else:
                cols = ["mentor_id"] + list(fields) + ["updated_at"]
                placeholders = ", ".join("?" for _ in cols)
                vals = [mentor_id] + list(fields.values()) + [now]
                cur.execute(
                    f"INSERT INTO mentor_profiles ({', '.join(cols)}) "
                    f"VALUES ({placeholders})",
                    vals,
                )
            conn.commit()
        finally:
            self._close(conn)

    def upsert_mentee_preferences(self, mentee_id: int, **fields: Any) -> None:
        if not isinstance(mentee_id, int) or mentee_id <= 0:
            raise MentoringMatchingError("mentee_id must be a positive integer")
        unknown = set(fields) - set(self.PREF_FIELDS)
        if unknown:
            raise MentoringMatchingError(f"Unknown mentee preference fields: {unknown}")

        if "course" in fields:
            fields["course"] = _norm_course(fields["course"])
        for k in ("learning_goals_csv", "preferred_languages_csv", "availability_csv"):
            if k in fields and fields[k] is not None and not isinstance(fields[k], str):
                fields[k] = ",".join(str(v) for v in fields[k])
        if "preferred_year_min" in fields and fields["preferred_year_min"] is not None:
            try:
                fields["preferred_year_min"] = int(fields["preferred_year_min"])
            except (TypeError, ValueError) as exc:
                raise MentoringMatchingError("preferred_year_min must be int") from exc

        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT mentee_id FROM mentee_preferences WHERE mentee_id = ?",
                (mentee_id,),
            )
            now = datetime.utcnow().isoformat()
            if cur.fetchone():
                if fields:
                    sets = ", ".join(f"{k} = ?" for k in fields)
                    params = list(fields.values()) + [now, mentee_id]
                    cur.execute(
                        f"UPDATE mentee_preferences SET {sets}, updated_at = ? "
                        f"WHERE mentee_id = ?",
                        params,
                    )
            else:
                cols = ["mentee_id"] + list(fields) + ["updated_at"]
                placeholders = ", ".join("?" for _ in cols)
                vals = [mentee_id] + list(fields.values()) + [now]
                cur.execute(
                    f"INSERT INTO mentee_preferences ({', '.join(cols)}) "
                    f"VALUES ({placeholders})",
                    vals,
                )
            conn.commit()
        finally:
            self._close(conn)

    # ---------- recommendation ----------
    def _score_pair(
        self, pref: sqlite3.Row, mentor: sqlite3.Row,
    ) -> Dict[str, Any]:
        reasons: List[str] = []
        score = 0

        mentee_course = _norm_course(pref["course"])
        mentor_course = _norm_course(mentor["course"])
        if mentee_course and mentor_course and mentee_course == mentor_course:
            score += 30
            reasons.append(f"course match (+30): {mentor_course}")

        mentee_avail = _parse_csv(pref["availability_csv"])
        mentor_avail = _parse_csv(mentor["availability_csv"])
        avail_overlap = _overlap(mentee_avail, mentor_avail)
        if avail_overlap:
            pts = min(20 * len(avail_overlap), 40)
            score += pts
            reasons.append(
                f"availability overlap (+{pts}): {', '.join(avail_overlap)}"
            )

        mentee_langs = _parse_csv(pref["preferred_languages_csv"])
        mentor_langs = _parse_csv(mentor["languages_csv"])
        lang_overlap = _overlap(mentee_langs, mentor_langs)
        if lang_overlap:
            pts = min(15 * len(lang_overlap), 30)
            score += pts
            reasons.append(
                f"language overlap (+{pts}): {', '.join(lang_overlap)}"
            )

        goals = _parse_csv(pref["learning_goals_csv"])
        strengths = _parse_csv(mentor["strengths_csv"])
        sg_overlap = _overlap(goals, strengths)
        if sg_overlap:
            pts = min(10 * len(sg_overlap), 30)
            score += pts
            reasons.append(
                f"strength↔goal overlap (+{pts}): {', '.join(sg_overlap)}"
            )

        max_mentees = mentor["max_mentees"] if mentor["max_mentees"] is not None else 3
        try:
            active = int(self._count_active_mentees(int(mentor["mentor_id"])))
        except Exception:
            active = 0
        if max_mentees is not None and active >= max_mentees:
            score -= 50
            reasons.append(
                f"mentor at capacity (-50): {active}/{max_mentees}"
            )

        return {
            "mentor_id": int(mentor["mentor_id"]),
            "score": int(score),
            "reasons": reasons,
        }

    def recommend_mentors(
        self, mentee_id: int, top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        if not isinstance(mentee_id, int) or mentee_id <= 0:
            raise MentoringMatchingError("mentee_id must be a positive integer")
        if not isinstance(top_n, int) or top_n <= 0:
            raise MentoringMatchingError("top_n must be a positive integer")

        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM mentee_preferences WHERE mentee_id = ?",
                (mentee_id,),
            )
            pref = cur.fetchone()
            if pref is None:
                raise MentoringMatchingError(
                    f"No preferences found for mentee {mentee_id}; call "
                    f"upsert_mentee_preferences first."
                )

            cur.execute("SELECT * FROM mentor_profiles")
            mentors = cur.fetchall()

            scored = [self._score_pair(pref, m) for m in mentors]
            scored.sort(key=lambda r: r["score"], reverse=True)
            top = scored[:top_n]

            now = datetime.utcnow().isoformat()
            for rec in top:
                cur.execute(
                    "INSERT INTO mentor_match_recommendations "
                    "(mentee_id, mentor_id, score, reasons_json, created_at, status) "
                    "VALUES (?, ?, ?, ?, ?, 'suggested')",
                    (
                        mentee_id,
                        rec["mentor_id"],
                        rec["score"],
                        json.dumps(rec["reasons"]),
                        now,
                    ),
                )
                rec["recommendation_id"] = cur.lastrowid
            conn.commit()
            return top
        finally:
            self._close(conn)

    def _set_recommendation_status(self, recommendation_id: int, status: str) -> None:
        if status not in ("accepted", "declined"):
            raise MentoringMatchingError("status must be accepted/declined")
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE mentor_match_recommendations SET status = ? "
                "WHERE recommendation_id = ?",
                (status, recommendation_id),
            )
            if cur.rowcount == 0:
                raise MentoringMatchingError(
                    f"Recommendation {recommendation_id} not found"
                )
            conn.commit()
        finally:
            self._close(conn)

    def accept_recommendation(self, recommendation_id: int) -> None:
        self._set_recommendation_status(recommendation_id, "accepted")

    def decline_recommendation(self, recommendation_id: int) -> None:
        self._set_recommendation_status(recommendation_id, "declined")

    # ---------- outcomes ----------
    def record_outcome(
        self,
        pair_id: int,
        confidence_pre: int,
        confidence_post: int,
        goals_met: int,
        satisfaction: int,
        would_recommend: int,
        narrative: Optional[str] = None,
    ) -> int:
        if not isinstance(pair_id, int) or pair_id <= 0:
            raise MentoringMatchingError("pair_id must be a positive integer")
        try:
            confidence_pre = int(confidence_pre)
            confidence_post = int(confidence_post)
            goals_met = int(goals_met)
            satisfaction = int(satisfaction)
            would_recommend = int(would_recommend)
        except (TypeError, ValueError) as exc:
            raise MentoringMatchingError("numeric fields must be ints") from exc
        if not 0 <= goals_met <= 100:
            raise MentoringMatchingError("goals_met must be 0..100")
        if not 1 <= satisfaction <= 5:
            raise MentoringMatchingError("satisfaction must be 1..5")
        if would_recommend not in (0, 1):
            raise MentoringMatchingError("would_recommend must be 0 or 1")

        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO mentoring_outcomes "
                "(pair_id, confidence_pre, confidence_post, goals_met, "
                "satisfaction, would_recommend, narrative, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pair_id, confidence_pre, confidence_post, goals_met,
                    satisfaction, would_recommend, narrative,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            self._close(conn)

    def get_outcome(self, pair_id: int) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM mentoring_outcomes WHERE pair_id = ? "
                "ORDER BY recorded_at DESC, outcome_id DESC LIMIT 1",
                (pair_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            self._close(conn)

    def outcomes_summary(self, mentor_id: Optional[int] = None) -> Dict[str, Any]:
        """Aggregate outcomes; if mentor_id given, restrict to pairs accepted
        for that mentor (via mentor_match_recommendations.status='accepted')."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            if mentor_id is None:
                cur.execute("SELECT * FROM mentoring_outcomes")
            else:
                cur.execute(
                    "SELECT o.* FROM mentoring_outcomes o "
                    "WHERE o.pair_id IN (SELECT recommendation_id "
                    "FROM mentor_match_recommendations "
                    "WHERE mentor_id = ? AND status = 'accepted')",
                    (mentor_id,),
                )
            rows = cur.fetchall()
            count = len(rows)
            if not count:
                return {
                    "count": 0,
                    "avg_confidence_delta": 0.0,
                    "avg_satisfaction": 0.0,
                    "pct_would_recommend": 0.0,
                }
            deltas = [(r["confidence_post"] or 0) - (r["confidence_pre"] or 0)
                      for r in rows]
            sats = [r["satisfaction"] or 0 for r in rows]
            recs = [r["would_recommend"] or 0 for r in rows]
            return {
                "count": count,
                "avg_confidence_delta": round(sum(deltas) / count, 2),
                "avg_satisfaction": round(sum(sats) / count, 2),
                "pct_would_recommend": round(100.0 * sum(recs) / count, 2),
            }
        finally:
            self._close(conn)

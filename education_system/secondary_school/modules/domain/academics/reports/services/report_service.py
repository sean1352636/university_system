"""Report and analytics service — queries existing data for summaries."""

import logging
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def attendance_summary(self, year_group=None):
        conn = self._conn()
        try:
            sql = """SELECT s.student_id as sid, s.first_name, s.last_name, s.year_group,
                            COUNT(*) as total,
                            SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present,
                            SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as absent,
                            SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) as late
                     FROM attendance_records a
                     JOIN students s ON a.student_id = s.id
                     WHERE 1=1"""
            params = []
            if year_group:
                sql += " AND s.year_group = ?"
                params.append(year_group)
            sql += " GROUP BY s.id ORDER BY s.last_name"
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["pct"] = round(d["present"] / d["total"] * 100, 1) if d["total"] else 0
                results.append(d)
            return results
        finally:
            conn.close()

    def grade_summary(self, year_group=None):
        conn = self._conn()
        try:
            sql = """SELECT s.student_id as sid, s.first_name, s.last_name, s.year_group,
                            subj.title as subject_title,
                            ROUND(AVG(g.score), 1) as avg_score,
                            COUNT(g.id) as assessments
                     FROM grades g
                     JOIN students s ON g.student_id = s.id
                     JOIN subjects subj ON g.subject_id = subj.id
                     WHERE g.score IS NOT NULL"""
            params = []
            if year_group:
                sql += " AND s.year_group = ?"
                params.append(year_group)
            sql += " GROUP BY s.id, subj.id ORDER BY s.last_name, subj.title"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def behaviour_summary(self, year_group=None):
        conn = self._conn()
        try:
            sql = """SELECT s.student_id as sid, s.first_name, s.last_name, s.year_group,
                            SUM(CASE WHEN b.type = 'positive' THEN b.points ELSE 0 END) as positive_pts,
                            SUM(CASE WHEN b.type = 'negative' THEN b.points ELSE 0 END) as negative_pts,
                            COUNT(*) as total_incidents
                     FROM behaviour_records b
                     JOIN students s ON b.student_id = s.id
                     WHERE 1=1"""
            params = []
            if year_group:
                sql += " AND s.year_group = ?"
                params.append(year_group)
            sql += " GROUP BY s.id ORDER BY s.last_name"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def subject_performance(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT subj.subject_code, subj.title,
                          COUNT(DISTINCT g.student_id) as students,
                          ROUND(AVG(g.score), 1) as avg_score,
                          MIN(g.score) as min_score,
                          MAX(g.score) as max_score
                   FROM grades g
                   JOIN subjects subj ON g.subject_id = subj.id
                   WHERE g.score IS NOT NULL
                   GROUP BY subj.id ORDER BY subj.title"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def year_group_overview(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT year_group,
                          COUNT(*) as total,
                          SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                          SUM(CASE WHEN sen_status != 'none' THEN 1 ELSE 0 END) as sen,
                          SUM(pupil_premium) as pp
                   FROM students GROUP BY year_group ORDER BY year_group"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

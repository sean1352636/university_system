"""Question-level analysis service for assessments."""
from education_system.college_system.core.exceptions import QuestionAnalysisError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class QuestionAnalysisService:
    """Analyse assessment performance at question and topic level."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ------------------------------------------------------------------
    # Assessment Papers
    # ------------------------------------------------------------------

    def create_paper(self, course_id, title, total_marks, exam_board=None,
                     paper_code=None, assessment_date=None, academic_year=None,
                     created_by=None):
        """Create an assessment paper record."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO assessment_papers
                   (course_id, title, total_marks, exam_board, paper_code,
                    assessment_date, academic_year, created_by,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (course_id, title, total_marks, exam_board, paper_code,
                 assessment_date, academic_year, created_by),
            )
            conn.commit()
            logger.info("Created assessment paper '%s' (id=%s)", title, cur.lastrowid)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to create paper: %s", exc)
            raise QuestionAnalysisError(f"Failed to create paper: {exc}") from exc
        finally:
            conn.close()

    def list_papers(self, course_id=None, academic_year=None):
        """List assessment papers with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM assessment_papers WHERE 1=1"
            params = []
            if course_id is not None:
                sql += " AND course_id = ?"
                params.append(course_id)
            if academic_year is not None:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY assessment_date DESC, id DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list papers: %s", exc)
            raise QuestionAnalysisError(f"Failed to list papers: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Paper Questions
    # ------------------------------------------------------------------

    def add_question(self, paper_id, question_number, topic, max_marks,
                     subtopic=None, skill_type=None, difficulty=None,
                     specification_ref=None):
        """Add a question to an assessment paper."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO paper_questions
                   (paper_id, question_number, topic, subtopic, max_marks,
                    skill_type, difficulty, specification_ref, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (paper_id, question_number, topic, subtopic, max_marks,
                 skill_type, difficulty, specification_ref),
            )
            conn.commit()
            logger.info("Added question %s to paper %s", question_number, paper_id)
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to add question: %s", exc)
            raise QuestionAnalysisError(f"Failed to add question: {exc}") from exc
        finally:
            conn.close()

    def list_questions(self, paper_id):
        """List all questions for a paper."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM paper_questions WHERE paper_id = ? ORDER BY question_number",
                (paper_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to list questions: %s", exc)
            raise QuestionAnalysisError(f"Failed to list questions: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Student Scores
    # ------------------------------------------------------------------

    def record_score(self, question_id, student_id, marks_awarded):
        """Record a student's score for a question."""
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO student_question_scores
                   (question_id, student_id, marks_awarded, created_at)
                   VALUES (?, ?, ?, datetime('now'))""",
                (question_id, student_id, marks_awarded),
            )
            conn.commit()
            return cur.lastrowid
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to record score: %s", exc)
            raise QuestionAnalysisError(f"Failed to record score: {exc}") from exc
        finally:
            conn.close()

    def bulk_record_scores(self, paper_id, scores_data):
        """Bulk-record scores for a paper.

        Args:
            paper_id: The assessment paper id.
            scores_data: list of dicts with keys student_id, question_number, marks.
        """
        conn = self._conn()
        try:
            questions = conn.execute(
                "SELECT id, question_number FROM paper_questions WHERE paper_id = ?",
                (paper_id,),
            ).fetchall()
            q_map = {row["question_number"]: row["id"] for row in questions}

            for entry in scores_data:
                qnum = str(entry["question_number"])
                qid = q_map.get(qnum)
                if qid is None:
                    raise QuestionAnalysisError(
                        f"Question number '{qnum}' not found on paper {paper_id}"
                    )
                conn.execute(
                    """INSERT INTO student_question_scores
                       (question_id, student_id, marks_awarded, created_at)
                       VALUES (?, ?, ?, datetime('now'))""",
                    (qid, entry["student_id"], entry["marks"]),
                )
            conn.commit()
            logger.info("Bulk recorded %d scores for paper %s", len(scores_data), paper_id)
            return len(scores_data)
        except QuestionAnalysisError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Failed to bulk record scores: %s", exc)
            raise QuestionAnalysisError(f"Failed to bulk record scores: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def get_question_analysis(self, paper_id):
        """Per-question statistics: avg marks, percentage, facility index."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT pq.id, pq.question_number, pq.topic, pq.subtopic,
                          pq.max_marks, pq.skill_type, pq.difficulty,
                          COUNT(sqs.id) AS num_students,
                          COALESCE(AVG(sqs.marks_awarded), 0) AS avg_marks,
                          CASE WHEN pq.max_marks > 0
                               THEN ROUND(COALESCE(AVG(sqs.marks_awarded), 0) * 100.0 / pq.max_marks, 1)
                               ELSE 0 END AS avg_pct,
                          CASE WHEN pq.max_marks > 0
                               THEN ROUND(COALESCE(AVG(sqs.marks_awarded), 0) * 1.0 / pq.max_marks, 3)
                               ELSE 0 END AS facility_index
                   FROM paper_questions pq
                   LEFT JOIN student_question_scores sqs ON sqs.question_id = pq.id
                   WHERE pq.paper_id = ?
                   GROUP BY pq.id
                   ORDER BY pq.question_number""",
                (paper_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get question analysis: %s", exc)
            raise QuestionAnalysisError(f"Failed to get question analysis: {exc}") from exc
        finally:
            conn.close()

    def get_topic_analysis(self, paper_id):
        """Aggregate analysis by topic."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT pq.topic,
                          SUM(pq.max_marks) AS total_max,
                          ROUND(AVG(sqs.marks_awarded), 2) AS avg_marks_per_q,
                          ROUND(SUM(sqs.marks_awarded) * 100.0 / NULLIF(SUM(pq.max_marks * sub.cnt), 0), 1) AS avg_pct,
                          COUNT(DISTINCT pq.id) AS num_questions
                   FROM paper_questions pq
                   LEFT JOIN student_question_scores sqs ON sqs.question_id = pq.id
                   LEFT JOIN (SELECT question_id, COUNT(*) AS cnt FROM student_question_scores GROUP BY question_id) sub
                       ON sub.question_id = pq.id
                   WHERE pq.paper_id = ?
                   GROUP BY pq.topic
                   ORDER BY avg_pct ASC""",
                (paper_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get topic analysis: %s", exc)
            raise QuestionAnalysisError(f"Failed to get topic analysis: {exc}") from exc
        finally:
            conn.close()

    def get_cohort_weaknesses(self, paper_id, threshold=50):
        """Topics where average percentage is below threshold."""
        conn = self._conn()
        try:
            topics = self.get_topic_analysis(paper_id)
            return [t for t in topics if t.get("avg_pct") is not None and t["avg_pct"] < threshold]
        except Exception as exc:
            logger.error("Failed to get cohort weaknesses: %s", exc)
            raise QuestionAnalysisError(f"Failed to get cohort weaknesses: {exc}") from exc
        finally:
            conn.close()

    def get_student_analysis(self, paper_id, student_id):
        """Per-student breakdown for a paper."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT pq.question_number, pq.topic, pq.subtopic, pq.max_marks,
                          pq.skill_type, pq.difficulty,
                          COALESCE(sqs.marks_awarded, 0) AS marks_awarded,
                          CASE WHEN pq.max_marks > 0
                               THEN ROUND(COALESCE(sqs.marks_awarded, 0) * 100.0 / pq.max_marks, 1)
                               ELSE 0 END AS pct
                   FROM paper_questions pq
                   LEFT JOIN student_question_scores sqs
                       ON sqs.question_id = pq.id AND sqs.student_id = ?
                   WHERE pq.paper_id = ?
                   ORDER BY pq.question_number""",
                (student_id, paper_id),
            ).fetchall()
            results = [dict(r) for r in rows]
            total_marks = sum(r["marks_awarded"] for r in results)
            total_max = sum(r["max_marks"] for r in results)
            return {
                "student_id": student_id,
                "paper_id": paper_id,
                "total_marks": total_marks,
                "total_max": total_max,
                "overall_pct": round(total_marks * 100.0 / total_max, 1) if total_max else 0,
                "questions": results,
            }
        except Exception as exc:
            logger.error("Failed to get student analysis: %s", exc)
            raise QuestionAnalysisError(f"Failed to get student analysis: {exc}") from exc
        finally:
            conn.close()

    def compare_papers(self, paper_ids):
        """Compare performance across multiple papers."""
        conn = self._conn()
        try:
            results = []
            for pid in paper_ids:
                row = conn.execute(
                    """SELECT ap.id, ap.title, ap.total_marks,
                              COUNT(DISTINCT sqs.student_id) AS num_students,
                              ROUND(AVG(student_totals.total), 2) AS avg_total,
                              CASE WHEN ap.total_marks > 0
                                   THEN ROUND(AVG(student_totals.total) * 100.0 / ap.total_marks, 1)
                                   ELSE 0 END AS avg_pct
                       FROM assessment_papers ap
                       LEFT JOIN paper_questions pq ON pq.paper_id = ap.id
                       LEFT JOIN student_question_scores sqs ON sqs.question_id = pq.id
                       LEFT JOIN (
                           SELECT sqs2.student_id, pq2.paper_id,
                                  SUM(sqs2.marks_awarded) AS total
                           FROM student_question_scores sqs2
                           JOIN paper_questions pq2 ON pq2.id = sqs2.question_id
                           WHERE pq2.paper_id = ?
                           GROUP BY sqs2.student_id
                       ) student_totals ON student_totals.paper_id = ap.id
                       WHERE ap.id = ?
                       GROUP BY ap.id""",
                    (pid, pid),
                ).fetchone()
                if row:
                    results.append(dict(row))
            return results
        except Exception as exc:
            logger.error("Failed to compare papers: %s", exc)
            raise QuestionAnalysisError(f"Failed to compare papers: {exc}") from exc
        finally:
            conn.close()

    def get_skill_analysis(self, paper_id):
        """Aggregate analysis by skill_type."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT pq.skill_type,
                          COUNT(DISTINCT pq.id) AS num_questions,
                          SUM(pq.max_marks) AS total_max,
                          ROUND(AVG(sqs.marks_awarded), 2) AS avg_marks_per_q,
                          CASE WHEN SUM(pq.max_marks) > 0
                               THEN ROUND(
                                   SUM(sqs.marks_awarded) * 100.0 /
                                   (SELECT SUM(pq2.max_marks * COALESCE(sub2.cnt, 1))
                                    FROM paper_questions pq2
                                    LEFT JOIN (SELECT question_id, COUNT(*) AS cnt
                                               FROM student_question_scores GROUP BY question_id) sub2
                                        ON sub2.question_id = pq2.id
                                    WHERE pq2.paper_id = ? AND pq2.skill_type = pq.skill_type), 1)
                               ELSE 0 END AS avg_pct
                   FROM paper_questions pq
                   LEFT JOIN student_question_scores sqs ON sqs.question_id = pq.id
                   WHERE pq.paper_id = ?
                   GROUP BY pq.skill_type
                   ORDER BY avg_pct ASC""",
                (paper_id, paper_id),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to get skill analysis: %s", exc)
            raise QuestionAnalysisError(f"Failed to get skill analysis: {exc}") from exc
        finally:
            conn.close()

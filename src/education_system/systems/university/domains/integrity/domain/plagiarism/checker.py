"""Compatibility facade over the university's similarity-check rules.

The old engine (word 3-grams + difflib over a whole-module pool, its own
tables created at runtime, NLTK downloads) is in ``remove/``. This class
keeps the method names older screens call and answers them from
``university/application/integrity/plagiarism_checks``, ``integrity_review`` and
``integrity_access``.

Pass ``who`` (an ``integrity_access.Person``) or ``auth`` (an object with
``current_user``) and every call is limited to what that person may see
and do. Without either, the facade runs as the system — only for
background jobs; screens must always pass the signed-in user.
"""

from __future__ import annotations

from contextlib import contextmanager

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.application.integrity import plagiarism_text as ptext
from education_system.systems.university.domains.integrity.domain.plagiarism.exceptions import (  # noqa: E501
    FileProcessingError,
    PlagiarismCheckerError,
)


class PlagiarismChecker:
    def __init__(self, db_path=None, *, who=None, auth=None):
        from education_system.systems.university.infrastructure.database import db as _db
        self.db_path = str(db_path or _db.DEFAULT_DB_PATH)
        self._who = who
        self._auth = auth

    # ── plumbing ────────────────────────────────────────────────────────

    def get_db_connection(self):
        from education_system.systems.university.domains.integrity.domain.plagiarism.db import (  # noqa: E501
            get_safe_db_connection,
        )
        return get_safe_db_connection(self.db_path)

    @contextmanager
    def _conn(self):
        """A connection that commits on success and lets refusals
        (``PermissionError`` / ``ValueError``) through unchanged."""
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection(self.db_path, row_factory=False)
        try:
            access.ensure(conn)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _person(self, conn):
        if self._who is not None:
            return self._who
        user = getattr(self._auth, "current_user", None) if self._auth else None
        return access.from_user(conn, user) if user else None

    def init_db(self):
        """Tables come from migrations; this only makes sure they exist."""
        with self._conn():
            pass

    # ── text ────────────────────────────────────────────────────────────

    def extract_text_from_file(self, file_path):
        from education_system.systems.university.infrastructure.integrity import text_extract
        try:
            return text_extract.extract(file_path), text_extract.file_type(file_path)
        except ValueError as exc:
            raise FileProcessingError(str(exc)) from exc

    def preprocess_text(self, text):
        return ptext.prepare(text).tokens

    def compute_ngrams(self, tokens, n=6):
        return set(ptext.shingles(list(tokens), n))

    def compute_similarity(self, ngrams1, ngrams2):
        a, b = set(ngrams1), set(ngrams2)
        return len(a & b) / len(a) if a else 0.0

    def get_content_hash(self, content):
        return checks.content_hash(content)

    # ── documents ───────────────────────────────────────────────────────

    def add_document_to_repository(self, title, content, author_id, module_code, file_type,
                                   kind="submission"):
        with self._conn() as conn:
            who = self._person(conn)
            if who is not None:
                return checks.add_document(conn, who, title=title, content=content,
                                           file_type=file_type, module_code=module_code,
                                           kind=kind)
            return checks._store(conn, title=title, content=content, file_type=file_type,
                                 module_code=module_code, kind=kind, author_id=author_id)

    def get_document_details(self, document_id):
        with self._conn() as conn:
            who = self._person(conn)
            if who is not None:
                doc = checks.document(conn, who, document_id)
            else:
                doc = access.one(conn, "SELECT * FROM document_repository WHERE id = ?",
                                 (document_id,))
                if not doc:
                    raise ValueError(f"Document with ID {document_id} not found")
            name = conn.execute("SELECT first_name || ' ' || last_name FROM users WHERE id = ?",
                                (doc["author_id"],)).fetchone()
            latest = access.one(conn, "SELECT id AS result_id, similarity_score, status, "
                                      "check_date, threshold_used FROM plagiarism_results "
                                      "WHERE document_id = ? ORDER BY id DESC LIMIT 1",
                                (document_id,))
            return {**doc, "author_name": name[0] if name else "Unknown",
                    "latest_check": latest}

    def search_repository(self, search_term=None, author_id=None, module_code=None):
        with self._conn() as conn:
            who = self._person(conn)
            if who is not None:
                rows = checks.documents(conn, who, module_code=module_code, search=search_term)
            else:
                rows = access.dicts(conn.execute(
                    "SELECT id, title, author_id, module_code, submission_date, file_type, "
                    "word_count FROM document_repository WHERE (? IS NULL OR module_code = ?) "
                    "AND (? IS NULL OR title LIKE ? OR content LIKE ?) ORDER BY id DESC",
                    (module_code, module_code, search_term, f"%{search_term}%",
                     f"%{search_term}%")))
            if author_id:
                rows = [r for r in rows if r["author_id"] == author_id]
            return rows

    def delete_document(self, document_id):
        with self._conn() as conn:
            who = self._person(conn)
            if who is None:
                raise PermissionError("Deleting a document needs a signed-in integrity officer")
            checks.delete_document(conn, who, document_id)
            return True

    # ── checks ──────────────────────────────────────────────────────────

    def check_plagiarism(self, document_id, checker_id=None, threshold=None):
        """Run a check. ``threshold`` is ignored: the module's own review
        threshold applies, so a result means the same wherever it ran."""
        try:
            with self._conn() as conn:
                result_id = checks.run_check(conn, document_id, who=self._person(conn))
                row = access.one(conn, "SELECT * FROM plagiarism_results WHERE id = ?",
                                 (result_id,))
                matches = conn.execute("SELECT matched_document_id, score FROM "
                                       "plagiarism_matches WHERE result_id = ? ORDER BY score "
                                       "DESC", (result_id,)).fetchall()
        except (ValueError, PermissionError):
            raise
        except Exception as exc:
            raise PlagiarismCheckerError(f"Plagiarism check failed: {exc}") from exc
        return {"result_id": result_id, "document_id": document_id,
                "match_type": "similarity",
                "matches": [(m[0], None, m[1]) for m in matches],
                "highest_similarity": row["similarity_score"], "status": row["status"],
                "threshold_used": row["threshold_used"],
                "review_status": row["review_status"]}

    def get_plagiarism_result(self, result_id):
        with self._conn() as conn:
            who = self._person(conn)
            if who is not None:
                detail = review.result_detail(conn, who, result_id)
            else:
                detail = review._result(conn, result_id)
            title = conn.execute("SELECT title FROM document_repository WHERE id = ?",
                                 (detail.get("matched_document_id"),)).fetchone()
            return {"result_id": detail["id"], "document_id": detail["document_id"],
                    "document_title": detail["title"],
                    "matched_document_id": detail["matched_document_id"],
                    "matched_document_title": title[0] if title else None,
                    "similarity_score": detail["similarity_score"],
                    "check_date": detail["check_date"], "status": detail["status"],
                    "report": detail["report"], "threshold_used": detail["threshold_used"],
                    "review_status": detail.get("review_status"),
                    "matches": detail.get("matches", [])}

    def get_document_check_history(self, document_id):
        with self._conn() as conn:
            who = self._person(conn)
            if who is not None:
                checks.document(conn, who, document_id)
            return access.dicts(conn.execute(
                "SELECT id AS result_id, matched_document_id, similarity_score, check_date, "
                "status, threshold_used, review_status FROM plagiarism_results WHERE "
                "document_id = ? ORDER BY id DESC", (document_id,)))

    def get_statistics(self):
        with self._conn() as conn:
            who = self._person(conn)
            docs = checks.documents(conn, who, limit=100000) if who else access.dicts(
                conn.execute("SELECT id, module_code FROM document_repository"))
            rows = review.results(conn, who, limit=100000) if who else access.dicts(
                conn.execute("SELECT r.id, d.title, r.similarity_score, r.status, r.check_date "
                             "FROM plagiarism_results r JOIN document_repository d ON "
                             "d.id = r.document_id ORDER BY r.id DESC"))
            by_module: dict = {}
            for d in docs:
                by_module[d["module_code"]] = by_module.get(d["module_code"], 0) + 1
            status_counts: dict = {}
            for r in rows:
                status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
            return {"total_documents": len(docs), "total_checks": len(rows),
                    "status_counts": status_counts,
                    "recent_checks": [{"result_id": r["id"], "document_title": r["title"],
                                       "similarity_score": r["similarity_score"],
                                       "status": r["status"], "check_date": r["check_date"]}
                                      for r in rows[:10]],
                    "documents_by_module": by_module}

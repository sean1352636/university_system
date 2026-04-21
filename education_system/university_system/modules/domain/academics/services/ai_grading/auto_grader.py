"""Heuristic auto-grading for text-based assignment submissions.

The grader scores five criteria out of a weighted 100-point scale, then
rescales to the assignment's ``max_marks``. It is deliberately crude —
the UI wraps every result in a "suggested" grade that a human still
needs to accept or edit.

Criteria and default weights
----------------------------

- **Length** (20 pts): below ``min_words`` scores 0; between ``min_words``
  and ``ideal_min`` scales linearly to the weight; ``ideal_min`` to
  ``ideal_max`` earns the full weight; above ``ideal_max`` decays back
  down so verbose submissions aren't rewarded.
- **Keyword coverage** (30 pts): unique terms extracted from the rubric
  criteria descriptions (or the assignment title/description if no
  rubric) and counted inside the submission text. Fraction found ×
  weight.
- **Structure** (20 pts): number of paragraphs and sentence-length
  variety. Single-paragraph or single-sentence submissions score
  poorly.
- **Readability** (15 pts): average sentence length and type/token
  ratio. Extreme values in either direction lose points.
- **Originality** (15 pts): inverse of the highest plagiarism
  similarity returned by ``PlagiarismChecker.check_plagiarism``. A
  100% match earns 0; below 10% earns the full weight.

The module returns structured results so the UI can render the
rationale per criterion and the caller can decide whether to show,
accept, or edit the suggested grade.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    sqlite3,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CriterionResult:
    name: str
    weight: float
    earned: float
    note: str


@dataclass
class AutoGradingResult:
    total_score: float          # final grade, in assignment's native scale
    max_marks: float            # for convenience on the caller side
    weighted_percent: float     # 0..100, before rescaling to max_marks
    breakdown: List[CriterionResult] = field(default_factory=list)
    overall_rationale: str = ""
    confidence: str = "medium"  # 'low' / 'medium' / 'high'
    error: Optional[str] = None

    def feedback_text(self) -> str:
        """Render a multi-line breakdown suitable for the feedback box."""
        lines = ["Auto-grader — suggested rationale (review before releasing):",
                 ""]
        for c in self.breakdown:
            lines.append(f"  · {c.name}: {c.earned:g} / {c.weight:g}"
                         f"    — {c.note}")
        lines.append("")
        lines.append(f"Suggested grade: {self.total_score:.1f} / "
                     f"{self.max_marks:g}  (confidence: {self.confidence})")
        if self.overall_rationale:
            lines.append("")
            lines.append(self.overall_rationale)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+", re.UNICODE)

# A compact English stopword list so keyword extraction doesn't pick up
# every "the" / "of" / "and". Intentionally hard-coded to avoid pulling
# NLTK as a hard dependency.
_STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be
because been before being below between both but by can can't cannot could
couldn't did didn't do does doesn't doing don don't down during each few for
from further had hadn't has hasn't have haven't having he he'd he'll he's
her here here's hers herself him himself his how how's i i'd i'll i'm i've
if in into is isn't it it's its itself let's me more most mustn't my myself
no nor not of off on once only or other ought our ours ourselves out over
own same shan't she she'd she'll she's should shouldn't so some such than
that that's the their theirs them themselves then there there's these they
they'd they'll they're they've this those through to too under until up
very was wasn't we we'd we'll we're we've were weren't what what's when
when's where where's which while who who's whom why why's with won't would
wouldn't you you'd you'll you're you've your yours yourself yourselves
""".split())


def _tokenise(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


def _sentences(text: str) -> List[str]:
    # Use regex to approximate sentences. Good enough for heuristics.
    sents = _SENTENCE_RE.findall(text)
    if sents:
        return [s.strip() for s in sents if s.strip()]
    # Single-sentence submissions without terminal punctuation.
    stripped = text.strip()
    return [stripped] if stripped else []


def _paragraph_count(text: str) -> int:
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return len(paragraphs)


def _extract_keywords(source: str, limit: int = 20) -> List[str]:
    """Strip stopwords / short words from *source* and keep the top `limit`
    most frequent tokens. Falls back to an empty list if nothing useful.
    """
    freq: Dict[str, int] = {}
    for tok in _tokenise(source):
        if len(tok) < 4 or tok in _STOPWORDS or tok.isdigit():
            continue
        freq[tok] = freq.get(tok, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:limit]]


# ---------------------------------------------------------------------------
# Per-criterion scorers
# ---------------------------------------------------------------------------


def _score_length(text: str, weight: float,
                  min_words: int = 50, ideal_min: int = 120,
                  ideal_max: int = 2000) -> CriterionResult:
    words = _tokenise(text)
    n = len(words)
    if n == 0:
        earned, note = 0.0, "submission is empty"
    elif n < min_words:
        earned = 0.0
        note = f"word count ({n}) is below the minimum of {min_words}"
    elif n < ideal_min:
        scale = (n - min_words) / max(ideal_min - min_words, 1)
        earned = weight * scale
        note = f"word count ({n}) is on the light side"
    elif n <= ideal_max:
        earned = weight
        note = f"word count ({n}) is in range"
    else:
        decay = max(0.0, 1 - (n - ideal_max) / ideal_max)
        earned = weight * max(0.5, decay)
        note = f"word count ({n}) is longer than typical — some decay"
    return CriterionResult("Length", weight, round(earned, 1), note)


def _score_keyword_coverage(text: str, weight: float,
                             keywords: List[str]) -> CriterionResult:
    if not keywords:
        return CriterionResult(
            "Rubric keyword coverage", weight, weight * 0.5,
            "no rubric keywords available — credited at half weight",
        )
    tokens = set(_tokenise(text))
    hit = [kw for kw in keywords if kw in tokens]
    frac = len(hit) / len(keywords)
    earned = weight * frac
    note = f"covered {len(hit)} of {len(keywords)} target keywords"
    if hit and len(hit) <= 8:
        note += f" ({', '.join(hit)})"
    return CriterionResult("Rubric keyword coverage", weight,
                           round(earned, 1), note)


def _score_structure(text: str, weight: float) -> CriterionResult:
    paras = _paragraph_count(text)
    sents = _sentences(text)
    n_sents = len(sents)
    if n_sents == 0:
        return CriterionResult("Structure", weight, 0.0,
                               "no sentence-like text found")

    # Encourage multiple paragraphs.
    para_score = min(1.0, paras / 4.0)
    # Encourage sentence variety.
    sent_lens = [len(s.split()) for s in sents]
    if sent_lens and len(sent_lens) > 1:
        mean = sum(sent_lens) / len(sent_lens)
        variance = sum((x - mean) ** 2 for x in sent_lens) / len(sent_lens)
        stdev = variance ** 0.5
        # Normalised coefficient of variation — 0.3..0.7 is a healthy range.
        cv = stdev / mean if mean else 0.0
        variety_score = min(1.0, cv / 0.5)
    else:
        variety_score = 0.3

    combined = 0.6 * para_score + 0.4 * variety_score
    earned = round(weight * combined, 1)
    note = (f"{paras} paragraph(s), {n_sents} sentence(s); "
            f"paragraph score {para_score:.2f}, variety {variety_score:.2f}")
    return CriterionResult("Structure", weight, earned, note)


def _score_readability(text: str, weight: float) -> CriterionResult:
    sents = _sentences(text)
    if not sents:
        return CriterionResult("Readability", weight, 0.0, "no sentences")
    tokens = _tokenise(text)
    if not tokens:
        return CriterionResult("Readability", weight, 0.0, "no words")

    words_per_sent = len(tokens) / len(sents)
    unique = len(set(tokens))
    type_token_ratio = unique / len(tokens)

    # Target: 10–25 words per sentence, TTR ≥ 0.35.
    if 10 <= words_per_sent <= 25:
        length_score = 1.0
    elif words_per_sent < 10:
        length_score = words_per_sent / 10.0
    else:
        length_score = max(0.2, 1.0 - (words_per_sent - 25) / 25.0)
    ttr_score = min(1.0, type_token_ratio / 0.35)

    combined = 0.5 * length_score + 0.5 * ttr_score
    earned = round(weight * combined, 1)
    note = (f"avg {words_per_sent:.1f} words/sentence, "
            f"type/token ratio {type_token_ratio:.2f}")
    return CriterionResult("Readability", weight, earned, note)


def _score_originality(weight: float,
                       plagiarism_similarity: Optional[float],
                       compared_count: int = 0) -> CriterionResult:
    if plagiarism_similarity is None:
        return CriterionResult(
            "Originality", weight, weight * 0.5,
            "plagiarism scan unavailable — credited at half weight",
        )
    sim = max(0.0, min(1.0, plagiarism_similarity))
    # 0.0 sim → full marks, 1.0 sim → 0 marks, decay starts at sim 0.1.
    if sim <= 0.1:
        frac = 1.0
    elif sim >= 0.8:
        frac = 0.0
    else:
        frac = 1.0 - (sim - 0.1) / 0.7
    earned = round(weight * frac, 1)
    note = (f"highest similarity against {compared_count} prior "
            f"submission(s): {sim * 100:.1f}%")
    return CriterionResult("Originality", weight, earned, note)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_submission(
    text: str,
    max_marks: float,
    *,
    rubric_keywords: Optional[List[str]] = None,
    assignment_description: Optional[str] = None,
    plagiarism_similarity: Optional[float] = None,
    compared_count: int = 0,
) -> AutoGradingResult:
    """Score *text* for an assignment worth *max_marks* points.

    If *rubric_keywords* is falsy, keywords are extracted from
    *assignment_description* as a fallback. *plagiarism_similarity* is
    expected in the range 0..1 (as returned by ``PlagiarismChecker``).
    """
    max_marks = float(max_marks) if max_marks else 100.0
    kw = rubric_keywords
    if not kw and assignment_description:
        kw = _extract_keywords(assignment_description, limit=10)
    kw = kw or []

    breakdown = [
        _score_length(text, 20.0),
        _score_keyword_coverage(text, 30.0, kw),
        _score_structure(text, 20.0),
        _score_readability(text, 15.0),
        _score_originality(15.0, plagiarism_similarity, compared_count),
    ]

    weighted = sum(c.earned for c in breakdown)
    total_weight = sum(c.weight for c in breakdown) or 100.0
    pct = (weighted / total_weight) * 100.0
    scaled = (pct / 100.0) * max_marks

    # Confidence is low when the submission is tiny, the rubric is
    # missing, or plagiarism data is unavailable.
    confidence = "medium"
    if len(text.split()) < 80 or plagiarism_similarity is None or not kw:
        confidence = "low"
    elif weighted >= 0.85 * total_weight:
        confidence = "high"

    rationale = (
        f"Heuristic scorer produced {pct:.1f}% → {scaled:.1f}/"
        f"{max_marks:g}. Confidence {confidence}. This is a suggestion "
        f"only — please review before releasing."
    )

    return AutoGradingResult(
        total_score=round(scaled, 1),
        max_marks=max_marks,
        weighted_percent=round(pct, 1),
        breakdown=breakdown,
        overall_rationale=rationale,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Database-backed convenience wrapper
# ---------------------------------------------------------------------------


def _connect():
    return sqlite3.connect(str(DEFAULT_DB_PATH))


def _load_submission_context(submission_id: int) -> Optional[Dict[str, Any]]:
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.id, s.student_id, s.file_path, s.file_name,
                       a.id, a.title, a.module_code, a.max_marks,
                       a.description, a.rubric_id
                FROM assignment_submissions s
                JOIN assignments a ON a.id = s.assignment_id
                WHERE s.id = ?
                """,
                (submission_id,)
            )
            row = cur.fetchone()
    except Exception as e:
        logger.warning("AI grader: context lookup failed: %s", e)
        return None
    if not row:
        return None
    (sub_id, student_id, file_path, file_name, assignment_id, title,
     module_code, max_marks, description, rubric_id) = row
    return {
        'submission_id': sub_id,
        'student_id': student_id,
        'file_path': file_path,
        'file_name': file_name,
        'assignment_id': assignment_id,
        'assignment_title': title,
        'module_code': module_code,
        'max_marks': float(max_marks) if max_marks else 100.0,
        'description': description or '',
        'rubric_id': rubric_id,
    }


def _load_rubric_keywords(rubric_id: Optional[int]) -> List[str]:
    if not rubric_id:
        return []
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT criteria_name, description
                FROM rubric_criteria
                WHERE rubric_id = ?
                """,
                (rubric_id,)
            )
            rows = cur.fetchall()
    except Exception as e:
        logger.debug("AI grader: rubric lookup failed: %s", e)
        return []
    combined = ' '.join(
        ' '.join(str(x or '') for x in row) for row in rows
    )
    return _extract_keywords(combined, limit=20)


def _resolve_file_path(stored_path: str) -> Optional[str]:
    """Re-use the submission-viewer resolver so legacy paths still work."""
    try:
        from education_system.university_system.modules.domain.academics.gui.assignment_system._file_viewer import (
            resolve_submission_path,
        )
        return resolve_submission_path(stored_path)
    except Exception:
        return stored_path if stored_path and os.path.exists(stored_path) else None


def _extract_submission_text(path: str) -> Optional[str]:
    try:
        from education_system.university_system.modules.domain.academics.services.plagiarism.checker import (
            PlagiarismChecker,
        )
        text, _ft = PlagiarismChecker().extract_text_from_file(path)
        return text
    except Exception as e:
        logger.info("AI grader: text extraction failed for %s: %s", path, e)
        return None


def _run_plagiarism_for_submission(submission_id: int, assignment_id: int,
                                   file_path: str, title: str,
                                   module_code: str,
                                   author_user_id: Optional[int]) -> Dict[str, Any]:
    """Mirror the student-portal plagiarism flow: seed the repo with the
    assignment's other final submissions, add the current submission, and
    run the check. Returns a dict with similarity + compared_count, or
    empty dict if anything goes wrong.
    """
    try:
        from education_system.university_system.modules.domain.academics.services.plagiarism.checker import (
            PlagiarismChecker,
        )
    except Exception:
        return {}
    try:
        checker = PlagiarismChecker()
    except Exception:
        return {}
    try:
        text, file_type = checker.extract_text_from_file(file_path)
    except Exception:
        return {}

    # Seed repo with other final submissions for this assignment.
    seeded_count = 0
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.id, s.file_path, s.file_name, a.title, a.module_code,
                       u.id AS author_user_id
                FROM assignment_submissions s
                JOIN assignments a ON a.id = s.assignment_id
                LEFT JOIN users u ON u.student_id = s.student_id
                WHERE s.assignment_id = ?
                  AND s.id != ?
                  AND COALESCE(s.is_final_submission, 1) = 1
                """,
                (assignment_id, submission_id)
            )
            other_rows = cur.fetchall()
    except Exception:
        other_rows = []

    for _sid, fpath, fname, t, mc, auid in other_rows:
        if not fpath or not auid:
            continue
        resolved = _resolve_file_path(fpath) or fpath
        if not resolved or not os.path.exists(resolved):
            continue
        try:
            other_text, other_type = checker.extract_text_from_file(resolved)
        except Exception:
            continue
        try:
            checker.add_document_to_repository(
                title=f"{t} — {fname}",
                content=other_text,
                author_id=auid,
                module_code=mc or '',
                file_type=other_type,
            )
            seeded_count += 1
        except Exception:
            pass

    if not author_user_id:
        return {'compared_count': len(other_rows)}

    try:
        doc_id = checker.add_document_to_repository(
            title=f"{title} — grading scan",
            content=text,
            author_id=author_user_id,
            module_code=module_code or '',
            file_type=file_type,
        )
        result = checker.check_plagiarism(
            document_id=doc_id, checker_id=author_user_id, threshold=0.3,
        )
    except Exception:
        return {'compared_count': len(other_rows)}

    if isinstance(result, dict):
        return {
            'similarity': result.get('highest_similarity') or 0.0,
            'compared_count': len(other_rows),
            'status': result.get('status'),
        }
    return {'compared_count': len(other_rows)}


def grade_submission_by_id(
    submission_id: int,
    grader_user_id: Optional[int] = None,
) -> AutoGradingResult:
    """Look up the submission, extract text, run the heuristic scorer.

    *grader_user_id* is used as the plagiarism checker's author_id when
    registering the scan run. Passing ``None`` still produces a grade
    but leaves the originality criterion at its "unavailable" fallback.
    """
    ctx = _load_submission_context(submission_id)
    if not ctx:
        return AutoGradingResult(
            total_score=0.0, max_marks=0.0, weighted_percent=0.0,
            error=f"submission {submission_id} not found",
        )

    file_path = _resolve_file_path(ctx['file_path'] or '')
    if not file_path:
        return AutoGradingResult(
            total_score=0.0, max_marks=ctx['max_marks'], weighted_percent=0.0,
            error="submission file is not on disk",
        )

    text = _extract_submission_text(file_path)
    if text is None:
        return AutoGradingResult(
            total_score=0.0, max_marks=ctx['max_marks'], weighted_percent=0.0,
            error="submission file is not plain text and textract is not installed",
        )

    plag = _run_plagiarism_for_submission(
        submission_id=ctx['submission_id'],
        assignment_id=ctx['assignment_id'],
        file_path=file_path,
        title=ctx['assignment_title'],
        module_code=ctx['module_code'],
        author_user_id=grader_user_id,
    )

    rubric_keywords = _load_rubric_keywords(ctx['rubric_id'])

    return score_submission(
        text,
        ctx['max_marks'],
        rubric_keywords=rubric_keywords,
        assignment_description=ctx['description'],
        plagiarism_similarity=plag.get('similarity'),
        compared_count=plag.get('compared_count', 0),
    )

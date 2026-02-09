"""
Automated Essay Grading System

Uses NLP and machine learning to assist teachers in grading essays.
Provides automated scores and detailed feedback based on rubrics.
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)

# Optional NLP imports
try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    from nltk.sentiment import SentimentIntensityAnalyzer
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("NLTK not available - using basic essay analysis")


@dataclass
class GradingRubric:
    """Rubric for essay grading"""
    total_points: int = 100

    # Component weights (must sum to 1.0)
    content_weight: float = 0.40
    organization_weight: float = 0.25
    grammar_weight: float = 0.20
    vocabulary_weight: float = 0.15

    # Criteria
    min_words: int = 250
    max_words: int = 1000
    required_paragraphs: int = 3

    # Content requirements
    required_keywords: List[str] = field(default_factory=list)
    required_concepts: List[str] = field(default_factory=list)


@dataclass
class EssayFeedback:
    """Detailed feedback for an essay"""
    score: float
    component_scores: Dict[str, float]
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    detailed_analysis: Dict[str, any]
    graded_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class EssayGrader:
    """
    Automated essay grading system.

    Analyzes essays on multiple dimensions:
    - Content quality and relevance
    - Organization and structure
    - Grammar and mechanics
    - Vocabulary and style
    """

    def __init__(self):
        """Initialize essay grader"""
        self.sentiment_analyzer = None

        if NLTK_AVAILABLE:
            try:
                self.sentiment_analyzer = SentimentIntensityAnalyzer()
            except Exception as e:
                logger.warning(f"Could not initialize sentiment analyzer: {e}")

        logger.info("EssayGrader initialized")

    def grade_essay(
        self,
        essay_text: str,
        rubric: GradingRubric,
        reference_answer: Optional[str] = None
    ) -> EssayFeedback:
        """
        Grade an essay based on the provided rubric.

        Args:
            essay_text: The essay text to grade
            rubric: Grading rubric with criteria
            reference_answer: Optional reference answer for content comparison

        Returns:
            EssayFeedback with score and detailed feedback
        """
        # Analyze essay on multiple dimensions
        content_score = self._grade_content(essay_text, rubric, reference_answer)
        organization_score = self._grade_organization(essay_text, rubric)
        grammar_score = self._grade_grammar(essay_text)
        vocabulary_score = self._grade_vocabulary(essay_text)

        # Calculate weighted total score
        total_score = (
            rubric.content_weight * content_score +
            rubric.organization_weight * organization_score +
            rubric.grammar_weight * grammar_score +
            rubric.vocabulary_weight * vocabulary_score
        )

        # Convert to rubric scale
        final_score = (total_score / 100) * rubric.total_points

        # Generate feedback
        feedback = self._generate_feedback(
            essay_text,
            rubric,
            {
                'content': content_score,
                'organization': organization_score,
                'grammar': grammar_score,
                'vocabulary': vocabulary_score
            }
        )

        return EssayFeedback(
            score=round(final_score, 2),
            component_scores={
                'content': content_score,
                'organization': organization_score,
                'grammar': grammar_score,
                'vocabulary': vocabulary_score,
                'total': total_score
            },
            **feedback
        )

    def _grade_content(
        self,
        essay_text: str,
        rubric: GradingRubric,
        reference_answer: Optional[str]
    ) -> float:
        """
        Grade content quality and relevance.

        Returns score out of 100.
        """
        score = 50  # Base score

        # Check word count
        words = self._tokenize_words(essay_text)
        word_count = len(words)

        if rubric.min_words <= word_count <= rubric.max_words:
            score += 20
        elif word_count < rubric.min_words:
            # Penalize for being too short
            ratio = word_count / rubric.min_words
            score += 20 * ratio
        else:
            # Slight penalty for being too long
            score += 15

        # Check for required keywords
        if rubric.required_keywords:
            text_lower = essay_text.lower()
            keywords_found = sum(
                1 for keyword in rubric.required_keywords
                if keyword.lower() in text_lower
            )
            keyword_score = (keywords_found / len(rubric.required_keywords)) * 20
            score += keyword_score

        # Compare with reference answer if provided
        if reference_answer:
            similarity = self._calculate_semantic_similarity(essay_text, reference_answer)
            score += similarity * 10

        return min(score, 100)

    def _grade_organization(
        self,
        essay_text: str,
        rubric: GradingRubric
    ) -> float:
        """
        Grade essay organization and structure.

        Returns score out of 100.
        """
        score = 40  # Base score

        # Count paragraphs
        paragraphs = [p.strip() for p in essay_text.split('\n\n') if p.strip()]
        num_paragraphs = len(paragraphs)

        # Check paragraph count
        if num_paragraphs >= rubric.required_paragraphs:
            score += 20
        else:
            score += (num_paragraphs / rubric.required_paragraphs) * 20

        # Check for introduction and conclusion
        if self._has_introduction(essay_text):
            score += 15

        if self._has_conclusion(essay_text):
            score += 15

        # Check for topic sentences
        if self._has_topic_sentences(paragraphs):
            score += 10

        return min(score, 100)

    def _grade_grammar(self, essay_text: str) -> float:
        """
        Grade grammar and mechanics.

        Returns score out of 100.
        """
        score = 70  # Base score (assumes mostly correct)

        # Check for common errors
        sentences = self._tokenize_sentences(essay_text)

        # Check sentence length variation
        sentence_lengths = [len(self._tokenize_words(s)) for s in sentences]
        if sentence_lengths:
            avg_length = sum(sentence_lengths) / len(sentence_lengths)

            # Penalize very short or very long average
            if 10 <= avg_length <= 25:
                score += 10
            else:
                score += 5

        # Check for spelling errors (basic)
        spelling_errors = self._count_spelling_errors(essay_text)
        if spelling_errors == 0:
            score += 10
        elif spelling_errors < 3:
            score += 5

        # Check punctuation
        if self._has_proper_punctuation(essay_text):
            score += 10

        return min(score, 100)

    def _grade_vocabulary(self, essay_text: str) -> float:
        """
        Grade vocabulary usage and style.

        Returns score out of 100.
        """
        score = 50  # Base score

        words = self._tokenize_words(essay_text)

        if not words:
            return score

        # Vocabulary diversity (unique words / total words)
        unique_words = set(w.lower() for w in words)
        diversity = len(unique_words) / len(words)

        if diversity > 0.6:
            score += 20
        elif diversity > 0.5:
            score += 15
        elif diversity > 0.4:
            score += 10
        else:
            score += 5

        # Average word length (longer words = more sophisticated)
        avg_word_length = sum(len(w) for w in words) / len(words)

        if avg_word_length > 5.5:
            score += 15
        elif avg_word_length > 4.5:
            score += 10
        else:
            score += 5

        # Check for academic vocabulary
        academic_words = self._count_academic_vocabulary(words)
        if academic_words > 10:
            score += 15
        elif academic_words > 5:
            score += 10
        else:
            score += 5

        return min(score, 100)

    def _generate_feedback(
        self,
        essay_text: str,
        rubric: GradingRubric,
        scores: Dict[str, float]
    ) -> Dict:
        """Generate detailed feedback"""
        strengths = []
        weaknesses = []
        suggestions = []

        # Content feedback
        if scores['content'] >= 80:
            strengths.append("Excellent content coverage with relevant examples")
        elif scores['content'] < 60:
            weaknesses.append("Content needs more depth and relevance")
            suggestions.append("Include more specific examples and evidence")

        # Organization feedback
        if scores['organization'] >= 80:
            strengths.append("Well-organized with clear structure")
        elif scores['organization'] < 60:
            weaknesses.append("Organization and structure need improvement")
            suggestions.append("Use clear topic sentences and transitions between paragraphs")

        # Grammar feedback
        if scores['grammar'] >= 85:
            strengths.append("Strong grammar and mechanics")
        elif scores['grammar'] < 70:
            weaknesses.append("Grammar and mechanical errors present")
            suggestions.append("Proofread carefully for spelling and punctuation errors")

        # Vocabulary feedback
        if scores['vocabulary'] >= 80:
            strengths.append("Sophisticated vocabulary and word choice")
        elif scores['vocabulary'] < 60:
            weaknesses.append("Vocabulary could be more varied and academic")
            suggestions.append("Use more varied vocabulary and avoid repetition")

        # Word count feedback
        words = self._tokenize_words(essay_text)
        word_count = len(words)

        if word_count < rubric.min_words:
            weaknesses.append(f"Essay is too short ({word_count} words, minimum {rubric.min_words})")
            suggestions.append("Expand your arguments with more details and examples")
        elif word_count > rubric.max_words:
            suggestions.append(f"Essay is longer than recommended ({word_count} words, maximum {rubric.max_words})")

        # Detailed analysis
        detailed_analysis = {
            'word_count': word_count,
            'paragraph_count': len([p for p in essay_text.split('\n\n') if p.strip()]),
            'sentence_count': len(self._tokenize_sentences(essay_text)),
            'average_sentence_length': sum(
                len(self._tokenize_words(s))
                for s in self._tokenize_sentences(essay_text)
            ) / max(len(self._tokenize_sentences(essay_text)), 1),
            'vocabulary_diversity': len(set(w.lower() for w in words)) / max(len(words), 1),
        }

        return {
            'strengths': strengths,
            'weaknesses': weaknesses,
            'suggestions': suggestions,
            'detailed_analysis': detailed_analysis
        }

    # Helper methods

    def _tokenize_sentences(self, text: str) -> List[str]:
        """Tokenize text into sentences"""
        if NLTK_AVAILABLE:
            try:
                return sent_tokenize(text)
            except:
                pass

        # Fallback: split on sentence endings
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _tokenize_words(self, text: str) -> List[str]:
        """Tokenize text into words"""
        if NLTK_AVAILABLE:
            try:
                return word_tokenize(text)
            except:
                pass

        # Fallback: simple word splitting
        return re.findall(r'\b\w+\b', text)

    def _calculate_semantic_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """
        Calculate semantic similarity between two texts.

        Returns value between 0 and 1.
        """
        # Simple bag-of-words similarity
        words1 = set(w.lower() for w in self._tokenize_words(text1))
        words2 = set(w.lower() for w in self._tokenize_words(text2))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _has_introduction(self, text: str) -> bool:
        """Check if essay has a proper introduction"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if not paragraphs:
            return False

        first_paragraph = paragraphs[0].lower()

        # Look for introduction indicators
        intro_words = ['introduction', 'begin', 'first', 'topic', 'discuss', 'essay']
        return any(word in first_paragraph for word in intro_words)

    def _has_conclusion(self, text: str) -> bool:
        """Check if essay has a proper conclusion"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if not paragraphs:
            return False

        last_paragraph = paragraphs[-1].lower()

        # Look for conclusion indicators
        conclusion_words = ['conclusion', 'finally', 'summary', 'therefore', 'thus', 'in conclusion']
        return any(word in last_paragraph for word in conclusion_words)

    def _has_topic_sentences(self, paragraphs: List[str]) -> bool:
        """Check if paragraphs have clear topic sentences"""
        # Simplified: check if paragraphs start with substantial sentences
        if len(paragraphs) < 2:
            return False

        # Skip first and last (intro/conclusion)
        body_paragraphs = paragraphs[1:-1] if len(paragraphs) > 2 else paragraphs

        for paragraph in body_paragraphs:
            sentences = self._tokenize_sentences(paragraph)
            if not sentences:
                continue

            first_sentence = sentences[0]
            # Check if first sentence is substantial
            if len(self._tokenize_words(first_sentence)) < 5:
                return False

        return True

    def _count_spelling_errors(self, text: str) -> int:
        """Count basic spelling errors"""
        # Simplified: look for common patterns
        errors = 0

        # Double spaces
        if '  ' in text:
            errors += text.count('  ')

        # Words with numbers (likely typos)
        words = self._tokenize_words(text)
        for word in words:
            if any(c.isdigit() and c.isalpha() for c in word):
                errors += 1

        return errors

    def _has_proper_punctuation(self, text: str) -> bool:
        """Check for proper punctuation usage"""
        sentences = self._tokenize_sentences(text)

        if not sentences:
            return False

        # Check if most sentences end with punctuation
        proper_endings = sum(
            1 for s in sentences
            if s.strip() and s.strip()[-1] in '.!?'
        )

        return (proper_endings / len(sentences)) > 0.8

    def _count_academic_vocabulary(self, words: List[str]) -> int:
        """Count usage of academic vocabulary"""
        # Common academic words
        academic_words = {
            'analyze', 'evaluate', 'discuss', 'examine', 'investigate',
            'demonstrate', 'illustrate', 'significant', 'furthermore',
            'therefore', 'consequently', 'however', 'moreover', 'nevertheless',
            'hypothesis', 'theory', 'evidence', 'research', 'study',
            'approach', 'concept', 'factor', 'issue', 'process', 'structure'
        }

        words_lower = [w.lower() for w in words]
        count = sum(1 for word in words_lower if word in academic_words)

        return count


# Singleton instance
_essay_grader: Optional[EssayGrader] = None


def get_essay_grader() -> EssayGrader:
    """Get singleton essay grader instance"""
    global _essay_grader
    if _essay_grader is None:
        _essay_grader = EssayGrader()
    return _essay_grader

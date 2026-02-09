"""Visual analysis and explanations for AI detection results."""

import re
from typing import Dict, List, Any

from university_system.utils.ai.ai_detector.core.constants import logger


class VisualAnalyzer:
    """Provides visual analysis and explanations"""

    def __init__(self, detector_instance):
        self.detector = detector_instance

    def generate_text_heatmap(self, text: str, ai_scores: List[float]) -> Dict[str, Any]:
        """Generate heatmap data for text visualization"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(ai_scores) != len(sentences):
            # Adjust scores to match sentences
            if len(ai_scores) > len(sentences):
                ai_scores = ai_scores[:len(sentences)]
            else:
                ai_scores.extend([0] * (len(sentences) - len(ai_scores)))

        heatmap_data = []

        for i, (sentence, score) in enumerate(zip(sentences, ai_scores)):
            # Determine color intensity based on score
            if score > 0.8:
                color = 'red'
                intensity = 'high'
            elif score > 0.6:
                color = 'orange'
                intensity = 'medium'
            elif score > 0.4:
                color = 'yellow'
                intensity = 'low'
            else:
                color = 'green'
                intensity = 'none'

            heatmap_data.append({
                'sentence_index': i,
                'text': sentence,
                'score': score,
                'color': color,
                'intensity': intensity,
                'word_count': len(sentence.split())
            })

        return {
            'heatmap_data': heatmap_data,
            'overall_score': sum(ai_scores) / len(ai_scores) if ai_scores else 0,
            'high_risk_sentences': len([s for s in ai_scores if s > 0.7]),
            'total_sentences': len(sentences)
        }

    def generate_writing_flow_visualization(self, text: str) -> Dict[str, Any]:
        """Generate writing flow visualization data"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        flow_data = []

        for i, paragraph in enumerate(paragraphs):
            sentences = re.split(r'[.!?]+', paragraph)
            sentences = [s.strip() for s in sentences if s.strip()]

            # Analyze paragraph characteristics
            word_count = len(paragraph.split())
            sentence_count = len(sentences)
            avg_sentence_length = word_count / max(1, sentence_count)

            # Detect transitions
            transition_words = ['however', 'furthermore', 'moreover', 'therefore', 'consequently', 'in addition', 'on the other hand']
            has_transition = any(word in paragraph.lower() for word in transition_words)

            flow_data.append({
                'paragraph_index': i,
                'word_count': word_count,
                'sentence_count': sentence_count,
                'avg_sentence_length': avg_sentence_length,
                'has_transition': has_transition,
                'complexity_score': self._calculate_paragraph_complexity(paragraph)
            })

        return {
            'flow_data': flow_data,
            'total_paragraphs': len(paragraphs),
            'avg_paragraph_length': sum(p['word_count'] for p in flow_data) / len(flow_data) if flow_data else 0,
            'transition_frequency': sum(1 for p in flow_data if p['has_transition']) / len(flow_data) if flow_data else 0
        }

    def _calculate_paragraph_complexity(self, paragraph: str) -> float:
        """Calculate complexity score for a paragraph"""
        words = paragraph.split()

        # Factors contributing to complexity
        avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
        punctuation_density = len(re.findall(r'[,;:()]', paragraph)) / len(paragraph) if paragraph else 0

        # Normalize to 0-1 scale
        complexity = min(1.0, (avg_word_length / 10) + (punctuation_density * 10))

        return complexity

"""Enhanced detection mixin for AIDetector - writing style fingerprinting, paraphrasing detection, etc."""

import re
import json
import math
import statistics
from datetime import datetime
from collections import Counter
from typing import Dict, List, Optional, Any

from education_system.university_system.utils.ai.ai_detector.core.constants import logger, LANG_DETECT_AVAILABLE

try:
    from langdetect import detect_langs
except ImportError:
    pass


class EnhancedDetectionMixin:
    """Mixin providing enhanced detection analysis functions (1-8)."""

    # =========================================================================
    # ENHANCED DETECTION ANALYSIS FUNCTIONS (1-8)
    # =========================================================================

    def analyze_writing_style_fingerprint(self, student_id: str, text: str = None) -> Dict[str, Any]:
        """
        Create unique writing style fingerprint for each student to compare against submissions.
        Analyzes vocabulary, sentence structure, punctuation patterns, and stylistic preferences.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Get all previous submissions for this student
            cursor.execute('''
            SELECT submission_text, word_count, submission_date
            FROM ai_detector_submissions
            WHERE student_id = ?
            ORDER BY submission_date DESC
            LIMIT 20
            ''', (student_id,))

            submissions = cursor.fetchall()
            conn.close()

            if not submissions and not text:
                return {
                    'student_id': student_id,
                    'error': 'No submissions found for fingerprint analysis',
                    'fingerprint': None
                }

            # Combine all texts for analysis
            all_texts = [row['submission_text'] for row in submissions if row['submission_text']]
            if text:
                all_texts.append(text)

            combined_text = ' '.join(all_texts)

            # Calculate fingerprint metrics
            fingerprint = {
                'vocabulary_metrics': self._analyze_vocabulary(combined_text),
                'sentence_metrics': self._analyze_sentence_patterns(combined_text),
                'punctuation_patterns': self._analyze_punctuation(combined_text),
                'transition_usage': self._analyze_transitions(combined_text),
                'paragraph_structure': self._analyze_paragraph_structure(combined_text),
                'formality_score': self._calculate_formality(combined_text),
                'unique_phrases': self._extract_unique_phrases(combined_text),
                'word_frequency_profile': self._build_word_frequency_profile(combined_text)
            }

            # Store fingerprint
            self._store_style_fingerprint(student_id, fingerprint)

            return {
                'student_id': student_id,
                'fingerprint': fingerprint,
                'submissions_analyzed': len(all_texts),
                'total_words_analyzed': len(combined_text.split()),
                'generated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating writing style fingerprint: {e}")
            return {'student_id': student_id, 'error': str(e), 'fingerprint': None}

    def _analyze_vocabulary(self, text: str) -> Dict[str, Any]:
        """Analyze vocabulary characteristics"""
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        unique_words = set(words)

        # Calculate various vocabulary metrics
        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
        lexical_diversity = len(unique_words) / len(words) if words else 0

        # Complex words (3+ syllables)
        complex_words = [w for w in words if self._count_syllables(w) >= 3]
        complex_ratio = len(complex_words) / len(words) if words else 0

        return {
            'unique_words': len(unique_words),
            'total_words': len(words),
            'avg_word_length': round(avg_word_length, 2),
            'lexical_diversity': round(lexical_diversity, 3),
            'complex_word_ratio': round(complex_ratio, 3),
            'top_words': Counter(words).most_common(20)
        }

    def _analyze_sentence_patterns(self, text: str) -> Dict[str, Any]:
        """Analyze sentence structure patterns"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return {'avg_length': 0, 'length_variance': 0, 'sentence_starters': []}

        lengths = [len(s.split()) for s in sentences]
        avg_length = sum(lengths) / len(lengths)
        variance = statistics.variance(lengths) if len(lengths) > 1 else 0

        # Analyze sentence starters
        starters = [s.split()[0].lower() if s.split() else '' for s in sentences]
        starter_counts = Counter(starters)

        return {
            'avg_length': round(avg_length, 2),
            'length_variance': round(variance, 2),
            'min_length': min(lengths),
            'max_length': max(lengths),
            'sentence_starters': starter_counts.most_common(10),
            'total_sentences': len(sentences)
        }

    def _analyze_punctuation(self, text: str) -> Dict[str, Any]:
        """Analyze punctuation usage patterns"""
        punct_counts = {
            'commas': text.count(','),
            'semicolons': text.count(';'),
            'colons': text.count(':'),
            'exclamations': text.count('!'),
            'questions': text.count('?'),
            'dashes': text.count('-') + text.count('\u2014'),
            'parentheses': text.count('(') + text.count(')'),
            'quotes': text.count('"') + text.count("'")
        }

        total_chars = len(text)
        punct_density = {k: round(v / total_chars * 1000, 3) for k, v in punct_counts.items()}

        return {
            'counts': punct_counts,
            'density_per_1000_chars': punct_density
        }

    def _analyze_transitions(self, text: str) -> Dict[str, Any]:
        """Analyze transition word usage"""
        transition_categories = {
            'addition': ['furthermore', 'moreover', 'additionally', 'also', 'besides'],
            'contrast': ['however', 'nevertheless', 'although', 'whereas', 'conversely'],
            'cause_effect': ['therefore', 'consequently', 'thus', 'hence', 'accordingly'],
            'sequence': ['firstly', 'secondly', 'finally', 'subsequently', 'meanwhile'],
            'emphasis': ['indeed', 'certainly', 'importantly', 'notably', 'significantly']
        }

        text_lower = text.lower()
        usage = {}

        for category, words in transition_categories.items():
            count = sum(len(re.findall(r'\b' + word + r'\b', text_lower)) for word in words)
            usage[category] = count

        total_transitions = sum(usage.values())
        word_count = len(text.split())

        return {
            'by_category': usage,
            'total_transitions': total_transitions,
            'transitions_per_100_words': round(total_transitions / word_count * 100, 2) if word_count else 0
        }

    def _analyze_paragraph_structure(self, text: str) -> Dict[str, Any]:
        """Analyze paragraph structure"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if not paragraphs:
            return {'avg_length': 0, 'count': 0}

        lengths = [len(p.split()) for p in paragraphs]

        return {
            'count': len(paragraphs),
            'avg_length': round(sum(lengths) / len(lengths), 2),
            'length_variance': round(statistics.variance(lengths), 2) if len(lengths) > 1 else 0,
            'min_length': min(lengths),
            'max_length': max(lengths)
        }

    def _calculate_formality(self, text: str) -> float:
        """Calculate formality score (0-1, higher = more formal)"""
        informal_markers = ['gonna', 'wanna', 'kinda', 'sorta', 'yeah', 'nope', 'ok', 'okay',
                          'stuff', 'things', 'like', 'basically', 'literally', 'actually']
        formal_markers = ['therefore', 'consequently', 'furthermore', 'moreover', 'nevertheless',
                        'henceforth', 'whereby', 'thereof', 'herein', 'notwithstanding']

        text_lower = text.lower()
        words = text_lower.split()

        informal_count = sum(1 for w in words if w in informal_markers)
        formal_count = sum(1 for w in words if w in formal_markers)

        # Also check for contractions (informal)
        contractions = len(re.findall(r"\b\w+n't\b|\b\w+'ll\b|\b\w+'ve\b|\b\w+'re\b|\b\w+'d\b", text_lower))
        informal_count += contractions

        total = informal_count + formal_count
        if total == 0:
            return 0.5  # Neutral

        return round(formal_count / total, 3)

    def _extract_unique_phrases(self, text: str) -> List[str]:
        """Extract potentially unique phrases/idioms"""
        # Common n-grams that might be distinctive
        words = text.lower().split()
        trigrams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
        trigram_counts = Counter(trigrams)

        # Return most common distinctive phrases
        return [phrase for phrase, count in trigram_counts.most_common(15) if count >= 2]

    def _build_word_frequency_profile(self, text: str) -> Dict[str, float]:
        """Build a normalized word frequency profile"""
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        total = len(words)

        if total == 0:
            return {}

        freq = Counter(words)
        # Normalize and return top 50
        return {word: round(count/total, 5) for word, count in freq.most_common(50)}

    def _store_style_fingerprint(self, student_id: str, fingerprint: Dict) -> None:
        """Store style fingerprint in database"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS style_fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                fingerprint_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            ''')

            # Check if fingerprint exists
            cursor.execute('SELECT id FROM style_fingerprints WHERE student_id = ?', (student_id,))
            existing = cursor.fetchone()

            now = datetime.now().isoformat()

            if existing:
                cursor.execute('''
                UPDATE style_fingerprints SET fingerprint_data = ?, updated_at = ?
                WHERE student_id = ?
                ''', (json.dumps(fingerprint), now, student_id))
            else:
                cursor.execute('''
                INSERT INTO style_fingerprints (student_id, fingerprint_data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ''', (student_id, json.dumps(fingerprint), now, now))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing style fingerprint: {e}")

    def detect_paraphrasing_tools(self, text: str) -> Dict[str, Any]:
        """
        Specifically detect content processed through Quillbot, Spinbot, etc.
        Looks for patterns characteristic of automated paraphrasing.
        """
        try:
            indicators = []
            scores = {}

            # Pattern 1: Unusual synonym chains
            synonym_patterns = [
                (r'\b(utilize|utilise)\b', 'formal_synonyms'),
                (r'\b(commence|initiate)\b.*\b(terminate|conclude)\b', 'formal_verb_pairs'),
                (r'\b(approximately|roughly|around)\b', 'hedging_synonyms')
            ]

            for pattern, name in synonym_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    scores[name] = min(1.0, len(matches) * 0.2)
                    indicators.append({
                        'type': name,
                        'count': len(matches),
                        'evidence': f"Found {len(matches)} instances of {name}"
                    })

            # Pattern 2: Awkward phrasing from automated rewrites
            awkward_patterns = [
                r'\bwith respect to the\b',
                r'\bin the event that\b',
                r'\bfor the purpose of\b',
                r'\bdue to the fact that\b',
                r'\bin order to\b',
                r'\bat this point in time\b',
                r'\bin the vicinity of\b'
            ]

            awkward_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in awkward_patterns)
            if awkward_count > 0:
                scores['awkward_phrasing'] = min(1.0, awkward_count * 0.15)
                indicators.append({
                    'type': 'awkward_phrasing',
                    'count': awkward_count,
                    'evidence': 'Detected verbose/awkward phrasings common in paraphrasing tools'
                })

            # Pattern 3: Inconsistent vocabulary level
            simple_words = len(re.findall(r'\b(the|is|are|was|were|a|an|and|or|but)\b', text, re.IGNORECASE))
            complex_words = len([w for w in text.split() if self._count_syllables(w) >= 4])
            total_words = len(text.split())

            if total_words > 50:
                ratio = complex_words / total_words
                if ratio > 0.15:  # Unusually high complex word ratio
                    scores['vocabulary_inconsistency'] = min(1.0, (ratio - 0.1) * 5)
                    indicators.append({
                        'type': 'vocabulary_inconsistency',
                        'ratio': round(ratio, 3),
                        'evidence': 'Unusually high ratio of complex words suggesting artificial enhancement'
                    })

            # Pattern 4: Repetitive sentence structure
            sentences = re.split(r'[.!?]+', text)
            sentence_starters = [s.strip().split()[0].lower() if s.strip() and s.strip().split() else '' for s in sentences]
            starter_freq = Counter(sentence_starters)

            if len(sentences) > 5:
                max_starter_freq = max(starter_freq.values()) if starter_freq else 0
                repetition_ratio = max_starter_freq / len(sentences)
                if repetition_ratio > 0.4:
                    scores['repetitive_structure'] = min(1.0, repetition_ratio)
                    indicators.append({
                        'type': 'repetitive_structure',
                        'most_common_starter': starter_freq.most_common(1)[0] if starter_freq else ('', 0),
                        'evidence': 'High repetition of sentence starters common in paraphrasing tools'
                    })

            # Pattern 5: Quillbot-specific patterns
            quillbot_patterns = [
                r'\b(whilst|amongst|towards)\b',  # British spellings mixed with American
                r'\b(that being said|having said that)\b',
                r'\b(it is worth noting|it should be noted)\b'
            ]

            quillbot_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in quillbot_patterns)
            if quillbot_count > 0:
                scores['quillbot_patterns'] = min(1.0, quillbot_count * 0.25)
                indicators.append({
                    'type': 'quillbot_specific',
                    'count': quillbot_count,
                    'evidence': 'Patterns commonly seen in Quillbot-processed text'
                })

            # Calculate overall paraphrasing score
            overall_score = sum(scores.values()) / max(len(scores), 1)

            # Determine likely tool
            likely_tool = None
            if overall_score > 0.5:
                if scores.get('quillbot_patterns', 0) > 0.3:
                    likely_tool = 'Quillbot (probable)'
                elif scores.get('vocabulary_inconsistency', 0) > 0.4:
                    likely_tool = 'Academic paraphraser (probable)'
                else:
                    likely_tool = 'Generic paraphrasing tool (probable)'

            return {
                'is_paraphrased': overall_score > 0.4,
                'paraphrasing_score': round(overall_score, 3),
                'confidence': round(min(0.95, overall_score + 0.2), 3) if overall_score > 0.3 else round(overall_score, 3),
                'likely_tool': likely_tool,
                'indicators': indicators,
                'detailed_scores': scores,
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error detecting paraphrasing tools: {e}")
            return {'error': str(e), 'is_paraphrased': False, 'paraphrasing_score': 0}

    def analyze_prompt_artifacts(self, text: str) -> Dict[str, Any]:
        """
        Detect common ChatGPT/Claude prompt response patterns and artifacts.
        """
        try:
            artifacts = []
            scores = {}

            # ChatGPT/Claude specific phrases
            ai_phrases = [
                (r"^(Certainly|Sure|Of course|Absolutely)[,!.]", "opening_affirmation"),
                (r"\bI'd be happy to\b", "eager_helper"),
                (r"\bAs an AI\b", "ai_reference"),
                (r"\bI don't have personal\b", "ai_limitation"),
                (r"\bLet me (explain|elaborate|break down)\b", "meta_commentary"),
                (r"\bIn (conclusion|summary)\b", "structured_conclusion"),
                (r"\bIt's (important|worth|crucial) to (note|mention|consider)\b", "importance_hedging"),
                (r"\bThere are (several|many|a few) (key|important|main)\b", "listing_intro"),
                (r"\bHere are (some|a few|several)\b", "list_intro"),
                (r"\b(First|Firstly|Second|Secondly|Third|Finally),\b", "enumeration"),
                (r"\bThis (highlights|demonstrates|illustrates|shows)\b", "analysis_language"),
                (r"\bOverall,?\s", "summary_transition"),
                (r"\bIn this (essay|response|answer)\b", "meta_reference")
            ]

            for pattern, artifact_type in ai_phrases:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    count = len(matches) if isinstance(matches[0], str) else len(matches)
                    scores[artifact_type] = min(1.0, count * 0.3)
                    artifacts.append({
                        'type': artifact_type,
                        'pattern': pattern,
                        'matches': count,
                        'severity': 'high' if count > 2 else 'medium' if count > 1 else 'low'
                    })

            # Check for characteristic structure
            paragraphs = text.split('\n\n')

            # ChatGPT often uses very consistent paragraph lengths
            if len(paragraphs) > 3:
                para_lengths = [len(p.split()) for p in paragraphs if p.strip()]
                if para_lengths:
                    avg_len = sum(para_lengths) / len(para_lengths)
                    variance = statistics.variance(para_lengths) if len(para_lengths) > 1 else 0

                    # Low variance suggests AI-generated uniform structure
                    if variance < 100 and avg_len > 30:
                        scores['uniform_paragraphs'] = 0.5
                        artifacts.append({
                            'type': 'uniform_structure',
                            'variance': round(variance, 2),
                            'avg_length': round(avg_len, 2),
                            'severity': 'medium'
                        })

            # Check for excessive hedging
            hedging_patterns = [
                r'\b(may|might|could|would)\b',
                r'\b(perhaps|possibly|potentially)\b',
                r'\b(generally|typically|usually|often)\b',
                r'\b(tend to|appears to|seems to)\b'
            ]

            hedging_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in hedging_patterns)
            word_count = len(text.split())
            hedging_ratio = hedging_count / word_count if word_count > 0 else 0

            if hedging_ratio > 0.05:  # More than 5% hedging words
                scores['excessive_hedging'] = min(1.0, hedging_ratio * 10)
                artifacts.append({
                    'type': 'excessive_hedging',
                    'ratio': round(hedging_ratio, 3),
                    'count': hedging_count,
                    'severity': 'high' if hedging_ratio > 0.08 else 'medium'
                })

            # Calculate overall score
            overall_score = sum(scores.values()) / max(len(scores), 1) if scores else 0

            return {
                'has_ai_artifacts': overall_score > 0.3,
                'artifact_score': round(overall_score, 3),
                'confidence': round(min(0.95, overall_score * 1.2), 3),
                'artifacts_found': artifacts,
                'detailed_scores': scores,
                'most_likely_source': self._determine_ai_source(artifacts, scores),
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing prompt artifacts: {e}")
            return {'error': str(e), 'has_ai_artifacts': False, 'artifact_score': 0}

    def _determine_ai_source(self, artifacts: List, scores: Dict) -> str:
        """Determine most likely AI source based on patterns"""
        if not artifacts:
            return "Likely human-written"

        chatgpt_indicators = ['opening_affirmation', 'eager_helper', 'list_intro', 'enumeration']
        claude_indicators = ['importance_hedging', 'analysis_language', 'meta_commentary']

        chatgpt_score = sum(scores.get(i, 0) for i in chatgpt_indicators)
        claude_score = sum(scores.get(i, 0) for i in claude_indicators)

        if chatgpt_score > claude_score and chatgpt_score > 0.5:
            return "ChatGPT (probable)"
        elif claude_score > chatgpt_score and claude_score > 0.5:
            return "Claude (probable)"
        elif chatgpt_score + claude_score > 0.8:
            return "AI-generated (uncertain source)"
        else:
            return "Possibly human with AI assistance"

    def compare_draft_versions(self, drafts: List[str], student_id: str = None) -> Dict[str, Any]:
        """
        Compare multiple drafts to detect suspicious jumps in quality.
        """
        try:
            if len(drafts) < 2:
                return {'error': 'Need at least 2 drafts to compare', 'suspicious': False}

            analyses = []
            quality_scores = []

            for i, draft in enumerate(drafts):
                analysis = {
                    'draft_number': i + 1,
                    'word_count': len(draft.split()),
                    'vocabulary_richness': self._calculate_vocabulary_richness(draft),
                    'sentence_complexity': self._calculate_sentence_complexity(draft),
                    'grammar_score': self._estimate_grammar_score(draft),
                    'formality': self._calculate_formality(draft),
                    'ai_likelihood': self._calculate_basic_ai_score(draft)
                }

                # Composite quality score
                quality = (
                    analysis['vocabulary_richness'] * 0.25 +
                    analysis['sentence_complexity'] * 0.25 +
                    analysis['grammar_score'] * 0.25 +
                    (1 - analysis['ai_likelihood']) * 0.25
                )
                analysis['quality_score'] = round(quality, 3)
                quality_scores.append(quality)

                analyses.append(analysis)

            # Detect suspicious jumps
            suspicious_jumps = []
            for i in range(1, len(quality_scores)):
                jump = quality_scores[i] - quality_scores[i-1]
                if jump > 0.3:  # 30% improvement threshold
                    suspicious_jumps.append({
                        'from_draft': i,
                        'to_draft': i + 1,
                        'improvement': round(jump, 3),
                        'severity': 'high' if jump > 0.5 else 'medium'
                    })

            # Check for style consistency
            style_changes = []
            for i in range(1, len(analyses)):
                vocab_change = abs(analyses[i]['vocabulary_richness'] - analyses[i-1]['vocabulary_richness'])
                formality_change = abs(analyses[i]['formality'] - analyses[i-1]['formality'])

                if vocab_change > 0.2 or formality_change > 0.3:
                    style_changes.append({
                        'from_draft': i,
                        'to_draft': i + 1,
                        'vocabulary_shift': round(vocab_change, 3),
                        'formality_shift': round(formality_change, 3)
                    })

            # Compare with student's historical fingerprint if available
            fingerprint_deviation = None
            if student_id:
                stored_fp = self._get_stored_fingerprint(student_id)
                if stored_fp:
                    final_draft = drafts[-1]
                    fingerprint_deviation = self._compare_to_fingerprint(final_draft, stored_fp)

            is_suspicious = len(suspicious_jumps) > 0 or len(style_changes) > 1

            return {
                'drafts_analyzed': len(drafts),
                'analyses': analyses,
                'quality_progression': quality_scores,
                'suspicious_jumps': suspicious_jumps,
                'style_changes': style_changes,
                'fingerprint_deviation': fingerprint_deviation,
                'is_suspicious': is_suspicious,
                'suspicion_reasons': self._summarize_suspicion_reasons(suspicious_jumps, style_changes),
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error comparing draft versions: {e}")
            return {'error': str(e), 'suspicious': False}

    def _calculate_vocabulary_richness(self, text: str) -> float:
        """Calculate vocabulary richness score (0-1)"""
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        if not words:
            return 0

        unique_words = len(set(words))
        total_words = len(words)

        # Type-token ratio with adjustment for text length
        ttr = unique_words / total_words
        # Root TTR is more stable across text lengths
        root_ttr = unique_words / math.sqrt(total_words)

        # Normalize to 0-1 scale
        return min(1.0, root_ttr / 10)

    def _calculate_sentence_complexity(self, text: str) -> float:
        """Calculate sentence complexity score (0-1)"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0

        complexities = []
        for sentence in sentences:
            words = sentence.split()
            word_count = len(words)

            # Factors: length, commas, subordinate clause indicators
            comma_count = sentence.count(',')
            subordinate_words = len(re.findall(r'\b(which|that|because|although|while|when|if)\b', sentence, re.IGNORECASE))

            complexity = (word_count / 30) + (comma_count / 5) + (subordinate_words / 3)
            complexities.append(min(1.0, complexity))

        return round(sum(complexities) / len(complexities), 3)

    def _estimate_grammar_score(self, text: str) -> float:
        """Estimate grammar quality score (0-1)"""
        # Simple heuristics for grammar quality
        issues = 0

        # Check for common issues
        issues += len(re.findall(r'\s{2,}', text))  # Double spaces
        issues += len(re.findall(r'[.!?]\s*[a-z]', text))  # No cap after period
        issues += len(re.findall(r'\bi\s', text))  # Lowercase 'i'
        issues += len(re.findall(r'\s[.!?,]', text))  # Space before punctuation

        word_count = len(text.split())
        issue_ratio = issues / max(word_count, 1)

        return max(0, min(1.0, 1 - (issue_ratio * 10)))

    def _get_stored_fingerprint(self, student_id: str) -> Optional[Dict]:
        """Retrieve stored fingerprint for a student"""
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT fingerprint_data FROM style_fingerprints
            WHERE student_id = ? ORDER BY updated_at DESC LIMIT 1
            ''', (student_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                return json.loads(result['fingerprint_data'])
            return None

        except Exception as e:
            logger.error(f"Error retrieving fingerprint: {e}")
            return None

    def _compare_to_fingerprint(self, text: str, fingerprint: Dict) -> Dict[str, Any]:
        """Compare text to stored fingerprint"""
        current_metrics = self._analyze_vocabulary(text)
        stored_metrics = fingerprint.get('vocabulary_metrics', {})

        deviations = {}

        if stored_metrics:
            for key in ['avg_word_length', 'lexical_diversity', 'complex_word_ratio']:
                if key in current_metrics and key in stored_metrics:
                    deviation = abs(current_metrics[key] - stored_metrics[key])
                    deviations[key] = round(deviation, 3)

        avg_deviation = sum(deviations.values()) / len(deviations) if deviations else 0

        return {
            'deviations': deviations,
            'average_deviation': round(avg_deviation, 3),
            'matches_fingerprint': avg_deviation < 0.15
        }

    def _summarize_suspicion_reasons(self, jumps: List, changes: List) -> List[str]:
        """Summarize reasons for suspicion"""
        reasons = []

        if jumps:
            reasons.append(f"Found {len(jumps)} suspicious quality jump(s) between drafts")
        if len(changes) > 1:
            reasons.append(f"Detected {len(changes)} significant style changes between drafts")

        return reasons

    def detect_translation_artifacts(self, text: str) -> Dict[str, Any]:
        """
        Identify text that was written in another language and translated.
        """
        try:
            indicators = []
            scores = {}

            # Pattern 1: Awkward article usage
            article_issues = re.findall(r'\ba\s+[aeiou]|\ban\s+[^aeiou]', text, re.IGNORECASE)
            if article_issues:
                scores['article_errors'] = min(1.0, len(article_issues) * 0.3)
                indicators.append({
                    'type': 'article_errors',
                    'count': len(article_issues),
                    'evidence': 'Incorrect a/an usage common in translated text'
                })

            # Pattern 2: Unusual word order (verb-subject in questions, adjective placement)
            word_order_patterns = [
                r'\b(very|extremely|quite)\s+(?!good|bad|big|small|important)\w+\s+(the|a)\b',  # Adjective after article
                r'\bhave\s+you\s+\w+\?',  # Unusual question form
            ]

            word_order_issues = sum(len(re.findall(p, text, re.IGNORECASE)) for p in word_order_patterns)
            if word_order_issues:
                scores['word_order'] = min(1.0, word_order_issues * 0.25)
                indicators.append({
                    'type': 'word_order_issues',
                    'count': word_order_issues,
                    'evidence': 'Unusual word order suggesting non-native construction'
                })

            # Pattern 3: Literal translation markers
            literal_patterns = [
                r'\bmake\s+(an?\s+)?(decision|choice|mistake)\b',  # Literal from many languages
                r'\btake\s+a\s+look\b',
                r'\bin\s+the\s+morning\s+of\b',
                r'\bsince\s+\d+\s+years\b',  # Common error from several languages
                r'\bI\s+am\s+agree\b',
                r'\bI\s+am\s+not\s+agree\b'
            ]

            literal_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in literal_patterns)
            if literal_count:
                scores['literal_translation'] = min(1.0, literal_count * 0.35)
                indicators.append({
                    'type': 'literal_translation',
                    'count': literal_count,
                    'evidence': 'Phrases suggesting literal translation from another language'
                })

            # Pattern 4: Preposition errors
            preposition_errors = [
                r'\binterested\s+for\b',
                r'\bdepend\s+from\b',
                r'\bon\s+the\s+internet\b',
                r'\bin\s+the\s+university\b',
                r'\bmarried\s+with\b',
                r'\bwait\s+\w+\s+at\b'
            ]

            prep_errors = sum(len(re.findall(p, text, re.IGNORECASE)) for p in preposition_errors)
            if prep_errors:
                scores['preposition_errors'] = min(1.0, prep_errors * 0.3)
                indicators.append({
                    'type': 'preposition_errors',
                    'count': prep_errors,
                    'evidence': 'Preposition usage errors common in translated text'
                })

            # Pattern 5: Use language detection library if available
            detected_language = None
            language_confidence = 0

            if LANG_DETECT_AVAILABLE:
                try:
                    langs = detect_langs(text)
                    if langs:
                        primary_lang = langs[0]
                        detected_language = primary_lang.lang
                        language_confidence = primary_lang.prob

                        # Check for mixed language signals
                        if len(langs) > 1 and langs[1].prob > 0.1:
                            scores['mixed_language'] = 0.5
                            indicators.append({
                                'type': 'mixed_language_signals',
                                'languages': [(l.lang, round(l.prob, 3)) for l in langs[:3]],
                                'evidence': 'Text shows characteristics of multiple languages'
                            })
                except Exception:
                    pass

            # Calculate overall translation score
            overall_score = sum(scores.values()) / max(len(scores), 1) if scores else 0

            return {
                'is_likely_translated': overall_score > 0.35,
                'translation_score': round(overall_score, 3),
                'confidence': round(min(0.9, overall_score + 0.15), 3) if overall_score > 0.2 else round(overall_score, 3),
                'detected_language': detected_language,
                'language_confidence': round(language_confidence, 3) if language_confidence else None,
                'indicators': indicators,
                'detailed_scores': scores,
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error detecting translation artifacts: {e}")
            return {'error': str(e), 'is_likely_translated': False, 'translation_score': 0}

    def analyze_knowledge_consistency(self, text: str, student_id: str, course_code: str = None) -> Dict[str, Any]:
        """
        Check if demonstrated knowledge matches student's course level.
        """
        try:
            conn = self._safe_db_connect()
            cursor = conn.cursor()

            # Get student's previous submissions
            cursor.execute('''
            SELECT s.submission_text, s.course_code, s.word_count, r.ai_score
            FROM ai_detector_submissions s
            LEFT JOIN ai_detector_results r ON s.id = r.submission_id
            WHERE s.student_id = ?
            ORDER BY s.submission_date DESC
            LIMIT 10
            ''', (student_id,))

            previous_submissions = cursor.fetchall()
            conn.close()

            # Analyze current text complexity
            current_analysis = {
                'vocabulary_level': self._assess_vocabulary_level(text),
                'concept_complexity': self._assess_concept_complexity(text),
                'technical_terms': self._extract_technical_terms(text),
                'citation_style': self._analyze_citation_maturity(text),
                'argument_sophistication': self._assess_argument_sophistication(text)
            }

            # Compare with historical data
            historical_baseline = None
            if previous_submissions:
                historical_texts = ' '.join([s['submission_text'] for s in previous_submissions if s['submission_text']])
                if historical_texts:
                    historical_baseline = {
                        'vocabulary_level': self._assess_vocabulary_level(historical_texts),
                        'concept_complexity': self._assess_concept_complexity(historical_texts),
                        'avg_ai_score': sum(s['ai_score'] or 0 for s in previous_submissions) / len(previous_submissions)
                    }

            # Detect inconsistencies
            inconsistencies = []

            if historical_baseline:
                vocab_jump = current_analysis['vocabulary_level'] - historical_baseline['vocabulary_level']
                concept_jump = current_analysis['concept_complexity'] - historical_baseline['concept_complexity']

                if vocab_jump > 0.3:
                    inconsistencies.append({
                        'type': 'vocabulary_jump',
                        'current': current_analysis['vocabulary_level'],
                        'historical': historical_baseline['vocabulary_level'],
                        'jump': round(vocab_jump, 3),
                        'severity': 'high' if vocab_jump > 0.5 else 'medium'
                    })

                if concept_jump > 0.35:
                    inconsistencies.append({
                        'type': 'concept_complexity_jump',
                        'current': current_analysis['concept_complexity'],
                        'historical': historical_baseline['concept_complexity'],
                        'jump': round(concept_jump, 3),
                        'severity': 'high' if concept_jump > 0.5 else 'medium'
                    })

            # Check for concepts beyond expected level
            advanced_concepts = self._detect_advanced_concepts(text, course_code)
            if advanced_concepts:
                inconsistencies.append({
                    'type': 'advanced_concepts_detected',
                    'concepts': advanced_concepts,
                    'severity': 'medium'
                })

            is_consistent = len(inconsistencies) == 0

            return {
                'student_id': student_id,
                'is_consistent': is_consistent,
                'current_analysis': current_analysis,
                'historical_baseline': historical_baseline,
                'inconsistencies': inconsistencies,
                'previous_submissions_count': len(previous_submissions),
                'recommendation': self._generate_consistency_recommendation(inconsistencies),
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing knowledge consistency: {e}")
            return {'error': str(e), 'is_consistent': True}

    def _assess_vocabulary_level(self, text: str) -> float:
        """Assess vocabulary sophistication level (0-1)"""
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        if not words:
            return 0

        # Basic words list (simplified)
        basic_words = {'the', 'is', 'are', 'was', 'were', 'have', 'has', 'had', 'do', 'does', 'did',
                      'will', 'would', 'could', 'should', 'can', 'may', 'might', 'must', 'shall',
                      'a', 'an', 'and', 'or', 'but', 'if', 'then', 'so', 'as', 'at', 'by', 'for',
                      'in', 'of', 'on', 'to', 'with', 'from', 'this', 'that', 'these', 'those'}

        advanced_count = sum(1 for w in words if len(w) > 8 and w not in basic_words)
        academic_patterns = len(re.findall(r'\b(analysis|methodology|theoretical|empirical|hypothesis)\b', text, re.IGNORECASE))

        level = (advanced_count / len(words)) * 2 + (academic_patterns / len(words)) * 5
        return min(1.0, level)

    def _assess_concept_complexity(self, text: str) -> float:
        """Assess conceptual complexity (0-1)"""
        # Look for indicators of complex reasoning
        complexity_markers = [
            r'\b(therefore|consequently|thus|hence)\b',
            r'\b(implies|suggests|indicates)\b',
            r'\b(correlation|causation|relationship)\b',
            r'\b(hypothesis|theory|model)\b',
            r'\b(analysis|synthesis|evaluation)\b',
            r'\b(furthermore|moreover|additionally)\b'
        ]

        marker_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in complexity_markers)
        word_count = len(text.split())

        return min(1.0, (marker_count / max(word_count, 1)) * 50)

    def _extract_technical_terms(self, text: str) -> List[str]:
        """Extract likely technical terms from text"""
        # Words that are likely technical (long, uncommon, or contain specific patterns)
        words = re.findall(r'\b[A-Za-z]{8,}\b', text)

        # Filter to unique, potentially technical terms
        technical = set()
        for word in words:
            if any(suffix in word.lower() for suffix in ['ology', 'ization', 'ification', 'ism', 'ity', 'ment']):
                technical.add(word.lower())
            elif self._count_syllables(word) >= 4:
                technical.add(word.lower())

        return list(technical)[:20]

    def _analyze_citation_maturity(self, text: str) -> float:
        """Analyze citation style maturity (0-1)"""
        # Look for citation patterns
        citation_patterns = [
            r'\([A-Z][a-z]+,?\s*\d{4}\)',  # APA style
            r'\[[0-9]+\]',  # Numeric citations
            r'\b(according to|as stated by|research by)\b',
            r'\bet\s+al\.',
            r'\b(ibid|op\.\s*cit)\b'
        ]

        citation_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in citation_patterns)
        word_count = len(text.split())

        return min(1.0, (citation_count / max(word_count, 1)) * 100)

    def _assess_argument_sophistication(self, text: str) -> float:
        """Assess argument structure sophistication (0-1)"""
        sophistication_markers = [
            r'\b(on\s+one\s+hand|on\s+the\s+other\s+hand)\b',
            r'\b(while\s+it\s+is\s+true\s+that|although)\b',
            r'\b(evidence\s+suggests|studies\s+show)\b',
            r'\b(counter-?argument|critique|limitation)\b',
            r'\b(nuanced|complex|multifaceted)\b'
        ]

        marker_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in sophistication_markers)
        return min(1.0, marker_count * 0.2)

    def _detect_advanced_concepts(self, text: str, course_code: str = None) -> List[str]:
        """Detect concepts that may be beyond expected level"""
        advanced_terms = [
            'epistemological', 'ontological', 'phenomenological', 'hermeneutic',
            'poststructuralist', 'deconstructionist', 'hegemonic', 'dialectical',
            'heteroscedasticity', 'multicollinearity', 'autocorrelation',
            'eigenvalue', 'eigenvector', 'laplacian', 'hamiltonian'
        ]

        found = []
        for term in advanced_terms:
            if term.lower() in text.lower():
                found.append(term)

        return found

    def _generate_consistency_recommendation(self, inconsistencies: List) -> str:
        """Generate recommendation based on inconsistencies"""
        if not inconsistencies:
            return "Submission appears consistent with student's demonstrated knowledge level."

        high_severity = sum(1 for i in inconsistencies if i.get('severity') == 'high')

        if high_severity > 0:
            return "Strong recommendation for further review - significant inconsistencies detected."
        else:
            return "Minor inconsistencies detected - may warrant follow-up discussion with student."

    def detect_copy_paste_patterns(self, text: str, metadata: Dict = None) -> Dict[str, Any]:
        """
        Identify copy-paste behavior from metadata and formatting anomalies.
        """
        try:
            indicators = []
            scores = {}

            # Pattern 1: Mixed formatting (fonts indicated by inconsistent styling)
            # In plain text, we look for inconsistent capitalization, spacing patterns

            # Check for inconsistent spacing
            space_patterns = re.findall(r'\s+', text)
            unique_space_patterns = set(space_patterns)
            if len(unique_space_patterns) > 3:  # Multiple different spacing patterns
                scores['inconsistent_spacing'] = min(1.0, len(unique_space_patterns) * 0.15)
                indicators.append({
                    'type': 'inconsistent_spacing',
                    'unique_patterns': len(unique_space_patterns),
                    'evidence': 'Multiple different whitespace patterns detected'
                })

            # Pattern 2: Quotation mark inconsistency
            straight_quotes = text.count('"') + text.count("'")
            curly_quotes = text.count('\u201c') + text.count('\u201d') + text.count('\u2018') + text.count('\u2019')

            if straight_quotes > 0 and curly_quotes > 0:
                scores['mixed_quotes'] = 0.4
                indicators.append({
                    'type': 'mixed_quotation_marks',
                    'straight': straight_quotes,
                    'curly': curly_quotes,
                    'evidence': 'Mixed straight and curly quotation marks (typical of copy-paste)'
                })

            # Pattern 3: Unicode anomalies
            unicode_chars = re.findall(r'[^\x00-\x7F]', text)
            if unicode_chars:
                unique_unicode = set(unicode_chars)
                # Look for suspicious characters
                suspicious_unicode = [c for c in unique_unicode if ord(c) > 8000]
                if suspicious_unicode:
                    scores['unicode_anomalies'] = min(1.0, len(suspicious_unicode) * 0.25)
                    indicators.append({
                        'type': 'unicode_anomalies',
                        'count': len(suspicious_unicode),
                        'evidence': 'Unusual Unicode characters often from copy-paste'
                    })

            # Pattern 4: Inconsistent line endings (if we can detect)
            if '\r\n' in text and '\n' in text.replace('\r\n', ''):
                scores['mixed_line_endings'] = 0.5
                indicators.append({
                    'type': 'mixed_line_endings',
                    'evidence': 'Mixed Windows and Unix line endings'
                })

            # Pattern 5: Abrupt style changes
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            if len(paragraphs) >= 3:
                style_changes = []
                for i in range(1, len(paragraphs)):
                    prev_formality = self._calculate_formality(paragraphs[i-1])
                    curr_formality = self._calculate_formality(paragraphs[i])

                    if abs(curr_formality - prev_formality) > 0.4:
                        style_changes.append({
                            'between': [i, i+1],
                            'formality_shift': round(curr_formality - prev_formality, 3)
                        })

                if style_changes:
                    scores['style_discontinuities'] = min(1.0, len(style_changes) * 0.3)
                    indicators.append({
                        'type': 'style_discontinuities',
                        'count': len(style_changes),
                        'details': style_changes,
                        'evidence': 'Abrupt changes in writing style between paragraphs'
                    })

            # Pattern 6: Analyze metadata if provided
            if metadata:
                if metadata.get('paste_count', 0) > 5:
                    scores['high_paste_count'] = min(1.0, metadata['paste_count'] * 0.1)
                    indicators.append({
                        'type': 'high_paste_count',
                        'count': metadata['paste_count'],
                        'evidence': f"User performed {metadata['paste_count']} paste operations"
                    })

                if metadata.get('typing_speed', 0) > 200:  # Words per minute
                    scores['impossible_typing_speed'] = 0.8
                    indicators.append({
                        'type': 'impossible_typing_speed',
                        'speed': metadata['typing_speed'],
                        'evidence': 'Typing speed exceeds human capability'
                    })

            # Calculate overall score
            overall_score = sum(scores.values()) / max(len(scores), 1) if scores else 0

            return {
                'has_copy_paste_indicators': overall_score > 0.3,
                'copy_paste_score': round(overall_score, 3),
                'confidence': round(min(0.9, overall_score + 0.1), 3),
                'indicators': indicators,
                'detailed_scores': scores,
                'metadata_analyzed': metadata is not None,
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error detecting copy-paste patterns: {e}")
            return {'error': str(e), 'has_copy_paste_indicators': False}

    def analyze_reference_authenticity(self, text: str) -> Dict[str, Any]:
        """
        Verify that cited sources actually exist and contain claimed information.
        """
        try:
            # Extract citations
            citations = []

            # APA style: (Author, Year)
            apa_citations = re.findall(r'\(([A-Z][a-zA-Z]+(?:\s+(?:&|and)\s+[A-Z][a-zA-Z]+)*),?\s*(\d{4})\)', text)
            for author, year in apa_citations:
                citations.append({
                    'style': 'APA',
                    'author': author,
                    'year': year,
                    'full_match': f"({author}, {year})"
                })

            # Numeric style: [1], [2], etc.
            numeric_citations = re.findall(r'\[(\d+)\]', text)
            for num in numeric_citations:
                citations.append({
                    'style': 'Numeric',
                    'reference_number': num,
                    'full_match': f"[{num}]"
                })

            # Look for reference list
            reference_section = None
            ref_patterns = [
                r'References?\s*\n',
                r'Bibliography\s*\n',
                r'Works\s+Cited\s*\n'
            ]

            for pattern in ref_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    reference_section = text[match.end():]
                    break

            # Analyze references
            reference_analysis = []
            suspicious_refs = []

            if reference_section:
                ref_lines = [line.strip() for line in reference_section.split('\n') if line.strip()]

                for ref in ref_lines[:20]:  # Analyze first 20 references
                    ref_check = self._check_reference_format(ref)
                    reference_analysis.append(ref_check)

                    if ref_check.get('suspicious'):
                        suspicious_refs.append(ref_check)

            # Check for common fabrication patterns
            fabrication_indicators = []

            # Pattern 1: References that don't match citations
            citation_authors = set(c.get('author', '').split()[0] for c in citations if c.get('author'))
            ref_authors = set()

            if reference_section:
                # Extract first word (likely surname) from each reference
                for line in reference_section.split('\n'):
                    words = line.strip().split()
                    if words:
                        ref_authors.add(words[0].rstrip(','))

            unmatched_citations = citation_authors - ref_authors
            if unmatched_citations:
                fabrication_indicators.append({
                    'type': 'unmatched_citations',
                    'missing_authors': list(unmatched_citations),
                    'evidence': 'Citations in text not found in reference list'
                })

            # Pattern 2: Suspiciously formatted references
            if reference_analysis:
                malformed_count = sum(1 for r in reference_analysis if r.get('format_issues'))
                if malformed_count > len(reference_analysis) * 0.3:
                    fabrication_indicators.append({
                        'type': 'high_malformed_ratio',
                        'ratio': round(malformed_count / len(reference_analysis), 2),
                        'evidence': 'High proportion of incorrectly formatted references'
                    })

            # Pattern 3: Check for impossible dates
            current_year = datetime.now().year
            future_dates = [c for c in citations if c.get('year') and int(c['year']) > current_year]
            if future_dates:
                fabrication_indicators.append({
                    'type': 'future_dates',
                    'count': len(future_dates),
                    'evidence': 'References with publication dates in the future'
                })

            # Calculate authenticity score
            total_refs = len(citations) + len(reference_analysis)
            issues = len(fabrication_indicators) + len(suspicious_refs)

            authenticity_score = 1.0 - (issues / max(total_refs, 1)) if total_refs > 0 else 1.0

            return {
                'citations_found': len(citations),
                'references_found': len(reference_analysis),
                'citations': citations[:20],  # Limit output
                'reference_analysis': reference_analysis,
                'suspicious_references': suspicious_refs,
                'fabrication_indicators': fabrication_indicators,
                'authenticity_score': round(max(0, authenticity_score), 3),
                'is_authentic': authenticity_score > 0.7,
                'verification_note': 'Full verification requires external API access to check source existence',
                'analyzed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing reference authenticity: {e}")
            return {'error': str(e), 'is_authentic': True, 'authenticity_score': 1.0}

    def _check_reference_format(self, reference: str) -> Dict[str, Any]:
        """Check if a reference is properly formatted"""
        result = {
            'reference': reference[:100] + '...' if len(reference) > 100 else reference,
            'format_issues': [],
            'suspicious': False
        }

        # Check for year
        if not re.search(r'\b(19|20)\d{2}\b', reference):
            result['format_issues'].append('Missing year')

        # Check for author pattern
        if not re.search(r'^[A-Z][a-z]+', reference):
            result['format_issues'].append('Does not start with author name')

        # Check minimum length
        if len(reference) < 30:
            result['format_issues'].append('Too short for valid reference')
            result['suspicious'] = True

        # Check for URL or DOI (good signs)
        if re.search(r'https?://|doi:', reference, re.IGNORECASE):
            result['has_url_or_doi'] = True

        # Flag as suspicious if multiple issues
        if len(result['format_issues']) >= 2:
            result['suspicious'] = True

        return result

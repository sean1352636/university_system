from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import json
import re
import math
from collections import Counter


class AIAssistantMixin:
    """Mixin providing AI-assisted tools for assignments: draft feedback,
    practice question generation, collusion analysis, and late pass recommendations."""

    def ai_assistant_menu(self):
        """Main AI assistant menu"""
        while True:
            print("\n" + "=" * 60)
            print("  AI Assistant - Assignment Tools")
            print("=" * 60)
            print("1. Get Draft Feedback")
            print("2. Generate Practice Questions")
            print("3. View Practice Questions / Take Quiz")
            print("4. Run Collusion Analysis")
            print("5. View Collusion Reports")
            print("6. Get Late Pass Recommendation")
            print("7. View Late Pass Recommendations")
            print("8. Back to Main Menu")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self.get_draft_feedback()
            elif choice == '2':
                self.generate_practice_questions()
            elif choice == '3':
                self.view_practice_questions()
            elif choice == '4':
                self.run_collusion_analysis()
            elif choice == '5':
                self.view_collusion_reports()
            elif choice == '6':
                self.get_late_pass_recommendation()
            elif choice == '7':
                self.view_late_pass_recommendations()
            elif choice == '8':
                break
            else:
                print("Invalid option. Please try again.")

    # ------------------------------------------------------------------ #
    #  1. Draft Feedback
    # ------------------------------------------------------------------ #

    def get_draft_feedback(self):
        """Student submits draft text and receives rule-based feedback on
        readability, structure, style, and word repetition."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Identify the student
            student_id = input("\nEnter your student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                conn.close()
                return

            # Select assignment context
            cursor.execute('''
                SELECT id, title, module_code
                FROM assignments
                WHERE is_active = 1
                ORDER BY due_date
            ''')
            assignments = cursor.fetchall()

            if not assignments:
                print("No active assignments found.")
                conn.close()
                return

            print("\nSelect Assignment:")
            for i, (aid, title, module) in enumerate(assignments, 1):
                print(f"  {i}. {title} ({module})")

            choice = input("\nAssignment number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(assignments)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id, assignment_title, module_code = assignments[index]

            print("\nPaste your draft text below (enter a blank line to finish):")
            lines = []
            while True:
                line = input()
                if line == '':
                    break
                lines.append(line)

            draft_text = '\n'.join(lines)
            if len(draft_text.strip()) < 20:
                print("Draft text is too short for meaningful feedback.")
                conn.close()
                return

            # ---------- Analysis ----------
            feedback = self._analyse_draft(draft_text)

            # Display feedback
            print("\n" + "=" * 60)
            print("  AI Draft Feedback Report")
            print("=" * 60)
            print(f"  Assignment : {assignment_title} ({module_code})")
            print(f"  Word Count : {feedback['word_count']}")
            print("-" * 60)

            # Readability
            print("\n  [Readability]")
            print(f"  Flesch-Kincaid Grade Level : {feedback['fk_grade']:.1f}")
            print(f"  Flesch Reading Ease        : {feedback['reading_ease']:.1f}")
            if feedback['reading_ease'] >= 60:
                print("  Verdict: Good readability for an academic text.")
            elif feedback['reading_ease'] >= 30:
                print("  Verdict: Moderately difficult - appropriate for university level.")
            else:
                print("  Verdict: Very difficult to read. Consider simplifying some sentences.")

            # Structure
            print("\n  [Structure]")
            print(f"  Paragraphs          : {feedback['paragraph_count']}")
            print(f"  Avg Sentences/Para  : {feedback['avg_sentences_per_para']:.1f}")
            print(f"  Avg Words/Sentence  : {feedback['avg_words_per_sentence']:.1f}")
            for note in feedback['structure_notes']:
                print(f"  * {note}")

            # Style
            print("\n  [Style]")
            print(f"  Passive Voice Usage : {feedback['passive_pct']:.1f}%")
            print(f"  Sentence Length Variety (StdDev) : {feedback['sentence_len_std']:.1f}")
            for note in feedback['style_notes']:
                print(f"  * {note}")

            # Word Repetition
            print("\n  [Word Repetition]")
            if feedback['repeated_words']:
                print("  Frequently repeated words (excluding common words):")
                for word, count in feedback['repeated_words']:
                    print(f"    '{word}' appears {count} times")
            else:
                print("  No excessive word repetition detected.")

            # Overall score
            print("\n  [Overall Score]")
            print(f"  Draft Quality Score : {feedback['overall_score']}/100")
            print("-" * 60)

            # Store feedback request
            cursor.execute('''
                INSERT INTO ai_feedback_requests
                (student_id, assignment_id, draft_text, feedback_json, overall_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                student_id,
                assignment_id,
                draft_text,
                json.dumps(feedback),
                feedback['overall_score'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            conn.commit()
            print("\nFeedback saved. You can revisit it later.")
            conn.close()

        except Exception as e:
            print(f"Error generating draft feedback: {e}")

    def _analyse_draft(self, text):
        """Run rule-based analysis on draft text and return a feedback dict."""
        sentences = self._split_sentences(text)
        words = re.findall(r"[a-zA-Z']+", text)
        word_count = len(words)
        syllable_counts = [self._count_syllables(w) for w in words]
        total_syllables = sum(syllable_counts)
        sentence_count = max(len(sentences), 1)

        # Flesch-Kincaid
        avg_words_per_sentence = word_count / sentence_count
        avg_syllables_per_word = total_syllables / max(word_count, 1)
        fk_grade = (0.39 * avg_words_per_sentence
                     + 11.8 * avg_syllables_per_word
                     - 15.59)
        reading_ease = (206.835
                        - 1.015 * avg_words_per_sentence
                        - 84.6 * avg_syllables_per_word)

        # Structure
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        paragraph_count = max(len(paragraphs), 1)
        sentences_per_para = sentence_count / paragraph_count

        structure_notes = []
        if paragraph_count == 1 and word_count > 150:
            structure_notes.append("Consider breaking the text into multiple paragraphs.")
        if avg_words_per_sentence > 30:
            structure_notes.append("Average sentence length is high. Try shortening some sentences.")
        if avg_words_per_sentence < 10 and word_count > 50:
            structure_notes.append("Sentences are very short. Try combining related ideas.")
        if not structure_notes:
            structure_notes.append("Structure looks reasonable.")

        # Style - passive voice detection
        passive_pattern = re.compile(
            r'\b(is|are|was|were|been|being|be)\s+\w+ed\b', re.IGNORECASE
        )
        passive_count = len(passive_pattern.findall(text))
        passive_pct = (passive_count / sentence_count) * 100 if sentence_count else 0

        # Sentence length variety
        sentence_lengths = [len(re.findall(r"[a-zA-Z']+", s)) for s in sentences]
        if len(sentence_lengths) > 1:
            mean_len = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((x - mean_len) ** 2 for x in sentence_lengths) / len(sentence_lengths)
            sentence_len_std = math.sqrt(variance)
        else:
            sentence_len_std = 0.0

        style_notes = []
        if passive_pct > 40:
            style_notes.append("High passive voice usage. Consider using more active constructions.")
        elif passive_pct > 20:
            style_notes.append("Moderate passive voice. A few more active sentences would help.")
        if sentence_len_std < 3 and sentence_count > 3:
            style_notes.append("Sentence lengths are very uniform. Vary sentence length for better flow.")
        if not style_notes:
            style_notes.append("Writing style is varied and clear.")

        # Word repetition
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'shall',
            'can', 'this', 'that', 'these', 'those', 'it', 'its', 'i',
            'we', 'they', 'he', 'she', 'you', 'not', 'no', 'so', 'if',
            'as', 'from', 'which', 'who', 'whom', 'what', 'when', 'where',
            'there', 'their', 'then', 'than', 'also', 'more', 'most',
            'very', 'just', 'about', 'into', 'over', 'such', 'each',
            'all', 'any', 'some', 'how', 'our', 'my', 'your', 'his',
            'her', 'up', 'out', 'one', 'two', 'new', 'now', 'way',
        }
        lower_words = [w.lower() for w in words if w.lower() not in stop_words and len(w) > 2]
        word_freq = Counter(lower_words)
        threshold = max(3, word_count // 40)
        repeated_words = [(w, c) for w, c in word_freq.most_common(10) if c >= threshold]

        # Overall score (0-100)
        score = 70  # baseline
        # Readability adjustments
        if 30 <= reading_ease <= 70:
            score += 10
        elif reading_ease < 20 or reading_ease > 80:
            score -= 10
        # Structure
        if paragraph_count > 1:
            score += 5
        if 12 <= avg_words_per_sentence <= 25:
            score += 5
        else:
            score -= 5
        # Style
        if passive_pct <= 20:
            score += 5
        elif passive_pct > 40:
            score -= 10
        if sentence_len_std >= 3:
            score += 5
        # Repetition penalty
        score -= min(len(repeated_words) * 3, 15)
        score = max(0, min(100, score))

        return {
            'word_count': word_count,
            'fk_grade': fk_grade,
            'reading_ease': reading_ease,
            'paragraph_count': paragraph_count,
            'avg_sentences_per_para': sentences_per_para,
            'avg_words_per_sentence': avg_words_per_sentence,
            'structure_notes': structure_notes,
            'passive_pct': passive_pct,
            'sentence_len_std': sentence_len_std,
            'style_notes': style_notes,
            'repeated_words': repeated_words,
            'overall_score': score,
        }

    def _split_sentences(self, text):
        """Split text into sentences using punctuation heuristics."""
        raw = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s for s in raw if len(s.strip()) > 0]

    def _count_syllables(self, word):
        """Estimate syllable count for an English word."""
        word = word.lower().strip()
        if len(word) <= 2:
            return 1
        vowels = 'aeiouy'
        count = 0
        prev_vowel = False
        for ch in word:
            if ch in vowels:
                if not prev_vowel:
                    count += 1
                prev_vowel = True
            else:
                prev_vowel = False
        if word.endswith('e') and count > 1:
            count -= 1
        return max(count, 1)

    # ------------------------------------------------------------------ #
    #  2. Generate Practice Questions
    # ------------------------------------------------------------------ #

    def generate_practice_questions(self):
        """Generate practice MCQ and short-answer questions from pasted content
        using keyword extraction and template-based generation."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            module_code = input("\nEnter module code: ").strip()
            if not module_code:
                print("Module code is required.")
                conn.close()
                return

            topic = input("Enter topic / title: ").strip()
            if not topic:
                topic = "General"

            print("\nPaste the source content below (enter a blank line to finish):")
            lines = []
            while True:
                line = input()
                if line == '':
                    break
                lines.append(line)

            content = '\n'.join(lines)
            if len(content.strip()) < 30:
                print("Content is too short to generate questions.")
                conn.close()
                return

            num_questions = input("Number of questions to generate (default 5): ").strip()
            try:
                num_questions = int(num_questions) if num_questions else 5
                num_questions = max(1, min(num_questions, 20))
            except ValueError:
                num_questions = 5

            # Extract keywords
            keywords = self._extract_keywords(content)
            sentences = self._split_sentences(content)

            if not keywords or not sentences:
                print("Could not extract enough information from the content.")
                conn.close()
                return

            questions = self._generate_questions_from_content(
                keywords, sentences, num_questions
            )

            if not questions:
                print("Could not generate questions from the provided content.")
                conn.close()
                return

            # Store questions
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for q in questions:
                cursor.execute('''
                    INSERT INTO practice_questions
                    (module_code, topic, question_type, question_text,
                     options_json, correct_answer, explanation, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    module_code,
                    topic,
                    q['type'],
                    q['question'],
                    json.dumps(q.get('options', [])),
                    q['answer'],
                    q.get('explanation', ''),
                    created_at,
                ))

            conn.commit()
            conn.close()

            print(f"\n{'=' * 60}")
            print(f"  Generated {len(questions)} Practice Questions")
            print(f"{'=' * 60}")
            for i, q in enumerate(questions, 1):
                print(f"\n  Q{i}. [{q['type'].upper()}] {q['question']}")
                if q['type'] == 'mcq' and q.get('options'):
                    for idx, opt in enumerate(q['options']):
                        label = chr(65 + idx)
                        print(f"      {label}. {opt}")
                print(f"      Answer: {q['answer']}")
                if q.get('explanation'):
                    print(f"      Explanation: {q['explanation']}")
            print(f"\n{'=' * 60}")
            print(f"Questions saved for module {module_code}, topic '{topic}'.")

        except Exception as e:
            print(f"Error generating practice questions: {e}")

    def _extract_keywords(self, text):
        """Extract significant keywords from text using frequency and filtering."""
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'shall',
            'can', 'this', 'that', 'these', 'those', 'it', 'its', 'not',
            'no', 'so', 'if', 'as', 'from', 'which', 'who', 'whom',
            'what', 'when', 'where', 'there', 'their', 'then', 'than',
            'also', 'more', 'most', 'very', 'just', 'about', 'into',
            'such', 'each', 'all', 'any', 'some', 'how', 'they', 'we',
            'you', 'he', 'she', 'i', 'me', 'my', 'our', 'your', 'his',
            'her', 'up', 'out', 'one', 'two', 'new', 'now', 'way',
            'use', 'used', 'using', 'many', 'like', 'over', 'after',
            'before', 'between', 'through', 'only', 'other', 'while',
            'because', 'since', 'both', 'same', 'different', 'make',
        }
        words = re.findall(r'[a-zA-Z]{3,}', text)
        lower_words = [w.lower() for w in words if w.lower() not in stop_words]
        freq = Counter(lower_words)
        # Return top keywords by frequency
        return [word for word, _ in freq.most_common(30)]

    def _generate_questions_from_content(self, keywords, sentences, num_questions):
        """Generate a mix of MCQ and short-answer questions."""
        questions = []
        used_sentences = set()

        # Templates for MCQ
        mcq_templates = [
            "Which of the following best describes '{keyword}'?",
            "What is the primary role of '{keyword}' in this context?",
            "Which statement about '{keyword}' is most accurate?",
        ]

        # Templates for short-answer
        sa_templates = [
            "Define '{keyword}' in the context of this topic.",
            "Explain the significance of '{keyword}'.",
            "In your own words, describe what '{keyword}' refers to.",
            "How does '{keyword}' relate to the main topic?",
        ]

        # Generate MCQs from keyword-bearing sentences
        for idx, sentence in enumerate(sentences):
            if len(questions) >= num_questions:
                break
            if idx in used_sentences:
                continue

            # Find a keyword present in this sentence
            sentence_lower = sentence.lower()
            matching_kw = None
            for kw in keywords:
                if kw in sentence_lower and len(kw) > 3:
                    matching_kw = kw
                    break

            if not matching_kw:
                continue

            used_sentences.add(idx)

            if len(questions) % 2 == 0:
                # MCQ
                template = mcq_templates[len(questions) % len(mcq_templates)]
                question_text = template.format(keyword=matching_kw)

                # Build options: correct answer is extracted from sentence
                correct = sentence.strip().rstrip('.')
                if len(correct) > 120:
                    correct = correct[:117] + '...'

                # Generate distractors from other sentences
                distractors = []
                for j, other in enumerate(sentences):
                    if j != idx and len(distractors) < 3:
                        d = other.strip().rstrip('.')
                        if len(d) > 120:
                            d = d[:117] + '...'
                        if d != correct:
                            distractors.append(d)

                while len(distractors) < 3:
                    distractors.append(f"None of the above regarding {matching_kw}")

                options = [correct] + distractors[:3]
                # Deterministic shuffle based on keyword
                options.sort(key=lambda x: hash(x + matching_kw) % 1000)
                correct_letter = chr(65 + options.index(correct))

                questions.append({
                    'type': 'mcq',
                    'question': question_text,
                    'options': options,
                    'answer': correct_letter,
                    'explanation': correct,
                })
            else:
                # Short answer
                template = sa_templates[len(questions) % len(sa_templates)]
                question_text = template.format(keyword=matching_kw)
                answer = sentence.strip()

                questions.append({
                    'type': 'short_answer',
                    'question': question_text,
                    'options': [],
                    'answer': answer,
                    'explanation': f"Based on the source material regarding {matching_kw}.",
                })

        # Fill remaining with keyword-based short-answer questions
        kw_idx = 0
        while len(questions) < num_questions and kw_idx < len(keywords):
            kw = keywords[kw_idx]
            kw_idx += 1
            if len(kw) <= 3:
                continue
            template = sa_templates[len(questions) % len(sa_templates)]
            questions.append({
                'type': 'short_answer',
                'question': template.format(keyword=kw),
                'options': [],
                'answer': f"Refer to source material on '{kw}'.",
                'explanation': '',
            })

        return questions[:num_questions]

    # ------------------------------------------------------------------ #
    #  3. View Practice Questions / Take Quiz
    # ------------------------------------------------------------------ #

    def view_practice_questions(self):
        """View generated practice questions for a module and optionally take a quiz."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            module_code = input("\nEnter module code (or leave blank for all): ").strip()

            if module_code:
                cursor.execute('''
                    SELECT id, module_code, topic, question_type, question_text,
                           options_json, correct_answer, explanation, created_at
                    FROM practice_questions
                    WHERE module_code = ?
                    ORDER BY created_at DESC
                ''', (module_code,))
            else:
                cursor.execute('''
                    SELECT id, module_code, topic, question_type, question_text,
                           options_json, correct_answer, explanation, created_at
                    FROM practice_questions
                    ORDER BY created_at DESC
                ''')

            rows = cursor.fetchall()
            if not rows:
                print("No practice questions found.")
                conn.close()
                return

            # Group by topic
            topics = {}
            for row in rows:
                qid, mod, topic, qtype, qtext, opts_json, answer, expl, created = row
                topics.setdefault(topic, []).append({
                    'id': qid, 'module': mod, 'topic': topic, 'type': qtype,
                    'question': qtext, 'options': json.loads(opts_json) if opts_json else [],
                    'answer': answer, 'explanation': expl, 'created': created,
                })

            print(f"\n{'=' * 60}")
            print(f"  Practice Questions ({len(rows)} total)")
            print(f"{'=' * 60}")
            topic_list = list(topics.keys())
            for i, t in enumerate(topic_list, 1):
                print(f"  {i}. {t} ({len(topics[t])} questions)")

            print(f"\n  {len(topic_list) + 1}. Take a practice quiz")
            print(f"  {len(topic_list) + 2}. Back")

            choice = input("\nSelect option: ").strip()
            try:
                choice_num = int(choice)
            except ValueError:
                print("Invalid selection.")
                conn.close()
                return

            if choice_num == len(topic_list) + 2:
                conn.close()
                return

            if choice_num == len(topic_list) + 1:
                # Take quiz
                print("\nSelect topic for quiz:")
                for i, t in enumerate(topic_list, 1):
                    print(f"  {i}. {t}")
                topic_choice = input("Topic number: ").strip()
                try:
                    tidx = int(topic_choice) - 1
                    if 0 <= tidx < len(topic_list):
                        self._run_practice_quiz(topics[topic_list[tidx]])
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")
                conn.close()
                return

            if 1 <= choice_num <= len(topic_list):
                selected_topic = topic_list[choice_num - 1]
                qs = topics[selected_topic]
                print(f"\n{'=' * 60}")
                print(f"  Topic: {selected_topic}")
                print(f"{'=' * 60}")
                for i, q in enumerate(qs, 1):
                    print(f"\n  Q{i}. [{q['type'].upper()}] {q['question']}")
                    if q['type'] == 'mcq' and q['options']:
                        for j, opt in enumerate(q['options']):
                            label = chr(65 + j)
                            print(f"      {label}. {opt}")
                    print(f"      Answer: {q['answer']}")
                    if q['explanation']:
                        print(f"      Explanation: {q['explanation']}")
            else:
                print("Invalid selection.")

            conn.close()

        except Exception as e:
            print(f"Error viewing practice questions: {e}")

    def _run_practice_quiz(self, questions):
        """Run an interactive practice quiz."""
        print(f"\n{'=' * 60}")
        print(f"  Practice Quiz - {len(questions)} Questions")
        print(f"{'=' * 60}")
        correct_count = 0

        for i, q in enumerate(questions, 1):
            print(f"\n  Q{i}. {q['question']}")
            if q['type'] == 'mcq' and q['options']:
                for j, opt in enumerate(q['options']):
                    label = chr(65 + j)
                    print(f"      {label}. {opt}")
                user_answer = input("  Your answer (A/B/C/D): ").strip().upper()
            else:
                user_answer = input("  Your answer: ").strip()

            if q['type'] == 'mcq':
                if user_answer == q['answer']:
                    print("  Correct!")
                    correct_count += 1
                else:
                    print(f"  Incorrect. The correct answer is {q['answer']}.")
                    if q['explanation']:
                        print(f"  Explanation: {q['explanation']}")
            else:
                # For short answer, display the model answer
                print(f"  Model answer: {q['answer']}")
                self_grade = input("  Did you get it right? (y/n): ").strip().lower()
                if self_grade == 'y':
                    correct_count += 1

        pct = (correct_count / len(questions)) * 100 if questions else 0
        print(f"\n{'-' * 60}")
        print(f"  Quiz Complete: {correct_count}/{len(questions)} ({pct:.0f}%)")
        if pct >= 80:
            print("  Excellent work!")
        elif pct >= 60:
            print("  Good effort. Review the topics you missed.")
        else:
            print("  Keep studying. Consider reviewing the source material.")
        print(f"{'-' * 60}")

    # ------------------------------------------------------------------ #
    #  4. Collusion Analysis
    # ------------------------------------------------------------------ #

    def run_collusion_analysis(self):
        """Compare all submissions for an assignment pairwise using n-gram
        Jaccard similarity, timing analysis, and structural similarity.
        Flag pairs above threshold."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, title, module_code, due_date
                FROM assignments
                WHERE is_active = 1
                ORDER BY due_date
            ''')
            assignments = cursor.fetchall()

            if not assignments:
                print("No active assignments found.")
                conn.close()
                return

            print("\nSelect Assignment for Collusion Analysis:")
            for i, (aid, title, module, due) in enumerate(assignments, 1):
                print(f"  {i}. {title} ({module}) - Due: {due}")

            choice = input("\nAssignment number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(assignments)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id, assignment_title, module_code, due_date = assignments[index]

            threshold_input = input(
                "Similarity threshold (0-100, default 60): "
            ).strip()
            try:
                threshold = float(threshold_input) if threshold_input else 60.0
                threshold = max(0, min(100, threshold))
            except ValueError:
                threshold = 60.0

            # Fetch submissions
            cursor.execute('''
                SELECT id, student_id, content, submitted_at
                FROM assignment_submissions
                WHERE assignment_id = ?
                ORDER BY student_id
            ''', (assignment_id,))
            submissions = cursor.fetchall()

            if len(submissions) < 2:
                print("Need at least 2 submissions for collusion analysis.")
                conn.close()
                return

            print(f"\nAnalysing {len(submissions)} submissions...")
            print("This may take a moment for large classes.\n")

            flagged_pairs = []
            total_pairs = 0

            for i in range(len(submissions)):
                for j in range(i + 1, len(submissions)):
                    total_pairs += 1
                    sid_a, student_a, content_a, time_a = submissions[i]
                    sid_b, student_b, content_b, time_b = submissions[j]

                    if not content_a or not content_b:
                        continue

                    # N-gram Jaccard similarity
                    ngram_sim = self._ngram_jaccard(content_a, content_b, n=3)

                    # Structural similarity
                    struct_sim = self._structural_similarity(content_a, content_b)

                    # Timing analysis
                    timing_flag = False
                    timing_diff_minutes = None
                    if time_a and time_b:
                        try:
                            t_a = datetime.strptime(time_a, '%Y-%m-%d %H:%M:%S')
                            t_b = datetime.strptime(time_b, '%Y-%m-%d %H:%M:%S')
                            timing_diff_minutes = abs((t_a - t_b).total_seconds()) / 60
                            if timing_diff_minutes < 5:
                                timing_flag = True
                        except (ValueError, TypeError):
                            pass

                    # Weighted composite score
                    composite = (ngram_sim * 0.5
                                 + struct_sim * 0.3
                                 + (100 if timing_flag else 0) * 0.2)

                    if composite >= threshold:
                        flagged_pairs.append({
                            'student_a': student_a,
                            'student_b': student_b,
                            'submission_a': sid_a,
                            'submission_b': sid_b,
                            'ngram_similarity': round(ngram_sim, 1),
                            'structural_similarity': round(struct_sim, 1),
                            'timing_diff_minutes': round(timing_diff_minutes, 1) if timing_diff_minutes is not None else None,
                            'timing_flag': timing_flag,
                            'composite_score': round(composite, 1),
                        })

            # Display results
            print("=" * 60)
            print("  Collusion Analysis Report")
            print("=" * 60)
            print(f"  Assignment  : {assignment_title} ({module_code})")
            print(f"  Submissions : {len(submissions)}")
            print(f"  Pairs Analysed : {total_pairs}")
            print(f"  Threshold   : {threshold}%")
            print(f"  Flagged     : {len(flagged_pairs)}")
            print("-" * 60)

            if not flagged_pairs:
                print("\n  No pairs exceeded the similarity threshold.")
            else:
                flagged_pairs.sort(key=lambda x: x['composite_score'], reverse=True)
                for idx, pair in enumerate(flagged_pairs, 1):
                    print(f"\n  Pair {idx}: {pair['student_a']} <-> {pair['student_b']}")
                    print(f"    N-gram Similarity      : {pair['ngram_similarity']}%")
                    print(f"    Structural Similarity  : {pair['structural_similarity']}%")
                    if pair['timing_diff_minutes'] is not None:
                        print(f"    Submission Time Gap    : {pair['timing_diff_minutes']} min", end='')
                        if pair['timing_flag']:
                            print("  [CLOSE TIMING]")
                        else:
                            print()
                    print(f"    Composite Score        : {pair['composite_score']}%")

            # Store flagged pairs
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for pair in flagged_pairs:
                cursor.execute('''
                    INSERT INTO collusion_reports
                    (assignment_id, student_a, student_b, submission_a, submission_b,
                     ngram_similarity, structural_similarity, timing_diff_minutes,
                     composite_score, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    assignment_id,
                    pair['student_a'],
                    pair['student_b'],
                    pair['submission_a'],
                    pair['submission_b'],
                    pair['ngram_similarity'],
                    pair['structural_similarity'],
                    pair['timing_diff_minutes'],
                    pair['composite_score'],
                    'pending',
                    created_at,
                ))

            conn.commit()
            conn.close()
            print(f"\n{len(flagged_pairs)} report(s) saved.")

        except Exception as e:
            print(f"Error running collusion analysis: {e}")

    def _ngram_jaccard(self, text_a, text_b, n=3):
        """Compute n-gram Jaccard similarity as a percentage."""
        def get_ngrams(text, n):
            words = re.findall(r'[a-zA-Z]+', text.lower())
            if len(words) < n:
                return set()
            return set(tuple(words[i:i + n]) for i in range(len(words) - n + 1))

        ngrams_a = get_ngrams(text_a, n)
        ngrams_b = get_ngrams(text_b, n)

        if not ngrams_a or not ngrams_b:
            return 0.0

        intersection = ngrams_a & ngrams_b
        union = ngrams_a | ngrams_b
        return (len(intersection) / len(union)) * 100 if union else 0.0

    def _structural_similarity(self, text_a, text_b):
        """Compare structural features: paragraph count, sentence lengths, word counts."""
        def features(text):
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
            sentences = self._split_sentences(text)
            words = re.findall(r'[a-zA-Z]+', text)
            sent_lens = [len(re.findall(r'[a-zA-Z]+', s)) for s in sentences]
            return {
                'para_count': len(paragraphs),
                'sent_count': len(sentences),
                'word_count': len(words),
                'avg_sent_len': sum(sent_lens) / max(len(sent_lens), 1),
                'sent_lens': sent_lens,
            }

        fa = features(text_a)
        fb = features(text_b)

        scores = []

        # Paragraph count similarity
        max_para = max(fa['para_count'], fb['para_count'], 1)
        scores.append(1 - abs(fa['para_count'] - fb['para_count']) / max_para)

        # Sentence count similarity
        max_sent = max(fa['sent_count'], fb['sent_count'], 1)
        scores.append(1 - abs(fa['sent_count'] - fb['sent_count']) / max_sent)

        # Word count similarity
        max_word = max(fa['word_count'], fb['word_count'], 1)
        scores.append(1 - abs(fa['word_count'] - fb['word_count']) / max_word)

        # Average sentence length similarity
        max_avg = max(fa['avg_sent_len'], fb['avg_sent_len'], 1)
        scores.append(1 - abs(fa['avg_sent_len'] - fb['avg_sent_len']) / max_avg)

        # Sentence length sequence similarity (truncate to shorter)
        min_len = min(len(fa['sent_lens']), len(fb['sent_lens']))
        if min_len > 0:
            diffs = []
            for k in range(min_len):
                max_val = max(fa['sent_lens'][k], fb['sent_lens'][k], 1)
                diffs.append(1 - abs(fa['sent_lens'][k] - fb['sent_lens'][k]) / max_val)
            scores.append(sum(diffs) / len(diffs))

        return (sum(scores) / len(scores)) * 100 if scores else 0.0

    # ------------------------------------------------------------------ #
    #  5. View Collusion Reports
    # ------------------------------------------------------------------ #

    def view_collusion_reports(self):
        """View flagged collusion reports and optionally mark them as reviewed."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            status_filter = input(
                "\nFilter by status (pending/reviewed/all, default all): "
            ).strip().lower()

            if status_filter in ('pending', 'reviewed'):
                cursor.execute('''
                    SELECT cr.id, a.title, cr.student_a, cr.student_b,
                           cr.ngram_similarity, cr.structural_similarity,
                           cr.timing_diff_minutes, cr.composite_score,
                           cr.status, cr.created_at
                    FROM collusion_reports cr
                    JOIN assignments a ON cr.assignment_id = a.id
                    WHERE cr.status = ?
                    ORDER BY cr.composite_score DESC
                ''', (status_filter,))
            else:
                cursor.execute('''
                    SELECT cr.id, a.title, cr.student_a, cr.student_b,
                           cr.ngram_similarity, cr.structural_similarity,
                           cr.timing_diff_minutes, cr.composite_score,
                           cr.status, cr.created_at
                    FROM collusion_reports cr
                    JOIN assignments a ON cr.assignment_id = a.id
                    ORDER BY cr.composite_score DESC
                ''')

            reports = cursor.fetchall()

            if not reports:
                print("No collusion reports found.")
                conn.close()
                return

            print(f"\n{'=' * 70}")
            print(f"  Collusion Reports ({len(reports)} found)")
            print(f"{'=' * 70}")
            print(f"  {'#':<4} {'Assignment':<20} {'Student A':<12} {'Student B':<12} "
                  f"{'Composite':<10} {'Status':<10}")
            print(f"  {'-' * 66}")

            for i, row in enumerate(reports, 1):
                rid, title, sa, sb, ngram, struct, timing, composite, status, created = row
                title_short = title[:18] + '..' if len(title) > 20 else title
                print(f"  {i:<4} {title_short:<20} {sa:<12} {sb:<12} "
                      f"{composite:<10} {status:<10}")

            # Option to view details or mark reviewed
            print("\n  Enter report number for details, 'r' to mark reviewed, or 'b' to go back.")
            action = input("  Choice: ").strip().lower()

            if action == 'b':
                conn.close()
                return

            if action == 'r':
                report_num = input("  Report number to mark as reviewed: ").strip()
                try:
                    ridx = int(report_num) - 1
                    if 0 <= ridx < len(reports):
                        cursor.execute('''
                            UPDATE collusion_reports
                            SET status = 'reviewed', reviewed_at = ?
                            WHERE id = ?
                        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), reports[ridx][0]))
                        conn.commit()
                        print("  Report marked as reviewed.")
                    else:
                        print("  Invalid report number.")
                except ValueError:
                    print("  Please enter a number.")
                conn.close()
                return

            try:
                ridx = int(action) - 1
                if 0 <= ridx < len(reports):
                    row = reports[ridx]
                    rid, title, sa, sb, ngram, struct, timing, composite, status, created = row
                    print(f"\n  {'=' * 50}")
                    print("  Collusion Report Detail")
                    print(f"  {'=' * 50}")
                    print(f"  Assignment           : {title}")
                    print(f"  Student A            : {sa}")
                    print(f"  Student B            : {sb}")
                    print(f"  N-gram Similarity    : {ngram}%")
                    print(f"  Structural Similarity: {struct}%")
                    if timing is not None:
                        print(f"  Timing Difference    : {timing} minutes")
                    else:
                        print("  Timing Difference    : N/A")
                    print(f"  Composite Score      : {composite}%")
                    print(f"  Status               : {status}")
                    print(f"  Created              : {created}")

                    if status == 'pending':
                        mark = input("\n  Mark as reviewed? (y/n): ").strip().lower()
                        if mark == 'y':
                            cursor.execute('''
                                UPDATE collusion_reports
                                SET status = 'reviewed', reviewed_at = ?
                                WHERE id = ?
                            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), rid))
                            conn.commit()
                            print("  Report marked as reviewed.")
                else:
                    print("  Invalid selection.")
            except ValueError:
                print("  Invalid input.")

            conn.close()

        except Exception as e:
            print(f"Error viewing collusion reports: {e}")

    # ------------------------------------------------------------------ #
    #  6. Late Pass Recommendation
    # ------------------------------------------------------------------ #

    def get_late_pass_recommendation(self):
        """Analyse student history and recommend grant/deny for a late pass."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            student_id = input("\nEnter student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                conn.close()
                return

            # Select assignment
            cursor.execute('''
                SELECT id, title, module_code, due_date
                FROM assignments
                WHERE is_active = 1
                ORDER BY due_date
            ''')
            assignments = cursor.fetchall()

            if not assignments:
                print("No active assignments found.")
                conn.close()
                return

            print("\nSelect Assignment:")
            for i, (aid, title, module, due) in enumerate(assignments, 1):
                print(f"  {i}. {title} ({module}) - Due: {due}")

            choice = input("\nAssignment number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(assignments)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id, assignment_title, module_code, due_date = assignments[index]

            # Gather student history
            # 1. On-time rate
            cursor.execute('''
                SELECT COUNT(*) FROM assignment_submissions
                WHERE student_id = ?
            ''', (student_id,))
            total_submissions = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM assignment_submissions
                WHERE student_id = ? AND late_submission = 0
            ''', (student_id,))
            on_time_count = cursor.fetchone()[0]

            on_time_rate = (on_time_count / total_submissions * 100) if total_submissions > 0 else 100.0

            # 2. Prior late-pass usage
            cursor.execute('''
                SELECT COUNT(*) FROM late_pass_recommendations
                WHERE student_id = ? AND recommendation = 'grant'
            ''', (student_id,))
            prior_grants = cursor.fetchone()[0]

            # 3. Grade trend
            cursor.execute('''
                SELECT grade FROM assignment_submissions
                WHERE student_id = ? AND grade IS NOT NULL
                ORDER BY submitted_at
            ''', (student_id,))
            grades = [row[0] for row in cursor.fetchall()]

            grade_trend = 'stable'
            trend_value = 0.0
            if len(grades) >= 2:
                recent_half = grades[len(grades) // 2:]
                earlier_half = grades[:len(grades) // 2]
                avg_recent = sum(recent_half) / len(recent_half)
                avg_earlier = sum(earlier_half) / len(earlier_half)
                trend_value = avg_recent - avg_earlier
                if trend_value > 5:
                    grade_trend = 'improving'
                elif trend_value < -5:
                    grade_trend = 'declining'

            # 4. Extension history
            cursor.execute('''
                SELECT COUNT(*) FROM late_pass_recommendations
                WHERE student_id = ?
            ''', (student_id,))
            total_requests = cursor.fetchone()[0]

            # Decision logic
            confidence = 50.0
            reasons = []

            # On-time rate factor
            if on_time_rate >= 80:
                confidence += 20
                reasons.append(f"Strong on-time record ({on_time_rate:.0f}%)")
            elif on_time_rate >= 60:
                confidence += 5
                reasons.append(f"Moderate on-time record ({on_time_rate:.0f}%)")
            else:
                confidence -= 15
                reasons.append(f"Low on-time record ({on_time_rate:.0f}%)")

            # Prior grants factor
            if prior_grants == 0:
                confidence += 15
                reasons.append("No prior late passes granted")
            elif prior_grants <= 2:
                confidence += 0
                reasons.append(f"{prior_grants} prior late pass(es) granted")
            else:
                confidence -= 15
                reasons.append(f"Multiple late passes already granted ({prior_grants})")

            # Grade trend factor
            if grade_trend == 'improving':
                confidence += 10
                reasons.append(f"Grades are improving (trend: +{trend_value:.1f})")
            elif grade_trend == 'declining':
                confidence -= 10
                reasons.append(f"Grades are declining (trend: {trend_value:.1f})")
            else:
                reasons.append("Grades are stable")

            # Total requests factor
            if total_requests > 3:
                confidence -= 10
                reasons.append(f"High number of prior requests ({total_requests})")

            # New student bonus
            if total_submissions <= 2:
                confidence += 5
                reasons.append("Relatively new student (few submissions)")

            confidence = max(0, min(100, confidence))
            recommendation = 'grant' if confidence >= 50 else 'deny'

            # Display recommendation
            print(f"\n{'=' * 60}")
            print("  Late Pass Recommendation")
            print(f"{'=' * 60}")
            print(f"  Student          : {student_id}")
            print(f"  Assignment       : {assignment_title} ({module_code})")
            print(f"  Due Date         : {due_date}")
            print("\n  --- Student History ---")
            print(f"  Total Submissions   : {total_submissions}")
            print(f"  On-time Rate        : {on_time_rate:.1f}%")
            print(f"  Prior Late Passes   : {prior_grants}")
            print(f"  Grade Trend         : {grade_trend}")
            if grades:
                avg_grade = sum(grades) / len(grades)
                print(f"  Average Grade       : {avg_grade:.1f}%")
            print(f"  Total Requests      : {total_requests}")
            print("\n  --- Recommendation ---")
            print(f"  Decision    : {recommendation.upper()}")
            print(f"  Confidence  : {confidence:.0f}%")
            print("\n  Factors:")
            for reason in reasons:
                print(f"    - {reason}")
            print(f"{'-' * 60}")

            # Store recommendation
            cursor.execute('''
                INSERT INTO late_pass_recommendations
                (student_id, assignment_id, recommendation, confidence,
                 on_time_rate, prior_grants, grade_trend, reasons_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id,
                assignment_id,
                recommendation,
                confidence,
                on_time_rate,
                prior_grants,
                grade_trend,
                json.dumps(reasons),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            print("\nRecommendation saved.")
            conn.close()

        except Exception as e:
            print(f"Error generating late pass recommendation: {e}")

    # ------------------------------------------------------------------ #
    #  7. View Late Pass Recommendations
    # ------------------------------------------------------------------ #

    def view_late_pass_recommendations(self):
        """View all late pass recommendations."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT lpr.id, lpr.student_id, a.title, lpr.recommendation,
                       lpr.confidence, lpr.on_time_rate, lpr.prior_grants,
                       lpr.grade_trend, lpr.reasons_json, lpr.created_at
                FROM late_pass_recommendations lpr
                JOIN assignments a ON lpr.assignment_id = a.id
                ORDER BY lpr.created_at DESC
            ''')
            rows = cursor.fetchall()

            if not rows:
                print("No late pass recommendations found.")
                conn.close()
                return

            print(f"\n{'=' * 70}")
            print(f"  Late Pass Recommendations ({len(rows)} total)")
            print(f"{'=' * 70}")
            print(f"  {'#':<4} {'Student':<12} {'Assignment':<20} {'Decision':<8} "
                  f"{'Confidence':<11} {'Date':<12}")
            print(f"  {'-' * 66}")

            for i, row in enumerate(rows, 1):
                rid, student, title, rec, conf, otr, pg, gt, reasons, created = row
                title_short = title[:18] + '..' if len(title) > 20 else title
                date_short = created[:10] if created else 'N/A'
                print(f"  {i:<4} {student:<12} {title_short:<20} {rec.upper():<8} "
                      f"{conf:<10.0f}% {date_short:<12}")

            # Detail view
            detail = input("\nEnter number for details (or 'b' to go back): ").strip()
            if detail.lower() == 'b':
                conn.close()
                return

            try:
                didx = int(detail) - 1
                if 0 <= didx < len(rows):
                    row = rows[didx]
                    rid, student, title, rec, conf, otr, pg, gt, reasons_json, created = row
                    reasons = json.loads(reasons_json) if reasons_json else []

                    print(f"\n  {'=' * 50}")
                    print("  Late Pass Recommendation Detail")
                    print(f"  {'=' * 50}")
                    print(f"  Student        : {student}")
                    print(f"  Assignment     : {title}")
                    print(f"  Decision       : {rec.upper()}")
                    print(f"  Confidence     : {conf:.0f}%")
                    print(f"  On-time Rate   : {otr:.1f}%")
                    print(f"  Prior Grants   : {pg}")
                    print(f"  Grade Trend    : {gt}")
                    print(f"  Created        : {created}")
                    if reasons:
                        print("\n  Factors:")
                        for r in reasons:
                            print(f"    - {r}")
                else:
                    print("  Invalid selection.")
            except ValueError:
                print("  Invalid input.")

            conn.close()

        except Exception as e:
            print(f"Error viewing late pass recommendations: {e}")

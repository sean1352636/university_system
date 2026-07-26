"""AI Assistant Manager for assignment system - rule-based AI features"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import re
import math
from datetime import datetime, timedelta
from collections import Counter
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class AIAssistantManager:
    """AI assistant features for the assignment system using rule-based heuristics"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style
        self._init_tables()

    def _init_tables(self):
        """Create required database tables if they don't exist"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ai_feedback_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        assignment_id INTEGER,
                        draft_text TEXT NOT NULL,
                        feedback_json TEXT,
                        requested_at TEXT NOT NULL,
                        completed_at TEXT
                    )
                ''')
                # Must match the canonical definition in db_manager.py.
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS practice_questions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        module_code TEXT,
                        source_material TEXT,
                        question_text TEXT NOT NULL,
                        answer TEXT,
                        question_type TEXT DEFAULT 'mcq',
                        generated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS collusion_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        student_id_1 TEXT NOT NULL,
                        student_id_2 TEXT NOT NULL,
                        similarity_score REAL NOT NULL,
                        analysis_json TEXT,
                        flagged INTEGER DEFAULT 0,
                        reviewed INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS late_pass_recommendations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        assignment_id INTEGER,
                        recommendation TEXT NOT NULL,
                        confidence_score REAL NOT NULL,
                        reasoning_json TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error initializing AI assistant tables: {e}")

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    # -------------------------------------------------------------------------
    # Main Dashboard
    # -------------------------------------------------------------------------

    def show_ai_dashboard(self):
        """Main AI features dashboard"""
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="AI Assistant Dashboard", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        desc = ttk.Label(
            parent,
            text="Rule-based AI tools for feedback, practice generation, "
                 "collusion detection, and late-pass advising.",
            wraplength=700,
        )
        desc.pack(anchor='w', pady=(0, 15))

        cards_frame = ttk.Frame(parent)
        cards_frame.pack(fill='both', expand=True)

        features = [
            (
                "Draft Feedback",
                "Submit a draft and receive writing suggestions, "
                "structure feedback, and readability analysis.",
                self.show_draft_feedback,
            ),
            (
                "Practice Question Generator",
                "Auto-generate MCQ and short-answer questions "
                "from uploaded course materials.",
                self.show_practice_generator,
            ),
            (
                "Collusion Detector",
                "Analyse submissions for suspicious similarity "
                "using structural, timing, and error patterns.",
                self.show_collusion_detector,
            ),
            (
                "Late-Pass Advisor",
                "Get smart late-pass recommendations based on "
                "student submission history and patterns.",
                self.show_late_pass_advisor,
            ),
        ]

        for idx, (feat_title, feat_desc, callback) in enumerate(features):
            row, col = divmod(idx, 2)
            card = ttk.LabelFrame(cards_frame, text=feat_title, padding=15)
            card.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            cards_frame.columnconfigure(col, weight=1)
            cards_frame.rowconfigure(row, weight=1)

            ttk.Label(card, text=feat_desc, wraplength=280).pack(
                anchor='w', pady=(0, 10)
            )
            ttk.Button(card, text=f"Open {feat_title}", command=callback).pack(
                anchor='w'
            )

        # Recent activity
        activity_frame = ttk.LabelFrame(parent, text="Recent Activity", padding=10)
        activity_frame.pack(fill='x', padx=10, pady=(20, 0))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM ai_feedback_requests "
                    "WHERE requested_at > datetime('now', '-7 days')"
                )
                feedback_count = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM practice_questions "
                    "WHERE generated_at > datetime('now', '-7 days')"
                )
                questions_count = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM collusion_reports "
                    "WHERE created_at > datetime('now', '-7 days')"
                )
                collusion_count = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM late_pass_recommendations "
                    "WHERE created_at > datetime('now', '-7 days')"
                )
                late_pass_count = cursor.fetchone()[0]
            finally:
                conn.close()

            stats_text = (
                f"Last 7 days:  Feedback requests: {feedback_count}  |  "
                f"Questions generated: {questions_count}  |  "
                f"Collusion reports: {collusion_count}  |  "
                f"Late-pass recommendations: {late_pass_count}"
            )
        except Exception:
            stats_text = "No activity data available."

        ttk.Label(activity_frame, text=stats_text).pack(anchor='w')

    # -------------------------------------------------------------------------
    # Draft Feedback
    # -------------------------------------------------------------------------

    def show_draft_feedback(self):
        """Student interface to submit a draft for AI feedback"""
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="AI Draft Feedback", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        ttk.Label(
            parent,
            text="Paste your draft below for writing suggestions and structure feedback. "
                 "This is not grading — it helps you improve before final submission.",
            wraplength=700,
        ).pack(anchor='w', pady=(0, 10))

        # Assignment selector
        sel_frame = ttk.Frame(parent)
        sel_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(sel_frame, text="Assignment (optional):").pack(side='left')
        self._feedback_assignment_var = tk.StringVar()
        assignment_combo = ttk.Combobox(
            sel_frame, textvariable=self._feedback_assignment_var, width=50, state='readonly'
        )
        assignment_combo.pack(side='left', padx=(5, 0))
        self._load_assignments_into_combo(assignment_combo)

        # Draft text area
        ttk.Label(parent, text="Draft Text:").pack(anchor='w')
        self._draft_text = scrolledtext.ScrolledText(parent, height=14, wrap='word')
        self._draft_text.pack(fill='both', expand=True, pady=(2, 10))

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x')
        ttk.Button(
            btn_frame, text="Get Feedback", command=self._on_submit_draft
        ).pack(side='left')
        ttk.Button(
            btn_frame, text="Back to Dashboard", command=self.show_ai_dashboard
        ).pack(side='right')

        # Feedback output area
        ttk.Label(parent, text="Feedback:").pack(anchor='w', pady=(10, 0))
        self._feedback_output = scrolledtext.ScrolledText(
            parent, height=12, wrap='word', state='disabled'
        )
        self._feedback_output.pack(fill='both', expand=True, pady=(2, 0))

    def _on_submit_draft(self):
        """Handle draft submission"""
        draft_text = self._draft_text.get('1.0', 'end').strip()
        if not draft_text:
            messagebox.showwarning("Empty Draft", "Please enter some text before requesting feedback.")
            return
        if len(draft_text) < 50:
            messagebox.showwarning(
                "Draft Too Short",
                "Please provide at least 50 characters for meaningful feedback.",
            )
            return

        feedback = self.generate_ai_feedback(draft_text)

        # Save to database
        try:
            student_id = self._get_current_student_id()
            assignment_id = self._parse_assignment_id(self._feedback_assignment_var.get())
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "INSERT INTO ai_feedback_requests "
                    "(student_id, assignment_id, draft_text, feedback_json, requested_at, completed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (student_id, assignment_id, draft_text, json.dumps(feedback), now, now),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error saving feedback request: {e}")

        # Display feedback
        self._feedback_output.configure(state='normal')
        self._feedback_output.delete('1.0', 'end')
        self._feedback_output.insert('end', self._format_feedback(feedback))
        self._feedback_output.configure(state='disabled')

    def generate_ai_feedback(self, draft_text):
        """Generate writing suggestions using rule-based analysis.

        Analyses structure, length, grammar patterns, and readability.
        Returns a dict with categorised feedback.
        """
        feedback = {
            'readability': self._analyse_readability(draft_text),
            'structure': self._analyse_structure(draft_text),
            'style': self._analyse_style(draft_text),
            'suggestions': [],
        }

        # Overall word/sentence stats
        words = draft_text.split()
        sentences = re.split(r'[.!?]+', draft_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        paragraphs = [p.strip() for p in draft_text.split('\n\n') if p.strip()]

        word_count = len(words)
        sentence_count = max(len(sentences), 1)
        avg_sentence_len = word_count / sentence_count

        feedback['statistics'] = {
            'word_count': word_count,
            'sentence_count': sentence_count,
            'paragraph_count': len(paragraphs),
            'avg_sentence_length': round(avg_sentence_len, 1),
        }

        # Actionable suggestions
        if word_count < 200:
            feedback['suggestions'].append(
                "Your draft is quite short. Consider expanding your arguments with "
                "more supporting evidence or examples."
            )
        if avg_sentence_len > 25:
            feedback['suggestions'].append(
                "Your average sentence length is high ({:.0f} words). "
                "Consider breaking some longer sentences into shorter ones "
                "for improved readability.".format(avg_sentence_len)
            )
        if avg_sentence_len < 8:
            feedback['suggestions'].append(
                "Your sentences are quite short on average. Consider combining "
                "related ideas to improve flow."
            )
        if len(paragraphs) == 1 and word_count > 150:
            feedback['suggestions'].append(
                "Your text is a single block. Break it into paragraphs to "
                "improve organisation and readability."
            )

        # Check for repeated words (overuse)
        word_freq = Counter(w.lower() for w in words if len(w) > 4)
        total = max(len(words), 1)
        for w, count in word_freq.most_common(5):
            if count / total > 0.03 and count > 3:
                feedback['suggestions'].append(
                    f"The word \"{w}\" appears {count} times. "
                    "Consider using synonyms for variety."
                )

        # Passive voice rough check
        passive_patterns = re.findall(
            r'\b(?:is|are|was|were|been|being|be)\s+\w+ed\b', draft_text, re.IGNORECASE
        )
        if len(passive_patterns) > sentence_count * 0.4:
            feedback['suggestions'].append(
                "A high proportion of sentences may use passive voice. "
                "Consider rewriting some in active voice for directness."
            )

        # Transition word check
        transitions = {
            'however', 'moreover', 'furthermore', 'therefore', 'consequently',
            'nevertheless', 'additionally', 'meanwhile', 'conversely', 'similarly',
            'in addition', 'on the other hand', 'as a result', 'in contrast',
        }
        text_lower = draft_text.lower()
        found_transitions = [t for t in transitions if t in text_lower]
        if len(paragraphs) > 2 and len(found_transitions) < 2:
            feedback['suggestions'].append(
                "Consider adding transition words (e.g. however, moreover, therefore) "
                "to improve the flow between paragraphs."
            )

        if not feedback['suggestions']:
            feedback['suggestions'].append(
                "Your draft looks well-structured overall. Review for "
                "specific content accuracy before final submission."
            )

        return feedback

    def _analyse_readability(self, text):
        """Compute Flesch-Kincaid readability metrics"""
        words = text.split()
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        word_count = max(len(words), 1)
        sentence_count = max(len(sentences), 1)

        # Syllable estimation
        syllable_count = sum(self._count_syllables(w) for w in words)

        # Flesch Reading Ease
        fre = (
            206.835
            - 1.015 * (word_count / sentence_count)
            - 84.6 * (syllable_count / word_count)
        )
        fre = max(0.0, min(100.0, fre))

        # Flesch-Kincaid Grade Level
        fk_grade = (
            0.39 * (word_count / sentence_count)
            + 11.8 * (syllable_count / word_count)
            - 15.59
        )
        fk_grade = max(0.0, fk_grade)

        if fre >= 70:
            level = "Easy"
        elif fre >= 50:
            level = "Moderate"
        elif fre >= 30:
            level = "Difficult"
        else:
            level = "Very Difficult"

        return {
            'flesch_reading_ease': round(fre, 1),
            'flesch_kincaid_grade': round(fk_grade, 1),
            'level': level,
        }

    def _count_syllables(self, word):
        """Estimate syllable count for a word"""
        word = word.lower().strip(".,;:!?\"'()-")
        if not word:
            return 1
        count = 0
        vowels = 'aeiouy'
        prev_vowel = False
        for ch in word:
            is_vowel = ch in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if word.endswith('e') and count > 1:
            count -= 1
        return max(count, 1)

    def _analyse_structure(self, text):
        """Analyse document structure"""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        para_lengths = [len(p.split()) for p in paragraphs]

        issues = []
        if para_lengths:
            max_para = max(para_lengths)
            min_para = min(para_lengths)
            if max_para > 200:
                issues.append("Some paragraphs are very long (>200 words). Consider splitting.")
            if min_para < 20 and len(paragraphs) > 1:
                issues.append("Some paragraphs are very short (<20 words). Consider expanding or merging.")
            variance = (
                sum((l - sum(para_lengths) / len(para_lengths)) ** 2 for l in para_lengths)
                / len(para_lengths)
            )
            if math.sqrt(variance) > 80:
                issues.append("Paragraph lengths vary significantly. Aim for more consistent sizing.")

        # Check for introduction / conclusion signals
        first_para = paragraphs[0].lower() if paragraphs else ''
        last_para = paragraphs[-1].lower() if paragraphs else ''
        has_intro_signal = any(
            kw in first_para
            for kw in ['introduction', 'this essay', 'this paper', 'in this', 'the purpose']
        )
        has_conclusion_signal = any(
            kw in last_para
            for kw in ['conclusion', 'in summary', 'to conclude', 'in closing', 'overall']
        )

        return {
            'paragraph_count': len(paragraphs),
            'paragraph_lengths': para_lengths,
            'has_intro_signal': has_intro_signal,
            'has_conclusion_signal': has_conclusion_signal,
            'issues': issues,
        }

    def _analyse_style(self, text):
        """Analyse writing style patterns"""
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        issues = []

        # Sentence-start variety
        if len(sentences) >= 5:
            starts = [s.split()[0].lower() if s.split() else '' for s in sentences]
            start_freq = Counter(starts)
            for word, cnt in start_freq.most_common(3):
                if cnt >= 3 and cnt / len(sentences) > 0.25:
                    issues.append(
                        f"Many sentences start with \"{word}\". Vary your sentence openings."
                    )

        # Informal language
        informal = {'gonna', 'wanna', 'gotta', 'kinda', 'sorta', 'ain\'t', 'lots of', 'stuff'}
        found_informal = [w for w in informal if w in text.lower()]
        if found_informal:
            issues.append(
                f"Informal language detected: {', '.join(found_informal)}. "
                "Consider more formal alternatives for academic writing."
            )

        # Hedging words
        hedges = ['maybe', 'perhaps', 'possibly', 'might', 'could be', 'sort of', 'kind of']
        hedge_count = sum(text.lower().count(h) for h in hedges)
        if hedge_count > len(sentences) * 0.3:
            issues.append(
                "Frequent hedging language detected. State your points "
                "with more confidence where appropriate."
            )

        return {'issues': issues}

    def _format_feedback(self, feedback):
        """Format feedback dict into readable text"""
        lines = []
        lines.append("=== AI DRAFT FEEDBACK ===\n")

        stats = feedback.get('statistics', {})
        lines.append("--- Statistics ---")
        lines.append(f"  Words: {stats.get('word_count', 'N/A')}")
        lines.append(f"  Sentences: {stats.get('sentence_count', 'N/A')}")
        lines.append(f"  Paragraphs: {stats.get('paragraph_count', 'N/A')}")
        lines.append(f"  Avg sentence length: {stats.get('avg_sentence_length', 'N/A')} words")
        lines.append("")

        rd = feedback.get('readability', {})
        lines.append("--- Readability ---")
        lines.append(f"  Flesch Reading Ease: {rd.get('flesch_reading_ease', 'N/A')} ({rd.get('level', '')})")
        lines.append(f"  Flesch-Kincaid Grade Level: {rd.get('flesch_kincaid_grade', 'N/A')}")
        lines.append("")

        structure = feedback.get('structure', {})
        lines.append("--- Structure ---")
        lines.append(f"  Paragraphs: {structure.get('paragraph_count', 'N/A')}")
        lines.append(f"  Introduction signal detected: {'Yes' if structure.get('has_intro_signal') else 'No'}")
        lines.append(f"  Conclusion signal detected: {'Yes' if structure.get('has_conclusion_signal') else 'No'}")
        for issue in structure.get('issues', []):
            lines.append(f"  * {issue}")
        lines.append("")

        style = feedback.get('style', {})
        if style.get('issues'):
            lines.append("--- Style ---")
            for issue in style['issues']:
                lines.append(f"  * {issue}")
            lines.append("")

        suggestions = feedback.get('suggestions', [])
        if suggestions:
            lines.append("--- Suggestions ---")
            for i, s in enumerate(suggestions, 1):
                lines.append(f"  {i}. {s}")

        return '\n'.join(lines)

    # -------------------------------------------------------------------------
    # Practice Question Generator
    # -------------------------------------------------------------------------

    def show_practice_generator(self):
        """Interface to generate practice questions from materials"""
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Practice Question Generator", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        ttk.Label(
            parent,
            text="Paste or load course material below to auto-generate practice questions.",
            wraplength=700,
        ).pack(anchor='w', pady=(0, 10))

        # Options row
        opt_frame = ttk.Frame(parent)
        opt_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(opt_frame, text="Module Code:").pack(side='left')
        self._pq_module_var = tk.StringVar()
        ttk.Entry(opt_frame, textvariable=self._pq_module_var, width=15).pack(side='left', padx=(5, 15))

        ttk.Label(opt_frame, text="Question Type:").pack(side='left')
        self._pq_type_var = tk.StringVar(value='mcq')
        ttk.Combobox(
            opt_frame, textvariable=self._pq_type_var,
            values=['mcq', 'short_answer', 'mixed'], width=14, state='readonly',
        ).pack(side='left', padx=(5, 15))

        ttk.Label(opt_frame, text="Count:").pack(side='left')
        self._pq_count_var = tk.IntVar(value=5)
        ttk.Spinbox(
            opt_frame, textvariable=self._pq_count_var,
            from_=1, to=20, width=5,
        ).pack(side='left', padx=(5, 0))

        # Source material
        ttk.Label(parent, text="Source Material:").pack(anchor='w')
        self._pq_source = scrolledtext.ScrolledText(parent, height=10, wrap='word')
        self._pq_source.pack(fill='both', expand=True, pady=(2, 5))

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', pady=(0, 5))
        ttk.Button(
            btn_frame, text="Load from File", command=self._load_material_file
        ).pack(side='left', padx=(0, 10))
        ttk.Button(
            btn_frame, text="Generate Questions", command=self._on_generate_questions
        ).pack(side='left')
        ttk.Button(
            btn_frame, text="Back to Dashboard", command=self.show_ai_dashboard
        ).pack(side='right')

        # Output
        ttk.Label(parent, text="Generated Questions:").pack(anchor='w', pady=(5, 0))
        self._pq_output = scrolledtext.ScrolledText(
            parent, height=12, wrap='word', state='disabled'
        )
        self._pq_output.pack(fill='both', expand=True, pady=(2, 0))

    def _load_material_file(self):
        """Load source material from a text file"""
        path = filedialog.askopenfilename(
            title="Select Source Material",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._pq_source.delete('1.0', 'end')
                self._pq_source.insert('1.0', content)
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {e}")

    def _on_generate_questions(self):
        """Handle question generation request"""
        content = self._pq_source.get('1.0', 'end').strip()
        if not content or len(content) < 30:
            messagebox.showwarning(
                "Insufficient Material",
                "Please provide at least 30 characters of source material.",
            )
            return

        count = self._pq_count_var.get()
        q_type = self._pq_type_var.get()
        module_code = self._pq_module_var.get().strip() or "UNKNOWN"

        questions = self.generate_practice_questions(content, count, q_type)

        # Save to database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for q in questions:
                    cursor.execute(
                        "INSERT INTO practice_questions "
                        "(module_code, source_material, question_text, answer, question_type, generated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (module_code, content[:500], q['question'], q.get('answer', ''), q['type'], now),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error saving practice questions: {e}")

        # Display
        self._pq_output.configure(state='normal')
        self._pq_output.delete('1.0', 'end')
        self._pq_output.insert('end', self._format_questions(questions))
        self._pq_output.configure(state='disabled')

    def generate_practice_questions(self, content, count, question_type):
        """Generate practice questions from content using keyword extraction
        and template-based generation.

        Args:
            content: Source material text.
            count: Number of questions to generate.
            question_type: 'mcq', 'short_answer', or 'mixed'.

        Returns:
            List of dicts with 'question', 'answer', 'type', and optionally 'options'.
        """
        keywords = self._extract_keywords(content)
        sentences = [s.strip() for s in re.split(r'[.!?]+', content) if len(s.strip()) > 20]
        questions = []

        # Determine type sequence
        if question_type == 'mixed':
            types_cycle = ['mcq', 'short_answer']
        else:
            types_cycle = [question_type]

        for i in range(count):
            q_type = types_cycle[i % len(types_cycle)]
            sent_idx = i % max(len(sentences), 1)
            sentence = sentences[sent_idx] if sentences else content[:200]

            if q_type == 'mcq':
                q = self._generate_mcq(sentence, keywords, i)
            else:
                q = self._generate_short_answer(sentence, keywords, i)
            questions.append(q)

        return questions

    def _extract_keywords(self, text):
        """Extract significant keywords from text using frequency and filtering"""
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'for',
            'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'under', 'and', 'but',
            'or', 'nor', 'not', 'so', 'yet', 'both', 'either', 'neither', 'each',
            'every', 'all', 'any', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'only', 'own', 'same', 'than', 'too', 'very', 'just', 'because',
            'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their',
            'we', 'our', 'you', 'your', 'he', 'she', 'his', 'her', 'which', 'who',
            'whom', 'what', 'when', 'where', 'why', 'how', 'if', 'then', 'also',
            'about', 'up', 'out', 'many', 'well', 'back', 'there', 'over',
        }
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        filtered = [w for w in words if w not in stopwords]
        freq = Counter(filtered)
        # Return top keywords by frequency
        return [w for w, _ in freq.most_common(30)]

    def _generate_mcq(self, sentence, keywords, index):
        """Generate a multiple-choice question from a sentence"""
        # Find a keyword in the sentence to blank out
        sent_words = re.findall(r'\b[a-zA-Z]{3,}\b', sentence)
        target = None
        for w in sent_words:
            if w.lower() in keywords[:15]:
                target = w
                break
        if not target and sent_words:
            target = sent_words[min(index, len(sent_words) - 1)]

        if target:
            blanked = sentence.replace(target, "______", 1)
            # Generate distractors from other keywords
            distractors = [
                kw for kw in keywords if kw.lower() != target.lower()
            ][:3]
            while len(distractors) < 3:
                distractors.append(f"option_{len(distractors) + 1}")

            options = [target.lower()] + [d.lower() for d in distractors]
            # Shuffle deterministically based on index
            for j in range(len(options)):
                swap = (j + index + 1) % len(options)
                options[j], options[swap] = options[swap], options[j]

            correct_letter = chr(65 + options.index(target.lower()))

            return {
                'type': 'mcq',
                'question': f"Fill in the blank: {blanked.strip()}",
                'options': {chr(65 + k): opt for k, opt in enumerate(options)},
                'answer': f"{correct_letter}) {target.lower()}",
            }

        return {
            'type': 'mcq',
            'question': f"Which of the following best describes: {sentence.strip()[:80]}...?",
            'options': {'A': 'True', 'B': 'False', 'C': 'Partially true', 'D': 'Not enough information'},
            'answer': 'A) True',
        }

    def _generate_short_answer(self, sentence, keywords, index):
        """Generate a short-answer question from a sentence"""
        templates = [
            "Explain the significance of {keyword} in the context of the following: \"{sentence}\"",
            "In your own words, describe what is meant by: \"{sentence}\"",
            "What is the role of {keyword} as discussed in the source material?",
            "Briefly define {keyword} and explain its relevance.",
            "Summarise the key point made in the following passage: \"{sentence}\"",
        ]

        kw = keywords[index % max(len(keywords), 1)] if keywords else "the topic"
        short_sent = sentence.strip()[:120]
        template = templates[index % len(templates)]
        question = template.format(keyword=kw, sentence=short_sent)

        return {
            'type': 'short_answer',
            'question': question,
            'answer': f"Answer should reference: {kw}. See source material for details.",
        }

    def _format_questions(self, questions):
        """Format generated questions for display"""
        lines = ["=== GENERATED PRACTICE QUESTIONS ===\n"]
        for i, q in enumerate(questions, 1):
            lines.append(f"Q{i}. [{q['type'].upper()}]")
            lines.append(f"  {q['question']}")
            if 'options' in q:
                for letter, opt in sorted(q['options'].items()):
                    lines.append(f"    {letter}) {opt}")
            lines.append(f"  Answer: {q['answer']}")
            lines.append("")
        return '\n'.join(lines)

    # -------------------------------------------------------------------------
    # Collusion Detection
    # -------------------------------------------------------------------------

    def show_collusion_detector(self):
        """Collusion detection dashboard"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to access collusion detection.")
            return

        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Collusion Detection", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        ttk.Label(
            parent,
            text="Analyse submissions for suspicious similarity beyond simple plagiarism — "
                 "structural patterns, timing analysis, and shared unusual errors.",
            wraplength=700,
        ).pack(anchor='w', pady=(0, 10))

        # Assignment selector
        sel_frame = ttk.Frame(parent)
        sel_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(sel_frame, text="Select Assignment:").pack(side='left')
        self._cd_assignment_var = tk.StringVar()
        cd_combo = ttk.Combobox(
            sel_frame, textvariable=self._cd_assignment_var, width=50, state='readonly'
        )
        cd_combo.pack(side='left', padx=(5, 15))
        self._load_assignments_into_combo(cd_combo)

        ttk.Button(
            sel_frame, text="Run Analysis", command=self._on_run_collusion
        ).pack(side='left')
        ttk.Button(
            sel_frame, text="Back to Dashboard", command=self.show_ai_dashboard
        ).pack(side='right')

        # Results area - treeview
        results_frame = ttk.LabelFrame(parent, text="Analysis Results", padding=10)
        results_frame.pack(fill='both', expand=True, pady=(5, 5))

        columns = ('pair', 'similarity', 'timing', 'structural', 'errors', 'flagged')
        self._cd_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)
        self._cd_tree.heading('pair', text='Student Pair')
        self._cd_tree.heading('similarity', text='Overall %')
        self._cd_tree.heading('timing', text='Timing Score')
        self._cd_tree.heading('structural', text='Structural Score')
        self._cd_tree.heading('errors', text='Error Match')
        self._cd_tree.heading('flagged', text='Flagged')

        self._cd_tree.column('pair', width=200)
        self._cd_tree.column('similarity', width=80, anchor='center')
        self._cd_tree.column('timing', width=100, anchor='center')
        self._cd_tree.column('structural', width=110, anchor='center')
        self._cd_tree.column('errors', width=100, anchor='center')
        self._cd_tree.column('flagged', width=70, anchor='center')

        scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=self._cd_tree.yview)
        self._cd_tree.configure(yscrollcommand=scrollbar.set)
        self._cd_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Detail area
        detail_frame = ttk.LabelFrame(parent, text="Detailed Analysis", padding=10)
        detail_frame.pack(fill='both', expand=True, pady=(5, 0))
        self._cd_detail = scrolledtext.ScrolledText(
            detail_frame, height=8, wrap='word', state='disabled'
        )
        self._cd_detail.pack(fill='both', expand=True)

        self._cd_tree.bind('<<TreeviewSelect>>', self._on_collusion_select)

        # Load previous reports
        self._load_previous_collusion_reports()

    def _on_run_collusion(self):
        """Handle collusion analysis request"""
        assignment_id = self._parse_assignment_id(self._cd_assignment_var.get())
        if not assignment_id:
            messagebox.showwarning("No Assignment", "Please select an assignment to analyse.")
            return

        results = self.run_collusion_analysis(assignment_id)

        # Clear tree
        for item in self._cd_tree.get_children():
            self._cd_tree.delete(item)

        if not results:
            messagebox.showinfo("No Results", "No submission pairs found for analysis.")
            return

        for r in results:
            flagged_text = "YES" if r['flagged'] else "No"
            self._cd_tree.insert('', 'end', values=(
                f"{r['student_id_1']} vs {r['student_id_2']}",
                f"{r['similarity_score']:.1f}%",
                f"{r['timing_score']:.2f}",
                f"{r['structural_score']:.2f}",
                f"{r['error_match_score']:.2f}",
                flagged_text,
            ), tags=('flagged',) if r['flagged'] else ())

        self._cd_tree.tag_configure('flagged', background='#ffcccc')

        messagebox.showinfo(
            "Analysis Complete",
            f"Analysed {len(results)} submission pairs. "
            f"{sum(1 for r in results if r['flagged'])} flagged for review.",
        )

    def run_collusion_analysis(self, assignment_id):
        """Analyse submissions for similar patterns.

        Checks submission timing, structural similarity, shared unusual errors,
        and n-gram overlap. Returns list of pair analysis dicts.
        """
        results = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT student_id, submission_text, submission_date "
                    "FROM ai_detector_submissions "
                    "WHERE assignment_id = ? ORDER BY student_id",
                    (assignment_id,),
                )
                submissions = cursor.fetchall()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error loading submissions: {e}")
            return results

        if len(submissions) < 2:
            return results

        # Compare all pairs
        for i in range(len(submissions)):
            for j in range(i + 1, len(submissions)):
                s1_id, s1_content, s1_time = submissions[i]
                s2_id, s2_content, s2_time = submissions[j]

                s1_text = s1_content or ''
                s2_text = s2_content or ''

                if not s1_text or not s2_text:
                    continue

                # Timing analysis
                timing_score = self._compute_timing_similarity(s1_time, s2_time)

                # Structural similarity
                structural_score = self._compute_structural_similarity(s1_text, s2_text)

                # N-gram text overlap
                ngram_score = self._compute_ngram_similarity(s1_text, s2_text, n=4)

                # Shared unusual error patterns
                error_match_score = self._compute_error_similarity(s1_text, s2_text)

                # Weighted overall score
                overall = (
                    0.15 * timing_score
                    + 0.35 * structural_score
                    + 0.35 * ngram_score
                    + 0.15 * error_match_score
                ) * 100

                flagged = overall > 65

                analysis = {
                    'student_id_1': s1_id,
                    'student_id_2': s2_id,
                    'similarity_score': overall,
                    'timing_score': timing_score,
                    'structural_score': structural_score,
                    'ngram_score': ngram_score,
                    'error_match_score': error_match_score,
                    'flagged': flagged,
                    'details': {
                        'timing_delta_minutes': self._get_timing_delta(s1_time, s2_time),
                        'shared_ngrams_sample': self._get_shared_ngrams(s1_text, s2_text, n=4, limit=5),
                        'structural_features': {
                            'para_count_diff': abs(
                                len(s1_text.split('\n\n')) - len(s2_text.split('\n\n'))
                            ),
                            'word_count_diff': abs(len(s1_text.split()) - len(s2_text.split())),
                        },
                    },
                }

                results.append(analysis)

                # Save to database
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    try:
                        cur = conn.cursor()
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        cur.execute(
                            "INSERT INTO collusion_reports "
                            "(assignment_id, student_id_1, student_id_2, similarity_score, "
                            "analysis_json, flagged, reviewed, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                            (
                                assignment_id, s1_id, s2_id, overall,
                                json.dumps(analysis['details']), 1 if flagged else 0, now,
                            ),
                        )
                        conn.commit()
                    finally:
                        conn.close()
                except Exception as e:
                    print(f"Error saving collusion report: {e}")

        results.sort(key=lambda r: r['similarity_score'], reverse=True)
        return results

    def _compute_timing_similarity(self, time1, time2):
        """Score how suspiciously close two submission times are (0-1)"""
        delta = self._get_timing_delta(time1, time2)
        if delta is None:
            return 0.0
        # Within 5 minutes = very suspicious (score ~1.0)
        # Within 60 minutes = somewhat suspicious
        # Beyond 120 minutes = not suspicious
        if delta <= 5:
            return 1.0
        elif delta <= 120:
            return max(0.0, 1.0 - (delta - 5) / 115.0)
        return 0.0

    def _get_timing_delta(self, time1, time2):
        """Get absolute time difference in minutes between two timestamps"""
        try:
            fmt = '%Y-%m-%d %H:%M:%S'
            t1 = datetime.strptime(str(time1), fmt)
            t2 = datetime.strptime(str(time2), fmt)
            return abs((t1 - t2).total_seconds()) / 60.0
        except (ValueError, TypeError):
            return None

    def _compute_structural_similarity(self, text1, text2):
        """Compare structural features of two texts (0-1)"""
        def features(text):
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
            words = text.split()
            para_lengths = [len(p.split()) for p in paragraphs]
            sent_lengths = [len(s.split()) for s in sentences]
            return {
                'para_count': len(paragraphs),
                'sent_count': len(sentences),
                'word_count': len(words),
                'avg_para_len': sum(para_lengths) / max(len(para_lengths), 1),
                'avg_sent_len': sum(sent_lengths) / max(len(sent_lengths), 1),
                'para_lengths': para_lengths,
            }

        f1 = features(text1)
        f2 = features(text2)

        scores = []

        # Paragraph count similarity
        max_para = max(f1['para_count'], f2['para_count'], 1)
        scores.append(1.0 - abs(f1['para_count'] - f2['para_count']) / max_para)

        # Sentence count similarity
        max_sent = max(f1['sent_count'], f2['sent_count'], 1)
        scores.append(1.0 - abs(f1['sent_count'] - f2['sent_count']) / max_sent)

        # Word count similarity
        max_words = max(f1['word_count'], f2['word_count'], 1)
        scores.append(1.0 - abs(f1['word_count'] - f2['word_count']) / max_words)

        # Average sentence length similarity
        max_asl = max(f1['avg_sent_len'], f2['avg_sent_len'], 1)
        scores.append(1.0 - abs(f1['avg_sent_len'] - f2['avg_sent_len']) / max_asl)

        # Paragraph length pattern similarity (ordered comparison)
        pl1 = f1['para_lengths']
        pl2 = f2['para_lengths']
        min_len = min(len(pl1), len(pl2))
        if min_len > 0:
            max_len = max(len(pl1), len(pl2))
            length_match = sum(
                1.0 - abs(pl1[k] - pl2[k]) / max(pl1[k], pl2[k], 1)
                for k in range(min_len)
            ) / max_len
            scores.append(length_match)

        return sum(scores) / max(len(scores), 1)

    def _compute_ngram_similarity(self, text1, text2, n=4):
        """Compute n-gram overlap (Jaccard similarity) between texts (0-1)"""
        def get_ngrams(text, n):
            words = re.findall(r'\b\w+\b', text.lower())
            if len(words) < n:
                return set()
            return set(tuple(words[i:i + n]) for i in range(len(words) - n + 1))

        ng1 = get_ngrams(text1, n)
        ng2 = get_ngrams(text2, n)

        if not ng1 or not ng2:
            return 0.0

        intersection = len(ng1 & ng2)
        union = len(ng1 | ng2)
        return intersection / max(union, 1)

    def _get_shared_ngrams(self, text1, text2, n=4, limit=5):
        """Get a sample of shared n-grams for display"""
        def get_ngrams(text, n):
            words = re.findall(r'\b\w+\b', text.lower())
            return set(tuple(words[i:i + n]) for i in range(len(words) - n + 1))

        ng1 = get_ngrams(text1, n)
        ng2 = get_ngrams(text2, n)
        shared = ng1 & ng2
        return [' '.join(ng) for ng in list(shared)[:limit]]

    def _compute_error_similarity(self, text1, text2):
        """Detect shared unusual errors or quirks (0-1)"""
        # Detect common misspellings / unusual patterns shared between texts
        def find_quirks(text):
            quirks = set()
            # Double spaces
            if '  ' in text:
                quirks.add('double_space')
            # Common misspelling patterns
            misspell_patterns = [
                r'\bteh\b', r'\brecieve\b', r'\boccured\b', r'\bseperate\b',
                r'\bdefinate\b', r'\baccomodate\b', r'\boccasion\b',
                r'\bneccessary\b', r'\bwierd\b', r'\bforiegn\b',
            ]
            for pat in misspell_patterns:
                if re.search(pat, text, re.IGNORECASE):
                    quirks.add(f'misspell:{pat}')
            # Unusual punctuation
            if re.search(r'\s,', text):
                quirks.add('space_before_comma')
            if re.search(r'\.\.\.\.\.*', text):
                quirks.add('excessive_ellipsis')
            if re.search(r'[!?]{2,}', text):
                quirks.add('repeated_punctuation')
            # Tab usage
            if '\t' in text:
                quirks.add('tab_chars')
            # Smart quotes or unusual Unicode
            if re.search(r'[\u2018\u2019\u201c\u201d]', text):
                quirks.add('smart_quotes')
            # Identical uncommon words
            uncommon_long = set(
                w.lower() for w in re.findall(r'\b[a-zA-Z]{10,}\b', text)
            )
            for w in uncommon_long:
                quirks.add(f'long_word:{w}')
            return quirks

        q1 = find_quirks(text1)
        q2 = find_quirks(text2)

        if not q1 or not q2:
            return 0.0

        shared = q1 & q2
        union = q1 | q2
        return len(shared) / max(len(union), 1)

    def _on_collusion_select(self, event):
        """Handle selection in collusion results treeview"""
        selection = self._cd_tree.selection()
        if not selection:
            return
        values = self._cd_tree.item(selection[0], 'values')
        if not values:
            return

        detail_text = (
            f"Pair: {values[0]}\n"
            f"Overall Similarity: {values[1]}\n"
            f"Timing Score: {values[2]} (1.0 = submitted within 5 min)\n"
            f"Structural Score: {values[3]} (1.0 = identical structure)\n"
            f"Error Match Score: {values[4]} (shared unusual patterns)\n"
            f"Flagged: {values[5]}\n\n"
            f"Recommendation: {'Manual review recommended.' if values[5] == 'YES' else 'No immediate concern.'}"
        )

        self._cd_detail.configure(state='normal')
        self._cd_detail.delete('1.0', 'end')
        self._cd_detail.insert('1.0', detail_text)
        self._cd_detail.configure(state='disabled')

    def _load_previous_collusion_reports(self):
        """Load previous collusion reports into the treeview"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT student_id_1, student_id_2, similarity_score, "
                    "analysis_json, flagged FROM collusion_reports "
                    "ORDER BY created_at DESC LIMIT 50"
                )
                rows = cursor.fetchall()
            finally:
                conn.close()

            for row in rows:
                sid1, sid2, score, analysis_json, flagged = row
                try:
                    analysis = json.loads(analysis_json) if analysis_json else {}
                except (json.JSONDecodeError, TypeError):
                    analysis = {}
                flagged_text = "YES" if flagged else "No"
                self._cd_tree.insert('', 'end', values=(
                    f"{sid1} vs {sid2}",
                    f"{score:.1f}%",
                    "N/A",
                    "N/A",
                    "N/A",
                    flagged_text,
                ), tags=('flagged',) if flagged else ())
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Late-Pass Advisor
    # -------------------------------------------------------------------------

    def show_late_pass_advisor(self):
        """Smart late-pass suggestion dashboard"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to access the late-pass advisor.")
            return

        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Smart Late-Pass Advisor", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        ttk.Label(
            parent,
            text="Analyse student submission patterns and get data-driven recommendations "
                 "for granting or denying late passes.",
            wraplength=700,
        ).pack(anchor='w', pady=(0, 10))

        # Student selector
        sel_frame = ttk.Frame(parent)
        sel_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(sel_frame, text="Student ID:").pack(side='left')
        self._lp_student_var = tk.StringVar()
        ttk.Entry(sel_frame, textvariable=self._lp_student_var, width=20).pack(side='left', padx=(5, 15))

        ttk.Label(sel_frame, text="Assignment (optional):").pack(side='left')
        self._lp_assignment_var = tk.StringVar()
        lp_combo = ttk.Combobox(
            sel_frame, textvariable=self._lp_assignment_var, width=40, state='readonly'
        )
        lp_combo.pack(side='left', padx=(5, 15))
        self._load_assignments_into_combo(lp_combo)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(
            btn_frame, text="Analyse Student", command=self._on_analyse_late_pass
        ).pack(side='left')
        ttk.Button(
            btn_frame, text="Back to Dashboard", command=self.show_ai_dashboard
        ).pack(side='right')

        # Results
        results_frame = ttk.LabelFrame(parent, text="Recommendation", padding=10)
        results_frame.pack(fill='both', expand=True, pady=(5, 5))
        self._lp_output = scrolledtext.ScrolledText(
            results_frame, height=10, wrap='word', state='disabled'
        )
        self._lp_output.pack(fill='both', expand=True)

        # History table
        history_frame = ttk.LabelFrame(parent, text="Previous Recommendations", padding=10)
        history_frame.pack(fill='both', expand=True, pady=(5, 0))

        cols = ('student', 'assignment', 'recommendation', 'confidence', 'date')
        self._lp_tree = ttk.Treeview(history_frame, columns=cols, show='headings', height=6)
        self._lp_tree.heading('student', text='Student')
        self._lp_tree.heading('assignment', text='Assignment')
        self._lp_tree.heading('recommendation', text='Recommendation')
        self._lp_tree.heading('confidence', text='Confidence')
        self._lp_tree.heading('date', text='Date')

        self._lp_tree.column('student', width=100)
        self._lp_tree.column('assignment', width=100)
        self._lp_tree.column('recommendation', width=100, anchor='center')
        self._lp_tree.column('confidence', width=80, anchor='center')
        self._lp_tree.column('date', width=140)

        lp_scrollbar = ttk.Scrollbar(history_frame, orient='vertical', command=self._lp_tree.yview)
        self._lp_tree.configure(yscrollcommand=lp_scrollbar.set)
        self._lp_tree.pack(side='left', fill='both', expand=True)
        lp_scrollbar.pack(side='right', fill='y')

        self._load_previous_late_pass_recommendations()

    def _on_analyse_late_pass(self):
        """Handle late-pass analysis request"""
        student_id = self._lp_student_var.get().strip()
        if not student_id:
            messagebox.showwarning("No Student", "Please enter a student ID.")
            return

        assignment_id = self._parse_assignment_id(self._lp_assignment_var.get())
        result = self.analyze_student_history(student_id)

        # Save recommendation
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "INSERT INTO late_pass_recommendations "
                    "(student_id, assignment_id, recommendation, confidence_score, reasoning_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        student_id, assignment_id, result['recommendation'],
                        result['confidence'], json.dumps(result['reasoning']), now,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error saving late-pass recommendation: {e}")

        # Display
        self._lp_output.configure(state='normal')
        self._lp_output.delete('1.0', 'end')
        self._lp_output.insert('end', self._format_late_pass_result(result, student_id))
        self._lp_output.configure(state='disabled')

        # Refresh history
        self._load_previous_late_pass_recommendations()

    def analyze_student_history(self, student_id):
        """Analyse submission patterns and recommend late pass decisions.

        Considers:
        - Historical on-time submission rate
        - Previous late pass usage
        - Average submission timing relative to deadlines
        - Recent submission trend (improving or declining)
        - Overall grade performance

        Returns dict with recommendation, confidence, and reasoning.
        """
        reasoning = {}
        scores = []  # (factor_name, score, weight) — higher score = more deserving of grant

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Get submission history
                cursor.execute(
                    "SELECT s.submission_date, a.due_date, s.grade "
                    "FROM assignment_submissions s "
                    "JOIN assignments a ON s.assignment_id = a.id "
                    "WHERE s.student_id = ? "
                    "ORDER BY s.submission_date",
                    (student_id,),
                )
                submissions = cursor.fetchall()

                # Get previous late pass recommendations
                cursor.execute(
                    "SELECT recommendation, created_at FROM late_pass_recommendations "
                    "WHERE student_id = ? ORDER BY created_at DESC",
                    (student_id,),
                )
                prev_recommendations = cursor.fetchall()

                # Get extension requests if table exists
                extension_count = 0
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM extension_requests WHERE student_id = ?",
                        (student_id,),
                    )
                    extension_count = cursor.fetchone()[0]
                except Exception:
                    pass

            finally:
                conn.close()
        except Exception as e:
            print(f"Error loading student history: {e}")
            return {
                'recommendation': 'grant',
                'confidence': 0.3,
                'reasoning': {'error': f'Insufficient data: {e}'},
            }

        total_submissions = len(submissions)

        if total_submissions == 0:
            reasoning['note'] = 'No submission history found for this student.'
            return {
                'recommendation': 'grant',
                'confidence': 0.4,
                'reasoning': reasoning,
            }

        # 1. On-time submission rate
        on_time = 0
        late_submissions = 0
        deltas_hours = []
        grades = []

        for submitted_at, due_date, grade in submissions:
            try:
                fmt = '%Y-%m-%d %H:%M:%S'
                sub_dt = datetime.strptime(str(submitted_at), fmt)
                due_dt = datetime.strptime(str(due_date), fmt)
                delta = (due_dt - sub_dt).total_seconds() / 3600.0
                deltas_hours.append(delta)
                if delta >= 0:
                    on_time += 1
                else:
                    late_submissions += 1
            except (ValueError, TypeError):
                pass
            if grade is not None:
                try:
                    grades.append(float(grade))
                except (ValueError, TypeError):
                    pass

        on_time_rate = on_time / max(total_submissions, 1)
        reasoning['on_time_rate'] = round(on_time_rate * 100, 1)
        reasoning['total_submissions'] = total_submissions
        reasoning['late_submissions'] = late_submissions

        # High on-time rate = more deserving
        scores.append(('on_time_history', on_time_rate, 0.30))

        # 2. Previous late-pass usage
        prev_grants = sum(1 for r, _ in prev_recommendations if r == 'grant')
        reasoning['previous_grants'] = prev_grants
        if prev_grants == 0:
            scores.append(('no_prior_grants', 1.0, 0.15))
        elif prev_grants <= 2:
            scores.append(('few_prior_grants', 0.6, 0.15))
        else:
            scores.append(('many_prior_grants', 0.2, 0.15))

        # 3. Average timing (how early/late relative to deadline)
        if deltas_hours:
            avg_delta = sum(deltas_hours) / len(deltas_hours)
            reasoning['avg_hours_before_deadline'] = round(avg_delta, 1)
            if avg_delta > 24:
                scores.append(('submits_early', 0.9, 0.15))
            elif avg_delta > 0:
                scores.append(('submits_on_time', 0.6, 0.15))
            else:
                scores.append(('submits_late', 0.2, 0.15))

        # 4. Recent trend (last 5 vs earlier)
        if len(deltas_hours) >= 5:
            recent = deltas_hours[-5:]
            earlier = deltas_hours[:-5]
            recent_avg = sum(recent) / len(recent)
            earlier_avg = sum(earlier) / max(len(earlier), 1)
            improving = recent_avg > earlier_avg
            reasoning['trend'] = 'improving' if improving else 'declining'
            scores.append(('recent_trend', 0.8 if improving else 0.3, 0.15))
        else:
            reasoning['trend'] = 'insufficient data'
            scores.append(('recent_trend', 0.5, 0.15))

        # 5. Grade performance
        if grades:
            avg_grade = sum(grades) / len(grades)
            reasoning['avg_grade'] = round(avg_grade, 1)
            if avg_grade >= 70:
                scores.append(('good_grades', 0.8, 0.10))
            elif avg_grade >= 50:
                scores.append(('average_grades', 0.5, 0.10))
            else:
                scores.append(('low_grades', 0.4, 0.10))
        else:
            scores.append(('no_grades', 0.5, 0.10))

        # 6. Extension request frequency
        reasoning['extension_requests'] = extension_count
        if extension_count <= 1:
            scores.append(('few_extensions', 0.8, 0.15))
        elif extension_count <= 3:
            scores.append(('some_extensions', 0.5, 0.15))
        else:
            scores.append(('many_extensions', 0.2, 0.15))

        # Compute weighted score
        total_weight = sum(w for _, _, w in scores)
        weighted_score = sum(s * w for _, s, w in scores) / max(total_weight, 0.01)
        reasoning['factor_scores'] = {name: round(score, 2) for name, score, _ in scores}

        # Decision
        if weighted_score >= 0.6:
            recommendation = 'grant'
        else:
            recommendation = 'deny'

        confidence = min(abs(weighted_score - 0.5) * 2 + 0.5, 1.0)

        return {
            'recommendation': recommendation,
            'confidence': round(confidence, 2),
            'reasoning': reasoning,
        }

    def _format_late_pass_result(self, result, student_id):
        """Format late-pass recommendation for display"""
        lines = [f"=== LATE-PASS RECOMMENDATION FOR {student_id} ===\n"]

        rec = result['recommendation'].upper()
        conf = result['confidence'] * 100
        lines.append(f"Recommendation: {rec}")
        lines.append(f"Confidence: {conf:.0f}%\n")

        reasoning = result.get('reasoning', {})

        if 'error' in reasoning:
            lines.append(f"Note: {reasoning['error']}")
            return '\n'.join(lines)

        if 'note' in reasoning:
            lines.append(f"Note: {reasoning['note']}")
            return '\n'.join(lines)

        lines.append("--- Student Profile ---")
        lines.append(f"  Total submissions: {reasoning.get('total_submissions', 'N/A')}")
        lines.append(f"  On-time rate: {reasoning.get('on_time_rate', 'N/A')}%")
        lines.append(f"  Late submissions: {reasoning.get('late_submissions', 'N/A')}")
        lines.append(f"  Previous late-pass grants: {reasoning.get('previous_grants', 'N/A')}")
        lines.append(f"  Extension requests: {reasoning.get('extension_requests', 'N/A')}")
        lines.append(f"  Avg hours before deadline: {reasoning.get('avg_hours_before_deadline', 'N/A')}")
        lines.append(f"  Recent trend: {reasoning.get('trend', 'N/A')}")
        lines.append(f"  Average grade: {reasoning.get('avg_grade', 'N/A')}")
        lines.append("")

        factor_scores = reasoning.get('factor_scores', {})
        if factor_scores:
            lines.append("--- Factor Scores ---")
            for factor, score in factor_scores.items():
                label = factor.replace('_', ' ').title()
                lines.append(f"  {label}: {score}")

        return '\n'.join(lines)

    def _load_previous_late_pass_recommendations(self):
        """Load previous late-pass recommendations into the history treeview"""
        try:
            for item in self._lp_tree.get_children():
                self._lp_tree.delete(item)
        except (AttributeError, tk.TclError):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT student_id, assignment_id, recommendation, confidence_score, created_at "
                    "FROM late_pass_recommendations ORDER BY created_at DESC LIMIT 30"
                )
                rows = cursor.fetchall()
            finally:
                conn.close()

            for row in rows:
                sid, aid, rec, conf, created = row
                self._lp_tree.insert('', 'end', values=(
                    sid,
                    aid if aid else 'N/A',
                    rec.upper(),
                    f"{conf * 100:.0f}%",
                    created,
                ))
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_current_student_id(self):
        """Get the current student ID from auth"""
        try:
            if hasattr(self.assignment_system, '_get_student_id'):
                return self.assignment_system._get_student_id()
            if self.auth and self.auth.current_user:
                return self.auth.current_user.get('id') or self.auth.current_user.get('student_id')
        except Exception:
            pass
        return 'unknown'

    def _load_assignments_into_combo(self, combo):
        """Load assignments into a combobox"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, title, module_code FROM assignments "
                    "WHERE is_active = 1 ORDER BY due_date DESC LIMIT 50"
                )
                rows = cursor.fetchall()
                values = [f"{r[0]} - {r[2]} - {r[1]}" for r in rows]
                combo['values'] = values
            finally:
                conn.close()
        except Exception:
            combo['values'] = []

    def _parse_assignment_id(self, combo_value):
        """Parse assignment ID from combobox value string"""
        if not combo_value:
            return None
        try:
            return int(combo_value.split(' - ')[0])
        except (ValueError, IndexError):
            return None

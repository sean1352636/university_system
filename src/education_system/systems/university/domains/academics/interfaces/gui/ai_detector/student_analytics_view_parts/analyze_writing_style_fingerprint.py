"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import student_analytics_view_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def analyze_writing_style_fingerprint(self):
    """Create unique writing style fingerprint for each student to compare against submissions"""
    student_id = self.style_student_var.get().strip()
    if not student_id:
        messagebox.showwarning(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_writing_style_fingerprint.dialogs.warning', default="Warning"), _t('gui.academics.ai_detector.student_analytics_view_parts.analyze_writing_style_fingerprint.dialogs.please_enter_a_student_id', default="Please enter a student ID"))
        return

    try:
        self.update_status("Analyzing writing style...")
        self.enhanced_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Get student's previous submissions
        cursor.execute('''
            SELECT text_content, ai_probability, analysis_date
            FROM ai_analysis_history
            WHERE student_id = ?
            ORDER BY analysis_date
            LIMIT 10
        ''', (student_id,))
        submissions = cursor.fetchall()

        if not submissions:
            self.enhanced_results_text.insert('1.0', f"No submission history found for student {student_id}")
            conn.close()
            return

        # Analyze writing characteristics
        fingerprint = {
            'avg_sentence_length': 0,
            'avg_word_length': 0,
            'vocabulary_richness': 0,
            'punctuation_density': 0,
            'contraction_usage': 0,
            'passive_voice_ratio': 0,
            'common_phrases': [],
            'sentence_starters': []
        }

        total_texts = 0
        all_words = []
        sentence_starters = {}

        for text_content, ai_prob, date in submissions:
            if text_content:
                total_texts += 1
                words = text_content.split()
                sentences = text_content.replace('!', '.').replace('?', '.').split('.')

                all_words.extend(words)
                fingerprint['avg_sentence_length'] += len(words) / max(len(sentences), 1)
                fingerprint['avg_word_length'] += sum(len(w) for w in words) / max(len(words), 1)

                # Count contractions
                contractions = sum(1 for w in words if "'" in w)
                fingerprint['contraction_usage'] += contractions / max(len(words), 1)

                # Track sentence starters
                for sent in sentences:
                    sent = sent.strip()
                    if sent:
                        starter = sent.split()[0] if sent.split() else ""
                        sentence_starters[starter] = sentence_starters.get(starter, 0) + 1

        if total_texts > 0:
            fingerprint['avg_sentence_length'] /= total_texts
            fingerprint['avg_word_length'] /= total_texts
            fingerprint['contraction_usage'] /= total_texts
            fingerprint['vocabulary_richness'] = len(set(all_words)) / max(len(all_words), 1)
            fingerprint['sentence_starters'] = sorted(sentence_starters.items(), key=lambda x: -x[1])[:5]

        # Store fingerprint
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_writing_fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE,
                fingerprint_data TEXT,
                submissions_analyzed INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT OR REPLACE INTO ai_writing_fingerprints
            (student_id, fingerprint_data, submissions_analyzed, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (student_id, json.dumps(fingerprint), total_texts))

        conn.commit()
        conn.close()

        # Display results
        result = f"Writing Style Fingerprint for Student {student_id}\n"
        result += "=" * 50 + "\n\n"
        result += f"Submissions Analyzed: {total_texts}\n\n"
        result += f"Average Sentence Length: {fingerprint['avg_sentence_length']:.1f} words\n"
        result += f"Average Word Length: {fingerprint['avg_word_length']:.1f} characters\n"
        result += f"Vocabulary Richness: {fingerprint['vocabulary_richness']:.2%}\n"
        result += f"Contraction Usage: {fingerprint['contraction_usage']:.2%}\n\n"
        result += "Common Sentence Starters:\n"
        for starter, count in fingerprint['sentence_starters']:
            result += f"  '{starter}' - {count} times\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Writing fingerprint created")
        messagebox.showinfo(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_writing_style_fingerprint.dialogs.success', default="Success"), f"Writing fingerprint created for student {student_id}")
    except Exception as e:
        messagebox.showerror(_t('gui.academics.ai_detector.student_analytics_view_parts.analyze_writing_style_fingerprint.dialogs.error', default="Error"), f"Failed to create fingerprint: {str(e)}")

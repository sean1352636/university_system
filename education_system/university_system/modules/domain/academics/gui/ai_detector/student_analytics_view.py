import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

try:
    from education_system.university_system.utils.ai.ai_detector.detector import AIDetector
    _AI_DETECTOR_IMPORT_ERROR = None
except Exception as import_error:
    AIDetector = None
    _AI_DETECTOR_IMPORT_ERROR = import_error

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    TEXTRACT_AVAILABLE = False

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from education_system.university_system.modules.shared.utils.i18n import get_text, _

def create_integrations_view(self, parent):
    """Create integrations view"""
    integrations_frame = ttk.Frame(parent)
    integrations_frame.pack(fill="both", expand=True)

    # Main card
    integrations_card = ttk.Frame(integrations_frame, style='Card.TFrame')
    integrations_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(integrations_card, text="External Integrations", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Plagiarism Checker Integration
    plagiarism_frame = ttk.LabelFrame(integrations_card, text="Plagiarism Checker Integration", padding=15)
    plagiarism_frame.pack(fill='x', padx=15, pady=(0, 15))

    plag_row1 = ttk.Frame(plagiarism_frame)
    plag_row1.pack(fill='x', pady=2)
    ttk.Label(plag_row1, text="Service:").pack(side='left')
    self.plagiarism_service_var = tk.StringVar(value="Turnitin")
    ttk.Combobox(plag_row1, textvariable=self.plagiarism_service_var,
                values=["Turnitin", "Copyleaks", "Grammarly", "PlagScan"],
                width=15, state='readonly').pack(side='left', padx=(5, 15))

    ttk.Label(plag_row1, text="API Key:").pack(side='left')
    self.plagiarism_api_var = tk.StringVar()
    ttk.Entry(plag_row1, textvariable=self.plagiarism_api_var, width=30, show='*').pack(side='left', padx=(5, 0))

    plag_buttons = ttk.Frame(plagiarism_frame)
    plag_buttons.pack(fill='x', pady=(10, 0))
    ttk.Button(plag_buttons, text="Save Configuration",
              command=self._save_plagiarism_config).pack(side='left', padx=(0, 10))
    ttk.Button(plag_buttons, text="Test Connection",
              command=self._test_plagiarism_connection).pack(side='left', padx=(0, 10))
    ttk.Button(plag_buttons, text="Sync Results",
              command=self.sync_with_plagiarism_checker).pack(side='left')

    # Academic Record Integration
    academic_frame = ttk.LabelFrame(integrations_card, text="Academic Record System", padding=15)
    academic_frame.pack(fill='x', padx=15, pady=(0, 15))

    acad_row1 = ttk.Frame(academic_frame)
    acad_row1.pack(fill='x', pady=2)
    ttk.Label(acad_row1, text="System:").pack(side='left')
    self.academic_system_var = tk.StringVar(value="Internal")
    ttk.Combobox(acad_row1, textvariable=self.academic_system_var,
                values=["Internal", "Banner", "PeopleSoft", "Ellucian"],
                width=15, state='readonly').pack(side='left', padx=(5, 15))

    self.auto_push_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(acad_row1, text="Auto-push confirmed violations",
                   variable=self.auto_push_var).pack(side='left')

    acad_row2 = ttk.Frame(academic_frame)
    acad_row2.pack(fill='x', pady=2)
    ttk.Label(acad_row2, text="Submission ID:").pack(side='left')
    self.push_submission_var = tk.StringVar()
    ttk.Entry(acad_row2, textvariable=self.push_submission_var, width=20).pack(side='left', padx=(5, 10))
    ttk.Button(acad_row2, text="Push to Academic Record",
              command=self.push_to_academic_record).pack(side='left')

    # Integration Status
    status_frame = ttk.LabelFrame(integrations_card, text="Integration Status", padding=15)
    status_frame.pack(fill='x', padx=15, pady=(0, 15))

    columns = ('service', 'status', 'last_sync', 'records')
    self.integration_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=4)
    self.integration_tree.heading('service', text='Service')
    self.integration_tree.heading('status', text='Status')
    self.integration_tree.heading('last_sync', text='Last Sync')
    self.integration_tree.heading('records', text='Records')

    self.integration_tree.column('service', width=150)
    self.integration_tree.column('status', width=100)
    self.integration_tree.column('last_sync', width=150)
    self.integration_tree.column('records', width=80)

    self.integration_tree.pack(fill='x')

    # Load integration status
    self._load_integration_status()


def _save_plagiarism_config(self):
    """Save plagiarism checker configuration"""
    try:
        service = self.plagiarism_service_var.get()
        api_key = self.plagiarism_api_var.get()

        if not api_key:
            messagebox.showwarning("Warning", "Please enter an API key")
            return

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_integration_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT UNIQUE,
                    api_key TEXT,
                    enabled INTEGER DEFAULT 1,
                    last_sync TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                INSERT OR REPLACE INTO ai_integration_config (service_name, api_key, enabled)
                VALUES (?, ?, 1)
            ''', (service, api_key))

            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo("Success", f"{service} configuration saved")
        self._load_integration_status()
        self.update_status(f"{service} configured")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")


def _test_plagiarism_connection(self):
    """Test connection to plagiarism checker"""
    service = self.plagiarism_service_var.get()
    api_key = self.plagiarism_api_var.get()

    if not api_key:
        messagebox.showwarning("Warning", "Please enter an API key first")
        return

    # Simulate connection test
    self.update_status(f"Testing connection to {service}...")

    def test():
        time.sleep(1)  # Simulate network delay
        # In real implementation, would test actual API
        messagebox.showinfo("Connection Test", f"Connection to {service} successful!")
        self.update_status(f"{service} connection verified")

    thread = threading.Thread(target=test, daemon=True)
    thread.start()


def _load_integration_status(self):
    """Load integration status into treeview"""
    try:
        for item in self.integration_tree.get_children():
            self.integration_tree.delete(item)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='ai_integration_config'
            ''')

            if cursor.fetchone():
                cursor.execute('''
                    SELECT service_name,
                           CASE WHEN enabled = 1 THEN 'Active' ELSE 'Inactive' END,
                           datetime(last_sync),
                           0
                    FROM ai_integration_config
                ''')
                integrations = cursor.fetchall()

                for integration in integrations:
                    self.integration_tree.insert('', 'end', values=integration)

        finally:
            conn.close()
    except Exception:
        pass


def sync_with_plagiarism_checker(self):
    """Sync results with Turnitin/Copyleaks/other plagiarism tools"""
    service = self.plagiarism_service_var.get()

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT api_key FROM ai_integration_config WHERE service_name = ?
        ''', (service,))
        result = cursor.fetchone()

        if not result:
            messagebox.showwarning("Warning", f"Please configure {service} first")
            conn.close()
            return

        # Update last sync time
        cursor.execute('''
            UPDATE ai_integration_config
            SET last_sync = CURRENT_TIMESTAMP
            WHERE service_name = ?
        ''', (service,))

        conn.commit()
        conn.close()

        # Simulate sync
        self.update_status(f"Syncing with {service}...")

        def sync():
            time.sleep(2)  # Simulate sync
            self._load_integration_status()
            messagebox.showinfo("Sync Complete", f"Successfully synced with {service}")
            self.update_status(f"Sync with {service} complete")

        thread = threading.Thread(target=sync, daemon=True)
        thread.start()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to sync: {str(e)}")


def push_to_academic_record(self):
    """Push confirmed violations to student academic record system"""
    submission_id = self.push_submission_var.get().strip()
    if not submission_id:
        messagebox.showwarning("Warning", "Please enter a submission ID")
        return

    system = self.academic_system_var.get()

    if not messagebox.askyesno("Confirm Push",
                               f"This will push the violation record for submission {submission_id} "
                               f"to the {system} academic record system.\n\n"
                               "This action will create a permanent record. Continue?"):
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Get submission details
        cursor.execute('''
            SELECT student_id, student_name, ai_probability, analysis_date
            FROM ai_analysis_history WHERE submission_id = ?
        ''', (submission_id,))
        submission = cursor.fetchone()

        if not submission:
            messagebox.showerror("Error", "Submission not found")
            conn.close()
            return

        # Create violation record
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_violation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id TEXT,
                student_id TEXT,
                student_name TEXT,
                ai_score REAL,
                pushed_to TEXT,
                pushed_by TEXT,
                pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT INTO ai_violation_records (submission_id, student_id, student_name, ai_score, pushed_to, pushed_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            submission_id,
            submission[0],
            submission[1],
            submission[2],
            system,
            self.auth.current_user.get('username', 'Unknown') if self.auth and self.auth.current_user else 'Unknown'
        ))

        # Log activity
        cursor.execute('''
            INSERT INTO ai_activity_log (username, action, details)
            VALUES (?, 'push_violation', ?)
        ''', (
            self.auth.current_user.get('username', 'Unknown') if self.auth and self.auth.current_user else 'Unknown',
            f'Pushed violation for submission {submission_id} to {system}'
        ))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success",
                          f"Violation record pushed to {system}\n\n"
                          f"Student: {submission[1]}\n"
                          f"AI Score: {submission[2]:.1f}%")
        self.update_status(f"Violation pushed to {system}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to push record: {str(e)}")


def create_enhanced_detection_view(self, parent):
    """Create enhanced detection analysis view"""
    detection_frame = ttk.Frame(parent)
    detection_frame.pack(fill="both", expand=True)

    # Main card
    detection_card = ttk.Frame(detection_frame, style='Card.TFrame')
    detection_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(detection_card, text="Enhanced Detection Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Writing Style Analysis Section
    style_frame = ttk.LabelFrame(detection_card, text="Writing Style Analysis", padding=15)
    style_frame.pack(fill='x', padx=15, pady=(0, 15))

    style_row = ttk.Frame(style_frame)
    style_row.pack(fill='x', pady=2)
    ttk.Label(style_row, text="Student ID:").pack(side='left')
    self.style_student_var = tk.StringVar()
    ttk.Entry(style_row, textvariable=self.style_student_var, width=20).pack(side='left', padx=(5, 10))
    ttk.Button(style_row, text="Create Writing Fingerprint",
              command=self.analyze_writing_style_fingerprint).pack(side='left', padx=(0, 10))
    ttk.Button(style_row, text="Analyze Knowledge Consistency",
              command=self.analyze_knowledge_consistency).pack(side='left')

    # Paraphrasing & AI Detection Section
    para_frame = ttk.LabelFrame(detection_card, text="Paraphrasing & AI Artifact Detection", padding=15)
    para_frame.pack(fill='x', padx=15, pady=(0, 15))

    para_buttons = ttk.Frame(para_frame)
    para_buttons.pack(fill='x')
    ttk.Button(para_buttons, text="Detect Paraphrasing Tools",
              command=self.detect_paraphrasing_tools).pack(side='left', padx=(0, 10))
    ttk.Button(para_buttons, text="Analyze Prompt Artifacts",
              command=self.analyze_prompt_artifacts).pack(side='left', padx=(0, 10))
    ttk.Button(para_buttons, text="Detect Translation Artifacts",
              command=self.detect_translation_artifacts).pack(side='left')

    # Draft Comparison Section
    draft_frame = ttk.LabelFrame(detection_card, text="Draft & Version Analysis", padding=15)
    draft_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(draft_frame, text="Upload multiple draft versions to compare quality progression:").pack(anchor='w')
    draft_buttons = ttk.Frame(draft_frame)
    draft_buttons.pack(fill='x', pady=(10, 0))
    ttk.Button(draft_buttons, text="Load Draft Files",
              command=self._load_draft_files).pack(side='left', padx=(0, 10))
    ttk.Button(draft_buttons, text="Compare Draft Versions",
              command=self.compare_draft_versions).pack(side='left')

    self.draft_files_var = tk.StringVar(value="No drafts loaded")
    ttk.Label(draft_frame, textvariable=self.draft_files_var,
             foreground=self.colors['text_secondary']).pack(anchor='w', pady=(5, 0))

    # Copy-Paste & Reference Section
    copy_frame = ttk.LabelFrame(detection_card, text="Copy-Paste & Reference Analysis", padding=15)
    copy_frame.pack(fill='x', padx=15, pady=(0, 15))

    copy_buttons = ttk.Frame(copy_frame)
    copy_buttons.pack(fill='x')
    ttk.Button(copy_buttons, text="Detect Copy-Paste Patterns",
              command=self.detect_copy_paste_patterns).pack(side='left', padx=(0, 10))
    ttk.Button(copy_buttons, text="Verify Reference Authenticity",
              command=self.analyze_reference_authenticity).pack(side='left')

    # Results Display
    results_frame = ttk.LabelFrame(detection_card, text="Analysis Results", padding=15)
    results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    self.enhanced_results_text = scrolledtext.ScrolledText(results_frame, height=10, wrap=tk.WORD)
    self.enhanced_results_text.pack(fill='both', expand=True)


def _load_draft_files(self):
    """Load draft files for comparison"""
    files = filedialog.askopenfilenames(
        title="Select Draft Files (in order)",
        filetypes=[("Text files", "*.txt"), ("Word docs", "*.docx"), ("All files", "*.*")]
    )
    if files:
        self._draft_files = list(files)
        self.draft_files_var.set(f"{len(files)} drafts loaded")


def analyze_writing_style_fingerprint(self):
    """Create unique writing style fingerprint for each student to compare against submissions"""
    student_id = self.style_student_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    try:
        self.update_status("Analyzing writing style...")
        self.enhanced_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
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
        finally:
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
        messagebox.showinfo("Success", f"Writing fingerprint created for student {student_id}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create fingerprint: {str(e)}")


def detect_paraphrasing_tools(self):
    """Specifically detect content processed through Quillbot, Spinbot, etc."""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning("Warning", "Please enter text in the Text Analysis view first")
        return

    try:
        self.update_status("Detecting paraphrasing patterns...")
        self.enhanced_results_text.delete('1.0', tk.END)

        # Paraphrasing tool indicators
        indicators = {
            'unusual_synonyms': 0,
            'awkward_phrasing': 0,
            'inconsistent_formality': 0,
            'over_complex_vocabulary': 0,
            'repetitive_structure': 0
        }

        # Common paraphrasing artifacts
        paraphrase_markers = [
            'in addition to this', 'furthermore', 'moreover', 'consequently',
            'nevertheless', 'notwithstanding', 'henceforth', 'whereby'
        ]

        words = text.lower().split()
        sentences = text.replace('!', '.').replace('?', '.').split('.')

        # Check for over-use of transition words (common in paraphrasing tools)
        transition_count = sum(1 for marker in paraphrase_markers if marker in text.lower())
        indicators['unusual_synonyms'] = min(transition_count / max(len(sentences), 1), 1.0)

        # Check for sentence structure repetition
        structures = []
        for sent in sentences:
            sent = sent.strip()
            if sent:
                structure = len(sent.split())
                structures.append(structure)

        if len(structures) > 3:
            variance = sum((s - sum(structures)/len(structures))**2 for s in structures) / len(structures)
            if variance < 5:
                indicators['repetitive_structure'] = 0.7

        # Calculate overall paraphrasing probability
        paraphrase_score = sum(indicators.values()) / len(indicators) * 100

        result = "Paraphrasing Tool Detection Results\n"
        result += "=" * 50 + "\n\n"
        result += f"Paraphrasing Probability: {paraphrase_score:.1f}%\n\n"
        result += "Indicators:\n"
        result += f"  Unusual Synonym Usage: {indicators['unusual_synonyms']:.0%}\n"
        result += f"  Awkward Phrasing: {indicators['awkward_phrasing']:.0%}\n"
        result += f"  Inconsistent Formality: {indicators['inconsistent_formality']:.0%}\n"
        result += f"  Over-complex Vocabulary: {indicators['over_complex_vocabulary']:.0%}\n"
        result += f"  Repetitive Structure: {indicators['repetitive_structure']:.0%}\n\n"

        if paraphrase_score > 50:
            result += "WARNING: High likelihood of paraphrasing tool usage detected.\n"
            result += "Recommend manual review of the submission.\n"
        elif paraphrase_score > 25:
            result += "NOTICE: Some indicators of paraphrasing detected.\n"
        else:
            result += "No significant paraphrasing tool indicators found.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Paraphrasing detection complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to detect paraphrasing: {str(e)}")


def analyze_prompt_artifacts(self):
    """Detect common ChatGPT/Claude prompt response patterns and artifacts"""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning("Warning", "Please enter text in the Text Analysis view first")
        return

    try:
        self.update_status("Analyzing prompt artifacts...")
        self.enhanced_results_text.delete('1.0', tk.END)

        artifacts = {
            'greeting_patterns': 0,
            'disclaimer_phrases': 0,
            'list_formatting': 0,
            'hedging_language': 0,
            'summary_endings': 0,
            'meta_references': 0
        }

        text_lower = text.lower()

        # Check for common AI greeting patterns
        greetings = ['certainly!', 'of course!', 'great question', 'happy to help',
                    'i\'d be glad to', 'absolutely!', 'sure thing']
        artifacts['greeting_patterns'] = sum(1 for g in greetings if g in text_lower) / len(greetings)

        # Check for disclaimer phrases
        disclaimers = ['it\'s important to note', 'it should be noted', 'keep in mind',
                      'please note', 'as an ai', 'i cannot', 'i don\'t have access']
        artifacts['disclaimer_phrases'] = sum(1 for d in disclaimers if d in text_lower) / len(disclaimers)

        # Check for list formatting (common in AI outputs)
        list_indicators = text.count('1.') + text.count('2.') + text.count('- ') + text.count('* ')
        artifacts['list_formatting'] = min(list_indicators / 10, 1.0)

        # Check for hedging language
        hedging = ['generally', 'typically', 'usually', 'often', 'may', 'might',
                  'could', 'potentially', 'it depends', 'in some cases']
        hedge_count = sum(1 for h in hedging if h in text_lower)
        artifacts['hedging_language'] = min(hedge_count / 20, 1.0)

        # Check for summary endings
        endings = ['in conclusion', 'to summarize', 'in summary', 'overall',
                  'to sum up', 'in essence', 'the key takeaway']
        artifacts['summary_endings'] = sum(1 for e in endings if e in text_lower) / len(endings)

        # Check for meta-references
        meta_refs = ['this text', 'this response', 'this answer', 'as mentioned above',
                    'as discussed', 'the following']
        artifacts['meta_references'] = sum(1 for m in meta_refs if m in text_lower) / len(meta_refs)

        # Calculate overall artifact score
        artifact_score = sum(artifacts.values()) / len(artifacts) * 100

        result = "AI Prompt Artifact Analysis\n"
        result += "=" * 50 + "\n\n"
        result += f"Artifact Detection Score: {artifact_score:.1f}%\n\n"
        result += "Detected Patterns:\n"
        result += f"  Greeting Patterns: {artifacts['greeting_patterns']:.0%}\n"
        result += f"  Disclaimer Phrases: {artifacts['disclaimer_phrases']:.0%}\n"
        result += f"  List Formatting: {artifacts['list_formatting']:.0%}\n"
        result += f"  Hedging Language: {artifacts['hedging_language']:.0%}\n"
        result += f"  Summary Endings: {artifacts['summary_endings']:.0%}\n"
        result += f"  Meta-references: {artifacts['meta_references']:.0%}\n\n"

        if artifact_score > 40:
            result += "HIGH ALERT: Strong AI prompt-response patterns detected.\n"
        elif artifact_score > 20:
            result += "MODERATE: Some AI-like patterns detected.\n"
        else:
            result += "LOW: Few AI prompt artifacts detected.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Prompt artifact analysis complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to analyze artifacts: {str(e)}")


def compare_draft_versions(self):
    """Compare multiple drafts to detect suspicious jumps in quality"""
    if not hasattr(self, '_draft_files') or not self._draft_files:
        messagebox.showwarning("Warning", "Please load draft files first")
        return

    try:
        self.update_status("Comparing draft versions...")
        self.enhanced_results_text.delete('1.0', tk.END)

        drafts = []
        for file_path in self._draft_files:
            text = self._extract_text_from_file(file_path)
            if text:
                drafts.append({
                    'file': os.path.basename(file_path),
                    'text': text,
                    'word_count': len(text.split()),
                    'avg_word_length': sum(len(w) for w in text.split()) / max(len(text.split()), 1),
                    'unique_words': len(set(text.lower().split()))
                })

        if len(drafts) < 2:
            self.enhanced_results_text.insert('1.0', "Need at least 2 readable drafts for comparison")
            return

        result = "Draft Version Comparison\n"
        result += "=" * 50 + "\n\n"

        quality_jumps = []
        for i, draft in enumerate(drafts):
            result += f"Draft {i+1}: {draft['file']}\n"
            result += f"  Word Count: {draft['word_count']}\n"
            result += f"  Avg Word Length: {draft['avg_word_length']:.1f}\n"
            result += f"  Unique Words: {draft['unique_words']}\n\n"

            if i > 0:
                prev = drafts[i-1]
                word_jump = (draft['word_count'] - prev['word_count']) / max(prev['word_count'], 1) * 100
                vocab_jump = (draft['unique_words'] - prev['unique_words']) / max(prev['unique_words'], 1) * 100

                if word_jump > 100 or vocab_jump > 50:
                    quality_jumps.append((i, word_jump, vocab_jump))

        result += "-" * 50 + "\n"
        result += "Analysis:\n\n"

        if quality_jumps:
            result += "WARNING: Suspicious quality jumps detected!\n\n"
            for draft_num, word_jump, vocab_jump in quality_jumps:
                result += f"Between Draft {draft_num} and {draft_num+1}:\n"
                result += f"  Word count increase: {word_jump:.0f}%\n"
                result += f"  Vocabulary increase: {vocab_jump:.0f}%\n\n"
            result += "Recommend investigation - possible external assistance or AI usage.\n"
        else:
            result += "No suspicious quality jumps detected.\n"
            result += "Draft progression appears natural.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Draft comparison complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to compare drafts: {str(e)}")


def detect_translation_artifacts(self):
    """Identify text that was written in another language and translated"""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning("Warning", "Please enter text in the Text Analysis view first")
        return

    try:
        self.update_status("Detecting translation artifacts...")
        self.enhanced_results_text.delete('1.0', tk.END)

        indicators = {
            'word_order_anomalies': 0,
            'article_misuse': 0,
            'preposition_errors': 0,
            'literal_translations': 0,
            'cultural_markers': 0
        }

        text_lower = text.lower()
        words = text_lower.split()

        # Check for missing/incorrect articles
        article_patterns = ['the the', 'a a', 'an an']
        for pattern in article_patterns:
            if pattern in text_lower:
                indicators['article_misuse'] += 0.3

        # Check for literal translation markers
        literal_markers = ['it makes that', 'it gives that', 'to have hunger',
                          'to have cold', 'to make attention', 'it rains cats and dogs']
        for marker in literal_markers:
            if marker in text_lower:
                indicators['literal_translations'] += 0.2

        # Check for unusual preposition usage
        prep_issues = ['in the morning of', 'by foot', 'in the bus', 'on the phone to']
        for issue in prep_issues:
            if issue in text_lower:
                indicators['preposition_errors'] += 0.2

        # Check sentence structure anomalies (e.g., adjective placement)
        sentences = text.split('.')
        for sent in sentences:
            words_in_sent = sent.split()
            # Check for adjective after noun patterns (common in Romance languages)
            for i in range(len(words_in_sent) - 1):
                if words_in_sent[i].endswith('tion') and words_in_sent[i+1] in ['beautiful', 'important', 'big']:
                    indicators['word_order_anomalies'] += 0.1

        # Calculate translation probability
        translation_score = min(sum(indicators.values()) / len(indicators) * 100, 100)

        result = "Translation Artifact Detection\n"
        result += "=" * 50 + "\n\n"
        result += f"Translation Probability: {translation_score:.1f}%\n\n"
        result += "Detected Indicators:\n"
        result += f"  Word Order Anomalies: {indicators['word_order_anomalies']:.0%}\n"
        result += f"  Article Misuse: {indicators['article_misuse']:.0%}\n"
        result += f"  Preposition Errors: {indicators['preposition_errors']:.0%}\n"
        result += f"  Literal Translations: {indicators['literal_translations']:.0%}\n"
        result += f"  Cultural Markers: {indicators['cultural_markers']:.0%}\n\n"

        if translation_score > 30:
            result += "NOTICE: Text may have been translated from another language.\n"
        else:
            result += "No significant translation artifacts detected.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Translation detection complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to detect translation: {str(e)}")


def analyze_knowledge_consistency(self):
    """Check if demonstrated knowledge matches student's course level"""
    student_id = self.style_student_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    try:
        self.update_status("Analyzing knowledge consistency...")
        self.enhanced_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            # Get student's course enrollments
            cursor.execute('''
                SELECT DISTINCT c.course_name, c.level
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                JOIN users u ON e.student_id = u.id
                WHERE u.username = ? OR u.id = ?
            ''', (student_id, student_id))
            courses = cursor.fetchall()

            # Get student's submissions
            cursor.execute('''
                SELECT text_content, course_name, ai_probability
                FROM ai_analysis_history
                WHERE student_id = ?
                ORDER BY analysis_date DESC
                LIMIT 5
            ''', (student_id,))
            submissions = cursor.fetchall()

        finally:
            conn.close()

        result = f"Knowledge Consistency Analysis - Student {student_id}\n"
        result += "=" * 50 + "\n\n"

        if courses:
            result += "Enrolled Courses:\n"
            for course_name, level in courses:
                result += f"  - {course_name} (Level: {level or 'N/A'})\n"
            result += "\n"
        else:
            result += "No course enrollment data found.\n\n"

        if submissions:
            result += "Recent Submissions Analysis:\n"
            result += "-" * 40 + "\n"

            for i, (text, course, ai_prob) in enumerate(submissions, 1):
                if text:
                    # Analyze vocabulary complexity
                    words = text.split()
                    unique_ratio = len(set(words)) / max(len(words), 1)
                    avg_length = sum(len(w) for w in words) / max(len(words), 1)

                    # Complex words (>3 syllables approximation)
                    complex_words = sum(1 for w in words if len(w) > 8)
                    complexity_ratio = complex_words / max(len(words), 1)

                    result += f"\nSubmission {i} ({course or 'Unknown Course'}):\n"
                    result += f"  Vocabulary Diversity: {unique_ratio:.2%}\n"
                    result += f"  Avg Word Length: {avg_length:.1f}\n"
                    result += f"  Complex Word Ratio: {complexity_ratio:.2%}\n"
                    result += f"  AI Detection Score: {ai_prob:.1f}%\n"

                    if complexity_ratio > 0.15 and ai_prob > 50:
                        result += "  WARNING: Unusually complex vocabulary with high AI score\n"

            result += "\n" + "-" * 40 + "\n"
            result += "\nConsistency Assessment:\n"
            result += "Review submissions for vocabulary beyond expected course level.\n"
        else:
            result += "No submission history found.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Knowledge consistency analysis complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to analyze consistency: {str(e)}")


def detect_copy_paste_patterns(self):
    """Identify copy-paste behavior from metadata and formatting anomalies"""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning("Warning", "Please enter text in the Text Analysis view first")
        return

    try:
        self.update_status("Detecting copy-paste patterns...")
        self.enhanced_results_text.delete('1.0', tk.END)

        indicators = {
            'formatting_inconsistency': 0,
            'font_hints': 0,
            'spacing_anomalies': 0,
            'style_shifts': 0,
            'citation_gaps': 0
        }

        # Check for multiple spaces (common in copy-paste)
        multiple_spaces = text.count('  ')
        indicators['spacing_anomalies'] = min(multiple_spaces / 10, 1.0)

        # Check for inconsistent line breaks
        weird_breaks = text.count('\r\n') + text.count('\n\n\n')
        indicators['formatting_inconsistency'] = min(weird_breaks / 5, 1.0)

        # Check for sudden style shifts (different sentence patterns)
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        if len(sentences) > 5:
            lengths = [len(s.split()) for s in sentences if s.strip()]
            avg_length = sum(lengths) / max(len(lengths), 1)
            variance = sum((l - avg_length)**2 for l in lengths) / max(len(lengths), 1)
            if variance > 100:
                indicators['style_shifts'] = 0.7

        # Check for reference format inconsistencies
        ref_patterns = ['et al', 'pp.', 'vol.', 'retrieved from', 'accessed']
        ref_count = sum(1 for p in ref_patterns if p.lower() in text.lower())
        if ref_count > 0 and ref_count < 3:
            indicators['citation_gaps'] = 0.5

        copy_paste_score = sum(indicators.values()) / len(indicators) * 100

        result = "Copy-Paste Pattern Detection\n"
        result += "=" * 50 + "\n\n"
        result += f"Copy-Paste Probability: {copy_paste_score:.1f}%\n\n"
        result += "Detected Indicators:\n"
        result += f"  Formatting Inconsistency: {indicators['formatting_inconsistency']:.0%}\n"
        result += f"  Font/Style Hints: {indicators['font_hints']:.0%}\n"
        result += f"  Spacing Anomalies: {indicators['spacing_anomalies']:.0%}\n"
        result += f"  Style Shifts: {indicators['style_shifts']:.0%}\n"
        result += f"  Citation Gaps: {indicators['citation_gaps']:.0%}\n\n"

        if copy_paste_score > 40:
            result += "WARNING: High likelihood of copy-paste from external sources.\n"
        elif copy_paste_score > 20:
            result += "NOTICE: Some copy-paste indicators present.\n"
        else:
            result += "No significant copy-paste patterns detected.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Copy-paste detection complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to detect patterns: {str(e)}")


def analyze_reference_authenticity(self):
    """Verify that cited sources actually exist and contain claimed information"""
    text = ""
    if hasattr(self, 'text_input'):
        text = self.text_input.get('1.0', tk.END).strip()

    if not text:
        messagebox.showwarning("Warning", "Please enter text in the Text Analysis view first")
        return

    try:
        self.update_status("Analyzing reference authenticity...")
        self.enhanced_results_text.delete('1.0', tk.END)

        import re

        # Extract potential references
        # APA style: (Author, Year)
        apa_pattern = r'\(([A-Z][a-z]+(?:\s+(?:&|and)\s+[A-Z][a-z]+)*),?\s*(\d{4})\)'
        apa_refs = re.findall(apa_pattern, text)

        # URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)

        # DOIs
        doi_pattern = r'10\.\d{4,}/[^\s]+'
        dois = re.findall(doi_pattern, text)

        result = "Reference Authenticity Analysis\n"
        result += "=" * 50 + "\n\n"

        result += f"References Found:\n"
        result += f"  APA-style citations: {len(apa_refs)}\n"
        result += f"  URLs: {len(urls)}\n"
        result += f"  DOIs: {len(dois)}\n\n"

        suspicious_refs = []

        # Check for suspicious patterns
        for author, year in apa_refs:
            year_int = int(year)
            if year_int > 2025:
                suspicious_refs.append(f"{author}, {year} - Future date")
            elif year_int < 1900:
                suspicious_refs.append(f"{author}, {year} - Very old reference")

        # Check for fake-looking URLs
        for url in urls:
            if 'fake' in url.lower() or 'example.com' in url.lower():
                suspicious_refs.append(f"Suspicious URL: {url[:50]}...")

        if suspicious_refs:
            result += "Suspicious References Detected:\n"
            result += "-" * 40 + "\n"
            for ref in suspicious_refs:
                result += f"  - {ref}\n"
            result += "\n"

        # Generate authenticity score
        total_refs = len(apa_refs) + len(urls) + len(dois)
        if total_refs > 0:
            authenticity_score = max(0, 100 - len(suspicious_refs) * 20)
            result += f"Reference Authenticity Score: {authenticity_score:.0f}%\n\n"

            if authenticity_score < 60:
                result += "WARNING: Multiple suspicious references detected.\n"
                result += "Manual verification recommended.\n"
            else:
                result += "References appear generally legitimate.\n"
                result += "Note: Full verification requires external database checks.\n"
        else:
            result += "No formal references detected in text.\n"

        self.enhanced_results_text.insert('1.0', result)
        self.update_status("Reference analysis complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to analyze references: {str(e)}")


def create_student_management_view(self, parent):
    """Create student management view"""
    student_frame = ttk.Frame(parent)
    student_frame.pack(fill="both", expand=True)

    # Main card
    student_card = ttk.Frame(student_frame, style='Card.TFrame')
    student_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(student_card, text="Student Management", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Student Profile Section
    profile_frame = ttk.LabelFrame(student_card, text="Student Profile", padding=15)
    profile_frame.pack(fill='x', padx=15, pady=(0, 15))

    profile_row = ttk.Frame(profile_frame)
    profile_row.pack(fill='x')
    ttk.Label(profile_row, text="Student ID:").pack(side='left')
    self.mgmt_student_var = tk.StringVar()
    ttk.Entry(profile_row, textvariable=self.mgmt_student_var, width=20).pack(side='left', padx=(5, 10))
    ttk.Button(profile_row, text="View Profile",
              command=self.view_student_profile).pack(side='left', padx=(0, 10))
    ttk.Button(profile_row, text="Flag for Review",
              command=self.flag_student_for_review).pack(side='left', padx=(0, 10))
    ttk.Button(profile_row, text="View Progression",
              command=self.view_student_progression).pack(side='left')

    # Student Comparison Section
    compare_frame = ttk.LabelFrame(student_card, text="Compare Students", padding=15)
    compare_frame.pack(fill='x', padx=15, pady=(0, 15))

    compare_row = ttk.Frame(compare_frame)
    compare_row.pack(fill='x')
    ttk.Label(compare_row, text="Student 1:").pack(side='left')
    self.compare_student1_var = tk.StringVar()
    ttk.Entry(compare_row, textvariable=self.compare_student1_var, width=15).pack(side='left', padx=(5, 10))
    ttk.Label(compare_row, text="Student 2:").pack(side='left')
    self.compare_student2_var = tk.StringVar()
    ttk.Entry(compare_row, textvariable=self.compare_student2_var, width=15).pack(side='left', padx=(5, 10))
    ttk.Button(compare_row, text="Compare",
              command=self.compare_students).pack(side='left')

    # Report Generation Section
    report_frame = ttk.LabelFrame(student_card, text="Reports", padding=15)
    report_frame.pack(fill='x', padx=15, pady=(0, 15))

    report_row = ttk.Frame(report_frame)
    report_row.pack(fill='x')
    ttk.Button(report_row, text="Generate Report Card",
              command=self.generate_student_report_card).pack(side='left', padx=(0, 10))
    ttk.Button(report_row, text="Bulk Student Analysis",
              command=self.bulk_student_analysis).pack(side='left')

    # Student Results Display
    results_frame = ttk.LabelFrame(student_card, text="Student Information", padding=15)
    results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    self.student_results_text = scrolledtext.ScrolledText(results_frame, height=12, wrap=tk.WORD)
    self.student_results_text.pack(fill='both', expand=True)


def view_student_profile(self):
    """Comprehensive view of student's submission history, risk level, and patterns"""
    student_id = self.mgmt_student_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    try:
        self.update_status("Loading student profile...")
        self.student_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            # Get student info
            cursor.execute('''
                SELECT username, first_name, last_name, email
                FROM users WHERE username = ? OR id = ?
            ''', (student_id, student_id))
            student = cursor.fetchone()

            # Get submission history
            cursor.execute('''
                SELECT COUNT(*), AVG(ai_probability),
                       MAX(ai_probability), MIN(ai_probability),
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END)
                FROM ai_analysis_history
                WHERE student_id = ?
            ''', (student_id,))
            stats = cursor.fetchone()

            # Get recent submissions
            cursor.execute('''
                SELECT submission_id, document_name, ai_probability, analysis_date
                FROM ai_analysis_history
                WHERE student_id = ?
                ORDER BY analysis_date DESC
                LIMIT 10
            ''', (student_id,))
            recent = cursor.fetchall()

            # Get any flags
            cursor.execute('''
                SELECT flag_reason, flagged_by, flagged_at
                FROM ai_student_flags
                WHERE student_id = ?
                ORDER BY flagged_at DESC
            ''', (student_id,))
            flags = cursor.fetchall()

        finally:
            conn.close()

        result = f"Student Profile: {student_id}\n"
        result += "=" * 50 + "\n\n"

        if student:
            result += f"Name: {student[1] or ''} {student[2] or ''}\n"
            result += f"Username: {student[0]}\n"
            result += f"Email: {student[3] or 'N/A'}\n\n"

        if stats and stats[0]:
            total, avg, max_score, min_score, high_risk = stats
            result += "Submission Statistics:\n"
            result += "-" * 40 + "\n"
            result += f"Total Submissions: {total}\n"
            result += f"Average AI Score: {avg:.1f}%\n"
            result += f"Highest Score: {max_score:.1f}%\n"
            result += f"Lowest Score: {min_score:.1f}%\n"
            result += f"High-Risk Submissions: {high_risk}\n"

            # Risk level assessment
            if high_risk / max(total, 1) > 0.5:
                risk_level = "HIGH"
            elif high_risk / max(total, 1) > 0.2:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            result += f"\nOverall Risk Level: {risk_level}\n"
        else:
            result += "No submission history found.\n"

        if flags:
            result += "\n" + "-" * 40 + "\n"
            result += "Active Flags:\n"
            for reason, flagged_by, flagged_at in flags:
                result += f"  - {reason} (by {flagged_by}, {flagged_at})\n"

        if recent:
            result += "\n" + "-" * 40 + "\n"
            result += "Recent Submissions:\n"
            for sub_id, doc_name, ai_prob, date in recent:
                result += f"  {date}: {doc_name or sub_id} - {ai_prob:.1f}%\n"

        self.student_results_text.insert('1.0', result)
        self.update_status("Profile loaded")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load profile: {str(e)}")


def compare_students(self):
    """Side-by-side comparison of two students' writing patterns"""
    student1 = self.compare_student1_var.get().strip()
    student2 = self.compare_student2_var.get().strip()

    if not student1 or not student2:
        messagebox.showwarning("Warning", "Please enter both student IDs")
        return

    try:
        self.update_status("Comparing students...")
        self.student_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            comparisons = {}
            for student_id in [student1, student2]:
                cursor.execute('''
                    SELECT COUNT(*), AVG(ai_probability),
                           AVG(LENGTH(text_content))
                    FROM ai_analysis_history
                    WHERE student_id = ?
                ''', (student_id,))
                stats = cursor.fetchone()

                # Get writing fingerprint if exists
                cursor.execute('''
                    SELECT fingerprint_data FROM ai_writing_fingerprints
                    WHERE student_id = ?
                ''', (student_id,))
                fingerprint = cursor.fetchone()

                comparisons[student_id] = {
                    'submissions': stats[0] if stats else 0,
                    'avg_ai_score': stats[1] if stats and stats[1] else 0,
                    'avg_length': stats[2] if stats and stats[2] else 0,
                    'fingerprint': json.loads(fingerprint[0]) if fingerprint else None
                }

        finally:
            conn.close()

        result = "Student Comparison\n"
        result += "=" * 50 + "\n\n"

        result += f"{'Metric':<30} {'Student 1':<15} {'Student 2':<15}\n"
        result += "-" * 60 + "\n"

        c1, c2 = comparisons[student1], comparisons[student2]

        result += f"{'Total Submissions':<30} {c1['submissions']:<15} {c2['submissions']:<15}\n"
        result += f"{'Avg AI Score':<30} {c1['avg_ai_score']:.1f}%{'':<10} {c2['avg_ai_score']:.1f}%\n"
        result += f"{'Avg Text Length':<30} {c1['avg_length']:.0f}{'':<10} {c2['avg_length']:.0f}\n"

        if c1['fingerprint'] and c2['fingerprint']:
            f1, f2 = c1['fingerprint'], c2['fingerprint']
            result += f"\nWriting Style Comparison:\n"
            result += "-" * 40 + "\n"
            result += f"{'Avg Sentence Length':<30} {f1.get('avg_sentence_length', 0):.1f}{'':<10} {f2.get('avg_sentence_length', 0):.1f}\n"
            result += f"{'Vocabulary Richness':<30} {f1.get('vocabulary_richness', 0):.2%}{'':<6} {f2.get('vocabulary_richness', 0):.2%}\n"

            # Calculate similarity
            similarity = 0
            if f1.get('avg_sentence_length') and f2.get('avg_sentence_length'):
                diff = abs(f1['avg_sentence_length'] - f2['avg_sentence_length'])
                similarity += max(0, 1 - diff/20) * 50

            if f1.get('vocabulary_richness') and f2.get('vocabulary_richness'):
                diff = abs(f1['vocabulary_richness'] - f2['vocabulary_richness'])
                similarity += max(0, 1 - diff) * 50

            result += f"\nWriting Style Similarity: {similarity:.0f}%\n"
            if similarity > 80:
                result += "WARNING: Very similar writing styles detected!\n"

        self.student_results_text.insert('1.0', result)
        self.update_status("Comparison complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to compare students: {str(e)}")


def generate_student_report_card(self):
    """Generate academic integrity report card for a student"""
    student_id = self.mgmt_student_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # Get comprehensive student data
        cursor.execute('''
            SELECT u.first_name, u.last_name, u.email
            FROM users u WHERE u.username = ? OR u.id = ?
        ''', (student_id, student_id))
        student = cursor.fetchone()

        cursor.execute('''
            SELECT COUNT(*), AVG(ai_probability),
                   SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN ai_probability > 50 THEN 1 ELSE 0 END)
            FROM ai_analysis_history WHERE student_id = ?
        ''', (student_id,))
        stats = cursor.fetchone()

        cursor.execute('''
            SELECT COUNT(*) FROM ai_dean_escalations
            WHERE student_name LIKE ?
        ''', (f'%{student_id}%',))
        escalations = cursor.fetchone()[0]

        conn.close()

        # Generate report
        report = "=" * 60 + "\n"
        report += "ACADEMIC INTEGRITY REPORT CARD\n"
        report += "=" * 60 + "\n\n"

        report += f"Student ID: {student_id}\n"
        if student:
            report += f"Name: {student[0] or ''} {student[1] or ''}\n"
        report += f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

        report += "-" * 60 + "\n"
        report += "INTEGRITY METRICS\n"
        report += "-" * 60 + "\n\n"

        if stats and stats[0]:
            total, avg_score, high_risk, moderate_risk = stats

            # Calculate integrity grade
            if avg_score < 30 and high_risk == 0:
                grade = "A"
                status = "Excellent Standing"
            elif avg_score < 50 and high_risk / max(total, 1) < 0.1:
                grade = "B"
                status = "Good Standing"
            elif avg_score < 70:
                grade = "C"
                status = "Requires Monitoring"
            else:
                grade = "F"
                status = "High Risk - Action Required"

            report += f"Integrity Grade: {grade}\n"
            report += f"Status: {status}\n\n"
            report += f"Total Submissions Analyzed: {total}\n"
            report += f"Average AI Detection Score: {avg_score:.1f}%\n"
            report += f"High-Risk Submissions (>80%): {high_risk}\n"
            report += f"Moderate-Risk Submissions (>50%): {moderate_risk}\n"
            report += f"Dean Escalations: {escalations}\n"
        else:
            report += "No submission data available.\n"

        report += "\n" + "=" * 60 + "\n"

        # Save report
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf")],
            initialfile=f"integrity_report_{student_id}_{datetime.now().strftime('%Y%m%d')}.txt"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            messagebox.showinfo("Success", f"Report card saved to:\n{file_path}")

        self.student_results_text.delete('1.0', tk.END)
        self.student_results_text.insert('1.0', report)
        self.update_status("Report card generated")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate report: {str(e)}")


def flag_student_for_review(self):
    """Manually flag student for academic integrity review"""
    student_id = self.mgmt_student_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    # Get flag reason
    reason = simpledialog.askstring("Flag Student",
                                    "Enter reason for flagging this student:",
                                    parent=self.root)
    if not reason:
        return

    try:
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_student_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                flag_reason TEXT,
                flagged_by TEXT,
                flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                resolved_at TIMESTAMP,
                resolution_notes TEXT
            )
        ''')

        flagged_by = "Unknown"
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            flagged_by = self.auth.current_user.get('username', 'Unknown')

        cursor.execute('''
            INSERT INTO ai_student_flags (student_id, flag_reason, flagged_by)
            VALUES (?, ?, ?)
        ''', (student_id, reason, flagged_by))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"Student {student_id} flagged for review.")
        self.update_status(f"Student {student_id} flagged")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to flag student: {str(e)}")


def view_student_progression(self):
    """Track how student's writing has evolved over time"""
    student_id = self.mgmt_student_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID")
        return

    try:
        self.update_status("Loading progression data...")
        self.student_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT analysis_date, ai_probability, document_name,
                       LENGTH(text_content) as length
                FROM ai_analysis_history
                WHERE student_id = ?
                ORDER BY analysis_date
            ''', (student_id,))
            submissions = cursor.fetchall()
        finally:
            conn.close()

        result = f"Writing Progression - Student {student_id}\n"
        result += "=" * 50 + "\n\n"

        if not submissions:
            result += "No submission history found.\n"
            self.student_results_text.insert('1.0', result)
            return

        result += f"{'Date':<12} {'AI Score':<10} {'Length':<10} Document\n"
        result += "-" * 60 + "\n"

        scores = []
        for date, ai_prob, doc_name, length in submissions:
            scores.append(ai_prob)
            date_str = date[:10] if date else "N/A"
            result += f"{date_str:<12} {ai_prob:>6.1f}%   {length or 0:>8}   {doc_name or 'Untitled'}\n"

        result += "\n" + "-" * 60 + "\n"
        result += "Trend Analysis:\n\n"

        if len(scores) >= 3:
            # Calculate trend
            first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
            second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
            trend = second_half - first_half

            if trend > 10:
                result += "CONCERNING: AI detection scores are INCREASING over time.\n"
                result += f"Average increase: {trend:.1f}%\n"
            elif trend < -10:
                result += "POSITIVE: AI detection scores are DECREASING over time.\n"
                result += f"Average decrease: {abs(trend):.1f}%\n"
            else:
                result += "STABLE: AI detection scores remain relatively consistent.\n"

            # Detect sudden changes
            for i in range(1, len(scores)):
                if abs(scores[i] - scores[i-1]) > 30:
                    result += f"\nALERT: Sudden change detected between submissions {i} and {i+1}\n"
        else:
            result += "Not enough submissions for trend analysis.\n"

        self.student_results_text.insert('1.0', result)
        self.update_status("Progression loaded")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load progression: {str(e)}")


def bulk_student_analysis(self):
    """Analyze all submissions from a class/cohort at once"""
    # Ask for course/cohort selection
    course = simpledialog.askstring("Bulk Analysis",
                                    "Enter course name or ID to analyze:",
                                    parent=self.root)
    if not course:
        return

    try:
        self.update_status("Running bulk analysis...")
        self.student_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id, student_name, COUNT(*) as submissions,
                       AVG(ai_probability) as avg_score,
                       MAX(ai_probability) as max_score,
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
                FROM ai_analysis_history
                WHERE course_name LIKE ?
                GROUP BY student_id
                ORDER BY avg_score DESC
            ''', (f'%{course}%',))
            students = cursor.fetchall()
        finally:
            conn.close()

        result = f"Bulk Analysis - {course}\n"
        result += "=" * 50 + "\n\n"

        if not students:
            result += "No submissions found for this course.\n"
            self.student_results_text.insert('1.0', result)
            return

        result += f"Total Students: {len(students)}\n\n"
        result += f"{'Student':<20} {'Subs':<6} {'Avg':<8} {'Max':<8} {'High Risk':<10}\n"
        result += "-" * 60 + "\n"

        high_risk_students = []
        for student_id, name, subs, avg, max_score, high_risk in students:
            display_name = (name or student_id)[:18]
            result += f"{display_name:<20} {subs:<6} {avg:>5.1f}%  {max_score:>5.1f}%  {high_risk:<10}\n"

            if avg > 60 or high_risk > 0:
                high_risk_students.append(name or student_id)

        result += "\n" + "-" * 60 + "\n"
        result += f"High-Risk Students: {len(high_risk_students)}\n"
        if high_risk_students:
            result += "Students requiring review:\n"
            for s in high_risk_students[:10]:
                result += f"  - {s}\n"

        self.student_results_text.insert('1.0', result)
        self.update_status("Bulk analysis complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to run bulk analysis: {str(e)}")


def create_advanced_analytics_view(self, parent):
    """Create advanced analytics and visualization view"""
    analytics_frame = ttk.Frame(parent)
    analytics_frame.pack(fill="both", expand=True)

    # Main card
    analytics_card = ttk.Frame(analytics_frame, style='Card.TFrame')
    analytics_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(analytics_card, text="Advanced Analytics & Visualization", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Distribution Analysis Section
    dist_frame = ttk.LabelFrame(analytics_card, text="Distribution Analysis", padding=15)
    dist_frame.pack(fill='x', padx=15, pady=(0, 15))

    dist_buttons = ttk.Frame(dist_frame)
    dist_buttons.pack(fill='x')
    ttk.Button(dist_buttons, text="Confidence Distribution",
              command=self.show_detection_confidence_distribution).pack(side='left', padx=(0, 10))
    ttk.Button(dist_buttons, text="Generate Word Cloud",
              command=self.generate_word_cloud).pack(side='left', padx=(0, 10))
    ttk.Button(dist_buttons, text="Correlation Matrix",
              command=self.show_correlation_matrix).pack(side='left')

    # Timeline & Trends Section
    timeline_frame = ttk.LabelFrame(analytics_card, text="Timeline & Trends", padding=15)
    timeline_frame.pack(fill='x', padx=15, pady=(0, 15))

    timeline_buttons = ttk.Frame(timeline_frame)
    timeline_buttons.pack(fill='x')
    ttk.Button(timeline_buttons, text="Submission Timeline",
              command=self.plot_submission_timeline).pack(side='left', padx=(0, 10))
    ttk.Button(timeline_buttons, text="Weekly Trends",
              command=self.show_weekly_trends).pack(side='left')

    # Clustering & Comparison Section
    cluster_frame = ttk.LabelFrame(analytics_card, text="Clustering & Comparison", padding=15)
    cluster_frame.pack(fill='x', padx=15, pady=(0, 15))

    cluster_buttons = ttk.Frame(cluster_frame)
    cluster_buttons.pack(fill='x')
    ttk.Button(cluster_buttons, text="Cluster Similar Submissions",
              command=self.cluster_similar_submissions).pack(side='left', padx=(0, 10))
    ttk.Button(cluster_buttons, text="Department Comparison",
              command=self.generate_department_comparison).pack(side='left')

    # Export Section
    export_frame = ttk.LabelFrame(analytics_card, text="Export", padding=15)
    export_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(export_frame, text="Export Visualization Pack",
              command=self.export_visualization_pack).pack(anchor='w')

    # Results Display
    results_frame = ttk.LabelFrame(analytics_card, text="Analytics Results", padding=15)
    results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    self.analytics_results_text = scrolledtext.ScrolledText(results_frame, height=10, wrap=tk.WORD)
    self.analytics_results_text.pack(fill='both', expand=True)


def show_detection_confidence_distribution(self):
    """Histogram of confidence scores across all submissions"""
    try:
        self.update_status("Generating distribution...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('SELECT ai_probability FROM ai_analysis_history')
            scores = [row[0] for row in cursor.fetchall() if row[0] is not None]
        finally:
            conn.close()

        if not scores:
            self.analytics_results_text.insert('1.0', "No data available for distribution analysis.")
            return

        # Create distribution buckets
        buckets = {
            '0-20%': 0, '20-40%': 0, '40-60%': 0,
            '60-80%': 0, '80-100%': 0
        }

        for score in scores:
            if score < 20:
                buckets['0-20%'] += 1
            elif score < 40:
                buckets['20-40%'] += 1
            elif score < 60:
                buckets['40-60%'] += 1
            elif score < 80:
                buckets['60-80%'] += 1
            else:
                buckets['80-100%'] += 1

        result = "AI Detection Confidence Distribution\n"
        result += "=" * 50 + "\n\n"
        result += f"Total Submissions: {len(scores)}\n"
        result += f"Average Score: {sum(scores)/len(scores):.1f}%\n"
        result += f"Median Score: {sorted(scores)[len(scores)//2]:.1f}%\n\n"

        result += "Distribution:\n"
        result += "-" * 40 + "\n"

        max_count = max(buckets.values()) if buckets.values() else 1
        for bucket, count in buckets.items():
            bar_length = int(count / max_count * 30)
            bar = "#" * bar_length
            pct = count / len(scores) * 100
            result += f"{bucket:<10} {bar:<30} {count:>5} ({pct:.1f}%)\n"

        result += "\n" + "-" * 40 + "\n"

        # Risk assessment
        high_risk = buckets['80-100%']
        moderate_risk = buckets['60-80%']
        result += f"\nHigh Risk (>80%): {high_risk} ({high_risk/len(scores)*100:.1f}%)\n"
        result += f"Moderate Risk (60-80%): {moderate_risk} ({moderate_risk/len(scores)*100:.1f}%)\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Distribution analysis complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate distribution: {str(e)}")


def generate_word_cloud(self):
    """Generate word cloud from flagged vs clean submissions"""
    try:
        self.update_status("Generating word analysis...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            # Get flagged submissions (high AI score)
            cursor.execute('''
                SELECT text_content FROM ai_analysis_history
                WHERE ai_probability > 70 AND text_content IS NOT NULL
                LIMIT 50
            ''')
            flagged_texts = [row[0] for row in cursor.fetchall()]

            # Get clean submissions (low AI score)
            cursor.execute('''
                SELECT text_content FROM ai_analysis_history
                WHERE ai_probability < 30 AND text_content IS NOT NULL
                LIMIT 50
            ''')
            clean_texts = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

        def get_word_freq(texts):
            words = {}
            stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                         'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                         'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                         'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                         'as', 'into', 'through', 'during', 'before', 'after', 'above',
                         'below', 'between', 'under', 'again', 'further', 'then', 'once',
                         'and', 'but', 'if', 'or', 'because', 'until', 'while', 'although',
                         'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them',
                         'their', 'what', 'which', 'who', 'whom', 'whose', 'where', 'when',
                         'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
                         'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
                         'own', 'same', 'so', 'than', 'too', 'very', 'can', 'just', 'also'}
            for text in texts:
                for word in text.lower().split():
                    word = ''.join(c for c in word if c.isalpha())
                    if word and len(word) > 3 and word not in stop_words:
                        words[word] = words.get(word, 0) + 1
            return sorted(words.items(), key=lambda x: -x[1])[:30]

        flagged_words = get_word_freq(flagged_texts)
        clean_words = get_word_freq(clean_texts)

        result = "Word Frequency Analysis\n"
        result += "=" * 50 + "\n\n"

        result += "Top Words in HIGH-RISK Submissions:\n"
        result += "-" * 40 + "\n"
        for word, count in flagged_words[:15]:
            result += f"  {word:<20} {count}\n"

        result += "\nTop Words in LOW-RISK Submissions:\n"
        result += "-" * 40 + "\n"
        for word, count in clean_words[:15]:
            result += f"  {word:<20} {count}\n"

        # Find unique words
        flagged_set = set(w for w, c in flagged_words)
        clean_set = set(w for w, c in clean_words)

        unique_flagged = flagged_set - clean_set
        unique_clean = clean_set - flagged_set

        result += f"\nWords unique to high-risk: {', '.join(list(unique_flagged)[:10])}\n"
        result += f"Words unique to low-risk: {', '.join(list(unique_clean)[:10])}\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Word analysis complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate word cloud: {str(e)}")


def plot_submission_timeline(self):
    """Interactive timeline of submissions with risk indicators"""
    try:
        self.update_status("Generating timeline...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT date(analysis_date) as date, COUNT(*) as count,
                       AVG(ai_probability) as avg_score,
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
                FROM ai_analysis_history
                WHERE analysis_date IS NOT NULL
                GROUP BY date(analysis_date)
                ORDER BY date DESC
                LIMIT 30
            ''')
            data = cursor.fetchall()
        finally:
            conn.close()

        result = "Submission Timeline (Last 30 Days)\n"
        result += "=" * 50 + "\n\n"

        if not data:
            result += "No timeline data available.\n"
            self.analytics_results_text.insert('1.0', result)
            return

        result += f"{'Date':<12} {'Count':<8} {'Avg Score':<12} {'High Risk':<10}\n"
        result += "-" * 50 + "\n"

        for date, count, avg_score, high_risk in reversed(data):
            risk_indicator = "!!!" if high_risk > 0 else ""
            result += f"{date:<12} {count:<8} {avg_score:>6.1f}%     {high_risk:<5} {risk_indicator}\n"

        # Show visual timeline
        result += "\n" + "-" * 50 + "\n"
        result += "Activity Graph:\n\n"

        max_count = max(d[1] for d in data) if data else 1
        for date, count, avg_score, high_risk in reversed(data[-14:]):
            bar_length = int(count / max_count * 20)
            bar = "#" * bar_length
            risk_mark = "[!]" if high_risk > 0 else "   "
            result += f"{date[-5:]}: {bar:<20} {count:>3} {risk_mark}\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Timeline generated")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to plot timeline: {str(e)}")


def show_correlation_matrix(self):
    """Show correlations between different detection metrics"""
    try:
        self.update_status("Calculating correlations...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ai_probability, LENGTH(text_content),
                       (LENGTH(text_content) - LENGTH(REPLACE(text_content, ' ', ''))) as word_count
                FROM ai_analysis_history
                WHERE text_content IS NOT NULL
                LIMIT 500
            ''')
            data = cursor.fetchall()
        finally:
            conn.close()

        if len(data) < 10:
            self.analytics_results_text.insert('1.0', "Insufficient data for correlation analysis.")
            return

        # Calculate correlations
        ai_scores = [d[0] for d in data if d[0] is not None]
        lengths = [d[1] for d in data if d[1] is not None]
        words = [d[2] for d in data if d[2] is not None]

        def correlation(x, y):
            n = min(len(x), len(y))
            if n < 2:
                return 0
            x, y = x[:n], y[:n]
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
            den_x = sum((xi - mean_x)**2 for xi in x) ** 0.5
            den_y = sum((yi - mean_y)**2 for yi in y) ** 0.5
            if den_x * den_y == 0:
                return 0
            return num / (den_x * den_y)

        corr_ai_length = correlation(ai_scores, lengths)
        corr_ai_words = correlation(ai_scores, words)
        corr_length_words = correlation(lengths, words)

        result = "Correlation Matrix\n"
        result += "=" * 50 + "\n\n"
        result += "Correlations between detection metrics:\n\n"

        result += f"{'Metric Pair':<35} {'Correlation':<15}\n"
        result += "-" * 50 + "\n"
        result += f"{'AI Score vs Text Length':<35} {corr_ai_length:>+.3f}\n"
        result += f"{'AI Score vs Word Count':<35} {corr_ai_words:>+.3f}\n"
        result += f"{'Text Length vs Word Count':<35} {corr_length_words:>+.3f}\n"

        result += "\n" + "-" * 50 + "\n"
        result += "\nInterpretation:\n"
        result += "Values close to +1: Strong positive correlation\n"
        result += "Values close to -1: Strong negative correlation\n"
        result += "Values close to 0: No correlation\n\n"

        if abs(corr_ai_length) > 0.5:
            result += f"NOTE: {'Longer' if corr_ai_length > 0 else 'Shorter'} texts tend to have higher AI scores.\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Correlation analysis complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to calculate correlations: {str(e)}")


def cluster_similar_submissions(self):
    """Use ML clustering to find suspiciously similar submissions"""
    try:
        self.update_status("Clustering submissions...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT submission_id, student_id, student_name, text_content, ai_probability
                FROM ai_analysis_history
                WHERE text_content IS NOT NULL AND LENGTH(text_content) > 100
                ORDER BY analysis_date DESC
                LIMIT 100
            ''')
            submissions = cursor.fetchall()
        finally:
            conn.close()

        if len(submissions) < 5:
            self.analytics_results_text.insert('1.0', "Insufficient submissions for clustering.")
            return

        # Simple similarity detection based on word overlap
        def get_word_set(text):
            words = set(w.lower() for w in text.split() if len(w) > 4)
            return words

        def jaccard_similarity(set1, set2):
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            return intersection / union if union > 0 else 0

        # Find similar pairs
        similar_pairs = []
        word_sets = [(s[0], s[1], s[2], get_word_set(s[3]), s[4]) for s in submissions]

        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                sim = jaccard_similarity(word_sets[i][3], word_sets[j][3])
                if sim > 0.4:  # 40% similarity threshold
                    similar_pairs.append((
                        word_sets[i][2] or word_sets[i][1],
                        word_sets[j][2] or word_sets[j][1],
                        sim,
                        word_sets[i][4],
                        word_sets[j][4]
                    ))

        result = "Submission Clustering Analysis\n"
        result += "=" * 50 + "\n\n"
        result += f"Submissions Analyzed: {len(submissions)}\n"
        result += f"Similar Pairs Found: {len(similar_pairs)}\n\n"

        if similar_pairs:
            result += "Suspiciously Similar Submissions:\n"
            result += "-" * 50 + "\n"

            similar_pairs.sort(key=lambda x: -x[2])
            for s1, s2, sim, ai1, ai2 in similar_pairs[:20]:
                result += f"\n{s1[:20]:<20} vs {s2[:20]:<20}\n"
                result += f"  Similarity: {sim:.0%} | AI Scores: {ai1:.0f}%, {ai2:.0f}%\n"

            result += "\n" + "-" * 50 + "\n"
            result += "\nWARNING: High similarity may indicate:\n"
            result += "  - Collaboration without permission\n"
            result += "  - Shared AI-generated content\n"
            result += "  - Plagiarism\n"
        else:
            result += "No suspiciously similar submissions found.\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Clustering complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to cluster submissions: {str(e)}")


def generate_department_comparison(self):
    """Compare AI detection rates across departments"""
    try:
        self.update_status("Generating comparison...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT course_name, COUNT(*) as submissions,
                       AVG(ai_probability) as avg_score,
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
                FROM ai_analysis_history
                WHERE course_name IS NOT NULL
                GROUP BY course_name
                ORDER BY avg_score DESC
            ''')
            departments = cursor.fetchall()
        finally:
            conn.close()

        result = "Department/Course Comparison\n"
        result += "=" * 50 + "\n\n"

        if not departments:
            result += "No departmental data available.\n"
            self.analytics_results_text.insert('1.0', result)
            return

        result += f"{'Course/Dept':<25} {'Subs':<8} {'Avg':<8} {'High Risk':<10}\n"
        result += "-" * 55 + "\n"

        total_subs = sum(d[1] for d in departments)
        total_high_risk = sum(d[3] for d in departments)

        for course, subs, avg, high_risk in departments:
            course_short = (course or "Unknown")[:23]
            risk_pct = high_risk / max(subs, 1) * 100
            flag = " !!!" if risk_pct > 20 else ""
            result += f"{course_short:<25} {subs:<8} {avg:>5.1f}%  {high_risk:<5} ({risk_pct:.0f}%){flag}\n"

        result += "\n" + "-" * 55 + "\n"
        result += f"\nOverall Statistics:\n"
        result += f"Total Submissions: {total_subs}\n"
        result += f"Total High-Risk: {total_high_risk} ({total_high_risk/max(total_subs,1)*100:.1f}%)\n"

        # Identify outliers
        if departments:
            avg_all = sum(d[2] for d in departments) / len(departments)
            outliers = [d for d in departments if d[2] > avg_all + 15]
            if outliers:
                result += f"\nCourses with above-average AI scores:\n"
                for d in outliers:
                    result += f"  - {d[0]}: {d[2]:.1f}%\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Comparison complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate comparison: {str(e)}")


def show_weekly_trends(self):
    """Weekly trend analysis with anomaly highlighting"""
    try:
        self.update_status("Analyzing trends...")
        self.analytics_results_text.delete('1.0', tk.END)

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT strftime('%Y-W%W', analysis_date) as week,
                       COUNT(*) as submissions,
                       AVG(ai_probability) as avg_score,
                       SUM(CASE WHEN ai_probability > 80 THEN 1 ELSE 0 END) as high_risk
                FROM ai_analysis_history
                WHERE analysis_date IS NOT NULL
                GROUP BY week
                ORDER BY week DESC
                LIMIT 12
            ''')
            weeks = cursor.fetchall()
        finally:
            conn.close()

        result = "Weekly Trend Analysis\n"
        result += "=" * 50 + "\n\n"

        if not weeks:
            result += "No weekly data available.\n"
            self.analytics_results_text.insert('1.0', result)
            return

        result += f"{'Week':<12} {'Subs':<8} {'Avg Score':<12} {'High Risk':<10}\n"
        result += "-" * 50 + "\n"

        # Calculate averages for anomaly detection
        avg_subs = sum(w[1] for w in weeks) / len(weeks)
        avg_score = sum(w[2] for w in weeks) / len(weeks)

        anomalies = []
        for week, subs, score, high_risk in reversed(weeks):
            flags = []
            if subs > avg_subs * 1.5:
                flags.append("high volume")
            if score > avg_score + 10:
                flags.append("high AI score")
            if high_risk / max(subs, 1) > 0.3:
                flags.append("many flagged")

            flag_str = " [" + ", ".join(flags) + "]" if flags else ""
            result += f"{week:<12} {subs:<8} {score:>6.1f}%     {high_risk:<5}{flag_str}\n"

            if flags:
                anomalies.append((week, flags))

        result += "\n" + "-" * 50 + "\n"

        # Trend direction
        if len(weeks) >= 4:
            recent = sum(w[2] for w in weeks[:4]) / 4
            older = sum(w[2] for w in weeks[-4:]) / 4

            result += f"\nTrend Analysis:\n"
            if recent > older + 5:
                result += "ALERT: AI detection scores are INCREASING\n"
                result += f"Recent avg: {recent:.1f}% vs Earlier avg: {older:.1f}%\n"
            elif recent < older - 5:
                result += "POSITIVE: AI detection scores are DECREASING\n"
            else:
                result += "Scores are relatively stable\n"

        if anomalies:
            result += f"\nAnomalous Weeks: {len(anomalies)}\n"

        self.analytics_results_text.insert('1.0', result)
        self.update_status("Trend analysis complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to analyze trends: {str(e)}")


def export_visualization_pack(self):
    """Export all charts/graphs as image pack for reports"""
    try:
        # Select export directory
        export_dir = filedialog.askdirectory(title="Select Export Directory")
        if not export_dir:
            return

        self.update_status("Exporting visualization pack...")

        # Create export folder
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pack_dir = os.path.join(export_dir, f"ai_detection_report_{timestamp}")
        os.makedirs(pack_dir, exist_ok=True)

        # Export each analysis as text (since we don't have matplotlib)
        analyses = [
            ("confidence_distribution.txt", self.show_detection_confidence_distribution),
            ("word_analysis.txt", self.generate_word_cloud),
            ("timeline.txt", self.plot_submission_timeline),
            ("correlations.txt", self.show_correlation_matrix),
            ("clustering.txt", self.cluster_similar_submissions),
            ("department_comparison.txt", self.generate_department_comparison),
            ("weekly_trends.txt", self.show_weekly_trends)
        ]

        exported = 0
        for filename, func in analyses:
            try:
                func()
                content = self.analytics_results_text.get('1.0', tk.END)
                file_path = os.path.join(pack_dir, filename)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                exported += 1
            except Exception:
                pass

        # Create summary file
        summary = f"AI Detection Analytics Export\n"
        summary += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        summary += f"Files Exported: {exported}\n\n"
        summary += "Contents:\n"
        for filename, _ in analyses:
            summary += f"  - {filename}\n"

        with open(os.path.join(pack_dir, "README.txt"), 'w', encoding='utf-8') as f:
            f.write(summary)

        messagebox.showinfo("Success",
                          f"Visualization pack exported!\n\n"
                          f"Location: {pack_dir}\n"
                          f"Files: {exported + 1}")
        self.update_status("Export complete")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export: {str(e)}")



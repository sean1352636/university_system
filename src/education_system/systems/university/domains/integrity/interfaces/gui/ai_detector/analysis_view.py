"""Text analysis: take a reading of a piece of work for a student on a
module the signed-in member of staff reviews, and show it — the indicators,
the passages behind them and what to do next. A reading is an indication to
review with the student, never a verdict."""

import logging
import os
import threading

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

from education_system.platform.delivery.gui.tk_threads import start_thread, ui

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)


def create_analysis_view(self, parent):
    """Create the main text analysis view"""
    analysis_frame = ttk.Frame(parent)
    analysis_frame.pack(fill='both', expand=True)

    # Create two-column layout
    left_frame = ttk.Frame(analysis_frame)
    left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

    right_frame = ttk.Frame(analysis_frame)
    right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

    # Left side - Input
    self.create_input_section(left_frame)

    # Right side - Results
    self.create_results_section(right_frame)


def create_input_section(self, parent):
    """Create text input section"""
    # Input card
    input_card = ttk.Frame(parent, style='Card.TFrame')
    input_card.pack(fill='both', expand=True, padx=5, pady=5)

    # Card title
    ttk.Label(input_card, text=_t('gui.academics.ai_detector.analysis_view.labels.text_input', default="Text Input"), style='Title.TLabel').pack(anchor='w', padx=15, pady=(15, 5))

    # Metadata inputs
    metadata_frame = ttk.Frame(input_card)
    metadata_frame.pack(fill='x', padx=15, pady=(0, 10))

    # Row 1: Student and Title
    row1 = ttk.Frame(metadata_frame)
    row1.pack(fill='x', pady=(0, 5))

    ttk.Label(row1, text=_t('gui.academics.ai_detector.analysis_view.labels.module', default="Module:")).pack(side='left')
    self.module_combo = common.IdPicker(row1, common.modules(self), width=28)
    self.module_combo.pack(side='left', padx=(5, 15))
    self.module_combo.bind('<<ComboboxSelected>>', self._on_module_selected)

    ttk.Label(row1, text=_t('gui.academics.ai_detector.analysis_view.labels.student', default="Student:")).pack(side='left')
    self.student_combo = common.IdPicker(row1, (), width=28)
    self.student_combo.pack(side='left', padx=(5, 0))

    # Row 2: Assignment and Title
    row2 = ttk.Frame(metadata_frame)
    row2.pack(fill='x')

    ttk.Label(row2, text=_t('gui.academics.ai_detector.analysis_view.labels.assignment', default="Assignment:")).pack(side='left')
    self.assignment_combo = common.IdPicker(row2, (), allow_blank=True, blank_label="(none)",
                                            width=30)
    self.assignment_combo.pack(side='left', padx=(5, 15))

    ttk.Label(row2, text=_t('gui.academics.ai_detector.analysis_view.labels.title', default="Title:")).pack(side='left')
    self.title_var = tk.StringVar()
    self.title_entry = ttk.Entry(row2, textvariable=self.title_var, width=30)
    self.title_entry.pack(side='left', padx=(5, 0))

    # Text input area
    ttk.Label(input_card, text=_t('gui.academics.ai_detector.analysis_view.labels.text_to_analyze', default="Text to Analyze:"), style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=(10, 5))

    # Buttons and word count packed BEFORE text area so they stay visible
    button_frame = ttk.Frame(input_card)
    button_frame.pack(side='bottom', fill='x', padx=15, pady=(0, 15))

    self.upload_btn = ttk.Button(button_frame, text=_t('gui.academics.ai_detector.analysis_view.buttons.load_file', default="📁 Load File"), command=self.load_file)
    self.upload_btn.pack(side='left', padx=(0, 10))

    self.clear_btn = ttk.Button(button_frame, text=_t('gui.academics.ai_detector.analysis_view.buttons.clear', default="🗑️ Clear"), command=self.clear_input)
    self.clear_btn.pack(side='left', padx=(0, 10))

    self.analyze_btn = ttk.Button(
        button_frame,
        text=_t('gui.academics.ai_detector.analysis_view.buttons.take_reading', default="🔍 Take a reading"),
        command=self.analyze_text,
        style='Accent.TButton'
    )
    self.analyze_btn.pack(side='right')

    self.word_count_label = ttk.Label(input_card, text=_t('gui.academics.ai_detector.analysis_view.labels.words_0', default="Words: 0"), style='Subtitle.TLabel')
    self.word_count_label.pack(side='bottom', anchor='e', padx=15, pady=(0, 5))

    # Text widget fills remaining space
    text_frame = ttk.Frame(input_card)
    text_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))

    self.text_input = scrolledtext.ScrolledText(
        text_frame,
        wrap=tk.WORD,
        width=50,
        height=20,
        bg=self.colors['bg_secondary'],
        fg=self.colors['text_primary'],
        insertbackground=self.colors['text_primary'],
        selectbackground=self.colors['accent']
    )
    self.text_input.pack(fill='both', expand=True)

    self.text_input.bind('<KeyRelease>', self.update_word_count)


def create_results_section(self, parent):
    """Create results display section"""
    # Results card
    results_card = ttk.Frame(parent, style='Card.TFrame')
    results_card.pack(fill='both', expand=True, padx=5, pady=5)

    # Card title
    ttk.Label(results_card, text=_t('gui.academics.ai_detector.analysis_view.labels.analysis_results', default="Analysis Results"), style='Title.TLabel').pack(anchor='w', padx=15, pady=(15, 5))

    # Results container
    self.results_container = ttk.Frame(results_card)
    self.results_container.pack(fill='both', expand=True, padx=15, pady=15)

    # Initial empty state
    self.show_empty_results()


def show_empty_results(self):
    """Show empty state for results"""
    for widget in self.results_container.winfo_children():
        widget.destroy()

    empty_label = ttk.Label(self.results_container, wraplength=520,
                          text=_t('gui.academics.ai_detector.analysis_view.labels.choose_and_take_reading', default="Choose the module and student, paste or load the work, then take a reading.\n\n") + common.NOTICE,
                          style='Subtitle.TLabel')
    empty_label.pack(expand=True)


def load_file(self):
    """Load text from a file (text, code, PDF, Word)."""
    file_path = filedialog.askopenfilename(
        parent=self.root,
        title=_t('gui.academics.ai_detector.analysis_view.dialogs.select_document_file', default="Select document file"),
        filetypes=[("Documents", "*.txt *.md *.pdf *.docx *.rtf *.tex"), ("All files", "*.*")])
    if not file_path:
        return
    from education_system.systems.university.infrastructure.integrity import text_extract
    try:
        content = text_extract.extract(file_path)
    except ValueError as exc:
        messagebox.showwarning(common.TITLE, str(exc), parent=self.root)
        return
    self.text_input.delete('1.0', tk.END)
    self.text_input.insert('1.0', content)
    self._loaded_file_type = text_extract.file_type(file_path)
    self.update_word_count()
    filename = os.path.basename(file_path)
    if not self.title_var.get():
        self.title_var.set(os.path.splitext(filename)[0])
    self.update_status(f"Loaded file: {filename}")


def clear_input(self):
    """Clear all input fields"""
    self.text_input.delete('1.0', tk.END)
    self.student_combo.set("")
    self.title_var.set("")
    self.module_combo.set("")
    self.assignment_combo.set_choices(())
    self.update_word_count()
    self.show_empty_results()


def analyze_text(self):
    """Take a reading of the input text for the chosen student and module."""
    text = self.text_input.get('1.0', tk.END).strip()
    if not text:
        messagebox.showwarning(common.TITLE, "Paste or load the work first.", parent=self.root)
        return
    module = self.module_combo.value()
    student = self.student_combo.value()
    if not module or not student:
        messagebox.showwarning(common.TITLE, "Choose the module and the student from the lists.",
                               parent=self.root)
        return
    assignment = self.assignment_combo.value()
    title = self.title_var.get().strip() or None
    file_type = getattr(self, "_loaded_file_type", "txt")

    self.analyze_btn.config(state='disabled', text="🔄 Reading...")
    self.update_status("Taking a reading...")
    self.show_progress(True)
    detector = self.detector

    def analyze_thread():
        try:
            result = detector.analyze_text_enhanced(
                text=text, title=title, student_id=student, course_code=module,
                assignment_id=assignment, file_type=file_type)
            ui(self.root, self.display_results, result, text)
        except (PermissionError, ValueError) as exc:
            ui(self.root, self.analysis_error, str(exc))
        except Exception as exc:
            logger.exception("AI-writing reading failed")
            ui(self.root, self.analysis_error, str(exc))

    start_thread(self.root, analyze_thread)


def display_results(self, result, text=None):
    """Show a reading: notice, summary, indicators, extras, highlighted text
    and what to do next."""
    for widget in self.results_container.winfo_children():
        widget.destroy()
    self.analyze_btn.config(state='normal', text="🔍 Take a reading")
    self.show_progress(False)
    if result.get('skipped'):
        self.update_status(result.get('reason') or "Not read")
        ttk.Label(self.results_container, text=result.get('reason') or "Not read",
                  wraplength=520).pack(expand=True)
        return
    self.analysis_results = result
    self.current_submission_id = result.get('submission_id')

    main_results = ttk.Frame(self.results_container)
    main_results.pack(fill='both', expand=True)
    self.create_score_display(main_results, result, text)
    self.create_detailed_analysis(main_results, result, text)
    self.create_recommendations(main_results, result)
    self.update_status(f"Reading {result.get('result_id')} taken")


def create_score_display(self, parent, result, text=None):
    """The reading itself (notice, level, indicators, highlighted text)."""
    common.show_reading(self, parent, result, text)


def create_detailed_analysis(self, parent, result, text=None):
    """Sentence by sentence (which indicator passages fall where), then the
    informational extras: citation checks, disguised characters,
    paraphrase-tool and prompt-artefact patterns, and (for a full analysis
    with metadata) timing, behaviour, images and code."""
    extras = dict(result.get('extras') or {})
    extras.update(result.get('advanced_analyses') or {})
    if not extras and not (text and result.get('indicators')):
        return
    details_frame = ttk.LabelFrame(parent, text="More detail (informational)", padding=6)
    details_frame.pack(fill='both', expand=True, pady=(0, 10))
    analysis_notebook = ttk.Notebook(details_frame)
    analysis_notebook.pack(fill='both', expand=True)
    if text and result.get('indicators'):
        self.create_sentences_tab(analysis_notebook, result, text)
    for name, data in extras.items():
        self.create_pattern_tab(analysis_notebook, {'name': name, 'data': data})


def create_sentences_tab(self, notebook, result, text):
    """Each sentence with the indicator passages in it and the share of it
    they cover; double-click a sentence to see it in full."""
    from education_system.systems.university.shared.ai.ai_detector.detector import (
        reading,
    )
    rows = reading.sentence_breakdown(text, result.get('passages') or [])
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=f"Sentences ({len(rows)})")
    ttk.Label(frame, text="Where the indicator passages fall. A sentence with passages in it is "
                          "something to ask the student about, not evidence.",
              wraplength=620).pack(anchor='w', padx=4, pady=(4, 2))
    names = common.PASSAGE_NAMES
    cols = (("n", "#", 40), ("words", "Words", 60), ("share", "Covered", 70),
            ("kinds", "Passages", 200), ("text", "Sentence", 420))
    box = ttk.Frame(frame)
    box.pack(fill='both', expand=True)
    tree = ttk.Treeview(box, columns=[c[0] for c in cols], show='headings', height=8)
    for col, label, width in cols:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor='w')
    bar = ttk.Scrollbar(box, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side='right', fill='y')
    tree.pack(side='left', fill='both', expand=True)
    for kind, colour in common.PASSAGE_COLOURS.items():
        tree.tag_configure(kind, background=colour)
    for r in rows:
        kinds = ", ".join(f"{names.get(k, k)} ×{n}" for k, n in r['kinds'].items())
        tag = max(r['kinds'], key=r['kinds'].get) if r['kinds'] else ''
        tree.insert('', 'end', iid=str(r['index']), tags=(tag,) if tag else (),
                    values=(r['index'], r['words'], f"{r['share']:.0%}", kinds,
                            r['text'][:200]))

    def open_sentence(_event=None):
        sel = tree.selection()
        if sel:
            r = rows[int(sel[0]) - 1]
            common.text_window(self, f"Sentence {r['index']}",
                               {"sentence": r['text'], "words": r['words'],
                                "covered": f"{r['share']:.0%}",
                                "passages": {names.get(k, k): n for k, n in r['kinds'].items()}},
                               640, 320)
    tree.bind('<Double-1>', open_sentence)


def create_pattern_tab(self, notebook, result):
    """One informational extra as a tab."""
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=str(result.get('name', 'detail')).replace('_', ' ').title())
    self.create_advanced_analysis_section(frame, result.get('name', ''), result.get('data'))


def create_pattern_indicator(self, parent, pattern_name, pattern_data):
    """One indicator row (label, value, meaning)."""
    row = ttk.Frame(parent)
    row.pack(fill='x', padx=5, pady=2)
    data = pattern_data if isinstance(pattern_data, dict) else {'shown': pattern_data}
    ttk.Label(row, text=str(data.get('label') or pattern_name).replace('_', ' '),
              font=('Segoe UI', 10, 'bold')).pack(side='left')
    ttk.Label(row, text=str(data.get('shown', ''))).pack(side='left', padx=8)
    if data.get('meaning'):
        ttk.Label(parent, text=data['meaning'], wraplength=520,
                  style='Subtitle.TLabel').pack(anchor='w', padx=15)


def create_sentence_tab(self, notebook, result):
    """The text with the passages behind the indicators highlighted."""
    frame = ttk.Frame(notebook)
    notebook.add(frame, text="Passages")
    common.show_reading(self, frame, result, result.get('text'))


def create_advanced_analysis_tab(self, notebook, result):
    """Create advanced analysis tab"""
    advanced_frame = ttk.Frame(notebook)
    notebook.add(advanced_frame, text=_t('gui.academics.ai_detector.analysis_view.tabs.advanced', default="Advanced"))

    # Advanced analysis results
    advanced_analyses = result.get('advanced_analyses', {})

    if advanced_analyses:
        # Create scrollable frame
        canvas = tk.Canvas(advanced_frame, bg=self.colors['bg_primary'])
        scrollbar = ttk.Scrollbar(advanced_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Display each advanced analysis
        for analysis_name, analysis_data in advanced_analyses.items():
            self.create_advanced_analysis_section(scrollable_frame, analysis_name, analysis_data)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    else:
        ttk.Label(advanced_frame, text=_t('gui.academics.ai_detector.analysis_view.labels.advanced_analysis_not_available', default="Advanced analysis not available"),
                 style='Subtitle.TLabel').pack(expand=True)


def create_advanced_analysis_section(self, parent, name, data):
    """Create section for advanced analysis"""
    section_frame = ttk.LabelFrame(parent, text=name.replace('_', ' ').title(), padding=10)
    section_frame.pack(fill='x', padx=5, pady=5)

    if isinstance(data, dict):
        evidence = data.get('evidence') if isinstance(data.get('evidence'), dict) else {}
        for key, value in list(data.items()) + list(evidence.items()):
            if key in ('evidence', 'informational'):
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                ttk.Label(section_frame, text=f"{key.replace('_', ' ').title()}: {value}",
                          wraplength=520).pack(anchor='w')
            elif isinstance(value, list) and value and all(isinstance(v, str) for v in value):
                ttk.Label(section_frame, text=f"{key.replace('_', ' ').title()}: "
                                              + "; ".join(value[:10]),
                          wraplength=520).pack(anchor='w')
    else:
        ttk.Label(section_frame, text=str(data), wraplength=520).pack(anchor='w')


def create_recommendations(self, parent, result):
    """Create recommendations section"""
    rec_frame = ttk.Frame(parent, style='Card.TFrame')
    rec_frame.pack(fill='x')

    ttk.Label(rec_frame, text=_t('gui.academics.ai_detector.analysis_view.labels.what_to_do_next', default="What to do next"),
             style='Title.TLabel').pack(anchor='w', padx=15, pady=(15, 10))

    # Get recommendations
    recommendations = result.get('recommendations', [])

    if not recommendations:
        recommendations = ["No follow-up suggested by this reading."]

    # Display recommendations
    for i, rec in enumerate(recommendations, 1):
        rec_item_frame = ttk.Frame(rec_frame)
        rec_item_frame.pack(fill='x', padx=15, pady=2)

        ttk.Label(rec_item_frame, text=f"{i}.", style='Subtitle.TLabel').pack(side='left')
        ttk.Label(rec_item_frame, text=rec, style='Subtitle.TLabel',
                  wraplength=520).pack(side='left', padx=(5, 0))

    # Add padding at bottom
    ttk.Label(rec_frame, text="").pack(pady=10)


def analysis_error(self, error_message):
    """Handle analysis error"""
    self.analyze_btn.config(state='normal', text="🔍 Take a reading")
    self.show_progress(False)
    self.update_status("No reading taken")
    messagebox.showerror(common.TITLE, f"No reading taken:\n{error_message}", parent=self.root)


def get_risk_color(self, score):
    """Colour for a strength against the review threshold."""
    return common.level_colour(self, score)


def get_risk_text(self, score):
    """Words for a strength against the review threshold."""
    if score is None:
        return "Not read"
    limit = common.threshold()
    if score >= limit:
        return "Waits for review"
    return "Below the review level"


def update_word_count(self, event=None):
    """Update word count display"""
    text = self.text_input.get('1.0', tk.END)
    word_count = len(text.split())
    char_count = len(text.strip())
    self.word_count_label.config(text=f"Words: {word_count} | Characters: {char_count}")



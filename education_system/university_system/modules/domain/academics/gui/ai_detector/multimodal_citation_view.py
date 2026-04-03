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
    from pypdf import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from education_system.university_system.modules.shared.utils.i18n import get_text, _

def create_multi_modal_analysis_tab(self):
    """Create multi-modal analysis tab"""
    multimodal_frame = ttk.Frame(self.notebook)
    self.notebook.add(multimodal_frame, text="🖼️ Multi-Modal")

    # Multi-modal card
    multimodal_card = ttk.Frame(multimodal_frame, style='Card.TFrame')
    multimodal_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(multimodal_card, text="Multi-Modal Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Analysis types
    types_frame = ttk.LabelFrame(multimodal_card, text="Analysis Types", padding=15)
    types_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(types_frame, text="📝 Text + Image Consistency",
              command=self.analyze_text_image_consistency).pack(fill='x', pady=(0, 5))
    ttk.Button(types_frame, text="💻 Code Submission Analysis",
              command=self.analyze_code_submission).pack(fill='x')

    # Image upload
    upload_frame = ttk.Frame(multimodal_card)
    upload_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(upload_frame, text="📤 Upload Images",
              command=self.upload_images_for_analysis).pack()


def create_multi_modal_analysis_view(self, parent):
    """Create multi-modal analysis tab - MISSING"""
    multimodal_frame = ttk.Frame(parent)

    multimodal_frame.pack(fill="both", expand=True)

    # Multi-modal card
    multimodal_card = ttk.Frame(multimodal_frame, style='Card.TFrame')
    multimodal_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(multimodal_card, text="Multi-Modal Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Image upload section
    image_frame = ttk.LabelFrame(multimodal_card, text="Image Analysis", padding=15)
    image_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(image_frame, text="📁 Upload Images",
              command=self.upload_images_for_analysis).pack(side='left', padx=(0, 10))
    ttk.Button(image_frame, text="📝 Analyze Image-Text Consistency",
              command=self.analyze_image_text_consistency).pack(side='left')

    # Code analysis section
    code_frame = ttk.LabelFrame(multimodal_card, text="Code Analysis", padding=15)
    code_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(code_frame, text="Programming Language:").pack(side='left')
    self.code_language_var = tk.StringVar(value="python")
    language_combo = ttk.Combobox(code_frame, textvariable=self.code_language_var,
                                 values=["python", "java", "javascript", "cpp", "c"], width=15)
    language_combo.pack(side='left', padx=(5, 15))

    ttk.Button(code_frame, text="💻 Analyze Code",
              command=self.analyze_code_submission).pack(side='right')

    # Code input area
    ttk.Label(multimodal_card, text="Code to Analyze:", style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=(10, 5))

    self.code_input = scrolledtext.ScrolledText(
        multimodal_card, wrap=tk.WORD, height=15,
        bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
    )
    self.code_input.pack(fill='both', expand=True, padx=15, pady=(0, 15))


def upload_images_for_analysis(self):
    """Upload images for multi-modal analysis"""
    file_paths = filedialog.askopenfilenames(
        title="Select images for analysis",
        filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")]
    )

    if file_paths:
        self.uploaded_images = []
        try:
            for file_path in file_paths:
                with open(file_path, 'rb') as f:
                    self.uploaded_images.append(f.read())

            messagebox.showinfo("Success", f"Uploaded {len(file_paths)} images for analysis")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to upload images: {str(e)}")


def analyze_image_text_consistency(self):
    """Analyze consistency between uploaded images and text"""
    if not hasattr(self, 'uploaded_images') or not self.uploaded_images:
        messagebox.showwarning("Warning", "Please upload images first")
        return

    text = self.text_input.get('1.0', tk.END).strip()
    if not text:
        messagebox.showwarning("Warning", "Please enter text for comparison")
        return

    try:
        if hasattr(self.detector, 'multimodal_analyzer'):
            result = self.detector.multimodal_analyzer.analyze_image_text_consistency(text, self.uploaded_images)
            self.show_multimodal_results(result)
        else:
            messagebox.showwarning("Warning", "Multi-modal analysis not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to analyze image-text consistency: {str(e)}")


def analyze_code_submission(self):
    """Analyze code submission"""
    code = self.code_input.get('1.0', tk.END).strip()
    language = self.code_language_var.get()

    if not code:
        messagebox.showwarning("Warning", "Please enter code to analyze")
        return

    try:
        if hasattr(self.detector, 'multimodal_analyzer'):
            result = self.detector.multimodal_analyzer.analyze_code_submission(code, language)
            self.show_code_analysis_results(result)
        else:
            messagebox.showwarning("Warning", "Code analysis not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to analyze code: {str(e)}")


def show_multimodal_results(self, result):
    """Show multi-modal analysis results"""
    results_window = tk.Toplevel(self.root)
    results_window.title("Multi-Modal Analysis Results")
    results_window.geometry("700x500")
    results_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(results_window, text="Image-Text Consistency Analysis", style='Title.TLabel').pack(pady=20)

    # Results display
    if hasattr(result, '__dict__'):
        score = result.score
        evidence = result.evidence

        results_frame = ttk.Frame(results_window, style='Card.TFrame')
        results_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(results_frame, text=f"Consistency Score: {score:.1%}",
                 font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)

        if evidence:
            ttk.Label(results_frame, text="Analysis Details:",
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(10, 5))
            for key, value in evidence.items():
                ttk.Label(results_frame, text=f"  {key}: {value}").pack(anchor='w', padx=25, pady=2)


def show_code_analysis_results(self, result):
    """Show code analysis results"""
    results_window = tk.Toplevel(self.root)
    results_window.title("Code Analysis Results")
    results_window.geometry("700x500")
    results_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(results_window, text="Code Analysis Results", style='Title.TLabel').pack(pady=20)

    # Results display
    if hasattr(result, '__dict__'):
        score = result.score
        evidence = result.evidence

        results_frame = ttk.Frame(results_window, style='Card.TFrame')
        results_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(results_frame, text=f"AI Generation Score: {score:.1%}",
                 font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)

        if evidence:
            ttk.Label(results_frame, text="Patterns Found:",
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(10, 5))

            patterns_found = evidence.get('patterns_found', [])
            for pattern in patterns_found:
                ttk.Label(results_frame, text=f"  • {pattern}").pack(anchor='w', padx=25, pady=2)


def create_citation_verification_tab(self):
    """Create citation verification tab"""
    citation_frame = ttk.Frame(self.notebook)
    self.notebook.add(citation_frame, text="📚 Citations")

    # Citation verification card
    citation_card = ttk.Frame(citation_frame, style='Card.TFrame')
    citation_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(citation_card, text="Citation Verification", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Text input for citation checking
    input_frame = ttk.LabelFrame(citation_card, text="Enter Text with Citations", padding=15)
    input_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    import scrolledtext
    self.citation_text = scrolledtext.ScrolledText(input_frame, height=10, wrap=tk.WORD)
    self.citation_text.pack(fill='both', expand=True)

    # Verify button
    ttk.Button(citation_card, text="Verify Citations",
              command=self.verify_citations).pack(pady=15)

    # Results
    self.citation_results_frame = ttk.Frame(citation_card)
    self.citation_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))


def create_citation_verification_view(self, parent):
    """Create citation verification tab - MISSING"""
    citation_frame = ttk.Frame(parent)

    citation_frame.pack(fill="both", expand=True)

    # Citation verification card
    citation_card = ttk.Frame(citation_frame, style='Card.TFrame')
    citation_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(citation_card, text="Citation Verification", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Text input for citation verification
    ttk.Label(citation_card, text="Text with Citations:", style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=(10, 5))

    self.citation_text = scrolledtext.ScrolledText(
        citation_card, wrap=tk.WORD, height=12,
        bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
    )
    self.citation_text.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    # Sample text with citations
    sample_citation_text = """
    According to recent research (Smith et al., 2023), artificial intelligence has shown remarkable progress.
    The study published in Nature (doi:10.1038/nature12345) demonstrates significant findings.
    However, some sources suggest different conclusions [Johnson, 2024].
    """
    self.citation_text.insert('1.0', sample_citation_text.strip())

    # Verification options
    options_frame = ttk.Frame(citation_card)
    options_frame.pack(fill='x', padx=15, pady=(0, 15))

    self.verify_dois_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(options_frame, text="Verify DOIs", variable=self.verify_dois_var).pack(side='left')

    self.check_dates_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(options_frame, text="Check Publication Dates", variable=self.check_dates_var).pack(side='left', padx=(15, 0))

    # Verify button
    ttk.Button(citation_card, text="🔍 Verify Citations",
              command=self.verify_citations, style='Accent.TButton').pack(pady=(0, 15))


def verify_citations(self):
    """Verify citations in text"""
    text = self.citation_text.get('1.0', tk.END).strip()
    if not text:
        messagebox.showwarning("Warning", "Please enter text with citations")
        return

    try:
        if hasattr(self.detector, 'citation_verifier'):
            result = self.detector.citation_verifier.verify_citations(text)
            self.show_citation_results(result)
        else:
            messagebox.showwarning("Warning", "Citation verification not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to verify citations: {str(e)}")


def show_citation_results(self, result):
    """Show citation verification results"""
    results_window = tk.Toplevel(self.root)
    results_window.title("Citation Verification Results")
    results_window.geometry("800x600")
    results_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(results_window, text="Citation Verification Results", style='Title.TLabel').pack(pady=20)

    # Create scrollable frame
    canvas = tk.Canvas(results_window, bg=self.colors['bg_primary'])
    scrollbar = ttk.Scrollbar(results_window, orient='vertical', command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Results content
    if hasattr(result, '__dict__'):
        score = result.score
        evidence = result.evidence

        # Summary
        summary_frame = ttk.Frame(scrollable_frame, style='Card.TFrame')
        summary_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(summary_frame, text=f"Suspicious Citation Score: {score:.1%}",
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=15)

        # Citation details
        if evidence and 'citation_details' in evidence:
            details_frame = ttk.LabelFrame(scrollable_frame, text="Citation Details", padding=15)
            details_frame.pack(fill='x', padx=20, pady=10)

            for i, citation_detail in enumerate(evidence['citation_details'], 1):
                citation_frame = ttk.Frame(details_frame, style='Card.TFrame')
                citation_frame.pack(fill='x', pady=5)

                citation_text = citation_detail.get('citation', 'Unknown')
                exists = citation_detail.get('exists', False)
                suspicious = citation_detail.get('suspicious', False)

                status_color = self.colors['success'] if exists and not suspicious else self.colors['danger']
                status_text = "✓ Valid" if exists and not suspicious else "⚠ Suspicious"

                ttk.Label(citation_frame, text=f"{i}. {citation_text}",
                         font=('Segoe UI', 10)).pack(anchor='w', padx=10, pady=5)

                status_label = tk.Label(citation_frame, text=status_text,
                                      fg=status_color, bg=self.colors['bg_tertiary'])
                status_label.pack(anchor='w', padx=20, pady=(0, 5))

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")


def create_temporal_analysis_tab(self):
    """Create temporal analysis tab"""
    temporal_frame = ttk.Frame(self.notebook)
    self.notebook.add(temporal_frame, text="⏱️ Temporal")

    # Temporal analysis card
    temporal_card = ttk.Frame(temporal_frame, style='Card.TFrame')
    temporal_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(temporal_card, text="Temporal Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Analysis options
    options_frame = ttk.LabelFrame(temporal_card, text="Analysis Options", padding=15)
    options_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(options_frame, text="📅 Submission Patterns",
              command=self.show_submission_patterns).pack(fill='x', pady=(0, 5))
    ttk.Button(options_frame, text="⚡ Writing Speed Analysis",
              command=self.analyze_writing_speed).pack(fill='x')


def create_temporal_analysis_view(self, parent):
    """Create temporal analysis tab - MISSING"""
    temporal_frame = ttk.Frame(parent)

    temporal_frame.pack(fill="both", expand=True)

    # Temporal analysis card
    temporal_card = ttk.Frame(temporal_frame, style='Card.TFrame')
    temporal_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(temporal_card, text="Temporal Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Writing speed analysis
    speed_frame = ttk.LabelFrame(temporal_card, text="Writing Speed Analysis", padding=15)
    speed_frame.pack(fill='x', padx=15, pady=(0, 15))

    # Input fields
    input_frame = ttk.Frame(speed_frame)
    input_frame.pack(fill='x')

    ttk.Label(input_frame, text="Time taken (minutes):").pack(side='left')
    self.time_taken_var = tk.StringVar()
    ttk.Entry(input_frame, textvariable=self.time_taken_var, width=10).pack(side='left', padx=(5, 15))

    ttk.Label(input_frame, text="Word count:").pack(side='left')
    self.word_count_display = ttk.Label(input_frame, text="0")
    self.word_count_display.pack(side='left', padx=(5, 15))

    ttk.Button(input_frame, text="📊 Analyze Writing Speed",
              command=self.analyze_writing_speed).pack(side='right')

    # Student submission patterns
    patterns_frame = ttk.LabelFrame(temporal_card, text="Submission Patterns", padding=15)
    patterns_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(patterns_frame, text="Student ID:").pack(side='left')
    self.temporal_student_var = tk.StringVar()
    ttk.Entry(patterns_frame, textvariable=self.temporal_student_var, width=20).pack(side='left', padx=(5, 15))

    ttk.Button(patterns_frame, text="📈 Analyze Patterns",
              command=self.analyze_submission_patterns).pack(side='right')

    # Results display
    self.temporal_results_frame = ttk.Frame(temporal_card)
    self.temporal_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))


def analyze_writing_speed(self):
    """Analyze writing speed"""
    try:
        time_taken_str = self.time_taken_var.get()
        if not time_taken_str:
            messagebox.showwarning("Warning", "Please enter time taken")
            return

        time_taken_minutes = float(time_taken_str)
        time_taken_seconds = int(time_taken_minutes * 60)

        text = self.text_input.get('1.0', tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter text in the main analysis tab")
            return

        if hasattr(self.detector, 'temporal_analyzer'):
            result = self.detector.temporal_analyzer.analyze_writing_speed(text, time_taken_seconds)
            self.show_temporal_results(result)
        else:
            messagebox.showwarning("Warning", "Temporal analysis not available")
    except ValueError:
        messagebox.showerror("Error", "Please enter a valid number for time taken")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to analyze writing speed: {str(e)}")


def analyze_submission_patterns(self):
    """Analyze student submission patterns"""
    student_id = self.temporal_student_var.get()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a Student ID")
        return

    try:
        if hasattr(self.detector, 'temporal_analyzer'):
            patterns = self.detector.temporal_analyzer.analyze_submission_patterns(student_id)
            self.show_submission_patterns(patterns)
        else:
            messagebox.showwarning("Warning", "Temporal analysis not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to analyze patterns: {str(e)}")


def show_temporal_results(self, result):
    """Show temporal analysis results"""
    # Clear previous results
    for widget in self.temporal_results_frame.winfo_children():
        widget.destroy()

    results_frame = ttk.Frame(self.temporal_results_frame, style='Card.TFrame')
    results_frame.pack(fill='x', pady=10)

    if hasattr(result, '__dict__'):
        score = result.score
        evidence = result.evidence
        risk_level = result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level)

        ttk.Label(results_frame, text="Writing Speed Analysis Results",
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))

        ttk.Label(results_frame, text=f"Anomaly Score: {score:.1%}").pack(anchor='w', padx=15, pady=2)
        ttk.Label(results_frame, text=f"Risk Level: {risk_level}").pack(anchor='w', padx=15, pady=2)

        if evidence:
            wpm = evidence.get('words_per_minute', 0)
            complexity = evidence.get('complexity_score', 0)
            ttk.Label(results_frame, text=f"Words per minute: {wpm:.1f}").pack(anchor='w', padx=15, pady=2)
            ttk.Label(results_frame, text=f"Text complexity: {complexity:.2f}").pack(anchor='w', padx=15, pady=2)

            if 'anomaly' in evidence:
                ttk.Label(results_frame, text=f"Issue: {evidence['anomaly']}",
                         foreground=self.colors['warning']).pack(anchor='w', padx=15, pady=5)


def show_submission_patterns(self, patterns):
    """Show submission pattern analysis"""
    # Clear previous results
    for widget in self.temporal_results_frame.winfo_children():
        widget.destroy()

    patterns_frame = ttk.Frame(self.temporal_results_frame, style='Card.TFrame')
    patterns_frame.pack(fill='x', pady=10)

    ttk.Label(patterns_frame, text="Submission Patterns Analysis",
             font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))

    if 'error' in patterns:
        ttk.Label(patterns_frame, text=f"Error: {patterns['error']}",
                 foreground=self.colors['danger']).pack(anchor='w', padx=15, pady=5)
    elif 'insufficient_data' in patterns:
        ttk.Label(patterns_frame, text="Insufficient data for pattern analysis",
                 style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=5)
    else:
        # Display pattern metrics
        total_submissions = patterns.get('total_submissions', 0)
        suspicious_ratio = patterns.get('suspicious_hour_ratio', 0)
        regular_intervals = patterns.get('regular_interval_count', 0)
        avg_hour = patterns.get('avg_hour', 12)

        ttk.Label(patterns_frame, text=f"Total Submissions: {total_submissions}").pack(anchor='w', padx=15, pady=2)
        ttk.Label(patterns_frame, text=f"Average Submission Hour: {avg_hour:.1f}").pack(anchor='w', padx=15, pady=2)
        ttk.Label(patterns_frame, text=f"Late Night Submissions: {suspicious_ratio:.1%}").pack(anchor='w', padx=15, pady=2)
        ttk.Label(patterns_frame, text=f"Regular 24h Intervals: {regular_intervals}").pack(anchor='w', padx=15, pady=2)

        # Warnings for suspicious patterns
        if suspicious_ratio > 0.3:
            ttk.Label(patterns_frame, text="Warning: High frequency of late-night submissions",
                     foreground=self.colors['warning']).pack(anchor='w', padx=15, pady=5)
        if regular_intervals > 3:
            ttk.Label(patterns_frame, text="Warning: Unusually regular submission intervals",
                     foreground=self.colors['warning']).pack(anchor='w', padx=15, pady=5)



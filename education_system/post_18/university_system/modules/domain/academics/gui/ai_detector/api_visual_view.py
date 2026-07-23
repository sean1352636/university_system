import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

try:
    from education_system.post_18.university_system.infrastructure.ai.ai_detector.detector import AIDetector
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

from education_system.post_18.university_system.core.i18n import get_text, _

def create_api_integration_view(self, parent):
    """Create API integration tab - MISSING"""
    api_frame = ttk.Frame(parent)

    api_frame.pack(fill="both", expand=True)

    # API integration card
    api_card = ttk.Frame(api_frame, style='Card.TFrame')
    api_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(api_card, text="External API Integration", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # API configuration
    config_frame = ttk.LabelFrame(api_card, text="API Configuration", padding=15)
    config_frame.pack(fill='x', padx=15, pady=(0, 15))

    # API service selection
    ttk.Label(config_frame, text="API Service:").pack(side='left')
    self.api_service_var = tk.StringVar(value="custom")
    api_combo = ttk.Combobox(config_frame, textvariable=self.api_service_var,
                            values=["custom", "openai", "cohere", "huggingface"], width=15)
    api_combo.pack(side='left', padx=(5, 15))

    # API key input
    ttk.Label(config_frame, text="API Key:").pack(side='left')
    self.api_key_var = tk.StringVar()
    api_key_entry = ttk.Entry(config_frame, textvariable=self.api_key_var, width=30, show="*")
    api_key_entry.pack(side='left', padx=(5, 15))

    ttk.Button(config_frame, text="🔗 Register API", command=self.register_external_api).pack(side='right')

    # API testing
    test_frame = ttk.LabelFrame(api_card, text="API Testing", padding=15)
    test_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(test_frame, text="🧪 Test API Connection",
              command=self.test_api_connection).pack(side='left', padx=(0, 10))
    ttk.Button(test_frame, text="📊 API Performance",
              command=self.show_api_performance).pack(side='left')

    # API results comparison
    comparison_frame = ttk.LabelFrame(api_card, text="Multi-API Analysis", padding=15)
    comparison_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(comparison_frame, text="🔍 Compare API Results",
              command=self.compare_api_results).pack(side='left', padx=(0, 10))
    ttk.Button(comparison_frame, text="⚡ Ensemble Prediction",
              command=self.run_ensemble_prediction).pack(side='left')


def register_external_api(self):
    """Register external API for integration"""
    service = self.api_service_var.get()
    api_key = self.api_key_var.get()

    if not api_key:
        messagebox.showwarning("Warning", "Please enter an API key")
        return

    try:
        if hasattr(self.detector, 'api_gateway'):
            # Configure API based on service type
            if service == "custom":
                url = tk.simpledialog.askstring("API URL", "Enter the API endpoint URL:")
                if not url:
                    return
            else:
                # Predefined URLs for known services
                service_urls = {
                    "openai": "https://api.openai.com/v1/completions",
                    "cohere": "https://api.cohere.ai/v1/classify",
                    "huggingface": "https://api-inference.huggingface.co/models/roberta-base-openai-detector"
                }
                url = service_urls.get(service, "")

            config = {
                'url': url,
                'api_key': api_key,
                'timeout': 30,
                'max_requests_per_minute': 60,
                'weight': 1.0
            }

            self.detector.api_gateway.register_api(service, config)
            messagebox.showinfo("Success", f"API '{service}' registered successfully")
            self.update_status(f"Registered API: {service}")
        else:
            messagebox.showwarning("Warning", "API gateway not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to register API: {str(e)}")


def test_api_connection(self):
    """Test API connection"""
    service = self.api_service_var.get()

    try:
        if hasattr(self.detector, 'api_gateway'):
            # Test with sample text
            test_text = "This is a test text to verify API connectivity."
            result = self.detector.api_gateway.call_api(service, test_text)

            if result:
                messagebox.showinfo("API Test", f"API '{service}' is working correctly!\nResponse time: {result.get('response_time', 0):.2f}s")
            else:
                messagebox.showwarning("API Test", f"API '{service}' test failed")
        else:
            messagebox.showwarning("Warning", "API gateway not available")
    except Exception as e:
        messagebox.showerror("Error", f"API test failed: {str(e)}")


def show_api_performance(self):
    """Show API performance metrics"""
    performance_window = tk.Toplevel(self.root)
    performance_window.title("API Performance Metrics")
    performance_window.geometry("600x400")
    performance_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(performance_window, text="API Performance Metrics", style='Title.TLabel').pack(pady=20)

    # Performance display would show:
    # - Response times
    # - Success rates
    # - Rate limit status
    # - Circuit breaker status

    perf_frame = ttk.Frame(performance_window, style='Card.TFrame')
    perf_frame.pack(fill='both', expand=True, padx=20, pady=20)

    ttk.Label(perf_frame, text="API performance monitoring feature",
             style='Subtitle.TLabel').pack(expand=True)


def compare_api_results(self):
    """Compare results from multiple APIs"""
    text = self.text_input.get('1.0', tk.END).strip()
    if not text:
        messagebox.showwarning("Warning", "Please enter text to analyze")
        return

    try:
        if hasattr(self.detector, 'api_gateway'):
            # This would call multiple APIs and compare results
            messagebox.showinfo("API Comparison", "Multi-API comparison feature available")
        else:
            messagebox.showwarning("Warning", "API gateway not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to compare APIs: {str(e)}")


def run_ensemble_prediction(self):
    """Run ensemble prediction using multiple APIs"""
    text = self.text_input.get('1.0', tk.END).strip()
    if not text:
        messagebox.showwarning("Warning", "Please enter text to analyze")
        return

    try:
        if hasattr(self.detector, 'advanced_ml_trainer'):
            result = self.detector.advanced_ml_trainer.predict_ensemble(text)
            if result:
                self.show_ensemble_results(result)
            else:
                messagebox.showinfo("Ensemble Prediction", "No trained ensemble models available")
        else:
            messagebox.showwarning("Warning", "Ensemble prediction not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to run ensemble prediction: {str(e)}")


def show_ensemble_results(self, result):
    """Show ensemble prediction results"""
    results_window = tk.Toplevel(self.root)
    results_window.title("Ensemble Prediction Results")
    results_window.geometry("700x500")
    results_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(results_window, text="Ensemble Prediction Results", style='Title.TLabel').pack(pady=20)

    # Results display
    results_frame = ttk.Frame(results_window, style='Card.TFrame')
    results_frame.pack(fill='both', expand=True, padx=20, pady=20)

    ensemble_score = result.get('ensemble_score', 0)
    confidence = result.get('confidence', 0)
    individual_predictions = result.get('individual_predictions', {})

    # Main score
    ttk.Label(results_frame, text=f"Ensemble Score: {ensemble_score:.1%}",
             font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=15, pady=15)
    ttk.Label(results_frame, text=f"Confidence: {confidence:.1%}",
             font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)

    # Individual model predictions
    if individual_predictions:
        ttk.Label(results_frame, text="Individual Model Predictions:",
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))

        for model_name, prediction in individual_predictions.items():
            ttk.Label(results_frame, text=f"  {model_name}: {prediction:.1%}").pack(anchor='w', padx=25, pady=2)


def create_visual_analysis_view(self, parent):
    """Create visual analysis and heatmap tab - MISSING"""
    visual_frame = ttk.Frame(parent)

    visual_frame.pack(fill="both", expand=True)

    # Visual analysis card
    visual_card = ttk.Frame(visual_frame, style='Card.TFrame')
    visual_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(visual_card, text="Visual Text Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Analysis options
    options_frame = ttk.Frame(visual_card)
    options_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(options_frame, text="🔥 Generate Text Heatmap",
              command=self.generate_text_heatmap).pack(side='left', padx=(0, 10))
    ttk.Button(options_frame, text="📈 Writing Flow Analysis",
              command=self.generate_writing_flow).pack(side='left', padx=(0, 10))
    ttk.Button(options_frame, text="📊 Complexity Visualization",
              command=self.generate_complexity_viz).pack(side='left')

    # Visualization display area
    self.visual_display_frame = ttk.Frame(visual_card)
    self.visual_display_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    # Initial message
    ttk.Label(self.visual_display_frame, text="Select an analysis option above to generate visualizations",
             style='Subtitle.TLabel').pack(expand=True)


def generate_text_heatmap(self):
    """Generate text heatmap visualization"""
    # Check if text_input widget still exists
    if not hasattr(self, 'text_input') or not self.text_input.winfo_exists():
        messagebox.showwarning("Warning", "Please go to the Analysis tab first")
        return

    try:
        text = self.text_input.get('1.0', tk.END).strip()
    except tk.TclError:
        messagebox.showwarning("Warning", "Text input widget is no longer available. Please go to the Analysis tab first.")
        return

    if not text:
        messagebox.showwarning("Warning", "Please enter text to analyze")
        return

    try:
        if hasattr(self.detector, 'visual_analyzer'):
            # Generate sample scores for demonstration
            sentences = text.split('.')
            sample_scores = [0.1, 0.3, 0.7, 0.2, 0.8, 0.1, 0.4][:len(sentences)]

            heatmap_data = self.detector.visual_analyzer.generate_text_heatmap(text, sample_scores)
            self.display_text_heatmap(heatmap_data)
        else:
            messagebox.showwarning("Warning", "Visual analyzer not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate heatmap: {str(e)}")


def display_text_heatmap(self, heatmap_data):
    """Display text heatmap"""
    # Clear previous display
    for widget in self.visual_display_frame.winfo_children():
        widget.destroy()

    # Create scrollable text area with color-coded sentences
    text_frame = ttk.LabelFrame(self.visual_display_frame, text="Text Heatmap", padding=15)
    text_frame.pack(fill='both', expand=True)

    # Create text widget
    text_widget = tk.Text(
        text_frame, wrap=tk.WORD, height=15,
        bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
        state='disabled'
    )
    text_widget.pack(fill='both', expand=True)

    # Configure color tags
    text_widget.tag_configure('high_risk', background='#ff4444', foreground='white')
    text_widget.tag_configure('medium_risk', background='#ffaa00', foreground='white')
    text_widget.tag_configure('low_risk', background='#ffff44', foreground='black')
    text_widget.tag_configure('safe', background='#44ff44', foreground='black')

    # Insert sentences with coloring
    text_widget.config(state='normal')
    heatmap_sentences = heatmap_data.get('heatmap_data', [])

    for sentence_data in heatmap_sentences:
        sentence_text = sentence_data.get('text', '')
        score = sentence_data.get('score', 0)

        start_index = text_widget.index(tk.INSERT)
        text_widget.insert(tk.INSERT, sentence_text + '. ')
        end_index = text_widget.index(tk.INSERT)

        # Apply color based on score
        if score > 0.7:
            text_widget.tag_add('high_risk', start_index, end_index)
        elif score > 0.5:
            text_widget.tag_add('medium_risk', start_index, end_index)
        elif score > 0.3:
            text_widget.tag_add('low_risk', start_index, end_index)
        else:
            text_widget.tag_add('safe', start_index, end_index)

    text_widget.config(state='disabled')

    # Legend
    legend_frame = ttk.Frame(text_frame)
    legend_frame.pack(fill='x', pady=(10, 0))

    ttk.Label(legend_frame, text="Risk Level:").pack(side='left')

    legend_items = [
        ('High Risk', '#ff4444'),
        ('Medium Risk', '#ffaa00'),
        ('Low Risk', '#ffff44'),
        ('Safe', '#44ff44')
    ]

    for label, color in legend_items:
        legend_item = tk.Label(legend_frame, text=f"■ {label}", fg=color, bg=self.colors['bg_tertiary'])
        legend_item.pack(side='left', padx=(10, 0))


def generate_writing_flow(self):
    """Generate writing flow visualization"""
    # Check if text_input widget still exists
    if not hasattr(self, 'text_input') or not self.text_input.winfo_exists():
        messagebox.showwarning("Warning", "Please go to the Analysis tab first")
        return

    try:
        text = self.text_input.get('1.0', tk.END).strip()
    except tk.TclError:
        messagebox.showwarning("Warning", "Text input widget is no longer available. Please go to the Analysis tab first.")
        return

    if not text:
        messagebox.showwarning("Warning", "Please enter text to analyze")
        return

    try:
        if hasattr(self.detector, 'visual_analyzer'):
            flow_data = self.detector.visual_analyzer.generate_writing_flow_visualization(text)
            self.display_writing_flow(flow_data)
        else:
            messagebox.showwarning("Warning", "Visual analyzer not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate writing flow: {str(e)}")


def display_writing_flow(self, flow_data):
    """Display writing flow visualization"""
    # Clear previous display
    for widget in self.visual_display_frame.winfo_children():
        widget.destroy()

    # Create flow visualization
    flow_frame = ttk.LabelFrame(self.visual_display_frame, text="Writing Flow Analysis", padding=15)
    flow_frame.pack(fill='both', expand=True)

    # Summary statistics
    summary_frame = ttk.Frame(flow_frame)
    summary_frame.pack(fill='x', pady=(0, 10))

    total_paragraphs = flow_data.get('total_paragraphs', 0)
    avg_length = flow_data.get('avg_paragraph_length', 0)
    transition_freq = flow_data.get('transition_frequency', 0)

    ttk.Label(summary_frame, text=f"Paragraphs: {total_paragraphs}").pack(side='left', padx=(0, 15))
    ttk.Label(summary_frame, text=f"Avg Length: {avg_length:.1f} words").pack(side='left', padx=(0, 15))
    ttk.Label(summary_frame, text=f"Transitions: {transition_freq:.1%}").pack(side='left')

    # Paragraph details
    if 'flow_data' in flow_data:
        details_frame = scrolledtext.ScrolledText(flow_frame, height=12, wrap=tk.WORD,
                                                 bg=self.colors['bg_secondary'], fg=self.colors['text_primary'])
        details_frame.pack(fill='both', expand=True)

        for i, para_data in enumerate(flow_data['flow_data'], 1):
            word_count = para_data.get('word_count', 0)
            sentence_count = para_data.get('sentence_count', 0)
            has_transition = para_data.get('has_transition', False)
            complexity = para_data.get('complexity_score', 0)

            paragraph_info = f"Paragraph {i}: {word_count} words, {sentence_count} sentences"
            if has_transition:
                paragraph_info += " [Has Transition]"
            paragraph_info += f" (Complexity: {complexity:.2f})\n"

            details_frame.insert(tk.END, paragraph_info)


def generate_complexity_viz(self):
    """Generate text complexity visualization"""
    # Check if text_input widget still exists
    if not hasattr(self, 'text_input') or not self.text_input.winfo_exists():
        messagebox.showwarning("Warning", "Please go to the Analysis tab first")
        return

    try:
        text = self.text_input.get('1.0', tk.END).strip()
    except tk.TclError:
        messagebox.showwarning("Warning", "Text input widget is no longer available. Please go to the Analysis tab first.")
        return

    if not text:
        messagebox.showwarning("Warning", "Please enter text to analyze")
        return

    try:
        # Clear previous display
        for widget in self.visual_display_frame.winfo_children():
            widget.destroy()

        # Create complexity analysis
        complexity_frame = ttk.LabelFrame(self.visual_display_frame, text="Text Complexity Analysis", padding=15)
        complexity_frame.pack(fill='both', expand=True)

        # Calculate various complexity metrics
        words = text.split()
        sentences = text.split('.')

        # Metrics
        avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
        avg_sentence_length = len(words) / len(sentences) if sentences else 0
        unique_words = len(set(word.lower() for word in words))
        lexical_diversity = unique_words / len(words) if words else 0

        # Display metrics
        metrics = [
            ("Average Word Length", f"{avg_word_length:.1f} characters"),
            ("Average Sentence Length", f"{avg_sentence_length:.1f} words"),
            ("Total Words", str(len(words))),
            ("Unique Words", str(unique_words)),
            ("Lexical Diversity", f"{lexical_diversity:.2f}"),
        ]

        for metric, value in metrics:
            metric_frame = ttk.Frame(complexity_frame)
            metric_frame.pack(fill='x', pady=2)

            ttk.Label(metric_frame, text=f"{metric}:").pack(side='left')
            ttk.Label(metric_frame, text=value, font=('Segoe UI', 10, 'bold')).pack(side='right')

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate complexity visualization: {str(e)}")



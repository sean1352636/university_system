import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

try:
    from university_system.utils.ai.ai_detector.detector import AIDetector
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

from university_system.modules.shared.utils.i18n import get_text, _

def create_statistics_view(self, parent):
    """Create statistics and dashboard tab"""
    stats_frame = ttk.Frame(parent)

    stats_frame.pack(fill="both", expand=True)

    # Create scrollable frame
    canvas = tk.Canvas(stats_frame, bg=self.colors['bg_primary'])
    scrollbar = ttk.Scrollbar(stats_frame, orient='vertical', command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Statistics cards
    self.create_stats_cards(scrollable_frame)
    self.create_charts_section(scrollable_frame)

    # Pack canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Bind mousewheel to canvas
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)


def create_stats_cards(self, parent):
    """Create statistics cards"""
    cards_frame = ttk.Frame(parent)

    cards_frame.pack(fill="both", expand=True)
    cards_frame.pack(fill='x', padx=10, pady=10)

    # Row 1: Main statistics
    row1 = ttk.Frame(cards_frame)
    row1.pack(fill='x', pady=(0, 10))

    self.stats_cards = {}

    # Total submissions card
    self.stats_cards['total'] = self.create_stat_card(row1, get_text("ai_detector.stats.total_submissions"), "0", "📄")
    self.stats_cards['total'].pack(side='left', fill='x', expand=True, padx=(0, 5))

    # Unique students card
    self.stats_cards['students'] = self.create_stat_card(row1, get_text("ai_detector.stats.unique_students"), "0", "👥")
    self.stats_cards['students'].pack(side='left', fill='x', expand=True, padx=5)

    # Average AI score card
    self.stats_cards['avg_score'] = self.create_stat_card(row1, get_text("ai_detector.stats.avg_ai_score"), "0.000", "🎯")
    self.stats_cards['avg_score'].pack(side='left', fill='x', expand=True, padx=5)

    # High risk submissions card
    self.stats_cards['high_risk'] = self.create_stat_card(row1, get_text("ai_detector.stats.high_risk"), "0", "⚠️")
    self.stats_cards['high_risk'].pack(side='left', fill='x', expand=True, padx=(5, 0))


def create_stat_card(self, parent, title, value, icon):
    """Create individual statistic card"""
    card = ttk.Frame(parent, style='Card.TFrame')

    # Icon and title
    header_frame = ttk.Frame(card)
    header_frame.pack(fill='x', padx=15, pady=(15, 5))

    ttk.Label(header_frame, text=icon, font=('Segoe UI', 16)).pack(side='left')
    ttk.Label(header_frame, text=title, style='Subtitle.TLabel').pack(side='left', padx=(10, 0))

    # Value
    value_label = ttk.Label(card, text=value, font=('Segoe UI', 24, 'bold'))
    value_label.pack(padx=15, pady=(0, 15))

    # Store value label for updates
    card.value_label = value_label

    return card


def create_charts_section(self, parent):
    """Create charts section"""
    charts_frame = ttk.Frame(parent, style='Card.TFrame')
    charts_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

    ttk.Label(charts_frame, text=get_text("ai_detector.analytics_dashboard"), style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Chart container
    self.chart_container = ttk.Frame(charts_frame)
    self.chart_container.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    # Create initial charts
    self.create_risk_distribution_chart()


def create_risk_distribution_chart(self):
    """Create risk distribution pie chart"""
    try:
        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.patch.set_facecolor(self.colors['bg_tertiary'])
        ax.set_facecolor(self.colors['bg_tertiary'])

        # Sample data (replace with real data)
        risk_levels = [get_text("ai_detector.risk.low"), get_text("ai_detector.risk.medium"), get_text("ai_detector.risk.high"), get_text("ai_detector.risk.critical")]
        counts = [70, 20, 8, 2]  # Sample percentages
        colors = [self.colors['success'], self.colors['warning'], self.colors['danger'], '#8B0000']

        # Create pie chart
        wedges, texts, autotexts = ax.pie(counts, labels=risk_levels, colors=colors, autopct='%1.1f%%',
                                        textprops={'color': self.colors['text_primary']})

        ax.set_title(get_text("ai_detector.risk_distribution"), color=self.colors['text_primary'], fontsize=14, fontweight='bold')

        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, self.chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    except Exception as e:
        # Fallback if matplotlib not available
        fallback_label = ttk.Label(self.chart_container,
                                 text=get_text("ai_detector.charts_require_matplotlib"),
                                 style='Subtitle.TLabel')
        fallback_label.pack(expand=True)


def refresh_statistics(self):
    """Refresh statistics display"""
    try:
        stats = self.detector.get_enhanced_statistics()

        # Update stat cards
        if hasattr(self, 'stats_cards'):
            self.stats_cards['total'].value_label.config(text=str(stats.get('total_submissions', 0)))
            self.stats_cards['students'].value_label.config(text=str(stats.get('unique_students', 0)))
            self.stats_cards['avg_score'].value_label.config(text=f"{stats.get('average_ai_score', 0):.3f}")
            self.stats_cards['high_risk'].value_label.config(text=str(stats.get('high_risk_submissions', 0)))

        # Update info label
        self.info_label.config(text=get_text("ai_detector.db_status", status=stats.get('database_status', get_text("common.unknown"))))

    except Exception as e:
        print(f"Error refreshing statistics: {e}")



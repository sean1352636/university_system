"""Statistics over the readings the signed-in person may see: counts, how
many wait for review, and how the readings are spread across levels (drawn
from the live readings, not sample figures)."""

import logging

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.domains.integrity.interfaces.gui.ai_detector import (
    _common as common,
)

logger = logging.getLogger(__name__)

LEVEL_ORDER = ("not enough text", "not assessed (code)", "few or no indicators",
               "some indicators", "several indicators")


def create_statistics_view(self, parent):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    header = ttk.Frame(frame)
    header.pack(fill="x", padx=15, pady=(15, 6))
    ttk.Label(header, text="Statistics (your modules)", style="Title.TLabel").pack(side="left")
    ttk.Button(header, text="🔄 Refresh", command=self.refresh_statistics).pack(side="right")
    self.create_stats_cards(frame)
    self.create_charts_section(frame)
    self.refresh_statistics()


def create_stats_cards(self, parent):
    row = ttk.Frame(parent)
    row.pack(fill="x", padx=10, pady=6)
    self.stats_cards = {}
    for key, title, icon in (("total", "Readings", "📄"), ("students", "Students", "👥"),
                             ("review", "Wait for review", "⚠️"),
                             ("recent", "Last 7 days", "🗓"),
                             ("not_read", "Not enough text", "✂")):
        card = self.create_stat_card(row, title, "—", icon)
        card.pack(side="left", fill="x", expand=True, padx=4)
        self.stats_cards[key] = card


def create_stat_card(self, parent, title, value, icon):
    card = ttk.Frame(parent, style="Card.TFrame")
    head = ttk.Frame(card)
    head.pack(fill="x", padx=12, pady=(10, 2))
    ttk.Label(head, text=icon, font=("Segoe UI", 14)).pack(side="left")
    ttk.Label(head, text=title, style="Subtitle.TLabel").pack(side="left", padx=6)
    card.value_label = ttk.Label(card, text=value, font=("Segoe UI", 20, "bold"))
    card.value_label.pack(padx=12, pady=(0, 10))
    return card


def create_charts_section(self, parent):
    box = ttk.LabelFrame(parent, text="Readings by level", padding=8)
    box.pack(fill="both", expand=True, padx=10, pady=(6, 10))
    self.chart_container = tk.Canvas(box, height=260, background=self.colors["bg_tertiary"],
                                     highlightthickness=0)
    self.chart_container.pack(fill="both", expand=True)
    self.chart_container.bind("<Configure>", lambda _e: self.create_risk_distribution_chart())


def _levels(self) -> dict:
    data = common.call(self, self.detector.get_submission_history, limit=100000, quiet=True)
    counts: dict = {}
    for s in (data or {}).get("submissions", []):
        level = s.get("level") or "taken before indicators"
        counts[level] = counts.get(level, 0) + 1
    return counts


def create_risk_distribution_chart(self):
    """Bars per level, from the live readings."""
    canvas = self.__dict__.get("chart_container")
    if canvas is None or not canvas.winfo_exists():
        return
    counts = self.__dict__.get("_level_counts")
    if counts is None:
        counts = self._level_counts = _levels(self)
    canvas.delete("all")
    order = [lvl for lvl in LEVEL_ORDER if lvl in counts] + sorted(
        lvl for lvl in counts if lvl not in LEVEL_ORDER)
    if not order:
        canvas.create_text(20, 20, anchor="nw", text="No readings yet.")
        return
    width = max(canvas.winfo_width(), 400)
    height = max(canvas.winfo_height(), 200)
    top = max(counts.values())
    bar_w = max(30, (width - 40) // len(order) - 20)
    colours = {"several indicators": self.colors["danger"],
               "some indicators": self.colors["warning"],
               "few or no indicators": self.colors["success"]}
    for i, level in enumerate(order):
        x0 = 20 + i * (bar_w + 20)
        h = int((height - 70) * counts[level] / top)
        canvas.create_rectangle(x0, height - 40 - h, x0 + bar_w, height - 40,
                                fill=colours.get(level, self.colors["text_secondary"]),
                                outline="")
        canvas.create_text(x0 + bar_w / 2, height - 46 - h, text=str(counts[level]),
                           anchor="s")
        canvas.create_text(x0 + bar_w / 2, height - 34, text=level, anchor="n",
                           width=bar_w + 16, font=("Segoe UI", 8))


def refresh_statistics(self):
    """Reload the counts and the chart."""
    cards = self.__dict__.get("stats_cards")
    if not cards:
        return
    stats = common.call(self, self.detector.get_enhanced_statistics, quiet=True)
    if stats is None:
        return
    for key, value in (("total", stats.get("total_submissions", 0)),
                       ("students", stats.get("unique_students", 0)),
                       ("review", stats.get("needs_review", 0)),
                       ("recent", stats.get("recent_submissions_7_days", 0)),
                       ("not_read", stats.get("not_enough_text", 0))):
        cards[key].value_label.config(text=str(value))
    self.info_label.config(text=f"Review level {stats.get('detection_threshold')}")
    self._level_counts = None
    self.create_risk_distribution_chart()

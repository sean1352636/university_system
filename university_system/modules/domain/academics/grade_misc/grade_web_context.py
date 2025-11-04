"""Shared imports and utilities for grade miscellaneous helpers."""

from __future__ import annotations

import csv
import math
import os
import warnings
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from university_system.infrastructure.database.db import DatabaseManager, get_connection, sqlite3
from university_system.modules.shared.utils.report_palette import get_report_palette
from university_system.modules.domain.academics.grading.common_utilities import select_assessment
try:
    from university_system.modules.domain.academics.grading.grade_calculation import (
        calculate_student_gpa,
        letter_to_gpa,
        compare_by_grade_threshold,
        GRADE_SYSTEMS,
    )
except Exception:  # pragma: no cover - provide minimal fallbacks
    def calculate_student_gpa(*_, **__):
        raise RuntimeError("grade_calculation.calculate_student_gpa is unavailable")

    def letter_to_gpa(*_, **__):
        raise RuntimeError("grade_calculation.letter_to_gpa is unavailable")

    def compare_by_grade_threshold(*_, **__):
        raise RuntimeError("grade_calculation.compare_by_grade_threshold is unavailable")

    GRADE_SYSTEMS = {
        "letter": {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0},
        "percentage": {
            "conversion": {
                (90, 100): "A",
                (80, 89): "B",
                (70, 79): "C",
                (60, 69): "D",
                (0, 59): "F",
            }
        },
    }

warnings.filterwarnings("ignore")

"""Shared imports for the Student Analytics GUI modules."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import sys
from datetime import datetime
import os
import json
import warnings

from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH

try:
    from education_system.post_18.university_system.infrastructure.auth import UserAuth
except ImportError:
    UserAuth = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import matplotlib.pyplot as plt
    import matplotlib
except ImportError:
    plt = None
    matplotlib = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, r2_score
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.naive_bayes import GaussianNB
    from sklearn.decomposition import PCA
except ImportError:
    StandardScaler = None
    KMeans = None
    RandomForestClassifier = None
    RandomForestRegressor = None
    train_test_split = None
    classification_report = None
    r2_score = None
    LogisticRegression = None
    SVC = None
    GaussianNB = None
    PCA = None

try:
    import openpyxl
    from openpyxl.styles import Font, Fill, PatternFill, Alignment
except ImportError:
    openpyxl = None

try:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
except ImportError:
    smtplib = None

try:
    from education_system.post_18.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"

try:
    from education_system.post_18.university_system.modules.shared.services.analytics.student_analytics import StudentAnalytics
except ImportError:
    StudentAnalytics = None

CONFIG = {
    'colors': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b'],
    'figure_size': (15, 10),
    'dpi': 300,
    'export_formats': ['png', 'pdf', 'svg', 'excel'],
    'email_config': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender_email': '',
        'sender_password': ''
    }
}


def configure_matplotlib():
    """Configure matplotlib backend with proper GUI support"""
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        return True
    except Exception:
        try:
            matplotlib.use('Agg')
            return False
        except Exception:
            return False

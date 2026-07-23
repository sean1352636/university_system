from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import csv
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import warnings
import io
import pickle
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score
from threading import Timer
import schedule
import time
from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_by_source_report import (
    print_revenue_by_source_report, revenue_by_source_menu
)
from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import (
    generate_financial_forecasting, generate_budget_variance_report, generate_financial_dashboard as financial_dashboard
)

# Import auth instance management from user_authentication
try:
    from education_system.post_18.university_system.infrastructure.auth import get_current_user, set_auth_instance, UserAuth
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None
    UserAuth = None

auth = None  # Placeholder for global auth variable

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

# Configure plotting style
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")
warnings.filterwarnings('ignore')


def get_current_academic_year():
    """Helper function to get current academic year"""
    current_date = datetime.now()
    if current_date.month >= 9:
        return f"{current_date.year}-{current_date.year + 1}"
    else:
        return f"{current_date.year - 1}-{current_date.year}"

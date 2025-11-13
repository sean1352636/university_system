"""Shared context and heavy imports for finance miscellaneous helpers."""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import json
import logging
import os
from university_system.infrastructure.database.db import sqlite3
import threading
import time
import warnings
from datetime import datetime, timedelta
from io import BytesIO

# Optional imports - make them available if installed
try:
    import joblib
except ImportError:
    joblib = None

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    import requests
except ImportError:
    requests = None

try:
    import schedule
except ImportError:
    schedule = None

try:
    import seaborn as sns
except ImportError:
    sns = None

import smtplib
import ssl

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None

try:
    from flask import Flask, jsonify, request
except ImportError:
    Flask = None
    jsonify = None
    request = None

try:
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib import colors as reportlab_colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:
    VerticalBarChart = None
    Pie = None
    Drawing = None
    reportlab_colors = None
    letter = None
    landscape = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    inch = None
    Image = None
    PageBreak = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
except ImportError:
    IsolationForest = None
    StandardScaler = None

from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.infrastructure.database.db import get_connection
from university_system.infrastructure.email import send_email
from university_system.utils.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings("ignore")

# Shared Flask app for webhook style integrations
app = Flask(__name__) if Flask else None

# Encryption key for sensitive data
if Fernet:
    ENCRYPTION_KEY = Fernet.generate_key()
    cipher_suite = Fernet(ENCRYPTION_KEY)
else:
    ENCRYPTION_KEY = None
    cipher_suite = None

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    "stripe": {
        "public_key": "pk_test_...",
        "secret_key": "sk_test_...",
        "webhook_secret": "whsec_...",
    },
    "paypal": {
        "client_id": "your_paypal_client_id",
        "client_secret": "your_paypal_client_secret",
        "environment": "sandbox",  # or 'live'
    },
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ["GBP", "USD", "EUR", "CAD", "AUD"]
BASE_CURRENCY = "GBP"
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')

# Use centralized auth management
from university_system.infrastructure.shared_context import (
    get_auth,
    set_auth,
    get_current_user,
    check_permission,
)

# Backward compatibility - auth will be initialized lazily
# Don't call get_auth() at module level to avoid warnings
auth = None

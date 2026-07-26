"""Shared context and heavy imports for finance miscellaneous helpers."""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import json
import logging
import os
from education_system.systems.university.infrastructure.database.db import sqlite3
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

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.email import send_email
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings("ignore")

# Shared Flask app for webhook style integrations
app = Flask(__name__) if Flask else None

# Encryption key for sensitive data
if Fernet:
    try:
        _generated_key = Fernet.generate_key()
    except Exception:
        _generated_key = None

    if isinstance(_generated_key, bytes):
        ENCRYPTION_KEY = _generated_key
        try:
            cipher_suite = Fernet(ENCRYPTION_KEY)
        except Exception:
            cipher_suite = None
    else:
        ENCRYPTION_KEY = None
        cipher_suite = None
else:
    ENCRYPTION_KEY = None
    cipher_suite = None

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    "stripe": {
        "public_key": os.getenv('STRIPE_PUBLIC_KEY', ''),
        "secret_key": os.getenv('STRIPE_SECRET_KEY', ''),
        "webhook_secret": os.getenv('STRIPE_WEBHOOK_SECRET', ''),
    },
    "paypal": {
        "client_id": os.getenv('PAYPAL_CLIENT_ID', ''),
        "client_secret": os.getenv('PAYPAL_CLIENT_SECRET', ''),
        "environment": os.getenv('PAYPAL_ENVIRONMENT', 'sandbox'),
    },
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ["GBP", "USD", "EUR", "CAD", "AUD"]
BASE_CURRENCY = "GBP"
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')

# Use centralized auth management
from education_system.systems.university.infrastructure.shared_context import (
    get_auth,
    set_auth,
    get_current_user,
    check_permission,
)

# Backward compatibility - auth will be initialized lazily
# Don't call get_auth() at module level to avoid warnings
auth = None

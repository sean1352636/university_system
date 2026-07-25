from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
import os
import csv
import numpy as np
from datetime import datetime, timedelta
import json
import hashlib
import hmac
import requests
import smtplib
import ssl
import threading
import schedule
import time
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
from flask import Flask, request, jsonify
from io import BytesIO
import base64
from education_system.systems.university.infrastructure.email import send_email
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

try:
    auth = get_auth()
except Exception:
    auth = None
app = Flask(__name__)

# Initialize security headers for all responses
try:
    from education_system.systems.university.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available

# Encryption key for sensitive data
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Currency exchange API configuration
# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
PAYMENT_GATEWAYS = {
    'stripe': {'public_key': '', 'secret_key': '', 'webhook_secret': ''},
    'paypal': {'client_id': '', 'client_secret': '', 'environment': 'sandbox'}
}
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')

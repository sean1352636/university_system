# Standard library imports
import os
import re
import time
import hashlib
import json
import random
import pickle
import uuid
import base64
import logging
import traceback
import threading
import statistics
import math
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Configure logging first using the centralized logging config
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging

# Setup logger using the centralized configuration
logger = configure_logging(name="ai_detector")

# Application imports
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Handle optional dependencies with proper error handling
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.info("requests library not available. External API features will be disabled.")

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.info("scikit-learn not available. ML features will be disabled.")

try:
    import langdetect
    from langdetect import detect_langs
    LANG_DETECT_AVAILABLE = True
except ImportError:
    LANG_DETECT_AVAILABLE = False
    logger.info("langdetect not available. Language detection will be disabled.")

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.info("spaCy not available. Advanced NLP features will be disabled.")

try:
    import transformers
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.info("transformers not available. Advanced AI detection will be disabled.")

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.info("OCR libraries not available. Image analysis will be disabled.")

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.info("OpenCV not available. Advanced image analysis will be disabled.")

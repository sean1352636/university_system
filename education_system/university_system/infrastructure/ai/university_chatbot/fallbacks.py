"""Graceful library fallbacks for optional dependencies.

Provides dummy/stub implementations so the chatbot can run
even when heavy libraries (speech_recognition, flask, transformers, etc.)
are not installed.
"""

import json
import logging
import warnings

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Library availability registry
# ---------------------------------------------------------------------------
LIBRARIES_AVAILABLE = {}

# ---------------------------------------------------------------------------
# requests
# ---------------------------------------------------------------------------
try:
    import requests  # noqa: F401
    LIBRARIES_AVAILABLE['requests'] = True
except ImportError:
    logging.debug("Optional dependency missing: requests library not available - web features disabled")
    LIBRARIES_AVAILABLE['requests'] = False

# ---------------------------------------------------------------------------
# schedule
# ---------------------------------------------------------------------------
try:
    import schedule
    LIBRARIES_AVAILABLE['schedule'] = True
except ImportError:
    logging.debug("Optional dependency missing: schedule library not available - background tasks disabled")
    LIBRARIES_AVAILABLE['schedule'] = False

    class DummySchedule:
        """
        Fallback scheduler when 'schedule' library is not installed.

        Provides a no-op implementation that logs when jobs would have been
        scheduled, allowing code to run without the actual library.
        """
        def __init__(self):
            self._jobs = []

        def every(self, interval=1):
            """Start a new job configuration."""
            self._current_interval = interval
            return self

        def day(self):
            """Set interval to daily."""
            self._current_unit = 'day'
            return self

        def days(self):
            """Set interval to days."""
            self._current_unit = 'days'
            return self

        def week(self):
            """Set interval to weekly."""
            self._current_unit = 'week'
            return self

        def weeks(self):
            """Set interval to weeks."""
            self._current_unit = 'weeks'
            return self

        def hour(self):
            """Set interval to hourly."""
            self._current_unit = 'hour'
            return self

        def hours(self):
            """Set interval to hours."""
            self._current_unit = 'hours'
            return self

        def minute(self):
            """Set interval to minutes."""
            self._current_unit = 'minute'
            return self

        def minutes(self):
            """Set interval to minutes."""
            self._current_unit = 'minutes'
            return self

        def second(self):
            """Set interval to seconds."""
            self._current_unit = 'second'
            return self

        def seconds(self):
            """Set interval to seconds."""
            self._current_unit = 'seconds'
            return self

        def at(self, time_str):
            """Set specific time (ignored in fallback)."""
            self._scheduled_time = time_str
            return self

        def do(self, func, *args, **kwargs):
            """
            Register a job function.

            In fallback mode, logs that the job would be scheduled but
            does not actually execute or schedule anything.
            """
            job_info = {
                'func': func.__name__ if hasattr(func, '__name__') else str(func),
                'args': args,
                'kwargs': kwargs
            }
            self._jobs.append(job_info)
            logging.debug(f"DummySchedule: Would schedule job '{job_info['func']}' (schedule library not available)")
            return self

        def run_pending(self):
            """
            Run pending jobs (no-op in fallback mode).

            Since no jobs are actually scheduled, this does nothing but
            logs a debug message.
            """
            if self._jobs:
                logging.debug(f"DummySchedule: run_pending called with {len(self._jobs)} registered jobs (not executed)")

        def clear(self, tag=None):
            """Clear scheduled jobs."""
            self._jobs = []

        def get_jobs(self, tag=None):
            """Return list of registered job info (for debugging)."""
            return self._jobs

    schedule = DummySchedule()

# ---------------------------------------------------------------------------
# jwt
# ---------------------------------------------------------------------------
try:
    import jwt  # noqa: F401
    LIBRARIES_AVAILABLE['jwt'] = True
except ImportError:
    logging.debug("Optional dependency missing: PyJWT library not available - JWT authentication disabled")
    LIBRARIES_AVAILABLE['jwt'] = False

# ---------------------------------------------------------------------------
# numpy
# ---------------------------------------------------------------------------
try:
    import numpy as np
    LIBRARIES_AVAILABLE['numpy'] = True
except ImportError:
    logging.debug("Optional dependency missing: numpy library not available - advanced analytics disabled")
    LIBRARIES_AVAILABLE['numpy'] = False

    class DummyNumpy:
        def argmax(self, arr): return 0 if arr else 0
        def max(self, arr): return max(arr) if arr else 0
    np = DummyNumpy()

# ---------------------------------------------------------------------------
# pandas
# ---------------------------------------------------------------------------
try:
    import pandas as pd  # noqa: F401
    LIBRARIES_AVAILABLE['pandas'] = True
except ImportError:
    logging.debug("Optional dependency missing: pandas library not available - data analysis features limited")
    LIBRARIES_AVAILABLE['pandas'] = False

# ---------------------------------------------------------------------------
# pyttsx3
# ---------------------------------------------------------------------------
try:
    import pyttsx3  # noqa: F401
    LIBRARIES_AVAILABLE['pyttsx3'] = True
except ImportError:
    logging.debug("Optional dependency missing: pyttsx3 library not available - text-to-speech disabled")
    LIBRARIES_AVAILABLE['pyttsx3'] = False

# ---------------------------------------------------------------------------
# spacy
# ---------------------------------------------------------------------------
try:
    import spacy  # noqa: F401
    LIBRARIES_AVAILABLE['spacy'] = True
except ImportError:
    logging.debug("Optional dependency missing: spacy library not available - advanced NLP features disabled")
    LIBRARIES_AVAILABLE['spacy'] = False

# ---------------------------------------------------------------------------
# pyaudio
# ---------------------------------------------------------------------------
try:
    import pyaudio  # noqa: F401
    LIBRARIES_AVAILABLE['pyaudio'] = True
except ImportError:
    logging.debug("Optional dependency missing: pyaudio library not available - audio recording disabled")
    LIBRARIES_AVAILABLE['pyaudio'] = False

# ---------------------------------------------------------------------------
# wave
# ---------------------------------------------------------------------------
try:
    import wave  # noqa: F401
    LIBRARIES_AVAILABLE['wave'] = True
except ImportError:
    logging.debug("Optional dependency missing: wave library not available - audio processing limited")
    LIBRARIES_AVAILABLE['wave'] = False

# ---------------------------------------------------------------------------
# speech_recognition
# ---------------------------------------------------------------------------
try:
    import speech_recognition as sr
    LIBRARIES_AVAILABLE['speech_recognition'] = True
except ImportError:
    logging.debug("Optional dependency missing: speech_recognition library not available - voice recognition disabled")
    LIBRARIES_AVAILABLE['speech_recognition'] = False

    class DummySR:
        """
        Fallback speech recognition when 'speech_recognition' library is not installed.

        Provides stub classes and methods that allow code to run without crashing,
        while clearly indicating that voice features are unavailable.
        """

        class Recognizer:
            """Fallback Recognizer that logs when speech recognition is attempted."""

            def __init__(self):
                self.energy_threshold = 500
                self.dynamic_energy_threshold = True
                self.pause_threshold = 0.8
                self.phrase_threshold = 0.3
                self.non_speaking_duration = 0.5
                self.operation_timeout = None

            def adjust_for_ambient_noise(self, source, duration=1):
                """Simulate ambient noise adjustment (no-op)."""
                logging.debug(f"DummySR: adjust_for_ambient_noise called (duration={duration}s)")

            def listen(self, source, timeout=None, phrase_time_limit=None):
                """
                Simulate listening for audio input.

                Returns a DummyAudioData object to maintain API compatibility.
                """
                logging.debug("DummySR: listen() called - speech recognition not available")
                return DummySR.AudioData(b'', 16000, 2)

            def record(self, source, duration=None, offset=None):
                """Simulate recording audio."""
                logging.debug("DummySR: record() called - speech recognition not available")
                return DummySR.AudioData(b'', 16000, 2)

            def recognize_google(self, audio_data, key=None, language="en-US", pfilter=0, show_all=False):
                """
                Fallback Google speech recognition.

                Raises UnknownValueError to indicate recognition failure.
                """
                raise DummySR.UnknownValueError("Speech recognition library not installed. Install with: pip install SpeechRecognition")

            def recognize_sphinx(self, audio_data, language="en-US", keyword_entries=None, grammar=None):
                """Fallback Sphinx recognition."""
                raise DummySR.UnknownValueError("Speech recognition library not installed")

            def recognize_wit(self, audio_data, key, show_all=False):
                """Fallback Wit.ai recognition."""
                raise DummySR.UnknownValueError("Speech recognition library not installed")

            def recognize_bing(self, audio_data, key, language="en-US", show_all=False):
                """Fallback Bing recognition."""
                raise DummySR.UnknownValueError("Speech recognition library not installed")

            def recognize_whisper(self, audio_data, model="base", show_dict=False, load_options=None, language=None, translate=False):
                """Fallback Whisper recognition."""
                raise DummySR.UnknownValueError("Speech recognition library not installed")

        class Microphone:
            """Fallback Microphone class for context manager compatibility."""

            def __init__(self, device_index=None, sample_rate=None, chunk_size=1024):
                self.device_index = device_index
                self.SAMPLE_RATE = sample_rate or 16000
                self.CHUNK = chunk_size

            def __enter__(self):
                logging.debug("DummySR: Microphone context entered (no actual microphone access)")
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                """
                Clean up microphone resources.

                In fallback mode, no actual resources are held, so this just logs
                the context exit. Returns None to not suppress any exceptions.
                """
                logging.debug("DummySR: Microphone context exited")
                return None

            @staticmethod
            def list_microphone_names():
                """Return empty list - no microphones available in fallback mode."""
                return []

        class AudioFile:
            """Fallback AudioFile class for file-based audio input."""

            def __init__(self, filename_or_fileobject):
                self.filename = filename_or_fileobject
                self.SAMPLE_RATE = 16000
                self.DURATION = None

            def __enter__(self):
                logging.debug(f"DummySR: AudioFile context entered for {self.filename} (no actual processing)")
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                """
                Clean up audio file resources.

                In fallback mode, no actual file handle is opened, so this just
                logs the context exit. Returns None to not suppress any exceptions.
                """
                logging.debug(f"DummySR: AudioFile context exited for {self.filename}")
                return None

        class AudioData:
            """Fallback AudioData class to hold audio information."""

            def __init__(self, frame_data, sample_rate, sample_width):
                self.frame_data = frame_data
                self.sample_rate = sample_rate
                self.sample_width = sample_width

            def get_raw_data(self, convert_rate=None, convert_width=None):
                """Return empty raw audio data."""
                return self.frame_data

            def get_wav_data(self, convert_rate=None, convert_width=None):
                """Return minimal WAV header with no audio data."""
                return b'RIFF\x00\x00\x00\x00WAVEfmt '

            def get_flac_data(self, convert_rate=None, convert_width=None):
                """Return empty FLAC data."""
                return b''

        class UnknownValueError(Exception):
            """Raised when speech cannot be understood."""
            pass

        class RequestError(Exception):
            """Raised when API request fails."""
            pass

        class WaitTimeoutError(Exception):
            """Raised when listening times out."""
            pass

    sr = DummySR()

# ---------------------------------------------------------------------------
# tkinter
# ---------------------------------------------------------------------------
try:
    import tkinter as tk  # noqa: F401
    LIBRARIES_AVAILABLE['tkinter'] = True
except ImportError:
    logging.debug("Optional dependency missing: tkinter library not available - GUI features disabled")
    LIBRARIES_AVAILABLE['tkinter'] = False

# ---------------------------------------------------------------------------
# cryptography
# ---------------------------------------------------------------------------
try:
    from cryptography.fernet import Fernet
    LIBRARIES_AVAILABLE['cryptography'] = True
except ImportError:
    logging.debug("Optional dependency missing: cryptography library not available - advanced encryption disabled")
    LIBRARIES_AVAILABLE['cryptography'] = False

    class SimpleFernet:
        def __init__(self, key): self.key = key
        def encrypt(self, data): return data.encode() if isinstance(data, str) else data
        def decrypt(self, data): return data.decode() if isinstance(data, bytes) else data
        @staticmethod
        def generate_key(): return b'simple_key_for_fallback_encryption_use'
    Fernet = SimpleFernet

# ---------------------------------------------------------------------------
# flask
# ---------------------------------------------------------------------------
try:
    from flask import Flask, request, jsonify
    LIBRARIES_AVAILABLE['flask'] = True
except ImportError:
    logging.debug("Optional dependency missing: Flask library not available - web API disabled")
    LIBRARIES_AVAILABLE['flask'] = False

    class DummyFlask:
        """
        Fallback Flask application when Flask library is not installed.

        Provides a minimal interface that allows code to define routes
        without crashing, though the web server cannot actually run.
        """

        def __init__(self, import_name, static_url_path=None, static_folder='static',
                     static_host=None, host_matching=False, subdomain_matching=False,
                     template_folder='templates', instance_path=None,
                     instance_relative_config=False, root_path=None):
            self.import_name = import_name
            self.routes = {}
            self.config = {}
            self.debug = False
            self.secret_key = None
            self._registered_routes = []

        def route(self, rule, **options):
            """Register a route decorator (stored but not functional)."""
            methods = options.get('methods', ['GET'])

            def decorator(func):
                self._registered_routes.append({
                    'rule': rule,
                    'methods': methods,
                    'func': func.__name__
                })
                logging.debug(f"DummyFlask: Route registered {rule} [{', '.join(methods)}] -> {func.__name__}")
                return func

            return decorator

        def add_url_rule(self, rule, endpoint=None, view_func=None, **options):
            """Add a URL rule (stored but not functional)."""
            self._registered_routes.append({
                'rule': rule,
                'endpoint': endpoint,
                'func': view_func.__name__ if view_func else None
            })

        def run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
            """
            Attempt to run the web server.

            Since Flask is not installed, this prints an error message
            and lists the routes that would have been available.
            """
            print("\n" + "=" * 60)
            print("ERROR: Flask library not installed")
            print("=" * 60)
            print("\nThe web server cannot start without Flask.")
            print("Install Flask with: pip install flask")
            print(f"\nApplication: {self.import_name}")
            print(f"Would have started on: {host or '127.0.0.1'}:{port or 5000}")
            if self._registered_routes:
                print("\nRegistered routes:")
                for route in self._registered_routes:
                    print(f"  {route['rule']} -> {route.get('func', 'N/A')}")
            print("=" * 60 + "\n")

        def before_request(self, func):
            """Register a before_request handler (no-op)."""
            return func

        def after_request(self, func):
            """Register an after_request handler (no-op)."""
            return func

        def errorhandler(self, code_or_exception):
            """Register an error handler (no-op)."""
            def decorator(func):
                return func
            return decorator

        def register_blueprint(self, blueprint, **options):
            """Register a blueprint (no-op)."""
            logging.debug(f"DummyFlask: Blueprint registered (not functional)")

    Flask = DummyFlask

    def jsonify(*args, **kwargs):
        """Fallback jsonify that returns JSON string."""
        if args and kwargs:
            raise TypeError("jsonify() behavior undefined when passed both args and kwargs")
        if len(args) == 1:
            data = args[0]
        elif args:
            data = list(args)
        else:
            data = kwargs
        return json.dumps(data, indent=2)

    class DummyRequest:
        """Fallback request object."""
        json = {}
        args = {}
        form = {}
        files = {}
        method = 'GET'
        path = '/'
        headers = {}
        cookies = {}

        @property
        def data(self):
            return b''

        def get_json(self, force=False, silent=False, cache=True):
            return self.json

    request = DummyRequest()

# ---------------------------------------------------------------------------
# transformers
# ---------------------------------------------------------------------------
try:
    from transformers import pipeline, AutoTokenizer, AutoModel  # noqa: F401
    try:
        import torch  # noqa: F401
        LIBRARIES_AVAILABLE['transformers'] = True
    except ImportError:
        try:
            import tensorflow  # noqa: F401
            LIBRARIES_AVAILABLE['transformers'] = True
        except ImportError:
            logging.debug("Optional dependency missing: transformers requires PyTorch or TensorFlow - using fallback")
            LIBRARIES_AVAILABLE['transformers'] = False
except ImportError:
    logging.debug("Optional dependency missing: transformers library not available - advanced AI features disabled")
    LIBRARIES_AVAILABLE['transformers'] = False

if not LIBRARIES_AVAILABLE.get('transformers'):
    def pipeline(task, model=None):
        class DummyPipeline:
            def __call__(self, text, **kwargs):
                if task == "sentiment-analysis":
                    return [{"label": "NEUTRAL", "score": 0.5}]
                elif task == "text-classification":
                    return [{"label": "general", "score": 0.5}]
                elif task == "question-answering":
                    return {"answer": "Information not available", "score": 0.5}
                return []
        return DummyPipeline()

# ---------------------------------------------------------------------------
# sklearn
# ---------------------------------------------------------------------------
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    LIBRARIES_AVAILABLE['sklearn'] = True
except ImportError:
    logging.debug("Optional dependency missing: sklearn library not available - similarity matching disabled")
    LIBRARIES_AVAILABLE['sklearn'] = False

    class DummyTfidfVectorizer:
        def fit_transform(self, texts): return [[0] * len(texts)]
    TfidfVectorizer = DummyTfidfVectorizer

    def cosine_similarity(a, b): return [[0.5]]

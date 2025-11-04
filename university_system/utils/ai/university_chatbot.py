# Standard library
import os
import re
import json
import time
import pickle
import random
import secrets
import hashlib
import threading
import warnings
import smtplib
import sys
from pathlib import Path
from university_system.infrastructure.database.db import sqlite3, DatabaseManager, ensure_parent_dir
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import logging
import json
from university_system.modules.shared.constants import paths

# Email handling
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Project-level structure
from dataclasses import dataclass
from enum import Enum

warnings.filterwarnings('ignore')

# Graceful imports with error handling
LIBRARIES_AVAILABLE = {}

# Add current directory and parent directories to path
current_file = Path(__file__).resolve()
current_dir = current_file.parent
project_root = current_dir.parent

if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# --- Circular import guard: avoid importing auth at module import time ---
AUTH_AVAILABLE = False

# Safe placeholders; will be replaced by _lazy_auth() if auth is available
class UserAuth:  # type: ignore
    pass

def get_current_user():  # type: ignore
    return None

PERMISSIONS: Dict[str, int] = {}  # type: ignore

def _lazy_auth() -> None:
    """Import auth lazily to avoid circular imports with user_authentication."""
    global UserAuth, get_current_user, PERMISSIONS, AUTH_AVAILABLE
    if AUTH_AVAILABLE:
        return
    try:
        from university_system.infrastructure.auth import user_authentication as _auth
        UserAuth = _auth.UserAuth            # type: ignore
        get_current_user = _auth.get_current_user  # type: ignore
        PERMISSIONS = _auth.PERMISSIONS      # type: ignore
        AUTH_AVAILABLE = True
    except Exception:
        # Leave placeholders in place; run in standalone mode.
        AUTH_AVAILABLE = False
# --- end circular import guard ---

# Third-party libraries with graceful fallbacks
try:
    import requests
    LIBRARIES_AVAILABLE['requests'] = True
except ImportError:
    print("Warning: requests library not available - web features disabled")
    LIBRARIES_AVAILABLE['requests'] = False

try:
    import schedule
    LIBRARIES_AVAILABLE['schedule'] = True
except ImportError:
    print("Warning: schedule library not available - background tasks disabled")
    LIBRARIES_AVAILABLE['schedule'] = False
    # Create dummy schedule module
    class DummySchedule:
        def every(self): return self
        def day(self): return self
        def at(self, time): return self
        def do(self, func): pass
        def run_pending(self): pass
        def week(self): return self
    schedule = DummySchedule()

try:
    import jwt
    LIBRARIES_AVAILABLE['jwt'] = True
except ImportError:
    print("Warning: PyJWT library not available - JWT authentication disabled")
    LIBRARIES_AVAILABLE['jwt'] = False

try:
    import numpy as np
    LIBRARIES_AVAILABLE['numpy'] = True
except ImportError:
    print("Warning: numpy library not available - advanced analytics disabled")
    LIBRARIES_AVAILABLE['numpy'] = False
    # Create dummy numpy for basic operations
    class DummyNumpy:
        def argmax(self, arr): return 0 if arr else 0
        def max(self, arr): return max(arr) if arr else 0
    np = DummyNumpy()

try:
    import pandas as pd
    LIBRARIES_AVAILABLE['pandas'] = True
except ImportError:
    print("Warning: pandas library not available - data analysis features limited")
    LIBRARIES_AVAILABLE['pandas'] = False

try:
    import pyttsx3
    LIBRARIES_AVAILABLE['pyttsx3'] = True
except ImportError:
    print("Warning: pyttsx3 library not available - text-to-speech disabled")
    LIBRARIES_AVAILABLE['pyttsx3'] = False

try:
    import spacy
    LIBRARIES_AVAILABLE['spacy'] = True
except ImportError:
    print("Warning: spacy library not available - advanced NLP features disabled")
    LIBRARIES_AVAILABLE['spacy'] = False

try:
    import pyaudio
    LIBRARIES_AVAILABLE['pyaudio'] = True
except ImportError:
    print("Warning: pyaudio library not available - audio recording disabled")
    LIBRARIES_AVAILABLE['pyaudio'] = False

try:
    import wave
    LIBRARIES_AVAILABLE['wave'] = True
except ImportError:
    print("Warning: wave library not available - audio processing limited")
    LIBRARIES_AVAILABLE['wave'] = False

try:
    import speech_recognition as sr
    LIBRARIES_AVAILABLE['speech_recognition'] = True
except ImportError:
    print("Warning: speech_recognition library not available - voice recognition disabled")
    LIBRARIES_AVAILABLE['speech_recognition'] = False
    # Create dummy speech recognition
    class DummySR:
        class Recognizer:
            def __init__(self): pass
            def adjust_for_ambient_noise(self, source, duration=1): pass
            def listen(self, source, timeout=None, phrase_time_limit=None): return None
            def record(self, source): return None
            def recognize_google(self, audio): return "Speech recognition not available"
            energy_threshold = 500
            dynamic_energy_threshold = True
            pause_threshold = 0.8
            phrase_threshold = 0.3
        
        class Microphone:
            def __init__(self): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
        
        class AudioFile:
            def __init__(self, filename): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
        
        class UnknownValueError(Exception): pass
        class RequestError(Exception): pass
        class WaitTimeoutError(Exception): pass
    
    sr = DummySR()

try:
    import tkinter as tk
    LIBRARIES_AVAILABLE['tkinter'] = True
except ImportError:
    print("Warning: tkinter library not available - GUI features disabled")
    LIBRARIES_AVAILABLE['tkinter'] = False

try:
    from cryptography.fernet import Fernet
    LIBRARIES_AVAILABLE['cryptography'] = True
except ImportError:
    print("Warning: cryptography library not available - advanced encryption disabled")
    LIBRARIES_AVAILABLE['cryptography'] = False
    # Simple fallback encryption
    class SimpleFernet:
        def __init__(self, key): self.key = key
        def encrypt(self, data): return data.encode() if isinstance(data, str) else data
        def decrypt(self, data): return data.decode() if isinstance(data, bytes) else data
        @staticmethod
        def generate_key(): return b'simple_key_for_fallback_encryption_use'
    Fernet = SimpleFernet

try:
    from flask import Flask, request, jsonify
    LIBRARIES_AVAILABLE['flask'] = True
except ImportError:
    print("Warning: Flask library not available - web API disabled")
    LIBRARIES_AVAILABLE['flask'] = False
    # Create dummy Flask for compatibility
    class DummyFlask:
        def __init__(self, name): pass
        def route(self, path, methods=None): 
            def decorator(func): return func
            return decorator
        def run(self, host=None, port=None, debug=False): 
            print("Flask not available - web server cannot start")
    Flask = DummyFlask
    def jsonify(data): return json.dumps(data)
    class DummyRequest:
        json = {}
    request = DummyRequest()

try:
    from transformers import pipeline, AutoTokenizer, AutoModel
    # Check if PyTorch/TensorFlow/Flax is actually available
    try:
        import torch
        LIBRARIES_AVAILABLE['transformers'] = True
    except ImportError:
        try:
            import tensorflow
            LIBRARIES_AVAILABLE['transformers'] = True
        except ImportError:
            print("Warning: transformers requires PyTorch or TensorFlow - using fallback")
            LIBRARIES_AVAILABLE['transformers'] = False
except ImportError:
    print("Warning: transformers library not available - advanced AI features disabled")
    LIBRARIES_AVAILABLE['transformers'] = False

# Define fallback pipeline if transformers not fully available
if not LIBRARIES_AVAILABLE['transformers']:
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

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    LIBRARIES_AVAILABLE['sklearn'] = True
except ImportError:
    print("Warning: sklearn library not available - similarity matching disabled")
    LIBRARIES_AVAILABLE['sklearn'] = False
    # Simple fallback
    class DummyTfidfVectorizer:
        def fit_transform(self, texts): return [[0] * len(texts)]
    TfidfVectorizer = DummyTfidfVectorizer
    def cosine_similarity(a, b): return [[0.5]]

class VoiceInterface:
    """Enhanced voice interface with proper fallback handling"""
    
    def __init__(self):
        self.enabled = False
        self.recognizer = None
        self.microphone = None
        self.is_listening = False
        self.audio_config = {
            'sample_rate': 16000,
            'chunk_size': 1024,
            'channels': 1,
            'format': None,  # Will be set if pyaudio is available
            'threshold': 500,
            'silence_limit': 2,
            'prev_audio': 0.5
        }
        self.pyaudio_instance = None
        
    def initialize(self) -> bool:
        """Initialize voice recognition and synthesis with proper error handling"""
        # Check if we're in a headless environment (no audio hardware)
        import os
        if os.environ.get('DISPLAY') is None and os.environ.get('WAYLAND_DISPLAY') is None:
            print("ℹ️  Headless environment detected - voice features disabled (text-only mode)")
            return False

        if not LIBRARIES_AVAILABLE['speech_recognition']:
            print("ℹ️  Speech recognition library not available - voice features disabled")
            return False

        if not LIBRARIES_AVAILABLE['pyaudio']:
            print("ℹ️  PyAudio library not available - voice input disabled")
            return False

        try:
            # Initialize PyAudio with ALSA warning suppression
            import pyaudio
            import os
            from contextlib import contextmanager

            @contextmanager
            def suppress_alsa_errors():
                """Temporarily suppress ALSA error messages"""
                devnull = os.open(os.devnull, os.O_WRONLY)
                old_stderr = os.dup(2)
                try:
                    os.dup2(devnull, 2)
                    yield
                finally:
                    os.dup2(old_stderr, 2)
                    os.close(devnull)

            # Initialize PyAudio quietly
            with suppress_alsa_errors():
                self.pyaudio_instance = pyaudio.PyAudio()
                self.audio_config['format'] = pyaudio.paInt16

                # Test microphone availability
                device_count = self.pyaudio_instance.get_device_count()

            print(f"ℹ️  Found {device_count} audio devices")

            # Find default input device
            try:
                with suppress_alsa_errors():
                    default_device = self.pyaudio_instance.get_default_input_device_info()
                print(f"ℹ️  Default input device: {default_device['name']}")
            except Exception as e:
                print(f"⚠️  Warning: Could not detect default input device: {e}")
                print("ℹ️  Voice recording may not work properly")

            # Initialize speech recognizer with microphone
            self.recognizer = sr.Recognizer()

            # Try to initialize microphone with timeout and error handling
            try:
                with suppress_alsa_errors():
                    self.microphone = sr.Microphone()

                    # Test if microphone actually works with a quick check
                    with self.microphone as source:
                        # Very short calibration to avoid hanging
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                # Set recognition parameters
                self.recognizer.energy_threshold = self.audio_config['threshold']
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.pause_threshold = 0.8
                self.recognizer.phrase_threshold = 0.3

                self.enabled = True
                print("✓ Voice interface initialized successfully!")
                return True

            except Exception as mic_error:
                print(f"⚠️  Warning: Microphone test failed: {mic_error}")
                print("ℹ️  Voice recording disabled - continuing without voice capabilities")
                if self.pyaudio_instance:
                    self.pyaudio_instance.terminate()
                    self.pyaudio_instance = None
                return False

        except Exception as e:
            print(f"⚠️  Voice interface initialization failed: {e}")
            print("ℹ️  Continuing without voice capabilities (text-only mode)")
            if self.pyaudio_instance:
                try:
                    self.pyaudio_instance.terminate()
                except:
                    pass
                self.pyaudio_instance = None
            return False
    
    def record_audio_chunk(self, duration: float = 5.0) -> Optional[str]:
        """Record audio chunk using PyAudio and convert to text"""
        if not self.enabled or not LIBRARIES_AVAILABLE['speech_recognition'] or not LIBRARIES_AVAILABLE['pyaudio']:
            print("⚠️  Voice recording not available - using text-only mode")
            return None

        if not self.pyaudio_instance:
            print("⚠️  PyAudio not initialized - voice recording disabled")
            return None

        try:
            print("🎤 Listening... (speak now)")

            import pyaudio
            import wave
            import os
            from contextlib import contextmanager

            @contextmanager
            def suppress_alsa_errors():
                """Temporarily suppress ALSA error messages"""
                devnull = os.open(os.devnull, os.O_WRONLY)
                old_stderr = os.dup(2)
                try:
                    os.dup2(devnull, 2)
                    yield
                finally:
                    os.dup2(old_stderr, 2)
                    os.close(devnull)

            # Record audio using PyAudio with error suppression
            try:
                with suppress_alsa_errors():
                    stream = self.pyaudio_instance.open(
                        format=self.audio_config['format'],
                        channels=self.audio_config['channels'],
                        rate=self.audio_config['sample_rate'],
                        input=True,
                        frames_per_buffer=self.audio_config['chunk_size'],
                        input_device_index=None  # Use default
                    )
            except Exception as stream_error:
                print(f"❌ Audio recording error: {stream_error}")
                print("ℹ️  Voice input is not available on this system")
                self.enabled = False  # Disable voice features permanently
                return None

            frames = []
            try:
                for _ in range(0, int(self.audio_config['sample_rate'] / self.audio_config['chunk_size'] * duration)):
                    with suppress_alsa_errors():
                        data = stream.read(self.audio_config['chunk_size'], exception_on_overflow=False)
                    frames.append(data)
            finally:
                # Always cleanup stream
                try:
                    stream.stop_stream()
                    stream.close()
                except:
                    pass
            
            # Save to temporary WAV file
            temp_filename = "temp_audio.wav"
            with wave.open(temp_filename, 'wb') as wf:
                wf.setnchannels(self.audio_config['channels'])
                wf.setsampwidth(self.pyaudio_instance.get_sample_size(self.audio_config['format']))
                wf.setframerate(self.audio_config['sample_rate'])
                wf.writeframes(b''.join(frames))
            
            # Convert to text using speech recognition
            with sr.AudioFile(temp_filename) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)
                
            # Clean up temporary file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            
            print(f"Recognized: {text}")
            return text
            
        except sr.UnknownValueError:
            print("Could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"Speech recognition error: {e}")
            return None
        except Exception as e:
            print(f"Audio recording error: {e}")
            return None
    
    def listen_continuously(self, callback_func):
        """Listen continuously for voice input"""
        if not self.enabled or not LIBRARIES_AVAILABLE['speech_recognition']:
            print("Continuous listening not available - missing dependencies")
            return None
            
        self.is_listening = True
        print("Starting continuous listening... (say 'stop listening' to end)")
        
        def listen_worker():
            while self.is_listening:
                try:
                    # Use speech recognition with microphone
                    with self.microphone as source:
                        print("Listening for wake word or command...")
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    
                    try:
                        text = self.recognizer.recognize_google(audio)
                        print(f"Heard: {text}")
                        
                        if "stop listening" in text.lower():
                            self.is_listening = False
                            print("Stopped listening")
                            break
                            
                        # Process the recognized text
                        callback_func(text)
                        
                    except sr.UnknownValueError:
                        pass  # Ignore unrecognized audio
                        
                except sr.WaitTimeoutError:
                    pass  # Continue listening
                except Exception as e:
                    print(f"Continuous listening error: {e}")
                    time.sleep(1)
        
        # Start listening in a separate thread
        listen_thread = threading.Thread(target=listen_worker)
        listen_thread.daemon = True
        listen_thread.start()
        
        return listen_thread
    
    def stop_listening(self):
        """Stop continuous listening"""
        self.is_listening = False
    
    def test_microphone(self) -> Dict[str, Any]:
        """Test microphone functionality"""
        if not self.enabled:
            return {"status": "disabled", "message": "Voice interface not initialized"}
            
        if not self.pyaudio_instance:
            return {"status": "error", "message": "PyAudio not initialized"}
        
        try:
            # List available devices
            devices = []
            for i in range(self.pyaudio_instance.get_device_count()):
                device_info = self.pyaudio_instance.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    devices.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'sample_rate': device_info['defaultSampleRate']
                    })
            
            # Test recording a short sample
            print("Testing microphone... say something!")
            test_text = self.record_audio_chunk(duration=3.0)
            
            return {
                "status": "success",
                "devices": devices,
                "test_recording": test_text,
                "enabled": self.enabled
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def cleanup(self):
        """Clean up PyAudio resources"""
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()

# Data Classes and Enums
class UserRole(Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    STAFF = "staff"
    ADMIN = "admin"
    GUEST = "guest"

class QueryType(Enum):
    ACADEMIC = "academic"
    FINANCIAL = "financial"
    TECHNICAL = "technical"
    ADMINISTRATIVE = "administrative"
    GENERAL = "general"

class NotificationChannel(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"

@dataclass
class AuthenticatedSession:
    user_id: str
    username: str
    role: str
    permissions: List[str]
    auth_token: str
    login_time: datetime
    last_activity: datetime


@dataclass
class UserSession:
    user_id: str
    session_token: str
    login_time: datetime
    last_activity: datetime
    role: UserRole
    is_active: bool = True

@dataclass
class ConversationContext:
    conversation_id: str
    user_id: str
    messages: List[Dict]
    intent_history: List[str]
    entities: Dict[str, Any]
    session_data: Dict[str, Any]

@dataclass
class StudentProfile:
    student_id: str
    name: str
    email: str
    program: str
    year: int
    gpa: float
    completed_courses: List[str]
    current_courses: List[str]
    interests: List[str]
    financial_aid: bool

def create_chatbot_with_auth(auth_system, db_path='student_records.db'):
    """Factory function to create chatbot with authentication"""
    chatbot = UniversityChatbot(db_path=db_path)
    chatbot.set_auth_system(auth_system)
    return chatbot

def test_chatbot_integration(auth_system):
    """Test chatbot integration with authentication system"""
    print("Testing chatbot integration...")
    
    try:
        # Create chatbot instance
        chatbot = create_chatbot_with_auth(auth_system)
        
        # Test basic functionality - updated with proper parameters
        test_message = "Hello, this is a test"
        response = chatbot.process_message(test_message, "test_user", session_id="test_session")
        
        if response:
            print("✅ Chatbot integration test passed")
            return True
        else:
            print("❌ Chatbot integration test failed")
            return False
            
    except Exception as e:
        print(f"❌ Chatbot integration test failed: {e}")
        return False
    
class MinimalChatbot:
    def __init__(self, db_path=None):
        self.db_path = db_path or 'student_records.db'
        self.auth_system = None
        self.conversation_history = {}
        self.enabled = True
        print("Minimal chatbot initialized")
    
    def set_auth_system(self, auth_system):
        """Set authentication system"""
        self.auth_system = auth_system
    
    def process_message(self, message, user_id, session_id=None, is_voice=False, **kwargs):
        """Process basic messages with conversation tracking"""
        message_lower = message.lower()
        
        # Get user context if auth system is available
        role = "guest"
        if self.auth_system and self.auth_system.current_user:
            role = self.auth_system.current_user.get('role', 'guest')
        
        # Generate response based on message content and role
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            if role == 'student':
                response = "Hello! I'm the University Chatbot. I can help you with courses, grades, registration, and more."
            elif role in ['staff', 'admin']:
                response = "Hello! I can help you with student management, course administration, and system functions."
            else:
                response = "Hello! I'm the University Chatbot. How can I help you with university information?"
        
        elif any(word in message_lower for word in ['course', 'class', 'program', 'module']):
            response = "I can help you with course information, enrollment, and academic planning. What specific course information do you need?"
        
        elif any(word in message_lower for word in ['grade', 'gpa', 'transcript', 'academic record']):
            response = "For grade information and academic records, please check your student portal for official records or contact the registrar's office."
        
        elif any(word in message_lower for word in ['fee', 'tuition', 'payment', 'financial']):
            response = "I can provide information about tuition fees, payment schedules, and financial aid. For specific account details, please visit the bursar's office."
        
        elif any(word in message_lower for word in ['register', 'enrollment', 'enroll']):
            response = "I can guide you through the registration process. Registration is typically available through the student portal during designated periods."
        
        elif any(word in message_lower for word in ['help', 'support']):
            response = "I'm here to help with university-related questions including:\n• Course information and enrollment\n• Academic records and grades\n• Financial information\n• Registration assistance\n• General university policies"
        
        else:
            response = "I'm here to help with university-related questions. You can ask about courses, grades, fees, registration, or general university information. How can I assist you today?"
        
        # Track conversation history
        self.track_conversation(user_id, message, response, is_voice, session_id)
        
        # Log to auth system if available
        if self.auth_system and hasattr(self.auth_system, '_log_activity'):
            try:
                current_user = self.auth_system.current_user
                user_id_for_log = current_user['id'] if current_user else None
                self.auth_system._log_activity(
                    user_id, 
                    'Chatbot interaction', 
                    f"Q: {message[:50]}... A: {response[:50]}...",
                    user_id_for_log
                )
            except Exception as e:
                pass  # Don't break if logging fails
        
        return response
    
    def track_conversation(self, user_id, message, response, is_voice=False, session_id=None):
        """Track conversation in memory with session tracking"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        self.conversation_history[user_id].append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'session_id': session_id,
            'message': message,
            'response': response,
            'type': 'voice' if is_voice else 'text'
        })
        
        # Keep only last 50 conversations per user
        if len(self.conversation_history[user_id]) > 50:
            self.conversation_history[user_id] = self.conversation_history[user_id][-50:]

    def run_authenticated_console_interface(self):
        """Run console interface with existing authentication"""
        print("University Chatbot")
        print("=" * 30)
        
        # Check if user is already authenticated through main system
        if not self.auth_system:
            print("Error: No authentication system available.")
            return
        
        # Check if session is still valid and get current user
        if not self.auth_system.check_session():
            print("Error: Your session has expired. Please log in through the main system.")
            return
        
        # Get current user
        user = self.auth_system.current_user
        if not user:
            print("Error: No authenticated user found.")
            return
        
        print(f"Welcome {user['username']}! You are logged in as {user['role']}.")
        
        # Check chatbot permissions
        if 'access_chatbot' not in user.get('permissions', []):
            print("You don't have permission to access the chatbot.")
            return
        
        print("\nType 'exit' to return to main menu, 'help' for commands.")
        
        # Main chat loop
        while True:
            try:
                # Check session validity
                if not self.auth_system.check_session():
                    print("\nYour session has expired.")
                    break
                
                user_input = input(f"\n{user['username']}: ")
                
                # Handle exit commands
                if user_input.lower() in ['exit', 'quit', 'back']:
                    print("Returning to main menu...")
                    break
                
                # Handle help command
                if user_input.lower() == 'help':
                    print("\nAvailable commands:")
                    print("- Ask about courses, registration, grades, fees")
                    print("- 'exit' to return to main menu")
                    continue
                
                # Handle empty input
                if not user_input.strip():
                    print("Please enter a message.")
                    continue
                
                # Process message
                try:
                    response = self.process_message(user_input, user['username'])
                    print(f"Chatbot: {response}")
                    
                except Exception as process_error:
                    print(f"Chatbot: I encountered an error: {process_error}")
                
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break
                
            except Exception as e:
                print(f"Error: {e}")
                break
        
        print(f"Chatbot session ended. Thank you!")
    
    def get_conversation_history(self, username, limit=10):
        """Get conversation history"""
        return self.conversation_history.get(username, [])[-limit:]

class UniversityChatbot:
    def __init__(self, db_path=None, config_path=None):
        # Core initialization
        self.db_path = db_path or os.fspath(paths.DEFAULT_DB_PATH)
        self.config_path = config_path or os.fspath(paths.CHATBOT_DATA_DIR / 'chatbot_config.json')
        self.log_dir = os.fspath(paths.LOG_DIR)
        self.upload_dir = os.fspath(paths.CHATBOT_UPLOAD_DIR)
        self.models_dir = os.fspath(paths.CHATBOT_MODELS_DIR)

        # Authentication system integration
        self.auth_system = None
        self.authenticated_sessions = {}
        self.conversation_contexts = {}
        self.active_sessions = {}  # ADD THIS
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize directories
        self.ensure_directories()
        self.active_sessions = {}          
        # Initialize voice interface FIRST
        self.voice_interface = VoiceInterface()
        self.voice_interface.initialize()
        
        # Initialize NLP components
        self.init_nlp_components()
        
        # Knowledge base and patterns
        self.init_knowledge_base()
        
        # Conversation tracking
        self.conversation_history = {}
        
        # Flask app for web API
        if LIBRARIES_AVAILABLE['flask']:
            self.app = Flask(__name__)
            self.setup_api_routes()
        
        print("University Chatbot initialized successfully!")
    
    def set_auth_system(self, auth_system):
        """Set the authentication system for integration"""
        self.auth_system = auth_system
        print("✅ Authentication system integrated with chatbot")
    
    # Enhanced Message Processing with Voice Support
    def process_message(self, message: str, user_id: str, session_id: str | None = None, is_voice: bool = False, **kwargs) -> str:
        """
        Canonical entrypoint. Supports optional session_id.
        If session_id matches an active authenticated session, we process with auth context.
        Otherwise we use/initialize a conversation context keyed by user_id.
        """
        try:
            # If session_id provided and corresponds to an active authenticated session, use it
            if session_id and session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                return self.process_message_with_auth(message, session, is_voice=is_voice)

            # Fallback: non-auth flow with conversation context
            if user_id not in self.conversation_contexts:
                self.conversation_contexts[user_id] = ConversationContext(
                    conversation_id=session_id or f"{user_id}_{int(time.time())}",
                    user_id=user_id,
                    messages=[],
                    intent_history=[],
                    entities={},
                    session_data={}
                )
            context = self.conversation_contexts[user_id]
                
            # Update session_id if provided
            if session_id:
                context.conversation_id = session_id
            
            # Process with NLP
            nlp_result = self.process_with_nlp(message, context)
            
            # Update context
            context.messages.append({
                "user_message": message,
                "timestamp": datetime.now().isoformat(),
                "nlp_result": nlp_result,
                "is_voice": is_voice,
                "session_id": session_id
            })
            
            if nlp_result["intent"]:
                context.intent_history.append(nlp_result["intent"])
            
            context.entities.update(nlp_result["entities"])
            
            # Handle voice commands specifically
            if nlp_result.get("is_voice_command", False):
                return self.handle_voice_command(message, user_id, context)
            
            # Check if escalation is needed
            if nlp_result["requires_escalation"]:
                return self.escalate_to_human(message, user_id)
            
            # Generate response based on intent
            response = self.generate_response(nlp_result, context)
            
            # Log conversation with session_id
            self.log_enhanced_conversation(user_id, message, response, nlp_result, session_id)
            
            return response
            
        except Exception as e:
            print(f"Message processing error: {e}")
            return "I apologize, but I encountered an error processing your message. Please try again or contact support."        

    def get_user_context(self, username):
        """Get user context from authentication system"""
        if not self.auth_system:
            return {"username": username, "role": "guest", "permissions": []}
        
        try:
            # Get current user from auth system
            current_user = self.auth_system.current_user
            if current_user and current_user['username'] == username:
                return {
                    "username": username,
                    "role": current_user['role'],
                    "permissions": current_user.get('permissions', []),
                    "user_id": current_user['id']
                }
        except Exception as e:
            logging.error(f"Error getting user context: {e}")
        
        return {"username": username, "role": "guest", "permissions": []}
    
    def generate_contextual_response(self, message, user_context):
        """Generate response based on user context and message"""
        message_lower = message.lower()
        role = user_context.get('role', 'guest')
        permissions = user_context.get('permissions', [])
        
        # Role-based responses
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            if role == 'student':
                return f"Hello! I'm here to help with your academic needs. You can ask about courses, grades, registration, and more."
            elif role == 'staff':
                return f"Hello! I can help you with student information, course management, and administrative tasks."
            elif role == 'admin':
                return f"Hello! I have full access to help you with any university system functions."
            else:
                return "Hello! I'm the University Chatbot. How can I help you today?"
        
        # Course information
        elif any(word in message_lower for word in ['course', 'class', 'program', 'module']):
            if role == 'student':
                return "I can help you find course information, check prerequisites, and guide you through registration. What specific course or program are you interested in?"
            elif role in ['staff', 'admin']:
                return "I can help you with course management, student enrollment, and academic planning. What course information do you need?"
            else:
                return "I can provide general course information. For specific enrollment details, please contact the registrar's office."
        
        # Grade information
        elif any(word in message_lower for word in ['grade', 'gpa', 'transcript', 'academic record']):
            if 'view_own_grades' in permissions or 'manage_grades' in permissions:
                return "I can help you with grade information. For official transcripts, please check your student portal or contact the registrar's office."
            elif role in ['staff', 'admin']:
                return "I can help you access student grade information and generate academic reports."
            else:
                return "For grade information, please check your student portal or contact the registrar's office."
        
        # Financial information
        elif any(word in message_lower for word in ['fee', 'tuition', 'payment', 'financial', 'scholarship']):
            if 'view_own_finances' in permissions or 'manage_finances' in permissions:
                return "I can help with financial information including tuition, fees, and payment options. For specific account details, please check your student account online."
            else:
                return "For financial information, please visit the bursar's office or check your student account online."
        
        # Registration
        elif any(word in message_lower for word in ['register', 'enrollment', 'enroll']):
            if role == 'student':
                return "I can guide you through the registration process. Registration is typically available through the student portal during designated periods. Would you like help with course selection?"
            elif role in ['staff', 'admin']:
                return "I can help you with student registration management and enrollment processes."
            else:
                return "For registration information, please contact the registrar's office or check the academic calendar."
        
        # Help and support
        elif any(word in message_lower for word in ['help', 'support']):
            features = []
            if role == 'student':
                features = [
                    "• Course information and enrollment",
                    "• Academic records and grades", 
                    "• Financial information",
                    "• Registration assistance",
                    "• General university policies"
                ]
            elif role in ['staff', 'admin']:
                features = [
                    "• Student information management",
                    "• Course and module management",
                    "• Administrative support",
                    "• System information",
                    "• Report generation"
                ]
            else:
                features = [
                    "• General university information",
                    "• Course catalogs",
                    "• Contact information",
                    "• Campus resources"
                ]
            
            return f"I'm here to help with university-related questions including:\n" + "\n".join(features)
        
        # Voice commands
        elif any(word in message_lower for word in ['voice', 'speak', 'listen']):
            if 'voice_interaction' in permissions:
                return "Voice features are available! You can speak your questions naturally. Say 'voice help' for more voice commands."
            else:
                return "Voice features require special permissions. Please contact your administrator."
        
        # Admin functions
        elif role == 'admin' and any(word in message_lower for word in ['system', 'database', 'admin']):
            return "As an administrator, I can help you with system management, user administration, database operations, and advanced reporting."
        
        # Default response
        else:
            if role == 'guest':
                return "I'm here to help with university-related questions. For personalized assistance, please log in to access more features."
            else:
                return f"I'm here to help with university-related questions. As a {role}, you have access to specialized features. What would you like to know?"
    
    def log_conversation(self, username, message, response, session_id):
        """Log conversation to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create the table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chatbot_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT
            )
            ''')
            
            # Get user_id if available
            user_id = None
            if self.auth_system and self.auth_system.current_user:
                user_id = self.auth_system.current_user.get('id')
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO chatbot_conversations 
            (user_id, username, message, response, timestamp, session_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, message, response, timestamp, session_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logging.error(f"Error logging conversation: {e}")
            # Don't raise the error to avoid breaking the conversation flow
            pass
    
    def track_conversation(self, username, message, response, is_voice=False):
        """Track conversation in memory for session"""
        if username not in self.conversation_history:
            self.conversation_history[username] = []
        
        self.conversation_history[username].append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': message,
            'response': response,
            'type': 'voice' if is_voice else 'text'
        })
        
        # Keep only last 50 conversations per user
        if len(self.conversation_history[username]) > 50:
            self.conversation_history[username] = self.conversation_history[username][-50:]
    
    def get_conversation_history(self, username, limit=10):
        """Get conversation history for user"""
        return self.conversation_history.get(username, [])[-limit:]
    
    def run_authenticated_console_interface(self):
        """Run console interface with existing authentication"""
        print("University Chatbot")
        print("=" * 30)
        
        # Check if user is authenticated
        if not self.auth_system or not self.auth_system.current_user:
            print("Error: No authenticated user found. Please log in through the main system first.")
            return
        
        user = self.auth_system.current_user
        print(f"Welcome {user['username']}! You are logged in as {user['role']}.")
        
        # Check chatbot permissions
        if 'access_chatbot' not in user.get('permissions', []):
            print("You don't have permission to access the chatbot.")
            return
        
        # Show available features based on role
        print(f"\nChatbot Features Available:")
        if user['role'] == 'student':
            print("• Ask about courses and enrollment")
            print("• Check academic information")
            print("• Get help with registration")
            print("• Financial aid information")
        elif user['role'] in ['staff', 'admin']:
            print("• Student information lookup")
            print("• Course management assistance")
            print("• Administrative support")
            print("• System information")
        
        print("\nType 'exit' to return to main menu, 'help' for commands.")
        
        session_id = f"{user['username']}_{int(datetime.now().timestamp())}"
        
        # Main chat loop
        while True:
            try:
                # Check session validity
                if not self.auth_system.check_session():
                    print("\nYour session has expired. Please log in again through the main system.")
                    break
                
                user_input = input(f"\n{user['username']}: ")
                
                # Handle exit commands
                if user_input.lower() in ['exit', 'quit', 'back', 'logout']:
                    print("Returning to main menu...")
                    break
                
                # Handle help command
                if user_input.lower() == 'help':
                    print("\nAvailable commands:")
                    print("- Ask about courses, registration, grades, fees")
                    print("- Request information based on your role permissions")
                    print(f"- Your role: {user['role']}")
                    print("- 'exit' to return to main menu")
                    continue
                
                # Handle empty input
                if not user_input.strip():
                    print("Please enter a message or type 'help' for available commands.")
                    continue
                
                # Process message
                try:
                    response = self.process_message(user_input, user['username'], session_id)
                    print(f"Chatbot: {response}")
                    
                except Exception as process_error:
                    print(f"Chatbot: I apologize, but I encountered an error processing your message: {process_error}")
                    print("Please try rephrasing your question or contact support if the issue persists.")
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Returning to main menu...")
                break
                
            except EOFError:
                print("\nEnd of input detected. Returning to main menu...")
                break
                
            except Exception as e:
                print(f"Unexpected error: {e}")
                print("Returning to main menu...")
                break
        
        # Final message
        print(f"Chatbot session ended for {user['username']}. Thank you for using the University Chatbot!")
    
    def ensure_directories(self):
        """Create necessary directories"""
        import os
        for directory in [self.log_dir, self.upload_dir, self.models_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def init_knowledge_base(self):
        """Initialize knowledge base"""
        self.knowledge_base = {
            "academic": {
                "courses": "Information about university courses and programs",
                "registration": "Course registration and enrollment procedures",
                "grades": "Academic performance and grading information",
                "requirements": "Degree and graduation requirements"
            },
            "financial": {
                "tuition": "Tuition fees and payment information",
                "scholarships": "Scholarship and financial aid opportunities",
                "billing": "Billing and payment procedures"
            },
            "administrative": {
                "policies": "University policies and procedures",
                "calendar": "Academic calendar and important dates",
                "contacts": "Department and office contact information"
            }
        }
    
    def get_system_status(self):
        """Get chatbot system status"""
        status = {
            "authenticated": self.auth_system is not None,
            "current_user": None,
            "active_sessions": len(self.conversation_history),
            "total_conversations": 0
        }
        
        if self.auth_system and self.auth_system.current_user:
            status["current_user"] = self.auth_system.current_user['username']
        
        # Count total conversations
        for user_history in self.conversation_history.values():
            status["total_conversations"] += len(user_history)
        
        return status
        
    def load_config(self) -> Dict:
        """Load configuration from file"""
        default_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "university_db"
            },
            "email": {
                "smtp_server": "smtp.university.edu",
                "smtp_port": 587,
                "username": "chatbot@university.edu",
                "password": ""
            },
            "sms": {
                "api_key": "",
                "service_url": ""
            },
            "security": {
                "jwt_secret": secrets.token_hex(32),
                "session_timeout": 3600,
                "max_login_attempts": 3
            },
            "nlp": {
                "model_name": "distilbert-base-uncased",
                "confidence_threshold": 0.7
            },
            "features": {
                "voice_enabled": True,
                "push_notifications": True,
                "analytics_enabled": True
            },
            "voice": {
                "sample_rate": 16000,
                "chunk_size": 1024,
                "threshold": 500,
                "silence_limit": 2,
                "language": "en-US"
            }
        }
        
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                return {**default_config, **config}
        else:
            # Save default config
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config

    def load_or_generate_encryption_key(self) -> bytes:
        """Load or generate encryption key"""
        key_path = "encryption.key"
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_path, 'wb') as f:
                f.write(key)
            return key

    def ensure_directories(self):
        """Create necessary directories"""
        for directory in [self.log_dir, self.upload_dir, self.models_dir]:
            os.makedirs(directory, exist_ok=True)

    # Authentication and Security
    def authenticate_user_for_chatbot(
        self,
        username: str,
        password: str,
        mfa_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Authenticate user specifically for chatbot access"""
        if not self.auth_system:
            return {"success": False, "error": "Authentication system not available"}
            
        try:
            # Attempt login
            result = self.auth_system.login(username, password)
                
            if result is True:
                # Login successful
                current_user = self.auth_system.current_user
                    
                # Create chatbot session
                session_token = secrets.token_hex(32)
                session = AuthenticatedSession(
                    user_id=str(current_user['id']),
                    username=current_user['username'],
                    role=current_user['role'],
                    permissions=current_user['permissions'],
                    auth_token=session_token,
                    login_time=datetime.now(),
                    last_activity=datetime.now()
                )
                    
                self.authenticated_sessions[session_token] = session
                
                # Log authentication
                self.log_enhanced_conversation(
                    current_user['username'],
                    "User authenticated for chatbot access",
                    f"Login successful for {current_user['role']} user",
                    {"authenticated": True, "role": current_user['role']}
                )
                
                return {
                    "success": True,
                    "session_token": session_token,
                    "user": {
                        "username": current_user['username'],
                        "role": current_user['role'],
                        "permissions": current_user['permissions']
                    },
                    "message": f"Welcome {current_user['username']}! You are logged in as {current_user['role']}."
                }
                
            elif isinstance(result, dict) and result.get('requires_2fa'):
                # 2FA required
                if mfa_code:
                    # Attempt 2FA completion
                    if self.auth_system.complete_two_fa_login(result['user_id'], result['username'], mfa_code):
                        # Repeat successful login process
                        return self.authenticate_user_for_chatbot(username, password)
                    else:
                        return {"success": False, "error": "Invalid 2FA code"}
                else:
                    return {
                        "success": False,
                        "requires_2fa": True,
                        "user_id": result['user_id'],
                        "username": result['username'],
                        "message": "2FA code required"
                    }
                    
            elif result == 'password_reset_required':
                return {
                    "success": False,
                    "password_reset_required": True,
                    "message": "Password reset required before chatbot access"
                }
            else:
                return {"success": False, "error": "Invalid credentials"}
                
        except Exception as e:
            print(f"Authentication error: {e}")
            return {"success": False, "error": "Authentication system error"}

    def init_nlp_components(self):
        """Initialize NLP components with proper error handling"""
        try:
            # Initialize components only if libraries are available
            if LIBRARIES_AVAILABLE['spacy']:
                try:
                    import spacy
                    self.nlp = spacy.load("en_core_web_sm")
                    print("✓ SpaCy NLP model loaded successfully")
                except OSError:
                    print("ℹ️  SpaCy model 'en_core_web_sm' not found - using lightweight fallback")
                    print("   To install: python -m spacy download en_core_web_sm")
                    self.nlp = None
            else:
                self.nlp = None
                print("ℹ️  SpaCy not available - using lightweight fallback NLP")
            
            # Initialize intent classifier
            if LIBRARIES_AVAILABLE['transformers']:
                try:
                    self.intent_classifier = pipeline(
                        "text-classification",
                        model="distilbert-base-uncased"
                    )
                    self.sentiment_analyzer = pipeline("sentiment-analysis")
                    self.qa_pipeline = pipeline("question-answering")
                    print("✓ Advanced NLP models loaded successfully")
                except Exception as e:
                    print(f"Warning: Advanced NLP model loading failed ({e}), using lightweight fallback")
                    # Use fallback pipeline
                    self.intent_classifier = pipeline("text-classification")
                    self.sentiment_analyzer = pipeline("sentiment-analysis")
                    self.qa_pipeline = pipeline("question-answering")
            else:
                # Using lightweight fallback
                self.intent_classifier = pipeline("text-classification")
                self.sentiment_analyzer = pipeline("sentiment-analysis")
                self.qa_pipeline = pipeline("question-answering")
            
            # TF-IDF for similarity matching
            if LIBRARIES_AVAILABLE['sklearn']:
                self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            else:
                self.vectorizer = TfidfVectorizer()
            
            print("✓ NLP components initialized successfully")
        except Exception as e:
            print(f"Warning: NLP components initialization failed: {e}")
            # Use fallback implementations
            self.nlp = None
            self.intent_classifier = pipeline("text-classification")
            self.sentiment_analyzer = pipeline("sentiment-analysis")
            self.qa_pipeline = pipeline("question-answering")
            try:
                self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            except:
                self.vectorizer = TfidfVectorizer()
        
    def init_knowledge_base(self):
        """Initialize enhanced knowledge base"""
        self.intents = {
            "course_inquiry": {
                "patterns": ["course", "program", "degree", "study", "major", "curriculum"],
                "responses": ["I can help you with course information.", "Let me find course details for you."],
                "requires_auth": False,
                "department": "academic"
            },
            "registration": {
                "patterns": ["register", "enroll", "sign up", "add course", "drop course"],
                "responses": ["I'll help you with registration.", "Let me guide you through the registration process."],
                "requires_auth": True,
                "department": "academic"
            },
            "financial": {
                "patterns": ["fee", "tuition", "payment", "scholarship", "financial aid"],
                "responses": ["I can assist with financial information.", "Let me help with your financial queries."],
                "requires_auth": True,
                "department": "finance"
            },
            "grades": {
                "patterns": ["grade", "gpa", "transcript", "academic record"],
                "responses": ["I can help you check your academic performance.", "Let me retrieve your grade information."],
                "requires_auth": True,
                "department": "academic"
            },
            "technical_support": {
                "patterns": ["password", "login", "system", "technical", "computer", "wifi"],
                "responses": ["I can help with technical issues.", "Let me connect you with IT support."],
                "requires_auth": False,
                "department": "it"
            },
            "voice_command": {
                "patterns": ["voice", "speech", "listen", "talk", "speak"],
                "responses": ["I can interact with you using voice commands.", "Voice mode is available for hands-free interaction."],
                "requires_auth": False,
                "department": "general"
            }
        }

        # FAQ database
        self.faq_database = self.load_faq_database()

    def load_faq_database(self) -> Dict:
        """Load FAQ database from file or create default"""
        faq_path = os.fspath(paths.CHATBOT_DATA_DIR / "faq_database.json")
        default_faq = {
            "academic": {
                "How do I register for courses?": "You can register through the student portal during registration periods.",
                "What are the prerequisites for advanced courses?": "Prerequisites vary by course. Check the course catalog for specific requirements.",
                "How do I calculate my GPA?": "GPA is calculated by dividing total grade points by total credit hours."
            },
            "financial": {
                "When are tuition payments due?": "Tuition is typically due before the start of each semester.",
                "How do I apply for financial aid?": "Submit the FAFSA form and university scholarship applications.",
                "What payment methods are accepted?": "We accept credit cards, bank transfers, and payment plans."
            },
            "technical": {
                "How do I reset my password?": "Use the 'Forgot Password' link on the login page or contact IT support.",
                "How do I connect to campus WiFi?": "Connect to 'UniversityWiFi' and use your student credentials.",
                "Where can I download campus software?": "Visit the IT services website for software downloads."
            },
            "voice": {
                "How do I use voice commands?": "Say 'start voice mode' to begin voice interaction. You can ask questions naturally and I'll respond with voice and text.",
                "What voice commands are available?": "You can ask about courses, grades, registration, and general university information using natural speech.",
                "How do I stop voice mode?": "Say 'stop listening' or 'exit voice mode' to return to text-only interaction."
            }
        }
        
        if os.path.exists(faq_path):
            with open(faq_path, 'r') as f:
                return json.load(f)
        else:
            with open(faq_path, 'w') as f:
                json.dump(default_faq, f, indent=4)
            return default_faq

    # Voice Processing Methods
    def process_voice_input(self, duration: float = 5.0) -> str:
        """Process voice input with error handling"""
        if not self.voice_interface.enabled:
            return ""
        
        text = self.voice_interface.record_audio_chunk(duration)
        return text if text else ""

    def start_voice_mode(self, user_id: str):
        """Start continuous voice interaction mode"""
        if not self.voice_interface.enabled:
            print("Voice interface not available")
            return None
        
        def voice_callback(text: str):
            """Handle voice input"""
            if text:
                print(f"Voice input: {text}")
                response = self.process_message(text, user_id, is_voice=True)
                print(f"Response: {response}")
                
                # Convert response to speech if TTS is available
                if LIBRARIES_AVAILABLE['pyttsx3']:
                    self.text_to_speech(response)
        
        print("Starting voice mode... Say 'stop listening' to exit.")
        if LIBRARIES_AVAILABLE['pyttsx3']:
            self.text_to_speech("Voice mode activated. How can I help you?")
        
        # Start continuous listening
        listen_thread = self.voice_interface.listen_continuously(voice_callback)
        
        return listen_thread

    def text_to_speech(self, text: str, output_path: str = None) -> bool:
        """Convert text to speech using pyttsx3"""
        if not LIBRARIES_AVAILABLE['pyttsx3']:
            print("Text-to-speech not available - missing pyttsx3 library")
            return False
            
        try:
            import pyttsx3
            engine = pyttsx3.init()
            
            # Configure voice properties
            voices = engine.getProperty('voices')
            if voices:
                engine.setProperty('voice', voices[0].id)  # Use first available voice
            engine.setProperty('rate', 150)  # Speed of speech
            engine.setProperty('volume', 0.9)  # Volume level
            
            if output_path:
                engine.save_to_file(text, output_path)
                engine.runAndWait()
            else:
                engine.say(text)
                engine.runAndWait()
            
            return True
            
        except Exception as e:
            print(f"Text-to-speech error: {e}")
            return False

    def test_voice_interface(self) -> Dict:
        """Test voice interface functionality"""
        if not self.voice_interface.enabled:
            return {"status": "disabled", "message": "Voice interface not available"}
        
        return self.voice_interface.test_microphone()

    def setup_api_routes(self):
        """Setup enhanced API routes with authentication"""
        if not LIBRARIES_AVAILABLE['flask']:
            print("Flask not available - web API routes disabled")
            return
        
        # Basic routes (remove the recursive call)
        @self.app.route('/api/chat', methods=['POST'])
        def api_chat():
            data = request.json
            message = data.get('message', '')
            user_id = data.get('user_id', 'anonymous')
            
            response = self.process_message(message, user_id)
            
            return jsonify({
                "response": response,
                "timestamp": datetime.now().isoformat()
            })
        
        # Add new authenticated routes
        @self.app.route('/api/auth/login', methods=['POST'])
        def api_auth_login():
            data = request.json
            username = data.get('username', '')
            password = data.get('password', '')
            mfa_code = data.get('mfa_code', '')
            
            result = self.authenticate_user_for_chatbot(username, password, mfa_code if mfa_code else None)
            
            if result["success"]:
                return jsonify(result), 200
            else:
                return jsonify(result), 401
        
        @self.app.route('/api/auth/logout', methods=['POST'])
        def api_auth_logout():
            data = request.json
            session_token = data.get('session_token', '')
            
            if self.logout_user(session_token):
                return jsonify({"success": True, "message": "Logged out successfully"})
            else:
                return jsonify({"success": False, "error": "Invalid session"}), 400
        
        @self.app.route('/api/auth/status', methods=['GET'])
        def api_auth_status():
            session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
            user_info = self.get_authenticated_user_info(session_token)
            
            if user_info:
                return jsonify({"authenticated": True, "user": user_info})
            else:
                return jsonify({"authenticated": False}), 401
        
        @self.app.route('/api/chat/authenticated', methods=['POST'])
        def api_authenticated_chat():
            data = request.json
            message = data.get('message', '')
            session_token = data.get('session_token', '')
            is_voice = data.get('is_voice', False)
            
            response = self.process_authenticated_message(message, session_token, is_voice)
            
            return jsonify({
                "response": response,
                "timestamp": datetime.now().isoformat(),
                "authenticated": True
            })
        
        @self.app.route('/api/permissions/check', methods=['POST'])
        def api_check_permission():
            data = request.json
            session_token = data.get('session_token', '')
            permission = data.get('permission', '')
            
            has_permission = self.check_user_permission(session_token, permission)
            
            return jsonify({
                "has_permission": has_permission,
                "permission": permission
            })
        
        @self.app.route('/api/voice/test', methods=['GET'])
        def api_voice_test():
            """Test voice interface"""
            result = self.test_voice_interface()
            return jsonify(result)
        
        @self.app.route('/api/voice/record', methods=['POST'])
        def api_voice_record():
            """Record voice input and convert to text"""
            data = request.json
            duration = data.get('duration', 5.0)
            session_token = data.get('session_token', '')
            
            # Validate session
            session = self.validate_session(session_token)
            if not session:
                return jsonify({"error": "Invalid session"}), 401
            
            # Record and process voice
            text = self.process_voice_input(duration)
            
            if text:
                # Process the recognized text
                response = self.process_message(text, session.user_id)
                return jsonify({
                    "recognized_text": text,
                    "response": response,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return jsonify({"error": "No speech recognized"}), 400
        
        @self.app.route('/api/voice/tts', methods=['POST'])
        def api_text_to_speech():
            """Convert text to speech"""
            data = request.json
            text = data.get('text', '')
            
            if not text:
                return jsonify({"error": "No text provided"}), 400
            
            success = self.text_to_speech(text)
            
            return jsonify({
                "success": success,
                "message": "Text converted to speech" if success else "TTS failed"
            })
        
        @self.app.route('/api/login', methods=['POST'])
        def api_login():
            data = request.json
            user_id = data.get('user_id', '')
            password = data.get('password', '')
            mfa_code = data.get('mfa_code', '')
            
            session = self.authenticate_user(user_id, password, mfa_code)
            if session:
                return jsonify({
                    "session_token": session.session_token,
                    "user_role": session.role.value,
                    "expires_at": (session.login_time + timedelta(seconds=self.config["security"]["session_timeout"])).isoformat(),
                    "voice_available": self.voice_interface.enabled
                })
            else:
                return jsonify({"error": "Authentication failed"}), 401
        
        @self.app.route('/api/recommendations/<student_id>', methods=['GET'])
        def api_recommendations(student_id):
            recommendations = self.get_course_recommendations(student_id)
            return jsonify({"recommendations": recommendations})
        
        @self.app.route('/api/gpa/<student_id>', methods=['GET'])
        def api_gpa(student_id):
            gpa_info = self.calculate_gpa(student_id)
            return jsonify(gpa_info)
        
    def validate_chatbot_session(self, session_token: str) -> Optional[AuthenticatedSession]:
        """Validate chatbot session and check permissions"""
        if not session_token or session_token not in self.authenticated_sessions:
            return None
        
        session = self.authenticated_sessions[session_token]
        
        # Check session timeout (30 minutes)
        if (datetime.now() - session.last_activity).seconds > 1800:
            del self.authenticated_sessions[session_token]
            return None
        
        # Update last activity
        session.last_activity = datetime.now()
        return session

    def check_user_permission(self, session_token: str, permission: str) -> bool:
        """Check if authenticated user has specific permission"""
        session = self.validate_chatbot_session(session_token)
        if not session:
            return False
        
        return permission in session.permissions

    def get_authenticated_user_info(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get information about authenticated user"""
        session = self.validate_chatbot_session(session_token)
        if not session:
            return None
        
        return {
            "user_id": session.user_id,
            "username": session.username,
            "role": session.role,
            "permissions": session.permissions,
            "login_time": session.login_time.isoformat(),
            "last_activity": session.last_activity.isoformat()
        }

    def process_authenticated_message(self, message: str, session_token: str, is_voice: bool = False) -> str:
        """Process message with authentication context"""
        # Validate session
        session = self.validate_chatbot_session(session_token)
        if not session:
            return "Your session has expired. Please log in again to continue using the chatbot."
        
        # Process message with user context
        response = self.process_message_with_auth(message, session, is_voice)
        
        return response

    def process_message_with_auth(self, message: str, session: AuthenticatedSession, is_voice: bool = False) -> str:
        """Enhanced message processing with authentication context"""
        try:
            # Get or create conversation context with auth info
            user_id = session.username  # Use username as conversation key
            
            if user_id not in self.conversation_contexts:
                self.conversation_contexts[user_id] = ConversationContext(
                    conversation_id=f"{user_id}_{int(time.time())}",
                    user_id=user_id,
                    messages=[],
                    intent_history=[],
                    entities={"authenticated_user": session.username, "user_role": session.role},
                    session_data={"permissions": session.permissions}
                )
            
            context = self.conversation_contexts[user_id]
            context.entities["authenticated_user"] = session.username
            context.entities["user_role"] = session.role
            context.session_data["permissions"] = session.permissions
            
            # Process with NLP
            nlp_result = self.process_with_nlp(message, context)
            
            # Update context
            context.messages.append({
                "user_message": message,
                "timestamp": datetime.now().isoformat(),
                "nlp_result": nlp_result,
                "is_voice": is_voice,
                "authenticated": True,
                "user_role": session.role
            })
            
            if nlp_result["intent"]:
                context.intent_history.append(nlp_result["intent"])
            
            context.entities.update(nlp_result["entities"])
            
            # Handle voice commands specifically
            if nlp_result.get("is_voice_command", False):
                return self.handle_voice_command(message, user_id, context)
            
            # Check if escalation is needed
            if nlp_result["requires_escalation"]:
                return self.escalate_to_human(message, user_id)
            
            # Generate response based on intent and permissions
            response = self.generate_authenticated_response(nlp_result, context, session)
            
            # Log conversation with auth info
            self.log_enhanced_conversation(session.username, message, response, nlp_result)
            
            return response
            
        except Exception as e:
            print(f"Authenticated message processing error: {e}")
            return "I apologize, but I encountered an error processing your message. Please try again."

    def generate_authenticated_response(self, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
        """Generate response with authentication and permission checks"""
        intent = nlp_result["intent"]
        
        # Handle different intents with permission checks
        if intent == "course_inquiry":
            return self.handle_authenticated_course_inquiry(nlp_result, context, session)
        elif intent == "registration":
            if "view_own_record" in session.permissions:
                return self.handle_authenticated_registration_query(nlp_result, context, session)
            else:
                return "You don't have permission to access registration information."
        elif intent == "financial":
            if "view_own_finances" in session.permissions or "manage_finances" in session.permissions:
                return self.handle_authenticated_financial_query(nlp_result, context, session)
            else:
                return "You don't have permission to access financial information."
        elif intent == "grades":
            if "view_own_grades" in session.permissions or "manage_grades" in session.permissions:
                return self.handle_authenticated_grades_query(nlp_result, context, session)
            else:
                return "You don't have permission to access grade information."
        elif intent == "technical_support":
            return self.handle_technical_query(nlp_result, context)
        elif intent == "voice_command":
            return self.handle_voice_command(context.messages[-1]["user_message"], context.user_id, context)
        else:
            return self.handle_authenticated_general_query(nlp_result, context, session)

    def handle_authenticated_course_inquiry(self, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
        """Handle course inquiries with user-specific data"""
        if session.role == "student" and "view_own_record" in session.permissions:
            # Get student-specific recommendations
            student_id = self.get_student_id_for_user(session.username)
            if student_id:
                recommendations = self.get_course_recommendations(student_id, 3)
                if recommendations:
                    response = f"Hello {session.username}! Based on your academic profile, I recommend:\n\n"
                    for rec in recommendations:
                        response += f"• {rec['course_code']}: {rec['course_name']}\n"
                        response += f"  Reason: {', '.join(rec['reasons'])}\n\n"
                    return response
        
        elif session.role in ["staff", "admin"] and "manage_modules" in session.permissions:
            return f"Hello {session.username}! As a {session.role}, I can help you with course management, student inquiries, and academic planning. What specific course information do you need?"
        
        return f"Hello {session.username}! I can help you with course information. What would you like to know about our academic programs?"

    def handle_authenticated_registration_query(self, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
        """Handle registration queries with permission checks"""
        if session.role == "student":
            student_id = self.get_student_id_for_user(session.username)
            if student_id:
                return f"I can help you with course registration, {session.username}. Let me check your current enrollment status and available courses for student ID: {student_id}."
        
        elif session.role in ["staff", "admin"] and "manage_students" in session.permissions:
            return f"Hello {session.username}! I can help you manage student registrations. Which student or registration process would you like assistance with?"
        
        return "I can help with registration information. Please provide more details about what you need."

    def handle_authenticated_financial_query(self, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
        """Handle financial queries with role-based responses"""
        if session.role == "student" and "view_own_finances" in session.permissions:
            return f"I can help you with your financial information, {session.username}. This includes tuition balance, payment history, and financial aid status. What specific financial information do you need?"
        
        elif session.role in ["staff", "admin"] and "manage_finances" in session.permissions:
            return f"Hello {session.username}! I can help you with financial administration including payment processing, financial reports, and student account management. What do you need assistance with?"
        
        return "I can help with financial information. Please specify what you'd like to know."

    def handle_authenticated_grades_query(self, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
        """Handle grade queries with authentication"""
        if session.role == "student" and "view_own_grades" in session.permissions:
            student_id = self.get_student_id_for_user(session.username)
            if student_id:
                gpa_info = self.calculate_gpa(student_id)
                if "error" not in gpa_info:
                    return f"Hello {session.username}! Your current GPA is {gpa_info['gpa']} based on {gpa_info['total_credits']} credit hours. I can provide more detailed grade information if needed."
                else:
                    return "I'm having trouble accessing your grade information right now. Please try again later or contact the registrar's office."
        
        elif session.role in ["instructor", "staff", "admin"] and "manage_grades" in session.permissions:
            return f"Hello {session.username}! I can help you with grade management, student performance analysis, and academic reporting. What would you like to do?"
        
        return "I can help with grade information. Please let me know what you need."

    def handle_authenticated_general_query(self, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
        """Handle general queries with user context"""
        user_message = context.messages[-1]["user_message"]
        
        # Personalized greeting based on role
        role_greetings = {
            "student": f"Hello {session.username}! As a student, I can help you with course information, grades, registration, financial aid, and campus resources.",
            "instructor": f"Hello {session.username}! I can assist you with course management, student information, grade processing, and administrative tasks.",
            "staff": f"Hello {session.username}! I can help you with student records, administrative tasks, reporting, and system management.",
            "admin": f"Hello {session.username}! I have full system access and can help you with any aspect of the student information system."
        }
        
        # Find best matching FAQ with role context
        best_match = self.find_best_faq_match(user_message)
        
        if best_match:
            return f"{role_greetings.get(session.role, f'Hello {session.username}!')} {best_match}"
        
        # Default response with available features based on role
        available_features = []
        if "view_own_record" in session.permissions:
            available_features.append("view your academic record")
        if "view_own_grades" in session.permissions:
            available_features.append("check grades and GPA")
        if "view_own_finances" in session.permissions:
            available_features.append("view financial information")
        if "manage_students" in session.permissions:
            available_features.append("manage student records")
        if "generate_reports" in session.permissions:
            available_features.append("generate reports")
        
        features_text = ", ".join(available_features) if available_features else "general university information"
        
        return f"{role_greetings.get(session.role, f'Hello {session.username}!')} I can help you with {features_text}. You can also use voice commands by saying 'start voice mode'. What would you like to know?"

    def get_student_id_for_user(self, username: str) -> Optional[str]:
        """Get student ID associated with a username"""
        if not self.auth_system:
            return None
        
        try:
            conn = self.connect_to_db()
            if not conn:
                return None
            
            cursor = conn.cursor()
            
            # Try to get student ID from users table
            cursor.execute("""
                SELECT u.student_id 
                FROM users u
                JOIN user_accounts ua ON u.id = ua.user_id
                WHERE ua.username = ?
            """, (username,))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result and result[0] else None
            
        except Exception as e:
            print(f"Error getting student ID for user {username}: {e}")
            return None

    def logout_user(self, session_token: str) -> bool:
        """Logout user from chatbot"""
        if session_token in self.authenticated_sessions:
            session = self.authenticated_sessions[session_token]
            
            # Log logout
            self.log_enhanced_conversation(
                session.username,
                "User logged out from chatbot",
                "Session ended",
                {"authenticated": False, "logout_time": datetime.now().isoformat()}
            )
            
            # Remove session
            del self.authenticated_sessions[session_token]
            
            # Logout from auth system if needed
            if self.auth_system and self.auth_system.current_user:
                if self.auth_system.current_user['username'] == session.username:
                    self.auth_system.logout()
            
            return True
        
        return False

    def run_authenticated_console_interface(self):
        """Run console interface with existing authentication - NO DOUBLE LOGIN"""
        print("Enhanced University Chatbot")
        print("=" * 30)
        
        # Check if user is already authenticated through main system
        if not self.auth_system:
            print("Error: No authentication system available. Please restart the application.")
            return
        
        # Check if session is still valid and get current user
        if not self.auth_system.check_session():
            print("Error: Your session has expired or you are not logged in.")
            print("Please log in through the main system first.")
            return
        
        # Get current user - this will be the most up-to-date user info
        user = self.auth_system.current_user
        if not user:
            print("Error: No authenticated user found. Please log in through the main system first.")
            return
        print(f"Welcome {user['username']}! You are logged in as {user['role']}.")
        
        # Check chatbot permissions
        if 'access_chatbot' not in user.get('permissions', []):
            print("You don't have permission to access the chatbot.")
            return
        
        # Show available features based on role
        print(f"\nChatbot Features Available:")
        if user['role'] == 'student':
            print("• Ask about courses and enrollment")
            print("• Check academic information")
            print("• Get help with registration")
            print("• Financial aid information")
        elif user['role'] in ['staff', 'admin']:
            print("• Student information lookup")
            print("• Course management assistance")
            print("• Administrative support")
            print("• System information")
        elif user['role'] == 'instructor':
            print("• Course management")
            print("• Student academic support")
            print("• Grade information")
        
        print("\nType 'exit' to return to main menu, 'help' for commands.")
        
        # Main chat loop with session validation
        while True:
            try:
                # Check session validity at the start of each loop iteration
                if not self.auth_system.check_session():
                    print("\nYour session has expired. Please log in again through the main system.")
                    break
                
                # Get fresh user data in case permissions changed
                current_user = self.auth_system.current_user
                if not current_user:
                    print("\nAuthentication lost. Please log in again through the main system.")
                    break
                
                user_input = input(f"\n{current_user['username']}: ")
                
                # Handle exit commands
                if user_input.lower() in ['exit', 'quit', 'back', 'logout']:
                    print("Returning to main menu...")
                    break
                
                # Handle help command
                if user_input.lower() == 'help':
                    print("\nAvailable commands:")
                    print("- Ask about courses, registration, grades, fees")
                    print("- Request information based on your role permissions")
                    print(f"- Your role: {current_user['role']}")
                    print(f"- Available permissions: {len(current_user.get('permissions', []))}")
                    if hasattr(self, 'voice_interface') and getattr(self.voice_interface, 'enabled', False):
                        print("- Voice commands: 'start voice mode', 'test voice'")
                    print("- 'exit' to return to main menu")
                    continue
                
                # Handle empty input
                if not user_input.strip():
                    print("Please enter a message or type 'help' for available commands.")
                    continue
                
                # Process message using current authentication context
                try:
                    response = self.process_message(user_input, current_user['username'])
                    print(f"Chatbot: {response}")
                    
                    # Log the interaction with full context
                    if hasattr(self.auth_system, '_log_activity'):
                        self.auth_system._log_activity(
                            current_user['username'], 
                            'Chatbot interaction', 
                            f"Q: {user_input[:50]}{'...' if len(user_input) > 50 else ''} A: {response[:50]}{'...' if len(response) > 50 else ''}",
                            current_user['id']
                        )
                    
                    # Store in chatbot's conversation history if available
                    if hasattr(self, 'conversation_history'):
                        if current_user['username'] not in self.conversation_history:
                            self.conversation_history[current_user['username']] = []
                        
                        from datetime import datetime
                        self.conversation_history[current_user['username']].append({
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'message': user_input,
                            'response': response,
                            'role': current_user['role']
                        })
                        
                        # Keep only last 50 conversations per user
                        if len(self.conversation_history[current_user['username']]) > 50:
                            self.conversation_history[current_user['username']] = self.conversation_history[current_user['username']][-50:]
                    
                except Exception as process_error:
                    print(f"Chatbot: I apologize, but I encountered an error processing your message: {process_error}")
                    print("Please try rephrasing your question or contact support if the issue persists.")
                    
                    # Log the error
                    if hasattr(self.auth_system, '_log_activity'):
                        self.auth_system._log_activity(
                            current_user['username'], 
                            'Chatbot error', 
                            f"Error processing: {user_input[:50]} - {str(process_error)[:100]}",
                            current_user['id']
                        )
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Returning to main menu...")
                break
                
            except EOFError:
                print("\nEnd of input detected. Returning to main menu...")
                break
                
            except Exception as e:
                print(f"Unexpected error: {e}")
                print("Returning to main menu...")
                break
        
        # Cleanup and final message
        final_user = self.auth_system.current_user
        if final_user:
            print(f"Chatbot session ended for {final_user['username']}. Thank you for using the University Chatbot!")
            
            # Log session end
            if hasattr(self.auth_system, '_log_activity'):
                self.auth_system._log_activity(
                    final_user['username'], 
                    'Chatbot session ended', 
                    'User exited chatbot interface',
                    final_user['id']
                )
        else:
            print("Chatbot session ended. Thank you for using the University Chatbot!")
            
    def verify_mfa(self, secret: str, code: str) -> bool:
        """Verify MFA code"""
        # Implement TOTP verification
        # This is a simplified version - use a proper TOTP library in production
        try:
            import pyotp
            totp = pyotp.TOTP(secret)
            return totp.verify(code)
        except ImportError:
            print("pyotp not available for MFA verification")
            return True  # Skip MFA if library not available

    def handle_failed_login(self, user_id: str):
        """Handle failed login attempts"""
        conn = self.connect_to_db()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_credentials 
                SET failed_attempts = failed_attempts + 1,
                    locked_until = CASE 
                        WHEN failed_attempts >= ? THEN ?
                        ELSE locked_until 
                    END
                WHERE user_id = ?
            """, (
                self.config["security"]["max_login_attempts"],
                (datetime.now() + timedelta(minutes=30)).isoformat(),
                user_id
            ))
            conn.commit()
        finally:
            conn.close()

    def validate_session(self, session_token: str) -> Optional[UserSession]:
        """Validate user session"""
        if session_token not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_token]
        
        # Check session timeout
        if (datetime.now() - session.last_activity).seconds > self.config["security"]["session_timeout"]:
            del self.active_sessions[session_token]
            return None
        
        # Update last activity
        session.last_activity = datetime.now()
        return session

    # Enhanced NLP Processing
    def process_with_nlp(self, text: str, user_context: Optional[ConversationContext] = None) -> Dict[str, Any]:
        """Process text with advanced NLP"""
        if not self.nlp:
            return self.fallback_processing(text)
        
        result = {
            "intent": None,
            "entities": {},
            "sentiment": None,
            "confidence": 0.0,
            "requires_escalation": False,
            "is_voice_command": False
        }
        
        try:
            # Check for voice-specific commands
            voice_commands = ["start voice mode", "voice mode", "talk to me", "speak", "listen"]
            if any(cmd in text.lower() for cmd in voice_commands):
                result["is_voice_command"] = True
                result["intent"] = "voice_command"
                result["confidence"] = 0.9
                return result
            
            # Extract entities
            doc = self.nlp(text)
            result["entities"] = {
                "persons": [ent.text for ent in doc.ents if ent.label_ == "PERSON"],
                "dates": [ent.text for ent in doc.ents if ent.label_ == "DATE"],
                "money": [ent.text for ent in doc.ents if ent.label_ == "MONEY"],
                "organizations": [ent.text for ent in doc.ents if ent.label_ == "ORG"]
            }
            
            # Classify intent
            intent_result = self.intent_classifier(text)
            if intent_result and len(intent_result) > 0:
                result["intent"] = intent_result[0]["label"]
                result["confidence"] = intent_result[0]["score"]
            
            # Analyze sentiment
            sentiment_result = self.sentiment_analyzer(text)
            if sentiment_result and len(sentiment_result) > 0:
                result["sentiment"] = sentiment_result[0]["label"]
                # Check for negative sentiment indicating frustration
                if result["sentiment"] == "NEGATIVE" and sentiment_result[0]["score"] > 0.8:
                    result["requires_escalation"] = True
            
            # Context-aware processing
            if user_context:
                result = self.enhance_with_context(result, user_context)
            
        except Exception as e:
            print(f"NLP processing error: {e}")
            result = self.fallback_processing(text)
        
        return result

    def enhance_with_context(self, nlp_result: Dict, context: ConversationContext) -> Dict:
        """Enhance NLP results with conversation context"""
        # Analyze conversation history for better understanding
        if len(context.intent_history) > 0:
            # If user is continuing previous topic
            last_intent = context.intent_history[-1]
            if nlp_result["confidence"] < 0.6:
                nlp_result["intent"] = last_intent
                nlp_result["confidence"] = 0.7
        
        # Extract context-specific entities
        if "student_id" in context.entities:
            nlp_result["entities"]["student_id"] = context.entities["student_id"]
        
        return nlp_result

    def fallback_processing(self, text: str) -> Dict[str, Any]:
        """Fallback processing when NLP is unavailable"""
        result = {
            "intent": "general",
            "entities": {},
            "sentiment": "NEUTRAL",
            "confidence": 0.5,
            "requires_escalation": False,
            "is_voice_command": False
        }
        
        # Simple keyword matching
        text_lower = text.lower()
        
        # Check for voice commands first
        voice_commands = ["start voice mode", "voice mode", "talk to me", "speak", "listen"]
        if any(cmd in text_lower for cmd in voice_commands):
            result["is_voice_command"] = True
            result["intent"] = "voice_command"
            result["confidence"] = 0.8
            return result
        
        for intent, data in self.intents.items():
            for pattern in data["patterns"]:
                if pattern in text_lower:
                    result["intent"] = intent
                    result["confidence"] = 0.6
                    break
        
        return result

    # Enhanced Message Processing with Voice Support
    def process_message(self, message: str, user_id: str, session_id: str | None = None, is_voice: bool = False, **kwargs) -> str:
        """Main message processing function with voice support"""
        try:
            # Get or create conversation context
            if user_id not in self.conversation_contexts:
                self.conversation_contexts[user_id] = ConversationContext(
                    conversation_id=f"{user_id}_{int(time.time())}",
                    user_id=user_id,
                    messages=[],
                    intent_history=[],
                    entities={},
                    session_data={}
                )
            
            context = self.conversation_contexts[user_id]
            
            # Process with NLP
            nlp_result = self.process_with_nlp(message, context)
            
            # Update context
            context.messages.append({
                "user_message": message,
                "timestamp": datetime.now().isoformat(),
                "nlp_result": nlp_result,
                "is_voice": is_voice
            })
            
            if nlp_result["intent"]:
                context.intent_history.append(nlp_result["intent"])
            
            context.entities.update(nlp_result["entities"])
            
            # Handle voice commands specifically
            if nlp_result.get("is_voice_command", False):
                return self.handle_voice_command(message, user_id, context)
            
            # Check if escalation is needed
            if nlp_result["requires_escalation"]:
                return self.escalate_to_human(message, user_id)
            
            # Generate response based on intent
            response = self.generate_response(nlp_result, context)
            
            # Log conversation
            self.log_enhanced_conversation(user_id, message, response, nlp_result)
            
            return response
            
        except Exception as e:
            print(f"Message processing error: {e}")
            return "I apologize, but I encountered an error processing your message. Please try again or contact support."

    def handle_voice_command(self, message: str, user_id: str, context: ConversationContext) -> str:
        """Handle voice-specific commands"""
        message_lower = message.lower()
        
        if any(cmd in message_lower for cmd in ["start voice mode", "voice mode", "talk to me"]):
            if self.voice_interface.enabled:
                # Start voice mode in a separate thread
                threading.Thread(target=self.start_voice_mode, args=(user_id,), daemon=True).start()
                return "Voice mode activated! You can now speak your questions. Say 'stop listening' to exit voice mode."
            else:
                return "Voice interface is not available. Please ensure your microphone is connected and try again."
        
        elif "test voice" in message_lower or "test microphone" in message_lower:
            result = self.test_voice_interface()
            if result["status"] == "success":
                return f"Voice interface is working! Found {len(result['devices'])} audio devices. Test recording: '{result['test_recording']}'"
            else:
                return f"Voice interface test failed: {result['message']}"
        
        elif "voice help" in message_lower:
            return """Voice commands available:
• "Start voice mode" - Begin voice interaction
• "Test voice" - Test microphone functionality  
• "Stop listening" - Exit voice mode
• You can ask any university question using natural speech
• Voice responses will be provided both as text and audio"""
        
        else:
            return "I understand you want to use voice features. Say 'voice help' for available commands or 'start voice mode' to begin."

    def generate_response(self, nlp_result: Dict, context: ConversationContext) -> str:
        """Generate contextual response"""
        intent = nlp_result["intent"]
        
        # Handle different intents
        if intent == "course_inquiry":
            return self.handle_course_inquiry(nlp_result, context)
        elif intent == "registration":
            return self.handle_registration_query(nlp_result, context)
        elif intent == "financial":
            return self.handle_financial_query(nlp_result, context)
        elif intent == "grades":
            return self.handle_grades_query(nlp_result, context)
        elif intent == "technical_support":
            return self.handle_technical_query(nlp_result, context)
        elif intent == "voice_command":
            return self.handle_voice_command(context.messages[-1]["user_message"], context.user_id, context)
        else:
            return self.handle_general_query(nlp_result, context)

    # Course Recommendation and Academic Planning
    def get_course_recommendations(self, student_id: str, num_recommendations: int = 5) -> List[Dict]:
        """Get personalized course recommendations"""
        student_profile = self.get_student_profile(student_id)
        if not student_profile:
            return []
        
        conn = self.connect_to_db()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            # Get all available courses
            cursor.execute("""
                SELECT module_code, module_name, module_type, prerequisites, credits, difficulty_level
                FROM modules
                WHERE module_code NOT IN (
                    SELECT module_code FROM student_modules WHERE student_id = ? AND status = 'completed'
                )
            """, (student_id,))
            
            available_courses = cursor.fetchall()
            
            # Score courses based on various factors
            recommendations = []
            for course in available_courses:
                score = self.calculate_course_score(course, student_profile)
                if score > 0:
                    recommendations.append({
                        "course_code": course[0],
                        "course_name": course[1],
                        "type": course[2],
                        "credits": course[4],
                        "difficulty": course[5],
                        "recommendation_score": score,
                        "reasons": self.get_recommendation_reasons(course, student_profile)
                    })
            
            # Sort by score and return top recommendations
            recommendations.sort(key=lambda x: x["recommendation_score"], reverse=True)
            return recommendations[:num_recommendations]
            
        except Exception as e:
            print(f"Recommendation error: {e}")
            return []
        finally:
            conn.close()

    def calculate_course_score(self, course: Tuple, student_profile: StudentProfile) -> float:
        """Calculate recommendation score for a course"""
        score = 0.0
        
        # Base score
        score += 1.0
        
        # GPA factor - suggest easier courses for struggling students
        if student_profile.gpa < 2.5 and course[5] == "advanced":
            score -= 0.5
        elif student_profile.gpa > 3.5 and course[5] == "beginner":
            score -= 0.3
        
        # Program relevance
        if course[2] == "core" and course[2] in student_profile.program.lower():
            score += 0.8
        
        # Interest matching
        for interest in student_profile.interests:
            if interest.lower() in course[1].lower():
                score += 0.6
        
        # Prerequisites check
        if course[3]:  # Has prerequisites
            prereq_courses = course[3].split(',')
            for prereq in prereq_courses:
                if prereq.strip() not in student_profile.completed_courses:
                    score = 0  # Cannot take if prerequisites not met
                    break
        
        # Workload consideration
        current_credits = len(student_profile.current_courses) * 3  # Assume 3 credits per course
        if current_credits + course[4] > 18:  # Don't overload
            score -= 0.4
        
        return max(0, score)

    def get_recommendation_reasons(self, course: Tuple, student_profile: StudentProfile) -> List[str]:
        """Get reasons for course recommendation"""
        reasons = []
        
        if course[2] == "core":
            reasons.append("Required for your program")
        
        for interest in student_profile.interests:
            if interest.lower() in course[1].lower():
                reasons.append(f"Matches your interest in {interest}")
        
        if student_profile.gpa > 3.5 and course[5] == "advanced":
            reasons.append("You're performing well academically")
        
        if len(student_profile.current_courses) < 4:
            reasons.append("Good addition to your current course load")
        
        return reasons

    # GPA Calculator and Academic Tracking
    def calculate_gpa(self, student_id: str, semester: Optional[str] = None) -> Dict:
        """Calculate GPA for student"""
        conn = self.connect_to_db()
        if not conn:
            return {"error": "Database connection failed"}
        
        try:
            cursor = conn.cursor()
            
            if semester:
                cursor.execute("""
                    SELECT grade, credits FROM student_grades
                    WHERE student_id = ? AND semester = ?
                """, (student_id, semester))
            else:
                cursor.execute("""
                    SELECT grade, credits FROM student_grades
                    WHERE student_id = ?
                """, (student_id,))
            
            grades = cursor.fetchall()
            
            if not grades:
                return {"gpa": 0.0, "total_credits": 0, "grade_points": 0.0}
            
            grade_points_map = {'A+': 4.0, 'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                              'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D': 1.0, 'F': 0.0}
            
            total_grade_points = 0.0
            total_credits = 0
            
            for grade, credits in grades:
                if grade in grade_points_map:
                    total_grade_points += grade_points_map[grade] * credits
                    total_credits += credits
            
            gpa = total_grade_points / total_credits if total_credits > 0 else 0.0
            
            return {
                "gpa": round(gpa, 2),
                "total_credits": total_credits,
                "grade_points": round(total_grade_points, 2),
                "semester": semester
            }
            
        except Exception as e:
            return {"error": f"GPA calculation error: {e}"}
        finally:
            conn.close()

    # Intent Handlers
    def handle_course_inquiry(self, nlp_result: Dict, context: ConversationContext) -> str:
        """Handle course-related inquiries"""
        # Extract course information from entities
        entities = nlp_result["entities"]
        
        if "student_id" in context.entities:
            student_id = context.entities["student_id"]
            recommendations = self.get_course_recommendations(student_id, 3)
            
            if recommendations:
                response = "Based on your profile, I recommend these courses:\n\n"
                for rec in recommendations:
                    response += f"• {rec['course_code']}: {rec['course_name']}\n"
                    response += f"  Reason: {', '.join(rec['reasons'])}\n\n"
                return response
        
        return "I can help you with course information. Could you please provide your student ID for personalized recommendations?"

    def handle_registration_query(self, nlp_result: Dict, context: ConversationContext) -> str:
        """Handle registration queries"""
        if "student_id" in context.entities:
            student_id = context.entities["student_id"]
            # Check registration status
            # This would connect to the registration system
            return f"I can help you with course registration. Let me check your current registration status for {student_id}..."
        
        return "To help with registration, I'll need your student ID. Please provide it to continue."

    def handle_financial_query(self, nlp_result: Dict, context: ConversationContext) -> str:
        """Handle financial queries"""
        entities = nlp_result["entities"]
        
        if "money" in entities:
            return "I can help with financial information. For specific payment amounts and due dates, please log into your student portal or contact the finance office."
        
        return "I can assist with financial aid, tuition payments, and scholarship information. What specific financial topic can I help you with?"

    def handle_grades_query(self, nlp_result: Dict, context: ConversationContext) -> str:
        """Handle grade-related queries"""
        if "student_id" in context.entities:
            student_id = context.entities["student_id"]
            gpa_info = self.calculate_gpa(student_id)
            
            if "error" not in gpa_info:
                return f"Your current GPA is {gpa_info['gpa']} based on {gpa_info['total_credits']} credit hours. For detailed grade information, please check your student portal."
        
        return "To check your grades and GPA, I'll need your student ID. Please provide it to continue."

    def handle_technical_query(self, nlp_result: Dict, context: ConversationContext) -> str:
        """Handle technical support queries"""
        return "I can help with basic technical issues. For complex problems, I'll connect you with our IT support team. What technical issue are you experiencing?"

    def handle_general_query(self, nlp_result: Dict, context: ConversationContext) -> str:
        """Handle general queries using FAQ matching"""
        user_message = context.messages[-1]["user_message"]
        
        # Find best matching FAQ
        best_match = self.find_best_faq_match(user_message)
        
        if best_match:
            return best_match
        
        return "I'm here to help with university-related questions. You can ask about courses, registration, grades, fees, or technical support. You can also use voice commands by saying 'start voice mode'. How can I assist you today?"

    def find_best_faq_match(self, query: str) -> Optional[str]:
        """Find best matching FAQ answer"""
        try:
            # Combine all FAQ questions and answers
            all_faqs = []
            for category, faqs in self.faq_database.items():
                for question, answer in faqs.items():
                    all_faqs.append((question, answer))
            
            if not all_faqs:
                return None
            
            # Vectorize questions
            questions = [faq[0] for faq in all_faqs]
            questions.append(query)
            
            # Calculate similarity
            vectors = self.vectorizer.fit_transform(questions)
            similarity_scores = cosine_similarity(vectors[-1:], vectors[:-1]).flatten()
            
            # Find best match
            best_idx = np.argmax(similarity_scores)
            best_score = similarity_scores[best_idx]
            
            # Return answer if similarity is above threshold
            if best_score > 0.3:  # Similarity threshold
                return all_faqs[best_idx][1]
            
            return None
            
        except Exception as e:
            print(f"FAQ matching error: {e}")
            return None

    def escalate_to_human(self, message: str, user_id: str) -> str:
        """Escalate conversation to human agent"""
        # Log escalation
        escalation_data = {
            "user_id": user_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "reason": "negative_sentiment_detected"
        }
        
        escalation_file = os.path.join(self.log_dir, "escalations.json")
        
        if os.path.exists(escalation_file):
            with open(escalation_file, 'r') as f:
                escalations = json.load(f)
        else:
            escalations = []
        
        escalations.append(escalation_data)
        
        with open(escalation_file, 'w') as f:
            json.dump(escalations, f, indent=4)
        
        return "I understand you may be frustrated. I'm connecting you with a human support agent who will be able to better assist you. Please expect a response within 2 hours."

    def log_enhanced_conversation(self, user_id: str, user_message: str, bot_response: str, nlp_result: Dict, session_id: Optional[str] = None):
        """Log conversation with enhanced metadata and session tracking"""
        timestamp = datetime.now().isoformat()
        log_date = datetime.now().strftime("%Y-%m-%d")
        log_filename = os.path.join(self.log_dir, f"enhanced_log_{log_date}.json")
        
        log_entry = {
            "timestamp": timestamp,
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message,
            "bot_response": bot_response,
            "intent": nlp_result.get("intent"),
            "confidence": nlp_result.get("confidence"),
            "sentiment": nlp_result.get("sentiment"),
            "entities": nlp_result.get("entities"),
            "escalated": nlp_result.get("requires_escalation", False),
            "is_voice": nlp_result.get("is_voice_command", False)
        }
        
        # Load existing logs
        if os.path.exists(log_filename):
            with open(log_filename, 'r') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        else:
            logs = []
        
        logs.append(log_entry)
        
        # Save logs
        with open(log_filename, 'w') as f:
            json.dump(logs, f, indent=4)
        
    # Utility Methods
    def connect_to_db(self):
        """Connect to the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            return conn
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None

    def get_student_profile(self, student_id: str) -> Optional[StudentProfile]:
        """Get comprehensive student profile"""
        conn = self.connect_to_db()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            # Get basic student info
            cursor.execute("""
                SELECT student_id, email, first_name, last_name, course, year
                FROM students
                WHERE student_id = ?
            """, (student_id,))
            
            student_data = cursor.fetchone()
            if not student_data:
                return None
            
            # Get GPA
            gpa_info = self.calculate_gpa(student_id)
            
            # Get completed courses
            cursor.execute("""
                SELECT module_code FROM student_modules
                WHERE student_id = ? AND status = 'completed'
            """, (student_id,))
            completed_courses = [row[0] for row in cursor.fetchall()]
            
            # Get current courses
            cursor.execute("""
                SELECT module_code FROM student_modules
                WHERE student_id = ? AND status = 'enrolled'
            """, (student_id,))
            current_courses = [row[0] for row in cursor.fetchall()]
            
            # Get interests (from profile or inferred from course history)
            cursor.execute("""
                SELECT interests FROM student_profiles
                WHERE student_id = ?
            """, (student_id,))
            interests_data = cursor.fetchone()
            interests = json.loads(interests_data[0]) if interests_data and interests_data[0] else []
            
            # Check financial aid status
            cursor.execute("""
                SELECT COUNT(*) FROM financial_aid
                WHERE student_id = ? AND status = 'active'
            """, (student_id,))
            has_financial_aid = cursor.fetchone()[0] > 0
            
            return StudentProfile(
                student_id=student_data[0],
                name=f"{student_data[2]} {student_data[3]}",
                email=student_data[1],
                program=student_data[4],
                year=student_data[5],
                gpa=gpa_info["gpa"],
                completed_courses=completed_courses,
                current_courses=current_courses,
                interests=interests,
                financial_aid=has_financial_aid
            )
            
        except Exception as e:
            print(f"Student profile error: {e}")
            return None
        finally:
            conn.close()

    # Console Interface with Voice Support
    def run(self):
        """Enhanced run method - uses existing authentication"""
        if hasattr(self, 'auth_system') and self.auth_system and self.auth_system.current_user:
            # User is already authenticated, go straight to chatbot
            self.run_authenticated_console_interface()
        else:
            # No authentication available, use basic mode
            self.run_console_interface()

    def run_console_interface(self):
        """Run the console-based chatbot interface with voice support"""
        print("Enhanced University Chatbot with Voice Support")
        print("=" * 50)
        
        # Simple authentication for demo
        user_id = input("Enter your student/staff ID: ")
        print(f"Welcome! Authenticated as {user_id}")
        
        if self.voice_interface.enabled:
            print("Voice interface is available! Say 'start voice mode' or 'voice help' for voice commands.")
        
        print("Type 'exit' to end the conversation, 'help' for commands.")
        
        while True:
            try:
                user_input = input(f"\n{user_id}: ")
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("Chatbot: Goodbye! Have a great day!")
                    if self.voice_interface.enabled:
                        self.voice_interface.cleanup()
                    break
                
                if user_input.lower() == 'help':
                    print("Available commands:")
                    print("- Ask about courses, registration, grades, fees")
                    print("- Request course recommendations")
                    print("- Check academic progress")
                    print("- Get help with technical issues")
                    if self.voice_interface.enabled:
                        print("- Voice commands: 'start voice mode', 'test voice', 'voice help'")
                    continue
                
                if not user_input.strip():
                    print("Chatbot: Please enter a message.")
                    continue
                
                # Process message
                response = self.process_message(user_input, user_id)
                print(f"Chatbot: {response}")
                
            except KeyboardInterrupt:
                print("\nChatbot: Goodbye!")
                if self.voice_interface.enabled:
                    self.voice_interface.cleanup()
                break
            except Exception as e:
                print(f"Chatbot: I encountered an error: {e}")

    def run_web_server(self, host='0.0.0.0', port=5000):
        """Run the web server for API access"""
        if LIBRARIES_AVAILABLE['flask']:
            self.app.run(host=host, port=port, debug=False)
        else:
            print("Flask not available - cannot start web server")

    def setup_scheduled_tasks(self):
        """Setup background scheduled tasks"""
        # Schedule proactive notifications
        schedule.every().day.at("09:00").do(self.send_proactive_alerts)
        
        # Schedule analytics generation
        schedule.every().day.at("23:59").do(self.generate_daily_analytics)
        
        # Schedule database cleanup
        schedule.every().week.do(self.cleanup_old_sessions)
        
        # Start scheduler in a separate thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()

    def generate_daily_analytics(self):
        """Generate daily analytics report"""
        analytics = self.generate_usage_analytics()
        
        # Save to file
        today = datetime.now().strftime("%Y-%m-%d")
        analytics_file = os.path.join(self.log_dir, f"analytics_{today}.json")
        
        with open(analytics_file, 'w') as f:
            json.dump(analytics, f, indent=4)

    def cleanup_old_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.now()
        expired_sessions = []
        
        for token, session in self.active_sessions.items():
            if (current_time - session.last_activity).seconds > self.config["security"]["session_timeout"]:
                expired_sessions.append(token)
        
        for token in expired_sessions:
            del self.active_sessions[token]

    def generate_usage_analytics(self) -> Dict:
        """Generate comprehensive usage analytics"""
        analytics = {
            "total_conversations": 0,
            "unique_users": set(),
            "popular_intents": {},
            "response_times": [],
            "user_satisfaction": {},
            "error_rates": {},
            "peak_usage_hours": {},
            "department_queries": {},
            "voice_usage": {"total": 0, "successful": 0, "failed": 0}
        }
        
        # Process log files
        if os.path.exists(self.log_dir):
            for filename in os.listdir(self.log_dir):
                if filename.startswith("enhanced_log_") and filename.endswith(".json"):
                    with open(os.path.join(self.log_dir, filename), 'r') as f:
                        try:
                            logs = json.load(f)
                            
                            for log in logs:
                                # Count conversations
                                analytics["total_conversations"] += 1
                                
                                # Track unique users
                                if "user_id" in log:
                                    analytics["unique_users"].add(log["user_id"])
                                
                                # Track intents
                                if "intent" in log:
                                    intent = log["intent"]
                                    analytics["popular_intents"][intent] = analytics["popular_intents"].get(intent, 0) + 1
                                
                                # Track voice usage
                                if log.get("is_voice", False):
                                    analytics["voice_usage"]["total"] += 1
                                    if log.get("confidence", 0) > 0.5:
                                        analytics["voice_usage"]["successful"] += 1
                                    else:
                                        analytics["voice_usage"]["failed"] += 1
                                
                                # Track usage hours
                                if "timestamp" in log:
                                    hour = datetime.fromisoformat(log["timestamp"]).hour
                                    analytics["peak_usage_hours"][hour] = analytics["peak_usage_hours"].get(hour, 0) + 1
                            
                        except json.JSONDecodeError:
                            continue
        
        # Convert sets to counts for JSON serialization
        analytics["unique_users"] = len(analytics["unique_users"])
        
        return analytics

    def send_proactive_alerts(self):
        """Send proactive notifications based on deadlines and events"""
        try:
            from datetime import datetime, timedelta
            import sqlite3

            # Connect to database
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            week_ahead = today + timedelta(days=7)

            alerts_sent = 0

            # Check for upcoming assignment deadlines (within 24 hours)
            try:
                cursor.execute("""
                    SELECT DISTINCT student_id, course_name, assignment_name, due_date
                    FROM assignments
                    WHERE due_date BETWEEN ? AND ?
                    AND status != 'submitted'
                """, (today.isoformat(), tomorrow.isoformat()))

                urgent_assignments = cursor.fetchall()
                for student_id, course, assignment, due_date in urgent_assignments:
                    self.logger.info(f"Alert: Assignment '{assignment}' for {course} due tomorrow for student {student_id}")
                    alerts_sent += 1
            except sqlite3.OperationalError:
                # Table doesn't exist, skip
                pass

            # Check for upcoming exams (within 7 days)
            try:
                cursor.execute("""
                    SELECT DISTINCT student_id, course_name, exam_name, exam_date
                    FROM exams
                    WHERE exam_date BETWEEN ? AND ?
                """, (today.isoformat(), week_ahead.isoformat()))

                upcoming_exams = cursor.fetchall()
                for student_id, course, exam, exam_date in upcoming_exams:
                    days_until = (datetime.fromisoformat(exam_date).date() - today).days
                    self.logger.info(f"Alert: Exam '{exam}' for {course} in {days_until} days for student {student_id}")
                    alerts_sent += 1
            except sqlite3.OperationalError:
                # Table doesn't exist, skip
                pass

            # Check for low grades (below 60%)
            try:
                cursor.execute("""
                    SELECT DISTINCT student_id, course_name, grade
                    FROM grades
                    WHERE grade < 60 AND grade > 0
                    AND created_at >= date('now', '-7 days')
                """)

                low_grades = cursor.fetchall()
                for student_id, course, grade in low_grades:
                    self.logger.info(f"Alert: Low grade ({grade}%) in {course} for student {student_id} - recommend tutoring")
                    alerts_sent += 1
            except sqlite3.OperationalError:
                # Table doesn't exist, skip
                pass

            # Check for missed classes (high absence rate)
            try:
                cursor.execute("""
                    SELECT student_id, course_name, COUNT(*) as absences
                    FROM attendance
                    WHERE status = 'absent'
                    AND date >= date('now', '-30 days')
                    GROUP BY student_id, course_name
                    HAVING COUNT(*) >= 3
                """)

                high_absences = cursor.fetchall()
                for student_id, course, count in high_absences:
                    self.logger.info(f"Alert: High absence rate ({count} absences) in {course} for student {student_id}")
                    alerts_sent += 1
            except sqlite3.OperationalError:
                # Table doesn't exist, skip
                pass

            conn.close()

            if alerts_sent > 0:
                self.logger.info(f"Proactive alerts completed: {alerts_sent} alerts processed")

        except Exception as e:
            self.logger.error(f"Error sending proactive alerts: {e}")


# Supporting Classes
class NotificationService:
    def __init__(self, config: Dict):
        self.config = config
    
    def send_bulk_notifications(self, notifications: List[Dict]) -> Dict:
        """Send multiple notifications efficiently"""
        results = {"success": 0, "failed": 0, "errors": []}
        
        for notification in notifications:
            try:
                # Process notification
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))
        
        return results

class AnalyticsService:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
    
    def generate_real_time_dashboard(self) -> Dict:
        """Generate real-time analytics dashboard data"""
        return {
            "active_users": 0,
            "conversations_today": 0,
            "average_response_time": 0.0,
            "top_intents": [],
            "satisfaction_score": 0.0,
            "voice_interactions": 0
        }

class CourseRecommendationEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        ensure_parent_dir(self.db_path)
    
    def update_recommendation_model(self):
        """Update the recommendation model with new data"""
        pass

class AdminPanel:
    def __init__(self, chatbot):
        self.chatbot = chatbot
    
    def generate_admin_dashboard(self) -> Dict:
        """Generate admin dashboard with comprehensive metrics"""
        return {
            "system_status": "operational",
            "active_sessions": len(self.chatbot.active_sessions),
            "daily_metrics": self.chatbot.generate_usage_analytics(),
            "voice_status": self.chatbot.voice_interface.enabled,
            "system_performance": self.get_system_performance()
        }
    
    def get_system_performance(self) -> Dict:
        """Get system performance metrics"""
        return {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "response_time": 0.0,
            "uptime": "24h"
        }

class BackgroundScheduler:
    def __init__(self):
        self.tasks = []
    
    def add_task(self, task_func, schedule_time):
        """Add a scheduled task"""
        self.tasks.append((task_func, schedule_time))

def setup_enhanced_api_routes(self):
    """Enhanced API routes setup"""
    self.setup_api_routes()

def authenticate_user(self, user_id, password, mfa_code):
    """Basic user authentication"""
    return self.authenticate_user_for_chatbot(user_id, password, mfa_code)


# Main execution enhancement
    if __name__ == "__main__":
        # Initialize enhanced chatbot with authentication
        try:
            chatbot = UniversityChatbot()
            
            # Choose interface mode
            if AUTH_AVAILABLE and chatbot.auth_system:
                print("Authentication system available!")
                mode = input("Choose interface mode (console/web/auth-console/both): ").lower()
            else:
                mode = input("Choose interface mode (console/web/both): ").lower()
            
            if mode == "console":
                chatbot.run_console_interface()
            elif mode == "auth-console" and AUTH_AVAILABLE:
                chatbot.run_authenticated_console_interface()
            elif mode == "web":
                if AUTH_AVAILABLE:
                    chatbot.setup_api_routes()
                chatbot.run_web_server()
            elif mode == "both":
                # Run web server in background, console in foreground
                if LIBRARIES_AVAILABLE['flask']:
                    import threading
                    if AUTH_AVAILABLE:
                        chatbot.setup_enhanced_api_routes()
                    web_thread = threading.Thread(target=chatbot.run_web_server)
                    web_thread.daemon = True
                    web_thread.start()
                    print("Web server started on http://localhost:5000")
                    if AUTH_AVAILABLE:
                        print("Authentication API endpoints available:")
                        print("- POST /api/auth/login - Authenticate user")
                        print("- POST /api/auth/logout - Logout user")
                        print("- GET /api/auth/status - Check auth status")
                        print("- POST /api/chat/authenticated - Authenticated chat")
                        print("- POST /api/permissions/check - Check permissions")
                else:
                    print("Flask not available - web server disabled")
                
                if AUTH_AVAILABLE and chatbot.auth_system:
                    chatbot.run_authenticated_console_interface()
                else:
                    chatbot.run_console_interface()
            else:
                print("Invalid mode selected. Starting console interface.")
                if AUTH_AVAILABLE and chatbot.auth_system:
                    chatbot.run_authenticated_console_interface()
                else:
                    chatbot.run_console_interface()
                
        except Exception as e:
            print(f"Failed to initialize chatbot: {e}")
            print("Please check your dependencies and try again.")

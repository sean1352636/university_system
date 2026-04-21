"""VoiceInterface class: low-level audio recording and speech recognition."""

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from education_system.university_system.infrastructure.ai.university_chatbot.fallbacks import (
    LIBRARIES_AVAILABLE,
    sr,
)

logger = logging.getLogger(__name__)


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
            'format': None,
            'threshold': 500,
            'silence_limit': 2,
            'prev_audio': 0.5
        }
        self.pyaudio_instance = None

    def initialize(self) -> bool:
        """Initialize voice recognition and synthesis with proper error handling"""
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
            import pyaudio
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

            with suppress_alsa_errors():
                self.pyaudio_instance = pyaudio.PyAudio()
                self.audio_config['format'] = pyaudio.paInt16
                device_count = self.pyaudio_instance.get_device_count()

            print(f"ℹ️  Found {device_count} audio devices")

            try:
                with suppress_alsa_errors():
                    default_device = self.pyaudio_instance.get_default_input_device_info()
                print(f"ℹ️  Default input device: {default_device['name']}")
            except Exception as e:
                print(f"⚠️  Warning: Could not detect default input device: {e}")
                print("ℹ️  Voice recording may not work properly")

            self.recognizer = sr.Recognizer()

            try:
                with suppress_alsa_errors():
                    self.microphone = sr.Microphone()
                    with self.microphone as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

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
                except Exception as e:
                    logger.debug(f"Failed to terminate PyAudio instance: {e}")
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

            try:
                with suppress_alsa_errors():
                    stream = self.pyaudio_instance.open(
                        format=self.audio_config['format'],
                        channels=self.audio_config['channels'],
                        rate=self.audio_config['sample_rate'],
                        input=True,
                        frames_per_buffer=self.audio_config['chunk_size'],
                        input_device_index=None
                    )
            except Exception as stream_error:
                print(f"❌ Audio recording error: {stream_error}")
                print("ℹ️  Voice input is not available on this system")
                self.enabled = False
                return None

            frames = []
            try:
                for _ in range(0, int(self.audio_config['sample_rate'] / self.audio_config['chunk_size'] * duration)):
                    with suppress_alsa_errors():
                        data = stream.read(self.audio_config['chunk_size'], exception_on_overflow=False)
                    frames.append(data)
            finally:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    logger.debug(f"Failed to cleanup audio stream: {e}")

            temp_filename = "temp_audio.wav"
            with wave.open(temp_filename, 'wb') as wf:
                wf.setnchannels(self.audio_config['channels'])
                wf.setsampwidth(self.pyaudio_instance.get_sample_size(self.audio_config['format']))
                wf.setframerate(self.audio_config['sample_rate'])
                wf.writeframes(b''.join(frames))

            with sr.AudioFile(temp_filename) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)

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

                        callback_func(text)

                    except sr.UnknownValueError:
                        pass

                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    print(f"Continuous listening error: {e}")
                    time.sleep(1)

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

"""
Voice Interface Module for University Chatbot

Provides voice input/output capabilities using speech recognition and text-to-speech.
Optional dependencies: SpeechRecognition, pyttsx3 (or gTTS), pyaudio
"""
import logging
from typing import Optional, Callable
import threading
import queue

logger = logging.getLogger(__name__)

# Track availability of voice libraries
_speech_recognition_available = False
_tts_available = False
_tts_engine = None

try:
    import speech_recognition as sr
    _speech_recognition_available = True
except ImportError:
    sr = None
    logger.debug("SpeechRecognition not installed - voice input disabled")

try:
    import pyttsx3
    _tts_available = True
    _tts_engine = "pyttsx3"
except ImportError:
    pyttsx3 = None
    try:
        from gtts import gTTS
        import io
        _tts_available = True
        _tts_engine = "gtts"
    except ImportError:
        gTTS = None
        logger.debug("No TTS engine available (pyttsx3 or gTTS) - voice output disabled")


class VoiceInterface:
    """Voice interface for speech recognition and text-to-speech."""

    def __init__(self,
                 on_speech_recognized: Optional[Callable[[str], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None):
        """Initialize the voice interface.

        Args:
            on_speech_recognized: Callback when speech is recognized
            on_error: Callback when an error occurs
        """
        self.on_speech_recognized = on_speech_recognized
        self.on_error = on_error
        self._listening = False
        self._listen_thread = None
        self._audio_queue = queue.Queue()

        # Initialize speech recognition
        self._recognizer = None
        self._microphone = None
        if _speech_recognition_available:
            try:
                self._recognizer = sr.Recognizer()
                self._microphone = sr.Microphone()
                # Adjust for ambient noise on init
                with self._microphone as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
            except Exception as e:
                logger.warning(f"Failed to initialize microphone: {e}")
                self._recognizer = None
                self._microphone = None

        # Initialize TTS
        self._tts = None
        if _tts_engine == "pyttsx3":
            try:
                self._tts = pyttsx3.init()
                # Configure voice settings
                self._tts.setProperty('rate', 175)  # Speed
                self._tts.setProperty('volume', 0.9)
            except Exception as e:
                logger.warning(f"Failed to initialize pyttsx3: {e}")

        logger.info(f"VoiceInterface initialized - Input: {self.is_input_available()}, "
                   f"Output: {self.is_output_available()}")

    def is_input_available(self) -> bool:
        """Check if voice input (speech recognition) is available."""
        return self._recognizer is not None and self._microphone is not None

    def is_output_available(self) -> bool:
        """Check if voice output (text-to-speech) is available."""
        return _tts_available

    def is_available(self) -> bool:
        """Check if any voice functionality is available."""
        return self.is_input_available() or self.is_output_available()

    def speak(self, text: str, block: bool = True) -> bool:
        """Convert text to speech.

        Args:
            text: Text to speak
            block: Whether to block until speech completes

        Returns:
            True if speech was initiated successfully
        """
        if not text or not self.is_output_available():
            return False

        try:
            if _tts_engine == "pyttsx3" and self._tts:
                if block:
                    self._tts.say(text)
                    self._tts.runAndWait()
                else:
                    # Run in background thread
                    def speak_async():
                        self._tts.say(text)
                        self._tts.runAndWait()
                    thread = threading.Thread(target=speak_async, daemon=True)
                    thread.start()
                return True

            elif _tts_engine == "gtts":
                # gTTS requires playing audio file
                try:
                    import pygame
                    tts = gTTS(text=text, lang='en')
                    audio_buffer = io.BytesIO()
                    tts.write_to_fp(audio_buffer)
                    audio_buffer.seek(0)

                    pygame.mixer.init()
                    pygame.mixer.music.load(audio_buffer)
                    pygame.mixer.music.play()

                    if block:
                        while pygame.mixer.music.get_busy():
                            pygame.time.wait(100)
                    return True
                except ImportError:
                    logger.warning("pygame not available for gTTS playback")
                    return False

        except Exception as e:
            logger.error(f"TTS error: {e}")
            if self.on_error:
                self.on_error(f"Speech output error: {e}")
            return False

        return False

    def listen(self, timeout: float = 5.0, phrase_limit: float = 10.0) -> Optional[str]:
        """Listen for speech and return recognized text.

        Args:
            timeout: Maximum seconds to wait for speech to start
            phrase_limit: Maximum seconds of speech to capture

        Returns:
            Recognized text or None if failed
        """
        if not self.is_input_available():
            return None

        try:
            with self._microphone as source:
                logger.debug("Listening for speech...")
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_limit
                )

            # Use Google's speech recognition (free tier)
            text = self._recognizer.recognize_google(audio)
            logger.debug(f"Recognized: {text}")

            if self.on_speech_recognized:
                self.on_speech_recognized(text)

            return text

        except sr.WaitTimeoutError:
            logger.debug("No speech detected within timeout")
            return None
        except sr.UnknownValueError:
            logger.debug("Speech was unintelligible")
            if self.on_error:
                self.on_error("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            if self.on_error:
                self.on_error(f"Speech recognition service unavailable: {e}")
            return None
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            if self.on_error:
                self.on_error(f"Voice input error: {e}")
            return None

    def start_continuous_listening(self,
                                   callback: Optional[Callable[[str], None]] = None,
                                   pause_threshold: float = 0.8) -> bool:
        """Start listening continuously in background.

        Args:
            callback: Function to call with recognized text
            pause_threshold: Seconds of silence to consider phrase complete

        Returns:
            True if listening started successfully
        """
        if not self.is_input_available() or self._listening:
            return False

        self._listening = True

        if callback:
            self.on_speech_recognized = callback

        self._recognizer.pause_threshold = pause_threshold

        def listen_loop():
            with self._microphone as source:
                while self._listening:
                    try:
                        audio = self._recognizer.listen(source, timeout=1.0)
                        try:
                            text = self._recognizer.recognize_google(audio)
                            if text and self.on_speech_recognized:
                                self.on_speech_recognized(text)
                        except sr.UnknownValueError:
                            pass  # Unintelligible, continue listening
                        except sr.RequestError as e:
                            if self.on_error:
                                self.on_error(f"Recognition service error: {e}")
                    except sr.WaitTimeoutError:
                        pass  # No speech, continue listening
                    except Exception as e:
                        if self._listening and self.on_error:
                            self.on_error(f"Listening error: {e}")

        self._listen_thread = threading.Thread(target=listen_loop, daemon=True)
        self._listen_thread.start()
        logger.info("Continuous listening started")
        return True

    def stop_continuous_listening(self):
        """Stop continuous listening."""
        self._listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
            self._listen_thread = None
        logger.info("Continuous listening stopped")

    def is_listening(self) -> bool:
        """Check if currently listening continuously."""
        return self._listening

    def get_available_voices(self) -> list:
        """Get list of available TTS voices.

        Returns:
            List of voice info dictionaries
        """
        voices = []
        if _tts_engine == "pyttsx3" and self._tts:
            try:
                for voice in self._tts.getProperty('voices'):
                    voices.append({
                        'id': voice.id,
                        'name': voice.name,
                        'languages': getattr(voice, 'languages', []),
                        'gender': getattr(voice, 'gender', 'unknown')
                    })
            except Exception as e:
                logger.warning(f"Failed to get voices: {e}")
        return voices

    def set_voice(self, voice_id: str) -> bool:
        """Set the TTS voice by ID.

        Args:
            voice_id: Voice identifier from get_available_voices()

        Returns:
            True if voice was set successfully
        """
        if _tts_engine == "pyttsx3" and self._tts:
            try:
                self._tts.setProperty('voice', voice_id)
                return True
            except Exception as e:
                logger.warning(f"Failed to set voice: {e}")
        return False

    def set_speech_rate(self, rate: int) -> bool:
        """Set speech rate (words per minute).

        Args:
            rate: Words per minute (typically 100-300)

        Returns:
            True if rate was set successfully
        """
        if _tts_engine == "pyttsx3" and self._tts:
            try:
                self._tts.setProperty('rate', rate)
                return True
            except Exception as e:
                logger.warning(f"Failed to set rate: {e}")
        return False

    def set_volume(self, volume: float) -> bool:
        """Set speech volume.

        Args:
            volume: Volume level 0.0 to 1.0

        Returns:
            True if volume was set successfully
        """
        if _tts_engine == "pyttsx3" and self._tts:
            try:
                self._tts.setProperty('volume', max(0.0, min(1.0, volume)))
                return True
            except Exception as e:
                logger.warning(f"Failed to set volume: {e}")
        return False

    def cleanup(self):
        """Clean up resources."""
        self.stop_continuous_listening()
        if self._tts and _tts_engine == "pyttsx3":
            try:
                self._tts.stop()
            except:
                pass


# Convenience functions
def create_voice_interface(**kwargs) -> Optional[VoiceInterface]:
    """Create a voice interface instance.

    Returns:
        VoiceInterface instance or None if no voice features available
    """
    try:
        vi = VoiceInterface(**kwargs)
        if vi.is_available():
            return vi
        return None
    except Exception as e:
        logger.warning(f"Failed to create voice interface: {e}")
        return None


def is_voice_available() -> bool:
    """Quick check if any voice functionality is available."""
    return _speech_recognition_available or _tts_available

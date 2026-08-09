"""Extracted backwards-compatible UserAuth methods."""
from ..facade_support import *

class AuthFacadeSupportOptionalInterfacesMixin:
    @property
    def voice_interface(self):
        """Voice interface, initialised on first access.

        Deferred from ``__init__`` because probing chatbot availability pulls in
        the full chatbot module tree (sklearn/transformers/Flask, ~1s) that the
        vast majority of sessions never use.
        """
        vi = getattr(self, "_voice_interface", None)
        if vi is None:
            vi = self._init_voice_interface()
            self._voice_interface = vi
        return vi

    @voice_interface.setter
    def voice_interface(self, value):
        self._voice_interface = value

    def _init_voice_interface(self):
        """Build the real chatbot-backed voice interface if available, else a
        minimal stub. Mirrors the original eager logic, now run lazily."""
        try:
            if is_chatbot_available():
                from education_system.systems.university.infrastructure.ai.university_chatbot import VoiceInterface
                vi = VoiceInterface()
                if hasattr(vi, "initialize"):
                    vi.initialize()
                return vi
            return MinimalVoiceInterface()
        except (ImportError, NameError, AttributeError):
            logger.info("Using minimal voice interface - voice features disabled")
            return MinimalVoiceInterface()

    def initialize_chatbot_integration(self):
        """Initialize chatbot integration with comprehensive error handling"""
        chatbot_cls = get_chatbot_class()
        if chatbot_cls is not None:
            try:
                logger.info("Initializing chatbot integration...")
                self.chatbot = chatbot_cls(db_path=self.db_path)

                # Verify the chatbot has required attributes
                required_attrs = ['app', 'config', 'conversation_history', 'auth_system']
                missing_attrs = [attr for attr in required_attrs if not hasattr(self.chatbot, attr)]

                if missing_attrs:
                    logger.warning(f"Chatbot missing attributes: {missing_attrs}")
                    # Add missing attributes
                    for attr in missing_attrs:
                        setattr(self.chatbot, attr, None)

                self.chatbot.set_auth_system(self)
                logger.info("Chatbot integration initialized successfully")
                return True

            except (ImportError, OptionalDependencyError) as e:
                logger.warning(f"Chatbot module not available: {e}")
                self._create_fallback_chatbot()
                return False
            except (AttributeError, TypeError) as e:
                logger.warning(f"Chatbot integration failed (attribute error): {e}")
                logger.debug(f"Error type: {type(e).__name__}")
                self._create_fallback_chatbot()
                return False
            except sqlite3.Error as e:
                logger.warning(f"Chatbot integration failed (database error): {e}")
                self._create_fallback_chatbot()
                return False
        else:
            logger.info("Chatbot module not available")
            self.chatbot = None
            return False

    def _create_fallback_chatbot(self):
        """Create a minimal fallback chatbot"""
        class FallbackChatbot:
            def __init__(self):
                self.enabled = False

            def process_message(self, msg, user, session_id=None, voice=False):
                return "Chatbot temporarily unavailable. Please try again later."

            def run_authenticated_console_interface(self):
                print("Chatbot is currently unavailable.")

            def set_auth_system(self, auth):
                """Set the authentication system reference"""
                self.auth_system = auth

            def get_conversation_history(self, user, limit=10):
                return []

        self.chatbot = FallbackChatbot()
        logger.info("Fallback chatbot created")

    def setup_chatbot_permissions(self):
        """
        Setup chatbot-specific permissions in the database.

        Delegates to the chatbot_integration module's setup_chatbot_permissions function.
        """
        from education_system.systems.university.infrastructure.auth.integrations.chatbot_integration import (
            setup_chatbot_permissions as setup_perms
        )
        return setup_perms(self)


class MinimalVoiceInterface:
    """Minimal fallback voice interface when full chatbot is unavailable"""
    def __init__(self):
        self.enabled = False

    def initialize(self):
        pass

    def process_voice_input(self, *args, **kwargs):
        return None

    def text_to_speech(self, *args, **kwargs):
        pass

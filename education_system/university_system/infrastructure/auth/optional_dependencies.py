"""Optional dependency management for the authentication module.

This module provides proper dependency injection and interface definitions
for optional features like voice interface and chatbot integration.
Instead of inline fallback implementations, this module:

1. Defines abstract interfaces for optional features
2. Provides factory functions that fail fast with clear error messages
3. Makes optional dependencies explicit and configurable

Usage:
    from education_system.university_system.infrastructure.auth.optional_dependencies import (
        get_chatbot,
        get_voice_interface,
        ChatbotInterface,
        VoiceInterface,
    )

    # Get optional dependency (raises if not available and required=True)
    chatbot = get_chatbot(auth_system=auth, required=False)
    if chatbot:
        chatbot.process_message(...)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from education_system.university_system.infrastructure.auth import UserAuth

from education_system.university_system.core.i18n import get_text, _

logger = logging.getLogger(__name__)


# =============================================================================
# Interface Definitions
# =============================================================================

@runtime_checkable
class VoiceInterface(Protocol):
    """Protocol defining the voice interface contract.

    Any voice interface implementation must provide these methods
    to be compatible with the authentication system.
    """

    enabled: bool

    def initialize(self) -> bool:
        """Initialize the voice interface.

        Returns:
            bool: True if initialization succeeded, False otherwise.
        """
        ...

    def cleanup(self) -> None:
        """Release voice interface resources."""
        ...


@runtime_checkable
class ChatbotInterface(Protocol):
    """Protocol defining the chatbot interface contract.

    Any chatbot implementation must provide these methods
    to be compatible with the authentication system.
    """

    enabled: bool

    def set_auth_system(self, auth_system: Any) -> None:
        """Set the authentication system for the chatbot.

        Args:
            auth_system: The authentication system instance.
        """
        ...

    def process_message(
        self,
        message: str,
        user_id: str,
        session_id: Optional[str] = None,
        is_voice: bool = False,
        **kwargs: Any,
    ) -> str:
        """Process a user message and return a response.

        Args:
            message: The user's message.
            user_id: Identifier for the user.
            session_id: Optional session identifier.
            is_voice: Whether this is a voice interaction.
            **kwargs: Additional arguments.

        Returns:
            str: The chatbot's response.
        """
        ...

    def run_authenticated_console_interface(self) -> None:
        """Run the chatbot in console mode with authentication."""
        ...


# =============================================================================
# Dependency Loading Errors
# =============================================================================

class OptionalDependencyError(Exception):
    """Raised when an optional dependency is not available.

    This exception is raised when attempting to use an optional feature
    that requires a dependency that is not installed or configured.

    Attributes:
        feature: Name of the feature that requires the dependency.
        dependency: Name of the missing dependency.
        install_hint: Optional installation instructions.
    """

    def __init__(
        self,
        feature: str,
        dependency: str,
        install_hint: Optional[str] = None,
    ):
        self.feature = feature
        self.dependency = dependency
        self.install_hint = install_hint
        message = f"{feature} requires {dependency} which is not available"
        if install_hint:
            message += f". {install_hint}"
        super().__init__(message)


# =============================================================================
# Chatbot Dependency
# =============================================================================

# Cache for loaded chatbot class
_chatbot_class: Optional[type] = None
_chatbot_load_attempted: bool = False
_chatbot_load_error: Optional[str] = None


def _load_chatbot_class() -> Optional[type]:
    """Attempt to load the chatbot class.

    Returns:
        The UniversityChatbot class if available, None otherwise.
    """
    global _chatbot_class, _chatbot_load_attempted, _chatbot_load_error

    if _chatbot_load_attempted:
        return _chatbot_class

    _chatbot_load_attempted = True

    try:
        from education_system.university_system.infrastructure.ai.university_chatbot import UniversityChatbot
        _chatbot_class = UniversityChatbot
        logger.info("Chatbot module loaded successfully")
        return _chatbot_class
    except ImportError as e:
        _chatbot_load_error = str(e)
        logger.info(f"Chatbot module not available: {e}")
        return None
    except Exception as e:
        _chatbot_load_error = str(e)
        logger.warning(f"Failed to load chatbot module: {e}")
        return None


def is_chatbot_available() -> bool:
    """Check if the chatbot module is available.

    Returns:
        bool: True if chatbot can be instantiated.
    """
    return _load_chatbot_class() is not None


def get_chatbot_class() -> Optional[type]:
    """Get the UniversityChatbot class if available.

    Returns:
        The UniversityChatbot class if available, None otherwise.
    """
    return _load_chatbot_class()


def get_chatbot(
    auth_system: Optional[Any] = None,
    required: bool = False,
    db_path: Optional[str] = None,
    config_path: Optional[str] = None,
) -> Optional[ChatbotInterface]:
    """Get a chatbot instance if available.

    Factory function that creates a chatbot instance using dependency
    injection. Instead of falling back to a minimal implementation,
    this function either returns a full chatbot or None (with optional
    exception for required dependencies).

    Args:
        auth_system: Optional authentication system to integrate.
        required: If True, raise exception when chatbot unavailable.
        db_path: Optional database path override.
        config_path: Optional configuration path override.

    Returns:
        ChatbotInterface: A chatbot instance if available.
        None: If chatbot not available and required=False.

    Raises:
        OptionalDependencyError: If required=True and chatbot unavailable.

    Example:
        >>> chatbot = get_chatbot(auth_system=auth, required=False)
        >>> if chatbot:
        ...     response = chatbot.process_message("Hello", user_id="user1")
        ... else:
        ...     print("Chatbot feature not available")
    """
    chatbot_class = _load_chatbot_class()

    if chatbot_class is None:
        if required:
            raise OptionalDependencyError(
                feature="Chatbot",
                dependency="university_system.infrastructure.ai.university_chatbot",
                install_hint=f"Import failed: {_chatbot_load_error}",
            )
        logger.debug("Chatbot requested but not available")
        return None

    try:
        # Create chatbot instance
        kwargs = {}
        if db_path:
            kwargs['db_path'] = db_path
        if config_path:
            kwargs['config_path'] = config_path

        chatbot = chatbot_class(**kwargs)

        # Integrate with auth system if provided
        if auth_system and hasattr(chatbot, 'set_auth_system'):
            chatbot.set_auth_system(auth_system)
            logger.debug("Chatbot integrated with authentication system")

        return chatbot

    except Exception as e:
        logger.error(f"Failed to create chatbot instance: {e}")
        if required:
            raise OptionalDependencyError(
                feature="Chatbot",
                dependency="UniversityChatbot",
                install_hint=f"Instantiation failed: {e}",
            )
        return None


# =============================================================================
# Voice Interface Dependency
# =============================================================================

# Cache for loaded voice interface class
_voice_class: Optional[type] = None
_voice_load_attempted: bool = False
_voice_load_error: Optional[str] = None


def _load_voice_class() -> Optional[type]:
    """Attempt to load the voice interface class.

    Returns:
        The voice interface class if available, None otherwise.
    """
    global _voice_class, _voice_load_attempted, _voice_load_error

    if _voice_load_attempted:
        return _voice_class

    _voice_load_attempted = True

    try:
        # Try to import the voice interface module
        from education_system.university_system.infrastructure.ai.voice_interface import VoiceInterface as VoiceImpl
        _voice_class = VoiceImpl
        logger.info("Voice interface module loaded successfully")
        return _voice_class
    except ImportError as e:
        _voice_load_error = str(e)
        logger.info(f"Voice interface module not available: {e}")
        return None
    except Exception as e:
        _voice_load_error = str(e)
        logger.warning(f"Failed to load voice interface module: {e}")
        return None


def is_voice_interface_available() -> bool:
    """Check if the voice interface module is available.

    Returns:
        bool: True if voice interface can be instantiated.
    """
    return _load_voice_class() is not None


def get_voice_interface(
    required: bool = False,
) -> Optional[VoiceInterface]:
    """Get a voice interface instance if available.

    Factory function that creates a voice interface instance. Instead of
    falling back to a minimal implementation, this function either returns
    a full voice interface or None.

    Args:
        required: If True, raise exception when voice interface unavailable.

    Returns:
        VoiceInterface: A voice interface instance if available.
        None: If voice interface not available and required=False.

    Raises:
        OptionalDependencyError: If required=True and voice unavailable.

    Example:
        >>> voice = get_voice_interface(required=False)
        >>> if voice and voice.initialize():
        ...     # Use voice features
        ...     voice.cleanup()
    """
    voice_class = _load_voice_class()

    if voice_class is None:
        if required:
            raise OptionalDependencyError(
                feature="Voice Interface",
                dependency="university_system.infrastructure.ai.voice_interface",
                install_hint=f"Import failed: {_voice_load_error}",
            )
        logger.debug("Voice interface requested but not available")
        return None

    try:
        return voice_class()
    except Exception as e:
        logger.error(f"Failed to create voice interface instance: {e}")
        if required:
            raise OptionalDependencyError(
                feature="Voice Interface",
                dependency="VoiceInterface",
                install_hint=f"Instantiation failed: {e}",
            )
        return None


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Interfaces
    "VoiceInterface",
    "ChatbotInterface",
    # Exceptions
    "OptionalDependencyError",
    # Factory Functions
    "get_chatbot",
    "get_voice_interface",
    # Availability Checks
    "is_chatbot_available",
    "is_voice_interface_available",
]

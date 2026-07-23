"""Voice support methods for the chatbot: TTS, voice mode, voice commands."""

import threading
from typing import Dict

from education_system.post_18.university_system.infrastructure.ai.university_chatbot.fallbacks import LIBRARIES_AVAILABLE
from education_system.post_18.university_system.infrastructure.ai.university_chatbot.models import ConversationContext


def process_voice_input(chatbot, duration: float = 5.0) -> str:
    """Process voice input with error handling"""
    if not chatbot.voice_interface.enabled:
        return ""

    text = chatbot.voice_interface.record_audio_chunk(duration)
    return text if text else ""


def start_voice_mode(chatbot, user_id: str):
    """Start continuous voice interaction mode"""
    if not chatbot.voice_interface.enabled:
        print("Voice interface not available")
        return None

    def voice_callback(text: str):
        """Handle voice input"""
        if text:
            print(f"Voice input: {text}")
            response = chatbot.process_message(text, user_id, is_voice=True)
            print(f"Response: {response}")

            if LIBRARIES_AVAILABLE['pyttsx3']:
                text_to_speech(chatbot, response)

    print("Starting voice mode... Say 'stop listening' to exit.")
    if LIBRARIES_AVAILABLE['pyttsx3']:
        text_to_speech(chatbot, "Voice mode activated. How can I help you?")

    listen_thread = chatbot.voice_interface.listen_continuously(voice_callback)

    return listen_thread


def text_to_speech(chatbot, text: str, output_path: str = None) -> bool:
    """Convert text to speech using pyttsx3"""
    if not LIBRARIES_AVAILABLE['pyttsx3']:
        print("Text-to-speech not available - missing pyttsx3 library")
        return False

    try:
        import pyttsx3
        engine = pyttsx3.init()

        voices = engine.getProperty('voices')
        if voices:
            engine.setProperty('voice', voices[0].id)
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.9)

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


def test_voice_interface(chatbot) -> Dict:
    """Test voice interface functionality"""
    if not chatbot.voice_interface.enabled:
        return {"status": "disabled", "message": "Voice interface not available"}

    return chatbot.voice_interface.test_microphone()


def handle_voice_command(chatbot, message: str, user_id: str, context: ConversationContext) -> str:
    """Handle voice-specific commands"""
    message_lower = message.lower()

    if any(cmd in message_lower for cmd in ["start voice mode", "voice mode", "talk to me"]):
        if chatbot.voice_interface.enabled:
            threading.Thread(target=start_voice_mode, args=(chatbot, user_id), daemon=True).start()
            return "Voice mode activated! You can now speak your questions. Say 'stop listening' to exit voice mode."
        else:
            return "Voice interface is not available. Please ensure your microphone is connected and try again."

    elif "test voice" in message_lower or "test microphone" in message_lower:
        result = test_voice_interface(chatbot)
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

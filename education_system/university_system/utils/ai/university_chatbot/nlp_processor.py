"""NLP processing pipeline: intent classification, entity extraction, sentiment analysis."""

from typing import Any, Dict, Optional

from education_system.university_system.utils.ai.university_chatbot.models import ConversationContext


def process_with_nlp(chatbot, text: str, user_context: Optional[ConversationContext] = None) -> Dict[str, Any]:
    """Process text with advanced NLP"""
    if not chatbot.nlp:
        return fallback_processing(chatbot, text)

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
        doc = chatbot.nlp(text)
        result["entities"] = {
            "persons": [ent.text for ent in doc.ents if ent.label_ == "PERSON"],
            "dates": [ent.text for ent in doc.ents if ent.label_ == "DATE"],
            "money": [ent.text for ent in doc.ents if ent.label_ == "MONEY"],
            "organizations": [ent.text for ent in doc.ents if ent.label_ == "ORG"]
        }

        # Classify intent
        intent_result = chatbot.intent_classifier(text)
        if intent_result and len(intent_result) > 0:
            result["intent"] = intent_result[0]["label"]
            result["confidence"] = intent_result[0]["score"]

        # Analyze sentiment
        sentiment_result = chatbot.sentiment_analyzer(text)
        if sentiment_result and len(sentiment_result) > 0:
            result["sentiment"] = sentiment_result[0]["label"]
            if result["sentiment"] == "NEGATIVE" and sentiment_result[0]["score"] > 0.8:
                result["requires_escalation"] = True

        # Context-aware processing
        if user_context:
            result = enhance_with_context(result, user_context)

    except Exception as e:
        print(f"NLP processing error: {e}")
        result = fallback_processing(chatbot, text)

    return result


def enhance_with_context(nlp_result: Dict, context: ConversationContext) -> Dict:
    """Enhance NLP results with conversation context"""
    if len(context.intent_history) > 0:
        last_intent = context.intent_history[-1]
        if nlp_result["confidence"] < 0.6:
            nlp_result["intent"] = last_intent
            nlp_result["confidence"] = 0.7

    if "student_id" in context.entities:
        nlp_result["entities"]["student_id"] = context.entities["student_id"]

    return nlp_result


def fallback_processing(chatbot, text: str) -> Dict[str, Any]:
    """Fallback processing when NLP is unavailable"""
    result = {
        "intent": "general",
        "entities": {},
        "sentiment": "NEUTRAL",
        "confidence": 0.5,
        "requires_escalation": False,
        "is_voice_command": False
    }

    text_lower = text.lower()

    voice_commands = ["start voice mode", "voice mode", "talk to me", "speak", "listen"]
    if any(cmd in text_lower for cmd in voice_commands):
        result["is_voice_command"] = True
        result["intent"] = "voice_command"
        result["confidence"] = 0.8
        return result

    for intent, data in chatbot.intents.items():
        for pattern in data["patterns"]:
            if pattern in text_lower:
                result["intent"] = intent
                result["confidence"] = 0.6
                break

    return result

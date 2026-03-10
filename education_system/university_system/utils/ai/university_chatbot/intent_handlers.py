"""Non-authenticated intent handlers and FAQ matching."""

import json
import os
from typing import Dict, Optional

from education_system.university_system.utils.ai.university_chatbot.fallbacks import (
    TfidfVectorizer,
    cosine_similarity,
    np,
)
from education_system.university_system.utils.ai.university_chatbot.models import ConversationContext


def handle_course_inquiry(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle course-related inquiries"""
    entities = nlp_result["entities"]

    if "student_id" in context.entities:
        student_id = context.entities["student_id"]
        recommendations = chatbot.get_course_recommendations(student_id, 3)

        if recommendations:
            response = "Based on your profile, I recommend these courses:\n\n"
            for rec in recommendations:
                response += f"• {rec['course_code']}: {rec['course_name']}\n"
                response += f"  Reason: {', '.join(rec['reasons'])}\n\n"
            return response

    return "I can help you with course information. Could you please provide your student ID for personalized recommendations?"


def handle_registration_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle registration queries"""
    if "student_id" in context.entities:
        student_id = context.entities["student_id"]
        return f"I can help you with course registration. Let me check your current registration status for {student_id}..."

    return "To help with registration, I'll need your student ID. Please provide it to continue."


def handle_financial_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle financial queries"""
    entities = nlp_result["entities"]

    if "money" in entities:
        return "I can help with financial information. For specific payment amounts and due dates, please log into your student portal or contact the finance office."

    return "I can assist with financial aid, tuition payments, and scholarship information. What specific financial topic can I help you with?"


def handle_grades_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle grade-related queries"""
    if "student_id" in context.entities:
        student_id = context.entities["student_id"]
        gpa_info = chatbot.calculate_gpa(student_id)

        if "error" not in gpa_info:
            return f"Your current GPA is {gpa_info['gpa']} based on {gpa_info['total_credits']} credit hours. For detailed grade information, please check your student portal."

    return "To check your grades and GPA, I'll need your student ID. Please provide it to continue."


def handle_technical_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle technical support queries"""
    return "I can help with basic technical issues. For complex problems, I'll connect you with our IT support team. What technical issue are you experiencing?"


def handle_general_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle general queries using FAQ matching"""
    user_message = context.messages[-1]["user_message"]

    best_match = find_best_faq_match(chatbot, user_message)

    if best_match:
        return best_match

    return "I'm here to help with university-related questions. You can ask about courses, registration, grades, fees, or technical support. You can also use voice commands by saying 'start voice mode'. How can I assist you today?"


def find_best_faq_match(chatbot, query: str) -> Optional[str]:
    """Find best matching FAQ answer"""
    try:
        all_faqs = []
        for category, faqs in chatbot.faq_database.items():
            for question, answer in faqs.items():
                all_faqs.append((question, answer))

        if not all_faqs:
            return None

        questions = [faq[0] for faq in all_faqs]
        questions.append(query)

        vectors = chatbot.vectorizer.fit_transform(questions)
        similarity_scores = cosine_similarity(vectors[-1:], vectors[:-1]).flatten()

        best_idx = np.argmax(similarity_scores)
        best_score = similarity_scores[best_idx]

        if best_score > 0.3:
            return all_faqs[best_idx][1]

        return None

    except Exception as e:
        print(f"FAQ matching error: {e}")
        return None


def escalate_to_human(chatbot, message: str, user_id: str) -> str:
    """Escalate conversation to human agent"""
    from datetime import datetime

    escalation_data = {
        "user_id": user_id,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "reason": "negative_sentiment_detected"
    }

    escalation_file = os.path.join(chatbot.log_dir, "escalations.json")

    if os.path.exists(escalation_file):
        with open(escalation_file, 'r') as f:
            escalations = json.load(f)
    else:
        escalations = []

    escalations.append(escalation_data)

    with open(escalation_file, 'w') as f:
        json.dump(escalations, f, indent=4)

    return "I understand you may be frustrated. I'm connecting you with a human support agent who will be able to better assist you. Please expect a response within 2 hours."

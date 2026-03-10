"""Authenticated intent handlers with permission-based responses."""

from typing import Dict

from education_system.university_system.utils.ai.university_chatbot.intent_handlers import (
    find_best_faq_match,
    handle_technical_query,
)
from education_system.university_system.utils.ai.university_chatbot.models import (
    AuthenticatedSession,
    ConversationContext,
)


def generate_authenticated_response(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Generate response with authentication and permission checks"""
    intent = nlp_result["intent"]

    if intent == "course_inquiry":
        return handle_authenticated_course_inquiry(chatbot, nlp_result, context, session)
    elif intent == "registration":
        if "view_own_record" in session.permissions:
            return handle_authenticated_registration_query(chatbot, nlp_result, context, session)
        else:
            return "You don't have permission to access registration information."
    elif intent == "financial":
        if "view_own_finances" in session.permissions or "manage_finances" in session.permissions:
            return handle_authenticated_financial_query(chatbot, nlp_result, context, session)
        else:
            return "You don't have permission to access financial information."
    elif intent == "grades":
        if "view_own_grades" in session.permissions or "manage_grades" in session.permissions:
            return handle_authenticated_grades_query(chatbot, nlp_result, context, session)
        else:
            return "You don't have permission to access grade information."
    elif intent == "technical_support":
        return handle_technical_query(chatbot, nlp_result, context)
    elif intent == "voice_command":
        return chatbot.handle_voice_command(context.messages[-1]["user_message"], context.user_id, context)
    else:
        return handle_authenticated_general_query(chatbot, nlp_result, context, session)


def handle_authenticated_course_inquiry(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Handle course inquiries with user-specific data"""
    if session.role == "student" and "view_own_record" in session.permissions:
        student_id = chatbot.get_student_id_for_user(session.username)
        if student_id:
            recommendations = chatbot.get_course_recommendations(student_id, 3)
            if recommendations:
                response = f"Hello {session.username}! Based on your academic profile, I recommend:\n\n"
                for rec in recommendations:
                    response += f"• {rec['course_code']}: {rec['course_name']}\n"
                    response += f"  Reason: {', '.join(rec['reasons'])}\n\n"
                return response

    elif session.role in ["staff", "admin"] and "manage_modules" in session.permissions:
        return f"Hello {session.username}! As a {session.role}, I can help you with course management, student inquiries, and academic planning. What specific course information do you need?"

    return f"Hello {session.username}! I can help you with course information. What would you like to know about our academic programs?"


def handle_authenticated_registration_query(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Handle registration queries with permission checks"""
    if session.role == "student":
        student_id = chatbot.get_student_id_for_user(session.username)
        if student_id:
            return f"I can help you with course registration, {session.username}. Let me check your current enrollment status and available courses for student ID: {student_id}."

    elif session.role in ["staff", "admin"] and "manage_students" in session.permissions:
        return f"Hello {session.username}! I can help you manage student registrations. Which student or registration process would you like assistance with?"

    return "I can help with registration information. Please provide more details about what you need."


def handle_authenticated_financial_query(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Handle financial queries with role-based responses"""
    if session.role == "student" and "view_own_finances" in session.permissions:
        return f"I can help you with your financial information, {session.username}. This includes tuition balance, payment history, and financial aid status. What specific financial information do you need?"

    elif session.role in ["staff", "admin"] and "manage_finances" in session.permissions:
        return f"Hello {session.username}! I can help you with financial administration including payment processing, financial reports, and student account management. What do you need assistance with?"

    return "I can help with financial information. Please specify what you'd like to know."


def handle_authenticated_grades_query(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Handle grade queries with authentication"""
    if session.role == "student" and "view_own_grades" in session.permissions:
        student_id = chatbot.get_student_id_for_user(session.username)
        if student_id:
            gpa_info = chatbot.calculate_gpa(student_id)
            if "error" not in gpa_info:
                return f"Hello {session.username}! Your current GPA is {gpa_info['gpa']} based on {gpa_info['total_credits']} credit hours. I can provide more detailed grade information if needed."
            else:
                return "I'm having trouble accessing your grade information right now. Please try again later or contact the registrar's office."

    elif session.role in ["instructor", "staff", "admin"] and "manage_grades" in session.permissions:
        return f"Hello {session.username}! I can help you with grade management, student performance analysis, and academic reporting. What would you like to do?"

    return "I can help with grade information. Please let me know what you need."


def handle_authenticated_general_query(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Handle general queries with user context"""
    user_message = context.messages[-1]["user_message"]

    role_greetings = {
        "student": f"Hello {session.username}! As a student, I can help you with course information, grades, registration, financial aid, and campus resources.",
        "instructor": f"Hello {session.username}! I can assist you with course management, student information, grade processing, and administrative tasks.",
        "staff": f"Hello {session.username}! I can help you with student records, administrative tasks, reporting, and system management.",
        "admin": f"Hello {session.username}! I have full system access and can help you with any aspect of the student information system."
    }

    best_match = find_best_faq_match(chatbot, user_message)

    if best_match:
        return f"{role_greetings.get(session.role, f'Hello {session.username}!')} {best_match}"

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

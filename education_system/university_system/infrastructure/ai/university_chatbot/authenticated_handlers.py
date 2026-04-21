"""Authenticated intent handlers with permission-based responses."""

from typing import Dict

from education_system.university_system.infrastructure.ai.university_chatbot.intent_handlers import (
    find_best_faq_match,
    handle_technical_query,
)
from education_system.university_system.infrastructure.ai.university_chatbot.models import (
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
    elif intent == "academic_support":
        return handle_authenticated_academic_support(chatbot, nlp_result, context, session)
    elif intent == "admissions":
        return handle_authenticated_admissions(chatbot, nlp_result, context, session)
    elif intent == "administrative":
        return handle_authenticated_administrative(chatbot, nlp_result, context, session)
    elif intent == "wellbeing":
        # Wellbeing queries don't need special auth — delegate to base handler
        from education_system.university_system.infrastructure.ai.university_chatbot.intent_handlers import handle_wellbeing_query
        return handle_wellbeing_query(chatbot, nlp_result, context)
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


def handle_authenticated_academic_support(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Handle academic support with user-specific data."""
    user_message = context.messages[-1]["user_message"].lower()
    student_id = chatbot.get_student_id_for_user(session.username) if session.role == "student" else None

    # Inject student_id into context for downstream handlers
    if student_id:
        context.entities["student_id"] = student_id

    # Deadline reminders — personalised
    if any(kw in user_message for kw in ["deadline", "due", "assignment"]):
        if student_id:
            deadlines = chatbot.get_upcoming_deadlines(student_id)
            if deadlines:
                response = f"Upcoming Deadlines for {session.username}:\n\n"
                for d in deadlines:
                    response += f"  {d['title']} ({d['module']})\n"
                    response += f"    Type: {d['type'] or 'N/A'}  |  Due: {d['due']}\n\n"
                return response
            return f"No upcoming deadlines, {session.username}. You're all caught up!"

    # Exam schedule — personalised
    if any(kw in user_message for kw in ["exam", "examination"]):
        if student_id:
            exams = chatbot.get_exam_schedule(student_id)
            if exams:
                response = f"Exam Schedule for {session.username}:\n\n"
                for e in exams:
                    room_str = f"{e['room'] or 'TBD'}"
                    if e.get('building'):
                        room_str += f" ({e['building']})"
                    response += f"  {e['module']}\n"
                    response += f"    Date: {e['date']}  |  Time: {e['start']} - {e['end']}  |  Room: {room_str}\n\n"
                return response
            return f"No upcoming exams found for your modules, {session.username}."

    # Delegate to the base handler for library, calendar, etc.
    from education_system.university_system.infrastructure.ai.university_chatbot.intent_handlers import handle_academic_support_query
    return handle_academic_support_query(chatbot, nlp_result, context)


def handle_authenticated_admissions(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Handle admissions with auth context."""
    user_message = context.messages[-1]["user_message"].lower()

    # Application status with auto-lookup
    if any(kw in user_message for kw in ["application status", "track", "my application"]):
        apps = chatbot.get_application_status(session.username)
        if apps:
            response = f"Application Status for {session.username}:\n\n"
            for a in apps:
                response += f"  Application #{a['id']} — {a['programme']}\n"
                response += f"    Status: {a['status']}  |  Submitted: {a['submitted']}"
                if a.get('decision'):
                    response += f"  |  Decision: {a['decision']}"
                response += "\n\n"
            return response

    # Admin/staff can view all applications
    if session.role in ["staff", "admin"] and "manage_students" in session.permissions:
        return f"As a {session.role}, you can access the full admissions dashboard. What would you like to look up?"

    from education_system.university_system.infrastructure.ai.university_chatbot.intent_handlers import handle_admissions_query
    return handle_admissions_query(chatbot, nlp_result, context)


def handle_authenticated_administrative(chatbot, nlp_result: Dict, context: ConversationContext, session: AuthenticatedSession) -> str:
    """Handle admin tasks with auth context."""
    user_message = context.messages[-1]["user_message"].lower()

    # Fee balance — personalised
    if any(kw in user_message for kw in ["fee", "balance", "payment", "invoice", "owe"]):
        if session.role == "student":
            student_id = chatbot.get_student_id_for_user(session.username) or session.username
            fee_info = chatbot.get_fee_balance(student_id)
            fees = fee_info.get("fees", [])
            if fees:
                response = f"Fee Balance for {session.username}:\n\n"
                for f in fees:
                    outstanding = (f['amount'] or 0) - (f['paid'] or 0)
                    response += f"  {f['description'] or 'Fee'}\n"
                    response += f"    Amount: £{f['amount'] or 0:.2f}  |  Paid: £{f['paid'] or 0:.2f}  |  Outstanding: £{outstanding:.2f}\n"
                    response += f"    Due: {f['due_date'] or 'N/A'}  |  Status: {f['status'] or 'N/A'}\n\n"
                return response
            return f"No outstanding fees found for {session.username}."

    # Transcript / certificate requests
    if any(kw in user_message for kw in ["transcript", "certificate", "enrollment verification"]):
        if session.role == "student":
            student_id = chatbot.get_student_id_for_user(session.username) or session.username
            requests = chatbot.get_transcript_requests(student_id)
            if requests:
                response = f"Your Document Requests:\n\n"
                for r in requests:
                    response += f"  #{r['id']} — {r['type']}\n"
                    response += f"    Status: {r['status']}  |  Requested: {r['date']}\n\n"
                response += "To submit a new request, visit the registrar's office or student portal."
                return response
            return ("You have no pending document requests.\n\n"
                    "To request a transcript or enrollment certificate:\n"
                    "  1. Visit the student portal > Documents section\n"
                    "  2. Or contact the registrar at registrar@university.ac.uk")

    # Room bookings with auto-lookup
    if any(kw in user_message for kw in ["room booking", "book a room", "my booking"]):
        bookings = chatbot.get_room_bookings(session.username)
        if bookings:
            response = f"Your Room Bookings, {session.username}:\n\n"
            for b in bookings:
                response += f"  {b['room']} — {b['date']}\n"
                response += f"    Time: {b['start']} - {b['end']}  |  Status: {b['status']}\n\n"
            return response

    from education_system.university_system.infrastructure.ai.university_chatbot.intent_handlers import handle_administrative_query
    return handle_administrative_query(chatbot, nlp_result, context)

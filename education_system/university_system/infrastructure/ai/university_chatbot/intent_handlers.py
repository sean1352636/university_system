"""Non-authenticated intent handlers and FAQ matching."""

import json
import os
from typing import Dict, Optional

from education_system.university_system.infrastructure.ai.university_chatbot.fallbacks import (
    TfidfVectorizer,
    cosine_similarity,
    np,
)
from education_system.university_system.infrastructure.ai.university_chatbot.models import ConversationContext


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


def handle_academic_support_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle academic support queries: deadlines, exams, library, calendar, timetable."""
    user_message = context.messages[-1]["user_message"].lower()

    # Deadline reminders
    if any(kw in user_message for kw in ["deadline", "due", "assignment"]):
        if "student_id" in context.entities:
            deadlines = chatbot.get_upcoming_deadlines(context.entities["student_id"])
            if deadlines:
                response = "Upcoming Deadlines:\n\n"
                for d in deadlines:
                    response += f"  {d['title']} ({d['module']})\n"
                    response += f"    Type: {d['type'] or 'N/A'}  |  Due: {d['due']}\n\n"
                return response
            return "You have no upcoming deadlines. Great job staying on top of things!"
        return "I can show your upcoming deadlines. Please provide your student ID or log in for personalised results."

    # Exam schedule
    if any(kw in user_message for kw in ["exam", "examination"]):
        if "student_id" in context.entities:
            exams = chatbot.get_exam_schedule(context.entities["student_id"])
            if exams:
                response = "Exam Schedule:\n\n"
                for e in exams:
                    room_str = f"{e['room'] or 'TBD'}"
                    if e.get('building'):
                        room_str += f" ({e['building']})"
                    response += f"  {e['module']}\n"
                    response += f"    Date: {e['date']}  |  Time: {e['start']} - {e['end']}  |  Room: {room_str}\n\n"
                return response
            return "No upcoming exams found for your enrolled modules."
        return "I can look up your exam schedule. Please provide your student ID."

    # Library search
    if any(kw in user_message for kw in ["library", "book"]):
        # Try to extract search terms
        search_term = user_message
        for prefix in ["search library for", "find book", "is", "library", "book available", "book"]:
            search_term = search_term.replace(prefix, "").strip()
        search_term = search_term.strip("? ")
        if search_term and len(search_term) > 2:
            results = chatbot.search_library(search_term)
            if results:
                response = f"Library Search Results for '{search_term}':\n\n"
                for b in results:
                    avail = f"{b['available']}/{b['total']}" if b['total'] else "N/A"
                    response += f"  {b['title']}\n"
                    response += f"    Author: {b['author'] or 'N/A'}  |  Available: {avail}\n\n"
                return response
            return f"No library results found for '{search_term}'. Try different search terms."
        return "I can search the library catalogue. What book or topic are you looking for?"

    # Academic calendar
    if any(kw in user_message for kw in ["calendar", "holiday", "term date", "semester"]):
        events = chatbot.get_academic_calendar()
        if events:
            response = "Academic Calendar:\n\n"
            for e in events:
                end_str = f" to {e['end']}" if e.get('end') else ""
                response += f"  {e['name']}\n"
                response += f"    Date: {e['start']}{end_str}  |  Type: {e['type'] or 'N/A'}\n\n"
            return response
        return "Academic calendar information is not currently available. Please check the university website."

    # Timetable (delegate to schedule handler if available)
    if any(kw in user_message for kw in ["timetable", "schedule", "class time"]):
        return "I can show your class timetable. Please use the 'View Schedule' quick action or ask 'Show my schedule'."

    # General academic support fallback
    best_match = find_best_faq_match(chatbot, context.messages[-1]["user_message"])
    if best_match:
        return best_match
    return ("I can help with academic support including:\n"
            "  - Deadline reminders for assignments and exams\n"
            "  - Exam schedules and room locations\n"
            "  - Library resource search\n"
            "  - Academic calendar and term dates\n"
            "  - Timetable lookup\n\n"
            "What would you like to know?")


def handle_admissions_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle admissions and onboarding queries."""
    user_message = context.messages[-1]["user_message"].lower()

    # Application status
    if any(kw in user_message for kw in ["application status", "track application", "my application"]):
        identifier = context.entities.get("student_id") or context.user_id
        apps = chatbot.get_application_status(identifier)
        if apps:
            response = "Application Status:\n\n"
            for a in apps:
                response += f"  Application #{a['id']} — {a['programme']}\n"
                response += f"    Status: {a['status']}  |  Submitted: {a['submitted']}"
                if a.get('decision'):
                    response += f"  |  Decision: {a['decision']}"
                response += "\n\n"
            return response
        return "I couldn't find any applications matching your details. Please check your application reference number."

    # Document submission
    if any(kw in user_message for kw in ["document", "submit", "upload", "required document"]):
        return ("Document Submission Guide:\n\n"
                "  Required documents typically include:\n"
                "    1. Academic transcripts (certified copies)\n"
                "    2. Personal statement / statement of purpose\n"
                "    3. Letters of reference (2-3)\n"
                "    4. Proof of identity (passport / national ID)\n"
                "    5. English language certificate (if applicable)\n"
                "    6. Portfolio (for creative programmes)\n\n"
                "  Upload documents through the application portal.\n"
                "  Contact admissions@university.ac.uk for specific programme requirements.")

    # Scholarships
    if any(kw in user_message for kw in ["scholarship", "bursary", "eligibility", "funding"]):
        return ("Scholarship Information:\n\n"
                "  Available scholarships:\n"
                "    - Academic Excellence Scholarship (GPA > 3.5)\n"
                "    - Need-Based Financial Grant\n"
                "    - International Student Scholarship\n"
                "    - Subject-Specific Awards (STEM, Arts, Humanities)\n"
                "    - Sports Scholarship\n"
                "    - Widening Participation Bursary\n\n"
                "  Deadlines vary by programme. Check the scholarships portal or ask me about a specific award.")

    # Campus tours
    if any(kw in user_message for kw in ["campus tour", "visit", "open day"]):
        return ("Campus Tours:\n\n"
                "  Campus tours are available on:\n"
                "    - Scheduled Open Days (check the admissions website)\n"
                "    - By appointment (individual or group)\n"
                "    - Virtual tours available online 24/7\n\n"
                "  To book a tour, contact admissions@university.ac.uk\n"
                "  or call the admissions office during business hours.")

    # General admissions
    best_match = find_best_faq_match(chatbot, context.messages[-1]["user_message"])
    if best_match:
        return best_match
    return ("I can help with admissions queries including:\n"
            "  - Application status tracking\n"
            "  - Document submission guidance\n"
            "  - Scholarship and eligibility information\n"
            "  - Campus tour scheduling\n\n"
            "What would you like to know?")


def handle_administrative_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle administrative task queries."""
    user_message = context.messages[-1]["user_message"].lower()

    # Leave of absence / deferral
    if any(kw in user_message for kw in ["leave of absence", "deferral", "defer", "suspend studies"]):
        return ("Leave of Absence / Deferral:\n\n"
                "  To apply for a leave of absence or deferral:\n"
                "    1. Download the request form from the student portal\n"
                "    2. Discuss with your personal tutor / academic advisor\n"
                "    3. Submit the completed form to the Student Office\n"
                "    4. Allow 5-10 working days for processing\n\n"
                "  Key considerations:\n"
                "    - Maximum leave period: typically 1 academic year\n"
                "    - Financial implications: tuition may be adjusted\n"
                "    - Visa impact: international students should consult the visa office\n\n"
                "  Contact: studentoffice@university.ac.uk")

    # ID card replacement
    if any(kw in user_message for kw in ["id card", "student card", "replacement card", "lost id"]):
        return ("ID Card Replacement:\n\n"
                "  To replace a lost or damaged ID card:\n"
                "    1. Report the loss via the student portal\n"
                "    2. Visit the Student Services desk with photo ID\n"
                "    3. Pay the replacement fee (if applicable)\n"
                "    4. New card issued within 3-5 working days\n\n"
                "  Temporary access can be arranged while you wait.\n"
                "  Contact: studentservices@university.ac.uk")

    # Room / facility booking
    if any(kw in user_message for kw in ["room booking", "book a room", "facility", "meeting room"]):
        if "student_id" in context.entities:
            bookings = chatbot.get_room_bookings(context.entities["student_id"])
            if bookings:
                response = "Your Room Bookings:\n\n"
                for b in bookings:
                    response += f"  {b['room']} — {b['date']}\n"
                    response += f"    Time: {b['start']} - {b['end']}  |  Status: {b['status']}\n\n"
                return response
        return ("Room & Facility Booking:\n\n"
                "  Available spaces:\n"
                "    - Study rooms (library)\n"
                "    - Meeting rooms\n"
                "    - Seminar rooms\n"
                "    - Sports facilities\n\n"
                "  Book through the room booking system on the student portal\n"
                "  or contact facilities@university.ac.uk")

    # Staff directory
    if any(kw in user_message for kw in ["staff", "directory", "contact", "department", "find", "office"]):
        search_term = user_message
        for prefix in ["find", "contact", "staff directory", "staff", "department", "who is"]:
            search_term = search_term.replace(prefix, "").strip()
        search_term = search_term.strip("? ")
        if search_term and len(search_term) > 2:
            results = chatbot.search_staff_directory(search_term)
            if results:
                response = f"Staff Directory Results for '{search_term}':\n\n"
                for s in results:
                    response += f"  {s['name']}\n"
                    response += f"    Role: {s['role'] or 'N/A'}  |  Dept: {s['department'] or 'N/A'}\n"
                    response += f"    Email: {s['email'] or 'N/A'}"
                    if s.get('phone'):
                        response += f"  |  Phone: {s['phone']}"
                    if s.get('office'):
                        response += f"  |  Office: {s['office']}"
                    response += "\n\n"
                return response
            return f"No staff members found matching '{search_term}'."
        return "I can search the staff directory. Who are you looking for?"

    # General administrative
    best_match = find_best_faq_match(chatbot, context.messages[-1]["user_message"])
    if best_match:
        return best_match
    return ("I can help with administrative tasks including:\n"
            "  - Leave of absence or deferral requests\n"
            "  - ID card replacement\n"
            "  - Room and facility booking\n"
            "  - Staff directory and department contacts\n\n"
            "What do you need help with?")


def handle_wellbeing_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle wellbeing and campus life queries."""
    user_message = context.messages[-1]["user_message"].lower()

    # Mental health
    if any(kw in user_message for kw in ["mental health", "counselling", "counseling", "wellbeing",
                                          "welfare", "stress", "anxiety", "depressed", "struggling"]):
        resources = chatbot.get_mental_health_resources()
        response = "Mental Health & Wellbeing Resources:\n\n"
        for r in resources:
            response += f"  {r['name']}\n"
            response += f"    {r['description']}\n"
            response += f"    Contact: {r['contact']}\n\n"
        response += "Remember: it's okay to ask for help. You are not alone."
        return response

    # Clubs and societies
    if any(kw in user_message for kw in ["club", "society", "societies", "student union", "join"]):
        clubs = chatbot.get_clubs_and_societies()
        if clubs:
            response = f"Student Clubs & Societies ({len(clubs)} found):\n\n"
            for c in clubs:
                response += f"  {c['name']}"
                if c.get('category'):
                    response += f" [{c['category']}]"
                response += "\n"
                if c.get('description'):
                    snippet = c['description'][:100] + ('...' if len(c['description']) > 100 else '')
                    response += f"    {snippet}\n"
                if c.get('contact'):
                    response += f"    Contact: {c['contact']}\n"
                response += "\n"
            return response
        return ("We have many student clubs and societies covering sports, arts, culture, academic interests, and more.\n\n"
                "Check the Students' Union website for the full list, or visit the freshers' fair.\n"
                "Contact: su@university.ac.uk")

    # Lost and found
    if any(kw in user_message for kw in ["lost", "found", "lost property", "missing"]):
        search_term = ""
        for prefix in ["i lost", "lost", "find my", "missing", "found"]:
            if prefix in user_message:
                search_term = user_message.split(prefix, 1)[-1].strip("., ?!")
                break
        items = chatbot.get_lost_found_items(search_term)
        if items:
            response = "Lost & Found Items:\n\n"
            for item in items:
                response += f"  #{item['id']}: {item['description']}\n"
                response += f"    Found at: {item['location'] or 'N/A'}  |  Date: {item['date'] or 'N/A'}  |  Status: {item['status']}\n\n"
            response += "To claim an item, visit the Student Services desk with your ID."
            return response
        return ("Lost & Found Service:\n\n"
                "  To report a lost item:\n"
                "    1. Visit the Student Services desk\n"
                "    2. Or email lostandfound@university.ac.uk\n"
                "    3. Provide: description, last known location, date\n\n"
                "  Found items are kept for 30 days before disposal.")

    # Transport / shuttle
    if any(kw in user_message for kw in ["shuttle", "transport", "bus", "route"]):
        schedule = chatbot.get_transport_schedule()
        if schedule:
            response = "Campus Transport Schedule:\n\n"
            for s in schedule:
                response += f"  {s['route']}\n"
                response += f"    From: {s['from']}  |  Depart: {s['depart_time']}\n"
                response += f"    To: {s['to']}  |  Arrive: {s['arrive_time']}\n\n"
            return response
        return ("Campus Transport:\n\n"
                "  Shuttle services operate between campus locations.\n"
                "  Schedules are posted at shuttle stops and on the university app.\n"
                "  For route information, visit transport@university.ac.uk")

    # Events (campus life)
    if any(kw in user_message for kw in ["event", "happening", "what's on"]):
        return "I can show upcoming campus events. Use the 'Events' quick action or ask 'Show upcoming events'."

    # General wellbeing
    best_match = find_best_faq_match(chatbot, context.messages[-1]["user_message"])
    if best_match:
        return best_match
    return ("I can help with wellbeing and campus life:\n"
            "  - Mental health resources and counselling\n"
            "  - Student clubs and societies\n"
            "  - Lost and found reporting\n"
            "  - Campus transport and shuttle schedules\n"
            "  - Campus events and activities\n\n"
            "What can I help you with?")


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

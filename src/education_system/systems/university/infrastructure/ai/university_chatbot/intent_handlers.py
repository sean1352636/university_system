"""Non-authenticated intent handlers and FAQ matching."""

import json
import os
from typing import Dict, Optional

from education_system.systems.university.infrastructure.ai.university_chatbot.fallbacks import (
    TfidfVectorizer,
    cosine_similarity,
    np,
)
from education_system.systems.university.infrastructure.ai.university_chatbot.models import ConversationContext


def handle_absence_quota_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """#49 — 'Am I allowed one more absence in PHYS101?' and similar.

    Triggered when the NLP result intent is 'absence_quota', or when the
    user utterance contains attendance/absence quota phrasing. Uses the
    absence_enhancements module to compute remaining misses per module.
    """
    try:
        from education_system.systems.university.domain.academics.services.attendance.absence_tracking \
            import absence_enhancements as ae
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
    except Exception:
        return "Attendance lookup is unavailable right now."

    entities = nlp_result.get("entities", {}) if isinstance(nlp_result, dict) else {}
    sid = (entities.get("student_id")
           or context.entities.get("student_id")
           or getattr(context, "user_id", None))
    if not sid:
        return ("To tell you how many absences you can still take I need your "
                "student ID — please share it.")
    module = entities.get("module_code") or context.entities.get("module_code")
    try:
        conn = get_connection()
        ae.ensure_enhanced_schema(conn)
        threshold = float(entities.get("threshold", 75))
        return ae.chatbot_absence_quota(conn, sid, module, threshold)
    except Exception:
        return "I couldn't compute your attendance quota right now."


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
    """Handle financial queries — routes to live tools.

    Pulls the actual balance and active holds from finance_bus via
    ``chatbot_tools`` rather than returning a canned string. Falls
    back to canned text on any error.
    """
    sid = context.entities.get("student_id") or context.user_id
    if not sid:
        return ("I need your student ID to look up balance or holds. "
                "Please provide it.")
    try:
        from education_system.systems.university.services.bus.chatbot_tools import (
            call_tool,
        )
        bal = call_tool("balance", student_id=sid)
        holds = call_tool("active_holds", student_id=sid)
    except Exception:
        return ("Finance lookup is unavailable right now. Please log "
                "into your student portal for balance and holds.")
    if not bal.get("ok"):
        return ("I couldn't read your finance balance. Try the student "
                "portal or contact the finance office.")
    bits = [f"Balance: £{float(bal.get('balance') or 0):,.2f}"]
    hold_list = (holds.get("holds") if holds.get("ok") else None) or []
    if hold_list:
        reasons = ", ".join((h.get("reason") or "") for h in hold_list[:3])
        bits.append(f"⚠ {len(hold_list)} active hold(s) — {reasons}")
    else:
        bits.append("✓ No active holds")
    return ". ".join(bits) + "."


def handle_grades_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle grade-related queries — uses compute_module_grade when a
    module code is available, otherwise falls back to GPA."""
    user_message = (context.messages[-1]["user_message"]
                    if context.messages else "").lower()

    # Transcript / certificate / enrolment-verification *requests* are
    # procedural questions ("how do I get..."), not grade lookups. They share
    # the 'grades' intent only because those nouns live in its keyword list, so
    # intercept them here before the GPA/module-grade path runs.
    doc_words = ("transcript", "certificate", "academic record",
                 "enrolment verification", "enrollment verification",
                 "enrolment certificate", "enrollment certificate")
    request_words = ("how", "request", "get", "obtain", "apply", "order",
                     "need", "want", "where", "download", "issue", "copy")
    if (any(d in user_message for d in doc_words)
            and any(r in user_message for r in request_words)):
        faq = find_best_faq_match(chatbot, user_message)
        if faq:
            return faq
        return (
            "To request an official transcript or an enrolment/enrollment "
            "certificate, go to the student portal (Records → Document "
            "Requests) or contact the Registry office. Official transcripts "
            "are normally issued within 3–5 working days; an enrolment "
            "certificate confirming your student status can usually be "
            "downloaded from the portal straight away."
        )

    sid = context.entities.get("student_id") or context.user_id
    if not sid:
        return "To check grades I'll need your student ID."

    module = (nlp_result.get("entities", {}).get("module_code")
              or context.entities.get("module_code"))
    try:
        from education_system.systems.university.services.bus.chatbot_tools import (
            call_tool,
        )
        if module:
            res = call_tool("module_grade", student_id=sid, module_code=module)
            if res.get("ok"):
                r = res["result"]
                pct = r.get("percentage")
                letter = r.get("letter") or ""
                if pct is None:
                    return (f"No graded work yet for {module}. "
                            f"Components on file: "
                            f"{', '.join(c.get('name','?') for c in r.get('components', [])) or 'none'}.")
                return (f"{module}: {pct}% ({letter}) — "
                        f"{len(r.get('components') or [])} components, "
                        f"{len(r.get('missing') or [])} missing.")
    except Exception:
        pass

    # GPA fallback (legacy chatbot helper).
    try:
        gpa_info = chatbot.calculate_gpa(sid)
        if gpa_info and "error" not in gpa_info:
            return (f"Your current GPA is {gpa_info['gpa']} based on "
                    f"{gpa_info['total_credits']} credit hours.")
    except Exception:
        pass
    return ("Tell me a module code (e.g. 'CS101') for a specific grade, "
            "or check the student portal for the full transcript.")


def handle_technical_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle technical support queries"""
    return "I can help with basic technical issues. For complex problems, I'll connect you with our IT support team. What technical issue are you experiencing?"


def handle_general_query(chatbot, nlp_result: Dict, context: ConversationContext) -> str:
    """Handle general queries — first try a tool-keyword shim, then FAQ.

    Routes natural-language queries to the live chatbot_tools surface
    when keywords match (jobs / cases / clubs / schedule / certs /
    timetable / engagements / period). Falls through to FAQ matching
    when nothing matches.
    """
    user_message = context.messages[-1]["user_message"]

    tool_reply = _route_to_tools(chatbot, user_message, context)
    if tool_reply is not None:
        return tool_reply

    best_match = find_best_faq_match(chatbot, user_message)

    if best_match:
        return best_match

    # A bare module code with no other context is ambiguous — offer the two
    # things it's most likely to be about instead of a generic fallback.
    module = nlp_result_safe_module(user_message)
    if module and len(user_message.split()) <= 2:
        return (f"Did you mean module {module}? I can show your grade for it "
                f"(say 'grade {module}') or its timetable "
                f"(say 'timetable {module}').")

    return ("I'm here to help with university-related questions. You "
            "can ask about courses, registration, grades, fees, jobs, "
            "your timetable, cases, or technical support. How can I "
            "assist you today?")


def _route_to_tools(chatbot, message: str,
                    context: ConversationContext) -> Optional[str]:
    """Keyword-shim that turns common phrases into live tool calls.

    Returns a templated reply if a tool fired, ``None`` otherwise so
    the FAQ matcher gets a chance.
    """
    if not message:
        return None
    text = message.lower()
    sid = context.entities.get("student_id") or context.user_id

    try:
        from education_system.systems.university.services.bus.chatbot_tools import (
            call_tool,
        )
    except Exception:
        return None

    # Job board.
    if any(k in text for k in ("jobs", "job listings", "internship",
                               "vacancies", "openings")):
        try:
            res = call_tool("recent_jobs")
            jobs = res.get("jobs") if res.get("ok") else []
            if not jobs:
                return "No recent job postings on the board right now."
            lines = [
                f"• {j.get('job_title','?')} @ {j.get('company_name','?')}"
                f" ({j.get('location') or 'remote/unknown'})"
                for j in jobs[:5]
            ]
            return "Recent postings:\n" + "\n".join(lines)
        except Exception:
            pass

    # Cases.
    if any(k in text for k in ("misconduct case", "disciplinary",
                               "open cases", "case against me")):
        if not sid:
            return "Tell me your user ID and I'll check open cases."
        res = call_tool("my_open_cases", user_id=sid)
        cases = res.get("cases") if res.get("ok") else []
        if not cases:
            return "No open misconduct or disciplinary cases on file."
        lines = [
            f"• {c.get('kind')} #{c.get('case_id')} "
            f"({c.get('severity') or '—'}, {c.get('status') or 'open'})"
            for c in cases
        ]
        return "Open cases:\n" + "\n".join(lines)

    # SU clubs / engagements.
    if "club" in text or "society" in text or "societies" in text:
        if not sid:
            return "Tell me your student ID and I'll check your clubs."
        res = call_tool("my_clubs", user_id=sid)
        clubs = res.get("clubs") if res.get("ok") else []
        if not clubs:
            return "You aren't recorded in any active SU clubs yet."
        return ("Your active clubs: "
                + ", ".join(c.get("name") or "?" for c in clubs))

    if any(k in text for k in ("placement", "apprenticeship",
                               "engagement", "my placements")):
        if not sid:
            return "Tell me your student ID and I'll check engagements."
        res = call_tool("my_engagements", user_id=sid)
        engs = res.get("engagements") if res.get("ok") else []
        if not engs:
            return "No careers engagements recorded for you yet."
        active = [e for e in engs if e.get("status") == "active"]
        line = (f"{len(engs)} engagement(s); "
                f"{len(active)} active.")
        for e in active[:3]:
            req = e.get("hours_required") or 0
            done = e.get("hours_logged") or 0
            pct = f" ({done/req*100:.0f}%)" if req > 0 else ""
            line += (f"\n• {e.get('kind')}: {e.get('role') or '?'} "
                     f"— {int(done)}h{pct}")
        return line

    # Module timetable / schedule.
    if any(k in text for k in ("timetable", "schedule", "next class",
                               "when is")):
        # Try to extract a module code from the entities or the message.
        module = (nlp_result_safe_module(text)
                  or context.entities.get("module_code"))
        if module:
            res = call_tool("module_timeline", module_code=module)
            ev = res.get("events") if res.get("ok") else []
            if not ev:
                return f"No scheduled events on file for {module}."
            lines = [
                f"• {e.get('kind')} {e.get('date') or 'recurring'} "
                f"— {e.get('label') or ''}"
                for e in ev[:6]
            ]
            return f"{module}:\n" + "\n".join(lines)

    # Term / exam-window context.
    if any(k in text for k in ("term", "exam window", "exam period",
                               "submission window", "reading week")):
        kind = "term"
        for k in ("exam_window", "exam window", "submission_window",
                  "submission window", "reading_week", "reading week"):
            if k in text:
                kind = k.replace(" ", "_")
                break
        res = call_tool("current_period", kind=kind)
        period = res.get("period") if res.get("ok") else None
        if not period:
            return f"No active {kind.replace('_', ' ')} on the calendar."
        return (f"Current {kind.replace('_', ' ')}: "
                f"{period.get('name','?')} "
                f"({period.get('date_start') or period.get('date','?')}"
                f"{' → ' + period['date_end'] if period.get('date_end') else ''}).")

    # Trips — registered trips for the user, or all upcoming.
    if "trip" in text or "field trip" in text or "excursion" in text:
        if "upcoming" in text or "available" in text or "what trips" in text:
            res = call_tool("upcoming_trips")
            trips = res.get("trips") if res.get("ok") else []
            if not trips:
                return "No upcoming trips on the calendar."
            lines = [
                f"• {t.get('trip_name','?')} → {t.get('destination','?')} "
                f"({t.get('start_date','?')})"
                for t in trips[:5]
            ]
            return "Upcoming trips:\n" + "\n".join(lines)
        if not sid:
            return "Tell me your student ID and I'll list your trips."
        res = call_tool("my_trips", user_id=sid)
        regs = res.get("trips") if res.get("ok") else []
        if not regs:
            return "You're not registered on any trips."
        lines = [
            f"• {r.get('trip_name','?')} → {r.get('destination','?')} "
            f"({r.get('start_date','?')}) — {r.get('status','?')}"
            for r in regs[:5]
        ]
        return "Your trips:\n" + "\n".join(lines)

    # Parking — permits + fines.
    if "parking" in text or "permit" in text or "parking fine" in text:
        if not sid:
            return "Tell me your ID and I'll check parking."
        res = call_tool("my_parking", user_id=sid)
        if not res.get("ok"):
            return "Parking lookup is unavailable right now."
        permits = res.get("permits") or []
        fines = res.get("fines") or []
        bits = []
        if permits:
            active = [p for p in permits
                      if p.get("status") == "active"
                      or p.get("active_status") == 1]
            bits.append(f"{len(active)} active permit(s)")
        else:
            bits.append("no permits on file")
        if fines:
            total = sum(float(f.get("amount") or 0) for f in fines)
            bits.append(f"{len(fines)} outstanding fine(s) £{total:,.2f}")
        else:
            bits.append("no outstanding fines")
        return "Parking: " + " · ".join(bits) + "."

    # Restaurant menu / meal plan.
    if any(k in text for k in ("menu", "lunch", "dinner", "what's for")):
        res = call_tool("todays_menu")
        menus = res.get("menus") if res.get("ok") else []
        if not menus:
            return "No menu posted for today yet."
        first = menus[0]
        items = first.get("body", {}).get("items", [])
        loc = first.get("body", {}).get("location", "")
        if not items:
            return f"Menu for {first.get('date','today')} is empty."
        return (f"Today's menu ({loc or 'campus'}):\n"
                + "\n".join(f"• {i}" for i in items[:8]))

    if "meal plan" in text or "meal balance" in text:
        if not sid:
            return "Tell me your student ID and I'll check your meal plan."
        res = call_tool("meal_plan_balance", user_id=sid)
        if not res.get("ok"):
            return "Meal-plan lookup unavailable."
        return f"Meal-plan balance: £{float(res.get('balance') or 0):,.2f}."

    # Email prefs / opt-out.
    if any(k in text for k in ("email pref", "stop email", "unsubscribe",
                               "email notification", "stop emailing")):
        if not sid:
            return "Tell me your user ID and I'll list email preferences."
        res = call_tool("email_prefs", user_id=sid)
        prefs = res.get("prefs") if res.get("ok") else {}
        if not prefs:
            return "No email preferences on file."
        on = [k for k, v in prefs.items() if v]
        off = [k for k, v in prefs.items() if not v]
        return (f"You're opted into {len(on)} event(s), out of "
                f"{len(off)}. To toggle one, ask 'stop emailing me "
                f"about <event_kind>'.")

    # Cert expiry — for staff-facing chats.
    if "certif" in text or "expir" in text:
        res = call_tool("certs_expiring", within_days=60)
        certs = res.get("certs") if res.get("ok") else []
        if not certs:
            return "No certifications expiring in the next 60 days."
        lines = [
            f"• {c.get('kind','?')} (subject {c.get('subject_id')}) — "
            f"expires {c.get('expires_on','?')}"
            for c in certs[:5]
        ]
        return f"Expiring soon ({len(certs)} total):\n" + "\n".join(lines)

    return None


def nlp_result_safe_module(text: str) -> Optional[str]:
    """Tiny regex-free extractor: the first uppercase-letter+digits token."""
    for tok in (text or "").upper().split():
        if any(c.isalpha() for c in tok) and any(c.isdigit() for c in tok):
            cleaned = "".join(c for c in tok if c.isalnum())
            if 3 <= len(cleaned) <= 12:
                return cleaned
    return None


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

    # Timetable — if the user named a module, show that module's timeline;
    # otherwise point them at their personal schedule.
    if any(kw in user_message for kw in ["timetable", "schedule", "class time"]):
        # Only use a module named in THIS message — module_code persists in
        # context.entities across turns, so "show my timetable" must not pick
        # up a code mentioned earlier in the conversation.
        module = (nlp_result.get("entities", {}).get("module_code")
                  or nlp_result_safe_module(user_message))
        if module:
            try:
                from education_system.systems.university.services.bus.chatbot_tools import (
                    call_tool,
                )
                res = call_tool("module_timeline", module_code=module)
                ev = res.get("events") if res.get("ok") else []
                if ev:
                    lines = [
                        f"• {e.get('kind')} {e.get('date') or 'recurring'} "
                        f"— {e.get('label') or ''}"
                        for e in ev[:6]
                    ]
                    return f"{module} timetable:\n" + "\n".join(lines)
                return f"No scheduled events on file for {module}."
            except Exception:
                pass
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
    if any(kw in user_message for kw in ["room booking", "book a room", "facility",
                                         "meeting room", "my booking"]):
        # "Show my bookings" is a request to see existing bookings; "how do I
        # book a room" is a request for booking info. Only the former should
        # hit the database.
        wants_own = ("my" in user_message.split()
                     or any(w in user_message for w in ("show", "view", "list",
                                                        "see", "check"))
                     and "booking" in user_message)
        sid = context.entities.get("student_id") or context.user_id

        if wants_own:
            if not sid:
                return "Please log in to view your room bookings."
            bookings = chatbot.get_room_bookings(sid)
            if bookings:
                response = "Your Room Bookings:\n\n"
                for b in bookings:
                    response += f"  {b['room']} — {b['date']}\n"
                    response += f"    Time: {b['start']} - {b['end']}  |  Status: {b['status']}\n\n"
                return response
            return ("You have no upcoming room bookings.\n\n"
                    "  To make one, use the room booking system on the student\n"
                    "  portal or contact facilities@university.ac.uk")

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

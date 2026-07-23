"""Conversation logging, tracking, and user context retrieval."""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

from education_system.post_18.university_system.infrastructure.database.db import sqlite3


def get_user_context(chatbot, username):
    """Get user context from authentication system"""
    if not chatbot.auth_system:
        return {"username": username, "role": "guest", "permissions": []}

    try:
        current_user = chatbot.auth_system.current_user
        if current_user and current_user['username'] == username:
            return {
                "username": username,
                "role": current_user['role'],
                "permissions": current_user.get('permissions', []),
                "user_id": current_user['id']
            }
    except Exception as e:
        logging.error(f"Error getting user context: {e}")

    return {"username": username, "role": "guest", "permissions": []}


def generate_contextual_response(chatbot, message, user_context):
    """Generate response based on user context and message"""
    message_lower = message.lower()
    role = user_context.get('role', 'guest')
    permissions = user_context.get('permissions', [])

    if any(word in message_lower for word in ['hello', 'hi', 'hey']):
        if role == 'student':
            return "Hello! I'm here to help with your academic needs. You can ask about courses, grades, registration, and more."
        elif role == 'staff':
            return "Hello! I can help you with student information, course management, and administrative tasks."
        elif role == 'admin':
            return "Hello! I have full access to help you with any university system functions."
        else:
            return "Hello! I'm the University Chatbot. How can I help you today?"

    elif any(word in message_lower for word in ['course', 'class', 'program', 'module']):
        if role == 'student':
            return "I can help you find course information, check prerequisites, and guide you through registration. What specific course or program are you interested in?"
        elif role in ['staff', 'admin']:
            return "I can help you with course management, student enrollment, and academic planning. What course information do you need?"
        else:
            return "I can provide general course information. For specific enrollment details, please contact the registrar's office."

    elif any(word in message_lower for word in ['grade', 'gpa', 'transcript', 'academic record']):
        if 'view_own_grades' in permissions or 'manage_grades' in permissions:
            return "I can help you with grade information. For official transcripts, please check your student portal or contact the registrar's office."
        elif role in ['staff', 'admin']:
            return "I can help you access student grade information and generate academic reports."
        else:
            return "For grade information, please check your student portal or contact the registrar's office."

    elif any(word in message_lower for word in ['fee', 'tuition', 'payment', 'financial', 'scholarship']):
        if 'view_own_finances' in permissions or 'manage_finances' in permissions:
            return "I can help with financial information including tuition, fees, and payment options. For specific account details, please check your student account online."
        else:
            return "For financial information, please visit the bursar's office or check your student account online."

    elif any(word in message_lower for word in ['register', 'enrollment', 'enroll']):
        if role == 'student':
            return "I can guide you through the registration process. Registration is typically available through the student portal during designated periods. Would you like help with course selection?"
        elif role in ['staff', 'admin']:
            return "I can help you with student registration management and enrollment processes."
        else:
            return "For registration information, please contact the registrar's office or check the academic calendar."

    elif any(word in message_lower for word in ['help', 'support']):
        features = []
        if role == 'student':
            features = [
                "• Course information and enrollment",
                "• Academic records and grades",
                "• Financial information",
                "• Registration assistance",
                "• General university policies"
            ]
        elif role in ['staff', 'admin']:
            features = [
                "• Student information management",
                "• Course and module management",
                "• Administrative support",
                "• System information",
                "• Report generation"
            ]
        else:
            features = [
                "• General university information",
                "• Course catalogs",
                "• Contact information",
                "• Campus resources"
            ]

        return "I'm here to help with university-related questions including:\n" + "\n".join(features)

    elif any(word in message_lower for word in ['voice', 'speak', 'listen']):
        if 'voice_interaction' in permissions:
            return "Voice features are available! You can speak your questions naturally. Say 'voice help' for more voice commands."
        else:
            return "Voice features require special permissions. Please contact your administrator."

    elif role == 'admin' and any(word in message_lower for word in ['system', 'database', 'admin']):
        return "As an administrator, I can help you with system management, user administration, database operations, and advanced reporting."

    else:
        if role == 'guest':
            return "I'm here to help with university-related questions. For personalized assistance, please log in to access more features."
        else:
            return f"I'm here to help with university-related questions. As a {role}, you have access to specialized features. What would you like to know?"


def log_conversation(chatbot, username, message, response, session_id):
    """Log conversation to database"""
    try:
        conn = sqlite3.connect(chatbot.db_path)
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            session_id TEXT
        )
        ''')

        user_id = None
        if chatbot.auth_system and chatbot.auth_system.current_user:
            user_id = chatbot.auth_system.current_user.get('id')

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO chatbot_conversations
        (user_id, username, message, response, timestamp, session_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, message, response, timestamp, session_id))

        conn.commit()
        conn.close()

    except Exception as e:
        logging.error(f"Error logging conversation: {e}")
        pass


def track_conversation(chatbot, username, message, response, is_voice=False):
    """Track conversation in memory for session"""
    if username not in chatbot.conversation_history:
        chatbot.conversation_history[username] = []

    chatbot.conversation_history[username].append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'message': message,
        'response': response,
        'type': 'voice' if is_voice else 'text'
    })

    if len(chatbot.conversation_history[username]) > 50:
        chatbot.conversation_history[username] = chatbot.conversation_history[username][-50:]


def get_conversation_history(chatbot, username, limit=10):
    """Get conversation history for user"""
    return chatbot.conversation_history.get(username, [])[-limit:]


def log_enhanced_conversation(chatbot, user_id: str, user_message: str, bot_response: str, nlp_result: Dict, session_id: Optional[str] = None):
    """Log conversation with enhanced metadata and session tracking"""
    timestamp = datetime.now().isoformat()
    log_date = datetime.now().strftime("%Y-%m-%d")
    log_filename = os.path.join(chatbot.log_dir, f"enhanced_log_{log_date}.json")

    log_entry = {
        "timestamp": timestamp,
        "user_id": user_id,
        "session_id": session_id,
        "user_message": user_message,
        "bot_response": bot_response,
        "intent": nlp_result.get("intent"),
        "confidence": nlp_result.get("confidence"),
        "sentiment": nlp_result.get("sentiment"),
        "entities": nlp_result.get("entities"),
        "escalated": nlp_result.get("requires_escalation", False),
        "is_voice": nlp_result.get("is_voice_command", False)
    }

    if os.path.exists(log_filename):
        with open(log_filename, 'r') as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []
    else:
        logs = []

    logs.append(log_entry)

    with open(log_filename, 'w') as f:
        json.dump(logs, f, indent=4)

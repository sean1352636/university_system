"""Flask API route definitions for the chatbot web server."""

from datetime import datetime

from education_system.systems.university.shared.ai.chatbot.fallbacks import (
    LIBRARIES_AVAILABLE,
    jsonify,
    request,
)


def _own_student(chatbot, student_id):
    """``(own_id, None)`` when the bearer token's holder is this student,
    else ``(None, error response)``. A student id in the URL is never
    trusted on its own."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    session = chatbot.validate_chatbot_session(token) or chatbot.validate_session(token)
    if not session:
        return None, (jsonify({"error": "Sign in required"}), 401)
    who = getattr(session, 'username', None) or session.user_id
    from education_system.systems.university.application.chatbot import care as chatbot_care
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    conn = get_connection(getattr(chatbot, 'db_path', None), row_factory=False)
    try:
        own, refusal = chatbot_care.personal_access(conn, who, student_id)
    finally:
        conn.close()
    if refusal:
        return None, (jsonify({"error": refusal}), 403)
    return own, None


def setup_api_routes(chatbot):
    """Setup enhanced API routes with authentication"""
    if not LIBRARIES_AVAILABLE['flask']:
        print("Flask not available - web API routes disabled")
        return

    @chatbot.app.route('/api/chat', methods=['POST'])
    def api_chat():
        data = request.json
        message = data.get('message', '')
        # Unauthenticated: never trust a user id from the request body (it
        # let a caller ask as anyone). Personal answers need
        # /api/chat/authenticated with a session token.
        response = chatbot.process_message(message, 'anonymous')

        return jsonify({
            "response": response,
            "timestamp": datetime.now().isoformat()
        })

    @chatbot.app.route('/api/auth/login', methods=['POST'])
    def api_auth_login():
        return jsonify({
            'success': False,
            'error': 'Authentication must be performed through the main application',
            'message': 'Please log in via the main GUI (python -m education_system --gui) first'
        }), 401

    @chatbot.app.route('/api/auth/logout', methods=['POST'])
    def api_auth_logout():
        return jsonify({
            'success': False,
            'error': 'Logout must be performed through the main application',
            'message': 'Please log out via the main GUI'
        }), 401

    @chatbot.app.route('/api/auth/status', methods=['GET'])
    def api_auth_status():
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user_info = chatbot.get_authenticated_user_info(session_token)

        if user_info:
            return jsonify({"authenticated": True, "user": user_info})
        else:
            return jsonify({"authenticated": False}), 401

    @chatbot.app.route('/api/chat/authenticated', methods=['POST'])
    def api_authenticated_chat():
        data = request.json
        message = data.get('message', '')
        session_token = data.get('session_token', '')
        is_voice = data.get('is_voice', False)

        response = chatbot.process_authenticated_message(message, session_token, is_voice)

        return jsonify({
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "authenticated": True
        })

    @chatbot.app.route('/api/permissions/check', methods=['POST'])
    def api_check_permission():
        data = request.json
        session_token = data.get('session_token', '')
        permission = data.get('permission', '')

        has_permission = chatbot.check_user_permission(session_token, permission)

        return jsonify({
            "has_permission": has_permission,
            "permission": permission
        })

    @chatbot.app.route('/api/voice/test', methods=['GET'])
    def api_voice_test():
        """Test voice interface"""
        result = chatbot.test_voice_interface()
        return jsonify(result)

    @chatbot.app.route('/api/voice/record', methods=['POST'])
    def api_voice_record():
        """Record voice input and convert to text"""
        data = request.json
        duration = data.get('duration', 5.0)
        session_token = data.get('session_token', '')

        session = chatbot.validate_session(session_token)
        if not session:
            return jsonify({"error": "Invalid session"}), 401

        text = chatbot.process_voice_input(duration)

        if text:
            response = chatbot.process_message(text, session.user_id)
            return jsonify({
                "recognized_text": text,
                "response": response,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "No speech recognized"}), 400

    @chatbot.app.route('/api/voice/tts', methods=['POST'])
    def api_text_to_speech():
        """Convert text to speech"""
        data = request.json
        text = data.get('text', '')

        if not text:
            return jsonify({"error": "No text provided"}), 400

        success = chatbot.text_to_speech(text)

        return jsonify({
            "success": success,
            "message": "Text converted to speech" if success else "TTS failed"
        })

    @chatbot.app.route('/api/login', methods=['POST'])
    def api_login():
        return jsonify({
            'success': False,
            'error': 'Authentication must be performed through the main application',
            'message': 'Please log in via the main GUI (python -m education_system --gui) first'
        }), 401

    @chatbot.app.route('/api/recommendations/<student_id>', methods=['GET'])
    def api_recommendations(student_id):
        own, error = _own_student(chatbot, student_id)
        if error:
            return error
        recommendations = chatbot.get_course_recommendations(own)
        return jsonify({"recommendations": recommendations})

    @chatbot.app.route('/api/gpa/<student_id>', methods=['GET'])
    def api_gpa(student_id):
        own, error = _own_student(chatbot, student_id)
        if error:
            return error
        gpa_info = chatbot.calculate_gpa(own)
        return jsonify(gpa_info)


def setup_enhanced_api_routes(chatbot):
    """Enhanced API routes setup"""
    setup_api_routes(chatbot)

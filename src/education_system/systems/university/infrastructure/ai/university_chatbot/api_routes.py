"""Flask API route definitions for the chatbot web server."""

from datetime import datetime

from education_system.systems.university.infrastructure.ai.university_chatbot.fallbacks import (
    LIBRARIES_AVAILABLE,
    jsonify,
    request,
)


def setup_api_routes(chatbot):
    """Setup enhanced API routes with authentication"""
    if not LIBRARIES_AVAILABLE['flask']:
        print("Flask not available - web API routes disabled")
        return

    @chatbot.app.route('/api/chat', methods=['POST'])
    def api_chat():
        data = request.json
        message = data.get('message', '')
        user_id = data.get('user_id', 'anonymous')

        response = chatbot.process_message(message, user_id)

        return jsonify({
            "response": response,
            "timestamp": datetime.now().isoformat()
        })

    @chatbot.app.route('/api/auth/login', methods=['POST'])
    def api_auth_login():
        return jsonify({
            'success': False,
            'error': 'Authentication must be performed through the main application',
            'message': 'Please log in via the main GUI (python run.py --gui) first'
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
            'message': 'Please log in via the main GUI (python run.py --gui) first'
        }), 401

    @chatbot.app.route('/api/recommendations/<student_id>', methods=['GET'])
    def api_recommendations(student_id):
        recommendations = chatbot.get_course_recommendations(student_id)
        return jsonify({"recommendations": recommendations})

    @chatbot.app.route('/api/gpa/<student_id>', methods=['GET'])
    def api_gpa(student_id):
        gpa_info = chatbot.calculate_gpa(student_id)
        return jsonify(gpa_info)


def setup_enhanced_api_routes(chatbot):
    """Enhanced API routes setup"""
    setup_api_routes(chatbot)

"""Shared API error handler registration for all system APIs.

Provides:
- Common HTTP error handlers (404, 405, 413, 422, 429, 500)
- Payload validation error handling
- A factory function for domain-specific error handlers
- Consistent JSON error response format across all systems
"""

from flask import jsonify
import logging

logger = logging.getLogger(__name__)


def register_common_error_handlers(app):
    """Register error handlers common to all systems."""

    @app.errorhandler(400)
    def handle_bad_request(e):
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "Not Found", "message": "Resource not found."}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({"error": "Method Not Allowed", "message": str(e)}), 405

    @app.errorhandler(413)
    def handle_request_too_large(e):
        max_bytes = app.config.get("MAX_CONTENT_LENGTH", 0)
        max_mb = max_bytes / (1024 * 1024) if max_bytes else 0
        return jsonify({
            "error": "Request Entity Too Large",
            "message": f"Maximum request size is {max_mb:.0f} MB" if max_mb else "Request too large",
        }), 413

    @app.errorhandler(429)
    def handle_rate_limited(e):
        return jsonify({"error": "Rate Limit Exceeded", "message": "Too many requests. Please try again later."}), 429

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error("Internal server error: %s", e)
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

    # Payload validation errors (from request_validator.py)
    try:
        from education_system.shared.api.request_validator import PayloadValidationError

        @app.errorhandler(PayloadValidationError)
        def handle_payload_validation(e):
            return jsonify({
                "error": "Validation Error",
                "message": str(e),
                "details": e.errors,
            }), 422
    except ImportError:
        pass

    # API validation errors (from validators.py)
    try:
        from education_system.shared.api.validators import APIValidationError

        @app.errorhandler(APIValidationError)
        def handle_api_validation(e):
            return jsonify({"error": "Validation Error", "message": str(e)}), 400
    except ImportError:
        pass


def domain_error_handler(error_class, label: str, status: int = 400):
    """Create a standard error handler for a domain exception class.

    Ensures consistent JSON error response format:
        {"error": "<label>", "message": "<exception message>"}

    Usage in a system's ``register_error_handlers``::

        app.register_error_handler(StudentError, domain_error_handler(StudentError, "Student Error"))
    """
    def handler(e):
        if status >= 500:
            logger.error("%s: %s", label, e)
        else:
            logger.warning("%s: %s", label, e)
        return jsonify({"error": label, "message": str(e)}), status
    handler.__name__ = f"handle_{error_class.__name__}"
    return handler

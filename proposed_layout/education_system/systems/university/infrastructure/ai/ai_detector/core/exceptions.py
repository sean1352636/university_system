class AIDetectionError(Exception):
    """Base exception for AI detection errors"""
    def __init__(self, message="An error occurred in the AI detection system"):
        self.message = message
        super().__init__(self.message)

class DatabaseError(AIDetectionError):
    """Exception raised for database connection/query errors"""
    def __init__(self, message="Database error occurred", query=None):
        self.query = query
        if query:
            message = f"{message} (Query: {query})"
        super().__init__(message)

class APIError(AIDetectionError):
    """Exception raised for API-related errors"""
    def __init__(self, message="API error occurred", status_code=None):
        self.status_code = status_code
        if status_code:
            message = f"{message} (Status code: {status_code})"
        super().__init__(message)

class ConfigurationError(AIDetectionError):
    """Exception raised for configuration errors"""
    def __init__(self, message="Configuration error occurred", setting=None):
        self.setting = setting
        if setting:
            message = f"{message} (Setting: {setting})"
        super().__init__(message)

class PrivacyError(AIDetectionError):
    """Exception raised for privacy violations"""
    pass

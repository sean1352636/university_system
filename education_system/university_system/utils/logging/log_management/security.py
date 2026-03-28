"""Security features for log management."""

import hashlib
import json


class LogSecurity:
    """Security features for log management"""

    @staticmethod
    def generate_hash(data):
        """Generate SHA-256 hash for data integrity"""
        return hashlib.sha256(str(data).encode()).hexdigest()

    @staticmethod
    def verify_integrity(log_entry, stored_hash):
        """Verify log entry integrity"""
        return LogSecurity.generate_hash(log_entry) == stored_hash

    @staticmethod
    def anonymize_data(data, fields_to_anonymize=['username', 'user_id']):
        """Anonymize sensitive data in logs"""
        anonymized = data.copy()
        for field in fields_to_anonymize:
            if field in anonymized:
                # Replace with hashed version
                anonymized[field] = hashlib.sha256(str(anonymized[field]).encode()).hexdigest()[:8]
        return anonymized

    @staticmethod
    def encrypt_log(log_data, key):
        """Simple encryption for log data (in production, use proper encryption)"""
        # This is a simplified example - use proper encryption libraries in production
        import base64
        encoded = base64.b64encode(json.dumps(log_data).encode()).decode()
        return encoded

    @staticmethod
    def decrypt_log(encrypted_data, key):
        """Decrypt log data"""
        import base64
        try:
            decoded = base64.b64decode(encrypted_data.encode()).decode()
            return json.loads(decoded)
        except (ValueError, TypeError, Exception):
            return None

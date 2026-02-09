import hashlib
import secrets
from typing import Tuple, Optional
from .exceptions import ValidationError

def hash_password(password: str, salt: Optional[bytes] = None,
                 iterations: int = 100000) -> Tuple[str, str]:
    """
    Hash password securely using PBKDF2-SHA256

    Uses PBKDF2 with SHA256 for secure password hashing.

    Args:
        password: Password to hash
        salt: Salt bytes (auto-generated if not provided)
        iterations: Number of PBKDF2 iterations (default: 100,000)

    Returns:
        Tuple[str, str]: (hashed_password_hex, salt_hex)

    Example:
        password_hash, salt = hash_password("user_password")
        # Store both password_hash and salt in database
    """
    if not password:
        raise ValidationError.required_field("password")

    # Generate salt if not provided
    if salt is None:
        salt = secrets.token_bytes(32)  # 256-bit salt

    # Hash password using PBKDF2-SHA256
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        iterations
    )

    return password_hash.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt: str,
                   iterations: int = 100000) -> bool:
    """
    Verify hashed password

    Compares provided password against stored hash using constant-time comparison.

    Args:
        password: Password to verify
        password_hash: Stored password hash (hex)
        salt: Stored salt (hex)
        iterations: Number of PBKDF2 iterations (must match hash_password)

    Returns:
        bool: True if password matches, False otherwise

    Example:
        if verify_password(user_input, stored_hash, stored_salt):
            print("Password correct")
    """
    if not password or not password_hash or not salt:
        return False

    try:
        # Convert hex strings back to bytes
        salt_bytes = bytes.fromhex(salt)
        stored_hash_bytes = bytes.fromhex(password_hash)

        # Hash the provided password with the same salt
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt_bytes,
            iterations
        )

        # Constant-time comparison to prevent timing attacks
        return secrets.compare_digest(computed_hash, stored_hash_bytes)

    except (ValueError, AttributeError):
        return False


def generate_token(length: int = 32, url_safe: bool = True) -> str:
    """
    Generate secure random token

    Creates cryptographically secure random tokens for sessions,
    API keys, CSRF tokens, etc.

    Args:
        length: Token length in bytes (default: 32 = 256 bits)
        url_safe: Whether to generate URL-safe token (default: True)

    Returns:
        str: Secure random token

    Example:
        session_token = generate_token(32)
        api_key = generate_token(64)
    """
    if length < 16:
        raise ValidationError(
            "Token length must be at least 16 bytes for security",
            field="length"
        )

    if url_safe:
        # URL-safe base64 encoded token
        return secrets.token_urlsafe(length)
    else:
        # Hexadecimal token
        return secrets.token_hex(length)



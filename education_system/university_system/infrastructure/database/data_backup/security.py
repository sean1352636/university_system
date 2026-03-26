"""Encryption, decryption, hashing, integrity checks, and secure file deletion."""

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.infrastructure.database.data_backup.config import config

logger = configure_logging(name=__name__)


def generate_encryption_key(password: str) -> bytes:
    """Generate encryption key from password"""
    password_bytes = password.encode()
    salt = b'backup_salt_12345'  # In production, use random salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    return key


def encrypt_file(file_path: str, password: str) -> str:
    """Encrypt a file and return the encrypted file path"""
    try:
        key = generate_encryption_key(password)
        fernet = Fernet(key)

        encrypted_path = file_path + '.encrypted'

        with open(file_path, 'rb') as original_file:
            original_data = original_file.read()

        encrypted_data = fernet.encrypt(original_data)

        with open(encrypted_path, 'wb') as encrypted_file:
            encrypted_file.write(encrypted_data)

        # Remove original file if secure deletion is enabled
        if config["secure_deletion"]:
            secure_delete_file(file_path)
        else:
            os.remove(file_path)

        return encrypted_path
    except (OSError, IOError) as e:
        logger.error(f"File I/O error during encryption: {e}")
        return None
    except (ValueError, TypeError) as e:
        logger.error("Encryption error (invalid key or data)")
        return None


def decrypt_file(encrypted_path: str, password: str, output_path: str = None) -> str:
    """Decrypt a file and return the decrypted file path"""
    from cryptography.fernet import InvalidToken
    try:
        key = generate_encryption_key(password)
        fernet = Fernet(key)

        if output_path is None:
            output_path = encrypted_path.replace('.encrypted', '')

        with open(encrypted_path, 'rb') as encrypted_file:
            encrypted_data = encrypted_file.read()

        decrypted_data = fernet.decrypt(encrypted_data)

        with open(output_path, 'wb') as decrypted_file:
            decrypted_file.write(decrypted_data)

        return output_path
    except (OSError, IOError) as e:
        logger.error(f"File I/O error during decryption: {e}")
        return None
    except InvalidToken as e:
        logger.error("Decryption failed - invalid password or corrupted data")
        return None
    except (ValueError, TypeError) as e:
        logger.error("Decryption error (invalid key format)")
        return None


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except (OSError, IOError) as e:
        logger.error(f"Error reading file for hash calculation: {e}")
        return None


def verify_backup_integrity(backup_path: str, expected_hash: str = None) -> bool:
    """Verify backup file integrity"""
    try:
        current_hash = calculate_file_hash(backup_path)
        if expected_hash:
            return current_hash == expected_hash
        return current_hash is not None
    except (OSError, IOError) as e:
        logger.error(f"Error reading backup file for integrity check: {e}")
        return False


def secure_delete_file(file_path: str, passes: int = 3):
    """Securely delete a file by overwriting it multiple times"""
    try:
        if not os.path.exists(file_path):
            return

        file_size = os.path.getsize(file_path)

        with open(file_path, "r+b") as file:
            for _ in range(passes):
                file.seek(0)
                file.write(os.urandom(file_size))
                file.flush()
                os.fsync(file.fileno())

        os.remove(file_path)
        logger.info(f"Securely deleted file: {file_path}")
    except (OSError, IOError) as e:
        logger.error(f"Error securely deleting file: {e}")
    except PermissionError as e:
        logger.error(f"Permission denied while securely deleting file: {e}")

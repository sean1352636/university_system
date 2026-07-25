#!/usr/bin/env python3
"""
Data Encryption at Rest System
Features:
- Encrypt sensitive database columns (SSN, grades, health records)
- Encrypted file storage for documents
- Key rotation policies
- Encryption key management system
- Encrypted backups
"""

import os
import sys
from education_system.systems.university.infrastructure.database.db import sqlite3
import secrets
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from cryptography.fernet import Fernet
import base64

# Import centralized database path and connection utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text, _

# Import KMS integration for secure master key storage
from education_system.systems.university.infrastructure.security.kms_integration import (
    KMSIntegration,
    KMSError,
    KMSProviderNotConfigured,
    KMSKeyRetrievalError,
    is_kms_enabled,
    get_kms_integration,
)

# Import SQL safety utilities to prevent SQL injection in dynamic queries
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger(__name__)

# Import immutable audit logging for compliance
try:
    from education_system.systems.university.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

class EncryptionManager:
    """Manages encryption keys and data encryption/decryption"""

    def __init__(self, db_path: str = None, master_key: bytes = None, use_kms: bool = None):
        """
        Initialize encryption manager

        Args:
            db_path: Path to database
            master_key: Master encryption key (if None, will be loaded from KMS or environment)
            use_kms: Force KMS usage (True/False) or auto-detect from environment (None)
        """
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)

        self.db_path = db_path

        # Determine if KMS should be used
        if use_kms is None:
            use_kms = is_kms_enabled()

        self._use_kms = use_kms
        self._kms: Optional[KMSIntegration] = None

        # Get or generate master key
        if master_key is None:
            master_key = self._get_or_create_master_key()

        self.master_key = master_key
        self.master_fernet = Fernet(master_key)

        # Cache for data encryption keys
        self._key_cache = {}

    def _get_or_create_master_key(self) -> bytes:
        """
        Get master key from KMS, environment, or generate new one.

        Priority:
        1. KMS (if USE_KMS=true and provider is configured)
        2. File-based storage (development/fallback)

        Returns:
            Master encryption key as bytes
        """
        # Try KMS first if enabled
        if self._use_kms:
            try:
                self._kms = get_kms_integration()
                if self._kms and self._kms.is_configured():
                    key = self._kms.get_master_key()
                    logger.info("Master key retrieved from KMS")

                    # Immutable audit log for KMS key retrieval
                    if IMMUTABLE_AUDIT_AVAILABLE:
                        safe_log_security_event(
                            action=AuditAction.CONFIG_CHANGE,
                            user_id='system',
                            resource_type='encryption',
                            details={'key_source': 'kms', 'operation': 'master_key_retrieved'}
                        )

                    return key
                else:
                    logger.warning(
                        "KMS is enabled but not properly configured. "
                        "Falling back to file-based key storage."
                    )
            except KMSError:
                logger.error("KMS error. Falling back to file-based key storage.")
            except Exception:
                logger.error("Unexpected KMS error. Falling back to file-based key storage.")

        # Fall back to file-based storage (development/non-production)
        return self._get_or_create_file_based_key()

    def _get_or_create_file_based_key(self) -> bytes:
        """
        Get or create master key from file storage.

        WARNING: File-based key storage should only be used in development.
        In production, use KMS integration (USE_KMS=true).

        Returns:
            Master encryption key as bytes
        """
        logger.warning(
            "Using FILE-BASED encryption key storage. "
            "This is NOT recommended for production. "
            "Set USE_KMS=true and configure a KMS provider for secure key management."
        )

        # Store keys in a separate .keys directory under the project root,
        # NOT alongside the database files
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        keys_dir = os.path.join(project_root, '.keys')
        os.makedirs(keys_dir, exist_ok=True)
        # Restrict directory permissions
        try:
            os.chmod(keys_dir, 0o700)
        except OSError:
            logger.warning("Could not set restrictive permissions on keys directory: %s", keys_dir)

        master_key_path = os.path.join(keys_dir, '.encryption_master_key')

        # Support legacy key location for backward compatibility
        legacy_key_path = os.path.join(
            os.path.dirname(self.db_path),
            '.encryption_master_key'
        )
        if not os.path.exists(master_key_path) and os.path.exists(legacy_key_path):
            logger.info("Migrating encryption key from legacy location to %s", keys_dir)
            try:
                import shutil
                shutil.move(legacy_key_path, master_key_path)
                os.chmod(master_key_path, 0o600)
            except Exception:
                logger.error("Failed to migrate legacy key file")
                # Fall back to legacy path if migration fails
                master_key_path = legacy_key_path

        # Try to load existing key
        if os.path.exists(master_key_path):
            try:
                with open(master_key_path, 'rb') as f:
                    key = f.read()
                logger.debug("Master key loaded from file")
                return key
            except Exception:
                logger.error("Failed to load master key")

        # Generate new master key
        logger.warning(
            "Generating new master key with FILE-BASED storage. "
            "For production, configure KMS (USE_KMS=true) for secure key management."
        )
        logger.warning("Generating new master key with file-based storage")
        logger.warning("In production, set USE_KMS=true and configure a KMS provider")

        master_key = Fernet.generate_key()

        # Save master key (with restricted permissions)
        try:
            with open(master_key_path, 'wb') as f:
                f.write(master_key)
            os.chmod(master_key_path, 0o600)  # Read/write for owner only
            logger.info(f"Master key saved to: {master_key_path}")

            # Immutable audit log for new key generation
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.CONFIG_CHANGE,
                    user_id='system',
                    resource_type='encryption',
                    details={
                        'key_source': 'file',
                        'operation': 'master_key_generated',
                        'new_key': True
                    }
                )

        except Exception:
            logger.error("Failed to save master key")

        return master_key

    def is_using_kms(self) -> bool:
        """
        Check if KMS is being used for master key storage.

        Returns:
            True if KMS is active, False if using file-based storage
        """
        return self._kms is not None and self._kms.is_configured()

    def _get_connection(self):
        """Get database connection using centralized pool"""
        return get_connection(db_path=self.db_path, row_factory=True)

    def create_encryption_key(self, key_type: str = 'data') -> Dict:
        """
        Create a new encryption key

        Args:
            key_type: Type of key ('master', 'data', 'file')

        Returns:
            Dict with key_id and key
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Generate data encryption key
            data_key = Fernet.generate_key()

            # Encrypt the data key with master key
            encrypted_key = self.master_fernet.encrypt(data_key)

            # Generate unique key ID
            key_id = f"{key_type}_{secrets.token_hex(8)}"

            # Store in database
            cursor.execute("""
                INSERT INTO encryption_keys (
                    key_id, key_type, encrypted_key, created_at, is_active, version
                )
                VALUES (?, ?, ?, ?, 1, 1)
            """, (key_id, key_type, encrypted_key.decode(), datetime.now()))

            conn.commit()

            # Cache the key
            self._key_cache[key_id] = data_key

            return {
                'success': True,
                'key_id': key_id,
                'key': data_key
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def get_encryption_key(self, key_id: str) -> Optional[bytes]:
        """
        Get encryption key by ID

        Args:
            key_id: Key identifier

        Returns:
            Decrypted encryption key or None
        """
        # Check cache first
        if key_id in self._key_cache:
            return self._key_cache[key_id]

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT encrypted_key FROM encryption_keys
                WHERE key_id = ? AND is_active = 1
            """, (key_id,))

            row = cursor.fetchone()

            if row:
                encrypted_key = row[0].encode()
                # Decrypt with master key
                data_key = self.master_fernet.decrypt(encrypted_key)

                # Cache the key
                self._key_cache[key_id] = data_key

                return data_key

            return None

        finally:
            conn.close()

    def rotate_key(self, old_key_id: str) -> Dict:
        """
        Rotate encryption key

        Creates new key and marks old as inactive
        Data should be re-encrypted with new key

        Returns:
            Dict with new_key_id
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get old key info
            cursor.execute("""
                SELECT key_type, version FROM encryption_keys
                WHERE key_id = ?
            """, (old_key_id,))

            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': 'Key not found'}

            key_type, old_version = row

            # Create new key
            new_key_result = self.create_encryption_key(key_type)

            if not new_key_result['success']:
                return new_key_result

            new_key_id = new_key_result['key_id']

            # Update new key version
            cursor.execute("""
                UPDATE encryption_keys
                SET version = ?
                WHERE key_id = ?
            """, (old_version + 1, new_key_id))

            # Mark old key as rotated
            cursor.execute("""
                UPDATE encryption_keys
                SET is_active = 0, rotated_at = ?
                WHERE key_id = ?
            """, (datetime.now(), old_key_id))

            # Get fields encrypted with old key
            cursor.execute("""
                SELECT table_name, column_name
                FROM encrypted_fields_metadata
                WHERE key_id = ?
            """, (old_key_id,))

            fields_to_reencrypt = cursor.fetchall()

            conn.commit()

            return {
                'success': True,
                'new_key_id': new_key_id,
                'old_key_id': old_key_id,
                'fields_to_reencrypt': [
                    {'table': t, 'column': c} for t, c in fields_to_reencrypt
                ]
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def encrypt_value(self, value: str, key_id: str) -> str:
        """
        Encrypt a value using specified key

        Args:
            value: Plain text value
            key_id: Encryption key ID

        Returns:
            Base64 encoded encrypted value
        """
        if value is None:
            return None

        key = self.get_encryption_key(key_id)
        if not key:
            raise ValueError(f"Encryption key {key_id} not found")

        fernet = Fernet(key)
        encrypted = fernet.encrypt(value.encode())
        return encrypted.decode()

    def decrypt_value(self, encrypted_value: str, key_id: str) -> str:
        """
        Decrypt a value using specified key

        Args:
            encrypted_value: Base64 encoded encrypted value
            key_id: Encryption key ID

        Returns:
            Decrypted plain text
        """
        if encrypted_value is None:
            return None

        key = self.get_encryption_key(key_id)
        if not key:
            raise ValueError(f"Encryption key {key_id} not found")

        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()

    def encrypt_field(self, table_name: str, column_name: str,
                     record_id: int, value: str, key_id: str = None) -> Dict:
        """
        Encrypt a specific database field

        Args:
            table_name: Database table
            column_name: Column to encrypt
            record_id: Record ID
            value: Value to encrypt
            key_id: Optional key ID (will create if not provided)

        Returns:
            Dict with success status
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # SECURITY: Validate table and column names to prevent SQL injection
            try:
                validated_table = validate_table_name(table_name, conn=conn)
                validated_column = validate_column_name(
                    column_name,
                    table_name=validated_table,
                    conn=conn
                )
            except SQLIdentifierError as e:
                logger.error(f"SQL injection prevention: {e}")
                return {'success': False, 'error': f"Invalid identifier: {e}"}

            # Get or create encryption key
            if not key_id:
                # Check if field already has a key
                cursor.execute("""
                    SELECT key_id FROM encrypted_fields_metadata
                    WHERE table_name = ? AND column_name = ?
                """, (table_name, column_name))

                row = cursor.fetchone()

                if row:
                    key_id = row[0]
                else:
                    # Create new key for this field
                    key_result = self.create_encryption_key('data')
                    key_id = key_result['key_id']

                    # Register field metadata
                    cursor.execute("""
                        INSERT INTO encrypted_fields_metadata (
                            table_name, column_name, key_id
                        )
                        VALUES (?, ?, ?)
                    """, (table_name, column_name, key_id))

            # Encrypt value
            encrypted_value = self.encrypt_value(value, key_id)

            # Update database using validated identifiers
            # SECURITY: table_name and column_name have been validated above
            query = f"""
                UPDATE [{validated_table}]
                SET [{validated_column}] = ?
                WHERE id = ?
            """
            cursor.execute(query, (encrypted_value, record_id))

            conn.commit()

            return {
                'success': True,
                'key_id': key_id,
                'encrypted': True
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def decrypt_field(self, table_name: str, column_name: str,
                     record_id: int = None, encrypted_value: str = None) -> str:
        """
        Decrypt a database field

        Args:
            table_name: Database table
            column_name: Column to decrypt
            record_id: Optional record ID (if not providing encrypted_value)
            encrypted_value: Optional encrypted value (if not querying database)

        Returns:
            Decrypted value

        Raises:
            ValueError: If encryption key not found or record not found
            SQLIdentifierError: If table or column name is invalid
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # SECURITY: Validate table and column names to prevent SQL injection
            validated_table = validate_table_name(table_name, conn=conn)
            validated_column = validate_column_name(
                column_name,
                table_name=validated_table,
                conn=conn
            )

            # Get encryption key for field
            cursor.execute("""
                SELECT key_id FROM encrypted_fields_metadata
                WHERE table_name = ? AND column_name = ?
            """, (table_name, column_name))

            row = cursor.fetchone()

            if not row:
                raise ValueError(f"No encryption key found for {table_name}.{column_name}")

            key_id = row[0]

            # Get encrypted value if not provided
            if encrypted_value is None and record_id is not None:
                # SECURITY: Using validated identifiers in query
                query = f"""
                    SELECT [{validated_column}] FROM [{validated_table}]
                    WHERE id = ?
                """
                cursor.execute(query, (record_id,))
                row = cursor.fetchone()

                if not row:
                    raise ValueError(f"Record {record_id} not found")

                encrypted_value = row[0]

            # Decrypt
            return self.decrypt_value(encrypted_value, key_id)

        finally:
            conn.close()

    def encrypt_file(self, file_path: str, key_id: str = None,
                    delete_original: bool = False) -> Dict:
        """
        Encrypt a file

        Args:
            file_path: Path to file to encrypt
            key_id: Optional encryption key ID
            delete_original: Whether to delete original file

        Returns:
            Dict with encrypted file path
        """
        try:
            # Get or create key
            if not key_id:
                key_result = self.create_encryption_key('file')
                key_id = key_result['key_id']

            # Read file
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Encrypt
            key = self.get_encryption_key(key_id)
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(file_data)

            # Write encrypted file
            encrypted_path = file_path + '.encrypted'
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)

            # Store metadata
            metadata = {
                'original_name': os.path.basename(file_path),
                'encrypted_at': datetime.now().isoformat(),
                'key_id': key_id
            }

            metadata_path = encrypted_path + '.meta'
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)

            # Delete original if requested
            if delete_original:
                os.remove(file_path)

            return {
                'success': True,
                'encrypted_path': encrypted_path,
                'key_id': key_id,
                'metadata_path': metadata_path
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def decrypt_file(self, encrypted_file_path: str, output_path: str = None) -> Dict:
        """
        Decrypt a file

        Args:
            encrypted_file_path: Path to encrypted file
            output_path: Optional output path (defaults to original name)

        Returns:
            Dict with decrypted file path
        """
        try:
            # Read metadata
            metadata_path = encrypted_file_path + '.meta'
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            key_id = metadata['key_id']

            # Read encrypted file
            with open(encrypted_file_path, 'rb') as f:
                encrypted_data = f.read()

            # Decrypt
            key = self.get_encryption_key(key_id)
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)

            # Determine output path
            if not output_path:
                output_dir = os.path.dirname(encrypted_file_path)
                output_path = os.path.join(output_dir, metadata['original_name'])

            # Write decrypted file
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)

            return {
                'success': True,
                'decrypted_path': output_path,
                'original_name': metadata['original_name']
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def create_encrypted_backup(self, backup_path: str, key_id: str = None) -> Dict:
        """
        Create encrypted database backup

        Args:
            backup_path: Path for backup file
            key_id: Optional encryption key ID

        Returns:
            Dict with backup info
        """
        try:
            # Create backup using centralized connection for source
            backup_conn = get_connection(db_path=backup_path, row_factory=False)
            source_conn = get_connection(db_path=self.db_path, row_factory=False)

            try:
                source_conn.backup(backup_conn)
            finally:
                backup_conn.close()
                source_conn.close()

            # Encrypt backup
            encrypt_result = self.encrypt_file(
                backup_path,
                key_id,
                delete_original=True
            )

            if encrypt_result['success']:
                return {
                    'success': True,
                    'backup_path': encrypt_result['encrypted_path'],
                    'key_id': encrypt_result['key_id'],
                    'created_at': datetime.now().isoformat()
                }
            else:
                return encrypt_result

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def list_encrypted_fields(self) -> List[Dict]:
        """
        List all encrypted database fields

        Returns:
            List of encrypted field info
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT table_name, column_name, key_id, encrypted_at
                FROM encrypted_fields_metadata
                ORDER BY table_name, column_name
            """)

            return [
                {
                    'table': row[0],
                    'column': row[1],
                    'key_id': row[2],
                    'encrypted_at': row[3]
                }
                for row in cursor.fetchall()
            ]

        finally:
            conn.close()

    def get_key_rotation_status(self) -> List[Dict]:
        """
        Get status of encryption keys for rotation planning

        Returns:
            List of key info with rotation recommendations
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT key_id, algorithm, created_at, rotated_at, is_active, id
                FROM encryption_keys
                ORDER BY created_at DESC
            """)

            keys = []
            for row in cursor.fetchall():
                key_id, algorithm, created_at, rotated_at, is_active, version = row

                created_dt = datetime.fromisoformat(created_at)
                age_days = (datetime.now() - created_dt).days

                # Recommend rotation after 90 days
                needs_rotation = age_days > 90 and is_active

                keys.append({
                    'key_id': key_id,
                    'type': algorithm or 'AES-256',
                    'created_at': created_at,
                    'rotated_at': rotated_at,
                    'is_active': bool(is_active),
                    'version': version,
                    'age_days': age_days,
                    'needs_rotation': needs_rotation
                })

            return keys

        finally:
            conn.close()

# Convenience functions
def encrypt_sensitive_data(user_id: int, field_name: str, value: str) -> Dict:
    """Quick encrypt sensitive user data"""
    manager = EncryptionManager()
    return manager.encrypt_field('users', field_name, user_id, value)

def decrypt_sensitive_data(user_id: int, field_name: str) -> str:
    """Quick decrypt sensitive user data"""
    manager = EncryptionManager()
    return manager.decrypt_field('users', field_name, user_id)

if __name__ == '__main__':
    print("Data Encryption System initialized")
    manager = EncryptionManager()
    print(f"Database: {manager.db_path}")
    print(f"Master key loaded: {manager.master_key is not None}")

    # Example: Create encryption key
    result = manager.create_encryption_key('data')
    if result['success']:
        print(f"\n✓ Created encryption key: {result['key_id']}")

        # Test encryption/decryption
        test_value = "Sensitive Data 123-45-6789"
        encrypted = manager.encrypt_value(test_value, result['key_id'])
        print(f"✓ Encrypted: {encrypted[:50]}...")

        decrypted = manager.decrypt_value(encrypted, result['key_id'])
        print(f"✓ Decrypted: {decrypted}")
        print(f"✓ Match: {test_value == decrypted}")

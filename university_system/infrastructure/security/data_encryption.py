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
import sqlite3
import secrets
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from cryptography.fernet import Fernet
import base64

# Import centralized database path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH


class EncryptionManager:
    """Manages encryption keys and data encryption/decryption"""

    def __init__(self, db_path: str = None, master_key: bytes = None):
        """
        Initialize encryption manager

        Args:
            db_path: Path to database
            master_key: Master encryption key (if None, will be loaded from environment)
        """
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)

        self.db_path = db_path

        # Get or generate master key
        if master_key is None:
            master_key = self._get_or_create_master_key()

        self.master_key = master_key
        self.master_fernet = Fernet(master_key)

        # Cache for data encryption keys
        self._key_cache = {}

    def _get_or_create_master_key(self) -> bytes:
        """
        Get master key from environment or generate new one

        IMPORTANT: In production, store this securely (e.g., AWS KMS, Azure Key Vault)
        """
        master_key_path = os.path.join(
            os.path.dirname(self.db_path),
            '.encryption_master_key'
        )

        # Try to load existing key
        if os.path.exists(master_key_path):
            try:
                with open(master_key_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                print(f"Failed to load master key: {e}")

        # Generate new master key
        print("⚠️  Generating new master key...")
        print("⚠️  In production, store this in a secure key management system!")

        master_key = Fernet.generate_key()

        # Save master key (with restricted permissions)
        try:
            with open(master_key_path, 'wb') as f:
                f.write(master_key)
            os.chmod(master_key_path, 0o600)  # Read/write for owner only
            print(f"✓ Master key saved to: {master_key_path}")
        except Exception as e:
            print(f"Failed to save master key: {e}")

        return master_key

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

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
                WHERE encryption_key_id = ?
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
            # Get or create encryption key
            if not key_id:
                # Check if field already has a key
                cursor.execute("""
                    SELECT encryption_key_id FROM encrypted_fields_metadata
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
                            table_name, column_name, encryption_key_id
                        )
                        VALUES (?, ?, ?)
                    """, (table_name, column_name, key_id))

            # Encrypt value
            encrypted_value = self.encrypt_value(value, key_id)

            # Update database
            query = f"""
                UPDATE {table_name}
                SET {column_name} = ?
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
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get encryption key for field
            cursor.execute("""
                SELECT encryption_key_id FROM encrypted_fields_metadata
                WHERE table_name = ? AND column_name = ?
            """, (table_name, column_name))

            row = cursor.fetchone()

            if not row:
                raise ValueError(f"No encryption key found for {table_name}.{column_name}")

            key_id = row[0]

            # Get encrypted value if not provided
            if encrypted_value is None and record_id is not None:
                query = f"""
                    SELECT {column_name} FROM {table_name}
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
            # Create backup
            backup_conn = sqlite3.connect(backup_path)
            source_conn = sqlite3.connect(self.db_path)

            source_conn.backup(backup_conn)

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
                SELECT table_name, column_name, encryption_key_id, encrypted_at
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
                SELECT key_id, key_type, created_at, rotated_at, is_active, version
                FROM encryption_keys
                ORDER BY created_at DESC
            """)

            keys = []
            for row in cursor.fetchall():
                key_id, key_type, created_at, rotated_at, is_active, version = row

                created_dt = datetime.fromisoformat(created_at)
                age_days = (datetime.now() - created_dt).days

                # Recommend rotation after 90 days
                needs_rotation = age_days > 90 and is_active

                keys.append({
                    'key_id': key_id,
                    'type': key_type,
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

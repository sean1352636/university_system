# Data Encryption & Key Management Guide

This guide covers data encryption, key management, KMS integration, and secure data handling within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Encryption Architecture](#encryption-architecture)
- [Master Key Management](#master-key-management)
- [KMS Integration](#kms-integration)
- [Data Encryption Keys](#data-encryption-keys)
- [Encrypting Data](#encrypting-data)
- [File Encryption](#file-encryption)
- [Database Field Encryption](#database-field-encryption)
- [Key Rotation](#key-rotation)
- [Encrypted Backups](#encrypted-backups)
- [Security Dashboard](#security-dashboard)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The Data Encryption module provides comprehensive encryption capabilities using industry-standard Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256). It supports a two-tier key management system with optional cloud KMS integration, per-field database encryption, file encryption, and automated key rotation tracking.

**Key files:**
- Encryption Manager: `infrastructure/security/data_encryption.py`
- KMS Integration: `infrastructure/security/kms_integration.py`
- Security Dashboard GUI: `infrastructure/security/security_dashboard_gui.py`
- Security Dashboard CLI: `infrastructure/security/security_dashboard_cli.py`
- Audit Helpers: `infrastructure/security/audit_helpers.py`

## Encryption Architecture

### Two-Tier Key Hierarchy

The system uses a two-tier key hierarchy for secure key management:

```
┌─────────────────────────────────────┐
│         Master Key (Tier 1)         │
│  (KMS or file-based storage)        │
├─────────────────────────────────────┤
│     Encrypts / Decrypts             │
│         ▼           ▼               │
│  ┌──────────┐ ┌──────────┐         │
│  │ Data Key │ │ Data Key │  ...     │
│  │    #1    │ │    #2    │         │
│  └──────────┘ └──────────┘         │
│     Encrypts / Decrypts             │
│         ▼           ▼               │
│  ┌──────────┐ ┌──────────┐         │
│  │User Data │ │ Files    │  ...     │
│  └──────────┘ └──────────┘         │
└─────────────────────────────────────┘
```

1. **Master Key** - Stored securely in KMS or local file; encrypts data keys
2. **Data Keys** - Generated per purpose; encrypted by master key before database storage

### Algorithm Details

| Component | Algorithm |
|-----------|-----------|
| Symmetric Encryption | Fernet (AES-128-CBC + HMAC-SHA256) |
| Key Format | Base64-encoded bytes |
| Master Key Storage | KMS (production) or file (development) |
| Data Key Storage | Encrypted in `encryption_keys` table |
| Integrity | HMAC-SHA256 authentication tag |

## Master Key Management

### File-Based Storage (Development)

For development and non-production environments, the master key is stored locally:

```
Location: ~/.encryption_master_key
Permissions: 0o600 (owner read/write only)
```

The system automatically generates a master key on first use if one does not exist.

### KMS-Based Storage (Production)

For production, enable KMS by setting the environment variable:

```bash
export USE_KMS=true
export KMS_PROVIDER=aws    # aws, azure, or vault
```

The master key is managed entirely by the cloud KMS provider and never stored locally.

## KMS Integration

The system supports three cloud KMS providers:

### AWS KMS

```bash
export KMS_PROVIDER=aws
export AWS_REGION=us-east-1
export AWS_KMS_KEY_ID=your-kms-key-id
```

Uses `boto3` for AWS KMS API calls. The `AWSKMSProvider` class handles encrypt/decrypt operations through the AWS KMS service.

### Azure Key Vault

```bash
export KMS_PROVIDER=azure
export AZURE_VAULT_URL=https://your-vault.vault.azure.net/
export AZURE_KEY_NAME=your-key-name
```

Uses `azure-keyvault-keys` and `azure-identity` for secure key operations.

### HashiCorp Vault

```bash
export KMS_PROVIDER=vault
export VAULT_ADDR=https://vault.example.com
export VAULT_TOKEN=your-vault-token
export VAULT_KEY_PATH=/secret/university/master
```

Connects to HashiCorp Vault's transit secrets engine for key management.

### Checking KMS Status

```python
from university_system.infrastructure.security.data_encryption import EncryptionManager

manager = EncryptionManager()
# KMS is automatically detected from USE_KMS environment variable
```

All providers support lazy initialization and graceful fallback to file-based storage if the KMS service is unavailable.

## Data Encryption Keys

### Creating Keys

```python
from university_system.infrastructure.security.data_encryption import EncryptionManager

manager = EncryptionManager()

# Create a new data encryption key
result = manager.create_encryption_key(key_type='data')
key_id = result['key_id']
print(f"Created key: {key_id}")
```

### Key Storage Schema

Keys are stored encrypted in the `encryption_keys` database table:

| Column | Type | Description |
|--------|------|-------------|
| key_id | TEXT | Unique key identifier |
| key_type | TEXT | Key purpose (e.g., 'data') |
| encrypted_key | BLOB | Key encrypted with master key |
| created_at | TIMESTAMP | Creation date |
| rotated_at | TIMESTAMP | Last rotation date |
| version | INTEGER | Key version number |
| is_active | BOOLEAN | Whether the key is in use |

### Key Caching

The `EncryptionManager` maintains an in-memory LRU cache (`_key_cache`) for frequently accessed keys, avoiding repeated decryption of data keys from the database.

## Encrypting Data

### String Encryption

```python
manager = EncryptionManager()

# Create a key (or use an existing one)
result = manager.create_encryption_key('data')
key_id = result['key_id']

# Encrypt a value
encrypted = manager.encrypt_value("SSN-123-45-6789", key_id)
print(f"Encrypted: {encrypted}")

# Decrypt a value
decrypted = manager.decrypt_value(encrypted, key_id)
print(f"Decrypted: {decrypted}")
```

### Retrieving Keys

```python
# Get a specific key by ID
key = manager.get_encryption_key(key_id)
```

## File Encryption

### Encrypting a File

```python
result = manager.encrypt_file(
    file_path='/path/to/sensitive_document.pdf',
    key_id=key_id,
    delete_original=True  # Optionally remove the original file
)
print(f"Encrypted file: {result['encrypted_path']}")
```

The encrypted file is saved alongside a `.meta` metadata file (JSON) containing:
- `original_name` - Original filename
- `encrypted_at` - Encryption timestamp
- `key_id` - The data key used

### Decrypting a File

```python
result = manager.decrypt_file(
    encrypted_file_path='/path/to/sensitive_document.pdf.enc',
    output_path='/path/to/restored_document.pdf'
)
```

## Database Field Encryption

### Encrypting a Database Column Value

```python
# Encrypt a specific field for a record
manager.encrypt_field(
    table_name='users',
    column_name='ssn',
    record_id=123,
    value='123-45-6789',
    key_id=key_id
)
```

### Decrypting a Database Column Value

```python
# Decrypt a field
decrypted_value = manager.decrypt_field(
    table_name='users',
    column_name='ssn',
    record_id=123
)
```

### Listing Encrypted Fields

```python
# List all encrypted fields in the database
fields = manager.list_encrypted_fields()
for field in fields:
    print(f"{field['table_name']}.{field['column_name']} - Key: {field['key_id']}")
```

### Encrypted Fields Metadata Table

| Column | Type | Description |
|--------|------|-------------|
| table_name | TEXT | Database table |
| column_name | TEXT | Column name |
| key_id | TEXT | Encryption key used |
| encrypted_at | TIMESTAMP | When the field was encrypted |

### SQL Injection Prevention

The encryption manager validates table and column names using `validate_table_name()` and `validate_column_name()` to prevent SQL injection when constructing dynamic queries.

## Key Rotation

### Checking Rotation Status

Keys older than 90 days are flagged for rotation:

```python
status = manager.get_key_rotation_status()
for key_info in status:
    if key_info['needs_rotation']:
        print(f"Key {key_info['key_id']} needs rotation (age: {key_info['age_days']} days)")
```

### Performing Key Rotation

```python
# Rotate a key - creates a new version and tracks re-encryption needs
result = manager.rotate_key(old_key_id='old-key-123')
new_key_id = result['new_key_id']
print(f"Rotated to new key: {new_key_id}")
```

Key rotation:
1. Creates a new data key
2. Marks the old key as inactive
3. Increments the version number
4. Tracks which fields need re-encryption with the new key

### Rotation Best Practices

- Rotate keys every 90 days (system recommendation)
- Monitor rotation status via the Security Dashboard
- Re-encrypt affected data after rotation
- Keep old keys available for decryption during transition

## Encrypted Backups

### Creating an Encrypted Database Backup

```python
result = manager.create_encrypted_backup(
    backup_path='/backups/student_records_backup.db',
    key_id=key_id
)
print(f"Encrypted backup created: {result['path']}")
```

This creates a full encrypted copy of the database, suitable for secure off-site storage.

## Security Dashboard

### CLI Dashboard

The Security Dashboard CLI (`infrastructure/security/security_dashboard_cli.py`) provides:
- Encryption key status overview
- Key rotation reminders
- Encrypted field inventory
- Audit log viewer for encryption operations

### GUI Dashboard

The Security Dashboard GUI (`infrastructure/security/security_dashboard_gui.py`) provides a Tkinter interface for:
- Visual key management
- Encryption status monitoring
- One-click key rotation
- Encrypted backup creation

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_KMS` | `false` | Enable cloud KMS integration |
| `KMS_PROVIDER` | - | KMS provider: `aws`, `azure`, or `vault` |
| `AWS_REGION` | `us-east-1` | AWS region for KMS |
| `AWS_KMS_KEY_ID` | - | AWS KMS key identifier |
| `AZURE_VAULT_URL` | - | Azure Key Vault URL |
| `AZURE_KEY_NAME` | - | Azure Key Vault key name |
| `VAULT_ADDR` | - | HashiCorp Vault address |
| `VAULT_TOKEN` | - | HashiCorp Vault token |
| `VAULT_KEY_PATH` | `/secret/university/master` | Vault key path |

### Master Key File Location

```
~/.encryption_master_key  (permissions: 0o600)
```

### Key Rotation Threshold

Keys older than **90 days** are flagged for rotation by `get_key_rotation_status()`.

## Troubleshooting

### Master Key Not Found

If the system cannot locate a master key:
1. Check if `~/.encryption_master_key` exists and has correct permissions (`0o600`)
2. If using KMS, verify environment variables are set correctly
3. The system auto-generates a file-based key on first use

### KMS Connection Errors

If KMS is configured but unreachable:
- The system falls back to file-based master key storage
- Check network connectivity and credentials
- Verify provider-specific environment variables

### Decryption Failures

If decryption fails:
1. Verify the correct key ID is being used
2. Check if the key has been rotated - the old key must still be accessible
3. Ensure the master key has not changed since the data was encrypted

### Key Cache Issues

If stale keys appear in cache:
- Restart the application to clear the in-memory key cache
- The cache repopulates on next access

### Permission Errors on Master Key File

```bash
# Fix master key file permissions
chmod 600 ~/.encryption_master_key
```

### Database Lock During Encryption Operations

- Ensure only one encryption operation runs at a time
- Use context managers for all database operations
- The system uses WAL mode for better concurrent read access

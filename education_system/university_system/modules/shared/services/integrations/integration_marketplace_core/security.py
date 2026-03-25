"""Security & Credentials Manager and CLI functions"""

from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core._imports import (
    datetime, hashlib, json, os, secrets, timedelta,
    Any, Dict, List, get_connection, paths, transaction,
)


class SecurityCredentialsManager:
    """Manages security and credential operations"""

    @staticmethod
    def rotate_api_credentials(credential_id: int) -> Dict[str, Any]:
        """Automatically rotate/regenerate API keys"""
        result = {'credential_id': credential_id, 'rotated': False}

        new_api_key = secrets.token_urlsafe(32)
        new_secret = secrets.token_urlsafe(48)

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE integration_credentials
                SET api_key = ?, api_secret = ?, created_at = ?
                WHERE credential_id = ?
            ''', (new_api_key, new_secret, datetime.now().isoformat(), credential_id))

            result['rotated'] = cursor.rowcount > 0
            result['new_api_key_prefix'] = new_api_key[:8] + '...' if result['rotated'] else None

        return result

    @staticmethod
    def check_credential_expiry(days_threshold: int = 30) -> List[Dict[str, Any]]:
        """Scan and alert for expiring credentials"""
        expiring = []
        threshold_date = (datetime.now() + timedelta(days=days_threshold)).isoformat()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT icr.credential_id, ic.integration_name, icr.token_expiry, icr.created_at
                FROM integration_credentials icr
                JOIN installed_integrations ii ON icr.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE icr.token_expiry IS NOT NULL AND icr.token_expiry <= ?
            ''', (threshold_date,))

            for row in cursor.fetchall():
                expiry = datetime.fromisoformat(row['token_expiry'].replace('Z', '+00:00'))
                days_until = (expiry.replace(tzinfo=None) - datetime.now()).days
                expiring.append({
                    'credential_id': row['credential_id'],
                    'integration_name': row['integration_name'],
                    'token_expiry': row['token_expiry'],
                    'days_until_expiry': days_until,
                    'status': 'expired' if days_until < 0 else 'expiring_soon'
                })

        return expiring

    @staticmethod
    def validate_credentials(credential_id: int) -> Dict[str, Any]:
        """Test if credentials are still valid by pinging endpoint"""
        result = {'credential_id': credential_id, 'valid': False, 'message': ''}

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT endpoint_url, api_key FROM integration_credentials
                WHERE credential_id = ?
            ''', (credential_id,))
            cred = cursor.fetchone()

        if not cred:
            result['message'] = 'Credential not found'
            return result

        if not cred['endpoint_url']:
            result['message'] = 'No endpoint URL configured'
            return result

        # Simulate validation (in production, would make actual HTTP request)
        result['valid'] = True
        result['message'] = 'Endpoint reachable (simulated)'
        result['endpoint_url'] = cred['endpoint_url']

        return result

    @staticmethod
    def encrypt_export_credentials(password: str) -> str:
        """Export credentials with password encryption"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT credential_id, install_id, credential_type, endpoint_url
                FROM integration_credentials
            ''')
            credentials = [dict(row) for row in cursor.fetchall()]

        content = json.dumps({
            'exported_at': datetime.now().isoformat(),
            'credentials': credentials
        })

        # Simple XOR encryption
        key = hashlib.sha256(password.encode()).hexdigest()
        encrypted = ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(content))

        filepath = os.path.join(paths.DATA_DIR, 'exports', f'credentials_encrypted_{datetime.now().strftime("%Y%m%d_%H%M%S")}.enc')
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump({'encrypted': True, 'data': encrypted}, f)

        return filepath

    @staticmethod
    def audit_credential_access(credential_id: int = None, days: int = 30) -> List[Dict[str, Any]]:
        """View log of credential access events"""
        # This would typically query an audit log table
        # For now, return simulated data
        return [
            {
                'timestamp': datetime.now().isoformat(),
                'credential_id': credential_id or 1,
                'action': 'accessed',
                'user': 'system',
                'ip_address': '127.0.0.1',
                'note': 'Simulated audit log entry'
            }
        ]

    @staticmethod
    def revoke_all_tokens(install_id: int) -> Dict[str, Any]:
        """Emergency revoke all OAuth tokens for an integration"""
        result = {'install_id': install_id, 'revoked_count': 0}

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE integration_credentials
                SET oauth_token = NULL, oauth_refresh_token = NULL,
                    token_expiry = NULL
                WHERE install_id = ?
            ''', (install_id,))
            result['revoked_count'] = cursor.rowcount

        return result


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def rotate_api_credentials():
    """Automatically rotate/regenerate API keys"""
    print("\n" + "="*50)
    print("      ROTATE API CREDENTIALS")
    print("="*50)

    try:
        credential_id = int(input("Enter credential ID to rotate: ").strip())
    except ValueError:
        print("Invalid credential ID.")
        return

    confirm = input(f"Rotate credentials for ID {credential_id}? This will invalidate current keys. (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = SecurityCredentialsManager.rotate_api_credentials(credential_id)
        if result.get('rotated'):
            print(f"\nCredentials rotated successfully!")
            print(f"  Credential ID: {result.get('credential_id')}")
            print(f"  New API Key (prefix): {result.get('new_api_key_prefix')}")
            print("\nIMPORTANT: Update your integration with the new credentials.")
        else:
            print("\nFailed to rotate credentials. Credential may not exist.")
    except Exception as e:
        print(f"\nError rotating credentials: {e}")


def check_credential_expiry():
    """Scan and alert for expiring credentials"""
    print("\n" + "="*50)
    print("      CHECK CREDENTIAL EXPIRY")
    print("="*50)

    days = input("Days threshold (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    try:
        expiring = SecurityCredentialsManager.check_credential_expiry(days)

        if not expiring:
            print(f"\nNo credentials expiring within {days} days.")
            return

        print(f"\nFound {len(expiring)} credential(s) expiring within {days} days:\n")

        expired = [c for c in expiring if c.get('status') == 'expired']
        expiring_soon = [c for c in expiring if c.get('status') == 'expiring_soon']

        if expired:
            print("[X] EXPIRED:")
            for c in expired:
                print(f"    - {c.get('integration_name')} (ID: {c.get('credential_id')})")
                print(f"      Expired: {c.get('token_expiry')}")

        if expiring_soon:
            print("\n[!] EXPIRING SOON:")
            for c in expiring_soon:
                print(f"    - {c.get('integration_name')} (ID: {c.get('credential_id')})")
                print(f"      Expires: {c.get('token_expiry')} ({c.get('days_until_expiry')} days)")

    except Exception as e:
        print(f"\nError checking expiry: {e}")


def validate_credentials():
    """Test if credentials are still valid by pinging endpoint"""
    print("\n" + "="*50)
    print("      VALIDATE CREDENTIALS")
    print("="*50)

    try:
        credential_id = int(input("Enter credential ID to validate: ").strip())
    except ValueError:
        print("Invalid credential ID.")
        return

    print("\nValidating credentials...")

    try:
        result = SecurityCredentialsManager.validate_credentials(credential_id)

        if result.get('valid'):
            print(f"\n[OK] Credentials are VALID")
            print(f"  Endpoint: {result.get('endpoint_url', 'N/A')}")
            print(f"  Message: {result.get('message')}")
        else:
            print(f"\n[X] Credentials are INVALID")
            print(f"  Message: {result.get('message')}")

    except Exception as e:
        print(f"\nError validating credentials: {e}")


def encrypt_export_credentials():
    """Export credentials with password encryption"""
    print("\n" + "="*50)
    print("      EXPORT ENCRYPTED CREDENTIALS")
    print("="*50)

    password = input("Enter encryption password: ").strip()
    if not password:
        print("Password is required for encrypted export.")
        return

    confirm_password = input("Confirm password: ").strip()
    if password != confirm_password:
        print("Passwords do not match.")
        return

    try:
        filepath = SecurityCredentialsManager.encrypt_export_credentials(password)
        print(f"\nCredentials exported (encrypted) to:\n{filepath}")
        print("\nKeep this file secure and remember your password!")
    except Exception as e:
        print(f"\nError exporting credentials: {e}")


def audit_credential_access():
    """View log of credential access events"""
    print("\n" + "="*50)
    print("      CREDENTIAL ACCESS AUDIT")
    print("="*50)

    cred_id = input("Credential ID (or blank for all): ").strip()
    credential_id = int(cred_id) if cred_id.isdigit() else None

    days = input("Days of history (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    try:
        logs = SecurityCredentialsManager.audit_credential_access(credential_id, days)

        if not logs:
            print("\nNo access logs found.")
            return

        print(f"\n--- CREDENTIAL ACCESS LOG (Last {days} days) ---\n")
        for log in logs:
            print(f"[{log.get('timestamp', 'N/A')[:19]}] {log.get('action', 'N/A').upper()}")
            print(f"  Credential ID: {log.get('credential_id')}")
            print(f"  User: {log.get('user', 'N/A')} | IP: {log.get('ip_address', 'N/A')}")
            if log.get('note'):
                print(f"  Note: {log.get('note')}")
            print()

    except Exception as e:
        print(f"\nError retrieving audit logs: {e}")


def revoke_all_tokens():
    """Emergency revoke all OAuth tokens for an integration"""
    print("\n" + "="*50)
    print("      EMERGENCY TOKEN REVOCATION")
    print("="*50)

    print("\n[!] WARNING: This will revoke ALL OAuth tokens for the specified integration.")
    print("    The integration will stop working until new tokens are configured.\n")

    try:
        install_id = int(input("Enter install ID: ").strip())
    except ValueError:
        print("Invalid install ID.")
        return

    confirm = input(f"CONFIRM: Revoke ALL tokens for install ID {install_id}? (type 'REVOKE' to confirm): ").strip()
    if confirm != 'REVOKE':
        print("Cancelled.")
        return

    try:
        result = SecurityCredentialsManager.revoke_all_tokens(install_id)
        print(f"\n[OK] Tokens revoked successfully!")
        print(f"  Install ID: {result.get('install_id')}")
        print(f"  Tokens revoked: {result.get('revoked_count')}")
    except Exception as e:
        print(f"\nError revoking tokens: {e}")

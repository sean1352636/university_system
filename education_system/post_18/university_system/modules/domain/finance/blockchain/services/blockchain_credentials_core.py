"""
Blockchain Credentials & Digital Badges Core CLI Service

Comprehensive CLI for managing blockchain credentials, digital badges,
badge issuances, verifications, and wallet management.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import secrets
import hashlib
import logging

# Core infrastructure
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

# Setup logging
logger = logging.getLogger(__name__)


def init_blockchain_database():
    """Initialize blockchain database tables"""
    try:
        from education_system.post_18.university_system.infrastructure.database.remaining_features_schema import BLOCKCHAIN_SCHEMA

        with transaction() as conn:
            conn.executescript(BLOCKCHAIN_SCHEMA)

        logger.info("Blockchain Credentials database tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False


def generate_blockchain_hash(data: str) -> str:
    """Generate a blockchain hash for credentials"""
    timestamp = str(datetime.now().timestamp())
    random_salt = secrets.token_hex(16)
    hash_input = f"{data}{timestamp}{random_salt}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


# ==================== Blockchain Credentials Management ====================

def create_blockchain_credential():
    """Create a new blockchain credential"""
    print("\n" + "="*60)
    print("CREATE BLOCKCHAIN CREDENTIAL")
    print("="*60)

    try:
        student_id = input("Enter Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            return

        print("\nCredential Types:")
        print("1. Degree")
        print("2. Certificate")
        print("3. Diploma")
        print("4. Transcript")
        cred_type_choice = input("Select credential type (1-4): ").strip()

        credential_types = {'1': 'degree', '2': 'certificate', '3': 'diploma', '4': 'transcript'}
        credential_type = credential_types.get(cred_type_choice, 'certificate')

        credential_name = input("Enter credential name: ").strip()
        if not credential_name:
            print("❌ Credential name is required")
            return

        issue_date = input("Enter issue date (YYYY-MM-DD) [today]: ").strip()
        if not issue_date:
            issue_date = datetime.now().strftime('%Y-%m-%d')

        blockchain_address = input("Enter blockchain address (optional): ").strip()
        ipfs_hash = input("Enter IPFS hash (optional): ").strip()

        # Generate blockchain hash
        hash_data = f"{student_id}{credential_type}{credential_name}{issue_date}"
        blockchain_hash = generate_blockchain_hash(hash_data)

        metadata = {
            'issuer': 'University System',
            'issued_date': issue_date,
            'credential_type': credential_type
        }

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO blockchain_credentials (
                    student_id, credential_type, credential_name, issue_date,
                    blockchain_hash, blockchain_address, ipfs_hash, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, credential_type, credential_name, issue_date,
                  blockchain_hash, blockchain_address or None, ipfs_hash or None,
                  json.dumps(metadata)))

            credential_id = cursor.lastrowid

        log_activity('create', 'blockchain_credential', credential_id=credential_id,
                    details={'student_id': student_id, 'type': credential_type})

        print("\n✅ Blockchain credential created successfully!")
        print(f"Credential ID: {credential_id}")
        print(f"Blockchain Hash: {blockchain_hash}")

    except Exception as e:
        print(f"❌ Error creating credential: {e}")
        logger.error(f"Error creating blockchain credential: {e}")


def view_blockchain_credentials():
    """View all blockchain credentials"""
    print("\n" + "="*60)
    print("BLOCKCHAIN CREDENTIALS")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT bc.credential_id, bc.student_id, s.first_name, s.last_name,
                   bc.credential_type, bc.credential_name, bc.issue_date,
                   bc.blockchain_hash, bc.is_revoked
            FROM blockchain_credentials bc
            LEFT JOIN students s ON bc.student_id = s.student_id
            ORDER BY bc.issue_date DESC
        ''')

        credentials = cursor.fetchall()
        conn.close()

        if not credentials:
            print("\n📋 No blockchain credentials found")
            return

        print(f"\nTotal Credentials: {len(credentials)}\n")
        print(f"{'ID':<6} {'Student':<25} {'Type':<12} {'Credential':<30} {'Date':<12} {'Status':<10}")
        print("-" * 110)

        for cred in credentials:
            cred_id, stud_id, first, last, ctype, cname, idate, bhash, revoked = cred
            student_name = f"{first or ''} {last or ''}".strip() or f"ID: {stud_id}"
            status = "❌ Revoked" if revoked else "✅ Active"

            print(f"{cred_id:<6} {student_name:<25} {ctype:<12} {cname[:28]:<30} {idate:<12} {status:<10}")

        log_activity('view', 'blockchain_credentials', details={'count': len(credentials)})

    except Exception as e:
        print(f"❌ Error viewing credentials: {e}")
        logger.error(f"Error viewing blockchain credentials: {e}")


def verify_blockchain_credential():
    """Verify a blockchain credential"""
    print("\n" + "="*60)
    print("VERIFY BLOCKCHAIN CREDENTIAL")
    print("="*60)

    try:
        credential_id = input("Enter Credential ID to verify: ").strip()
        if not credential_id:
            print("❌ Credential ID is required")
            return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT credential_id, student_id, credential_type, credential_name,
                   blockchain_hash, is_revoked
            FROM blockchain_credentials
            WHERE credential_id = ?
        ''', (credential_id,))

        credential = cursor.fetchone()

        if not credential:
            print(f"❌ Credential ID {credential_id} not found")
            conn.close()
            return

        cred_id, stud_id, ctype, cname, bhash, revoked = credential

        print(f"\n{'='*60}")
        print(f"Credential ID: {cred_id}")
        print(f"Student ID: {stud_id}")
        print(f"Type: {ctype}")
        print(f"Name: {cname}")
        print(f"Blockchain Hash: {bhash}")
        print(f"Status: {'❌ REVOKED' if revoked else '✅ VALID'}")
        print(f"{'='*60}")

        if not revoked:
            # Record verification
            verifier_name = input("\nEnter your name: ").strip()
            verifier_email = input("Enter your email: ").strip()

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO credential_verifications (
                        credential_id, verifier_name, verifier_email, verification_method
                    ) VALUES (?, ?, ?, ?)
                ''', (credential_id, verifier_name, verifier_email, 'cli'))

            print("\n✅ Credential verified and logged successfully!")
            log_activity('verify', 'blockchain_credential', credential_id=credential_id)
        else:
            print("\n⚠️ This credential has been revoked and is no longer valid")

        conn.close()

    except Exception as e:
        print(f"❌ Error verifying credential: {e}")
        logger.error(f"Error verifying credential: {e}")


def revoke_blockchain_credential():
    """Revoke a blockchain credential"""
    print("\n" + "="*60)
    print("REVOKE BLOCKCHAIN CREDENTIAL")
    print("="*60)

    try:
        credential_id = input("Enter Credential ID to revoke: ").strip()
        if not credential_id:
            print("❌ Credential ID is required")
            return

        reason = input("Enter revocation reason: ").strip()
        if not reason:
            print("❌ Revocation reason is required")
            return

        confirm = input(f"\n⚠️ Are you sure you want to revoke credential {credential_id}? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Revocation cancelled")
            return

        with transaction() as conn:
            # Update credential
            conn.execute('''
                UPDATE blockchain_credentials
                SET is_revoked = 1
                WHERE credential_id = ?
            ''', (credential_id,))

            # Record revocation
            conn.execute('''
                INSERT INTO revoked_credentials (credential_id, reason)
                VALUES (?, ?)
            ''', (credential_id, reason))

        log_activity('revoke', 'blockchain_credential', credential_id=credential_id,
                    details={'reason': reason})

        print(f"\n✅ Credential {credential_id} has been revoked successfully")

    except Exception as e:
        print(f"❌ Error revoking credential: {e}")
        logger.error(f"Error revoking credential: {e}")


# ==================== Digital Badges Management ====================

def create_digital_badge():
    """Create a new digital badge"""
    print("\n" + "="*60)
    print("CREATE DIGITAL BADGE")
    print("="*60)

    try:
        badge_name = input("Enter badge name: ").strip()
        if not badge_name:
            print("❌ Badge name is required")
            return

        description = input("Enter badge description: ").strip()
        criteria = input("Enter badge criteria: ").strip()
        if not criteria:
            print("❌ Badge criteria is required")
            return

        issuer_name = input("Enter issuer name [University System]: ").strip()
        if not issuer_name:
            issuer_name = "University System"

        print("\nBadge Types:")
        print("1. Skill")
        print("2. Achievement")
        print("3. Completion")
        badge_type_choice = input("Select badge type (1-3) [1]: ").strip()

        badge_types = {'1': 'skill', '2': 'achievement', '3': 'completion'}
        badge_type = badge_types.get(badge_type_choice, 'skill')

        badge_image_url = input("Enter badge image URL (optional): ").strip()

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO digital_badges (
                    badge_name, description, criteria, badge_image_url,
                    issuer_name, badge_type
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (badge_name, description, criteria, badge_image_url or None,
                  issuer_name, badge_type))

            badge_id = cursor.lastrowid

        log_activity('create', 'digital_badge', badge_id=badge_id,
                    details={'name': badge_name, 'type': badge_type})

        print("\n✅ Digital badge created successfully!")
        print(f"Badge ID: {badge_id}")

    except Exception as e:
        print(f"❌ Error creating badge: {e}")
        logger.error(f"Error creating digital badge: {e}")


def view_digital_badges():
    """View all digital badges"""
    print("\n" + "="*60)
    print("DIGITAL BADGES")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT badge_id, badge_name, badge_type, issuer_name, is_active, created_at
            FROM digital_badges
            ORDER BY created_at DESC
        ''')

        badges = cursor.fetchall()
        conn.close()

        if not badges:
            print("\n📋 No digital badges found")
            return

        print(f"\nTotal Badges: {len(badges)}\n")
        print(f"{'ID':<6} {'Badge Name':<35} {'Type':<15} {'Issuer':<25} {'Status':<10}")
        print("-" * 100)

        for badge in badges:
            badge_id, name, btype, issuer, active, created = badge
            status = "✅ Active" if active else "❌ Inactive"

            print(f"{badge_id:<6} {name[:33]:<35} {btype:<15} {issuer[:23]:<25} {status:<10}")

        log_activity('view', 'digital_badges', details={'count': len(badges)})

    except Exception as e:
        print(f"❌ Error viewing badges: {e}")
        logger.error(f"Error viewing digital badges: {e}")


def issue_badge_to_student():
    """Issue a badge to a student"""
    print("\n" + "="*60)
    print("ISSUE BADGE TO STUDENT")
    print("="*60)

    try:
        # Show available badges
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT badge_id, badge_name, badge_type
            FROM digital_badges
            WHERE is_active = 1
        ''')

        badges = cursor.fetchall()

        if not badges:
            print("\n❌ No active badges available")
            conn.close()
            return

        print("\nAvailable Badges:")
        for badge in badges:
            badge_id, name, btype = badge
            print(f"  {badge_id}. {name} ({btype})")

        badge_id = input("\nEnter Badge ID: ").strip()
        if not badge_id:
            print("❌ Badge ID is required")
            conn.close()
            return

        student_id = input("Enter Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            conn.close()
            return

        evidence_url = input("Enter evidence URL (optional): ").strip()
        expires_in_days = input("Expires in days (optional, leave blank for no expiration): ").strip()

        expires_at = None
        if expires_in_days and expires_in_days.isdigit():
            expires_at = (datetime.now() + timedelta(days=int(expires_in_days))).strftime('%Y-%m-%d')

        # Generate blockchain hash for the issuance
        hash_data = f"{badge_id}{student_id}{datetime.now().timestamp()}"
        blockchain_hash = generate_blockchain_hash(hash_data)

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO badge_issuances (
                    badge_id, student_id, blockchain_hash, evidence_url, expires_at
                ) VALUES (?, ?, ?, ?, ?)
            ''', (badge_id, student_id, blockchain_hash, evidence_url or None, expires_at))

            issuance_id = cursor.lastrowid

        conn.close()

        log_activity('issue', 'badge_issuance', issuance_id=issuance_id,
                    details={'badge_id': badge_id, 'student_id': student_id})

        print("\n✅ Badge issued successfully!")
        print(f"Issuance ID: {issuance_id}")
        print(f"Blockchain Hash: {blockchain_hash}")

    except Exception as e:
        print(f"❌ Error issuing badge: {e}")
        logger.error(f"Error issuing badge: {e}")


def view_student_badges():
    """View badges issued to a student"""
    print("\n" + "="*60)
    print("VIEW STUDENT BADGES")
    print("="*60)

    try:
        student_id = input("Enter Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT bi.issuance_id, db.badge_name, db.badge_type, bi.issued_date,
                   bi.expires_at, bi.is_revoked, bi.blockchain_hash
            FROM badge_issuances bi
            JOIN digital_badges db ON bi.badge_id = db.badge_id
            WHERE bi.student_id = ?
            ORDER BY bi.issued_date DESC
        ''', (student_id,))

        issuances = cursor.fetchall()
        conn.close()

        if not issuances:
            print(f"\n📋 No badges found for student {student_id}")
            return

        print(f"\nBadges for Student {student_id}: {len(issuances)}\n")
        print(f"{'ID':<6} {'Badge Name':<35} {'Type':<15} {'Issued':<12} {'Expires':<12} {'Status':<10}")
        print("-" * 100)

        for issuance in issuances:
            iss_id, name, btype, issued, expires, revoked, bhash = issuance
            status = "❌ Revoked" if revoked else ("✅ Valid" if not expires or expires > datetime.now().strftime('%Y-%m-%d') else "⏰ Expired")
            expires_str = expires if expires else "Never"

            print(f"{iss_id:<6} {name[:33]:<35} {btype:<15} {issued[:10]:<12} {expires_str:<12} {status:<10}")

        log_activity('view', 'student_badges', student_id=student_id)

    except Exception as e:
        print(f"❌ Error viewing student badges: {e}")
        logger.error(f"Error viewing student badges: {e}")


# ==================== Blockchain Wallets Management ====================

def create_blockchain_wallet():
    """Create a blockchain wallet for a user"""
    print("\n" + "="*60)
    print("CREATE BLOCKCHAIN WALLET")
    print("="*60)

    try:
        user_id = input("Enter User ID: ").strip()
        if not user_id:
            print("❌ User ID is required")
            return

        # Generate wallet address
        wallet_address = "0x" + secrets.token_hex(20)
        public_key = secrets.token_hex(32)

        print("\nBlockchain Types:")
        print("1. Ethereum")
        print("2. Hyperledger")
        print("3. Bitcoin")
        blockchain_type_choice = input("Select blockchain type (1-3) [1]: ").strip()

        blockchain_types = {'1': 'ethereum', '2': 'hyperledger', '3': 'bitcoin'}
        blockchain_type = blockchain_types.get(blockchain_type_choice, 'ethereum')

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO blockchain_wallets (
                    user_id, wallet_address, blockchain_type, public_key
                ) VALUES (?, ?, ?, ?)
            ''', (user_id, wallet_address, blockchain_type, public_key))

            wallet_id = cursor.lastrowid

        log_activity('create', 'blockchain_wallet', wallet_id=wallet_id,
                    details={'user_id': user_id, 'type': blockchain_type})

        print("\n✅ Blockchain wallet created successfully!")
        print(f"Wallet ID: {wallet_id}")
        print(f"Wallet Address: {wallet_address}")
        print("⚠️ Store this address securely!")

    except Exception as e:
        print(f"❌ Error creating wallet: {e}")
        logger.error(f"Error creating blockchain wallet: {e}")


def view_blockchain_wallets():
    """View all blockchain wallets"""
    print("\n" + "="*60)
    print("BLOCKCHAIN WALLETS")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT wallet_id, user_id, wallet_address, blockchain_type, created_at
            FROM blockchain_wallets
            ORDER BY created_at DESC
        ''')

        wallets = cursor.fetchall()
        conn.close()

        if not wallets:
            print("\n📋 No blockchain wallets found")
            return

        print(f"\nTotal Wallets: {len(wallets)}\n")
        print(f"{'ID':<6} {'User ID':<10} {'Wallet Address':<45} {'Type':<15} {'Created':<20}")
        print("-" * 100)

        for wallet in wallets:
            wallet_id, user_id, address, btype, created = wallet
            print(f"{wallet_id:<6} {user_id:<10} {address:<45} {btype:<15} {created:<20}")

        log_activity('view', 'blockchain_wallets', details={'count': len(wallets)})

    except Exception as e:
        print(f"❌ Error viewing wallets: {e}")
        logger.error(f"Error viewing blockchain wallets: {e}")


# ==================== Main Menu ====================

def display_blockchain_credentials_menu(auth=None):
    """Main CLI menu for blockchain credentials and digital badges"""

    # Initialize database on first run
    init_blockchain_database()

    while True:
        print("\n" + "="*60)
        print("  BLOCKCHAIN CREDENTIALS & DIGITAL BADGES")
        print("="*60)
        print("\n📜 BLOCKCHAIN CREDENTIALS")
        print("1. Create Blockchain Credential")
        print("2. View All Credentials")
        print("3. Verify Credential")
        print("4. Revoke Credential")
        print("\n🏆 DIGITAL BADGES")
        print("5. Create Digital Badge")
        print("6. View All Badges")
        print("7. Issue Badge to Student")
        print("8. View Student Badges")
        print("\n💰 BLOCKCHAIN WALLETS")
        print("9. Create Blockchain Wallet")
        print("10. View All Wallets")
        print("\n11. Statistics & Reports")
        print("12. Return to Main Menu")
        print("="*60)

        choice = input("\nEnter your choice (1-12): ").strip()

        if choice == '1':
            create_blockchain_credential()
        elif choice == '2':
            view_blockchain_credentials()
        elif choice == '3':
            verify_blockchain_credential()
        elif choice == '4':
            revoke_blockchain_credential()
        elif choice == '5':
            create_digital_badge()
        elif choice == '6':
            view_digital_badges()
        elif choice == '7':
            issue_badge_to_student()
        elif choice == '8':
            view_student_badges()
        elif choice == '9':
            create_blockchain_wallet()
        elif choice == '10':
            view_blockchain_wallets()
        elif choice == '11':
            display_blockchain_statistics()
        elif choice == '12':
            print("Returning to main menu...")
            break
        else:
            print("❌ Invalid choice. Please try again.")

        input("\nPress Enter to continue...")


def display_blockchain_statistics():
    """Display blockchain statistics"""
    print("\n" + "="*60)
    print("BLOCKCHAIN CREDENTIALS STATISTICS")
    print("="*60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Total credentials
        cursor.execute("SELECT COUNT(*) FROM blockchain_credentials")
        total_credentials = cursor.fetchone()[0]

        # Active vs revoked
        cursor.execute("SELECT COUNT(*) FROM blockchain_credentials WHERE is_revoked = 0")
        active_credentials = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM blockchain_credentials WHERE is_revoked = 1")
        revoked_credentials = cursor.fetchone()[0]

        # Total badges
        cursor.execute("SELECT COUNT(*) FROM digital_badges")
        total_badges = cursor.fetchone()[0]

        # Total issuances
        cursor.execute("SELECT COUNT(*) FROM badge_issuances")
        total_issuances = cursor.fetchone()[0]

        # Total wallets
        cursor.execute("SELECT COUNT(*) FROM blockchain_wallets")
        total_wallets = cursor.fetchone()[0]

        # Total verifications
        cursor.execute("SELECT COUNT(*) FROM credential_verifications")
        total_verifications = cursor.fetchone()[0]

        conn.close()

        print("\n📊 CREDENTIALS:")
        print(f"   Total: {total_credentials}")
        print(f"   Active: {active_credentials}")
        print(f"   Revoked: {revoked_credentials}")

        print("\n🏆 BADGES:")
        print(f"   Total Badge Types: {total_badges}")
        print(f"   Total Issuances: {total_issuances}")

        print("\n💰 WALLETS:")
        print(f"   Total: {total_wallets}")

        print("\n✅ VERIFICATIONS:")
        print(f"   Total: {total_verifications}")

    except Exception as e:
        print(f"❌ Error displaying statistics: {e}")
        logger.error(f"Error displaying blockchain statistics: {e}")


# Export main function
__all__ = ['display_blockchain_credentials_menu']

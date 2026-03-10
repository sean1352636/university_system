# Security Integration Guide

This guide shows how to use the new integrated security features in your university management system.

## Quick Start

```python
from university_system.infrastructure.security import get_security_manager

# Initialize security manager (one-time setup)
security = get_security_manager()

# Check which security features are available
status = security.get_security_status()
print(status)
# Output: {'enhanced_auth': True, 'remember_me': True, 'rate_limiter': True, ...}
```

## 1. Enhanced Authentication with Remember Me

### Basic Login with Remember Me

```python
from university_system.infrastructure.security import login_with_security

# Login with remember me enabled
result = login_with_security(
    username='john.doe',
    password='SecurePass123!',
    remember_me=True,
    device_fingerprint='device_abc123',
    ip_address='192.168.1.100',
    user_agent='Mozilla/5.0...'
)

if result['success']:
    print(f"Welcome {result['user']['username']}!")

    # Save remember me token (send to client as secure cookie)
    if 'remember_token' in result:
        remember_token = result['remember_token']
        # Store in secure HTTP-only cookie with SameSite=Strict

    # Check for security warnings
    if result.get('session_warnings'):
        print("Security warnings:", result['session_warnings'])
else:
    print("Login failed:", result.get('error'))
```

### Verify Remember Me Token (Auto-Login)

```python
from university_system.infrastructure.security import remember_me_manager

# When user returns with remember me token
user_id = remember_me_manager.verify_and_rotate_token(
    token=remember_token,
    device_fingerprint='device_abc123',
    ip_address='192.168.1.100'
)

if user_id:
    print(f"Auto-logged in user {user_id}")
else:
    print("Invalid or expired token")
```

### Logout and Revoke All Sessions

```python
security = get_security_manager()

# Logout and revoke all remember me tokens
security.revoke_all_sessions(user_id=123)
```

## 2. File Upload Validation

### Validate Document Upload

```python
from university_system.infrastructure.security import validate_upload_secure

# Validate uploaded document
result = validate_upload_secure(
    file_path='/tmp/uploaded_file.pdf',
    original_filename='report.pdf',
    validator_type='document'  # or 'image', 'avatar', 'strict'
)

if result['valid']:
    print(f"File is safe: {result['sanitized_filename']}")
    print(f"File hash: {result['file_hash']}")
    print(f"MIME type: {result['mime_type']}")

    if result['warnings']:
        print("Warnings:", result['warnings'])
else:
    print(f"File rejected: {result['error']}")
```

### Validate Image Upload

```python
from university_system.infrastructure.security import (
    FileUploadValidator,
    image_validator
)

# Use pre-configured image validator
result = image_validator.validate_file(
    file_path='/tmp/avatar.jpg',
    original_filename='profile_picture.jpg'
)

if result.valid:
    # Safe to process image
    safe_filename = result.sanitized_filename
    print(f"Image validated: {safe_filename}")
else:
    print(f"Invalid image: {result.error}")
```

### Custom File Validator

```python
from university_system.infrastructure.security import FileUploadValidator

# Create custom validator for specific requirements
custom_validator = FileUploadValidator(
    allowed_extensions={'pdf', 'docx', 'xlsx'},
    max_size_mb=25,
    scan_viruses=True,  # Requires ClamAV
    validate_images=False
)

result = custom_validator.validate_file('/tmp/upload.pdf')
```

## 3. Rate Limiting

### Check Rate Limits

```python
from university_system.infrastructure.security import check_rate_limit_secure

# Check login rate limit
username = 'john.doe'
if check_rate_limit_secure(username, limiter_type='login'):
    # Proceed with login
    pass
else:
    print("Too many attempts. Please try again later.")

# Check API rate limit
api_key = 'api_key_123'
if check_rate_limit_secure(api_key, limiter_type='api'):
    # Process API request
    pass
```

### Manual Rate Limit Control

```python
from university_system.infrastructure.security import login_limiter

# Get remaining attempts
remaining = login_limiter.get_remaining_attempts('user@example.com')
print(f"Attempts remaining: {remaining}")

# Reset rate limit (admin only)
login_limiter.reset('user@example.com')
```

## 4. Input Validation

### Validate User Input

```python
from university_system.infrastructure.security import validate_input_secure

# Validate email
result = validate_input_secure(
    value='user@example.com',
    field_type='email'
)

if result['valid']:
    safe_email = result['sanitized']
else:
    print(f"Invalid email: {result['error']}")

# Validate with custom length
result = validate_input_secure(
    value='John Doe',
    field_type='name',
    custom_max=50,
    check_xss=True,
    check_sql_injection=True
)
```

### Validate Multiple Fields

```python
from university_system.infrastructure.security import InputValidator

# Validate form data
form_data = {
    'username': 'john.doe',
    'email': 'john@example.com',
    'phone': '+1-555-0123',
    'bio': 'Software engineer...'
}

field_types = {
    'username': 'username',
    'email': 'email',
    'phone': 'phone',
    'bio': 'description'
}

result = InputValidator.validate_multiple(
    fields=form_data,
    field_types=field_types
)

if result['valid']:
    # All fields valid - use sanitized values
    clean_data = result['sanitized']
else:
    # Show field-specific errors
    for field, error in result['errors'].items():
        print(f"{field}: {error}")
```

## 5. Session Management

### Get Active Sessions

```python
security = get_security_manager()

# Get all active sessions for current user
sessions = security.get_active_sessions()

for session in sessions:
    print(f"Type: {session['type']}")
    print(f"Device: {session.get('device', 'Unknown')}")
    print(f"Created: {session.get('created_at')}")

    if session['type'] == 'remember_me':
        print(f"Last used: {session.get('last_used')}")
        print(f"Use count: {session.get('use_count')}")
```

### Revoke Specific Session

```python
from university_system.infrastructure.security import remember_me_manager

# Revoke a specific remember me token
remember_me_manager.revoke_token(token)

# Revoke all tokens for a user
count = remember_me_manager.revoke_all_user_tokens(user_id=123)
print(f"Revoked {count} tokens")
```

## 6. Security Scanning

### Run Local Security Scan

```bash
# Run comprehensive security scan
make security-scan-local

# Run detailed scan (all severity levels)
make security-scan-detailed

# Generate security reports
make security-reports
```

### Manual Security Checks

```bash
# Run individual security tools
bandit -r university_system/ -ll
safety check
pip-audit

# Run custom security script
./scripts/security_scan.sh --detailed
```

## 7. Complete Integration Example

Here's a complete example integrating all security features:

```python
from university_system.infrastructure.security import (
    get_security_manager,
    login_with_security,
    validate_upload_secure,
    validate_input_secure,
    check_rate_limit_secure
)

def secure_login_handler(username, password, remember_me, request):
    """Complete login handler with all security features"""

    # 1. Extract request info
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    device_fingerprint = generate_device_fingerprint(request)

    # 2. Check rate limit first
    if not check_rate_limit_secure(ip_address, 'login'):
        return {'error': 'Rate limit exceeded'}, 429

    # 3. Validate inputs
    username_result = validate_input_secure(username, 'username')
    if not username_result['valid']:
        return {'error': username_result['error']}, 400

    # 4. Perform login with remember me
    result = login_with_security(
        username=username_result['sanitized'],
        password=password,
        remember_me=remember_me,
        device_fingerprint=device_fingerprint,
        ip_address=ip_address,
        user_agent=user_agent
    )

    if not result['success']:
        return {'error': result.get('error')}, 401

    # 5. Handle remember me token
    response = {'user': result['user']}

    if 'remember_token' in result:
        # Set secure cookie
        response['set_cookie'] = {
            'name': 'remember_token',
            'value': result['remember_token'],
            'httponly': True,
            'secure': True,
            'samesite': 'Strict',
            'max_age': 30 * 24 * 60 * 60  # 30 days
        }

    return response, 200


def secure_file_upload_handler(file, user_id, category):
    """Complete file upload handler with validation"""

    # 1. Save to temporary location
    temp_path = save_to_temp(file)

    try:
        # 2. Validate file
        result = validate_upload_secure(
            file_path=temp_path,
            original_filename=file.filename,
            validator_type=category  # 'document', 'image', etc.
        )

        if not result['valid']:
            return {'error': result['error']}, 400

        # 3. Move to permanent location with safe filename
        safe_filename = result['sanitized_filename']
        file_hash = result['file_hash']

        permanent_path = move_to_permanent_storage(
            temp_path,
            safe_filename,
            user_id
        )

        # 4. Store metadata in database
        store_file_metadata(
            user_id=user_id,
            filename=safe_filename,
            file_hash=file_hash,
            mime_type=result['mime_type'],
            path=permanent_path
        )

        return {
            'filename': safe_filename,
            'hash': file_hash,
            'path': permanent_path,
            'warnings': result.get('warnings', [])
        }, 200

    finally:
        # Clean up temp file
        os.remove(temp_path)
```

## 8. Security Best Practices

### Password Security
```python
# Never store plaintext passwords
# Use the built-in authentication system which uses PBKDF2 with 1M iterations

from university_system.infrastructure.auth import EnhancedAuth

auth = EnhancedAuth()
auth.create_user(username='newuser', password='SecurePass123!', role='student')
```

### Session Security
```python
# Always check session timeout
# Use secure session cookies
# Implement CSRF protection
# Use HTTPS only

# The session manager automatically handles:
# - Session timeouts by role
# - Concurrent session limits
# - Suspicious login detection
```

### File Upload Security
```python
# Always validate before processing
# Use pre-configured validators
# Enable virus scanning in production
# Store files outside web root

from university_system.infrastructure.security import strict_validator

# Strict validator includes:
# - File type validation
# - Size limits
# - Virus scanning
# - Image validation
# - MIME type verification
```

### Input Validation
```python
# Validate all user input
# Sanitize before storage
# Escape before display
# Use parameterized queries

from university_system.infrastructure.security import InputValidator

# Input validator protects against:
# - XSS attacks (30+ patterns)
# - SQL injection (15+ patterns)
# - Path traversal
# - Null byte injection
```

## 9. Troubleshooting

### Remember Me Not Working
- Check that `remember_me_manager.initialize_database()` was called
- Verify device fingerprint is consistent
- Check token hasn't expired (default: 30 days)
- Review logs for theft detection warnings

### File Upload Validation Fails
- Check file extension is in allowed list
- Verify file size is within limits
- Ensure ClamAV is running if virus scanning enabled
- Check file is not corrupted

### Rate Limit Issues
- Use `login_limiter.reset(identifier)` to manually reset
- Check Redis connection if using distributed rate limiting
- Adjust limits in rate limiter configuration

### Security Scan Fails
- Install required tools: `pip install bandit safety pip-audit`
- Fix high-severity issues first
- Review false positives (use `# nosec` for exceptions)
- Update vulnerable dependencies

## 10. Migration Guide

If you're using the old authentication system, here's how to migrate:

```python
# OLD WAY
from university_system.infrastructure.auth import UserAuth

auth = UserAuth()
result = auth.login(username, password)

# NEW WAY - with remember me
from university_system.infrastructure.auth import EnhancedAuth

auth = EnhancedAuth()
result = auth.login_with_remember_me(
    username=username,
    password=password,
    remember_me=True,
    device_fingerprint='device123',
    ip_address='192.168.1.1'
)

# Or use the convenience function
from university_system.infrastructure.security import login_with_security

result = login_with_security(username, password, remember_me=True)
```

## Support

For issues or questions:
1. Check the CHANGELOG.md for version-specific information
2. Review security logs in `logs/` directory
3. Run security scan: `make security-scan-local`
4. Check security reports in `security-reports/` directory

## 11. GUI and CLI Remember Me

The remember me functionality is now integrated into both the GUI and CLI interfaces.

### GUI Remember Me

When you launch the GUI application:

1. **Login Screen**:
   - Check the "Remember Me (30 days)" checkbox before logging in
   - Your token will be saved securely and you'll be auto-logged in for 30 days

2. **Auto-Login**:
   - Next time you launch the app, you'll be automatically logged in
   - No need to enter username/password again

3. **Logout**:
   - Logging out clears your remember me token
   - All remember me sessions are revoked for security

### CLI Remember Me

When you use the CLI:

```bash
python run.py --cli
```

**First Login**:
```
Username: admin
Password: ****
Remember me? (y/n, default: n): y
✅ Remember me token saved. You'll be automatically logged in next time.
✅ Login successful! Welcome, admin!
```

**Next Time**:
```
🔓 Auto-login successful! Welcome back, admin!
```

**Logout**:
```
5. Logout
Remember me token cleared.
```

### Technical Details

**Token Storage**:
- GUI: `~/.university_system/remember_me.json`
- CLI: `~/.university_system/cli_remember_me.json`

**Token Structure**:
```json
{
    "username": "admin",
    "token": "secure_random_token_here",
    "device_fingerprint": "sha256_hash_of_device"
}
```

**Security**:
- Tokens are single-use and automatically rotated
- Device fingerprinting prevents token theft
- 30-day expiration (can be configured)
- All tokens revoked on logout

## Version

This guide is for University Management System v5.11.0 with integrated security features and remember me functionality.

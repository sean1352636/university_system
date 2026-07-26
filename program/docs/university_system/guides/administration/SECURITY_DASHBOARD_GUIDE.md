# Security Dashboard - User Guide

## Overview

The Security Dashboard provides comprehensive monitoring and management of the university system's security infrastructure. It covers session management, rate limiting, data encryption, API security, audit logging, incident response, vulnerability scanning, data loss prevention, and compliance reporting (GDPR, FERPA). Available via both CLI and GUI interfaces, it provides real-time visibility into security events and threats.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Security Overview](#security-overview)
3. [Session Management](#session-management)
4. [Rate Limiting](#rate-limiting)
5. [Data Encryption](#data-encryption)
6. [API Security](#api-security)
7. [Audit Log](#audit-log)
8. [Incident Response](#incident-response)
9. [Data Loss Prevention](#data-loss-prevention)
10. [Vulnerability Scanning](#vulnerability-scanning)
11. [Compliance & Reporting](#compliance--reporting)
12. [Real-Time Alerts](#real-time-alerts)
13. [Best Practices](#best-practices)
14. [Troubleshooting](#troubleshooting)
15. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Security Dashboard

**CLI Mode:**
1. Navigate to **Main Menu** → **Security Dashboard**
2. Select from: Security Overview, Sessions, Encryption Status, API Security, Audit Log, Incidents, DLP Exports, Vulnerability Scans

**GUI Mode:**
1. Launch the application → **Administration** → **Security Dashboard**
2. Login with administrator credentials
3. Multi-tab interface with quick access toolbar

### Required Permissions

The Security Dashboard is restricted to **Admin** and authorised **Staff** roles. Standard users cannot access security monitoring features.

---

## Security Overview

The dashboard home screen displays real-time statistics:

| Metric | Description |
|--------|-------------|
| **Active Sessions** | Number of currently active user sessions |
| **Failed Logins** | Recent failed login attempts |
| **Security Events** | Total logged security events |
| **Encrypted Fields** | Number of encrypted database fields |
| **API Keys** | Active API keys in the system |
| **Open Incidents** | Unresolved security incidents |
| **Pending Exports** | Data exports awaiting approval |
| **High Vulnerabilities** | Critical/high severity vulnerabilities |

Recent alerts with high/critical severity are displayed prominently.

---

## Session Management

### Session Timeouts (Role-Based)

| Role | Timeout | Max Concurrent Sessions |
|------|---------|------------------------|
| **Admin** | 30 minutes | 2 |
| **Staff** | 60 minutes | 3 |
| **Instructor** | 2 hours | 5 |
| **Student** | 4 hours | 3 |
| **Parent** | 4 hours | 2 |

### Session Features

- **Session creation** with IP tracking and device fingerprinting
- **Automatic expiration** based on role-specific timeouts
- **Remote termination** — administrators can end individual or bulk sessions
- **Activity logging** — IP changes and activity timestamps tracked per session
- **Session statistics** — active sessions, daily session counts, suspicious login tracking

### Suspicious Activity Detection

The system automatically flags the following:

| Detection Type | Threshold | Description |
|----------------|-----------|-------------|
| **Impossible Travel** | > 800 km/h | Login from a distant location faster than physically possible |
| **Country Change** | Any | IP address changes across countries within a session |
| **Unusual Hours** | 12am-5am, 11pm-12am | Logins during unusual hours |
| **Multiple Failed Attempts** | 3+ in 1 hour | Repeated failed login attempts |
| **IP Inconsistency** | Any | IP address changes within the same session |

---

## Rate Limiting

### Pre-configured Limiters

| Limiter | Max Attempts | Window | Block Duration |
|---------|-------------|--------|----------------|
| **Login** | 5 attempts | 5 minutes | 15 minutes |
| **API** | 100 requests | 1 minute | 1 minute |
| **Password Reset** | 3 attempts | 1 hour | 1 hour |

### How It Works

1. Each action is tracked per identifier (username, IP, API key)
2. When the maximum attempts are exceeded within the time window, the identifier is blocked
3. Blocked users must wait for the block duration to expire
4. Rate limit events are logged to the immutable audit log
5. Security alerts are triggered for brute force detection

### Storage Backends

- **In-Memory**: Default, thread-safe dictionary (single instance)
- **Redis**: Optional distributed storage for multi-instance deployments (configured via `REDIS_URL` environment variable)

---

## Data Encryption

### Encryption Features

| Feature | Description |
|---------|-------------|
| **Field Encryption** | AES-128 + HMAC (Fernet) encryption for individual database fields |
| **File Encryption** | Encrypted file storage with metadata |
| **Database Backups** | Encrypted backup creation and restoration |
| **Key Rotation** | Automatic key rotation tracking (90-day recommended interval) |

### Key Management

- Master key sourced from KMS (Key Management Service) or file-based storage
- Per-field encryption with unique keys
- Key versioning support for rotation
- Automatic re-encryption tracking after key rotation

### Viewing Encryption Status

1. Navigate to **Encryption Status** in the dashboard
2. View: encrypted fields count, last key rotation date, rotation status
3. Review which database fields are currently encrypted

---

## API Security

### API Key Management

- **Create API keys** with specific permissions and expiration (default: 365 days)
- **Validate keys** — SHA-256 hashed storage, never stored in plaintext
- **Rate limiting** per API key
- **Last-used tracking** for monitoring key activity
- **Revoke keys** when compromised or no longer needed

### Viewing API Security

1. Navigate to **API Security** in the dashboard
2. View active API keys, their permissions, and last-used dates
3. Monitor rate limiting statistics per key

---

## Audit Log

### Immutable Audit Log

The system maintains a blockchain-style immutable audit log:

- **SHA-256 hash chaining** — each entry links to the previous via cryptographic hash
- **HMAC signatures** — tamper-evident verification
- **Append-only** — entries cannot be modified or deleted
- **Compliance support** — GDPR Article 30, FERPA, SOX, HIPAA

### Audit Log Contents

Each entry records:
- Timestamp and user ID
- Action performed and resource affected
- IP address and user agent
- Session ID
- Previous hash link and current hash

### Filtering the Audit Log

1. Navigate to **Audit Log** in the dashboard
2. Filter by:
   - **Severity**: Low, Medium, High, Critical
   - **Event Type**: Login, data access, permission change, etc.
   - **Date Range**: Custom date range
   - **User**: Specific user ID

---

## Incident Response

### Creating an Incident

1. Navigate to **Incidents** in the dashboard
2. Create a new incident with:
   - Incident type (e.g., breach, unauthorised access, data leak)
   - Severity level (low, medium, high, critical)
   - Description and affected users/resources
3. System assigns a unique incident ID

### Managing Incidents

- Log response actions with timestamps and descriptions
- Update incident status (open → resolved)
- Track affected users and resources
- Review incident timeline

---

## Data Loss Prevention

### Bulk Export Controls

The DLP system monitors and controls bulk data exports:

| Resource Type | Auto-Approve Threshold | Above Threshold |
|---------------|----------------------|-----------------|
| **Student Records** | Up to 100 records | Requires admin approval |
| **Grades** | Up to 500 records | Requires admin approval |
| **Staff Records** | Up to 50 records | Requires admin approval |
| **Default** | Up to 100 records | Requires admin approval |

### PII Detection

The system scans for sensitive data patterns:
- Social Security Numbers (SSN)
- Credit card numbers
- Email addresses
- Phone numbers

### Managing Export Requests

1. Navigate to **DLP Exports** in the dashboard
2. View pending export requests
3. Approve or deny requests based on data sensitivity
4. All decisions logged in the audit trail

---

## Vulnerability Scanning

### Scan Types

| Scan | Description |
|------|-------------|
| **SQL Injection** | Detects SQL injection patterns in code and queries |
| **XSS** | Cross-site scripting vulnerability detection |
| **General** | Broad vulnerability assessment |

### Managing Vulnerabilities

1. Navigate to **Vulnerability Scans** in the dashboard
2. View scan results with severity and target details
3. Track fix status for each vulnerability
4. Prioritise based on severity (critical, high, medium, low)

---

## Compliance & Reporting

### Available Reports

| Report | Standard | Contents |
|--------|----------|----------|
| **FERPA Compliance** | Educational records | Data access patterns, permission changes, security events |
| **GDPR Compliance** | Data protection | Processing activities, access logs, breach records |
| **Security Events** | General | Event severity breakdown, failed logins, suspicious activity |
| **Access Audit** | General | Top users, most accessed resources, access frequency |

### Generating Reports

1. Navigate to **Reports** in the dashboard
2. Select the report type
3. Set date range if applicable
4. Generate and review the report
5. Export or email to stakeholders

---

## Real-Time Alerts

### Alert Severity Levels

| Level | Description |
|-------|-------------|
| **Low** | Informational events |
| **Medium** | Noteworthy security events |
| **High** | Significant security concerns |
| **Critical** | Immediate attention required |

### Notification Channels

| Channel | Configuration | Use Case |
|---------|--------------|----------|
| **Email** | Configurable recipients and severity threshold | Standard notifications |
| **Slack** | Webhook integration, colour-coded by severity | Team notifications |
| **SMS** | Critical alerts only | Emergency notifications |

### Alert Types

- Brute force login attempts
- Suspicious logins (impossible travel, country changes)
- Unauthorised access attempts
- Potential data exfiltration
- Account lockouts
- Privilege escalation attempts
- Configuration changes

---

## Best Practices

1. **Review alerts daily** — check the security overview for new high/critical alerts
2. **Monitor failed logins** — investigate patterns of repeated failures
3. **Rotate encryption keys** — rotate every 90 days as recommended
4. **Review API keys** — revoke unused or expired API keys regularly
5. **Audit export requests** — review and approve/deny bulk export requests promptly
6. **Investigate incidents** — respond to security incidents within the defined SLA
7. **Run vulnerability scans** — schedule regular scans and track fixes
8. **Generate compliance reports** — produce FERPA/GDPR reports as required
9. **Monitor session activity** — watch for unusual session patterns
10. **Keep security policies updated** — review rate limiting and timeout configurations

---

## Troubleshooting

### Common Issues

**User locked out after failed logins:**
- The login rate limiter blocks after 5 failed attempts for 15 minutes
- Wait for the block to expire or ask an admin to review the session

**Session expired unexpectedly:**
- Sessions expire based on role-specific timeouts (30 min for admin, 4 hours for students)
- Activity keeps sessions alive; inactivity triggers expiration
- Check if another session displaced yours (concurrent session limits apply)

**Encryption key rotation warning:**
- The system flags keys older than 90 days
- Schedule key rotation through the encryption management interface
- Re-encryption of fields is tracked automatically

**API key not working:**
- Verify the key has not expired
- Check that the key has the required permissions
- Ensure rate limits have not been exceeded

**Audit log integrity warning:**
- If the hash chain is broken, it indicates potential tampering
- Investigate immediately and generate an incident report
- Contact the security team

---

## Contact Information

**University IT Security Team**
- **Phone**: (555) 123-SEC
- **Email**: security@university.edu
- **Location**: IT Building, Room 401

**Security Operations Centre**
- **Available**: 24/7
- **Emergency Email**: soc@university.edu

**Data Protection Officer**
- **Email**: dpo@university.edu
- **For**: GDPR and data privacy enquiries

---

**Last Updated**: February 2026
**Module**: `university_system/infrastructure/security/`
**Support**: security@university.edu | (555) 123-SEC

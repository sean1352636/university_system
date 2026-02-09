# Mobile App & PWA Features Guide

This guide covers mobile device management, Progressive Web App (PWA) features, offline synchronization, and mobile session management within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Device Management](#device-management)
- [Session Management](#session-management)
- [Offline Synchronization](#offline-synchronization)
- [App Installation Tracking](#app-installation-tracking)
- [Analytics & Usage Tracking](#analytics--usage-tracking)
- [User Preferences](#user-preferences)
- [GUI Interface](#gui-interface)
- [CLI Interface](#cli-interface)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The Mobile App & PWA module manages mobile devices, sessions, offline data synchronization, app installations, usage analytics, and user preferences. It supports iOS, Android, and Web/PWA platforms with secure token-based authentication and comprehensive activity logging.

**Key files:**
- GUI: `modules/domain/mobility/gui/mobile_app_pwa_gui.py`
- Core Service: `modules/domain/mobility/services/mobile_app_pwa_core.py`
- Related: `modules/domain/mobility/services/parking_management.py` (mobile parking)
- Related: `modules/domain/mobility/services/trip_management.py` (mobile trips)

## Architecture

```
┌──────────────────────────────────────────────────┐
│              Mobile App / PWA                     │
├──────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │    iOS     │  │  Android   │  │  Web/PWA   │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘ │
│        │               │               │         │
│        ▼               ▼               ▼         │
│  ┌──────────────────────────────────────────┐    │
│  │         Device Registry                   │    │
│  │    Push Tokens | OS Version | App Version │    │
│  ├──────────────────────────────────────────┤    │
│  │         Session Management                │    │
│  │    Session Tokens | IP | Activity Track   │    │
│  ├──────────────────────────────────────────┤    │
│  │         Offline Sync Queue                │    │
│  │    CREATE | UPDATE | DELETE operations     │    │
│  ├──────────────────────────────────────────┤    │
│  │         Analytics & Preferences           │    │
│  │    Event Tracking | User Settings         │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

## Device Management

### Registering a Device

Each mobile device must be registered before it can access system features:

```python
# Via CLI
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    register_mobile_device
)

register_mobile_device()
# Prompts for: device type, device name, OS version, app version
```

**Device registration creates:**
- A unique `device_id` (UUID)
- A secure `push_token` (32-character URL-safe token via `secrets.token_urlsafe`)
- Registration timestamp
- Active status flag

### Supported Platforms

| Platform | Device Type | Description |
|----------|-------------|-------------|
| iOS | `ios` | iPhone and iPad devices |
| Android | `android` | Android phones and tablets |
| Web/PWA | `web` | Progressive Web App in browser |

### Viewing Registered Devices

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    view_mobile_devices
)

view_mobile_devices()
# Displays: device_id, type, name, OS version, app version, last active, status
```

### Deactivating a Device

Devices can be deactivated without deletion, preserving audit history:

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    deactivate_mobile_device
)

deactivate_mobile_device()
# Prompts for device_id, sets is_active = False
```

### Device Database Schema

| Column | Type | Description |
|--------|------|-------------|
| device_id | TEXT (PK) | Unique device identifier |
| user_id | TEXT (FK) | Associated user account |
| device_type | TEXT | ios, android, or web |
| device_name | TEXT | User-friendly device name |
| push_token | TEXT (UNIQUE) | 32-char secure push token |
| os_version | TEXT | Operating system version |
| app_version | TEXT | Application version |
| last_active | TIMESTAMP | Last activity timestamp |
| is_active | BOOLEAN | Active/deactivated status |
| registered_at | TIMESTAMP | Registration date |

## Session Management

### Creating Sessions

Each login from a mobile device creates a new session:

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    create_mobile_session
)

create_mobile_session()
# Creates session with: session_token, IP address, OS type, app version
```

**Session details:**
- Unique `session_id` (UUID)
- Secure `session_token` (32-character URL-safe)
- Associated device and user
- IP address and OS type tracking
- Activity timestamp monitoring

### Viewing Active Sessions

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    view_mobile_sessions
)

view_mobile_sessions()
# Shows: session_id, device_id, user_id, IP, OS, app version, last activity, status
```

### Ending Sessions

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    end_mobile_session
)

end_mobile_session()
# Sets is_active = False for the specified session
```

### Session Security

- Session tokens are cryptographically secure (32-character URL-safe)
- IP address tracking for session monitoring
- Concurrent session limits enforced
- Inactive sessions can be terminated remotely
- All session operations are audit-logged

## Offline Synchronization

### How Offline Sync Works

When devices lose connectivity, operations are queued locally and synchronized when connectivity returns:

```
Device Offline:
  User action → Queue locally → Store in offline_sync_queue

Device Online:
  offline_sync_queue → Process each item → Apply to database → Mark as synced
```

### Supported Operations

| Operation | Description |
|-----------|-------------|
| `CREATE` | New records created offline |
| `UPDATE` | Existing records modified offline |
| `DELETE` | Records deleted offline |

### Queuing Offline Data

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    sync_offline_data
)

sync_offline_data()
# Queues: operation_type, entity_type, entity_id, data (JSON)
```

### Viewing the Sync Queue

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    view_sync_queue
)

view_sync_queue()
# Shows: sync_id, device_id, operation, entity, status, created_at
```

### Processing Sync Items

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    process_sync_item
)

process_sync_item()
# Applies offline changes to the database, updates status to 'synced'
```

### Sync Status Values

| Status | Description |
|--------|-------------|
| `pending` | Queued, awaiting synchronization |
| `synced` | Successfully applied to database |
| `failed` | Sync failed (will retry) |

### Sync Queue Schema

| Column | Type | Description |
|--------|------|-------------|
| sync_id | TEXT (PK) | Unique sync operation ID |
| device_id | TEXT (FK) | Source device |
| operation_type | TEXT | CREATE, UPDATE, DELETE |
| entity_type | TEXT | Type of data entity |
| entity_id | TEXT | Specific entity identifier |
| data_json | TEXT | Serialized operation data |
| sync_status | TEXT | pending, synced, failed |
| created_at | TIMESTAMP | When queued |

## App Installation Tracking

### Recording Installations

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    record_app_installation
)

record_app_installation()
# Records: device_id, app_version, installed_at, is_current
```

### Viewing Installation History

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    view_app_installations
)

view_app_installations()
```

### Installation Statistics

The GUI provides installation metrics including:
- Total installations across all platforms
- Version distribution breakdown
- Platform-specific installation counts
- Current vs. outdated version tracking

## Analytics & Usage Tracking

### Event Tracking

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    track_app_analytics
)

track_app_analytics()
# Records: device_id, event_type, event_data (JSON), timestamp
```

### Viewing Analytics

```python
from university_system.modules.domain.mobility.services.mobile_app_pwa_core import (
    view_app_analytics
)

view_app_analytics()
```

### Analytics Data

Events tracked include:
- App launches and screen views
- Feature usage patterns
- Session duration
- Error occurrences
- Performance metrics

### Exporting Analytics

The GUI supports CSV export of analytics data for external analysis tools.

## User Preferences

### Managing Preferences

User preferences are stored as key-value pairs:

```python
# Via GUI: Preferences tab allows editing preference values
# Preferences include:
#   - Notification settings
#   - Display preferences
#   - Language selection
#   - Theme choice
#   - Data sync frequency
```

### Preference Schema

| Column | Type | Description |
|--------|------|-------------|
| preference_id | TEXT (PK) | Unique preference ID |
| user_id | TEXT (FK) | Associated user |
| preference_key | TEXT | Setting name |
| preference_value | TEXT | Setting value |
| updated_at | TIMESTAMP | Last modification |

## GUI Interface

The `MobileAppPWAGUI` class provides a tabbed Tkinter interface:

### Tabs

| Tab | Purpose |
|-----|---------|
| **Devices** | Register, view, and deactivate mobile devices |
| **Sessions** | Monitor and terminate active sessions |
| **Sync Queue** | View pending sync operations, process or mark failed |
| **Installations** | Track app installations, view version statistics |
| **Analytics** | Usage metrics, event tracking, CSV export |
| **Preferences** | User preference management |

### Launching the GUI

The Mobile App GUI is accessible from the main system GUI under the Mobility section. It initializes with:
- Authentication context from `get_auth()`
- Database schema creation via `init_database()`
- TTK styling with the `clam` theme
- Internationalization support via `i18n`

### Features

- **Device Registration Dialog** - Register new devices with platform selection
- **Session Monitoring** - Real-time session list with end-session capability
- **Sync Processing** - Process pending sync items or mark as failed
- **Installation Stats** - View installation metrics and version distribution
- **Analytics Export** - Export usage data to CSV
- **Preference Editor** - Edit user preferences inline
- **Language Selector** - Multi-language UI support
- **Refresh All** - Reload data across all tabs

## CLI Interface

The CLI provides menu-driven access to all mobile app features:

```
Mobile App & PWA Management
1. Register Mobile Device
2. View Mobile Devices
3. Deactivate Mobile Device
4. Create Mobile Session
5. View Mobile Sessions
6. End Mobile Session
7. Sync Offline Data
8. View Sync Queue
9. Process Sync Item
10. Record App Installation
11. View App Installations
12. Track App Analytics
13. View App Analytics
0. Return to Main Menu
```

## Configuration

### Integration Points

The mobile module integrates with:

| System | Integration |
|--------|-------------|
| Authentication | `get_auth()` for user context |
| Email | `send_email()` for notifications |
| Activity Logging | `log_activity()` for compliance |
| Database | `get_connection()` for data access |
| i18n | `get_text()` for multi-language support |

### Database Initialization

The module creates its tables on first launch via `init_database()`. Tables are created in the main `student_records.db` database.

### Security

- Push tokens: 32-character cryptographic tokens (`secrets.token_urlsafe`)
- Session tokens: 32-character cryptographic tokens
- All operations logged to activity log
- Device deactivation (not deletion) preserves audit trail
- Email notifications for security-relevant events

## Troubleshooting

### Device Registration Fails

1. Verify the user is authenticated (`get_auth()` returns a valid user)
2. Check the database connection
3. Ensure the `mobile_devices` table exists (run `init_database()`)

### Sync Queue Not Processing

1. Check sync item status - `failed` items need manual review
2. Verify the target entity exists in the database
3. Check for data conflicts (entity modified by another user)
4. Review the `data_json` for valid JSON format

### Session Token Invalid

1. Session may have been terminated remotely
2. Check if the session's `is_active` flag is True
3. Verify the device is still active
4. Create a new session if the current one is expired

### Analytics Data Missing

1. Ensure `track_app_analytics()` is being called for user events
2. Check the device_id association
3. Verify the `app_analytics` table exists

### Push Notifications Not Received

1. Verify the device's `push_token` is valid
2. Check the device is marked as active
3. Ensure the notification service is configured
4. Test with the email fallback channel

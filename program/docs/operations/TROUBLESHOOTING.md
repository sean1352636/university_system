# Troubleshooting

> Back to [README](../README.md)

## Troubleshooting

### Common Issues

#### 1. Import Errors After Refactoring

The codebase was refactored in October 2025 and again in February 2026 (v5.42.x — 54 monolithic files split into packages). All refactored modules maintain backward compatibility via `__init__.py` re-exports. If you still see import errors:

```python
# Old import (deprecated):
from university_system.modules.interfaces.gui.grade_tracking_gui import GradeTrackingApp

# New import (current architecture):
from university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app import GradeTrackingApp
```

#### 2. Database Lock Errors

If you encounter "database is locked" errors:
- Ensure only one instance of the application is running
- Verify WAL mode is enabled (default configuration)
- Always use context managers for database operations
- Check connection pool limits in configuration
- Restart the application to clear stale connections

#### 3. Email Delivery Issues

If emails aren't being sent:
- Verify SMTP settings in `.env` or `infrastructure/email/config.py`
- Check firewall settings and port accessibility (typically port 587 or 465)
- For Gmail: Enable "App Passwords" instead of using account password
- Test SMTP connection manually using a Python script
- Check email queue status in the database

#### 4. Module Import Errors

If you see `ModuleNotFoundError`:
```bash
# Ensure you're running from the project root
cd /path/to/university_system

# Use proper module syntax (not file paths)
python -m university_system.cli_main

# Verify Python path includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### 5. Permission Errors

If you encounter file permission errors:
```bash
# Fix data directory permissions
chmod -R 755 data/ logs/ backups/

# Fix ownership (if running as different user)
chown -R yourusername:yourusername data/ logs/ backups/
```

#### 6. Tkinter Not Found

If GUI fails to start with "No module named tkinter":
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# CentOS/RHEL
sudo yum install tkinter

# macOS (usually included, but if needed)
brew install python-tk

# Windows (usually included with Python)
```

For more help, see:
- [Troubleshooting Guide](../university/TROUBLESHOOTING.md)
- [Documentation Index](../university/README.md)
- [Security Documentation](../../../SECURITY.md)

---


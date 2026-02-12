"""
System Health Checks

Monitors database, email service, disk space, and other critical subsystems.
Provides readiness and liveness probes for deployment orchestration.
"""

import os
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthChecker:
    """
    Performs health checks on system components.

    Checks:
    - Database connectivity
    - Disk space
    - Email service
    - Memory usage
    - Critical file existence
    """

    def __init__(self):
        self._checks: Dict[str, callable] = {}
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default health checks"""
        self.register_check('database', self._check_database)
        self.register_check('disk_space', self._check_disk_space)
        self.register_check('email_service', self._check_email_service)
        self.register_check('critical_files', self._check_critical_files)

    def register_check(self, name: str, check_func: callable):
        """Register a custom health check"""
        self._checks[name] = check_func

    def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity and health"""
        try:
            from university_system.infrastructure.database.db import get_connection

            start_time = datetime.now()

            with get_connection() as conn:
                # Test query
                cursor = conn.execute("SELECT 1")
                result = cursor.fetchone()

                if result and result[0] == 1:
                    elapsed = (datetime.now() - start_time).total_seconds()

                    # Check for WAL mode
                    wal_check = conn.execute("PRAGMA journal_mode").fetchone()
                    wal_enabled = wal_check and wal_check[0] == 'wal'

                    # Get database size
                    from university_system.core import paths
                    db_size = os.path.getsize(paths.DEFAULT_DB_PATH) / (1024 * 1024)  # MB

                    return {
                        'status': HealthStatus.HEALTHY.value,
                        'response_time_ms': elapsed * 1000,
                        'wal_enabled': wal_enabled,
                        'db_size_mb': round(db_size, 2),
                        'message': 'Database is accessible and responsive'
                    }

            return {
                'status': HealthStatus.UNHEALTHY.value,
                'message': 'Database test query failed'
            }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': str(e),
                'message': 'Cannot connect to database'
            }

    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space"""
        try:
            from university_system.core import paths

            # Check data directory disk space
            data_dir = os.path.dirname(paths.DEFAULT_DB_PATH)
            usage = shutil.disk_usage(data_dir)

            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            percent_used = (usage.used / usage.total) * 100

            # Determine status based on available space
            if percent_used > 90:
                status = HealthStatus.UNHEALTHY
                message = 'Critical: Less than 10% disk space remaining'
            elif percent_used > 80:
                status = HealthStatus.DEGRADED
                message = 'Warning: Less than 20% disk space remaining'
            else:
                status = HealthStatus.HEALTHY
                message = 'Sufficient disk space available'

            return {
                'status': status.value,
                'total_gb': round(total_gb, 2),
                'used_gb': round(used_gb, 2),
                'free_gb': round(free_gb, 2),
                'percent_used': round(percent_used, 2),
                'message': message
            }

        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return {
                'status': HealthStatus.UNKNOWN.value,
                'error': str(e),
                'message': 'Cannot check disk space'
            }

    def _check_email_service(self) -> Dict[str, Any]:
        """Check email service connectivity"""
        try:
            # Try to import email service
            from university_system.infrastructure.email.email_service import EmailService

            # Check if email configuration exists
            email_service = EmailService()

            if hasattr(email_service, 'is_configured') and email_service.is_configured():
                return {
                    'status': HealthStatus.HEALTHY.value,
                    'message': 'Email service is configured'
                }
            else:
                return {
                    'status': HealthStatus.DEGRADED.value,
                    'message': 'Email service not configured (optional)'
                }

        except Exception as e:
            logger.debug(f"Email service check: {e}")
            return {
                'status': HealthStatus.DEGRADED.value,
                'message': 'Email service not available (optional)'
            }

    def _check_critical_files(self) -> Dict[str, Any]:
        """Check existence of critical files"""
        try:
            from university_system.core import paths

            critical_paths = {
                'database': paths.DEFAULT_DB_PATH,
                'data_dir': paths.DATA_DIR,
                'logs_dir': paths.LOGS_DIR,
            }

            missing_files = []
            existing_files = []

            for name, path in critical_paths.items():
                if os.path.exists(path):
                    existing_files.append(name)
                else:
                    missing_files.append(name)

            if missing_files:
                return {
                    'status': HealthStatus.DEGRADED.value,
                    'existing': existing_files,
                    'missing': missing_files,
                    'message': f'Some critical paths missing: {", ".join(missing_files)}'
                }

            return {
                'status': HealthStatus.HEALTHY.value,
                'existing': existing_files,
                'message': 'All critical files exist'
            }

        except Exception as e:
            logger.error(f"Critical files check failed: {e}")
            return {
                'status': HealthStatus.UNKNOWN.value,
                'error': str(e),
                'message': 'Cannot check critical files'
            }

    def check_all(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        overall_status = HealthStatus.HEALTHY

        for name, check_func in self._checks.items():
            try:
                result = check_func()
                results[name] = result

                # Update overall status
                check_status = HealthStatus(result.get('status', HealthStatus.UNKNOWN.value))

                if check_status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif check_status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED

            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e}")
                results[name] = {
                    'status': HealthStatus.UNKNOWN.value,
                    'error': str(e),
                    'message': f'Health check failed: {e}'
                }
                overall_status = HealthStatus.DEGRADED

        return {
            'status': overall_status.value,
            'timestamp': datetime.now().isoformat(),
            'checks': results
        }

    def check_readiness(self) -> bool:
        """
        Check if system is ready to serve requests.

        Returns True if database is accessible and disk space is available.
        """
        db_check = self._check_database()
        disk_check = self._check_disk_space()

        db_healthy = db_check.get('status') == HealthStatus.HEALTHY.value
        disk_ok = disk_check.get('status') != HealthStatus.UNHEALTHY.value

        return db_healthy and disk_ok

    def check_liveness(self) -> bool:
        """
        Check if system is alive (basic health check).

        Returns True if application is running and can execute code.
        """
        return True  # If we can execute this, we're alive


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance"""
    global _health_checker

    if _health_checker is None:
        _health_checker = HealthChecker()

    return _health_checker


def check_system_health() -> Dict[str, Any]:
    """Quick function to check system health"""
    checker = get_health_checker()
    return checker.check_all()

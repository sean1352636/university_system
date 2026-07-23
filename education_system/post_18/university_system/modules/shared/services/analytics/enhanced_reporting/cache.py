"""Report caching for improved performance."""

import os
import json
import hashlib
from datetime import datetime, timedelta

from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting.config import CONFIG, logger


class CacheManager:
    """Report caching for improved performance"""

    @staticmethod
    def get_cache_key(template_name, start_date, end_date, filters=None):
        key_data = f"{template_name}_{start_date}_{end_date}_{str(filters)}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    @staticmethod
    def get_cached_report(cache_key):
        cache_file = os.path.join(CONFIG['cache_dir'], f"{cache_key}.json")

        if not os.path.exists(cache_file):
            return None

        # Check if cache is expired
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - file_time > timedelta(hours=CONFIG['cache_expiry_hours']):
            os.remove(cache_file)
            return None

        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except (OSError, IOError, json.JSONDecodeError):
            return None

    @staticmethod
    def cache_report(cache_key, report_data):
        cache_file = os.path.join(CONFIG['cache_dir'], f"{cache_key}.json")

        try:
            with open(cache_file, 'w') as f:
                json.dump(report_data, f)

            # Clean up old cache files if needed
            CacheManager.cleanup_cache()

        except Exception as e:
            logger.error(f"Failed to cache report: {str(e)}")

    @staticmethod
    def cleanup_cache():
        cache_files = []
        total_size = 0

        for file in os.listdir(CONFIG['cache_dir']):
            if file.endswith('.json'):
                file_path = os.path.join(CONFIG['cache_dir'], file)
                size = os.path.getsize(file_path)
                mtime = os.path.getmtime(file_path)
                cache_files.append((file_path, size, mtime))
                total_size += size

        # Remove old files if cache is too large
        max_size = CONFIG['max_cache_size_mb'] * 1024 * 1024
        if total_size > max_size:
            cache_files.sort(key=lambda x: x[2])  # Sort by modification time

            for file_path, size, _ in cache_files:
                if total_size <= max_size:
                    break
                os.remove(file_path)
                total_size -= size

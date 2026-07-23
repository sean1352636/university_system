"""Configuration, cache, and status methods mixin for the enhanced reporting GUI."""

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (
    tk, ttk, messagebox,
    os, json, logging,
    datetime,
    paths, get_db_connection,
    CONFIG, ENHANCED_AVAILABLE,
    _t,
    CacheManager, SystemConfig,
    load_templates,
)


class ConfigMixin:
    """Mixin providing configuration, cache management, auth, and status methods."""

    # ===== CONFIG METHODS =====

    def reload_config(self):
        """Reload system configuration"""
        try:
            if ENHANCED_AVAILABLE:
                config = SystemConfig.load_config()

                config_text = json.dumps(config, indent=4)
                self.config_display.delete(1.0, tk.END)
                self.config_display.insert(1.0, config_text)

                messagebox.showinfo("Success", "Configuration reloaded successfully!")
            else:
                messagebox.showwarning("Feature Unavailable",
                                     "Configuration management requires the enhanced system.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to reload configuration: {str(e)}")

    def save_config(self):
        """Save system configuration"""
        try:
            if ENHANCED_AVAILABLE:
                config_text = self.config_display.get(1.0, tk.END).strip()
                config = json.loads(config_text)

                SystemConfig.save_config(config)
                messagebox.showinfo("Success", "Configuration saved successfully!")
            else:
                messagebox.showwarning("Feature Unavailable",
                                     "Configuration management requires the enhanced system.")

        except json.JSONDecodeError:
            messagebox.showerror("Invalid JSON", "Configuration contains invalid JSON syntax.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    # ===== STATUS / PROGRESS METHODS =====

    def update_status(self, message, status_type="info"):
        """Update status bar message"""
        colors = {
            "info": "Info.TLabel",
            "success": "Success.TLabel",
            "warning": "Warning.TLabel",
            "error": "Error.TLabel"
        }

        self.status_text.config(text=message, style=colors.get(status_type, "Info.TLabel"))

    def start_progress(self):
        """Start progress bar animation"""
        self.progress.start(10)

    def stop_progress(self):
        """Stop progress bar animation"""
        self.progress.stop()

    # ===== OVERVIEW / SYSTEM STATUS METHODS =====

    def update_overview_cards(self):
        """Update the overview cards with current statistics"""
        try:
            # Get database statistics (works regardless of ENHANCED_AVAILABLE)
            conn = get_db_connection()
            if not conn:
                logging.error("Failed to get database connection for overview cards")
                return

            cursor = conn.cursor()

            # Student count - always query from database
            cursor.execute("SELECT COUNT(*) FROM students")
            student_count = cursor.fetchone()[0]

            # Course count - always query from database
            cursor.execute("SELECT COUNT(DISTINCT course) FROM students WHERE course IS NOT NULL")
            course_count = cursor.fetchone()[0]

            conn.close()

            # Template count (use enhanced features if available)
            if ENHANCED_AVAILABLE:
                templates = load_templates()
                template_count = len(templates)
            else:
                # Fallback: count from database
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM email_templates")
                    template_count = cursor.fetchone()[0]
                    conn.close()
                except Exception:
                    template_count = 0

            # Report count (from files)
            reports_dir = CONFIG.get('reports_dir', 'reports') if ENHANCED_AVAILABLE else 'reports'
            report_count = 0
            if os.path.exists(reports_dir):
                report_count = len([f for f in os.listdir(reports_dir)
                                  if f.endswith(('.pdf', '.xlsx', '.html'))])

            # Update cards directly (more reliable than scheduled callback)
            def update_labels():
                try:
                    if hasattr(self, 'overview_students') and self.overview_students:
                        self.overview_students.config(text=str(student_count))
                    if hasattr(self, 'overview_courses') and self.overview_courses:
                        self.overview_courses.config(text=str(course_count))
                    if hasattr(self, 'overview_templates') and self.overview_templates:
                        self.overview_templates.config(text=str(template_count))
                    if hasattr(self, 'overview_reports') and self.overview_reports:
                        self.overview_reports.config(text=str(report_count))
                    logging.debug(f"Updated overview cards: Students={student_count}, Courses={course_count}, Templates={template_count}, Reports={report_count}")
                except Exception as e:
                    logging.error(f"Error in update_labels: {e}")

            # Try to update immediately if on main thread, otherwise schedule
            try:
                update_labels()
            except Exception:
                # If direct update fails, schedule it
                self._schedule_on_ui_thread(update_labels)

        except Exception as e:
            logging.error(f"Error updating overview cards: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())

    def check_system_status(self):
        """Check and update system status"""
        try:
            status_parts = []

            # Check database connection
            if ENHANCED_AVAILABLE:
                conn = get_db_connection()
                conn.close()
                status_parts.append("Database: \u2713")

            # Check directories
            dirs_to_check = ['reports', 'templates', 'cache'] if ENHANCED_AVAILABLE else ['reports']
            for dir_name in dirs_to_check:
                if os.path.exists(dir_name):
                    status_parts.append(f"{dir_name.title()}: \u2713")
                else:
                    status_parts.append(f"{dir_name.title()}: \u2717")

            status_text = " | ".join(status_parts)

            self._schedule_on_ui_thread(lambda: [
                setattr(self.system_status, 'text', status_text),
                setattr(self.status_indicator, 'text', "\u25cf System Ready")
            ])

        except Exception as e:
            error_text = f"System Error: {str(e)}"
            self._schedule_on_ui_thread(lambda: [
                setattr(self.system_status, 'text', error_text),
                setattr(self.status_indicator, 'text', "\u25cf System Error"),
                setattr(self.status_indicator, 'style', 'Error.TLabel')
            ])

    # ===== AUTH METHOD =====

    def set_auth(self, auth_obj):
        """Set authentication context for integration"""
        try:
            self.auth = auth_obj
            if auth_obj and auth_obj.current_user:
                self.current_user = auth_obj.current_user
                logging.info(f"Enhanced reporting authenticated for: {auth_obj.current_user['username']}")
            else:
                logging.warning("No authentication context provided")
        except Exception as e:
            logging.error(f"Error setting auth context: {e}")

    # ===== CACHE MANAGEMENT METHODS =====

    def cache_report(self, cache_key, report_data):
        """Cache a report for faster retrieval"""
        try:
            if not ENHANCED_AVAILABLE:
                return False

            CacheManager.cache_report(cache_key, report_data)
            self.update_status("Report cached successfully", "success")
            return True
        except Exception as e:
            logging.error(f"Error caching report: {str(e)}")
            return False

    def get_cached_report(self, cache_key):
        """Retrieve a cached report"""
        try:
            if not ENHANCED_AVAILABLE:
                return None

            return CacheManager.get_cached_report(cache_key)
        except Exception as e:
            logging.error(f"Error getting cached report: {str(e)}")
            return None

    def get_cache_key(self, template_name, start_date, end_date, filters=None):
        """Generate cache key for report"""
        try:
            if not ENHANCED_AVAILABLE:
                return None

            return CacheManager.get_cache_key(template_name, start_date, end_date, filters)
        except Exception as e:
            logging.error(f"Error generating cache key: {str(e)}")
            return None

    def cleanup_cache_dialog(self):
        """Clean up old cache files"""
        try:
            if not ENHANCED_AVAILABLE:
                messagebox.showwarning("Not Available", "Enhanced features not available")
                return

            self.update_status("Cleaning up cache...")
            CacheManager.cleanup_cache()
            self.update_status("Cache cleaned successfully", "success")
            messagebox.showinfo("Success", "Cache cleaned successfully!")
        except Exception as e:
            logging.error(f"Error cleaning cache: {str(e)}")
            messagebox.showerror("Error", f"Failed to clean cache: {str(e)}")

    # ===== UTILITY & CONFIGURATION METHODS =====

    def configure_logging(self, level='INFO'):
        """Configure logging level"""
        try:
            logging.basicConfig(level=getattr(logging, level))
            self.update_status(f"Logging level set to {level}", "success")
        except Exception as e:
            logging.error(f"Error configuring logging: {str(e)}")

    def load_config(self):
        """Load system configuration"""
        try:
            return CONFIG
        except Exception as e:
            logging.error(f"Error loading config: {str(e)}")
            return {}

    def get_log_file(self):
        """Get log file path"""
        try:
            return CONFIG.get('log_file', str(paths.LOG_DIR / 'enhanced_reporting.log'))
        except Exception as e:
            logging.error(f"Error getting log file: {str(e)}")
            return None

    def get_reporting_db_connection(self):
        """Get database connection for reporting"""
        try:
            return get_db_connection()
        except Exception as e:
            logging.error(f"Error getting database connection: {str(e)}")
            return None

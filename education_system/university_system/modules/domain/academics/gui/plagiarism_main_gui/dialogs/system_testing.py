import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.university_system.core.i18n import get_text as _t

from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import get_authenticated_user_auth, PlagiarismCheckerError, logger


class SystemTestingDialog:
    """Comprehensive system testing dialog"""

    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker
        self.dialog = None
        self.test_results = []

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Create interface first
        self.create_search_interface()
        self.load_all_documents()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab

        self.create_interface()

    def create_interface(self):
        """Create the testing interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.system_testing_suite"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Test categories
        categories_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.test_categories"), padding=GuiConfig.PADDING_MEDIUM)
        categories_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Checkboxes for test categories
        self.test_vars = {}
        test_categories = [
            ("Database Connection", "db_connection"),
            ("Document Repository", "doc_repository"),
            ("Document Submission", "doc_submission"),
            ("Plagiarism Detection", "plagiarism_check"),
            ("Error Handling", "error_handling"),
            ("Edge Cases", "edge_cases"),
            ("Performance Tests", "performance"),
            ("Integration Tests", "integration")
        ]

        for i, (name, key) in enumerate(test_categories):
            var = tk.BooleanVar(value=True)
            self.test_vars[key] = var

            row = i // 2
            col = i % 2

            ttk.Checkbutton(categories_frame, text=name, variable=var).grid(
                row=row, column=col, sticky=tk.W, padx=GuiConfig.PADDING_SMALL, pady=GuiConfig.PADDING_SMALL
            )

        # Test controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Button(controls_frame, text=_t("plagiarism.run_selected_tests"), command=self.run_tests).pack(side=tk.LEFT)
        ttk.Button(controls_frame, text=_t("common.select_all"), command=self.select_all_tests).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(controls_frame, text=_t("common.select_none"), command=self.select_no_tests).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Progress
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))

        self.status_var = tk.StringVar()
        self.status_var.set("Ready to run tests")
        ttk.Label(progress_frame, textvariable=self.status_var).pack()

        # Results
        results_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.test_results"), padding=GuiConfig.PADDING_SMALL)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            height=15,
            font=GuiConfig.MONOSPACE_FONT,
            wrap=tk.WORD
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text=_t("plagiarism.save_results"), command=self.save_results).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_t("plagiarism.clear_results"), command=self.clear_results).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def select_all_tests(self):
        """Select all test categories"""
        for var in self.test_vars.values():
            var.set(True)

    def select_no_tests(self):
        """Deselect all test categories"""
        for var in self.test_vars.values():
            var.set(False)

    def run_tests(self):
        """Run selected tests"""
        selected_tests = [key for key, var in self.test_vars.items() if var.get()]

        if not selected_tests:
            messagebox.showwarning("No Tests Selected", "Please select at least one test category.")
            return

        # Clear previous results
        self.clear_results()
        self.test_results = []

        # Run tests in a separate thread
        def test_task():
            try:
                total_tests = len(selected_tests)

                for i, test_key in enumerate(selected_tests):
                    self.dialog.after(0, lambda p=i/total_tests*100: self.progress_var.set(p))
                    self.dialog.after(0, lambda t=test_key: self.status_var.set(f"Running {t} tests..."))

                    result = self.run_test_category(test_key)
                    self.test_results.append(result)

                    # Update results display
                    self.dialog.after(0, lambda r=result: self.add_test_result(r))

                self.dialog.after(0, lambda: self.progress_var.set(100))
                self.dialog.after(0, lambda: self.status_var.set("All tests completed"))
                self.dialog.after(0, self.show_test_summary)

            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Test Error", f"Testing failed: {err}"))

        thread = threading.Thread(target=test_task, daemon=True)
        thread.start()

    def run_test_category(self, test_key):
        """Run a specific test category"""
        try:
            if test_key == "db_connection":
                return self.test_database_connection()
            elif test_key == "doc_repository":
                return self.test_document_repository()
            elif test_key == "doc_submission":
                return self.test_document_submission()
            elif test_key == "plagiarism_check":
                return self.test_plagiarism_detection()
            elif test_key == "error_handling":
                return self.test_error_handling()
            elif test_key == "edge_cases":
                return self.test_edge_cases()
            elif test_key == "performance":
                return self.test_performance()
            elif test_key == "integration":
                return self.test_integration()
            else:
                return {"category": test_key, "status": "UNKNOWN", "message": "Test not implemented"}

        except Exception as e:
            return {"category": test_key, "status": "ERROR", "message": str(e)}

    def test_database_connection(self):
        """Test database connection and basic operations"""
        try:
            with self.checker.get_db_connection() as conn:
                cursor = conn.cursor()

                # Test basic query
                cursor.execute("SELECT COUNT(*) FROM document_repository")
                count = cursor.fetchone()[0]

                return {
                    "category": "Database Connection",
                    "status": "PASSED",
                    "message": f"Successfully connected to database. Found {count} documents in repository."
                }

        except Exception as e:
            return {
                "category": "Database Connection",
                "status": "FAILED",
                "message": f"Database connection failed: {e}"
            }

    def test_document_repository(self):
        """Test document repository operations"""
        try:
            # Test search
            results = self.checker.search_repository()

            if not isinstance(results, list):
                return {
                    "category": "Document Repository",
                    "status": "FAILED",
                    "message": "Search repository did not return a list"
                }

            # Test document details if documents exist
            if results:
                doc_id = results[0]['id']
                details = self.checker.get_document_details(doc_id)

                if not isinstance(details, dict) or not details.get('title'):
                    return {
                        "category": "Document Repository",
                        "status": "FAILED",
                        "message": "Get document details returned invalid data"
                    }

            return {
                "category": "Document Repository",
                "status": "PASSED",
                "message": f"Repository operations successful. Found {len(results)} documents."
            }

        except Exception as e:
            return {
                "category": "Document Repository",
                "status": "FAILED",
                "message": f"Repository test failed: {e}"
            }

    def test_document_submission(self):
        """Test document submission functionality"""
        try:
            # Create authenticated user for testing
            auth = get_authenticated_user_auth()
            if not auth.current_user:
                return {
                    "category": "Document Submission",
                    "status": "FAILED",
                    "message": "No test user available"
                }

            # Test content
            test_content = f"Test document content created at {datetime.now().isoformat()}"
            title = f"Test Document {datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Submit document
            doc_id = self.checker.add_document_to_repository(
                title, test_content, auth.current_user['id'], 'TEST_MODULE', 'txt'
            )

            if not doc_id:
                return {
                    "category": "Document Submission",
                    "status": "FAILED",
                    "message": "Document submission returned no ID"
                }

            # Verify document exists
            details = self.checker.get_document_details(doc_id)
            if details['title'] != title:
                return {
                    "category": "Document Submission",
                    "status": "FAILED",
                    "message": "Document verification failed - title mismatch"
                }

            return {
                "category": "Document Submission",
                "status": "PASSED",
                "message": f"Document submitted successfully with ID: {doc_id}"
            }

        except Exception as e:
            return {
                "category": "Document Submission",
                "status": "FAILED",
                "message": f"Document submission test failed: {e}"
            }

    def test_plagiarism_detection(self):
        """Test plagiarism detection functionality"""
        try:
            # Get existing documents
            documents = self.checker.search_repository()
            if not documents:
                return {
                    "category": "Plagiarism Detection",
                    "status": "SKIPPED",
                    "message": "No documents available for plagiarism testing"
                }

            doc_id = documents[0]['id']

            # Create authenticated user for testing
            auth = get_authenticated_user_auth()
            if not auth.current_user:
                return {
                    "category": "Plagiarism Detection",
                    "status": "FAILED",
                    "message": "No test user available"
                }

            # Perform plagiarism check
            result = self.checker.check_plagiarism(doc_id, auth.current_user['id'], 0.3)

            if not isinstance(result, dict) or 'status' not in result:
                return {
                    "category": "Plagiarism Detection",
                    "status": "FAILED",
                    "message": "Plagiarism check returned invalid result format"
                }

            return {
                "category": "Plagiarism Detection",
                "status": "PASSED",
                "message": f"Plagiarism check completed successfully. Status: {result['status']}"
            }

        except Exception as e:
            return {
                "category": "Plagiarism Detection",
                "status": "FAILED",
                "message": f"Plagiarism detection test failed: {e}"
            }

    def test_error_handling(self):
        """Test error handling with invalid inputs"""
        try:
            error_count = 0
            total_tests = 5

            # Test invalid document ID
            try:
                self.checker.get_document_details(-1)
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle invalid document ID"
                }
            except (ValueError, PlagiarismCheckerError):
                error_count += 1

            # Test invalid plagiarism check
            try:
                self.checker.check_plagiarism("invalid")
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle invalid plagiarism check input"
                }
            except (ValueError, TypeError, PlagiarismCheckerError):
                error_count += 1

            # Test empty document submission
            try:
                self.checker.add_document_to_repository("", "content", 1, "MOD", "txt")
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle empty title submission"
                }
            except (ValueError, PlagiarismCheckerError):
                error_count += 1

            # Test invalid result ID
            try:
                self.checker.get_plagiarism_result(-1)
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle invalid result ID"
                }
            except (ValueError, PlagiarismCheckerError):
                error_count += 1

            # Test invalid search parameters
            try:
                self.checker.search_repository("", author_id="invalid")
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle invalid search parameters"
                }
            except (ValueError, PlagiarismCheckerError):
                error_count += 1

            if error_count == total_tests:
                return {
                    "category": "Error Handling",
                    "status": "PASSED",
                    "message": f"All {total_tests} error handling tests passed"
                }
            else:
                return {
                    "category": "Error Handling",
                    "status": "PARTIAL",
                    "message": f"Passed {error_count} out of {total_tests} error handling tests"
                }

        except Exception as e:
            return {
                "category": "Error Handling",
                "status": "FAILED",
                "message": f"Error handling test failed: {e}"
            }

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        try:
            test_count = 0
            passed_count = 0

            # Test empty search
            test_count += 1
            try:
                results = self.checker.search_repository("")
                if isinstance(results, list):
                    passed_count += 1
            except Exception as e:
                logger.debug(f"Edge case test failed - empty search: {e}")

            # Test text preprocessing with edge cases
            test_count += 1
            try:
                edge_texts = ["", "   ", "123", "!@#$", "a b c"]
                for text in edge_texts:
                    tokens = self.checker.preprocess_text(text)
                    if isinstance(tokens, list):
                        passed_count += 1
                        break
            except Exception as e:
                logger.debug(f"Edge case test failed - text preprocessing: {e}")

            # Test statistics with empty database
            test_count += 1
            try:
                stats = self.checker.get_statistics()
                if isinstance(stats, dict):
                    passed_count += 1
            except Exception as e:
                logger.debug(f"Edge case test failed - statistics: {e}")

            return {
                "category": "Edge Cases",
                "status": "PASSED" if passed_count == test_count else "PARTIAL",
                "message": f"Passed {passed_count} out of {test_count} edge case tests"
            }

        except Exception as e:
            return {
                "category": "Edge Cases",
                "status": "FAILED",
                "message": f"Edge case testing failed: {e}"
            }

    def test_performance(self):
        """Test system performance"""
        try:
            import time

            # Test search performance
            start_time = time.time()
            results = self.checker.search_repository()
            search_time = time.time() - start_time

            # Test statistics performance
            start_time = time.time()
            stats = self.checker.get_statistics()
            stats_time = time.time() - start_time

            performance_ok = search_time < 5.0 and stats_time < 3.0

            return {
                "category": "Performance",
                "status": "PASSED" if performance_ok else "WARNING",
                "message": f"Search: {search_time:.2f}s, Stats: {stats_time:.2f}s"
            }

        except Exception as e:
            return {
                "category": "Performance",
                "status": "FAILED",
                "message": f"Performance test failed: {e}"
            }

    def test_integration(self):
        """Test integration between components"""
        try:
            # Test full workflow: submit -> check -> retrieve
            auth = get_authenticated_user_auth()
            if not auth.current_user:
                return {
                    "category": "Integration",
                    "status": "FAILED",
                    "message": "No test user available for integration test"
                }

            # Submit document
            test_content = f"Integration test content {datetime.now().isoformat()}"
            title = f"Integration Test {datetime.now().strftime('%Y%m%d%H%M%S')}"

            doc_id = self.checker.add_document_to_repository(
                title, test_content, auth.current_user['id'], 'TEST_MODULE', 'txt'
            )

            # Check for plagiarism
            result = self.checker.check_plagiarism(doc_id, auth.current_user['id'], 0.3)

            # Retrieve result details
            if result.get('result_id'):
                details = self.checker.get_plagiarism_result(result['result_id'])

                if not details or details['document_title'] != title:
                    return {
                        "category": "Integration",
                        "status": "FAILED",
                        "message": "Integration test failed - result details mismatch"
                    }

            return {
                "category": "Integration",
                "status": "PASSED",
                "message": "Full workflow integration test completed successfully"
            }

        except Exception as e:
            return {
                "category": "Integration",
                "status": "FAILED",
                "message": f"Integration test failed: {e}"
            }

    def add_test_result(self, result):
        """Add test result to display"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_symbol = {"PASSED": "\u2713", "FAILED": "\u2717", "WARNING": "\u26a0", "SKIPPED": "\u2298", "PARTIAL": "\u25d0"}.get(result['status'], "?")

        result_line = f"[{timestamp}] {status_symbol} {result['category']}: {result['status']} - {result['message']}\n"

        self.results_text.insert(tk.END, result_line)
        self.results_text.see(tk.END)
        self.results_text.update()

    def show_test_summary(self):
        """Show test summary"""
        if not self.test_results:
            return

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['status'] == 'PASSED')
        failed = sum(1 for r in self.test_results if r['status'] == 'FAILED')

        summary = f"\n{'='*50}\nTEST SUMMARY\n{'='*50}\n"
        summary += f"Total Tests: {total}\n"
        summary += f"Passed: {passed}\n"
        summary += f"Failed: {failed}\n"
        summary += f"Success Rate: {passed/total*100:.1f}%\n"
        summary += f"{'='*50}\n"

        self.results_text.insert(tk.END, summary)
        self.results_text.see(tk.END)

    def clear_results(self):
        """Clear test results"""
        self.results_text.delete(1.0, tk.END)
        self.test_results = []
        self.progress_var.set(0)
        self.status_var.set("Ready to run tests")

    def save_results(self):
        """Save test results to file"""
        if not self.test_results:
            messagebox.showwarning("No Results", "No test results to save.")
            return

        try:
            from tkinter import filedialog

            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Test Results"
            )

            if filename:
                content = self.results_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)

                messagebox.showinfo("Save Complete", f"Test results saved to {filename}")

        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving results: {e}")

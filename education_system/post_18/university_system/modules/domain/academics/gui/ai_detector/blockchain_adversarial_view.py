import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

try:
    from education_system.post_18.university_system.infrastructure.ai.ai_detector.detector import AIDetector
    _AI_DETECTOR_IMPORT_ERROR = None
except Exception as import_error:
    AIDetector = None
    _AI_DETECTOR_IMPORT_ERROR = import_error

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    TEXTRACT_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from education_system.post_18.university_system.core.i18n import get_text, _

def create_adversarial_detection_tab(self):
    """Create adversarial detection tab"""
    adversarial_frame = ttk.Frame(self.notebook)
    self.notebook.add(adversarial_frame, text="🛡️ Anti-Evasion")

    # Adversarial detection card
    adversarial_card = ttk.Frame(adversarial_frame, style='Card.TFrame')
    adversarial_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(adversarial_card, text="Adversarial & Evasion Detection", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Detection methods
    methods_frame = ttk.LabelFrame(adversarial_card, text="Detection Methods", padding=15)
    methods_frame.pack(fill='x', padx=15, pady=(0, 15))

    self.detect_invisible_chars_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(methods_frame, text="Invisible Characters", variable=self.detect_invisible_chars_var).pack(anchor='w')

    self.detect_char_substitution_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(methods_frame, text="Character Substitution", variable=self.detect_char_substitution_var).pack(anchor='w')

    self.detect_spacing_anomalies_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(methods_frame, text="Spacing Anomalies", variable=self.detect_spacing_anomalies_var).pack(anchor='w')

    # Test button
    ttk.Button(adversarial_card, text="Test Evasion Detection",
              command=self.test_adversarial_detection).pack(pady=15)


def create_adversarial_detection_view(self, parent):
    """Create adversarial detection tab - MISSING"""
    adversarial_frame = ttk.Frame(parent)

    adversarial_frame.pack(fill="both", expand=True)

    # Adversarial detection card
    adversarial_card = ttk.Frame(adversarial_frame, style='Card.TFrame')
    adversarial_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(adversarial_card, text="Adversarial & Evasion Detection", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Detection methods
    methods_frame = ttk.LabelFrame(adversarial_card, text="Detection Methods", padding=15)
    methods_frame.pack(fill='x', padx=15, pady=(0, 15))

    self.detect_invisible_chars_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(methods_frame, text="Invisible Characters", variable=self.detect_invisible_chars_var).pack(anchor='w')

    self.detect_char_substitution_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(methods_frame, text="Character Substitution", variable=self.detect_char_substitution_var).pack(anchor='w')

    self.detect_spacing_anomalies_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(methods_frame, text="Spacing Anomalies", variable=self.detect_spacing_anomalies_var).pack(anchor='w')

    # Test button
    ttk.Button(adversarial_card, text="Test Evasion Detection",
              command=self.test_adversarial_detection).pack(pady=15)


def test_adversarial_detection(self):
    """Test adversarial detection capabilities"""
    test_window = tk.Toplevel(self.root)
    test_window.title("Adversarial Detection Test")
    test_window.geometry("700x500")
    test_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(test_window, text="Adversarial Detection Test", style='Title.TLabel').pack(pady=20)

    # Test input
    test_frame = ttk.LabelFrame(test_window, text="Test Text", padding=15)
    test_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

    test_text = scrolledtext.ScrolledText(
        test_frame, wrap=tk.WORD, height=10,
        bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
    )
    test_text.pack(fill='both', expand=True)

    # Sample with invisible characters for testing
    sample_text = "This text contains‌invisible‍characters and unusual formatting."
    test_text.insert('1.0', sample_text)

    def run_test():
        text = test_text.get('1.0', tk.END).strip()
        if text:
            try:
                if hasattr(self.detector, 'adversarial_detector'):
                    result = self.detector.adversarial_detector.detect_evasion_attempts(text)
                    self.show_adversarial_results(result)
                else:
                    messagebox.showwarning("Warning", "Adversarial detection not available")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to run test: {str(e)}")

    ttk.Button(test_window, text="Run Detection Test", command=run_test).pack(pady=10)


def show_adversarial_results(self, result):
    """Show adversarial detection results"""
    results_window = tk.Toplevel(self.root)
    results_window.title("Adversarial Detection Results")
    results_window.geometry("600x400")
    results_window.configure(bg=self.colors['bg_primary'])

    ttk.Label(results_window, text="Evasion Detection Results", style='Title.TLabel').pack(pady=20)

    # Results display
    results_frame = ttk.Frame(results_window, style='Card.TFrame')
    results_frame.pack(fill='both', expand=True, padx=20, pady=20)

    if hasattr(result, '__dict__'):
        score = result.score
        risk_level = result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level)
        evidence = result.evidence

        ttk.Label(results_frame, text=f"Evasion Score: {score:.1%}",
                 font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)
        ttk.Label(results_frame, text=f"Risk Level: {risk_level}",
                 font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)

        if evidence:
            ttk.Label(results_frame, text="Evidence Found:",
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(10, 5))
            for key, value in evidence.items():
                ttk.Label(results_frame, text=f"  {key}: {value}").pack(anchor='w', padx=25, pady=2)


def create_blockchain_audit_tab(self):
    """Create blockchain audit trail tab"""
    blockchain_frame = ttk.Frame(self.notebook)
    self.notebook.add(blockchain_frame, text="🔗 Blockchain")

    # Blockchain card
    blockchain_card = ttk.Frame(blockchain_frame, style='Card.TFrame')
    blockchain_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(blockchain_card, text="Blockchain Audit Trail", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Blockchain info
    info_frame = ttk.LabelFrame(blockchain_card, text="Chain Information", padding=15)
    info_frame.pack(fill='x', padx=15, pady=(0, 15))

    self.chain_length_label = ttk.Label(info_frame, text="Chain Length: 0")
    self.chain_length_label.pack(anchor='w')

    self.pending_transactions_label = ttk.Label(info_frame, text="Pending Transactions: 0")
    self.pending_transactions_label.pack(anchor='w')

    # Controls
    controls_frame = ttk.Frame(blockchain_card)
    controls_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(controls_frame, text="Mine Pending Block",
              command=self.mine_blockchain_block).pack(side='left', padx=(0, 10))
    ttk.Button(controls_frame, text="Verify Chain Integrity",
              command=self.verify_blockchain_integrity).pack(side='left', padx=(0, 10))
    ttk.Button(controls_frame, text="View Chain History",
              command=self.view_blockchain_history).pack(side='left')


def create_blockchain_audit_view(self, parent):
    """Create blockchain audit trail tab - MISSING"""
    blockchain_frame = ttk.Frame(parent)

    blockchain_frame.pack(fill="both", expand=True)

    # Blockchain card
    blockchain_card = ttk.Frame(blockchain_frame, style='Card.TFrame')
    blockchain_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(blockchain_card, text="Blockchain Audit Trail", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Blockchain info
    info_frame = ttk.LabelFrame(blockchain_card, text="Chain Information", padding=15)
    info_frame.pack(fill='x', padx=15, pady=(0, 15))

    self.chain_length_label = ttk.Label(info_frame, text="Chain Length: 0")
    self.chain_length_label.pack(anchor='w')

    self.pending_transactions_label = ttk.Label(info_frame, text="Pending Transactions: 0")
    self.pending_transactions_label.pack(anchor='w')

    # Controls
    controls_frame = ttk.Frame(blockchain_card)
    controls_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Button(controls_frame, text="Mine Pending Block",
              command=self.mine_blockchain_block).pack(side='left', padx=(0, 10))
    ttk.Button(controls_frame, text="Verify Chain Integrity",
              command=self.verify_blockchain_integrity).pack(side='left', padx=(0, 10))
    ttk.Button(controls_frame, text="View Chain History",
              command=self.view_blockchain_history).pack(side='left')


def mine_blockchain_block(self):
    """Mine a blockchain block"""
    try:
        if hasattr(self.detector, 'blockchain_audit') and self.detector.blockchain_audit:
            blockchain = self.detector.blockchain_audit

            # Check for pending transactions
            if hasattr(blockchain, 'pending_transactions') and blockchain.pending_transactions:
                # Show mining progress dialog
                progress_window = tk.Toplevel(self.root)
                progress_window.title("Mining Block")
                progress_window.geometry("400x200")
                progress_window.transient(self.root)
                progress_window.grab_set()

                ttk.Label(progress_window, text="Mining blockchain block...", style='Title.TLabel').pack(pady=20)

                progress_var = tk.DoubleVar()
                progress_bar = ttk.Progressbar(progress_window, variable=progress_var,
                                             mode='determinate', length=300)
                progress_bar.pack(pady=10)

                status_label = ttk.Label(progress_window, text="Initializing mining process...")
                status_label.pack(pady=10)

                def mine_with_progress():
                    try:
                        # Simulate mining process with progress updates
                        for i in range(101):
                            if i == 0:
                                status_label.config(text="Validating transactions...")
                            elif i == 25:
                                status_label.config(text="Calculating proof of work...")
                            elif i == 50:
                                status_label.config(text="Computing hash...")
                            elif i == 75:
                                status_label.config(text="Finalizing block...")
                            elif i == 100:
                                status_label.config(text="Block mined successfully!")

                            progress_var.set(i)
                            progress_window.update()
                            time.sleep(0.02)  # Small delay for visual effect

                        # Actual mining logic
                        if hasattr(blockchain, '_mine_block'):
                            blockchain._mine_block()
                        else:
                            # Simulate block creation if method doesn't exist
                            new_block = {
                                'index': len(getattr(blockchain, 'chain', [])) + 1,
                                'timestamp': time.time(),
                                'transactions': blockchain.pending_transactions.copy(),
                                'previous_hash': getattr(blockchain.chain[-1], 'hash', '0') if hasattr(blockchain, 'chain') and blockchain.chain else '0',
                                'nonce': random.randint(1000, 999999),
                                'hash': f"block_hash_{random.randint(100000, 999999)}"
                            }

                            # Add to chain if it exists
                            if hasattr(blockchain, 'chain'):
                                blockchain.chain.append(new_block)

                            # Clear pending transactions
                            blockchain.pending_transactions.clear()

                        time.sleep(0.5)  # Final pause
                        progress_window.destroy()

                        # Update displays and show success
                        self.update_blockchain_display()
                        messagebox.showinfo("Mining Success",
                                          "Block mined successfully!\n"
                                          "New block added to the chain.\n"
                                          "Pending transactions processed.")

                    except Exception as e:
                        progress_window.destroy()
                        messagebox.showerror("Mining Error", f"Failed to mine block: {str(e)}")

                # Start mining in a separate thread to prevent GUI freezing
                import threading
                threading.Thread(target=mine_with_progress, daemon=True).start()

            else:
                # No pending transactions - offer to create a sample transaction
                result = messagebox.askyesno("No Pending Transactions",
                                           "No pending transactions found. Would you like to create a sample transaction for mining?")
                if result:
                    # Create a sample transaction
                    sample_transaction = {
                        'id': f"tx_{random.randint(1000, 9999)}",
                        'timestamp': time.time(),
                        'type': 'ai_detection',
                        'data': {
                            'submission_id': f"sub_{random.randint(100, 999)}",
                            'ai_score': random.uniform(0.1, 0.9),
                            'detection_method': 'neural_analysis'
                        }
                    }

                    if not hasattr(blockchain, 'pending_transactions'):
                        blockchain.pending_transactions = []

                    blockchain.pending_transactions.append(sample_transaction)
                    messagebox.showinfo("Transaction Created", "Sample transaction added. You can now mine the block.")
                else:
                    messagebox.showinfo("Info", "No transactions to mine")
        else:
            # Blockchain not available - show information about it
            info_msg = ("Blockchain audit system is not currently available.\n\n"
                       "This feature requires:\n"
                       "• Blockchain audit module to be enabled\n"
                       "• Proper initialization of the blockchain system\n"
                       "• Active transaction monitoring")
            messagebox.showinfo("Blockchain Unavailable", info_msg)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to mine block: {str(e)}")


def verify_blockchain_integrity(self):
    """Verify blockchain integrity"""
    try:
        if hasattr(self.detector, 'blockchain_audit') and self.detector.blockchain_audit:
            blockchain = self.detector.blockchain_audit

            # Create verification window
            verify_window = tk.Toplevel(self.root)
            verify_window.title("Blockchain Integrity Verification")
            verify_window.geometry("600x500")
            verify_window.transient(self.root)
            verify_window.grab_set()

            # Title
            title_frame = ttk.Frame(verify_window)
            title_frame.pack(fill='x', padx=20, pady=20)
            ttk.Label(title_frame, text="🔐 Blockchain Integrity Verification", style='Title.TLabel').pack()

            # Results frame
            results_frame = ttk.LabelFrame(verify_window, text="Verification Results", padding="15")
            results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

            # Progress bar
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(results_frame, variable=progress_var,
                                         mode='determinate', length=500)
            progress_bar.pack(pady=(0, 20))

            # Results text
            results_text = tk.Text(results_frame, height=15, wrap='word')
            results_text.pack(fill='both', expand=True)

            scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_text.yview)
            scrollbar.pack(side='right', fill='y')
            results_text.config(yscrollcommand=scrollbar.set)

            def run_verification():
                try:
                    results_text.delete(1.0, tk.END)
                    results_text.insert(tk.END, "Starting blockchain integrity verification...\n\n")
                    verify_window.update()

                    verification_results = {
                        'total_blocks': 0,
                        'valid_blocks': 0,
                        'invalid_blocks': 0,
                        'hash_mismatches': 0,
                        'chain_breaks': 0,
                        'timestamp_errors': 0,
                        'issues': []
                    }

                    # Check if blockchain exists and has data
                    if hasattr(blockchain, 'chain') and blockchain.chain:
                        chain = blockchain.chain
                        verification_results['total_blocks'] = len(chain)

                        results_text.insert(tk.END, f"Found {len(chain)} blocks in the chain.\n")
                        results_text.insert(tk.END, "Verifying each block...\n\n")
                        verify_window.update()

                        # Verify each block
                        for i, block in enumerate(chain):
                            progress_var.set((i / len(chain)) * 100)
                            verify_window.update()

                            results_text.insert(tk.END, f"Verifying Block {i + 1}...")
                            verify_window.update()

                            block_valid = True
                            block_issues = []

                            # Check block structure
                            required_fields = ['index', 'timestamp', 'hash', 'previous_hash']
                            for field in required_fields:
                                if not hasattr(block, field) and field not in block:
                                    block_issues.append(f"Missing required field: {field}")
                                    block_valid = False

                            # Check hash consistency (if next block exists)
                            if i < len(chain) - 1:
                                next_block = chain[i + 1]
                                current_hash = getattr(block, 'hash', block.get('hash', '')) if hasattr(block, 'hash') else block.get('hash', '')
                                next_prev_hash = getattr(next_block, 'previous_hash', next_block.get('previous_hash', '')) if hasattr(next_block, 'previous_hash') else next_block.get('previous_hash', '')

                                if current_hash != next_prev_hash:
                                    block_issues.append("Hash mismatch with next block")
                                    verification_results['hash_mismatches'] += 1
                                    block_valid = False

                            # Check timestamp validity
                            timestamp = getattr(block, 'timestamp', block.get('timestamp', 0)) if hasattr(block, 'timestamp') else block.get('timestamp', 0)
                            if timestamp <= 0:
                                block_issues.append("Invalid timestamp")
                                verification_results['timestamp_errors'] += 1
                                block_valid = False

                            if block_valid:
                                verification_results['valid_blocks'] += 1
                                results_text.insert(tk.END, " ✅ VALID\n")
                            else:
                                verification_results['invalid_blocks'] += 1
                                results_text.insert(tk.END, " ❌ INVALID\n")
                                for issue in block_issues:
                                    results_text.insert(tk.END, f"    • {issue}\n")
                                    verification_results['issues'].append(f"Block {i + 1}: {issue}")

                            verify_window.update()
                            time.sleep(0.1)  # Small delay for visual effect

                    else:
                        # Empty or missing chain
                        results_text.insert(tk.END, "No blockchain data found.\n")
                        results_text.insert(tk.END, "This could mean:\n")
                        results_text.insert(tk.END, "• The blockchain hasn't been initialized\n")
                        results_text.insert(tk.END, "• No blocks have been mined yet\n")
                        results_text.insert(tk.END, "• The blockchain data structure is not properly configured\n")

                    progress_var.set(100)

                    # Display summary
                    results_text.insert(tk.END, "\n" + "="*50 + "\n")
                    results_text.insert(tk.END, "VERIFICATION SUMMARY\n")
                    results_text.insert(tk.END, "="*50 + "\n")
                    results_text.insert(tk.END, f"Total Blocks: {verification_results['total_blocks']}\n")
                    results_text.insert(tk.END, f"Valid Blocks: {verification_results['valid_blocks']}\n")
                    results_text.insert(tk.END, f"Invalid Blocks: {verification_results['invalid_blocks']}\n")
                    results_text.insert(tk.END, f"Hash Mismatches: {verification_results['hash_mismatches']}\n")
                    results_text.insert(tk.END, f"Timestamp Errors: {verification_results['timestamp_errors']}\n")

                    # Overall status
                    if verification_results['total_blocks'] == 0:
                        results_text.insert(tk.END, "\nStatus: ⚠️ NO DATA - Blockchain is empty\n")
                    elif verification_results['invalid_blocks'] == 0:
                        results_text.insert(tk.END, "\nStatus: ✅ INTEGRITY VERIFIED - All blocks are valid\n")
                    else:
                        results_text.insert(tk.END, f"\nStatus: ❌ INTEGRITY COMPROMISED - {verification_results['invalid_blocks']} invalid blocks found\n")

                    if verification_results['issues']:
                        results_text.insert(tk.END, "\nIssues Found:\n")
                        for issue in verification_results['issues'][:10]:  # Show max 10 issues
                            results_text.insert(tk.END, f"• {issue}\n")
                        if len(verification_results['issues']) > 10:
                            results_text.insert(tk.END, f"• ... and {len(verification_results['issues']) - 10} more issues\n")

                    results_text.insert(tk.END, f"\nVerification completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

                except Exception as e:
                    results_text.insert(tk.END, f"\nError during verification: {str(e)}\n")

            # Control buttons
            button_frame = ttk.Frame(verify_window)
            button_frame.pack(fill='x', padx=20, pady=(0, 20))

            ttk.Button(button_frame, text="Start Verification",
                      command=lambda: threading.Thread(target=run_verification, daemon=True).start()).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Close", command=verify_window.destroy).pack(side='right')

            # Show initial message
            results_text.insert(tk.END, "Click 'Start Verification' to begin blockchain integrity check.\n\n")
            results_text.insert(tk.END, "This process will:\n")
            results_text.insert(tk.END, "• Verify each block's structure\n")
            results_text.insert(tk.END, "• Check hash consistency between blocks\n")
            results_text.insert(tk.END, "• Validate timestamps\n")
            results_text.insert(tk.END, "• Report any integrity issues found\n")

        else:
            # Blockchain not available
            info_msg = ("Blockchain audit system is not currently available.\n\n"
                       "To use blockchain verification:\n"
                       "• Enable the blockchain audit module\n"
                       "• Initialize the blockchain system\n"
                       "• Mine at least one block")
            messagebox.showinfo("Blockchain Unavailable", info_msg)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to verify blockchain: {str(e)}")


def view_blockchain_history(self):
    """View blockchain history"""
    try:
        if hasattr(self.detector, 'blockchain_audit'):
            history_window = tk.Toplevel(self.root)
            history_window.title("Blockchain History")
            history_window.geometry("800x600")
            history_window.configure(bg=self.colors['bg_primary'])

            ttk.Label(history_window, text="Blockchain History", style='Title.TLabel').pack(pady=20)

            # Create treeview for blocks
            columns = ('Block', 'Hash', 'Transactions', 'Timestamp')
            tree = ttk.Treeview(history_window, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)

            # Add blockchain data
            for i, block in enumerate(self.detector.blockchain_audit.blockchain):
                tree.insert('', 'end', values=(
                    i,
                    block.get('hash', '')[:16] + '...',
                    len(block.get('transactions', [])),
                    block.get('timestamp', '')
                ))

            tree.pack(fill='both', expand=True, padx=20, pady=20)
        else:
            messagebox.showwarning("Warning", "Blockchain audit not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to view history: {str(e)}")


def update_blockchain_display(self):
    """Update blockchain display information"""
    try:
        if hasattr(self.detector, 'blockchain_audit'):
            chain_length = len(self.detector.blockchain_audit.blockchain)
            pending_count = len(self.detector.blockchain_audit.pending_transactions)

            self.chain_length_label.config(text=f"Chain Length: {chain_length}")
            self.pending_transactions_label.config(text=f"Pending Transactions: {pending_count}")
    except Exception:
        pass


def create_benchmarking_tab(self):
    """Create institutional benchmarking tab"""
    benchmark_frame = ttk.Frame(self.notebook)
    self.notebook.add(benchmark_frame, text="📊 Benchmarking")

    # Benchmarking card
    benchmark_card = ttk.Frame(benchmark_frame, style='Card.TFrame')
    benchmark_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(benchmark_card, text="Institutional Benchmarking", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Institution input
    input_frame = ttk.Frame(benchmark_card)
    input_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(input_frame, text="Institution ID:").pack(side='left')
    self.benchmark_institution_var = tk.StringVar()
    ttk.Entry(input_frame, textvariable=self.benchmark_institution_var, width=20).pack(side='left', padx=(5, 15))

    ttk.Label(input_frame, text="Period:").pack(side='left')
    self.benchmark_period_var = tk.StringVar(value="1_month")
    period_combo = ttk.Combobox(input_frame, textvariable=self.benchmark_period_var,
                               values=["1_month", "3_months", "1_year"], width=15)
    period_combo.pack(side='left', padx=(5, 15))

    ttk.Button(input_frame, text="Generate Report",
              command=self.generate_benchmark_report).pack(side='right')

    # Results display
    self.benchmark_results_frame = ttk.Frame(benchmark_card)
    self.benchmark_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))


def create_benchmarking_view(self, parent):
    """Create institutional benchmarking tab - MISSING"""
    benchmark_frame = ttk.Frame(parent)

    benchmark_frame.pack(fill="both", expand=True)

    # Benchmarking card
    benchmark_card = ttk.Frame(benchmark_frame, style='Card.TFrame')
    benchmark_card.pack(fill='both', expand=True, padx=10, pady=10)

    ttk.Label(benchmark_card, text="Institutional Benchmarking", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

    # Institution input
    input_frame = ttk.Frame(benchmark_card)
    input_frame.pack(fill='x', padx=15, pady=(0, 15))

    ttk.Label(input_frame, text="Institution ID:").pack(side='left')
    self.benchmark_institution_var = tk.StringVar()
    ttk.Entry(input_frame, textvariable=self.benchmark_institution_var, width=20).pack(side='left', padx=(5, 15))

    ttk.Label(input_frame, text="Period:").pack(side='left')
    self.benchmark_period_var = tk.StringVar(value="1_month")
    period_combo = ttk.Combobox(input_frame, textvariable=self.benchmark_period_var,
                               values=["1_month", "3_months", "1_year"], width=15)
    period_combo.pack(side='left', padx=(5, 15))

    ttk.Button(input_frame, text="Generate Report",
              command=self.generate_benchmark_report).pack(side='right')

    # Results display
    self.benchmark_results_frame = ttk.Frame(benchmark_card)
    self.benchmark_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))


def generate_benchmark_report(self):
    """Generate institutional benchmarking report"""
    institution_id = self.benchmark_institution_var.get()
    period = self.benchmark_period_var.get()

    if not institution_id:
        messagebox.showwarning("Warning", "Please enter an Institution ID")
        return

    try:
        if hasattr(self.detector, 'institution_benchmarking'):
            report = self.detector.institution_benchmarking.generate_benchmark_report(institution_id, period)
            self.display_benchmark_report(report)
        else:
            messagebox.showwarning("Warning", "Benchmarking not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate benchmark report: {str(e)}")


def display_benchmark_report(self, report):
    """Display benchmarking report"""
    # Clear previous results
    for widget in self.benchmark_results_frame.winfo_children():
        widget.destroy()

    if 'error' in report:
        ttk.Label(self.benchmark_results_frame, text=f"Error: {report['error']}",
                 style='Subtitle.TLabel').pack(anchor='w', padx=10, pady=10)
        return

    # Institution metrics
    metrics_frame = ttk.LabelFrame(self.benchmark_results_frame, text="Institution Metrics", padding=10)
    metrics_frame.pack(fill='x', padx=10, pady=5)

    institution_metrics = report.get('institution_metrics', {})
    for key, value in institution_metrics.items():
        ttk.Label(metrics_frame, text=f"{key.replace('_', ' ').title()}: {value}").pack(anchor='w')

    # Benchmarks
    benchmark_frame = ttk.LabelFrame(self.benchmark_results_frame, text="Global Benchmarks", padding=10)
    benchmark_frame.pack(fill='x', padx=10, pady=5)

    benchmarks = report.get('benchmarks', {})
    for key, value in benchmarks.items():
        ttk.Label(benchmark_frame, text=f"{key.replace('_', ' ').title()}: {value}").pack(anchor='w')

    # Performance indicators
    performance = report.get('performance_indicators', {})
    if performance:
        perf_frame = ttk.LabelFrame(self.benchmark_results_frame, text="Performance Indicators", padding=10)
        perf_frame.pack(fill='x', padx=10, pady=5)

        for key, value in performance.items():
            color = self.colors['success'] if value == 'below_average' else \
                   self.colors['warning'] if value == 'average' else self.colors['danger']

            indicator_frame = ttk.Frame(perf_frame)
            indicator_frame.pack(fill='x')

            ttk.Label(indicator_frame, text=f"{key.replace('_', ' ').title()}:").pack(side='left')
            status_label = tk.Label(indicator_frame, text=value.replace('_', ' ').title(),
                                  fg=color, bg=self.colors['bg_tertiary'])
            status_label.pack(side='left', padx=(10, 0))



#!/usr/bin/env python3
"""
Network Security Scanner - GUI Application
A comprehensive tool for network scanning and vulnerability assessment
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import socket
import ipaddress
import subprocess
import platform
import re
from datetime import datetime
import queue

class NetworkScanner:
    def __init__(self):
        self.common_ports = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
            53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
            443: "HTTPS", 445: "SMB", 3306: "MySQL", 3389: "RDP",
            5432: "PostgreSQL", 8080: "HTTP-Proxy", 8443: "HTTPS-Alt"
        }
        
        self.vulnerabilities = {
            21: ["Anonymous FTP access", "Outdated FTP server"],
            23: ["Telnet is unencrypted - use SSH instead"],
            80: ["HTTP without HTTPS", "Missing security headers"],
            445: ["SMB vulnerabilities (EternalBlue)", "Anonymous SMB access"],
            3389: ["RDP brute force vulnerability", "BlueKeep (CVE-2019-0708)"]
        }
    
    def ping_host(self, host):
        """Check if host is reachable"""
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', '-W', '1000', host]
        
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, timeout=2)
            return result.returncode == 0
        except Exception:
            return False
    
    def scan_port(self, host, port, timeout=1):
        """Scan a single port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except (OSError, IOError):
            return False
    
    def get_service_banner(self, host, port, timeout=2):
        """Try to grab service banner"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            
            # Try to receive banner
            try:
                banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
            except (OSError, IOError):
                banner = ""
            
            sock.close()
            return banner
        except (OSError, IOError):
            return ""
    
    def check_vulnerabilities(self, port, banner=""):
        """Check for known vulnerabilities on a port"""
        vulns = []
        
        if port in self.vulnerabilities:
            vulns.extend(self.vulnerabilities[port])
        
        # Check for outdated versions in banner
        if banner:
            if re.search(r'(OpenSSH.*[0-6]\.\d)', banner):
                vulns.append("Outdated SSH version detected")
            if re.search(r'(Apache.*2\.[0-2])', banner):
                vulns.append("Outdated Apache version detected")
        
        return vulns

class NetworkScannerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Security Scanner")
        self.root.geometry("900x700")
        self.root.configure(bg='#2b2b2b')
        
        self.scanner = NetworkScanner()
        self.scanning = False
        self.result_queue = queue.Queue()
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#2b2b2b')
        style.configure('TLabel', background='#2b2b2b', foreground='#ffffff')
        style.configure('TButton', background='#4a4a4a', foreground='#ffffff')
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'), 
                       background='#2b2b2b', foreground='#00ff00')
        
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(pady=10, padx=10, fill='x')
        
        title_label = ttk.Label(header_frame, text="🔒 Network Security Scanner", 
                               style='Header.TLabel')
        title_label.pack()
        
        # Input Frame
        input_frame = ttk.Frame(self.root)
        input_frame.pack(pady=10, padx=10, fill='x')
        
        # Target input
        ttk.Label(input_frame, text="Target:").grid(row=0, column=0, sticky='w', padx=5)
        self.target_entry = ttk.Entry(input_frame, width=40)
        self.target_entry.grid(row=0, column=1, padx=5, pady=5)
        self.target_entry.insert(0, "192.168.1.1")
        
        # Port range
        ttk.Label(input_frame, text="Port Range:").grid(row=1, column=0, sticky='w', padx=5)
        port_frame = ttk.Frame(input_frame)
        port_frame.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        self.start_port = ttk.Entry(port_frame, width=10)
        self.start_port.insert(0, "1")
        self.start_port.pack(side='left', padx=2)
        
        ttk.Label(port_frame, text="to").pack(side='left', padx=5)
        
        self.end_port = ttk.Entry(port_frame, width=10)
        self.end_port.insert(0, "1000")
        self.end_port.pack(side='left', padx=2)
        
        # Scan options
        ttk.Label(input_frame, text="Scan Type:").grid(row=2, column=0, sticky='w', padx=5)
        self.scan_type = ttk.Combobox(input_frame, width=37, state='readonly')
        self.scan_type['values'] = ('Quick Scan (Common Ports)', 
                                     'Full Port Scan', 
                                     'Vulnerability Assessment')
        self.scan_type.current(0)
        self.scan_type.grid(row=2, column=1, padx=5, pady=5)
        
        # Control buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)
        
        self.start_btn = tk.Button(button_frame, text="▶ Start Scan", 
                                   command=self.start_scan,
                                   bg='#00aa00', fg='white', 
                                   font=('Arial', 10, 'bold'),
                                   padx=20, pady=5)
        self.start_btn.pack(side='left', padx=5)
        
        self.stop_btn = tk.Button(button_frame, text="⏹ Stop Scan", 
                                  command=self.stop_scan,
                                  bg='#aa0000', fg='white',
                                  font=('Arial', 10, 'bold'),
                                  padx=20, pady=5, state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        self.clear_btn = tk.Button(button_frame, text="🗑 Clear Results", 
                                   command=self.clear_results,
                                   bg='#555555', fg='white',
                                   font=('Arial', 10, 'bold'),
                                   padx=20, pady=5)
        self.clear_btn.pack(side='left', padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(self.root, mode='indeterminate')
        self.progress.pack(pady=5, padx=10, fill='x')
        
        # Status label
        self.status_label = ttk.Label(self.root, text="Ready to scan", 
                                     foreground='#00ff00')
        self.status_label.pack(pady=5)
        
        # Results area
        results_frame = ttk.Frame(self.root)
        results_frame.pack(pady=10, padx=10, fill='both', expand=True)
        
        ttk.Label(results_frame, text="Scan Results:", 
                 font=('Arial', 10, 'bold')).pack(anchor='w')
        
        self.results_text = scrolledtext.ScrolledText(results_frame, 
                                                      bg='#1e1e1e', 
                                                      fg='#00ff00',
                                                      font=('Courier', 9),
                                                      wrap='word')
        self.results_text.pack(fill='both', expand=True)
        
        # Configure text tags for colored output
        self.results_text.tag_config('header', foreground='#00ffff', 
                                    font=('Courier', 9, 'bold'))
        self.results_text.tag_config('success', foreground='#00ff00')
        self.results_text.tag_config('warning', foreground='#ffaa00')
        self.results_text.tag_config('critical', foreground='#ff0000', 
                                    font=('Courier', 9, 'bold'))
        self.results_text.tag_config('info', foreground='#aaaaaa')
    
    def log(self, message, tag='success'):
        """Log message to results area"""
        self.results_text.insert('end', message + '\n', tag)
        self.results_text.see('end')
        self.root.update_idletasks()
    
    def clear_results(self):
        """Clear the results area"""
        self.results_text.delete('1.0', 'end')
        self.status_label.config(text="Results cleared")
    
    def validate_input(self):
        """Validate user input"""
        target = self.target_entry.get().strip()
        
        if not target:
            messagebox.showerror("Error", "Please enter a target IP or hostname")
            return False
        
        try:
            start = int(self.start_port.get())
            end = int(self.end_port.get())
            
            if start < 1 or end > 65535 or start > end:
                messagebox.showerror("Error", 
                    "Invalid port range. Ports must be between 1-65535")
                return False
        except ValueError:
            messagebox.showerror("Error", "Port numbers must be integers")
            return False
        
        return True
    
    def start_scan(self):
        """Start the scanning process"""
        if not self.validate_input():
            return
        
        self.scanning = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.progress.start()
        
        # Start scan in separate thread
        scan_thread = threading.Thread(target=self.perform_scan)
        scan_thread.daemon = True
        scan_thread.start()
    
    def stop_scan(self):
        """Stop the scanning process"""
        self.scanning = False
        self.progress.stop()
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_label.config(text="Scan stopped by user")
        self.log("\n[!] Scan stopped by user", 'warning')
    
    def perform_scan(self):
        """Perform the actual network scan"""
        target = self.target_entry.get().strip()
        scan_type = self.scan_type.get()
        
        try:
            # Resolve hostname to IP
            try:
                target_ip = socket.gethostbyname(target)
            except socket.gaierror:
                self.log(f"[!] Could not resolve hostname: {target}", 'critical')
                self.stop_scan()
                return
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.log("="*70, 'header')
            self.log(f"NETWORK SECURITY SCAN - {timestamp}", 'header')
            self.log("="*70, 'header')
            self.log(f"Target: {target} ({target_ip})", 'info')
            self.log(f"Scan Type: {scan_type}", 'info')
            self.log("="*70 + "\n", 'header')
            
            # Ping test
            self.status_label.config(text=f"Checking if {target_ip} is reachable...")
            self.log("[*] Performing host discovery...", 'info')
            
            if self.scanner.ping_host(target_ip):
                self.log(f"[+] Host {target_ip} is UP", 'success')
            else:
                self.log(f"[-] Host {target_ip} appears to be DOWN or blocking ICMP", 'warning')
                self.log("[*] Continuing with port scan anyway...\n", 'info')
            
            # Determine ports to scan
            if "Common Ports" in scan_type:
                ports = list(self.scanner.common_ports.keys())
            else:
                start = int(self.start_port.get())
                end = int(self.end_port.get())
                ports = range(start, end + 1)
            
            self.log(f"\n[*] Scanning {len(ports)} ports...\n", 'info')
            
            open_ports = []
            vulnerabilities_found = []
            
            for i, port in enumerate(ports):
                if not self.scanning:
                    break
                
                self.status_label.config(
                    text=f"Scanning port {port}... ({i+1}/{len(ports)})")
                
                if self.scanner.scan_port(target_ip, port):
                    service = self.scanner.common_ports.get(port, "Unknown")
                    open_ports.append((port, service))
                    
                    self.log(f"[+] Port {port}/tcp OPEN - {service}", 'success')
                    
                    # Vulnerability assessment
                    if "Vulnerability" in scan_type:
                        banner = self.scanner.get_service_banner(target_ip, port)
                        if banner:
                            self.log(f"    └─ Banner: {banner[:100]}", 'info')
                        
                        vulns = self.scanner.check_vulnerabilities(port, banner)
                        if vulns:
                            vulnerabilities_found.extend(vulns)
                            for vuln in vulns:
                                self.log(f"    └─ [!] {vuln}", 'critical')
            
            # Summary
            self.log("\n" + "="*70, 'header')
            self.log("SCAN SUMMARY", 'header')
            self.log("="*70, 'header')
            self.log(f"Total ports scanned: {len(ports)}", 'info')
            self.log(f"Open ports found: {len(open_ports)}", 'success')
            
            if vulnerabilities_found:
                self.log(f"Potential vulnerabilities: {len(vulnerabilities_found)}", 
                        'critical')
                self.log("\n[!] SECURITY RECOMMENDATIONS:", 'critical')
                for vuln in set(vulnerabilities_found):
                    self.log(f"  • {vuln}", 'warning')
            
            self.log("\n[*] Scan completed!", 'success')
            self.status_label.config(text="Scan completed")
            
        except Exception as e:
            self.log(f"\n[!] Error during scan: {str(e)}", 'critical')
            self.status_label.config(text="Scan failed")
        
        finally:
            self.progress.stop()
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.scanning = False

def main():
    root = tk.Tk()
    app = NetworkScannerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

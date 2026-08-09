"""
Password Analyzer & Generator
==============================
Analyze password strength, estimate crack time, calculate entropy,
and generate secure passwords. No external dependencies.
"""

import math
import string
import secrets
import re
import tkinter as tk
from tkinter import ttk, messagebox


# ── Common password patterns / wordlist ────────────────────────────

COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "michael", "shadow", "123123", "654321", "superman", "qazwsx",
    "football", "password1", "password123", "welcome", "hello", "charlie",
    "donald", "admin", "login", "princess", "starwars", "passw0rd", "pass123",
    "p@ssword", "p@ssw0rd", "changeme", "secret", "winter", "summer",
    "spring", "autumn", "qwerty123", "password1!", "letmein1", "welcome1",
    "1q2w3e4r", "1qaz2wsx", "zaq1xsw2", "000000", "111111", "121212",
    "access", "flower", "hottie", "loveme", "zaq1zaq1", "test", "guest",
    "1234", "12345", "123456789", "1234567890", "0987654321",
}

KEYBOARD_PATTERNS = [
    "qwerty", "asdfgh", "zxcvbn", "qwertyuiop", "asdfghjkl", "zxcvbnm",
    "1234567890", "0987654321", "qazwsx", "wsxedc", "rfvtgb", "tgbyhn",
    "yhnujm", "1qaz", "2wsx", "3edc", "4rfv", "5tgb", "6yhn", "7ujm",
    "!@#$%", "!@#$%^&*",
]

LEET_MAP = {"@": "a", "4": "a", "3": "e", "1": "i", "!": "i", "0": "o",
            "$": "s", "5": "s", "7": "t", "+": "t"}


def _deleet(pwd):
    """Convert leet speak back to letters."""
    return "".join(LEET_MAP.get(c, c) for c in pwd.lower())


# ── Analysis Engine ────────────────────────────────────────────────

class PasswordAnalysis:
    """Analyze a password and produce a detailed report."""

    def __init__(self, password):
        self.password = password
        self.length = len(password)
        self.checks = {}
        self.score = 0  # 0-100
        self.entropy = 0.0
        self.crack_time = ""
        self.suggestions = []
        self._analyze()

    def _analyze(self):
        pwd = self.password

        # Character class checks
        has_lower = bool(re.search(r"[a-z]", pwd))
        has_upper = bool(re.search(r"[A-Z]", pwd))
        has_digit = bool(re.search(r"[0-9]", pwd))
        has_special = bool(re.search(r"[^a-zA-Z0-9]", pwd))

        self.checks["Length"] = {"value": self.length, "pass": self.length >= 8,
                                 "detail": f"{self.length} characters"}
        self.checks["Lowercase"] = {"value": has_lower, "pass": has_lower,
                                     "detail": "Contains lowercase" if has_lower else "No lowercase letters"}
        self.checks["Uppercase"] = {"value": has_upper, "pass": has_upper,
                                     "detail": "Contains uppercase" if has_upper else "No uppercase letters"}
        self.checks["Digits"] = {"value": has_digit, "pass": has_digit,
                                  "detail": "Contains digits" if has_digit else "No digits"}
        self.checks["Special Characters"] = {"value": has_special, "pass": has_special,
                                              "detail": "Contains special chars" if has_special else "No special characters"}

        # Charset size for entropy
        charset = 0
        if has_lower:
            charset += 26
        if has_upper:
            charset += 26
        if has_digit:
            charset += 10
        if has_special:
            charset += 33

        if charset > 0 and self.length > 0:
            self.entropy = self.length * math.log2(charset)
        else:
            self.entropy = 0

        # Common password check
        is_common = pwd.lower() in COMMON_PASSWORDS or _deleet(pwd) in COMMON_PASSWORDS
        self.checks["Not Common"] = {"value": not is_common, "pass": not is_common,
                                      "detail": "COMMON PASSWORD!" if is_common else "Not a common password"}

        # Keyboard pattern check
        pwd_lower = pwd.lower()
        has_pattern = False
        for pat in KEYBOARD_PATTERNS:
            if pat in pwd_lower or pat[::-1] in pwd_lower:
                has_pattern = True
                break
        self.checks["No Keyboard Pattern"] = {"value": not has_pattern, "pass": not has_pattern,
                                               "detail": "Contains keyboard pattern" if has_pattern else "No keyboard patterns"}

        # Repeated characters
        has_repeats = bool(re.search(r"(.)\1{2,}", pwd))
        self.checks["No Excessive Repeats"] = {"value": not has_repeats, "pass": not has_repeats,
                                                "detail": "Has repeated characters (3+)" if has_repeats else "No excessive repeats"}

        # Sequential chars
        has_sequential = False
        for i in range(len(pwd) - 2):
            if ord(pwd[i]) + 1 == ord(pwd[i + 1]) == ord(pwd[i + 2]) - 1:
                has_sequential = True
                break
        self.checks["No Sequential Chars"] = {"value": not has_sequential, "pass": not has_sequential,
                                               "detail": "Contains sequential characters" if has_sequential else "No sequential characters"}

        # Score calculation
        score = 0
        # Length scoring (up to 30 points)
        score += min(self.length * 3, 30)
        # Character variety (up to 25 points)
        variety = sum([has_lower, has_upper, has_digit, has_special])
        score += variety * 6
        # Entropy bonus (up to 25 points)
        score += min(self.entropy / 4, 25)
        # Penalties
        if is_common:
            score = min(score, 5)
        if has_pattern:
            score -= 15
        if has_repeats:
            score -= 10
        if has_sequential:
            score -= 5
        if self.length < 6:
            score = min(score, 15)

        self.score = max(0, min(100, int(score)))

        # Crack time estimation (offline, 10B guesses/sec)
        guesses_per_sec = 10_000_000_000
        if charset > 0 and self.length > 0:
            combinations = charset ** self.length
            seconds = combinations / guesses_per_sec / 2  # average case
            self.crack_time = self._format_time(seconds)
        else:
            self.crack_time = "Instant"

        if is_common:
            self.crack_time = "Instant (common password)"

        # Suggestions
        self.suggestions = []
        if self.length < 12:
            self.suggestions.append("Increase length to at least 12 characters")
        if not has_upper:
            self.suggestions.append("Add uppercase letters (A-Z)")
        if not has_lower:
            self.suggestions.append("Add lowercase letters (a-z)")
        if not has_digit:
            self.suggestions.append("Add numbers (0-9)")
        if not has_special:
            self.suggestions.append("Add special characters (!@#$%...)")
        if is_common:
            self.suggestions.append("Avoid common passwords entirely")
        if has_pattern:
            self.suggestions.append("Avoid keyboard patterns (qwerty, 1234, etc.)")
        if has_repeats:
            self.suggestions.append("Avoid repeating the same character 3+ times")
        if has_sequential:
            self.suggestions.append("Avoid sequential characters (abc, 123)")
        if not self.suggestions:
            self.suggestions.append("Password meets all recommended criteria")

    @staticmethod
    def _format_time(seconds):
        if seconds < 0.001:
            return "Instant"
        if seconds < 1:
            return f"{seconds * 1000:.0f} milliseconds"
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        if seconds < 3600:
            return f"{seconds / 60:.1f} minutes"
        if seconds < 86400:
            return f"{seconds / 3600:.1f} hours"
        if seconds < 31536000:
            return f"{seconds / 86400:.1f} days"
        years = seconds / 31536000
        if years < 1000:
            return f"{years:.1f} years"
        if years < 1e6:
            return f"{years / 1000:.1f} thousand years"
        if years < 1e9:
            return f"{years / 1e6:.1f} million years"
        if years < 1e12:
            return f"{years / 1e9:.1f} billion years"
        return f"{years / 1e12:.1f} trillion years"

    @property
    def strength_label(self):
        if self.score < 20:
            return "Very Weak"
        if self.score < 40:
            return "Weak"
        if self.score < 60:
            return "Fair"
        if self.score < 80:
            return "Strong"
        return "Very Strong"

    @property
    def strength_color(self):
        if self.score < 20:
            return "#dc3545"
        if self.score < 40:
            return "#e67e22"
        if self.score < 60:
            return "#f1c40f"
        if self.score < 80:
            return "#27ae60"
        return "#2ecc71"


# ── Password Generator ────────────────────────────────────────────

def generate_password(length=16, use_lower=True, use_upper=True, use_digits=True,
                      use_special=True, exclude_ambiguous=False):
    """Generate a cryptographically secure random password."""
    chars = ""
    required = []
    if use_lower:
        pool = string.ascii_lowercase
        if exclude_ambiguous:
            pool = pool.replace("l", "").replace("o", "")
        chars += pool
        required.append(secrets.choice(pool))
    if use_upper:
        pool = string.ascii_uppercase
        if exclude_ambiguous:
            pool = pool.replace("I", "").replace("O", "")
        chars += pool
        required.append(secrets.choice(pool))
    if use_digits:
        pool = string.digits
        if exclude_ambiguous:
            pool = pool.replace("0", "").replace("1", "")
        chars += pool
        required.append(secrets.choice(pool))
    if use_special:
        pool = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        chars += pool
        required.append(secrets.choice(pool))

    if not chars:
        chars = string.ascii_letters + string.digits
        required = [secrets.choice(chars)]

    length = max(length, len(required))
    remaining = length - len(required)
    password_chars = required + [secrets.choice(chars) for _ in range(remaining)]

    # Shuffle using Fisher-Yates
    for i in range(len(password_chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password_chars[i], password_chars[j] = password_chars[j], password_chars[i]

    return "".join(password_chars)


# ── GUI Application ───────────────────────────────────────────────

class PasswordAnalyzerApp(tk.Tk):
    """Main application for password analysis and generation."""

    def __init__(self):
        super().__init__()
        self.title("Password Analyzer & Generator")
        self.geometry("800x720")
        self.minsize(700, 600)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Score.TLabel", font=("Segoe UI", 28, "bold"))
        style.configure("Pass.TLabel", foreground="#27ae60", font=("Segoe UI", 10))
        style.configure("Fail.TLabel", foreground="#dc3545", font=("Segoe UI", 10))
        style.configure("Suggest.TLabel", foreground="#2980b9", font=("Segoe UI", 10))

        self.show_password = tk.BooleanVar(value=False)
        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.analyze_tab = ttk.Frame(notebook, padding=10)
        self.generate_tab = ttk.Frame(notebook, padding=10)

        notebook.add(self.analyze_tab, text="  Analyze Password  ")
        notebook.add(self.generate_tab, text="  Generate Password  ")

        self._build_analyze_tab()
        self._build_generate_tab()

    def _build_analyze_tab(self):
        f = self.analyze_tab
        ttk.Label(f, text="Password Strength Analyzer", style="Title.TLabel").pack(anchor="w")
        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 10))

        # Input
        input_frame = ttk.Frame(f)
        input_frame.pack(fill="x", pady=4)
        ttk.Label(input_frame, text="Password:").pack(side="left")
        self.pwd_var = tk.StringVar()
        self.pwd_entry = ttk.Entry(input_frame, textvariable=self.pwd_var, show="*",
                                   font=("Consolas", 12), width=35)
        self.pwd_entry.pack(side="left", padx=8, fill="x", expand=True)
        self.pwd_var.trace_add("write", lambda *_: self._on_pwd_change())

        ttk.Checkbutton(input_frame, text="Show", variable=self.show_password,
                        command=self._toggle_show).pack(side="left")
        ttk.Button(input_frame, text="Analyze", command=self._analyze).pack(side="left", padx=8)

        # Strength meter canvas
        meter_frame = ttk.LabelFrame(f, text="Strength Meter", padding=8)
        meter_frame.pack(fill="x", pady=8)

        self.meter_canvas = tk.Canvas(meter_frame, height=40, bg="#f0f0f0", highlightthickness=0)
        self.meter_canvas.pack(fill="x")

        info_frame = ttk.Frame(meter_frame)
        info_frame.pack(fill="x", pady=(4, 0))
        self.strength_label = ttk.Label(info_frame, text="", style="Score.TLabel")
        self.strength_label.pack(side="left")
        self.score_label = ttk.Label(info_frame, text="", font=("Segoe UI", 12))
        self.score_label.pack(side="left", padx=16)

        # Details
        details_frame = ttk.LabelFrame(f, text="Analysis Details", padding=8)
        details_frame.pack(fill="both", expand=True, pady=4)

        # Scrollable frame for checks
        canvas = tk.Canvas(details_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=canvas.yview)
        self.checks_frame = ttk.Frame(canvas)

        self.checks_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.checks_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Info labels (will be populated by _analyze)
        self.entropy_label = ttk.Label(self.checks_frame, text="")
        self.crack_label = ttk.Label(self.checks_frame, text="")

    def _toggle_show(self):
        self.pwd_entry.config(show="" if self.show_password.get() else "*")

    def _on_pwd_change(self):
        """Live analysis as user types."""
        pwd = self.pwd_var.get()
        if pwd:
            self._analyze(quiet=True)
        else:
            self._clear_analysis()

    def _clear_analysis(self):
        self.meter_canvas.delete("all")
        self.strength_label.config(text="")
        self.score_label.config(text="")
        for w in self.checks_frame.winfo_children():
            w.destroy()

    def _analyze(self, quiet=False):
        pwd = self.pwd_var.get()
        if not pwd:
            if not quiet:
                messagebox.showwarning("Warning", "Please enter a password.")
            return

        analysis = PasswordAnalysis(pwd)

        # Update meter
        self.meter_canvas.delete("all")
        w = self.meter_canvas.winfo_width() or 600
        bar_w = int(w * analysis.score / 100)
        self.meter_canvas.create_rectangle(0, 0, w, 40, fill="#e0e0e0", outline="")
        if bar_w > 0:
            self.meter_canvas.create_rectangle(0, 0, bar_w, 40, fill=analysis.strength_color, outline="")
        self.meter_canvas.create_text(w // 2, 20, text=f"{analysis.score}%",
                                       font=("Segoe UI", 14, "bold"), fill="#333")

        self.strength_label.config(text=analysis.strength_label)
        self.score_label.config(text=f"Entropy: {analysis.entropy:.1f} bits  |  Crack time: {analysis.crack_time}")

        # Update checks
        for w in self.checks_frame.winfo_children():
            w.destroy()

        row = 0
        ttk.Label(self.checks_frame, text="Security Checks:", style="Section.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
        row += 1

        for name, check in analysis.checks.items():
            icon = "PASS" if check["pass"] else "FAIL"
            style = "Pass.TLabel" if check["pass"] else "Fail.TLabel"
            ttk.Label(self.checks_frame, text=f"[{icon}]", style=style).grid(row=row, column=0, sticky="w", padx=(0, 8))
            ttk.Label(self.checks_frame, text=f"{name}: {check['detail']}").grid(row=row, column=1, sticky="w")
            row += 1

        if analysis.suggestions:
            row += 1
            ttk.Label(self.checks_frame, text="Suggestions:", style="Section.TLabel").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
            row += 1
            for s in analysis.suggestions:
                ttk.Label(self.checks_frame, text=f"  -> {s}", style="Suggest.TLabel").grid(
                    row=row, column=0, columnspan=2, sticky="w")
                row += 1

    # ── Generator Tab ──────────────────────────────────────────────

    def _build_generate_tab(self):
        f = self.generate_tab
        ttk.Label(f, text="Password Generator", style="Title.TLabel").pack(anchor="w")
        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=(4, 10))

        # Options
        opts_frame = ttk.LabelFrame(f, text="Options", padding=10)
        opts_frame.pack(fill="x", pady=4)

        len_frame = ttk.Frame(opts_frame)
        len_frame.pack(fill="x", pady=2)
        ttk.Label(len_frame, text="Length:").pack(side="left")
        self.gen_length = tk.IntVar(value=16)
        self.len_spin = ttk.Spinbox(len_frame, from_=4, to=128, textvariable=self.gen_length, width=6)
        self.len_spin.pack(side="left", padx=8)
        self.len_slider = ttk.Scale(len_frame, from_=4, to=128, variable=self.gen_length, orient="horizontal")
        self.len_slider.pack(side="left", fill="x", expand=True, padx=8)

        self.gen_lower = tk.BooleanVar(value=True)
        self.gen_upper = tk.BooleanVar(value=True)
        self.gen_digits = tk.BooleanVar(value=True)
        self.gen_special = tk.BooleanVar(value=True)
        self.gen_no_ambiguous = tk.BooleanVar(value=False)

        check_frame = ttk.Frame(opts_frame)
        check_frame.pack(fill="x", pady=4)
        ttk.Checkbutton(check_frame, text="Lowercase (a-z)", variable=self.gen_lower).pack(side="left", padx=8)
        ttk.Checkbutton(check_frame, text="Uppercase (A-Z)", variable=self.gen_upper).pack(side="left", padx=8)
        ttk.Checkbutton(check_frame, text="Digits (0-9)", variable=self.gen_digits).pack(side="left", padx=8)
        ttk.Checkbutton(check_frame, text="Special (!@#...)", variable=self.gen_special).pack(side="left", padx=8)

        ttk.Checkbutton(opts_frame, text="Exclude ambiguous characters (0, O, l, 1, I)",
                        variable=self.gen_no_ambiguous).pack(anchor="w", pady=2)

        # Generate button
        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", pady=8)
        ttk.Button(btn_frame, text="Generate Password", command=self._generate).pack(side="left")
        ttk.Button(btn_frame, text="Generate 5", command=self._generate_multi).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="Copy to Clipboard", command=self._copy_generated).pack(side="left", padx=8)

        # Result
        result_frame = ttk.LabelFrame(f, text="Generated Password", padding=10)
        result_frame.pack(fill="x", pady=4)
        self.gen_result_var = tk.StringVar()
        ttk.Entry(result_frame, textvariable=self.gen_result_var, font=("Consolas", 14),
                  state="readonly").pack(fill="x")

        self.gen_strength = ttk.Label(result_frame, text="")
        self.gen_strength.pack(anchor="w", pady=(4, 0))

        # Multi results
        multi_frame = ttk.LabelFrame(f, text="Batch Generated", padding=10)
        multi_frame.pack(fill="both", expand=True, pady=4)
        self.gen_multi_text = tk.Text(multi_frame, height=10, font=("Consolas", 11), state="disabled",
                                      bg="#f5f5f5")
        self.gen_multi_text.pack(fill="both", expand=True)

    def _generate(self):
        pwd = generate_password(
            length=self.gen_length.get(),
            use_lower=self.gen_lower.get(),
            use_upper=self.gen_upper.get(),
            use_digits=self.gen_digits.get(),
            use_special=self.gen_special.get(),
            exclude_ambiguous=self.gen_no_ambiguous.get(),
        )
        self.gen_result_var.set(pwd)
        analysis = PasswordAnalysis(pwd)
        self.gen_strength.config(
            text=f"Strength: {analysis.strength_label} ({analysis.score}%)  |  "
                 f"Entropy: {analysis.entropy:.1f} bits  |  Crack time: {analysis.crack_time}")

    def _generate_multi(self):
        lines = []
        for i in range(5):
            pwd = generate_password(
                length=self.gen_length.get(),
                use_lower=self.gen_lower.get(),
                use_upper=self.gen_upper.get(),
                use_digits=self.gen_digits.get(),
                use_special=self.gen_special.get(),
                exclude_ambiguous=self.gen_no_ambiguous.get(),
            )
            analysis = PasswordAnalysis(pwd)
            lines.append(f"{i + 1}. {pwd}  ({analysis.strength_label}, {analysis.entropy:.0f} bits)")
        self.gen_multi_text.config(state="normal")
        self.gen_multi_text.delete("1.0", "end")
        self.gen_multi_text.insert("1.0", "\n".join(lines))
        self.gen_multi_text.config(state="disabled")

    def _copy_generated(self):
        pwd = self.gen_result_var.get()
        if pwd:
            self.clipboard_clear()
            self.clipboard_append(pwd)
            messagebox.showinfo("Copied", "Password copied to clipboard.")


if __name__ == "__main__":
    app = PasswordAnalyzerApp()
    app.mainloop()

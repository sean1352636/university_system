"""
Enhanced Console Output Utility
Provides colored, formatted console output for better user experience.
"""

import sys
import os
from typing import Optional, List, Dict, Any
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output"""
    # Basic colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'

    # Reset
    RESET = '\033[0m'

    @staticmethod
    def supports_color() -> bool:
        """Check if the terminal supports color output"""
        if not hasattr(sys.stdout, "isatty"):
            return False
        if not sys.stdout.isatty():
            return False
        if os.environ.get("TERM") == "dumb":
            return False
        return True


class ConsoleOutput:
    """Enhanced console output with colors and formatting"""

    def __init__(self, use_colors: bool = True):
        """
        Initialize console output handler

        Args:
            use_colors: Enable colored output (auto-detects terminal support)
        """
        self.use_colors = use_colors and Colors.supports_color()

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled"""
        if not self.use_colors:
            return text
        return f"{color}{text}{Colors.RESET}"

    # ==================== Basic Output Methods ====================

    def print(self, message: str, color: Optional[str] = None):
        """Print a message with optional color"""
        if color:
            print(self._colorize(message, color))
        else:
            print(message)

    def success(self, message: str, prefix: str = "✓"):
        """Print a success message in green"""
        formatted = f"{prefix} {message}" if prefix else message
        print(self._colorize(formatted, Colors.BRIGHT_GREEN))

    def error(self, message: str, prefix: str = "✗"):
        """Print an error message in red"""
        formatted = f"{prefix} {message}" if prefix else message
        print(self._colorize(formatted, Colors.BRIGHT_RED))

    def warning(self, message: str, prefix: str = "⚠"):
        """Print a warning message in yellow"""
        formatted = f"{prefix} {message}" if prefix else message
        print(self._colorize(formatted, Colors.BRIGHT_YELLOW))

    def info(self, message: str, prefix: str = "ℹ"):
        """Print an info message in cyan"""
        formatted = f"{prefix} {message}" if prefix else message
        print(self._colorize(formatted, Colors.BRIGHT_CYAN))

    def debug(self, message: str, prefix: str = "🔧"):
        """Print a debug message in dim color"""
        formatted = f"{prefix} {message}" if prefix else message
        print(self._colorize(formatted, Colors.DIM))

    # ==================== Formatted Output Methods ====================

    def header(self, title: str, width: int = 80, char: str = "="):
        """Print a header with title"""
        print()
        print(self._colorize(char * width, Colors.BOLD + Colors.BRIGHT_BLUE))
        centered_title = title.center(width)
        print(self._colorize(centered_title, Colors.BOLD + Colors.BRIGHT_WHITE))
        print(self._colorize(char * width, Colors.BOLD + Colors.BRIGHT_BLUE))
        print()

    def section(self, title: str, width: int = 80):
        """Print a section divider"""
        print()
        print(self._colorize(f"  {title}  ", Colors.BOLD + Colors.BRIGHT_CYAN))
        print(self._colorize("-" * width, Colors.CYAN))

    def box(self, message: str, width: int = 60, color: Optional[str] = None):
        """Print a message in a box"""
        lines = message.split('\n')
        max_len = max(len(line) for line in lines)
        box_width = min(max(max_len + 4, width), 100)

        border_color = color or Colors.BRIGHT_WHITE

        # Top border
        print(self._colorize("╔" + "═" * (box_width - 2) + "╗", border_color))

        # Content lines
        for line in lines:
            padding = box_width - len(line) - 4
            content = f"║ {line}{' ' * padding} ║"
            print(self._colorize(content, border_color))

        # Bottom border
        print(self._colorize("╚" + "═" * (box_width - 2) + "╝", border_color))

    def status(self, label: str, value: Any, success: bool = True):
        """Print a status line with label and value"""
        status_color = Colors.BRIGHT_GREEN if success else Colors.BRIGHT_RED
        label_formatted = self._colorize(f"{label}:", Colors.BRIGHT_WHITE)
        value_formatted = self._colorize(str(value), status_color)
        print(f"  {label_formatted} {value_formatted}")

    def progress(self, current: int, total: int, label: str = "", width: int = 40):
        """Print a progress bar"""
        percent = (current / total) if total > 0 else 0
        filled = int(width * percent)
        bar = "█" * filled + "░" * (width - filled)

        # Color based on progress
        if percent < 0.33:
            color = Colors.BRIGHT_RED
        elif percent < 0.66:
            color = Colors.BRIGHT_YELLOW
        else:
            color = Colors.BRIGHT_GREEN

        percentage_str = f"{percent * 100:.1f}%"
        label_str = f"{label} " if label else ""
        progress_str = f"{label_str}[{bar}] {percentage_str} ({current}/{total})"

        print(f"\r{self._colorize(progress_str, color)}", end="", flush=True)

        if current >= total:
            print()  # New line when complete

    # ==================== Table Output Methods ====================

    def table(self, headers: List[str], rows: List[List[Any]],
              title: Optional[str] = None, max_width: int = 120):
        """
        Print a formatted table

        Args:
            headers: List of column headers
            rows: List of rows (each row is a list of values)
            title: Optional table title
            max_width: Maximum width of the table
        """
        if not rows:
            self.warning("No data to display")
            return

        # Calculate column widths
        col_widths = [len(str(h)) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # Adjust widths if total exceeds max_width
        total_width = sum(col_widths) + len(headers) * 3 + 1
        if total_width > max_width:
            scale = (max_width - len(headers) * 3 - 1) / sum(col_widths)
            col_widths = [max(8, int(w * scale)) for w in col_widths]

        # Print title if provided
        if title:
            print()
            title_width = sum(col_widths) + len(headers) * 3 + 1
            print(self._colorize(title.center(title_width), Colors.BOLD + Colors.BRIGHT_CYAN))

        # Print top border
        print(self._colorize("┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐",
                           Colors.BRIGHT_WHITE))

        # Print headers
        header_row = "│"
        for i, header in enumerate(headers):
            header_row += f" {self._colorize(str(header).ljust(col_widths[i]), Colors.BOLD + Colors.BRIGHT_YELLOW)} │"
        print(header_row)

        # Print header separator
        print(self._colorize("├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤",
                           Colors.BRIGHT_WHITE))

        # Print rows
        for row in rows:
            row_str = "│"
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    cell_str = str(cell)[:col_widths[i]].ljust(col_widths[i])
                    row_str += f" {cell_str} │"
            print(row_str)

        # Print bottom border
        print(self._colorize("└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘",
                           Colors.BRIGHT_WHITE))

    def simple_table(self, headers: List[str], rows: List[List[Any]],
                    title: Optional[str] = None):
        """
        Print a simple table without borders (lighter version)

        Args:
            headers: List of column headers
            rows: List of rows
            title: Optional table title
        """
        if not rows:
            self.warning("No data to display")
            return

        # Calculate column widths
        col_widths = [len(str(h)) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # Print title
        if title:
            print()
            print(self._colorize(title, Colors.BOLD + Colors.BRIGHT_CYAN))

        # Print separator
        total_width = sum(col_widths) + len(headers) * 3
        print(self._colorize("=" * total_width, Colors.BRIGHT_WHITE))

        # Print headers
        header_row = ""
        for i, header in enumerate(headers):
            header_row += self._colorize(str(header).ljust(col_widths[i] + 2),
                                        Colors.BOLD + Colors.BRIGHT_YELLOW)
        print(header_row)

        # Print header separator
        print(self._colorize("-" * total_width, Colors.BRIGHT_WHITE))

        # Print rows
        for row in rows:
            row_str = ""
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    row_str += str(cell)[:col_widths[i]].ljust(col_widths[i] + 2)
            print(row_str)

        print()

    def key_value_list(self, data: Dict[str, Any], title: Optional[str] = None,
                       indent: int = 2):
        """
        Print a key-value list

        Args:
            data: Dictionary of key-value pairs
            title: Optional title
            indent: Number of spaces to indent
        """
        if title:
            print()
            print(self._colorize(title, Colors.BOLD + Colors.BRIGHT_CYAN))
            print(self._colorize("-" * len(title), Colors.CYAN))

        max_key_len = max(len(str(k)) for k in data.keys()) if data else 0

        for key, value in data.items():
            key_str = self._colorize(f"{str(key)}:".ljust(max_key_len + 2),
                                    Colors.BRIGHT_WHITE)
            print(f"{' ' * indent}{key_str} {value}")

        print()

    # ==================== Special Output Methods ====================

    def banner(self, text: str, width: int = 80, style: str = "double"):
        """Print a banner with text"""
        styles = {
            "single": ("┌", "─", "┐", "│", "│", "└", "─", "┘"),
            "double": ("╔", "═", "╗", "║", "║", "╚", "═", "╝"),
            "bold": ("┏", "━", "┓", "┃", "┃", "┗", "━", "┛"),
        }

        chars = styles.get(style, styles["single"])

        print()
        print(self._colorize(chars[0] + chars[1] * (width - 2) + chars[2],
                           Colors.BOLD + Colors.BRIGHT_CYAN))

        # Center text
        centered = text.center(width - 2)
        print(self._colorize(f"{chars[3]}{centered}{chars[4]}",
                           Colors.BOLD + Colors.BRIGHT_WHITE))

        print(self._colorize(chars[5] + chars[6] * (width - 2) + chars[7],
                           Colors.BOLD + Colors.BRIGHT_CYAN))
        print()

    def menu(self, title: str, options: List[str], show_numbers: bool = True):
        """
        Print a formatted menu

        Args:
            title: Menu title
            options: List of menu options
            show_numbers: Show option numbers
        """
        print()
        self.header(title, width=60, char="=")

        for i, option in enumerate(options, 1):
            if show_numbers:
                number = self._colorize(f"[{i}]", Colors.BRIGHT_YELLOW)
                print(f"  {number} {option}")
            else:
                bullet = self._colorize("•", Colors.BRIGHT_CYAN)
                print(f"  {bullet} {option}")

        print()

    def list_items(self, items: List[str], title: Optional[str] = None,
                   bullet: str = "•", color: Optional[str] = None):
        """Print a bulleted list"""
        if title:
            print()
            print(self._colorize(title, Colors.BOLD + Colors.BRIGHT_CYAN))

        item_color = color or Colors.BRIGHT_WHITE
        bullet_formatted = self._colorize(bullet, Colors.BRIGHT_CYAN)

        for item in items:
            print(f"  {bullet_formatted} {self._colorize(item, item_color)}")

        print()

    def divider(self, width: int = 80, char: str = "-", color: Optional[str] = None):
        """Print a horizontal divider"""
        divider_color = color or Colors.BRIGHT_WHITE
        print(self._colorize(char * width, divider_color))

    def timestamp(self, label: str = "Timestamp"):
        """Print current timestamp"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status(label, now)

    # ==================== Interactive Methods ====================

    def prompt(self, message: str, default: Optional[str] = None) -> str:
        """Prompt user for input with colored message"""
        prompt_text = self._colorize(f"{message}", Colors.BRIGHT_CYAN)
        if default:
            prompt_text += self._colorize(f" [{default}]", Colors.DIM)
        prompt_text += self._colorize(": ", Colors.BRIGHT_WHITE)

        response = input(prompt_text).strip()
        return response if response else (default or "")

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask for yes/no confirmation"""
        default_str = "Y/n" if default else "y/N"
        prompt_text = self._colorize(f"{message} ", Colors.BRIGHT_YELLOW)
        prompt_text += self._colorize(f"[{default_str}]", Colors.DIM)
        prompt_text += self._colorize(": ", Colors.BRIGHT_WHITE)

        response = input(prompt_text).strip().lower()

        if not response:
            return default

        return response in ('y', 'yes')

    def pause(self, message: str = "Press Enter to continue..."):
        """Pause and wait for user input"""
        input(self._colorize(message, Colors.DIM))

    # ==================== Summary Methods ====================

    def summary(self, title: str, stats: Dict[str, Any], width: int = 60):
        """Print a summary box with statistics"""
        print()
        print(self._colorize("╔" + "═" * (width - 2) + "╗", Colors.BRIGHT_BLUE))

        # Title
        title_centered = title.center(width - 2)
        print(self._colorize(f"║{title_centered}║", Colors.BOLD + Colors.BRIGHT_WHITE))

        # Separator
        print(self._colorize("╠" + "═" * (width - 2) + "╣", Colors.BRIGHT_BLUE))

        # Stats
        max_key_len = max(len(str(k)) for k in stats.keys()) if stats else 0

        for key, value in stats.items():
            key_str = str(key).ljust(max_key_len)
            value_str = str(value).rjust(width - max_key_len - 6)
            content = f"║ {key_str} {value_str} ║"
            print(self._colorize(content, Colors.BRIGHT_WHITE))

        # Bottom border
        print(self._colorize("╚" + "═" * (width - 2) + "╝", Colors.BRIGHT_BLUE))
        print()


# Create a global instance for easy access
console = ConsoleOutput()


# ==================== Convenience Functions ====================

def print_success(message: str):
    """Quick success message"""
    console.success(message)


def print_error(message: str):
    """Quick error message"""
    console.error(message)


def print_warning(message: str):
    """Quick warning message"""
    console.warning(message)


def print_info(message: str):
    """Quick info message"""
    console.info(message)


def print_header(title: str, width: int = 80):
    """Quick header"""
    console.header(title, width)


def print_table(headers: List[str], rows: List[List[Any]], title: Optional[str] = None):
    """Quick table"""
    console.table(headers, rows, title)


def print_menu(title: str, options: List[str]):
    """Quick menu"""
    console.menu(title, options)

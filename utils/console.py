"""
Console - Centralized Terminal Output Management

Modern terminal output with colors, spinners, progress bars, and dynamic line updates.
Supports verbosity control for clean production output vs detailed debugging.

Usage:
    from utils.console import console
    
    console.info("Processing...")
    console.success("Complete!")
    console.progress("Uploading", 5, 10)
    
    with console.spinner("Initializing..."):
        do_something()
"""

import os
import sys
import time
import threading
from contextlib import contextmanager
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Console:
    """
    Centralized console output with colors, spinners, and progress bars.
    
    Verbosity Levels:
        SILENT (0): Errors only
        NORMAL (1): User-facing progress (default)
        VERBOSE (2): Debug messages
    """
    
    # Verbosity levels
    SILENT = 0
    NORMAL = 1
    VERBOSE = 2
    
    # ANSI color codes (PowerShell 7+ / Windows Terminal)
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "cyan": "\033[96m",
        "magenta": "\033[95m",
        "blue": "\033[94m",
        "white": "\033[97m",
        "gray": "\033[90m",
    }
    
    # Spinner frames
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    # Icons
    ICONS = {
        "success": "✓",
        "error": "✗",
        "warning": "⚠",
        "info": "ℹ",
        "progress": "⏳",
        "arrow": "→",
        "bullet": "•",
        "spark": "✦",
    }
    
    def __init__(self):
        self._verbosity = int(os.getenv("CONSOLE_VERBOSITY", "1"))
        self._spinner_active = False
        self._spinner_thread = None
        self._last_line_length = 0
        self._colors_enabled = self._detect_color_support()
    
    def _detect_color_support(self) -> bool:
        """Detect if terminal supports ANSI colors."""
        # Windows Terminal and PowerShell 7+ support colors
        if os.name == "nt":
            # Enable ANSI on Windows
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
                return True
            except Exception:
                return False
        return True
    
    def set_verbosity(self, level: int):
        """Set verbosity level (SILENT=0, NORMAL=1, VERBOSE=2)."""
        self._verbosity = max(0, min(2, level))
    
    def _color(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self._colors_enabled:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"
    
    def _should_print(self, level: int) -> bool:
        """Check if message should be printed based on verbosity."""
        return self._verbosity >= level
    
    def _clear_line(self):
        """Clear the current line."""
        sys.stdout.write("\r" + " " * self._last_line_length + "\r")
        sys.stdout.flush()
    
    def _print(self, message: str, end: str = "\n", level: int = NORMAL):
        """Internal print with verbosity check."""
        if not self._should_print(level):
            return
        print(message, end=end, flush=True)
        if end == "\n":
            self._last_line_length = 0
        else:
            self._last_line_length = len(message)
    
    # =========================================================
    # PUBLIC API - Basic Messages
    # =========================================================
    
    def info(self, message: str, indent: int = 0):
        """Print info message (cyan)."""
        prefix = "  " * indent
        icon = self._color(self.ICONS["info"], "cyan")
        self._print(f"{prefix}{icon} {message}")
    
    def success(self, message: str, indent: int = 0):
        """Print success message (green)."""
        prefix = "  " * indent
        icon = self._color(self.ICONS["success"], "green")
        self._print(f"{prefix}{icon} {message}")
    
    def warning(self, message: str, indent: int = 0):
        """Print warning message (yellow)."""
        prefix = "  " * indent
        icon = self._color(self.ICONS["warning"], "yellow")
        self._print(f"{prefix}{icon} {message}")
    
    def error(self, message: str, indent: int = 0):
        """Print error message (red). Always shown."""
        prefix = "  " * indent
        icon = self._color(self.ICONS["error"], "red")
        self._print(f"{prefix}{icon} {self._color(message, 'red')}", level=self.SILENT)
    
    def debug(self, message: str, indent: int = 0):
        """Print debug message (gray). Only shown in VERBOSE mode."""
        prefix = "  " * indent
        msg = self._color(message, "gray")
        self._print(f"{prefix}   {msg}", level=self.VERBOSE)
    
    def item(self, message: str, indent: int = 1):
        """Print bullet item."""
        prefix = "  " * indent
        arrow = self._color(self.ICONS["arrow"], "dim")
        self._print(f"{prefix}{arrow} {message}")
    
    # =========================================================
    # PUBLIC API - Sections & Headers
    # =========================================================
    
    def header(self, title: str, width: int = 50):
        """Print application header."""
        if not self._should_print(self.NORMAL):
            return
        bar = "═" * ((width - len(title) - 2) // 2)
        header_text = f"\n{bar} {self._color(title, 'bold')} {bar}"
        print(header_text)
    
    def section(self, title: str, width: int = 40):
        """Print section header."""
        if not self._should_print(self.NORMAL):
            return
        bar = "═" * ((width - len(title) - 2) // 2)
        print(f"\n{self._color(bar, 'dim')} {self._color(title, 'cyan')} {self._color(bar, 'dim')}")
    
    def blank(self):
        """Print blank line."""
        if self._should_print(self.NORMAL):
            print()
    
    # =========================================================
    # PUBLIC API - Progress
    # =========================================================
    
    def progress(self, label: str, current: int, total: int, width: int = 20):
        """
        Print/update progress bar on same line.
        
        Example: ⏳ Processing [████████░░░░░░░░░░░░] 40% (8/20)
        """
        if not self._should_print(self.NORMAL):
            return
        
        percent = current / total if total > 0 else 0
        filled = int(width * percent)
        empty = width - filled
        
        bar = self._color("█" * filled, "cyan") + self._color("░" * empty, "dim")
        icon = self._color(self.ICONS["progress"], "cyan")
        
        line = f"\r{icon} {label} [{bar}] {int(percent * 100):3d}% ({current}/{total})"
        
        sys.stdout.write(line + " " * 5)  # Padding to clear previous
        sys.stdout.flush()
        self._last_line_length = len(line) + 5
        
        if current >= total:
            print()  # Newline when complete
            self._last_line_length = 0
    
    def step(self, current: int, total: int, message: str):
        """Print step progress (e.g., [2/5] Processing file.py)."""
        if not self._should_print(self.NORMAL):
            return
        step_label = self._color(f"[{current}/{total}]", "cyan")
        print(f"  {step_label} {message}")
    
    # =========================================================
    # PUBLIC API - Spinner
    # =========================================================
    
    @contextmanager
    def spinner(self, message: str):
        """
        Context manager for spinner animation.
        
        Usage:
            with console.spinner("Loading..."):
                do_something()
        """
        if not self._should_print(self.NORMAL):
            yield
            return
        
        self._spinner_active = True
        stop_event = threading.Event()
        
        def animate():
            frame_idx = 0
            while not stop_event.is_set():
                frame = self._color(self.SPINNER_FRAMES[frame_idx], "cyan")
                sys.stdout.write(f"\r{frame} {message}")
                sys.stdout.flush()
                frame_idx = (frame_idx + 1) % len(self.SPINNER_FRAMES)
                time.sleep(0.08)
        
        thread = threading.Thread(target=animate, daemon=True)
        thread.start()
        
        try:
            yield
            stop_event.set()
            thread.join(timeout=0.2)
            # Show success
            icon = self._color(self.ICONS["success"], "green")
            sys.stdout.write(f"\r{icon} {message}\n")
            sys.stdout.flush()
        except Exception:
            stop_event.set()
            thread.join(timeout=0.2)
            # Show error
            icon = self._color(self.ICONS["error"], "red")
            sys.stdout.write(f"\r{icon} {message}\n")
            sys.stdout.flush()
            raise
        finally:
            self._spinner_active = False
    
    def status(self, message: str, done: bool = False):
        """
        Print status message that can be updated.
        
        Args:
            message: Status message
            done: If True, adds checkmark and newline
        """
        if not self._should_print(self.NORMAL):
            return
        
        self._clear_line()
        
        if done:
            icon = self._color(self.ICONS["success"], "green")
            print(f"{icon} {message}")
        else:
            icon = self._color(self.ICONS["progress"], "cyan")
            sys.stdout.write(f"{icon} {message}")
            sys.stdout.flush()
            self._last_line_length = len(message) + 2
    
    # =========================================================
    # PUBLIC API - Tables
    # =========================================================
    
    def table(self, headers: list, rows: list, col_widths: Optional[list] = None):
        """Print a simple table."""
        if not self._should_print(self.NORMAL):
            return
        
        if not col_widths:
            col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 
                         for i in range(len(headers))]
        
        # Header
        header_row = "".join(
            self._color(str(h).ljust(w), "bold") 
            for h, w in zip(headers, col_widths)
        )
        print(f"  {header_row}")
        print(f"  {self._color('─' * sum(col_widths), 'dim')}")
        
        # Rows
        for row in rows:
            row_text = "".join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
            print(f"  {row_text}")


# =========================================================
# SINGLETON INSTANCE
# =========================================================

console = Console()


# =========================================================
# SUPPRESS EXTERNAL LIBRARY LOGGING
# =========================================================

def suppress_library_logs():
    """Suppress verbose logging from external libraries."""
    import logging
    
    # Suppress gemini_webapi debug logs
    logging.getLogger("gemini_webapi").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Suppress other noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


    # Suppress loguru (used by gemini_webapi)
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="SUCCESS")
    except ImportError:
        pass

# Auto-suppress on import if not in VERBOSE mode
if console._verbosity < Console.VERBOSE:
    suppress_library_logs()

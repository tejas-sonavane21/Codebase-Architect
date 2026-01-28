"""
Rate Limiter - Centralized Delay Configuration

Controls API call delays to stay within Gemini free tier limits.
Configure via .env: DELAY_MODE=safe|fast

Includes TokenBucket for TPM (Tokens Per Minute) management.
TPM tracking only applies to generate_content calls, NOT file uploads.
"""

import os
import time
import sys
from dotenv import load_dotenv

load_dotenv()


# ============================================
# TPM (Token Per Minute) - TRUE SLIDING WINDOW
# ============================================
class TokenBucket:
    """
    Tracks token usage using a TRUE sliding window (70 seconds).
    
    Unlike the flawed "leaky bucket" approach, this tracks EACH call's
    timestamp and token count. Before a new call, we count only tokens
    from calls made within the last 70 seconds.
    
    Full Reset Strategy: We wait until ALL previous calls fall outside
    the 70-second window before making a new call.
    
    Why 70s? Google uses 60s, but we add 10s buffer for network latency.
    """
    
    WINDOW_SECONDS = 70  # Google's window (60s) + Network Buffer (10s)
    
    def __init__(self, capacity: int = 15_000):
        """
        Initialize the token bucket.
        
        Args:
            capacity: TPM limit (default 15,000 for Gemma models).
        """
        self.capacity = capacity
        # List of (timestamp, tokens) tuples for all calls in the window
        self.call_history: list = []
    
    def _prune_old_calls(self):
        """Remove calls older than 60 seconds from history."""
        cutoff = time.time() - self.WINDOW_SECONDS
        self.call_history = [(ts, tokens) for ts, tokens in self.call_history if ts > cutoff]
    
    def _get_current_usage(self) -> int:
        """Get total tokens used in the current 60-second window."""
        self._prune_old_calls()
        return sum(tokens for _, tokens in self.call_history)
    
    def _get_oldest_call_age(self) -> float:
        """Get the age (in seconds) of the oldest call in the window."""
        if not self.call_history:
            return self.WINDOW_SECONDS  # No calls, window is "empty"
        oldest_ts = min(ts for ts, _ in self.call_history)
        return time.time() - oldest_ts
    
    def wait_for_full_reset(self):
        """
        Wait until the sliding window is completely empty (Full Reset strategy).
        
        This means waiting for the OLDEST call in our history to fall outside
        the 60-second window.
        
        Returns:
            float: Actual time waited (0 if no wait needed).
        """
        self._prune_old_calls()
        
        if not self.call_history:
            return 0.0  # No calls in window, we're clear
        
        # Find the oldest call and wait for it to fall outside the window
        oldest_ts = min(ts for ts, _ in self.call_history)
        age = time.time() - oldest_ts
        wait_time = self.WINDOW_SECONDS - age
        
        if wait_time > 0:
            current_usage = self._get_current_usage()
            print(f"   🛑 TPM Window: {current_usage:,}/{self.capacity:,} tokens in last {age:.0f}s. "
                  f"Waiting {wait_time:.1f}s for full reset...")
            wait_with_progress(int(wait_time) + 1, "TPM Full Reset")
            # After waiting, prune again - all calls should now be outside window
            self.call_history = []
        
        return max(0, wait_time)
    
    def consume(self, tokens: int):
        """
        Record token usage after a generate_content call.
        
        Args:
            tokens: Number of tokens used (from usage_metadata.total_token_count).
        """
        self.call_history.append((time.time(), tokens))
        self._prune_old_calls()
        current_usage = self._get_current_usage()
        # Debug log to track token usage
        print(f"   📊 TPM: +{tokens:,} -> {current_usage:,}/{self.capacity:,} (in 60s window)")
    
    def get_usage(self) -> tuple:
        """Get current usage stats."""
        return self._get_current_usage(), self.capacity


# Global TPM bucket instance (shared across all nodes)
# Capacity loaded from env, default 15k for Gemma models
TPM_CAPACITY = int(os.getenv("TPM_LIMIT", "15000"))
tpm_bucket = TokenBucket(capacity=TPM_CAPACITY)

# Get delay mode from environment (default: safe)
DELAY_MODE = os.getenv("DELAY_MODE", "safe").lower()

# ============================================
# SAFE MODE DELAYS (Default - Free Tier Safe)
# ============================================
SAFE_DELAYS = {
    "single_file_upload": 90,      # After each upload_file()
    "batch_upload": 120,           # After each batch of files
    "file_verification": 70,       # Between verification checks
    "single_api_call": 90,         # After cleanup, surveyor, architect
    "summarizer_batch": 120,       # After each summarizer batch
    "drafter_per_diagram": 80,     # After each diagram generation
    "on_error": 60,                # After any failed API call
}

# ============================================
# FAST MODE DELAYS (70% reduction)
# ============================================
FAST_DELAYS = {
    "single_file_upload": 27,      # 90 * 0.3
    "batch_upload": 36,            # 120 * 0.3
    "file_verification": 21,       # 70 * 0.3
    "single_api_call": 27,         # 90 * 0.3
    "summarizer_batch": 36,        # 120 * 0.3
    "drafter_per_diagram": 24,     # 80 * 0.3
    "on_error": 18,                # 60 * 0.3
}

# Select active delays based on mode
DELAYS = FAST_DELAYS if DELAY_MODE == "fast" else SAFE_DELAYS


def get_delay(delay_type: str) -> int:
    """Get delay for a specific operation type.
    
    Args:
        delay_type: One of the delay keys (e.g., 'single_file_upload')
        
    Returns:
        Delay in seconds.
    """
    return DELAYS.get(delay_type, 60)


def wait_with_progress(seconds: int, message: str = "Rate limit protection"):
    """Wait with a visual progress indicator.
    
    Args:
        seconds: Number of seconds to wait.
        message: Message to display.
    """
    if seconds <= 0:
        return
    
    print(f"⏳ {message}: waiting {seconds} seconds...")
    
    bar_width = 30
    for i in range(seconds):
        progress = int((i + 1) / seconds * bar_width)
        remaining = seconds - i - 1
        bar = "=" * progress + ">" + " " * (bar_width - progress - 1)
        sys.stdout.write(f"\r   [{bar}] {remaining}s remaining")
        sys.stdout.flush()
        time.sleep(1)
    
    sys.stdout.write("\r" + " " * 60 + "\r")  # Clear the line
    sys.stdout.flush()


def rate_limit_delay(delay_type: str, show_progress: bool = True):
    """Apply rate limiting delay.
    
    Args:
        delay_type: Type of delay to apply.
        show_progress: Whether to show progress bar.
    """
    delay = get_delay(delay_type)
    
    if show_progress:
        wait_with_progress(delay, f"Rate limit ({delay_type})")
    else:
        time.sleep(delay)


# Print mode on import
if DELAY_MODE == "fast":
    print(f"⚡ Rate limiter: FAST mode (70% reduced delays)")
else:
    print(f"🐢 Rate limiter: SAFE mode (free tier optimized)")

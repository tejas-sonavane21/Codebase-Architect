"""
Rate Limiter - Centralized Delay Configuration

Controls API call delays to stay within Gemini free tier limits.
Configure via .env: DELAY_MODE=safe|fast
"""

import os
import time
import sys
from dotenv import load_dotenv

load_dotenv()

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

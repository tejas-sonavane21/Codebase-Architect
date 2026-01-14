"""
Security Module

Redacts sensitive information from configuration files
before uploading to the LLM.
"""

import re
from typing import List, Tuple


# Patterns for sensitive data (pattern, replacement description)
SECRET_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # API Keys
    (re.compile(r'(sk-live[a-zA-Z0-9_-]+)', re.IGNORECASE), "<REDACTED_STRIPE_KEY>"),
    (re.compile(r'(sk-[a-zA-Z0-9]{32,})', re.IGNORECASE), "<REDACTED_API_KEY>"),
    (re.compile(r'(api[_-]?key\s*[=:]\s*["\']?)([a-zA-Z0-9_-]{16,})(["\']?)', re.IGNORECASE), r"\1<REDACTED>\3"),
    
    # AWS Credentials
    (re.compile(r'(AWS_ACCESS_KEY_ID\s*[=:]\s*["\']?)([A-Z0-9]{16,})(["\']?)', re.IGNORECASE), r"\1<REDACTED>\3"),
    (re.compile(r'(AWS_SECRET_ACCESS_KEY\s*[=:]\s*["\']?)([a-zA-Z0-9/+=]{32,})(["\']?)', re.IGNORECASE), r"\1<REDACTED>\3"),
    (re.compile(r'(AKIA[A-Z0-9]{12,})', re.IGNORECASE), "<REDACTED_AWS_KEY>"),
    
    # Database URLs
    (re.compile(r'(postgres(?:ql)?://[^:]+:)([^@]+)(@)', re.IGNORECASE), r"\1<REDACTED>\3"),
    (re.compile(r'(mysql://[^:]+:)([^@]+)(@)', re.IGNORECASE), r"\1<REDACTED>\3"),
    (re.compile(r'(mongodb(?:\+srv)?://[^:]+:)([^@]+)(@)', re.IGNORECASE), r"\1<REDACTED>\3"),
    (re.compile(r'(redis://[^:]+:)([^@]+)(@)', re.IGNORECASE), r"\1<REDACTED>\3"),
    
    # Generic Secrets
    (re.compile(r'(password\s*[=:]\s*["\']?)([^"\'\s]{8,})(["\']?)', re.IGNORECASE), r"\1<REDACTED>\3"),
    (re.compile(r'(secret\s*[=:]\s*["\']?)([^"\'\s]{8,})(["\']?)', re.IGNORECASE), r"\1<REDACTED>\3"),
    (re.compile(r'(token\s*[=:]\s*["\']?)([a-zA-Z0-9_-]{16,})(["\']?)', re.IGNORECASE), r"\1<REDACTED>\3"),
    
    # Private Keys
    (re.compile(r'(-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----)', re.IGNORECASE), "<REDACTED_PRIVATE_KEY_START>"),
    (re.compile(r'(-----END (?:RSA |EC |DSA )?PRIVATE KEY-----)', re.IGNORECASE), "<REDACTED_PRIVATE_KEY_END>"),
    
    # Common OAuth/API patterns
    (re.compile(r'(client_secret\s*[=:]\s*["\']?)([a-zA-Z0-9_-]{16,})(["\']?)', re.IGNORECASE), r"\1<REDACTED>\3"),
    (re.compile(r'(bearer\s+)([a-zA-Z0-9_-]{16,})', re.IGNORECASE), r"\1<REDACTED>"),
]

# Files that commonly contain secrets
SENSITIVE_FILE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "credentials*",
    "secrets*",
    "*config*.json",
    "*config*.yaml",
    "*config*.yml",
    "*.secrets",
]


def redact_secrets(content: str) -> Tuple[str, int]:
    """Redact sensitive information from content.
    
    Args:
        content: The file content to redact.
        
    Returns:
        Tuple of (redacted_content, redaction_count).
    """
    redacted = content
    count = 0
    
    for pattern, replacement in SECRET_PATTERNS:
        matches = pattern.findall(redacted)
        if matches:
            count += len(matches)
            redacted = pattern.sub(replacement, redacted)
    
    return redacted, count


def is_sensitive_file(filename: str) -> bool:
    """Check if a filename matches sensitive file patterns.
    
    Args:
        filename: The filename to check.
        
    Returns:
        True if the file might contain secrets.
    """
    import fnmatch
    
    filename_lower = filename.lower()
    
    for pattern in SENSITIVE_FILE_PATTERNS:
        if fnmatch.fnmatch(filename_lower, pattern.lower()):
            return True
    
    return False


def redact_file_content(file_path: str, content: str) -> Tuple[str, int]:
    """Redact secrets from file content, with extra caution for sensitive files.
    
    Args:
        file_path: Path to the file (for determining sensitivity).
        content: The file content.
        
    Returns:
        Tuple of (redacted_content, redaction_count).
    """
    import os
    
    filename = os.path.basename(file_path)
    
    # Always redact, but log more for sensitive files
    redacted, count = redact_secrets(content)
    
    if is_sensitive_file(filename) and count > 0:
        print(f"  🔒 Redacted {count} potential secrets in {filename}")
    
    return redacted, count

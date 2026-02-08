"""
Gemini Client - gemini_webapi Wrapper (Singleton)

Primary client for all LLM interactions using the gemini_webapi library.
Uses browser cookies for authentication and Gemini Gems for system prompts.

This module implements a singleton pattern to avoid:
- Multiple client initializations
- Multiple auto_refresh tasks
- Resource waste
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
from gemini_webapi import GeminiClient as WebClient
from utils.console import console

try:
    from loguru import logger
    logger.remove()
except ImportError:
    pass


# Load environment variables
load_dotenv()


# Module-level singleton instance
_client_instance: Optional["GeminiClient"] = None


def get_client() -> "GeminiClient":
    """
    Get the singleton GeminiClient instance.
    
    Creates the client on first call, returns existing instance on subsequent calls.
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = GeminiClient()
    return _client_instance


class GeminiClient:
    """Gemini client using gemini_webapi library (Singleton)."""
    
    # Single model for all operations
    MODEL = os.getenv("GEMINI_WEB_MODEL", "gemini-3.0-pro")
    
    # Request timing
    SAFETY_DELAY = 2  # seconds between requests
    MAX_RETRIES = 5
    BASE_WAIT = 10  # seconds for retry backoff
    
    def __init__(self):
        """Initialize the Gemini client.
        
        Reads cookies from environment variables:
        - GEMINI_SECURE_1PSID
        - GEMINI_SECURE_1PSIDTS
        
        Note: Use get_client() to get the singleton instance instead of
        instantiating this class directly.
        """
        self._client = None
        self._loop = None
        self._last_request_time = 0
        self._initialized = False
        
        # Get cookies from environment
        self._secure_1psid = os.getenv("GEMINI_SECURE_1PSID")
        self._secure_1psidts = os.getenv("GEMINI_SECURE_1PSIDTS")
        
        if not self._secure_1psid:
            raise ValueError("GEMINI_SECURE_1PSID environment variable required")
    
    async def _ensure_initialized(self):
        """Initialize the gemini_webapi client lazily."""
        if self._initialized:
            return
        
        console.status("Initializing Gemini client")
        
        # Correct initialization pattern:
        # 1. Create client with cookies
        # 2. Call init() to complete setup
        self._client = WebClient(
            self._secure_1psid,
            self._secure_1psidts,
            proxy=None
        )
        await self._client.init(
            timeout=120,  # Increased from 30s for longer API calls
            auto_close=False,
            auto_refresh=True
        )
        
        self._initialized = True
        console.status("Gemini client initialized", done=True)
    
    def _apply_safety_delay(self):
        """Apply safety delay between requests."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.SAFETY_DELAY:
                wait_time = self.SAFETY_DELAY - elapsed
                # Silent delay - no need to inform user about internal throttling
                time.sleep(wait_time)
    
    def _get_or_create_loop(self):
        """Get or create a persistent event loop."""
        try:
            # Try to get existing loop
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Loop is closed")
            return loop
        except RuntimeError:
            # Create new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    async def _generate_content_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        files: Optional[List[Path]] = None,
        model_override: Optional[str] = None,
        gem_id: Optional[str] = None,
    ) -> str:
        """Generate content asynchronously.
        
        Args:
            prompt: The user prompt.
            system_prompt: System instructions (used only if gem_id not provided).
            files: Optional list of file paths to include.
            model_override: Optional model override.
            gem_id: Gem ID for system prompt (preferred over inline).
            
        Returns:
            Generated text content.
        """
        await self._ensure_initialized()
        
        model = model_override or self.MODEL
        
        # Build prompt - use gem_id if available, otherwise inline system prompt
        if gem_id:
            full_prompt = prompt
        elif system_prompt:
            full_prompt = f"<INSTRUCTIONS>\n{system_prompt}\n</INSTRUCTIONS>\n\n<USER_REQUEST>\n{prompt}\n</USER_REQUEST>"
        else:
            full_prompt = prompt
        
        # Retry logic
        for attempt in range(self.MAX_RETRIES):
            try:
                if gem_id:
                    response = await self._client.generate_content(
                        full_prompt,
                        files=files,
                        model=model,
                        gem=gem_id
                    )
                else:
                    response = await self._client.generate_content(
                        full_prompt,
                        files=files,
                        model=model
                    )
                return response.text
            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise RuntimeError(f"Gemini API failed after {self.MAX_RETRIES} retries: {e}")
                
                wait_time = self.BASE_WAIT * (2 ** attempt)
                from utils.console import console
                console.debug(f"API error: {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        return ""
    
    def generate_content(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        file_uris: Optional[List] = None,
        temperature: float = 0.7,  # Ignored - not supported by web API
        model_override: Optional[str] = None,
        gem_id: Optional[str] = None,
    ) -> str:
        """Generate content (synchronous wrapper).
        
        Args:
            prompt: The user prompt.
            system_prompt: System instructions (used if gem_id not provided).
            file_uris: List of file references (dicts with 'local_path' or 'uri').
            temperature: Ignored (not supported by web API).
            model_override: Optional model override.
            gem_id: Gem ID for system prompt (preferred).
            
        Returns:
            Generated text content.
        """
        self._apply_safety_delay()
        
        # Convert file_uris to Path objects
        files = None
        if file_uris:
            files = []
            for ref in file_uris:
                if isinstance(ref, dict):
                    path = ref.get("local_path") or ref.get("uri")
                elif isinstance(ref, str):
                    path = ref
                else:
                    continue
                
                if path and os.path.exists(path):
                    files.append(Path(path))
        
        # Use persistent event loop
        if not self._loop or self._loop.is_closed():
            self._loop = self._get_or_create_loop()
        
        result = self._loop.run_until_complete(
            self._generate_content_async(
                prompt=prompt,
                system_prompt=system_prompt,
                files=files,
                model_override=model_override,
                gem_id=gem_id,
            )
        )
        
        self._last_request_time = time.time()
        return result
    
    # ==========================================================================
    # File Operations (Local Path Management)
    # ==========================================================================
    
    MIME_TYPES = {
        ".py": "text/x-python",
        ".js": "application/javascript",
        ".ts": "application/typescript",
        ".tsx": "text/tsx",
        ".jsx": "text/jsx",
        ".json": "application/json",
        ".xml": "application/xml",
        ".html": "text/html",
        ".css": "text/css",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".toml": "text/plain",
        ".rs": "text/x-rust",
        ".go": "text/x-go",
        ".java": "text/x-java",
        ".c": "text/x-c",
        ".cpp": "text/x-c++",
        ".h": "text/x-c",
        ".hpp": "text/x-c++",
    }
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type for a file."""
        ext = Path(file_path).suffix.lower()
        return self.MIME_TYPES.get(ext, "text/plain")
    
    def prepare_file(self, file_path: str) -> dict:
        """Prepare a file reference for use in prompts.
        
        Args:
            file_path: Path to the local file.
            
        Returns:
            Dict with 'uri', 'local_path', and 'mime_type'.
        """
        return {
            "uri": file_path,
            "local_path": file_path,
            "mime_type": self._get_mime_type(file_path),
        }
    
    def cleanup_all_files(self) -> int:
        """No-op - local files don't need cleanup."""
        return 0


# Backwards compatibility - nodes can still do GeminiClient() but 
# should prefer get_client()

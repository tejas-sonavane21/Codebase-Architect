"""
Gemini API Client Wrapper

Handles Gemini 2.5 Flash interactions with exponential backoff
and Files API for code context uploads.
"""

import os
import time
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()


class GeminiClient:
    """Wrapper for Google Gemini API with retry logic."""
    
    # Model from .env with fallback default
    MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite-preview-09-2025")
    MAX_RETRIES = 3
    BASE_WAIT = 60 # seconds
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini client.
        
        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found. Set it in .env or pass directly.")
        
        self.client = genai.Client(api_key=self.api_key)
    
    def generate_content(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        file_uris: Optional[list] = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate content with exponential backoff on failure.
        
        Args:
            prompt: The user prompt.
            system_prompt: Optional system instructions.
            file_uris: Optional list of uploaded file URIs for context.
            temperature: Sampling temperature.
            
        Returns:
            Generated text content.
        """
        # Build content parts
        contents = []
        
        # Add file references if provided
        if file_uris:
            for file_ref in file_uris:
                # Support both dict format {uri, mime_type} and string format (backward compatible)
                if isinstance(file_ref, dict):
                    uri = file_ref["uri"]
                    mime = file_ref.get("mime_type", "text/plain")
                else:
                    uri = file_ref
                    mime = "text/plain"  # Fallback for legacy string format
                
                contents.append(types.Part.from_uri(file_uri=uri, mime_type=mime))
        
        # Add the text prompt
        contents.append(prompt)
        
        # Build config
        config = types.GenerateContentConfig(
            temperature=temperature,
        )
        if system_prompt:
            config.system_instruction = system_prompt
        
        # Retry with exponential backoff
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=self.MODEL,
                    contents=contents,
                    config=config,
                )
                return response.text
            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise RuntimeError(f"Gemini API failed after {self.MAX_RETRIES} retries: {e}")
                
                wait_time = self.BASE_WAIT * (2 ** attempt)
                print(f"  ⚠ Gemini API error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        return ""  # Should never reach here
    
    # MIME type mapping for code files
    MIME_TYPES = {
        # Python
        ".py": "text/x-python",
        ".pyw": "text/x-python",
        # JavaScript/TypeScript
        ".js": "text/javascript",
        ".jsx": "text/javascript",
        ".ts": "text/typescript",
        ".tsx": "text/typescript",
        ".mjs": "text/javascript",
        ".cjs": "text/javascript",
        # Web
        ".html": "text/html",
        ".htm": "text/html",
        ".css": "text/css",
        ".scss": "text/css",
        ".sass": "text/css",
        ".less": "text/css",
        # Data/Config
        ".json": "application/json",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".toml": "text/plain",
        ".xml": "text/xml",
        ".ini": "text/plain",
        ".cfg": "text/plain",
        ".conf": "text/plain",
        # Other languages
        ".java": "text/x-java-source",
        ".go": "text/x-go",
        ".rs": "text/x-rust",
        ".c": "text/x-c",
        ".cpp": "text/x-c++",
        ".h": "text/x-c",
        ".hpp": "text/x-c++",
        ".cs": "text/x-csharp",
        ".rb": "text/x-ruby",
        ".php": "text/x-php",
        ".swift": "text/x-swift",
        ".kt": "text/x-kotlin",
        ".scala": "text/x-scala",
        ".vue": "text/html",
        ".svelte": "text/html",
        # Shell
        ".sh": "text/x-shellscript",
        ".bash": "text/x-shellscript",
        ".zsh": "text/x-shellscript",
        ".ps1": "text/plain",
        # Docs
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".rst": "text/plain",
        # Docker/Build
        "dockerfile": "text/plain",
        ".dockerfile": "text/plain",
    }
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type for a file based on extension.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            MIME type string, defaults to text/plain.
        """
        filename = os.path.basename(file_path).lower()
        ext = os.path.splitext(filename)[1].lower()
        
        # Check extension first
        if ext in self.MIME_TYPES:
            return self.MIME_TYPES[ext]
        
        # Check full filename (for Dockerfile, etc.)
        if filename in self.MIME_TYPES:
            return self.MIME_TYPES[filename]
        
        # Default to text/plain for unknown types
        return "text/plain"
    
    def upload_file(self, file_path: str, display_name: Optional[str] = None) -> str:
        """Upload a file to Gemini Files API.
        
        Args:
            file_path: Path to the file to upload.
            display_name: Optional display name for the file.
            
        Returns:
            Dict with 'uri' and 'mime_type' for use in prompts.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        name = display_name or os.path.basename(file_path)
        mime_type = self._get_mime_type(file_path)
        
        for attempt in range(self.MAX_RETRIES):
            try:
                uploaded_file = self.client.files.upload(
                    file=file_path,
                    config=types.UploadFileConfig(
                        display_name=name,
                        mime_type=mime_type,
                    ),
                )
                # Return dict with both URI and MIME type
                return {"uri": uploaded_file.uri, "mime_type": mime_type}
            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise RuntimeError(f"File upload failed after {self.MAX_RETRIES} retries: {e}")
                
                wait_time = self.BASE_WAIT * (2 ** attempt)
                print(f"  ⚠ Upload error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        return {"uri": "", "mime_type": "text/plain"}  # Should never reach here
    
    def get_file(self, file_uri: str):
        """Get file info from Gemini API.
        
        Args:
            file_uri: The file URI to check.
            
        Returns:
            File object with state info.
        """
        # Extract file name from URI (format: files/xxx or https://.../files/xxx)
        file_name = file_uri.split("/")[-1]
        if not file_name.startswith("files/"):
            file_name = f"files/{file_name}"
        
        return self.client.files.get(name=file_name)
    
    def wait_for_file_active(self, file_uri: str, timeout: int = 60) -> bool:
        """Wait for a file to become ACTIVE.
        
        Args:
            file_uri: The file URI to check.
            timeout: Maximum seconds to wait.
            
        Returns:
            True if file is ACTIVE, False if timeout or FAILED.
        """
        file_name = file_uri.split("/")[-1]
        if not file_name.startswith("files/"):
            file_name = f"files/{file_name}"
        
        start_time = time.time()
        poll_interval = 2  # seconds
        
        while time.time() - start_time < timeout:
            try:
                file_info = self.client.files.get(name=file_name)
                state = getattr(file_info, 'state', None)
                
                # State can be a string or enum
                state_str = str(state).upper() if state else "UNKNOWN"
                
                if "ACTIVE" in state_str:
                    return True
                elif "FAILED" in state_str:
                    print(f"  ⚠ File {file_name} failed processing")
                    return False
                elif "PROCESSING" in state_str:
                    time.sleep(poll_interval)
                else:
                    # Unknown state, assume it's ready if we can get file info
                    return True
                    
            except Exception as e:
                # If we can't get file info, wait and retry
                time.sleep(poll_interval)
        
        print(f"  ⚠ Timeout waiting for file {file_name} to become ACTIVE")
        return False
    
    def verify_files_ready(self, file_uris: list, timeout_per_file: int = 30) -> list:
        """Verify all files are ready (ACTIVE state).
        
        Args:
            file_uris: List of file URIs to check.
            timeout_per_file: Seconds to wait per file.
            
        Returns:
            List of ready file URIs.
        """
        ready_uris = []
        
        print(f"   🔍 Verifying {len(file_uris)} files are ready...")
        
        for uri in file_uris:
            if self.wait_for_file_active(uri, timeout=timeout_per_file):
                ready_uris.append(uri)
        
        if len(ready_uris) < len(file_uris):
            failed_count = len(file_uris) - len(ready_uris)
            print(f"   ⚠ {failed_count} files failed verification")
        else:
            print(f"   ✓ All {len(ready_uris)} files verified as ACTIVE")
        
        return ready_uris
    
    def delete_file(self, file_uri: str) -> bool:
        """Delete an uploaded file.
        
        Args:
            file_uri: URI of the file to delete.
            
        Returns:
            True if deletion succeeded.
        """
        try:
            # Extract file name from URI
            file_name = file_uri.split("/")[-1]
            self.client.files.delete(name=file_name)
            return True
        except Exception as e:
            print(f"  ⚠ Failed to delete file {file_uri}: {e}")
            return False
    
    def list_files(self) -> list:
        """List all files on Gemini server.
        
        Returns:
            List of file objects.
        """
        try:
            return list(self.client.files.list())
        except Exception as e:
            print(f"  ⚠ Failed to list files: {e}")
            return []
    
    def cleanup_all_files(self) -> int:
        """Delete all files from Gemini server.
        
        Returns:
            Count of files deleted.
        """
        files = self.list_files()
        deleted_count = 0
        
        for f in files:
            try:
                self.client.files.delete(name=f.name)
                deleted_count += 1
            except Exception as e:
                print(f"  ⚠ Failed to delete {f.name}: {e}")
        
        return deleted_count

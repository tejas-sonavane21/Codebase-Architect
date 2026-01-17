"""
Node 3: The Uploader

Uploads ALL files selected by Gemini (Surveyor) to Gemini Files API.
NO FIXED LIMIT - uploads in smart batches to manage rate limits.
Also uploads project_map.txt for Gemini context.
"""

import os
import time
from typing import List, Optional, Dict
from pocketflow import Node

from utils.gemini_client import GeminiClient
from utils.security import redact_file_content
from utils.rate_limiter import rate_limit_delay, get_delay


class UploaderNode(Node):
    """Uploader node that sends ALL selected files to Gemini Files API in batches."""
    
    # Batch size for uploads (to manage rate limits)
    # Gemini allows many files, but we batch to avoid hitting rate limits
    BATCH_SIZE = 5
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
    
    def prep(self, shared: dict) -> dict:
        """Gather ALL files to upload based on Surveyor's config.
        
        Args:
            shared: Shared store with 'upload_config' and 'clone_path'.
            
        Returns:
            Dict with file list, clone path, and context files.
        """
        upload_config = shared.get("upload_config", {})
        clone_path = shared.get("clone_path")
        clone_dir = shared.get("clone_dir")
        
        if not clone_path or not os.path.exists(clone_path):
            raise ValueError("Invalid 'clone_path' in shared store")
        
        include_paths = upload_config.get("include_paths", [])
        exclude_patterns = upload_config.get("exclude_patterns", [])
        
        # Initialize client
        self.client = GeminiClient()
        
        # Clean up any existing files on Gemini server before uploading
        print("🧹 Cleaning up existing files on Gemini server...")
        deleted = self.client.cleanup_all_files()
        if deleted > 0:
            print(f"   ✓ Deleted {deleted} old files")
            # Apply rate limit delay after cleanup API call
            rate_limit_delay("single_api_call")
        else:
            print("   ✓ No old files to delete")
        
        # Gather context files first (project_map.txt, file_inventory.json)
        context_files = []
        
        project_map_file = shared.get("project_map_file")
        if project_map_file and os.path.exists(project_map_file):
            context_files.append({
                "path": project_map_file,
                "display_name": "project_map.txt",
                "is_context": True,
            })
        
        inventory_file = shared.get("inventory_file")
        if inventory_file and os.path.exists(inventory_file):
            context_files.append({
                "path": inventory_file,
                "display_name": "file_inventory.json",
                "is_context": True,
            })
        
        # Find all source files based on Surveyor's selection
        source_files = []
        
        for include_path in include_paths:
            full_path = os.path.join(clone_path, include_path)
            
            if os.path.isfile(full_path):
                source_files.append({
                    "path": full_path,
                    "display_name": include_path,
                    "is_context": False,
                })
            elif os.path.isdir(full_path):
                # Walk the directory
                for root, _, files in os.walk(full_path):
                    # Check exclude patterns
                    rel_root = os.path.relpath(root, clone_path)
                    if self._should_exclude(rel_root, exclude_patterns):
                        continue
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, clone_path)
                        
                        # Skip binary files
                        if not self._is_text_file(file):
                            continue
                        
                        source_files.append({
                            "path": file_path,
                            "display_name": rel_path,
                            "is_context": False,
                        })
        
        # If Surveyor didn't specify paths, use file_inventory to find text files
        if not source_files:
            print("   ⚠ No specific paths from Surveyor, using file inventory...")
            file_inventory = shared.get("file_inventory", [])
            
            for file_info in file_inventory:
                if file_info.get("type") == "text":
                    file_path = os.path.join(clone_path, file_info["path"])
                    if os.path.exists(file_path):
                        source_files.append({
                            "path": file_path,
                            "display_name": file_info["path"],
                            "is_context": False,
                        })
        
        # Combine context files (uploaded first) + source files
        all_files = context_files + source_files
        
        print(f"   📚 Context files: {len(context_files)}")
        print(f"   📄 Source files: {len(source_files)}")
        print(f"   📦 Total to upload: {len(all_files)}")
        
        return {
            "files": all_files,
            "clone_path": clone_path,
            "total_count": len(all_files),
        }
    
    def _should_exclude(self, path: str, patterns: List[str]) -> bool:
        """Check if path should be excluded."""
        import fnmatch
        path_lower = path.lower()
        
        # Always exclude these
        always_exclude = ['node_modules', '.git', '__pycache__', 'venv', '.venv', 'dist', 'build']
        if any(excl in path_lower for excl in always_exclude):
            return True
        
        # Check user-defined patterns
        for pattern in patterns:
            if fnmatch.fnmatch(path_lower, pattern.lower()):
                return True
        
        return False
    
    def _is_text_file(self, filename: str) -> bool:
        """Check if file is a text file (not binary)."""
        binary_extensions = {
            ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".o", ".a",
            ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg", ".webp",
            ".mp3", ".mp4", ".wav", ".avi", ".mov",
            ".zip", ".tar", ".gz", ".rar", ".7z",
            ".pdf", ".doc", ".docx", ".xls", ".xlsx",
            ".ttf", ".otf", ".woff", ".woff2",
            ".db", ".sqlite",
        }
        ext = os.path.splitext(filename)[1].lower()
        return ext not in binary_extensions
    
    def exec(self, prep_res: dict) -> dict:
        """Upload ALL files to Gemini in smart batches.
        
        Args:
            prep_res: Dict with 'files', 'clone_path', 'total_count'.
            
        Returns:
            Dict with file URIs and manifest.
        """
        files = prep_res["files"]
        clone_path = prep_res["clone_path"]
        total = prep_res["total_count"]
        
        if not files:
            print("   ⚠ No files to upload!")
            return {"file_uris": [], "manifest": "", "context_uris": []}
        
        print(f"📤 Uploading {total} files to Gemini (in batches of {self.BATCH_SIZE})...")
        
        file_uris = []
        context_uris = []
        manifest_lines = ["# Uploaded Files Manifest", ""]
        
        # Process in batches
        for batch_start in range(0, len(files), self.BATCH_SIZE):
            batch = files[batch_start:batch_start + self.BATCH_SIZE]
            batch_num = (batch_start // self.BATCH_SIZE) + 1
            total_batches = (len(files) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            
            print(f"   Batch {batch_num}/{total_batches}...")
            
            for file_info in batch:
                file_path = file_info["path"]
                display_name = file_info["display_name"]
                is_context = file_info.get("is_context", False)
                
                try:
                    # Read and optionally redact content
                    if not is_context:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        
                        redacted_content, redact_count = redact_file_content(file_path, content)
                        
                        # Create temp file with redacted content
                        temp_path = file_path + ".redacted"
                        with open(temp_path, "w", encoding="utf-8") as f:
                            f.write(redacted_content)
                        
                        upload_path = temp_path
                    else:
                        upload_path = file_path
                    
                    # Upload the file - now returns dict with uri and mime_type
                    upload_result = self.client.upload_file(upload_path, display_name=display_name)
                    
                    file_entry = {
                        "path": display_name, 
                        "uri": upload_result["uri"], 
                        "mime_type": upload_result["mime_type"],
                        "is_context": is_context
                    }
                    file_uris.append(file_entry)
                    
                    if is_context:
                        context_uris.append(upload_result["uri"])
                    
                    # Add to manifest
                    manifest_lines.append(f"## {display_name}")
                    manifest_lines.append(f"- URI: {upload_result['uri']}")
                    manifest_lines.append(f"- MIME: {upload_result['mime_type']}")
                    manifest_lines.append(f"- Type: {'Context' if is_context else 'Source'}")
                    manifest_lines.append("")
                    
                    # Clean up temp file
                    if not is_context and os.path.exists(file_path + ".redacted"):
                        os.remove(file_path + ".redacted")
                    
                    print(f"      ✓ {display_name}")
                    
                    # Rate limit delay between individual file uploads
                    rate_limit_delay("single_file_upload")
                    
                except Exception as e:
                    print(f"      ✗ {display_name}: {e}")
                    # Delay after error
                    rate_limit_delay("on_error")
            
            # Rate limit delay between batches
            if batch_start + self.BATCH_SIZE < len(files):
                rate_limit_delay("batch_upload")
        
        # Create manifest content
        manifest_content = "\n".join(manifest_lines)
        
        return {
            "file_uris": file_uris,
            "context_uris": context_uris,
            "manifest": manifest_content,
        }
    
    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        """Store uploaded file info.
        
        Args:
            shared: Shared store.
            prep_res: Prep result.
            exec_res: Upload results with URIs and manifest.
            
        Returns:
            Action string for flow.
        """
        file_uris = exec_res["file_uris"]
        context_uris = exec_res.get("context_uris", [])
        
        if not file_uris:
            raise ValueError("No files were uploaded. Check UploaderNode.")
        
        # Strategic 3-file verification (first, middle, last)
        # Instead of verifying all N files, we check only 3 strategic files
        # If the last uploaded file is ACTIVE, earlier files are almost certainly ACTIVE too
        all_uris = [f["uri"] for f in file_uris]
        
        if len(all_uris) >= 3:
            # Check in reverse order: last -> middle -> first
            strategic_uris = [
                all_uris[-1],                    # Last file
                all_uris[len(all_uris) // 2],    # Middle file
                all_uris[0],                     # First file
            ]
            print(f"   🔍 Verifying 3 strategic files (of {len(all_uris)})...")
        else:
            strategic_uris = all_uris
            print(f"   🔍 Verifying {len(all_uris)} files...")
        
        verified_count = 0
        for uri in strategic_uris:
            if self.client.wait_for_file_active(uri, timeout=60):
                verified_count += 1
            # Delay between verification checks
            if uri != strategic_uris[-1]:  # Don't delay after last check
                rate_limit_delay("file_verification")
        
        if verified_count == 0:
            raise ValueError("No uploaded files became ACTIVE. Upload may have failed.")
        
        # If strategic files are active, assume all are active
        verified_uris = all_uris if verified_count == len(strategic_uris) else []
        
        # Filter file_uris to only include verified ones
        verified_file_uris = [f for f in file_uris if f["uri"] in verified_uris]
        
        shared["file_uris"] = verified_file_uris
        shared["context_uris"] = [uri for uri in context_uris if uri in verified_uris]
        shared["manifest"] = exec_res["manifest"]
        
        # Create uri_list with MIME types for generate_content
        shared["uri_list"] = [{"uri": f["uri"], "mime_type": f["mime_type"]} for f in verified_file_uris]
        
        # Separate context URIs for prompts (also with MIME types)
        shared["source_uri_list"] = [
            {"uri": f["uri"], "mime_type": f["mime_type"]} 
            for f in verified_file_uris 
            if not f.get("is_context")
        ]
        
        source_count = len([f for f in verified_file_uris if not f.get("is_context")])
        context_count = len([f for f in verified_file_uris if f.get("is_context")])
        
        print(f"✓ Verified {source_count} source files + {context_count} context files ready on Gemini")
        
        return "default"

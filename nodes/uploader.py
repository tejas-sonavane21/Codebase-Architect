"""
Node 3: The Uploader

Prepares local file references for Gemini processing.
No actual uploads - gemini_webapi handles files directly via local paths.
"""

import os
from typing import List, Optional, Dict
from pathlib import Path
from pocketflow import Node

from utils.console import console
from utils.gemini_client import get_client
from utils.security import redact_file_content


class UploaderNode(Node):
    """Uploader node that prepares local file references."""
    
    # Binary file extensions to skip
    BINARY_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".zip", ".tar", ".gz", ".rar", ".7z",
        ".mp3", ".mp4", ".wav", ".avi", ".mov",
        ".exe", ".dll", ".so", ".dylib",
        ".pyc", ".pyo", ".class", ".o", ".obj",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".db", ".sqlite", ".sqlite3",
    }
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
    
    def _is_text_file(self, file_path: str) -> bool:
        """Check if file is a text file (not binary)."""
        ext = Path(file_path).suffix.lower()
        return ext not in self.BINARY_EXTENSIONS
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type for a file."""
        mime_types = {
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
        }
        ext = Path(file_path).suffix.lower()
        return mime_types.get(ext, "text/plain")
    
    def prep(self, shared: dict) -> dict:
        """Gather all files to prepare based on Surveyor's config."""
        upload_config = shared.get("upload_config", {})
        clone_path = shared.get("clone_path")
        clone_dir = shared.get("clone_dir")
        
        if not clone_path or not os.path.exists(clone_path):
            raise ValueError("Invalid 'clone_path' in shared store")
        
        include_paths = upload_config.get("include_paths", [])
        
        # Initialize client
        self.client = get_client()
        
        # Gather context files (project_map.txt, file_inventory.json)
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
        
        # Find all source files
        source_files = []
        skipped_binary = 0
        
        for include_path in include_paths:
            full_path = os.path.join(clone_path, include_path)
            
            if os.path.isfile(full_path):
                if not self._is_text_file(include_path):
                    skipped_binary += 1
                    continue
                
                source_files.append({
                    "path": full_path,
                    "display_name": include_path,
                    "is_context": False,
                })
            elif os.path.isdir(full_path):
                for root, _, files in os.walk(full_path):
                    for file in files:
                        if not self._is_text_file(file):
                            skipped_binary += 1
                            continue
                        
                        file_full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_full_path, clone_path)
                        
                        source_files.append({
                            "path": file_full_path,
                            "display_name": rel_path,
                            "is_context": False,
                        })
        
        total_files = len(context_files) + len(source_files)
        console.status(f"Preparing {total_files} files", done=True)
        if skipped_binary > 0:
            console.item(f"Skipped {skipped_binary} binary files", indent=2)
        
        return {
            "context_files": context_files,
            "source_files": source_files,
            "clone_path": clone_path,
            "clone_dir": clone_dir,
            "analysis": upload_config.get("analysis", ""),
        }
    
    def exec(self, prep_res: dict) -> dict:
        """Prepare file references (no upload needed for gemini_webapi)."""
        context_files = prep_res["context_files"]
        source_files = prep_res["source_files"]
        
        file_uris = []
        
        # Prepare context files
        for file_info in context_files:
            path = file_info["path"]
            file_uris.append({
                "uri": path,
                "local_path": path,
                "path": file_info["display_name"],
                "mime_type": self._get_mime_type(path),
                "is_context": True,
            })
        
        # Prepare source files
        for file_info in source_files:
            path = file_info["path"]
            file_uris.append({
                "uri": path,
                "local_path": path,
                "path": file_info["display_name"],
                "mime_type": self._get_mime_type(path),
                "is_context": False,
            })
        
        console.item(f"Prepared {len(file_uris)} file references", indent=1)
        
        return {
            "file_uris": file_uris,
            "success": True,
            "analysis": prep_res["analysis"],
        }
    
    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        """Store file references in shared state."""
        file_uris = exec_res["file_uris"]
        
        # Store in shared
        shared["file_uris"] = file_uris
        
        # Separate lists for different use cases
        shared["uri_list"] = [
            {"uri": f["uri"], "mime_type": f["mime_type"]}
            for f in file_uris
        ]
        shared["source_uri_list"] = [
            {"uri": f["uri"], "mime_type": f["mime_type"]}
            for f in file_uris if not f.get("is_context")
        ]
        
        # Store analysis
        shared["project_analysis"] = exec_res.get("analysis", "")
        
        console.status(f"{len(file_uris)} files ready for processing", done=True)
        return "default"

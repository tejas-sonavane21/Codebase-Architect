"""
Node 1: The Scout

Clones a GitHub repository and creates a COMPLETE project map.
Maps ALL files - lets Gemini (Surveyor) decide what's important.
Only collapses known junk directories (node_modules, .git, etc.)
"""

import os
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, List
from pocketflow import Node

from utils.security import redact_file_content
from utils.console import console


class ScoutNode(Node):
    """Scout node that clones and maps a repository completely."""
    
    # Folders to always collapse (these are ALWAYS junk - no source code)
    # This is kept minimal - only absolute known junk folders
    ALWAYS_COLLAPSE = {
        "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
        ".next", ".nuxt", ".cache", ".pytest_cache", ".mypy_cache",
        ".tox", ".eggs", "*.egg-info",
    }
    
    # Binary extensions that CANNOT be uploaded to Gemini (not text)
    # These are skipped because they literally can't be processed as text
    BINARY_EXTENSIONS = {
        ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".o", ".a",
        ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg", ".webp", ".bmp",
        ".mp3", ".mp4", ".wav", ".avi", ".mov", ".flv", ".wmv", ".webm",
        ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
        ".db", ".sqlite", ".sqlite3",
    }
    
    def __init__(self, max_retries: int = 1, wait: int = 0):
        super().__init__(max_retries=max_retries, wait=wait)
        self.clone_dir: Optional[str] = None
    
    def prep(self, shared: dict) -> dict:
        """Clone the repository.
        
        Args:
            shared: Shared store with 'repo_url' key.
            
        Returns:
            Dict with clone path.
        """
        import git
        
        repo_url = shared.get("repo_url")
        if not repo_url:
            raise ValueError("No 'repo_url' in shared store")
        
        # Get project root directory (where main.py is located)
        project_root = shared.get("project_root", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Create cloned_repo directory in project root
        self.clone_dir = os.path.join(project_root, "cloned_repo")
        
        # Clean up existing clone if present
        if os.path.exists(self.clone_dir):
            console.debug(f"Removing previous clone: {self.clone_dir}")
            # Handle Windows .git read-only files
            def remove_readonly(func, path, excinfo):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(self.clone_dir, onerror=remove_readonly)
        
        os.makedirs(self.clone_dir, exist_ok=True)
        clone_path = os.path.join(self.clone_dir, "repo")
        
        console.status(f"Cloning repository")
        console.debug(f"URL: {repo_url}")
        
        try:
            git.Repo.clone_from(repo_url, clone_path, depth=1)
            console.status("Repository cloned", done=True)
        except Exception as e:
            shutil.rmtree(self.clone_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to clone repository: {e}")
        
        return {"clone_path": clone_path}
    
    def exec(self, prep_res: dict) -> Dict:
        """Scan and map the ENTIRE directory tree.
        
        Args:
            prep_res: Result from prep with 'clone_path'.
            
        Returns:
            Dict with project_map (text) and file_inventory (structured).
        """
        clone_path = prep_res["clone_path"]
        
        console.section("PHASE 1: Project Analysis")
        console.status("Scanning project structure")
        
        # Create both a readable map AND a structured inventory
        map_lines = []
        file_inventory = []
        
        self._scan_directory(
            Path(clone_path), 
            map_lines, 
            file_inventory,
            depth=0, 
            base_path=Path(clone_path)
        )
        
        project_map = "\n".join(map_lines)
        
        # Count stats
        text_files = [f for f in file_inventory if f["type"] == "text"]
        binary_files = [f for f in file_inventory if f["type"] == "binary"]
        collapsed_dirs = [f for f in file_inventory if f["type"] == "collapsed_dir"]
        
        console.status("Scan complete", done=True)
        console.item(f"{len(text_files)} text files")
        console.item(f"{len(binary_files)} binary (skipped)")
        console.item(f"{len(collapsed_dirs)} junk dirs collapsed")
        
        return {
            "project_map": project_map,
            "file_inventory": file_inventory,
            "stats": {
                "text_files": len(text_files),
                "binary_files": len(binary_files),
                "collapsed_dirs": len(collapsed_dirs),
            }
        }
    
    def _scan_directory(
        self, 
        path: Path, 
        map_lines: list,
        file_inventory: list,
        depth: int, 
        base_path: Path
    ) -> int:
        """Recursively scan a directory - map EVERYTHING.
        
        Args:
            path: Current directory path.
            map_lines: List to append output lines to.
            file_inventory: List to append file info dicts to.
            depth: Current depth for indentation.
            base_path: Root path for relative paths.
            
        Returns:
            Total file count in this directory (recursive).
        """
        indent = "  " * depth
        dir_name = path.name
        
        # Check if this is a junk directory to collapse
        if dir_name.lower() in self.ALWAYS_COLLAPSE or dir_name.startswith("."):
            # Still collapse known junk
            file_count = self._count_files(path)
            map_lines.append(f"{indent}[DIR: {dir_name} - {file_count} files]")
            file_inventory.append({
                "type": "collapsed_dir",
                "name": dir_name,
                "path": str(path.relative_to(base_path)),
                "file_count": file_count,
            })
            return file_count
        
        # Get directory contents
        try:
            contents = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            map_lines.append(f"{indent}[DIR: {dir_name} - ACCESS DENIED]")
            return 0
        
        # Separate files and directories
        files = [f for f in contents if f.is_file()]
        dirs = [d for d in contents if d.is_dir()]
        
        # Add directory header
        if depth > 0:
            map_lines.append(f"{indent}{dir_name}/")
        
        total_files = 0
        
        # List ALL files (but mark binary vs text)
        for f in files:
            rel_path = str(f.relative_to(base_path))
            ext = f.suffix.lower()
            
            if ext in self.BINARY_EXTENSIONS:
                # Binary files - still list but mark as binary
                map_lines.append(f"{indent}  {f.name} [BINARY]")
                file_inventory.append({
                    "type": "binary",
                    "name": f.name,
                    "path": rel_path,
                    "extension": ext,
                    "size_bytes": f.stat().st_size if f.exists() else 0,
                })
            else:
                # Text files - these are candidates for upload
                map_lines.append(f"{indent}  {f.name}")
                file_inventory.append({
                    "type": "text",
                    "name": f.name,
                    "path": rel_path,
                    "extension": ext,
                    "size_bytes": f.stat().st_size if f.exists() else 0,
                })
            total_files += 1
        
        # Recurse into subdirectories
        for d in dirs:
            total_files += self._scan_directory(d, map_lines, file_inventory, depth + 1, base_path)
        
        return total_files
    
    def _count_files(self, path: Path) -> int:
        """Count all files in a directory recursively."""
        count = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    count += 1
        except PermissionError:
            pass
        return count
    
    def post(self, shared: dict, prep_res: dict, exec_res: Dict) -> str:
        """Store the project map and clone path.
        
        Args:
            shared: Shared store.
            prep_res: Prep result with clone_path.
            exec_res: Dict with project_map, file_inventory, stats.
            
        Returns:
            Action string for flow.
        """
        shared["project_map"] = exec_res["project_map"]
        shared["file_inventory"] = exec_res["file_inventory"]
        shared["project_stats"] = exec_res["stats"]
        shared["clone_path"] = prep_res["clone_path"]
        shared["clone_dir"] = self.clone_dir
        
        # Save project map to file (for Gemini context)
        map_file = os.path.join(self.clone_dir, "project_map.txt")
        with open(map_file, "w", encoding="utf-8") as f:
            f.write(exec_res["project_map"])
        shared["project_map_file"] = map_file
        
        # Save structured inventory as JSON (for programmatic access)
        inventory_file = os.path.join(self.clone_dir, "file_inventory.json")
        with open(inventory_file, "w", encoding="utf-8") as f:
            json.dump({
                "stats": exec_res["stats"],
                "files": exec_res["file_inventory"],
            }, f, indent=2)
        shared["inventory_file"] = inventory_file
        
        console.debug(f"Project map saved: {map_file}")
        console.debug(f"Inventory saved: {inventory_file}")
        
        return "default"
    
    def cleanup(self, shared: dict):
        """Clean up cloned repository.
        
        Handles Windows .git folder by removing read-only attributes.
        """
        clone_dir = shared.get("clone_dir")
        if clone_dir and os.path.exists(clone_dir):
            # On Windows, .git folder files are read-only and need special handling
            def remove_readonly(func, path, excinfo):
                """Error handler that removes read-only attribute and retries."""
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
            
            try:
                shutil.rmtree(clone_dir, onerror=remove_readonly)
                console.debug("Cleaned up cloned repository")
            except Exception as e:
                console.debug(f"Cleanup warning: {e}")


"""
Node: The Summarizer

Context Distillation node that builds a semantic knowledge base (codebase_knowledge.xml)
using a Map-Reduce approach. Processes files in small batches to avoid token limits.
"""

import os
import json
import time
from typing import Optional, List, Dict, Tuple
from pocketflow import Node

from utils.gemini_client import GeminiClient
from utils.rate_limiter import rate_limit_delay, get_delay


# Threshold for keeping full content vs summarizing
SMALL_FILE_THRESHOLD = 50  # lines

# Batch configuration
BATCH_SIZE = 2  # files per batch (excluding summary)

from utils.prompts import get_prompt

# Summarizer prompts are now managed centrally in utils/prompts.py
# Use get_prompt("summarizer_pass1", model) or get_prompt("summarizer_pass2", model)


class SummarizerNode(Node):
    """Summarizer node that builds codebase_knowledge.xml using Map-Reduce."""
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
        self.knowledge_xml: str = ""
        self.project_name: str = "Unknown"
    
    def prep(self, shared: dict) -> dict:
        """Prepare file list and initialize knowledge base.
        
        Args:
            shared: Shared store with file URIs and inventory.
            
        Returns:
            Dict with files to process and their metadata.
        """
        self.client = GeminiClient()
        
        # Get file inventory for metadata (line counts, etc.)
        inventory_file = shared.get("inventory_file")
        file_inventory = {}
        if inventory_file and os.path.exists(inventory_file):
            with open(inventory_file, "r", encoding="utf-8") as f:
                inventory_data = json.load(f)
                for item in inventory_data.get("files", []):
                    file_inventory[item["path"]] = item
        
        # Get uploaded file URIs with MIME types
        file_uris = shared.get("file_uris", [])
        
        # Filter to only source files (not context files like project_map.txt)
        source_files = [f for f in file_uris if not f.get("is_context", False)]
        
        # Get project name from inventory or clone path
        self.project_name = inventory_data.get("project_name", "Project")
        
        # Get clone path for reading file contents
        clone_path = shared.get("clone_path", "")
        
        print(f"📚 Building codebase knowledge from {len(source_files)} files...")
        
        return {
            "source_files": source_files,
            "file_inventory": file_inventory,
            "clone_path": clone_path,
            "project_analysis": shared.get("project_analysis", ""),
        }
    
    def _count_lines(self, file_path: str) -> int:
        """Count lines in a file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return len(f.readlines())
        except:
            return 0
    
    def _read_file_content(self, file_path: str) -> str:
        """Read file content safely."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except:
            return ""
    
    def _sort_files_by_dependency(self, files: List[Dict], inventory: Dict) -> List[Dict]:
        """Sort files so utilities/models are processed before controllers/apps.
        
        This is a heuristic ordering:
        1. Config files (pyproject.toml, setup.py, etc.)
        2. Utility/helper modules
        3. Models/data classes
        4. Services/business logic
        5. Controllers/routes/views
        6. Main entry points (app.py, main.py)
        """
        priority_patterns = [
            # Low priority (process first) - foundational
            (["config", "settings", "constants", "types", "typing"], 1),
            (["util", "helper", "common", "base", "core"], 2),
            (["model", "schema", "entity", "dto"], 3),
            (["service", "manager", "handler", "processor"], 4),
            (["controller", "route", "view", "api", "endpoint"], 5),
            # High priority (process last) - entry points
            (["main", "app", "__init__", "index", "wsgi", "asgi"], 6),
        ]
        
        def get_priority(file_info: Dict) -> int:
            path = file_info.get("path", "").lower()
            for patterns, priority in priority_patterns:
                if any(p in path for p in patterns):
                    return priority
            return 4  # Default middle priority
        
        return sorted(files, key=get_priority)
    
    def _build_initial_xml(self, project_name: str, analysis: str) -> str:
        """Create initial empty knowledge XML."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<codebase_knowledge project="{project_name}">
  <overview>{analysis}</overview>
  <files>
  </files>
</codebase_knowledge>"""
    
    def _process_batch(
        self, 
        batch_files: List[Dict], 
        current_xml: str,
        clone_path: str,
        retry_with_single: bool = False
    ) -> Tuple[str, bool]:
        """Process a batch of files and update knowledge XML.
        
        Args:
            batch_files: List of file dicts with path, uri, mime_type
            current_xml: Current knowledge XML
            clone_path: Path to cloned repo
            retry_with_single: If True, only process first file (retry mode)
            
        Returns:
            Tuple of (updated_xml, success)
        """
        if retry_with_single and len(batch_files) > 1:
            batch_files = [batch_files[0]]
            print(f"      ↳ Retrying with single file: {batch_files[0]['path']}")
        
        # Build file content descriptions
        file_descriptions = []
        file_refs = []
        
        for f in batch_files:
            rel_path = f.get("path", "unknown")
            full_path = os.path.join(clone_path, rel_path)
            line_count = self._count_lines(full_path)
            
            # Determine if we should include full content or summarize
            if line_count <= SMALL_FILE_THRESHOLD:
                content = self._read_file_content(full_path)
                file_descriptions.append(
                    f"FILE: {rel_path} (SMALL - {line_count} lines, keep FULL content)\n"
                    f"```\n{content}\n```"
                )
            else:
                file_descriptions.append(
                    f"FILE: {rel_path} (LARGE - {line_count} lines, create SUMMARY)"
                )
                # Add file URI reference for Gemini to read
                file_refs.append({"uri": f["uri"], "mime_type": f.get("mime_type", "text/plain")})
        
        # Build prompt
        prompt = f"""Current codebase knowledge:
```xml
{current_xml}
```

Analyze these new files and UPDATE the XML by adding entries for them:

{chr(10).join(file_descriptions)}

Return the COMPLETE updated XML with the new file entries added."""

        try:
            # If we have large files, include their URIs for content access
            # Pass 1: Use Gemma for high-volume batch summarization
            active_model = GeminiClient.GEMMA_MODEL
            response = self.client.generate_content(
                prompt=prompt,
                system_prompt=get_prompt("summarizer_pass1", active_model),
                file_uris=file_refs if file_refs else None,
                temperature=0.3,
                model_override=active_model,
            )
            
            # Extract XML from response
            xml_content = response.strip()
            if xml_content.startswith("```"):
                lines = xml_content.split("\n")
                xml_content = "\n".join(lines[1:-1])
            
            # Basic validation
            if "<codebase_knowledge" in xml_content and "</codebase_knowledge>" in xml_content:
                return xml_content, True
            else:
                print(f"      ⚠ Invalid XML response, using previous state")
                return current_xml, False
                
        except Exception as e:
            error_msg = str(e)
            print(f"      ⚠ Batch failed: {error_msg[:100]}...")
            
            # Rate limit delay after error
            rate_limit_delay("on_error", show_progress=False)
            
            # If not already retrying with single file, try that
            if not retry_with_single and len(batch_files) > 1:
                return self._process_batch(batch_files, current_xml, clone_path, retry_with_single=True)
            
            return current_xml, False
    
    def _add_relationships(self, current_xml: str) -> str:
        """Pass 2: Identify cross-file relationships and patterns.
        
        Args:
            current_xml: Complete knowledge XML from Pass 1
            
        Returns:
            Updated XML with relationships section
        """
        prompt = f"""Analyze this codebase knowledge and identify:
1. Import/dependency relationships between files
2. Class inheritance and composition
3. Architectural patterns used

Current knowledge:
```xml
{current_xml}
```

Add <relationships> and <architecture> sections to the XML.
Return the COMPLETE updated XML."""

        try:
            # Pass 2: Use Gemini for high-complexity relationship detection
            active_model = GeminiClient.GEMINI_MODEL
            response = self.client.generate_content(
                prompt=prompt,
                system_prompt=get_prompt("summarizer_pass2", active_model),
                temperature=0.3,
                model_override=active_model,
            )
            
            xml_content = response.strip()
            if xml_content.startswith("```"):
                lines = xml_content.split("\n")
                xml_content = "\n".join(lines[1:-1])
            
            if "<relationships>" in xml_content or "<architecture>" in xml_content:
                return xml_content
            
        except Exception as e:
            print(f"   ⚠ Relationship detection failed: {str(e)[:100]}")
        
        return current_xml
    
    def exec(self, prep_res: dict) -> dict:
        """Build codebase knowledge through iterative summarization.
        
        Args:
            prep_res: Contains source files, inventory, and clone path.
            
        Returns:
            Dict with final knowledge XML and file path.
        """
        source_files = prep_res["source_files"]
        inventory = prep_res["file_inventory"]
        clone_path = prep_res["clone_path"]
        analysis = prep_res["project_analysis"]
        
        # Sort files by dependency order
        sorted_files = self._sort_files_by_dependency(source_files, inventory)
        
        # Initialize knowledge XML
        self.knowledge_xml = self._build_initial_xml(self.project_name, analysis)
        
        # ===== PASS 1: Build per-file summaries =====
        print(f"   📝 Pass 1: Building file summaries (Model: {GeminiClient.GEMMA_MODEL})...")
        
        total_batches = (len(sorted_files) + BATCH_SIZE - 1) // BATCH_SIZE
        processed = 0
        failed = 0
        
        for batch_start in range(0, len(sorted_files), BATCH_SIZE):
            batch = sorted_files[batch_start:batch_start + BATCH_SIZE]
            batch_num = (batch_start // BATCH_SIZE) + 1
            
            file_names = [f.get("path", "?")[-30:] for f in batch]
            print(f"      Batch {batch_num}/{total_batches}: {', '.join(file_names)}")
            
            updated_xml, success = self._process_batch(
                batch, self.knowledge_xml, clone_path
            )
            
            if success:
                self.knowledge_xml = updated_xml
                processed += len(batch)
            else:
                failed += len(batch)
            
            # Rate limit delay between summarizer batches
            if batch_start + BATCH_SIZE < len(sorted_files):
                rate_limit_delay("summarizer_batch")
        
        print(f"   ✓ Pass 1 complete: {processed} files processed, {failed} failed")
        
        # ===== PASS 2: Identify relationships =====
        print(f"   🔗 Pass 2: Detecting cross-file relationships (Model: {GeminiClient.GEMINI_MODEL})...")
        
        self.knowledge_xml = self._add_relationships(self.knowledge_xml)
        
        # Rate limit delay after Pass 2 API call
        rate_limit_delay("single_api_call")
        
        print(f"   ✓ Pass 2 complete: Relationships identified")
        
        # Save knowledge XML to file
        knowledge_file = os.path.join(os.path.dirname(clone_path), "codebase_knowledge.xml")
        with open(knowledge_file, "w", encoding="utf-8") as f:
            f.write(self.knowledge_xml)
        
        print(f"📄 Codebase knowledge saved to: {knowledge_file}")
        
        return {
            "knowledge_xml": self.knowledge_xml,
            "knowledge_file": knowledge_file,
            "files_processed": processed,
            "files_failed": failed,
        }
    
    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        """Upload knowledge XML and store in shared state.
        
        Args:
            shared: Shared store.
            prep_res: Prep result.
            exec_res: Exec result with knowledge XML.
            
        Returns:
            Action string for flow.
        """
        knowledge_file = exec_res["knowledge_file"]
        
        # Upload knowledge XML to Gemini for Architect to use
        print(f"📤 Uploading codebase knowledge to Gemini...")
        
        upload_result = self.client.upload_file(
            knowledge_file, 
            display_name="codebase_knowledge.xml"
        )
        
        # Wait for file to be active
        self.client.wait_for_file_active(upload_result["uri"], timeout=30)
        
        # Store in shared state for Architect
        shared["knowledge_xml"] = exec_res["knowledge_xml"]
        shared["knowledge_file"] = knowledge_file
        shared["knowledge_uri"] = upload_result  # {uri, mime_type}
        
        print(f"✓ Codebase knowledge ready ({exec_res['files_processed']} files distilled)")
        
        # Rate limit delay after upload
        rate_limit_delay("single_api_call")
        
        return "default"

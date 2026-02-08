"""
Node: The Summarizer

Context Distillation node that builds a semantic knowledge base (codebase_knowledge.xml)
using a Map-Reduce approach. Processes files in small batches.
"""

import os
import re
from typing import Optional, List, Dict, Tuple
from pocketflow import Node

from utils.gemini_client import get_client
from utils.prompts import get_prompt, get_gem_id
from utils.output_cleaner import clean_xml
from utils.response_supervisor import ResponseSupervisor
from utils.console import console


# Threshold for keeping full content vs summarizing
SMALL_FILE_THRESHOLD = 50  # lines

# Batch configuration
BATCH_SIZE = 2  # files per batch


class SummarizerNode(Node):
    """Summarizer node that builds codebase_knowledge.xml using Map-Reduce."""
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
        self.knowledge_xml: str = ""
    
    def _count_lines(self, file_path: str) -> int:
        """Count lines in a file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except:
            return 0
    
    def _read_file_content(self, file_path: str) -> str:
        """Read file content with error handling."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except:
            return ""
    
    def _sort_files_by_dependency(self, files: List[Dict]) -> List[Dict]:
        """Sort files to process foundational files first."""
        priority_patterns = [
            (["config", "settings", "constants", "types", "typing"], 1),
            (["util", "helper", "common", "base", "core"], 2),
            (["model", "schema", "entity", "dto"], 3),
            (["service", "manager", "handler", "processor"], 4),
            (["controller", "route", "view", "api", "endpoint"], 5),
            (["main", "app", "__init__", "index", "wsgi", "asgi"], 6),
        ]
        
        def get_priority(file_info: Dict) -> int:
            path = file_info.get("path", "").lower()
            for patterns, priority in priority_patterns:
                if any(p in path for p in patterns):
                    return priority
            return 4
        
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
    ) -> Tuple[str, bool]:
        """Process a batch of files and update knowledge XML."""
        file_descriptions = []
        file_refs = []
        
        for f in batch_files:
            rel_path = f.get("path", "unknown")
            full_path = os.path.join(clone_path, rel_path)
            line_count = self._count_lines(full_path)
            
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
                file_refs.append({
                    "uri": f["uri"], 
                    "local_path": f.get("local_path", f["uri"]),
                    "mime_type": f.get("mime_type", "text/plain")
                })
        
        prompt = f"""Give me XML code. 
        Current codebase knowledge:
```xml
{current_xml}
```

Analyze these new files and UPDATE the XML by adding entries for them:

{chr(10).join(file_descriptions)}

Return the COMPLETE updated XML code with the new file entries added."""

        # Build context for supervisor
        batch_file_paths = [f.get("path", "unknown") for f in batch_files]
        
        # Define generate function that takes critique and returns CLEANED response
        def generate_with_critique(critique: str = "") -> str:
            active_model = self.client.MODEL
            gem_id = get_gem_id("summarizer_pass1")
            
            full_prompt = prompt
            if critique:
                full_prompt += f"\n\n[SUPERVISOR FEEDBACK]\n{critique}\nPlease regenerate a CORRECT response."
            
            response = self.client.generate_content(
                prompt=full_prompt,
                system_prompt=None if gem_id else get_prompt("summarizer_pass1", active_model),
                file_uris=file_refs if file_refs else None,
                model_override=active_model,
                gem_id=gem_id,
            )
            return clean_xml(response)  # Clean before returning
        
        # Generate initial response and clean it
        try:
            initial_response = generate_with_critique("")
        except Exception as e:
            console.warning(f"Initial generation failed: {str(e)[:100]}", indent=2)
            return current_xml, False
        
        # Use supervisor with optimized flow (local validation first)
        supervisor = ResponseSupervisor(self.client, max_retries=10)
        
        context = {
            "previous_xml": current_xml,
            "batch_files": batch_file_paths,
            "original_prompt": prompt,
        }
        
        xml_content, success = supervisor.supervise_xml(
            cleaned_response=initial_response,
            context=context,
            generate_with_critique_fn=generate_with_critique
        )
        
        return xml_content, success
    
    def _add_relationships(self, current_xml: str) -> str:
        """Pass 2: Add relationship analysis to knowledge XML."""
        prompt = f"""Analyze this codebase knowledge and add relationship mappings:

```xml
{current_xml}
```

Add <relationships> and <architecture> sections to the XML.
Return the COMPLETE updated XML."""

        # Define generate function that returns CLEANED response
        def generate_with_critique(critique: str = "") -> str:
            active_model = self.client.MODEL
            gem_id = get_gem_id("summarizer_pass2")
            
            full_prompt = prompt
            if critique:
                full_prompt += f"\n\n[SUPERVISOR FEEDBACK]\n{critique}\nPlease regenerate a CORRECT response."
            
            response = self.client.generate_content(
                prompt=full_prompt,
                system_prompt=None if gem_id else get_prompt("summarizer_pass2", active_model),
                model_override=active_model,
                gem_id=gem_id,
            )
            return clean_xml(response)
        
        # Generate initial response
        try:
            initial_response = generate_with_critique("")
        except Exception as e:
            console.warning(f"Pass 2 initial generation failed: {str(e)[:100]}", indent=2)
            return current_xml
        
        # Use supervisor with optimized flow (local validation first)
        supervisor = ResponseSupervisor(self.client, max_retries=10)
        
        context = {
            "previous_xml": current_xml,
            "batch_files": [],  # No new files in Pass 2
            "original_prompt": prompt,
        }
        
        xml_content, success = supervisor.supervise_xml(
            cleaned_response=initial_response,
            context=context,
            generate_with_critique_fn=generate_with_critique
        )
        
        return xml_content
    
    def prep(self, shared: dict) -> dict:
        """Prepare for summarization."""
        file_uris = shared.get("file_uris", [])
        clone_path = shared.get("clone_path")
        
        if not file_uris:
            raise ValueError("No 'file_uris' in shared store. Run UploaderNode first.")
        if not clone_path:
            raise ValueError("No 'clone_path' in shared store.")
        
        self.client = get_client()
        
        source_files = [f for f in file_uris if not f.get("is_context")]
        
        return {
            "source_files": source_files,
            "clone_path": clone_path,
            "analysis": shared.get("project_analysis", ""),
        }
    
    def exec(self, prep_res: dict) -> dict:
        """Execute the Map-Reduce summarization."""
        source_files = prep_res["source_files"]
        clone_path = prep_res["clone_path"]
        analysis = prep_res["analysis"]
        
        project_name = os.path.basename(clone_path)
        
        console.section("PHASE 2: Knowledge Base Construction")
        console.info(f"Summarizing {len(source_files)} files into knowledge base...", indent=1)
        
        self.knowledge_xml = self._build_initial_xml(project_name, analysis)
        
        sorted_files = self._sort_files_by_dependency(source_files)
        total_files = len(sorted_files)
        total_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE
        
        # console.status(f"Pass 1: Processing files in {(len(sorted_files) + BATCH_SIZE - 1) // BATCH_SIZE} batches...", done=True)
        
        processed = 0
        failed = 0
        
        for batch_start in range(0, len(sorted_files), BATCH_SIZE):
            batch = sorted_files[batch_start:batch_start + BATCH_SIZE]
            batch_num = (batch_start // BATCH_SIZE) + 1
            # total_batches calculated above
            
            # Update progress bar
            console.progress("Processing batches", batch_num, total_batches)
            
            # Print details only in verbose mode
            file_names = [f.get("path", "?")[-30:] for f in batch]
            console.debug(f"Batch {batch_num}: {', '.join(file_names)}")
            
            updated_xml, success = self._process_batch(batch, self.knowledge_xml, clone_path)
            
            if success:
                self.knowledge_xml = updated_xml
                processed += len(batch)
            else:
                failed += len(batch)
        
        console.success(f"Pass 1 complete: {processed} files processed, {failed} failed", indent=1)
        
        # Pass 2: Identify relationships
        console.status("Pass 2: Detecting cross-file relationships...", done=True)
        self.knowledge_xml = self._add_relationships(self.knowledge_xml)
        console.success("Pass 2 complete: Relationships identified", indent=1)
        
        # Save knowledge XML
        knowledge_file = os.path.join(os.path.dirname(clone_path), "codebase_knowledge.xml")
        with open(knowledge_file, "w", encoding="utf-8") as f:
            f.write(self.knowledge_xml)
        
        console.info(f"Codebase knowledge saved to: {knowledge_file}", indent=1)
        
        return {
            "knowledge_xml": self.knowledge_xml,
            "knowledge_file": knowledge_file,
            "files_processed": processed,
            "files_failed": failed,
        }
    
    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        """Store knowledge in shared state."""
        knowledge_file = exec_res["knowledge_file"]
        
        shared["knowledge_xml"] = exec_res["knowledge_xml"]
        shared["knowledge_file"] = knowledge_file
        shared["knowledge_uri"] = {
            "uri": knowledge_file,
            "local_path": knowledge_file,
            "mime_type": "text/xml"
        }
        
        print(f"✓ Codebase knowledge ready ({exec_res['files_processed']} files distilled)")
        return "default"

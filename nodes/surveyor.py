"""
Node 2: The Surveyor

Analyzes the project map using Gemini to identify
relevant source files for processing.
"""

import json
from typing import Optional
from pocketflow import Node

from utils.gemini_client import get_client
from utils.prompts import get_prompt, get_gem_id
from utils.output_cleaner import clean_json


class SurveyorNode(Node):
    """Surveyor node that selects relevant files using LLM analysis."""
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
    
    def prep(self, shared: dict) -> str:
        """Get the project map from shared store."""
        project_map = shared.get("project_map")
        if not project_map:
            raise ValueError("No 'project_map' in shared store. Run ScoutNode first.")
        
        self.client = get_client()
        return project_map
    
    def exec(self, prep_res: str) -> dict:
        """Analyze project map with Gemini."""
        active_model = self.client.MODEL
        print(f"🔬 Analyzing project structure with {active_model}...")
        
        base_prompt = f"""Analyze this project structure and identify ALL the important source files that are needed to understand the architecture:

PROJECT STRUCTURE:
```
{prep_res}
```

IMPORTANT: You must select ALL files that contain source code, business logic, models, controllers, services, and essential configuration. Do NOT limit your selection - include everything needed for complete architectural understanding.

Return paths that would be needed to understand the system architecture and generate accurate diagrams."""
        
        max_parse_retries = 3
        last_error = None
        
        for attempt in range(max_parse_retries):
            if attempt == 0:
                prompt = base_prompt
            else:
                print(f"   🔄 Retry {attempt}/{max_parse_retries - 1}: Requesting properly formatted JSON...")
                prompt = f"""Your previous response was not valid JSON. Error: {last_error}

{base_prompt}

CRITICAL: Return ONLY a valid JSON object. No markdown code blocks, no explanatory text before or after.
Example format:
{{"analysis": "...", "include_paths": ["file1.py", "file2.js"], "exclude_patterns": ["*.log"], "estimated_file_count": 10}}"""
            
            gem_id = get_gem_id("surveyor")
            
            response = self.client.generate_content(
                prompt=prompt,
                system_prompt=None if gem_id else get_prompt("surveyor", active_model),
                temperature=0.3,
                model_override=active_model,
                gem_id=gem_id,
            )
            
            try:
                clean_response = clean_json(response)
                config = json.loads(clean_response)
                
                if "include_paths" not in config:
                    config["include_paths"] = []
                if "exclude_patterns" not in config:
                    config["exclude_patterns"] = []
                if "analysis" not in config:
                    config["analysis"] = "Unknown project type"
                
                print(f"   ✓ Analysis: {config['analysis']}")
                print(f"   ✓ Selected {len(config['include_paths'])} paths for upload")
                
                return config
                
            except json.JSONDecodeError as e:
                last_error = str(e)
                print(f"   ⚠ Failed to parse JSON (attempt {attempt + 1}/{max_parse_retries}): {e}")
                if attempt < max_parse_retries - 1:
                    print(f"   Raw response preview: {response[:300]}...")
        
        # All retries exhausted
        print(f"\n❌ CRITICAL ERROR: Failed to get valid JSON response after {max_parse_retries} attempts.")
        raise RuntimeError(f"Surveyor failed: Could not parse Gemini response. Last error: {last_error}")
    
    def post(self, shared: dict, prep_res: str, exec_res: dict) -> str:
        """Store the upload configuration."""
        import os
        
        shared["upload_config"] = exec_res
        shared["project_analysis"] = exec_res.get("analysis", "")
        
        clone_dir = shared.get("clone_dir", ".")
        config_file = os.path.join(clone_dir, "upload_config.json")
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(exec_res, f, indent=2)
        
        print(f"📄 Upload config saved to: {config_file}")
        return "default"

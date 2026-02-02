"""
Node 2: The Surveyor

Analyzes the project map using Gemini to identify
relevant source files for upload.
"""

import json
from typing import Optional
from pocketflow import Node

from utils.gemini_client import GeminiClient
from utils.rate_limiter import rate_limit_delay

from utils.prompts import get_prompt

# Surveyor prompt is now managed centrally in utils/prompts.py
# Use get_prompt("surveyor", model_name) to get the appropriate prompt

class SurveyorNode(Node):
    """Surveyor node that selects relevant files using LLM analysis."""
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
    
    def prep(self, shared: dict) -> str:
        """Get the project map from shared store.
        
        Args:
            shared: Shared store with 'project_map' key.
            
        Returns:
            The project map string.
        """
        project_map = shared.get("project_map")
        if not project_map:
            raise ValueError("No 'project_map' in shared store. Run ScoutNode first.")
        
        # Initialize Gemini client
        self.client = GeminiClient()
        
        return project_map
    
    def exec(self, prep_res: str) -> dict:
        """Analyze project map with Gemini.
        
        Args:
            prep_res: The project map string.
            
        Returns:
            Parsed upload configuration.
        """
        active_model = GeminiClient.GEMINI_MODEL
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
            # Build prompt with error context for retries
            if attempt == 0:
                prompt = base_prompt
            else:
                print(f"   🔄 Retry {attempt}/{max_parse_retries - 1}: Requesting properly formatted JSON...")
                prompt = f"""Your previous response was not valid JSON. Error: {last_error}

{base_prompt}

CRITICAL: Return ONLY a valid JSON object. No markdown code blocks, no explanatory text before or after.
Example format:
{{"analysis": "...", "include_paths": ["file1.py", "file2.js"], "exclude_patterns": ["*.log"], "estimated_file_count": 10}}"""
            
            # Use Gemma for file selection (high volume, structured task)
            # active_model defined at start of exec
            response = self.client.generate_content(
                prompt=prompt,
                system_prompt=get_prompt("surveyor", active_model),
                temperature=0.3,
                model_override=active_model,
            )
            
            # Parse JSON response
            try:
                # Handle markdown code blocks if present
                clean_response = response.strip()
                if clean_response.startswith("```"):
                    # Remove code block markers
                    lines = clean_response.split("\n")
                    # Find the closing ``` and extract content between
                    start_idx = 1  # Skip first line with ```json
                    end_idx = len(lines) - 1
                    for i in range(len(lines) - 1, 0, -1):
                        if lines[i].strip() == "```":
                            end_idx = i
                            break
                    clean_response = "\n".join(lines[start_idx:end_idx])
                
                config = json.loads(clean_response)
                
                # Validate required fields
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
                print(f"   ⚠ Failed to parse Gemini response as JSON (attempt {attempt + 1}/{max_parse_retries}): {e}")
                if attempt < max_parse_retries - 1:
                    print(f"   Raw response preview: {response[:300]}...")
                    # Wait before retry
                    rate_limit_delay("single_api_call")
        
        # All retries exhausted - halt the program
        print(f"\n❌ CRITICAL ERROR: Failed to get valid JSON response after {max_parse_retries} attempts.")
        print(f"   Last raw response: {response[:500]}...")
        raise RuntimeError(
            f"Surveyor failed: Could not parse Gemini response as valid JSON after {max_parse_retries} attempts. "
            f"Last error: {last_error}"
        )
    
    def post(self, shared: dict, prep_res: str, exec_res: dict) -> str:
        """Store the upload configuration.
        
        Args:
            shared: Shared store.
            prep_res: Project map.
            exec_res: Upload configuration.
            
        Returns:
            Action string for flow.
        """
        shared["upload_config"] = exec_res
        shared["project_analysis"] = exec_res.get("analysis", "")
        
        # Save config to file in clone_dir
        import os
        clone_dir = shared.get("clone_dir", ".")
        config_file = os.path.join(clone_dir, "upload_config.json")
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(exec_res, f, indent=2)
        
        print(f"📄 Upload config saved to: {config_file}")
        
        # Rate limit delay after Gemini API call
        rate_limit_delay("single_api_call")
        
        return "default"

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


SURVEYOR_SYSTEM_PROMPT = """You are a Technical Lead selecting files for architectural analysis.
Your task is to identify source files needed to understand the system architecture.

INCLUDE RULES:
1. Source code: .py, .js, .ts, .java, .go, .rs, .jsx, .tsx, .vue, .svelte
2. Configuration: package.json, pyproject.toml, Dockerfile, docker-compose.yml, settings files
3. Core logic: models, views, controllers, services, routes, middleware, utils
4. Entry points: main.py, app.py, index.js, manage.py

EXCLUDE RULES:
5. Binary files: ALL files with "type": "binary" in file_inventory.json
6. Generated/cached: node_modules, dist, build, .git, __pycache__, venv, migrations
7. Tests: test files unless critical to architecture
8. Docs: .md, .txt files (except README if it contains architecture info)
9. Lock files: package-lock.json, poetry.lock, yarn.lock

CRITICAL RULES:
10. MUTUAL EXCLUSIVITY: A file path CANNOT appear in both include_paths AND exclude_patterns. Choose one.
11. NO DUPLICATES: If you exclude a file, do NOT also include it. If you include it, do NOT also exclude it.
12. SMART SELECTION: When similar files exist (e.g., index.html and old_index.html), include ONLY the current version:
    - SKIP files with prefixes: old_, backup_, deprecated_, _old, _backup, _bak
    - SKIP files with suffixes: .bak, .backup, .old, _copy
    - INCLUDE: The non-prefixed, non-suffixed current version
13. TEMPLATES: For web frameworks (Django, Flask, Rails, React):
    - INCLUDE: Only key structural templates (base, layout, index, main)
    - EXCLUDE: All other HTML templates (they follow the same patterns)
14. STATIC FILES: Exclude CSS/JS unless they contain significant business logic

Return your response as a JSON object with this exact structure:
{
    "analysis": "Brief 1-2 sentence summary of the project type",
    "include_paths": ["path/to/file1", "path/to/file2"],
    "exclude_patterns": ["pattern1", "pattern2"],
    "estimated_file_count": 42
}

FINAL CHECK: Before returning, verify NO file appears in both lists.

Return ONLY the JSON object, no additional text."""


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
        print("🔬 Analyzing project structure with Gemini...")
        
        prompt = f"""Analyze this project structure and identify ALL the important source files that are needed to understand the architecture:

PROJECT STRUCTURE:
```
{prep_res}
```

IMPORTANT: You must select ALL files that contain source code, business logic, models, controllers, services, and essential configuration. Do NOT limit your selection - include everything needed for complete architectural understanding.

Return paths that would be needed to understand the system architecture and generate accurate diagrams."""
        
        response = self.client.generate_content(
            prompt=prompt,
            system_prompt=SURVEYOR_SYSTEM_PROMPT,
            temperature=0.3,  # Lower temperature for more consistent JSON
        )
        
        # Parse JSON response
        try:
            # Handle markdown code blocks if present
            clean_response = response.strip()
            if clean_response.startswith("```"):
                # Remove code block markers
                lines = clean_response.split("\n")
                clean_response = "\n".join(lines[1:-1])
            
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
            print(f"   ⚠ Failed to parse Gemini response as JSON: {e}")
            print(f"   Raw response: {response[:500]}...")
            
            # Fallback: include common source directories
            return {
                "analysis": "Failed to parse - using defaults",
                "include_paths": ["src", "lib", "app", "api", "models", "controllers", "services"],
                "exclude_patterns": ["node_modules", "dist", "build", "__pycache__", ".git"],
                "estimated_file_count": 50,
            }
    
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

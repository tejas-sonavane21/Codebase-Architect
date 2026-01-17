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


SURVEYOR_SYSTEM_PROMPT = """You are a Technical Lead reviewing a codebase structure.
Your task is to identify which folders and files contain actual source code, business logic, 
and essential configuration that would be needed to understand the system architecture.

RULES:
1. INCLUDE: Source code files (.py, .js, .ts, .java, .go, .rs, etc.)
2. INCLUDE: Configuration files (package.json, pyproject.toml, Dockerfile, etc.)
3. INCLUDE: API definitions, schemas, models, controllers, services
4. EXCLUDE: Test files (unless specifically relevant to architecture)
5. EXCLUDE: Documentation files (.md, .txt) except README
6. EXCLUDE: Any path containing: node_modules, dist, build, .git, __pycache__, venv, .venv
7. EXCLUDE: Lock files, logs, and generated files

Return your response as a JSON object with this exact structure:
{
    "analysis": "Brief 1-2 sentence summary of the project type",
    "include_paths": ["path/to/include1", "path/to/include2"],
    "exclude_patterns": ["pattern1", "pattern2"],
    "estimated_file_count": 42
}

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

"""
Node 7: The Critic

Validates PlantUML syntax, checks complexity,
renders via Kroki API, and triggers self-correction if needed.
"""

import os
from pathlib import Path
from typing import Optional
from pocketflow import Node

from utils.kroki_client import KrokiClient


class CriticNode(Node):
    """Critic node that validates and renders diagrams."""
    
    MAX_RETRIES = 3
    
    def __init__(self, max_retries: int = 1, wait: int = 0):
        super().__init__(max_retries=max_retries, wait=wait)
    
    def prep(self, shared: dict) -> dict:
        """Get current PlantUML code.
        
        Args:
            shared: Shared store with 'current_plantuml'.
            
        Returns:
            Dict with code and diagram info.
        """
        plantuml = shared.get("current_plantuml", "")
        diagram_info = shared.get("current_diagram_info", {})
        retry_count = shared.get("retry_count", 0)
        output_dir = shared.get("output_dir", "generated_diagrams")
        
        return {
            "plantuml": plantuml,
            "diagram_info": diagram_info,
            "retry_count": retry_count,
            "output_dir": output_dir,
        }
    
    def exec(self, prep_res: dict) -> dict:
        """Validate and render the diagram.
        
        Args:
            prep_res: Dict with PlantUML code and context.
            
        Returns:
            Dict with success status, output path or error.
        """
        plantuml = prep_res["plantuml"]
        diagram_info = prep_res["diagram_info"]
        retry_count = prep_res["retry_count"]
        output_dir = prep_res["output_dir"]
        
        diagram_name = diagram_info.get("name", "diagram")
        safe_name = self._sanitize_filename(diagram_name)
        
        print(f"🔍 Validating: {diagram_name}")
        
        # Step 1: Syntax validation
        is_valid, syntax_error = KrokiClient.validate_syntax(plantuml)
        if not is_valid:
            print(f"   ✗ Syntax error: {syntax_error}")
            return {
                "success": False,
                "error": f"Syntax validation failed: {syntax_error}",
                "error_type": "syntax",
            }
        
        # Step 2: Complexity analysis (warnings only)
        complexity = KrokiClient.analyze_complexity(plantuml)
        for warning in complexity["warnings"]:
            print(f"   ⚠ {warning}")
        
        # Step 3: Render via Kroki
        print(f"   Rendering via Kroki API...")
        success, png_bytes, render_error = KrokiClient.render_plantuml(plantuml)
        
        if not success:
            print(f"   ✗ Render failed: {render_error}")
            return {
                "success": False,
                "error": f"Kroki rendering failed: {render_error}",
                "error_type": "render",
            }
        
        # Step 4: Save outputs
        os.makedirs(output_dir, exist_ok=True)
        
        # Save PNG
        png_path = os.path.join(output_dir, f"{safe_name}.png")
        with open(png_path, "wb") as f:
            f.write(png_bytes)
        
        # Save PlantUML source
        puml_path = os.path.join(output_dir, f"{safe_name}.puml")
        with open(puml_path, "w", encoding="utf-8") as f:
            f.write(plantuml)
        
        print(f"   ✓ Saved: {png_path}")
        print(f"   ✓ Saved: {puml_path}")
        
        return {
            "success": True,
            "png_path": png_path,
            "puml_path": puml_path,
            "diagram_name": diagram_name,
            "complexity": complexity,
        }
    
    def _sanitize_filename(self, name: str) -> str:
        """Convert diagram name to safe filename."""
        # Replace spaces and special chars
        safe = name.lower()
        safe = safe.replace(" ", "_")
        safe = "".join(c for c in safe if c.isalnum() or c in "_-")
        return safe[:50]  # Limit length
    
    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        """Handle result and determine next action.
        
        Args:
            shared: Shared store.
            prep_res: Prep result.
            exec_res: Execution result.
            
        Returns:
            Action: 'next' for success, 'retry' for self-correction, 'fail' if max retries.
        """
        retry_count = prep_res["retry_count"]
        
        if exec_res["success"]:
            # Success! Record and move to next diagram
            generated = shared.get("generated_diagrams", [])
            generated.append({
                "name": exec_res["diagram_name"],
                "png_path": exec_res["png_path"],
                "puml_path": exec_res["puml_path"],
            })
            shared["generated_diagrams"] = generated
            
            # Move to next diagram
            shared["current_diagram_index"] = shared.get("current_diagram_index", 0) + 1
            shared["retry_count"] = 0
            shared["critic_error"] = None
            
            return "next"
        
        else:
            # Failed - should we retry?
            if retry_count < self.MAX_RETRIES:
                shared["retry_count"] = retry_count + 1
                shared["critic_error"] = exec_res["error"]
                
                print(f"   ↩ Sending back to Drafter for correction...")
                return "retry"
            
            else:
                # Max retries exceeded
                print(f"   ✗ Max retries ({self.MAX_RETRIES}) exceeded. Skipping diagram.")
                
                # Move to next diagram anyway
                shared["current_diagram_index"] = shared.get("current_diagram_index", 0) + 1
                shared["retry_count"] = 0
                shared["critic_error"] = None
                
                return "next"

"""
Node 6: The Drafter

Generates PlantUML code for a specific diagram
using Gemini with code context.
"""

from typing import Optional
from pocketflow import Node

from utils.gemini_client import get_client
from utils.prompts import get_prompt, get_gem_id
from utils.diagram_rules import get_diagram_rules
from utils.gem_manager import update_gem
from utils.output_cleaner import clean_plantuml
from utils.console import console


MAX_RETRIES = 5  # Maximum retries per diagram


class DrafterNode(Node):
    """Drafter node that generates PlantUML code using LLM."""
    
    def __init__(self, max_retries: int = MAX_RETRIES, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
    
    def prep(self, shared: dict) -> dict:
        """Get current diagram from queue."""
        queue = shared.get("diagram_queue", [])
        current_idx = shared.get("current_diagram_index", 0)
        
        if current_idx >= len(queue):
            return {"done": True}
        
        current_diagram = queue[current_idx]
        retry_count = shared.get("retry_count", 0)
        knowledge_uri = shared.get("knowledge_uri")
        
        self.client = get_client()
        
        return {
            "current_index": current_idx,
            "total_diagrams": len(queue),
            "done": False,
            "diagram": current_diagram,
            "retry_count": retry_count,
            "knowledge_uri": knowledge_uri,
        }
    
    def exec(self, prep_res: dict) -> str:
        """Generate PlantUML code."""
        if prep_res.get("done"):
            return ""
        
        diagram = prep_res["diagram"]
        retry_count = prep_res.get("retry_count", 0)
        
        diagram_name = diagram["name"]
        diagram_type = diagram["type"]
        focus = diagram["focus"]
        complexity = diagram.get("complexity", "unknown")
        
        active_model = self.client.MODEL
        
        if retry_count > 0:
            console.debug(f"Retry {retry_count}/{MAX_RETRIES} for: {diagram_name}")
        else:
            console.step(prep_res["current_index"] + 1, prep_res["total_diagrams"], f"Drafting: {diagram_name} [{complexity}]")
        
        # ---------------------------------------------------------
        # Dynamic Gem Update (only if diagram type changed)
        # ---------------------------------------------------------
        gem_id = get_gem_id("drafter")
        
        if gem_id:
            # Check if we need to update the gem rules
            last_type = self.client.__dict__.get("_last_drafter_type")
            
            if last_type != diagram_type:
                console.debug(f"Updating drafter gem rules for: {diagram_type}")
                
                # Get base prompt and specific rules
                base_prompt = get_prompt("drafter", active_model)
                specific_rules = get_diagram_rules(diagram_type)
                
                # Combine them
                full_system_prompt = f"{base_prompt}\n\n{specific_rules}"
                if retry_count > 0:
                     full_system_prompt += f"\n\nIMPORTANT: This is a RETRY. The previous attempt failed validation. Pay extra attention to syntax rules."
                
                # Update the gem
                success = update_gem(
                    self.client, 
                    "drafter", 
                    name=f"Drafter ({diagram_type})", 
                    prompt=full_system_prompt,
                    description=f"PlantUML {diagram_type} diagram generator with strict syntax rules"
                )
                
                if success:
                    self.client.__dict__["_last_drafter_type"] = diagram_type
        
        # ---------------------------------------------------------
        # Prompt Construction
        # ---------------------------------------------------------
        
        # Build user prompt with diagram context
        prompt_parts = [
            f"Generate a {diagram_type.upper()} diagram in PlantUML format.",
            f"",
            f"Diagram Name: {diagram_name}",
            f"Focus: {focus}",
        ]
        
        if diagram.get("files"):
            prompt_parts.append(f"Relevant Files: {', '.join(diagram['files'])}")
        
        if diagram.get("expected_elements"):
            prompt_parts.append(f"\nExpected Elements (MUST include ALL):")
            for elem in diagram["expected_elements"]:
                prompt_parts.append(f"  - {elem}")
        
        prompt = "\n".join(prompt_parts)
        
        # Get knowledge context
        knowledge_uri = prep_res.get("knowledge_uri")
        file_uris = [knowledge_uri] if knowledge_uri else []
        
        # If no gem, pass FULL prompt inline (base + rules)
        system_prompt = None
        if not gem_id:
            base_prompt = get_prompt("drafter", active_model)
            specific_rules = get_diagram_rules(diagram_type)
            system_prompt = f"{base_prompt}\n\n{specific_rules}"
        
        response = self.client.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            file_uris=file_uris,
            temperature=0.4,
            model_override=active_model,
            gem_id=gem_id,
        )
        
        code = clean_plantuml(response)
        console.debug(f"Generated {len(code.split(chr(10)))} lines of PlantUML")
        
        return code
    
    def post(self, shared: dict, prep_res: dict, exec_res: str) -> str:
        """Store generated code and proceed to critic."""
        if prep_res.get("done"):
            return "complete"
        
        shared["current_plantuml"] = exec_res
        shared["current_diagram_info"] = prep_res["diagram"]
        
        return "validate"

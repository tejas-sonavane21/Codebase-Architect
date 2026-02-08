"""
Node 4: The Architect (Dual-Prompt)

Plans focused architectural diagrams using a two-pass strategy:
1. Pass 1 (Behavioral): State machines, algorithms, workflows
2. Pass 2 (Structural): Classes, components, modules
3. Pass 3 (Merge): AI-driven deduplication

Uses dynamic gem updates to switch between prompts.
"""

import json
import os
from typing import Optional, Dict, List
from pocketflow import Node

from utils.gemini_client import get_client
from utils.prompts import get_prompt, get_gem_id
from utils.console import console
from utils.gem_manager import update_gem
from utils.output_cleaner import clean_json


# ID offset for structural diagrams (prevents ID collision)
STRUCTURAL_ID_OFFSET = 100


class ArchitectNode(Node):
    """Architect node that plans focused diagrams using dual-prompt LLM strategy."""
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
    
    def prep(self, shared: dict) -> dict:
        """Gather context for diagram planning."""
        knowledge_uri = shared.get("knowledge_uri")
        knowledge_xml = shared.get("knowledge_xml", "")
        project_analysis = shared.get("project_analysis", "")
        
        if not knowledge_uri:
            uri_list = shared.get("uri_list", [])
            if not uri_list:
                raise ValueError("No knowledge or files available. Check SummarizerNode/UploaderNode.")
            return {
                "uri_list": uri_list,
                "knowledge_xml": "",
                "analysis": project_analysis,
                "use_knowledge": False,
            }
        
        self.client = get_client()
        
        return {
            "knowledge_uri": knowledge_uri,
            "knowledge_xml": knowledge_xml,
            "analysis": project_analysis,
            "use_knowledge": True,
        }
    
    def _update_gem_prompt(self, prompt_key: str, description: str) -> bool:
        """
        Dynamically update the 'architect' gem with a different prompt.
        
        Args:
            prompt_key: Key in PROMPTS dict (e.g., 'architect', 'architect_overview')
            description: Description for the updated gem
            
        Returns:
            True if update succeeded.
        """
        gem_id = get_gem_id("architect")
        if not gem_id:
            return False
        
        prompt_content = get_prompt(prompt_key, self.client.MODEL)
        
        success = update_gem(
            self.client,
            "architect",
            name=f"codebase-architect",
            prompt=prompt_content,
            description=description
        )
        
        return success
    
    def _generate_plan(self, prep_res: dict, pass_name: str) -> Dict:
        """
        Generate a diagram plan using current gem configuration.
        
        Args:
            prep_res: Prepared resources from prep()
            pass_name: Name of the pass for logging
            
        Returns:
            Diagram plan dict.
        """
        active_model = self.client.MODEL
        
        if prep_res.get("use_knowledge"):
            prompt = """Analyze the attached codebase_knowledge.xml file and propose focused architectural diagrams.

The XML contains:
- File summaries with purpose and key components
- Small files with full content
- Cross-file relationships and patterns

Based on this semantic understanding of the codebase, propose specific, focused diagrams.

Consider:
1. What are the main modules/components?
2. What are the key workflows that should be visualized?
3. What data models exist and their relationships?
4. How do components interact with each other?

Propose specific, focused diagrams that would help a developer understand this codebase."""

            gem_id = get_gem_id("architect")
            
            response = self.client.generate_content(
                prompt=prompt,
                system_prompt=None if gem_id else get_prompt("architect", active_model),
                file_uris=[prep_res["knowledge_uri"]],
                temperature=0.5,
                model_override=active_model,
                gem_id=gem_id,
            )
        else:
            prompt = f"""Based on the uploaded codebase files, analyze the architecture and propose focused diagrams.

Project Analysis: {prep_res['analysis']}

Consider:
1. What are the main modules/components?
2. What are the key workflows that should be visualized?
3. What data models exist and their relationships?
4. How do components interact with each other?

Propose specific, focused diagrams that would help a developer understand this codebase."""

            gem_id = get_gem_id("architect")
            
            response = self.client.generate_content(
                prompt=prompt,
                system_prompt=None if gem_id else get_prompt("architect", active_model),
                file_uris=prep_res.get("uri_list", []),
                temperature=0.5,
                model_override=active_model,
                gem_id=gem_id,
            )
        
        try:
            clean_response = clean_json(response)
            plan = json.loads(clean_response)
            
            if "diagrams" not in plan:
                plan["diagrams"] = []
            
            return plan
            
        except json.JSONDecodeError as e:
            console.debug(f"Failed to parse {pass_name} response: {e}", indent=2)
            return {"project_summary": "", "diagrams": []}
    
    def _offset_diagram_ids(self, diagrams: List[Dict], offset: int) -> List[Dict]:
        """Add offset to diagram IDs to prevent collision."""
        for d in diagrams:
            d["id"] = d.get("id", 0) + offset
        return diagrams
    
    def exec(self, prep_res: dict) -> dict:
        """
        Generate diagram plan using dual-prompt strategy.
        
        Pass 1: Behavioral Analysis (State, Activity, Sequence)
        Pass 2: Structural Analysis (Class, Component)
        
        Note: Audit/deduplication is now handled by AuditNode at the end of the flow.
        """
        active_model = self.client.MODEL
        console.section("PHASE 3: Architecture Planning")
        console.info(f"Using model: {active_model}", indent=1)
        
        # =========================================================
        # PASS 1: Behavioral Analysis
        # =========================================================
        console.status("Running Pass 1: Behavioral Analysis...")
        behavioral_plan = self._generate_plan(prep_res, "Behavioral")
        behavioral_count = len(behavioral_plan.get("diagrams", []))
        console.status(f"Found {behavioral_count} behavioral diagrams", done=True)
        
        for d in behavioral_plan.get("diagrams", []):
            console.item(f"{d['name']} ({d['type']})")
        
        # =========================================================
        # PASS 2: Structural Analysis (Dynamic Gem Update)
        # =========================================================
        console.status("Running Pass 2: Structural Analysis...")
        console.debug("Updating 'architect' gem to Structural mode...")
        
        self._update_gem_prompt("architect_overview", "STRUCTURAL-MAPPER: High-level architecture planner")
        
        structural_plan = self._generate_plan(prep_res, "Structural")
        
        # Offset IDs to prevent collision
        structural_plan["diagrams"] = self._offset_diagram_ids(
            structural_plan.get("diagrams", []), 
            STRUCTURAL_ID_OFFSET
        )
        
        structural_count = len(structural_plan.get("diagrams", []))
        console.status(f"Found {structural_count} structural diagrams", done=True)
        
        for d in structural_plan.get("diagrams", []):
            console.item(f"{d['name']} ({d['type']})")
        
        # Restore original prompt
        console.debug("Restoring 'architect' gem to Behavioral mode...")
        self._update_gem_prompt("architect", "DIAGRAM-STRATEGIST: Strategic diagram planner")
        
        # =========================================================
        # MERGE: Combine all diagrams (Audit happens later in AuditNode)
        # =========================================================
        all_diagrams = behavioral_plan.get("diagrams", []) + structural_plan.get("diagrams", [])
        
        # Renumber IDs sequentially
        for i, d in enumerate(all_diagrams, 1):
            d["id"] = i
        
        final_plan = {
            "project_summary": behavioral_plan.get("project_summary", structural_plan.get("project_summary", "")),
            "diagrams": all_diagrams
        }
        
        console.success(f"Combined Plan: {len(all_diagrams)} diagrams (audit pending)")
        
        return final_plan
    
    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        """Store the diagram plan."""
        shared["diagram_plan"] = exec_res
        shared["all_diagrams"] = exec_res.get("diagrams", [])
        
        clone_path = shared.get("clone_path", ".")
        plan_file = os.path.join(clone_path, "..", "diagram_plan.json")
        
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(exec_res, f, indent=2)
        
        console.debug(f"Plan saved: {plan_file}")
        return "default"

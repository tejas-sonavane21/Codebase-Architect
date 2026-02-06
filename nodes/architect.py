"""
Node 4: The Architect

Plans focused architectural diagrams based on the codebase knowledge.
Avoids "God Diagrams" by breaking into sub-modules.
"""

import json
import os
from typing import Optional
from pocketflow import Node

from utils.gemini_client import get_client
from utils.prompts import get_prompt, get_gem_id
from utils.output_cleaner import clean_json


class ArchitectNode(Node):
    """Architect node that plans focused diagrams using LLM."""
    
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
    
    def exec(self, prep_res: dict) -> dict:
        """Generate diagram plan using Gemini."""
        active_model = self.client.MODEL
        print(f"📐 Planning architectural diagrams with {active_model}...")
        
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
            
            print(f"   ✓ Planned {len(plan['diagrams'])} diagrams")
            
            for d in plan["diagrams"]:
                print(f"      [{d['id']}] {d['name']} ({d['type']})")
            
            return plan
            
        except json.JSONDecodeError as e:
            print(f"   ⚠ Failed to parse response: {e}")
            
            return {
                "project_summary": "Unable to fully analyze project",
                "diagrams": [
                    {
                        "id": 1,
                        "name": "System Overview Class Diagram",
                        "type": "class",
                        "focus": "Main classes and their relationships",
                        "files": [],
                        "complexity": "medium",
                    },
                    {
                        "id": 2,
                        "name": "Component Architecture",
                        "type": "component",
                        "focus": "High-level system components and dependencies",
                        "files": [],
                        "complexity": "low",
                    },
                ],
            }
    
    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        """Store the diagram plan."""
        shared["diagram_plan"] = exec_res
        shared["all_diagrams"] = exec_res.get("diagrams", [])
        
        clone_path = shared.get("clone_path", ".")
        plan_file = os.path.join(clone_path, "..", "diagram_plan.json")
        
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(exec_res, f, indent=2)
        
        print(f"📄 Diagram plan saved to: {plan_file}")
        return "default"

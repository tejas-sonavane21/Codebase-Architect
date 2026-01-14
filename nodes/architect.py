"""
Node 4: The Architect

Plans focused architectural diagrams based on the uploaded code.
Avoids "God Diagrams" by breaking into sub-modules.
"""

import json
from typing import Optional
from pocketflow import Node

from utils.gemini_client import GeminiClient


ARCHITECT_SYSTEM_PROMPT = """You are a Senior Software Architect specializing in system visualization.
Your task is to analyze a codebase and propose specific, focused architectural diagrams.

CRITICAL RULES:
1. DO NOT create "God Diagrams" with more than 15 classes/components
2. Break large systems into focused sub-modules (e.g., "Auth Module", "Payment Service")
3. Each diagram should have a clear, specific purpose
4. Suggest a mix of diagram types:
   - Class Diagrams: For OOP structures, inheritance, relationships
   - Sequence Diagrams: For important workflows and API flows
   - Component Diagrams: For high-level architecture
   - Entity-Relationship: For data models

Return your response as a JSON object with this structure:
{
    "project_summary": "Brief 1-2 sentence project description",
    "diagrams": [
        {
            "id": 1,
            "name": "Authentication Module Class Diagram",
            "type": "class",
            "focus": "Classes related to user authentication, JWT tokens, and session management",
            "files": ["auth.py", "models/user.py"],
            "complexity": "medium"
        },
        {
            "id": 2,
            "name": "Order Processing Sequence",
            "type": "sequence",
            "focus": "Flow from order creation through payment to fulfillment",
            "files": ["orders/service.py", "payments/processor.py"],
            "complexity": "high"
        }
    ]
}

Suggest 3-8 diagrams depending on project complexity.
Return ONLY the JSON object, no additional text."""


class ArchitectNode(Node):
    """Architect node that plans focused diagrams using LLM."""
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
    
    def prep(self, shared: dict) -> dict:
        """Gather context for diagram planning.
        
        Args:
            shared: Shared store with knowledge XML from Summarizer.
            
        Returns:
            Dict with context info.
        """
        # Use knowledge_uri from Summarizer (single distilled file)
        knowledge_uri = shared.get("knowledge_uri")
        knowledge_xml = shared.get("knowledge_xml", "")
        project_analysis = shared.get("project_analysis", "")
        
        if not knowledge_uri:
            # Fallback to old behavior if Summarizer didn't run
            uri_list = shared.get("uri_list", [])
            if not uri_list:
                raise ValueError("No knowledge or files available. Check SummarizerNode/UploaderNode.")
            return {
                "uri_list": uri_list,
                "knowledge_xml": "",
                "analysis": project_analysis,
                "use_knowledge": False,
            }
        
        self.client = GeminiClient()
        
        return {
            "knowledge_uri": knowledge_uri,  # {uri, mime_type}
            "knowledge_xml": knowledge_xml,
            "analysis": project_analysis,
            "use_knowledge": True,
        }
    
    def exec(self, prep_res: dict) -> dict:
        """Generate diagram plan using Gemini.
        
        Args:
            prep_res: Context with knowledge XML or fallback URIs.
            
        Returns:
            Parsed diagram plan.
        """
        print("📐 Planning architectural diagrams...")
        
        if prep_res.get("use_knowledge"):
            # Use the distilled codebase knowledge (efficient - single file)
            prompt = f"""Analyze the attached codebase_knowledge.xml file and propose focused architectural diagrams.

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

            response = self.client.generate_content(
                prompt=prompt,
                system_prompt=ARCHITECT_SYSTEM_PROMPT,
                file_uris=[prep_res["knowledge_uri"]],  # Single distilled file!
                temperature=0.5,
            )
        else:
            # Fallback: use raw file URIs (old behavior)
            prompt = f"""Based on the uploaded codebase files, analyze the architecture and propose focused diagrams.

Project Analysis: {prep_res['analysis']}

Consider:
1. What are the main modules/components?
2. What are the key workflows that should be visualized?
3. What data models exist and their relationships?
4. How do components interact with each other?

Propose specific, focused diagrams that would help a developer understand this codebase."""

            response = self.client.generate_content(
                prompt=prompt,
                system_prompt=ARCHITECT_SYSTEM_PROMPT,
                file_uris=prep_res.get("uri_list", []),
                temperature=0.5,
            )
        
        # Parse JSON response
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                lines = clean_response.split("\n")
                clean_response = "\n".join(lines[1:-1])
            
            plan = json.loads(clean_response)
            
            if "diagrams" not in plan:
                plan["diagrams"] = []
            
            print(f"   ✓ Planned {len(plan['diagrams'])} diagrams")
            
            for d in plan["diagrams"]:
                print(f"      [{d['id']}] {d['name']} ({d['type']})")
            
            return plan
            
        except json.JSONDecodeError as e:
            print(f"   ⚠ Failed to parse response: {e}")
            
            # Fallback: suggest basic diagrams
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
        """Store the diagram plan.
        
        Args:
            shared: Shared store.
            prep_res: Prep result.
            exec_res: Diagram plan.
            
        Returns:
            Action string for flow.
        """
        shared["diagram_plan"] = exec_res
        shared["all_diagrams"] = exec_res.get("diagrams", [])
        
        # Save plan to file
        import os
        clone_path = shared.get("clone_path", ".")
        plan_file = os.path.join(clone_path, "..", "diagram_plan.json")
        
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(exec_res, f, indent=2)
        
        print(f"📄 Diagram plan saved to: {plan_file}")
        
        return "default"

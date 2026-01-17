"""
Node 6: The Drafter

Generates PlantUML code for a specific diagram
using Gemini with code context.
"""

from typing import Optional
from pocketflow import Node

from utils.gemini_client import GeminiClient
from utils.rate_limiter import rate_limit_delay


DRAFTER_SYSTEM_PROMPT = """You are a Strict PlantUML Generator.
You do NOT speak English.
Return ONLY valid PlantUML code wrapped in @startuml and @enduml tags.

RULES:
1. Start with @startuml
2. End with @enduml
3. Use accurate class names and method signatures from the uploaded code
4. Keep diagrams focused - max 15 classes/components
5. Use proper PlantUML syntax
6. Add meaningful relationships and cardinalities
7. Include brief notes for complex parts

Do NOT include any explanatory text before or after the PlantUML code.
Return ONLY the PlantUML code."""


class DrafterNode(Node):
    """Drafter node that generates PlantUML code using LLM."""
    
    MAX_RETRIES = 3  # For self-correction loop
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client: Optional[GeminiClient] = None
    
    def prep(self, shared: dict) -> dict:
        """Get current diagram from queue.
        
        Args:
            shared: Shared store with diagram queue.
            
        Returns:
            Dict with current diagram info and any error context.
        """
        queue = shared.get("diagram_queue", [])
        current_idx = shared.get("current_diagram_index", 0)
        
        if current_idx >= len(queue):
            return {"done": True}
        
        current_diagram = queue[current_idx]
        error_context = shared.get("critic_error", None)
        retry_count = shared.get("retry_count", 0)
        
        # Use knowledge_uri (distilled XML) instead of uri_list (raw files)
        # This prevents 500 Internal Errors from too many file references
        knowledge_uri = shared.get("knowledge_uri")  # {uri, mime_type}
        
        # Clear error after reading
        if error_context:
            shared["critic_error"] = None
        
        self.client = GeminiClient()
        
        return {
            "done": False,
            "diagram": current_diagram,
            "error_context": error_context,
            "retry_count": retry_count,
            "knowledge_uri": knowledge_uri,
        }
    
    def exec(self, prep_res: dict) -> str:
        """Generate PlantUML code.
        
        Args:
            prep_res: Context with diagram info and optional error.
            
        Returns:
            PlantUML code string.
        """
        if prep_res.get("done"):
            return ""
        
        diagram = prep_res["diagram"]
        error_context = prep_res.get("error_context")
        retry_count = prep_res.get("retry_count", 0)
        
        diagram_name = diagram["name"]
        diagram_type = diagram["type"]
        focus = diagram["focus"]
        
        if retry_count > 0:
            print(f"🔄 Retry {retry_count}/{self.MAX_RETRIES} for: {diagram_name}")
        else:
            print(f"✏️  Drafting: {diagram_name}")
        
        # Build prompt
        prompt_parts = [
            f"Generate a {diagram_type.upper()} diagram in PlantUML format.",
            f"",
            f"Diagram Name: {diagram_name}",
            f"Focus: {focus}",
        ]
        
        if diagram.get("files"):
            prompt_parts.append(f"Relevant Files: {', '.join(diagram['files'])}")
        
        # Add error context if retrying
        if error_context:
            prompt_parts.extend([
                "",
                "PREVIOUS ATTEMPT FAILED. Fix these errors:",
                error_context,
                "",
                "Generate corrected PlantUML code.",
            ])
        
        prompt = "\n".join(prompt_parts)
        
        # Generate with knowledge context (single distilled file, not 15+ raw files)
        knowledge_uri = prep_res.get("knowledge_uri")
        file_uris = [knowledge_uri] if knowledge_uri else []
        
        response = self.client.generate_content(
            prompt=prompt,
            system_prompt=DRAFTER_SYSTEM_PROMPT,
            file_uris=file_uris,
            temperature=0.4,  # Lower for more consistent output
        )
        
        # Clean response
        code = self._clean_plantuml(response)
        
        print(f"   ✓ Generated {len(code.split(chr(10)))} lines of PlantUML")
        
        return code
    
    def _clean_plantuml(self, response: str) -> str:
        """Extract and clean PlantUML code from response."""
        text = response.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Find start and end of code block
            start_idx = 1
            end_idx = len(lines) - 1
            
            # Skip language identifier
            if lines[0].startswith("```"):
                start_idx = 1
            
            # Find closing ```
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip() == "```":
                    end_idx = i
                    break
            
            text = "\n".join(lines[start_idx:end_idx])
        
        # Ensure proper tags
        if "@startuml" not in text:
            text = "@startuml\n" + text
        if "@enduml" not in text:
            text = text + "\n@enduml"
        
        return text.strip()
    
    def post(self, shared: dict, prep_res: dict, exec_res: str) -> str:
        """Store generated code and proceed to critic.
        
        Args:
            shared: Shared store.
            prep_res: Prep result.
            exec_res: PlantUML code.
            
        Returns:
            Action string for flow.
        """
        if prep_res.get("done"):
            return "complete"
        
        shared["current_plantuml"] = exec_res
        shared["current_diagram_info"] = prep_res["diagram"]
        
        # Rate limit delay after diagram generation
        retry_count = prep_res.get("retry_count", 0)
        if retry_count > 0:
            # This was a retry, use shorter error cooldown
            rate_limit_delay("on_error")
        else:
            # Normal diagram generation
            rate_limit_delay("drafter_per_diagram")
        
        return "validate"

"""
Kroki API Client

Renders PlantUML diagrams to PNG using the public Kroki API.
"""

import requests
from typing import Tuple, Optional


class KrokiClient:
    """Client for the Kroki diagram rendering API."""
    
    BASE_URL = "https://kroki.io"
    TIMEOUT = 30  # seconds
    
    @classmethod
    def render_plantuml(cls, plantuml_code: str) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """Render PlantUML code to PNG.
        
        Args:
            plantuml_code: The PlantUML source code (including @startuml/@enduml).
            
        Returns:
            Tuple of (success, png_bytes, error_message).
            - On success: (True, bytes, None)
            - On failure: (False, None, error_string)
        """
        url = f"{cls.BASE_URL}/plantuml/png"
        
        headers = {
            "Content-Type": "text/plain",
        }
        
        try:
            response = requests.post(
                url,
                data=plantuml_code.encode("utf-8"),
                headers=headers,
                timeout=cls.TIMEOUT,
            )
            
            if response.status_code == 200:
                return True, response.content, None
            else:
                error_msg = f"Kroki API returned {response.status_code}: {response.text}"
                return False, None, error_msg
                
        except requests.exceptions.Timeout:
            return False, None, "Kroki API request timed out"
        except requests.exceptions.RequestException as e:
            return False, None, f"Kroki API request failed: {str(e)}"
    
    @classmethod
    def validate_syntax(cls, plantuml_code: str) -> Tuple[bool, Optional[str]]:
        """Validate PlantUML syntax before rendering.
        
        Args:
            plantuml_code: The PlantUML source code.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        # Check for required tags
        if "@startuml" not in plantuml_code:
            return False, "Missing @startuml tag"
        
        if "@enduml" not in plantuml_code:
            return False, "Missing @enduml tag"
        
        # Check order
        start_idx = plantuml_code.find("@startuml")
        end_idx = plantuml_code.find("@enduml")
        
        if start_idx > end_idx:
            return False, "@startuml must come before @enduml"
        
        return True, None
    
    @classmethod
    def analyze_complexity(cls, plantuml_code: str) -> dict:
        """Analyze diagram complexity for warnings.
        
        Args:
            plantuml_code: The PlantUML source code.
            
        Returns:
            Dict with line_count, class_count, and warnings.
        """
        lines = plantuml_code.strip().split("\n")
        line_count = len(lines)
        
        # Count class-like definitions
        class_keywords = ["class ", "interface ", "abstract ", "entity ", "enum "]
        class_count = sum(
            1 for line in lines 
            for kw in class_keywords 
            if line.strip().startswith(kw)
        )
        
        warnings = []
        if line_count > 100:
            warnings.append(f"Diagram has {line_count} lines (>100), may be too complex")
        if class_count > 20:
            warnings.append(f"Diagram has {class_count} classes (>20), consider splitting")
        
        return {
            "line_count": line_count,
            "class_count": class_count,
            "warnings": warnings,
        }

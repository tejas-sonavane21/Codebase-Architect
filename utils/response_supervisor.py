"""
Response Supervisor - Agentic Self-Correction

A multi-agent system where a Supervisor LLM reviews Worker LLM output
and provides intelligent, context-aware feedback for correction.

Agent 1 (Worker): Generates content (e.g., SummarizerNode)
Agent 2 (Supervisor): Reviews and critiques failures semantically
"""

import json
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Callable, Any

from utils.prompts import get_prompt, get_gem_id
from utils.output_cleaner import clean_json
from utils.console import console


class ResponseSupervisor:
    """
    Agentic supervisor that uses LLM to analyze and critique failed responses.
    
    Unlike hardcoded validation, this supervisor THINKS about what went wrong
    and crafts dynamic, context-aware critiques.
    """
    
    def __init__(self, client, max_retries: int = 10):
        """
        Initialize supervisor with Gemini client.
        
        Args:
            client: GeminiClient instance
            max_retries: Maximum correction attempts
        """
        self.client = client
        self.max_retries = max_retries
    
    def _basic_xml_check(self, text: str) -> tuple[bool, str]:
        """
        Minimal local check - just verify XML can parse.
        All semantic analysis is done by Supervisor LLM.
        
        Returns:
            (is_parseable, error_message)
        """
        try:
            ET.fromstring(text)
            return True, ""
        except ET.ParseError as e:
            return False, f"XMLParseError: {str(e)}"
    
    def _build_supervisor_prompt(
        self,
        worker_response: str,
        context: Dict[str, Any],
        parse_error: Optional[str] = None
    ) -> str:
        """
        Build the prompt for Supervisor LLM to analyze the failure.
        
        Args:
            worker_response: The potentially broken response
            context: Dict with previous_xml, batch_files, original_prompt
            parse_error: Optional parse error message
        """
        previous_xml = context.get("previous_xml", "")
        batch_files = context.get("batch_files", [])
        original_prompt = context.get("original_prompt", "")
        
        # Truncate large XMLs for context window
        prev_xml_preview = previous_xml[:3000] + "..." if len(previous_xml) > 3000 else previous_xml
        response_preview = worker_response[:3000] + "..." if len(worker_response) > 3000 else worker_response
        
        prompt = f"""Give me JSON code.

You are a SENIOR CODE REVIEWER analyzing an LLM's output.

=== CONTEXT ===
- Task: Build codebase knowledge XML by merging NEW file summaries into EXISTING XML.
- Previous XML size: {len(previous_xml)} characters
- Files sent in this batch: {batch_files}
{f'- Parse Error Detected: {parse_error}' if parse_error else ''}

=== PREVIOUS XML (Before This Batch) ===
```xml
{prev_xml_preview}
```

=== WORKER'S RESPONSE ===
```
{response_preview}
```

=== ORIGINAL PROMPT GIVEN TO WORKER ===
{original_prompt[:1500]}...

=== YOUR TASK ===
1. Analyze what went wrong semantically.
2. Determine if:
   - Data was LOST (files from previous XML missing)
   - Structure was CORRUPTED (malformed XML)
   - Content was INCOMPLETE (batch files not added)
   - Or if the response is actually VALID
3. Craft a SPECIFIC critique telling the Worker what to fix.

=== OUTPUT FORMAT ===
Return ONLY a JSON object:
{{
    "is_valid": true/false,
    "issues": ["Issue 1", "Issue 2"],
    "critique": "Detailed feedback for the worker..."
}}

If the response is valid, return: {{"is_valid": true, "issues": [], "critique": ""}}"""
        
        return prompt
    
    def _call_supervisor(
        self,
        worker_response: str,
        context: Dict[str, Any],
        parse_error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call Supervisor LLM to analyze the worker's response.
        
        Returns:
            Dict with is_valid, issues, critique
        """
        prompt = self._build_supervisor_prompt(worker_response, context, parse_error)
        
        gem_id = get_gem_id("supervisor")
        active_model = self.client.MODEL
        
        response = self.client.generate_content(
            prompt=prompt,
            system_prompt=None if gem_id else get_prompt("supervisor", active_model),
            model_override=active_model,
            gem_id=gem_id,
        )
        
        try:
            cleaned = clean_json(response)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Supervisor itself failed - assume invalid
            return {
                "is_valid": False,
                "issues": ["Supervisor analysis failed"],
                "critique": "Please ensure your response is valid XML with all required elements."
            }
    
    def local_validate_xml(self, text: str, context: Dict[str, Any]) -> tuple[bool, str]:
        """
        Local validation - faster than LLM.
        Checks: XML parsing, root tag, basic structure.
        
        Returns:
            (is_valid, error_message)
        """
        # Check 1: XML must parse
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            return False, f"XMLParseError: {str(e)}"
        
        # Check 2: Must have codebase_knowledge root
        if root.tag != "codebase_knowledge":
            return False, f"Wrong root tag: expected 'codebase_knowledge', got '{root.tag}'"
        
        # Check 3: Must have files section
        files_section = root.find("files")
        if files_section is None:
            return False, "Missing <files> section"
        
        return True, ""
    
    def supervise_xml(
        self,
        cleaned_response: str,
        context: Dict[str, Any],
        generate_with_critique_fn: Callable[[str], str]
    ) -> tuple[str, bool]:
        """
        Supervise XML response with optimized flow:
        1. Local validation (fast)
        2. If valid → return immediately (no LLM)
        3. If invalid → call Supervisor LLM for critique → retry
        
        Args:
            cleaned_response: ALREADY CLEANED response (markdown stripped)
            context: Dict with previous_xml, batch_files, original_prompt
            generate_with_critique_fn: Function that generates with critique appended
            
        Returns:
            (final_response, success)
        """
        attempt = 0
        current_response = cleaned_response
        last_critique = ""
        
        while attempt < self.max_retries:
            attempt += 1
            
            # Local validation first (fast, no LLM)
            is_valid, local_error = self.local_validate_xml(current_response, context)
            
            if is_valid:
                console.debug(f"Validation passed (attempt {attempt})", indent=2)
                return current_response, True
            
            console.debug(f"Validation failed: {local_error[:60]}...", indent=2)
            
            # Local failed → call Supervisor LLM for semantic analysis
            console.debug("Supervisor analyzing failure...", indent=2)
            analysis = self._call_supervisor(current_response, context, local_error)
            
            # Get critique from LLM
            last_critique = analysis.get("critique", f"Fix error: {local_error}")
            issues = analysis.get("issues", [])
            for issue in issues[:2]:
                console.debug(f"Issue: {issue[:50]}...", indent=2)
            
            if attempt < self.max_retries:
                console.debug(f"Retrying ({attempt + 1}/{self.max_retries})...", indent=2)
                try:
                    # Generate new response with critique
                    current_response = generate_with_critique_fn(last_critique)
                except Exception as e:
                    console.debug(f"Retry failed: {str(e)[:60]}", indent=2)
                    continue
        
        # Max retries exhausted
        console.warning(f"Supervisor: Max retries ({self.max_retries}) exhausted", indent=2)
        return current_response, False


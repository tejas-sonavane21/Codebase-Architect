"""
Output Cleaner for Gemini Web API Responses

Centralizes cleaning logic for all outputs from gemini_webapi.
The Gemini web interface returns markdown-formatted responses with
escaped characters that need to be cleaned before parsing.

Supported output types:
- generic: Basic escape cleaning
- xml: XML-specific cleaning (codebase_knowledge.xml)
- json: JSON-specific cleaning (upload_config.json, diagram_plan.json)
- plantuml: PlantUML-specific cleaning
"""

import re
from typing import Optional


def clean_gemini_output(text: str, output_type: str = "generic") -> str:
    """
    Clean Gemini web API output by removing markdown artifacts and escaped characters.
    
    Args:
        text: Raw response from Gemini web API
        output_type: One of 'generic', 'xml', 'json', 'plantuml'
        
    Returns:
        Cleaned text ready for parsing
    """
    if not text:
        return ""
    
    text = text.strip()
    
    # Step 1: Remove markdown code blocks
    text = _strip_markdown_blocks(text, output_type)
    
    # Step 2: Fix escaped characters (common to all types)
    text = _unescape_characters(text)
    
    # Step 3: Apply type-specific cleaning
    if output_type == "xml":
        text = _clean_xml_specific(text)
    elif output_type == "json":
        text = _clean_json_specific(text)
    elif output_type == "plantuml":
        text = _clean_plantuml_specific(text)
    
    return text.strip()


def _strip_markdown_blocks(text: str, output_type: str) -> str:
    """Remove markdown code block fences."""
    if "```" not in text:
        return text
    
    # Try regex pattern for code blocks
    # Matches ```lang or ``` followed by content and closing ```
    patterns = [
        r"```(?:plantuml|xml|json|javascript|python)?\s*\n(.*?)\s*```",
        r"```\s*\n(.*?)\s*```",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Fallback: manual line stripping
    lines = text.split("\n")
    if len(lines) >= 2 and lines[0].strip().startswith("```"):
        # Remove first line
        lines = lines[1:]
        # Remove last line if it's closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    
    return text


def _unescape_characters(text: str) -> str:
    """Remove backslash escapes from special characters."""
    # Direct replacements for common escapes
    replacements = [
        (r"\<", "<"),
        (r"\>", ">"),
        (r"\_", "_"),
        (r"\[", "["),
        (r"\]", "]"),
        (r"\!", "!"),
        (r"\#", "#"),
        (r"\-", "-"),
        (r"\*", "*"),
        (r"\`", "`"),
        (r"\'", "'"),
        (r'\"', '"'),
    ]
    
    for escaped, unescaped in replacements:
        text = text.replace(escaped, unescaped)
    
    # Handle multiple backslashes before special chars
    # Matches \\+ followed by special char, replaces with just the char
    text = re.sub(r'\\+([<>_\[\]!#\-*`\'"])', r'\1', text)
    
    return text


def _clean_xml_specific(text: str) -> str:
    """XML-specific cleaning."""
    # Ensure we have the main XML tags
    # If content doesn't start with < after cleaning, it might have preamble
    if not text.startswith("<"):
        # Find first XML tag
        match = re.search(r'<[a-zA-Z_]', text)
        if match:
            text = text[match.start():]
    
    return text


def _clean_json_specific(text: str) -> str:
    """JSON-specific cleaning."""
    # Find the JSON object/array boundaries
    # JSON must start with { or [
    
    if not text.startswith(("{", "[")):
        # Find first { or [
        brace_idx = text.find("{")
        bracket_idx = text.find("[")
        
        if brace_idx == -1 and bracket_idx == -1:
            return text  # No JSON found
        
        if brace_idx == -1:
            start = bracket_idx
        elif bracket_idx == -1:
            start = brace_idx
        else:
            start = min(brace_idx, bracket_idx)
        
        text = text[start:]
    
    # Find matching end
    if text.startswith("{"):
        # Object - find last }
        last_brace = text.rfind("}")
        if last_brace != -1:
            text = text[:last_brace + 1]
    elif text.startswith("["):
        # Array - find last ]
        last_bracket = text.rfind("]")
        if last_bracket != -1:
            text = text[:last_bracket + 1]
    
    return text


def _clean_plantuml_specific(text: str) -> str:
    """PlantUML-specific cleaning."""
    # Ensure @startuml and @enduml exist
    if "@startuml" not in text:
        text = "@startuml\n" + text
    if "@enduml" not in text:
        text = text + "\n@enduml"
    
    # Extract only the content between markers if there's extra text
    start_match = re.search(r'@startuml', text)
    end_match = re.search(r'@enduml', text)
    
    if start_match and end_match:
        text = text[start_match.start():end_match.end()]
    
    return text


# Convenience functions for specific output types
def clean_xml(text: str) -> str:
    """Clean XML output from Gemini."""
    return clean_gemini_output(text, "xml")


def clean_json(text: str) -> str:
    """Clean JSON output from Gemini."""
    return clean_gemini_output(text, "json")


def clean_plantuml(text: str) -> str:
    """Clean PlantUML output from Gemini."""
    return clean_gemini_output(text, "plantuml")

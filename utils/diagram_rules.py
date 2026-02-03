"""
Diagram Rules Manager

Provides isolated, per-diagram-type PlantUML generation rules.
Only the relevant rules are passed to Gemma for focused generation.

Usage:
    from utils.diagram_rules import get_diagram_rules
    
    rules = get_diagram_rules("class")  # Returns only class diagram rules
"""

from typing import Optional


# ============================================
# DIAGRAM-SPECIFIC RULES
# ============================================
# Each diagram type has its own isolated ruleset.
# Rules are detailed with WRONG/RIGHT examples to guide Gemma.

DIAGRAM_RULES = {
    "class": """=== CLASS DIAGRAM RULES ===
1. VISIBILITY: `+` public, `#` protected, `-` private.
2. TYPES: Include return types and parameter types when available.
3. ABSTRACT: Mark abstract classes/methods with `{abstract}`.
4. INHERITANCE: Use ONLY ONE style per relationship. Never both.
   WRONG: class Child extends Parent ... Parent <|-- Child (DUPLICATE!)
   RIGHT: class Child extends Parent (no separate arrow)
   RIGHT: class Parent ... class Child ... Parent <|-- Child (no extends keyword)
5. COMPLETENESS: If showing a hierarchy, include ALL classes that extend the base.
6. NOTES: Add `note` blocks to explain complex logic or design patterns.""",

    "component": """=== COMPONENT DIAGRAM RULES ===
1. STRUCTURE: Use `component "Name" as Alias`. Components CANNOT contain text.
   WRONG: component "Flow" { Uses PocketFlow }
   WRONG: component "Nodes" { Includes ScoutNode }
   RIGHT: component "Flow" as Flow
   RIGHT: component "Nodes" as Nodes
2. GROUPING: Define components INSIDE the package, not outside then reference.
   WRONG: component "Flow" as Flow ... package "App" { Flow }
   RIGHT: package "App" { component "Flow" as Flow }
3. DESCRIPTIONS: Use `note right of Alias` for descriptions.
   RIGHT: note right of Flow : Uses PocketFlow framework
4. LABELS: All arrows must have SPECIFIC labels (method names, data types), not generic "uses".
5. EXTERNAL SYSTEMS: For external APIs/services, use simple component names without internal structure.""",

    "sequence": """=== SEQUENCE DIAGRAM RULES ===
1. ACTOR REQUIRED: Every sequence diagram MUST start with an `actor "User"` or equivalent initiator.
2. PARTICIPANTS: Use actual class names from user code. `participant "ClassName" as Alias`.
3. DECLARE BEFORE USE: Every participant MUST be declared before using in arrows.
   WRONG: A -> UndeclaredAPI : call (ERROR: UndeclaredAPI not defined!)
   RIGHT: participant "ExternalAPI" as API / A -> API : call
4. LIBRARY EXCLUSION: Do NOT create participants for standard library modules (`argparse`, `asyncio`, `os`, `sys`, `json`, `logging`, `re`, `time`) OR third-party libraries (`aiohttp`, `requests`, `BeautifulSoup`, `bs4`, `httpx`). These are implementation details, not architecture.
5. ARROWS: Label every arrow with the method call or action: `A -> B : search(query)`.
6. CONTROL FLOW:
   - `alt/else/end` for conditionals.
   - `loop/end` for iterations.
   - `par/end par` for concurrent execution.
7. VISUAL POLISH: Use activation colors to distinguish phases: `activate VS #LightBlue`, `activate VS #LightGreen`.
8. COMPLETENESS: If the diagram involves N similar components, show ALL of them, not just one representative.
9. NOTES: Annotate important steps with `note right` explaining the logic.
10. ONE WORKFLOW: Show only ONE class/component's workflow per diagram. Do NOT merge unrelated workflows.
11. SIMPLICITY: When in doubt, simplify. Remove complex constructs rather than risk invalid syntax.""",

    "activity": """=== ACTIVITY DIAGRAM RULES ===
1. START/END: Use `start` and `stop` keywords.
2. ACTIONS: Use `:Action description;` syntax.
3. DECISIONS: Use `if (condition?) then (yes)` / `else (no)` / `endif`.
4. LOOPS: Use ONLY `repeat` / `repeat while (condition)` for loops.
   WRONG: -> LabelName; (broken goto - creates dangling arrow)
   WRONG: repeat for each item (INVALID SYNTAX!)
   RIGHT: repeat / :action; / repeat while (condition) is true
5. ANNOTATIONS: Add `note right` after decision branches to explain logic.
6. PARALLEL: Use `fork` and `end fork` for concurrent activities.
7. SWIMLANE ORDERING: If using swimlanes, define them BEFORE `start` or any actions.
   WRONG: start / :action; / |Swimlane| (swimlane AFTER actions = ERROR!)
   RIGHT: |Swimlane| / start / :action; (swimlane FIRST)
8. NO ORPHAN SWIMLANES: Do NOT add disconnected swimlane blocks at the end of the diagram.
9. SPECIFICITY: Inside actions, mention specific methods or values when known.
10. SIMPLICITY: When in doubt, simplify. Remove complex nested structures rather than risk invalid syntax.""",

    "state": """=== STATE DIAGRAM RULES ===
1. STATES: Use `state "StateName" as Alias`.
2. TRANSITIONS: Label with trigger/condition: `State1 --> State2 : event`.
3. INITIAL/FINAL: Use `[*] --> FirstState` and `LastState --> [*]`.
4. NESTED: Use `state ParentState { ... }` for composite states.""",

    "usecase": """=== USE CASE DIAGRAM RULES ===
1. ACTORS: Use `actor "ActorName" as Alias`.
2. USE CASES: Use `usecase "Action" as UC1`.
3. RELATIONSHIPS: `Actor --> UseCase` for associations.
4. BOUNDARIES: Use `rectangle "System" { ... }` to define system scope.""",
}


# ============================================
# RULES FACTORY
# ============================================
def get_diagram_rules(diagram_type: str) -> str:
    """
    Get the rules for a specific diagram type.
    
    Args:
        diagram_type: The type of diagram (class, component, sequence, activity, state, usecase)
        
    Returns:
        String containing the rules for that diagram type, or empty string if not found.
    """
    # Normalize the type (lowercase, handle common variations)
    normalized = diagram_type.lower().strip()
    
    # Handle common variations
    type_mapping = {
        "class": "class",
        "class diagram": "class",
        "component": "component",
        "component diagram": "component",
        "sequence": "sequence",
        "sequence diagram": "sequence",
        "activity": "activity",
        "activity diagram": "activity",
        "state": "state",
        "state diagram": "state",
        "usecase": "usecase",
        "use case": "usecase",
        "use case diagram": "usecase",
    }
    
    mapped_type = type_mapping.get(normalized, normalized)
    return DIAGRAM_RULES.get(mapped_type, "")


def get_all_diagram_types() -> list:
    """Return list of all supported diagram types."""
    return list(DIAGRAM_RULES.keys())

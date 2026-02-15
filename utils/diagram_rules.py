"""
Diagram Rules Manager

Provides isolated, per-diagram-type PlantUML generation rules.
All rules have ZERO-TOLERANCE enforcement with TERMINATION language.
Creative freedom WITHIN strict boundaries.

Usage:
    from utils.diagram_rules import get_diagram_rules
    
    rules = get_diagram_rules("class")  # Returns only class diagram rules
"""

from typing import Optional


# ============================================
# DIAGRAM-SPECIFIC RULES - MAXIMUM ENFORCEMENT
# ============================================

DIAGRAM_RULES = {
    # ==========================================================
    # CLASS DIAGRAM RULES
    # ==========================================================
    "class": """=== CLASS DIAGRAM RULES ===

=== STRUCTURE (MANDATORY) ===
@startuml
!theme blueprint
' Class definitions first
class "FullClassName" as Alias {
    +publicMethod(): ReturnType
    #protectedMethod(): ReturnType
    -privateMethod(): ReturnType
}
' Relationships after all classes defined
ParentAlias <|-- ChildAlias : extends
@enduml

=== VISIBILITY MARKERS ===
+ public
# protected
- private
~ package-private

=== NAMING RULES (ZERO TOLERANCE) ===
Use FULL class names exactly as they appear in codebase_knowledge.xml.
CORRECT: class "PaymentProcessor" as PaymentProcessor
CORRECT: class "BaseHandler" as BaseHandler
WRONG: class "PP" (abbreviation = TERMINATION)
WRONG: class "Handler" (too generic = TERMINATION)

=== INHERITANCE RULES ===
Define inheritance ONCE using either:
- OPTION A: class Child extends Parent { } (inline)
- OPTION B: Parent <|-- Child (arrow)
NEVER BOTH = duplicate relationship = TERMINATION

=== COMPOSITION/AGGREGATION ===
- Composition (owns): ClassA *-- ClassB : contains
- Aggregation (uses): ClassA o-- ClassB : has
- Dependency: ClassA ..> ClassB : uses
- Association: ClassA --> ClassB : calls

=== COMPLETENESS ===
If base class has N subclasses, show ALL N subclasses.
Showing only 2 of 5 handlers = INCOMPLETE = TERMINATION

=== LABELS ===
Every relationship arrow MUST have a label describing the relationship.
WRONG: Parent <|-- Child (no label)
RIGHT: Parent <|-- Child : extends""",

    # ==========================================================
    # COMPONENT DIAGRAM RULES
    # ==========================================================
    "component": """=== COMPONENT DIAGRAM RULES ===

=== STRUCTURE (MANDATORY) ===
@startuml
!theme blueprint
package "PackageName" {
    component "ComponentName" as Alias
}
Alias1 --> Alias2 : relationship
@enduml

=== COMPONENT DEFINITION ===
Use FULL component names exactly as they appear in codebase_knowledge.xml.
CORRECT: component "OrderService" as OrderService
WRONG: component "OS" as OS (abbreviation = TERMINATION)

=== GROUPING RULES ===
Define components INSIDE packages, not outside then reference.
WRONG: component "Flow" as Flow ... package "App" { Flow }
RIGHT: package "App" { component "Flow" as Flow }

=== RELATIONSHIP LABELS (MANDATORY) ===
Every arrow MUST have a specific label:
- What method is called
- What data flows
- What event triggers

WRONG: A --> B (no label = TERMINATION)
RIGHT: OrderService --> PaymentGateway : processPayment()
RIGHT: DataExporter --> FileWriter : saveToFile()

=== NOTES ===
Use notes for important context:
note right of ComponentAlias : Description of purpose

=== COMPLETENESS ===
A component diagram with components but NO relationships = WORTHLESS = TERMINATION
Every diagram must show at least 2 meaningful relationships.""",

    # ==========================================================
    # SEQUENCE DIAGRAM RULES
    # ==========================================================
    "sequence": """=== SEQUENCE DIAGRAM RULES ===

=== STRUCTURE (MANDATORY - EXACT ORDER) ===
@startuml
!theme blueprint
' === DECLARATIONS (ALL participants before ANY arrows) ===
actor "User" as User
participant "FullClassName1" as Alias1
participant "FullClassName2" as Alias2

' === INTERACTIONS (only after ALL declarations) ===
User -> Alias1 : methodCall()
activate Alias1
Alias1 -> Alias2 : anotherMethod()
Alias2 --> Alias1 : returnValue
deactivate Alias1
@enduml

=== DECLARATION RULES (ZERO TOLERANCE) ===
EVERY alias used in arrows MUST be declared first.
Using undeclared alias = SYNTAX ERROR = TERMINATION

WRONG:
XS -> YH : action (XS and YH not declared = TERMINATION)

CORRECT:
participant "OrderController" as OrderController
participant "InventoryService" as InventoryService
OrderController -> InventoryService : checkStock(itemId)

=== NAMING RULES (ZERO TOLERANCE) ===
Use FULL class names from codebase_knowledge.xml:
CORRECT: participant "AuthenticationService" as AuthenticationService
WRONG: participant "AS" as AS (abbreviation = TERMINATION)
WRONG: participant "Service" as Service (too generic = TERMINATION)

=== ARROW LABELS (MANDATORY) ===
Every arrow MUST have a method call or action:
CORRECT: Client -> Server : sendRequest(payload)
CORRECT: Server --> Client : responseData
WRONG: Client -> Server (no label = TERMINATION)

=== FORBIDDEN PARTICIPANTS ===
NEVER include standard library or third-party as participants:
FORBIDDEN: json, os, sys, logging, requests, aiohttp, BeautifulSoup, httpx, certifi, asyncio
These are implementation details, not architecture.

=== CONTROL FLOW ===
- Conditions: alt / else / end
- Loops: loop / end
- Activation: activate Alias / deactivate Alias

=== COMPLETENESS ===
- Show the COMPLETE flow from trigger to result
- Minimum 5 interactions for a meaningful sequence
- A 3-line sequence diagram = INCOMPLETE = TERMINATION""",

    # ==========================================================
    # ACTIVITY DIAGRAM RULES
    # ==========================================================
    "activity": """=== ACTIVITY DIAGRAM RULES ===

=== STRUCTURE (MANDATORY) ===
@startuml
!theme blueprint
start
:First action;
if (condition?) then (yes)
    :Action if true;
else (no)
    :Action if false;
endif
:Final action;
stop
@enduml

=== START/END ===
MUST begin with: start
MUST end with: stop (normal) or end (error/exception)

=== ACTIONS ===
Use colon-semicolon syntax: :Action description;
CORRECT: :Parse input parameters;
CORRECT: :Process all pending requests;

=== DECISIONS ===
CORRECT syntax:
if (condition?) then (yes)
    :action;
else (no)
    :action;
endif

=== LOOPS ===
ONLY use repeat/repeat while syntax:
repeat
    :action;
repeat while (condition?) is (true)

WRONG: for each item (INVALID SYNTAX = TERMINATION)
WRONG: -> label (creates broken arrow = TERMINATION)

=== SWIMLANES ===
If using swimlanes, define BEFORE start:
|Swimlane1|
start
:action;

WRONG: start / :action; / |Swimlane| (swimlane after start = ERROR)

=== FORK/JOIN ===
For parallel activities:
fork
    :Parallel action 1;
fork again
    :Parallel action 2;
end fork

=== COMPLETENESS ===
Show the COMPLETE workflow from start to stop.
An activity diagram with < 5 actions = INCOMPLETE = TERMINATION""",

    # ==========================================================
    # STATE DIAGRAM RULES
    # ==========================================================
    "state": """=== STATE DIAGRAM RULES ===

=== STRUCTURE (MANDATORY) ===
@startuml
!theme blueprint
[*] --> InitialState : trigger
state "StateName" as Alias {
    Alias : entry / action
    Alias : exit / action
}
StateName --> NextState : event
FinalState --> [*]
@enduml

=== STATE DEFINITION ===
CORRECT: state "Idle" as Idle
CORRECT: state "Processing" as Processing

=== TRANSITIONS ===
Every transition MUST have a trigger/event label:
CORRECT: Idle --> Processing : start_requested
WRONG: Idle --> Processing (no trigger = TERMINATION)

=== INITIAL/FINAL ===
[*] --> FirstState : initialization
LastState --> [*] : completion

=== NESTED STATES ===
state ParentState {
    state ChildState1
    state ChildState2
}

=== COMPLETENESS ===
Show ALL states an object can be in, not just main ones.
A state diagram with < 3 states = TOO SIMPLE = TERMINATION""",

    # ==========================================================
    # USE CASE DIAGRAM RULES
    # ==========================================================
    "usecase": """=== USE CASE DIAGRAM RULES ===

=== STRUCTURE (MANDATORY) ===
@startuml
!theme blueprint
actor "ActorName" as Actor
rectangle "System Boundary" {
    usecase "Action Description" as UC1
    usecase "Another Action" as UC2
}
Actor --> UC1
UC1 ..> UC2 : <<include>>
@enduml

=== ACTORS ===
CORRECT: actor "Security Analyst" as Analyst
CORRECT: actor "CLI User" as User
WRONG: actor "U" (abbreviation = TERMINATION)

=== USE CASES ===
CORRECT: usecase "Create New Order" as UC1
CORRECT: usecase "Generate Report" as UC2

=== RELATIONSHIPS ===
- Association: Actor --> UseCase
- Include: UC1 ..> UC2 : <<include>>
- Extend: UC2 ..> UC1 : <<extend>>

=== SYSTEM BOUNDARY ===
Use rectangle to show system scope:
rectangle "Application System" {
    usecase "Primary Action" as UC1
}

=== COMPLETENESS ===
Show ALL major use cases, not just one.
A use case diagram with < 3 use cases = INCOMPLETE = TERMINATION""",

    # ==========================================================
    # ER (ENTITY-RELATIONSHIP) DIAGRAM RULES
    # ==========================================================
    "er": """=== ER (ENTITY-RELATIONSHIP) DIAGRAM RULES ===

=== STRUCTURE (MANDATORY) ===
@startuml
!theme blueprint
entity "EntityName" as Alias {
    *primary_key : type <<PK>>
    --
    attribute1 : type
    attribute2 : type
}

Entity1 ||--o{ Entity2 : relationship_label
@enduml

=== ENTITY DEFINITION ===
Use FULL entity names as they appear in codebase_knowledge.xml.
CORRECT: entity "Customer" as Customer
CORRECT: entity "OrderItem" as OrderItem
WRONG: entity "C" as C (abbreviation = TERMINATION)

=== ATTRIBUTE SYNTAX ===
* marks primary key
-- separates primary keys from other attributes
Optional: <<PK>>, <<FK>>, <<unique>>

Example:
entity "UserAccount" as User {
    *user_id : int <<PK>>
    --
    username : varchar
    email : varchar <<unique>>
    created_at : timestamp
}

=== RELATIONSHIP CARDINALITY ===
Use crow's foot notation:
- ||--|| : one to one
- ||--o{ : one to many
- }o--o{ : many to many
- ||--o| : one to zero or one

CORRECT: User ||--o{ Order : places
CORRECT: Order }o--o{ Product : contains
WRONG: User -- Order (no cardinality = TERMINATION)

=== RELATIONSHIP LABELS (MANDATORY) ===
Every relationship MUST have a descriptive label:
CORRECT: Customer ||--o{ Order : places
WRONG: Customer ||--o{ Order (no label = TERMINATION)

=== COMPLETENESS ===
Show ALL entities and their relationships.
An ER diagram with < 3 entities = TOO SIMPLE = TERMINATION""",

    # ==========================================================
    # DFD (DATA FLOW DIAGRAM) RULES - WITH STRIDE THREAT MODEL
    # ==========================================================
    "dfd": """=== DFD (DATA FLOW DIAGRAM) RULES ===

=== CRITICAL: USE @startuml NOT @startdfd ===
PlantUML does NOT support @startdfd. You MUST use @startuml.
Using @startdfd = SYNTAX ERROR = RENDER FAILURE = TERMINATION

=== STRUCTURE (MANDATORY) ===
@startuml
!theme blueprint
title Data Flow Diagram - [System Name]

' === EXTERNAL ENTITIES (actors/systems outside trust boundary) ===
actor "ExternalEntity" as EE1

' === TRUST BOUNDARIES (dashed rectangles) ===
rectangle "Trust Boundary Name" #line.dashed {
    ' === PROCESSES (components inside boundary) ===
    component "ProcessName" as P1
    
    ' === DATA STORES ===
    database "DataStoreName" as DS1
}

' === DATA FLOWS (labeled arrows) ===
EE1 --> P1 : data_description
P1 --> DS1 : store(data)
DS1 --> P1 : retrieve(data)

' === STRIDE ANNOTATIONS (notes on boundary crossings) ===
note on link
    **STRIDE**: Spoofing, Tampering
    Crosses trust boundary: validate input
end note

@enduml

=== ELEMENT TYPES ===
1. EXTERNAL ENTITY: actor or rectangle OUTSIDE all trust boundaries
   - Users, external APIs, third-party services
   CORRECT: actor "CLI User" as User
   CORRECT: rectangle "External API" as ExtAPI

2. PROCESS: component INSIDE a trust boundary
   - Application logic, services, handlers
   CORRECT: component "AuthenticationService" as AuthService
   WRONG: component "AS" (abbreviation = TERMINATION)

3. DATA STORE: database element
   - Databases, file systems, caches, session stores
   CORRECT: database "UserDatabase" as UserDB
   CORRECT: database "SessionCache" as Cache

4. TRUST BOUNDARY: dashed rectangle grouping related processes
   CORRECT: rectangle "Internal Network" #line.dashed { ... }
   CORRECT: rectangle "DMZ" #line.dashed { ... }
   WRONG: rectangle "Boundary" (too generic = TERMINATION)

=== TRUST BOUNDARY RULES (MANDATORY) ===
Every DFD MUST have at least 2 trust boundaries, for example:
- "External/Untrusted Zone" (users, external APIs)
- "Application Layer" (web server, API handlers)
- "Data Layer" (databases, file stores)
- "Internal Services" (background workers, message queues)

=== DATA FLOW RULES (MANDATORY) ===
Every arrow MUST be labeled with what data flows:
CORRECT: User --> WebApp : HTTP Request (credentials)
CORRECT: WebApp --> Database : SQL Query (user_id)
CORRECT: Database --> WebApp : ResultSet (user_record)
WRONG: User --> WebApp (no label = TERMINATION)
WRONG: A --> B : "data" (too vague = TERMINATION)

=== STRIDE THREAT ANNOTATIONS (MANDATORY) ===
Every data flow that CROSSES a trust boundary MUST have a STRIDE note.
Use "note on link" syntax attached to boundary-crossing arrows.

STRIDE Categories (annotate ALL that apply):
- **S**poofing: Can the source be impersonated? (auth entry points)
- **T**ampering: Can the data be modified in transit? (user inputs)
- **R**epudiation: Can the action be denied? (logging gaps)
- **I**nformation Disclosure: Can data leak? (error messages, responses)
- **D**enial of Service: Can the flow be overwhelmed? (public endpoints)
- **E**levation of Privilege: Can access controls be bypassed? (auth checks)

Example STRIDE note:
User --> WebApp : login(username, password)
note on link
    **STRIDE**: S, T, D
    Spoofing: Credential stuffing
    Tampering: Parameter injection
    DoS: Brute-force attempts
end note

=== NAMING RULES (ZERO TOLERANCE) ===
Use FULL names from codebase_knowledge.xml.
CORRECT: component "PaymentProcessor" as PaymentProcessor
WRONG: component "PP" as PP (abbreviation = TERMINATION)

=== COMPLETENESS ===
- Minimum 2 trust boundaries
- Minimum 3 data flows
- At least 1 STRIDE annotation on a boundary-crossing flow
- A DFD with no trust boundaries = NOT A DFD = TERMINATION
- A DFD with no STRIDE notes = MISSING THREAT ANALYSIS = TERMINATION""",
}


# ============================================
# RULES FACTORY
# ============================================
def get_diagram_rules(diagram_type: str) -> str:
    """
    Get the rules for a specific diagram type.
    
    Args:
        diagram_type: The type of diagram (class, component, sequence, activity, state, usecase, er, dfd)
        
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
        "er": "er",
        "entity-relationship": "er",
        "entity relationship": "er",
        "erd": "er",
        "er diagram": "er",
        "dfd": "dfd",
        "data flow": "dfd",
        "data flow diagram": "dfd",
        "dataflow": "dfd",
    }
    
    mapped_type = type_mapping.get(normalized, normalized)
    return DIAGRAM_RULES.get(mapped_type, "")


def get_all_diagram_types() -> list:
    """Return list of all supported diagram types."""
    return list(DIAGRAM_RULES.keys())

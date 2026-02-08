"""
Flow Orchestration

Wires all PocketFlow nodes into a Directed Acyclic Graph (DAG)
with conditional transitions and self-correction loops.
"""

from pocketflow import Flow

from utils.console import console
from nodes.scout import ScoutNode
from nodes.surveyor import SurveyorNode
from nodes.uploader import UploaderNode
from nodes.summarizer import SummarizerNode
from nodes.architect import ArchitectNode
from nodes.human_handshake import HumanHandshakeNode
from nodes.drafter import DrafterNode
from nodes.critic import CriticNode
from nodes.audit import AuditNode


def create_diagram_generation_flow() -> Flow:
    """Create the main diagram generation flow.
    
    Flow Structure:
    ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
    │  Scout  │───▶│ Surveyor │───▶│ Uploader │───▶│ Architect │
    └─────────┘    └──────────┘    └──────────┘    └───────────┘
                                                         │
                                                         ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    Human Handshake                           │
    │                  (Interactive Selection)                     │
    └─────────────────────────────────────────────────────────────┘
                             │
                             ▼ (default)
    ┌─────────────────────────────────────────────────────────────┐
    │                 Diagram Generation Loop                      │
    │  ┌─────────┐  validate  ┌────────┐  retry   ┌─────────┐    │
    │  │ Drafter │──────────▶│ Critic │─────────▶│ Drafter │    │
    │  └─────────┘            └────────┘          └─────────┘    │
    │       ▲                      │ next                         │
    │       │                      │                              │
    │       └──────────────────────┼──────────────────────────────│
    │                              ▼                              │
    │                         Next Diagram                        │
    └─────────────────────────────────────────────────────────────┘
                             │
                             ▼ (complete)
                    ┌───────────────┐
                    │   AuditNode   │ (Post-Generation Audit)
                    └───────────────┘
    
    Returns:
        Configured PocketFlow Flow.
    """
    # Create node instances
    scout = ScoutNode()
    surveyor = SurveyorNode()
    uploader = UploaderNode()
    summarizer = SummarizerNode()
    architect = ArchitectNode()
    handshake = HumanHandshakeNode()
    drafter = DrafterNode()
    critic = CriticNode()
    audit = AuditNode()
    
    # Wire the main pipeline
    # Scout -> Surveyor -> Uploader -> Summarizer -> Architect -> Handshake
    scout >> surveyor >> uploader >> summarizer >> architect >> handshake
    
    # Handshake -> Drafter (on "default" action, user selected diagrams)
    handshake.next(drafter, "default")
    
    # Handshake -> End (on "quit" action, user cancelled)
    # (No successor means flow ends)
    
    # Drafter -> Critic (on "validate" action)
    drafter.next(critic, "validate")
    
    # Drafter -> AuditNode (on "complete" action, all diagrams done)
    drafter.next(audit, "complete")
    
    # Self-correction loop:
    # Critic -> Drafter (on "retry" action, diagram failed validation)
    critic.next(drafter, "retry")
    
    # Critic -> Drafter (on "next" action, move to next diagram)
    critic.next(drafter, "next")
    
    # Create the flow starting from Scout
    flow = Flow(start=scout)
    
    return flow


def run_flow(repo_url: str, output_dir: str = "generated_diagrams") -> dict:
    """Run the complete diagram generation flow.
    
    Args:
        repo_url: GitHub repository URL to analyze.
        output_dir: Directory to save generated diagrams.
        
    Returns:
        Dict with results including generated diagram paths.
    """
    # Create the flow
    flow = create_diagram_generation_flow()
    
    # Initialize shared store
    import os
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    shared = {
        "repo_url": repo_url,
        "output_dir": output_dir,
        "project_root": project_root,
    }
    
    console.header("CODEBASE ARCHITECT")
    console.info(f"Repository: {repo_url}")
    console.info(f"Output: {output_dir}/")
    console.blank()
    
    try:
        # Run the flow
        flow.run(shared)
        
        # Collect results
        generated = shared.get("generated_diagrams", [])
        
        console.section("Generation Complete")
        
        if generated:
            console.success(f"Generated {len(generated)} diagram(s):", indent=1)
            for diag in generated:
                console.item(f"{diag['name']}", indent=2)
                console.item(f"PNG: {diag['png_path']}", indent=3)
        else:
            console.warning("No diagrams were generated.", indent=1)
        
        # Cleanup temp files
        scout_node = ScoutNode()
        scout_node.cleanup(shared)
        
        return {
            "success": True,
            "diagrams": generated,
            "output_dir": output_dir,
        }
        
    except Exception as e:
        console.error(f"Error during flow execution: {e}")
        
        # Attempt cleanup
        try:
            scout_node = ScoutNode()
            scout_node.cleanup(shared)
        except:
            pass
        
        return {
            "success": False,
            "error": str(e),
        }

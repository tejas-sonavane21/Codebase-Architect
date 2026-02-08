"""
Node 5: Human Handshake

Interactive CLI node that displays the diagram plan
and lets the user select which diagrams to generate.
"""

from typing import List
from pocketflow import Node
from utils.console import console


class HumanHandshakeNode(Node):
    """Interactive node for user diagram selection."""
    
    def __init__(self, max_retries: int = 1, wait: int = 0):
        super().__init__(max_retries=max_retries, wait=wait)
    
    def prep(self, shared: dict) -> List[dict]:
        """Get diagram plan.
        
        Args:
            shared: Shared store with 'diagram_plan'.
            
        Returns:
            List of proposed diagrams.
        """
        plan = shared.get("diagram_plan", {})
        diagrams = plan.get("diagrams", [])
        
        if not diagrams:
            console.warning("No diagrams in plan!", indent=1)
            return []
        
        return diagrams
    
    def exec(self, prep_res: List[dict]) -> List[dict]:
        """Display plan and get user selection.
        
        Args:
            prep_res: List of diagram proposals.
            
        Returns:
            Filtered list of selected diagrams.
        """
        if not prep_res:
            return []
        
        # Display the diagram plan
        console.section("Proposed Architectural Diagrams")
        
        for diagram in prep_res:
            complexity_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(
                diagram.get("complexity", "medium"), "⚪"
            )
            
            console.item(f"[{diagram['id']}] {diagram['name']}", indent=1)
            # console.info(f"Type: {diagram['type'].upper()}", indent=3) # Optional detail
            print(f"      Type: {diagram['type'].upper()}")
            print(f"      Focus: {diagram['focus']}")
            print(f"      Complexity: {complexity_emoji} {diagram.get('complexity', 'unknown')}")
            if diagram.get("files"):
                print(f"      Files: {', '.join(diagram['files'][:3])}...")
            print()
        
        console.blank()
        print("OPTIONS:")
        print("  • Enter diagram IDs separated by commas (e.g., 1,3,5)")
        print("  • Enter 'all' or 'a' to generate all diagrams")
        print("  • Enter 'quit' or 'q' to cancel")
        console.blank()
        
        # Get user input
        while True:
            try:
                user_input = input("🎯 Select diagrams to generate: ").strip().lower()
                
                if user_input in ("quit", "q", "exit"):
                    console.warning("Cancelled by user.", indent=1)
                    return []
                
                if user_input in ("all", "a", "*"):
                    console.success(f"Selected all {len(prep_res)} diagrams", indent=1)
                    return prep_res
                
                # Parse comma-separated IDs
                try:
                    selected_ids = [int(x.strip()) for x in user_input.split(",")]
                except ValueError:
                    console.warning("Invalid input. Enter numbers separated by commas.", indent=1)
                    continue
                
                # Filter diagrams
                selected = [d for d in prep_res if d["id"] in selected_ids]
                
                if not selected:
                    valid_ids = [d['id'] for d in prep_res]
                    console.warning(f"No matching diagrams. Valid IDs: {valid_ids}", indent=1)
                    continue
                
                console.success(f"Selected {len(selected)} diagram(s)", indent=1)
                return selected
                
            except EOFError:
                # Handle non-interactive mode
                console.warning("Non-interactive mode: selecting all diagrams", indent=1)
                return prep_res
            except KeyboardInterrupt:
                console.warning("Cancelled by user.", indent=1)
                return []
    
    def post(self, shared: dict, prep_res: list, exec_res: List[dict]) -> str:
        """Store selected diagrams.
        
        Args:
            shared: Shared store.
            prep_res: All diagrams.
            exec_res: Selected diagrams.
            
        Returns:
            Action string ('default' to continue, 'quit' to end).
        """
        if not exec_res:
            shared["diagram_queue"] = []
            return "quit"
        
        shared["diagram_queue"] = exec_res
        shared["current_diagram_index"] = 0
        shared["generated_diagrams"] = []
        
        shared["generated_diagrams"] = []
        
        console.section("PHASE 4: Diagram Generation")
        console.info(f"Queue: {len(exec_res)} diagram(s)", indent=1)
        
        return "default"

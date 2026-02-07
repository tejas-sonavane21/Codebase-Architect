"""
Node: The Auditor (Post-Generation)

Runs AFTER Drafter completes all diagrams.
Performs a 2-Phase Audit:
1. Plan Audit: Identifies potential duplicates from diagram_plan.json
2. Content Audit: Compares actual PUML files to verify duplicates

Outputs:
- Moves inferior diagrams to _deprecated/ folder
- Generates audit_report.md
"""

import json
import os
import re
import shutil
from typing import Optional, Dict, List, Tuple
from pocketflow import Node

from utils.gemini_client import get_client
from utils.prompts import get_prompt, get_gem_id
from utils.output_cleaner import clean_json


class AuditNode(Node):
    """
    Post-generation Auditor that verifies diagram quality.
    
    Phase 1: Plan-based duplicate identification (from diagram_plan.json)
    Phase 2: Content-based verification (from actual PUML files)
    """
    
    def __init__(self, max_retries: int = 3, wait: int = 2):
        super().__init__(max_retries=max_retries, wait=wait)
        self.client = None
        self.output_dir = ""
        self.deprecated_dir = ""
    
    def prep(self, shared: dict) -> dict:
        """Gather context for audit."""
        self.output_dir = shared.get("output_dir", "generated_diagrams")
        self.deprecated_dir = os.path.join(self.output_dir, "_deprecated")
        
        # Create deprecated folder
        os.makedirs(self.deprecated_dir, exist_ok=True)
        
        self.client = get_client()
        
        return {
            "diagram_plan": shared.get("diagram_plan", {}),
            "generated_diagrams": shared.get("generated_diagrams", []),
            "output_dir": self.output_dir,
        }
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Convert diagram name to sanitized filename format.
        
        Rules:
        - Lowercase
        - Spaces to underscores
        - Remove special characters
        - Max 50 chars
        """
        # Lowercase and replace spaces
        sanitized = name.lower().replace(" ", "_")
        
        # Remove special characters (keep alphanumeric and underscores)
        sanitized = re.sub(r'[^a-z0-9_]', '', sanitized)
        
        # Truncate
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        
        return sanitized
    
    def _find_diagram_file(self, diagram_name: str, output_dir: str) -> Optional[str]:
        """
        Find the PUML file for a diagram by name with fuzzy matching.
        
        Returns absolute path to .puml file or None if not found.
        """
        sanitized_name = self._sanitize_filename(diagram_name)
        
        # List all puml files in output dir
        puml_files = [f for f in os.listdir(output_dir) if f.endswith('.puml')]
        
        # Try exact match first
        for f in puml_files:
            f_base = os.path.splitext(f)[0].lower()
            if f_base == sanitized_name:
                return os.path.join(output_dir, f)
        
        # Try partial match (diagram name contains in filename or vice versa)
        for f in puml_files:
            f_base = os.path.splitext(f)[0].lower()
            if sanitized_name in f_base or f_base in sanitized_name:
                return os.path.join(output_dir, f)
        
        return None
    
    def _phase1_plan_audit(self, diagram_plan: Dict) -> List[Dict]:
        """
        Phase 1: Use LLM to identify potential duplicates from the plan.
        
        Returns list of candidate pairs: [{"dropped": id, "kept": id, "reason": str}, ...]
        """
        diagrams = diagram_plan.get("diagrams", [])
        
        if len(diagrams) <= 1:
            print("      ℹ Only 1 diagram, skipping Phase 1")
            return []
        
        prompt = f"""Analyze this list of proposed diagrams and identify POTENTIAL DUPLICATES.

=== DIAGRAM PLAN ===
{json.dumps(diagrams, indent=2)}

For each pair of diagrams that appear to represent the SAME THING:
- Identify which one to DROP and which to KEEP
- Use Information Density as the primary criteria

Return JSON:
{{
    "drop_ids": [list of IDs to potentially drop],
    "reasoning": [
        {{"dropped": id, "kept": id, "reason": "explanation"}},
        ...
    ]
}}

If no duplicates found, return: {{"drop_ids": [], "reasoning": []}}"""

        gem_id = get_gem_id("plan_auditor")
        active_model = self.client.MODEL
        
        response = self.client.generate_content(
            prompt=prompt,
            system_prompt=None if gem_id else get_prompt("plan_auditor", active_model),
            temperature=0.3,
            model_override=active_model,
            gem_id=gem_id,
        )
        
        try:
            clean_response = clean_json(response)
            result = json.loads(clean_response)
            
            candidates = result.get("reasoning", [])
            print(f"      ✓ Phase 1: Found {len(candidates)} potential duplicate pairs")
            
            for c in candidates:
                print(f"         ⚠ Candidate: Drop {c.get('dropped')} vs Keep {c.get('kept')}")
            
            return candidates
            
        except json.JSONDecodeError as e:
            print(f"      ⚠ Phase 1 parse error: {e}")
            return []
    
    def _phase2_content_audit(
        self, 
        candidates: List[Dict], 
        diagram_plan: Dict,
        output_dir: str
    ) -> List[Dict]:
        """
        Phase 2: Compare actual PUML content for candidate pairs.
        
        Returns list of verified decisions with file paths.
        """
        diagrams = {d["id"]: d for d in diagram_plan.get("diagrams", [])}
        verified = []
        
        for candidate in candidates:
            dropped_id = candidate.get("dropped")
            kept_id = candidate.get("kept")
            
            # Get diagram info
            dropped_diagram = diagrams.get(dropped_id)
            kept_diagram = diagrams.get(kept_id)
            
            if not dropped_diagram or not kept_diagram:
                print(f"      ⚠ Skipping pair ({dropped_id}, {kept_id}): Diagram info not found in plan")
                verified.append({
                    "dropped_id": dropped_id,
                    "kept_id": kept_id,
                    "status": "SKIPPED",
                    "reason": "Diagram not in plan",
                })
                continue
            
            # Find actual files
            dropped_file = self._find_diagram_file(dropped_diagram["name"], output_dir)
            kept_file = self._find_diagram_file(kept_diagram["name"], output_dir)
            
            if not dropped_file:
                print(f"      ⚠ Skipping pair: '{dropped_diagram['name']}' not found (generation may have failed)")
                verified.append({
                    "dropped_id": dropped_id,
                    "kept_id": kept_id,
                    "status": "SKIPPED",
                    "reason": f"File not found: {dropped_diagram['name']}",
                })
                continue
            
            if not kept_file:
                print(f"      ⚠ Skipping pair: '{kept_diagram['name']}' not found (generation may have failed)")
                verified.append({
                    "dropped_id": dropped_id,
                    "kept_id": kept_id,
                    "status": "SKIPPED",
                    "reason": f"File not found: {kept_diagram['name']}",
                })
                continue
            
            # Load PUML content
            with open(dropped_file, "r", encoding="utf-8") as f:
                dropped_puml = f.read()
            with open(kept_file, "r", encoding="utf-8") as f:
                kept_puml = f.read()
            
            # Compare using LLM
            decision = self._compare_diagrams(
                dropped_id, dropped_diagram["name"], dropped_puml,
                kept_id, kept_diagram["name"], kept_puml,
                candidate.get("reason", "")
            )
            
            decision["dropped_file"] = dropped_file
            decision["kept_file"] = kept_file
            verified.append(decision)
        
        return verified
    
    def _compare_diagrams(
        self,
        dropped_id: int, dropped_name: str, dropped_puml: str,
        kept_id: int, kept_name: str, kept_puml: str,
        plan_reason: str
    ) -> Dict:
        """
        Use LLM to compare two actual diagrams and decide which to keep.
        
        Returns decision dict.
        """
        # Truncate PUML if very long
        max_len = 3000
        d_puml = dropped_puml if len(dropped_puml) < max_len else dropped_puml[:max_len] + "\n... (truncated)"
        k_puml = kept_puml if len(kept_puml) < max_len else kept_puml[:max_len] + "\n... (truncated)"
        
        prompt = f"""Compare these two PlantUML diagrams.

=== DIAGRAM A (ID {dropped_id}: {dropped_name}) ===
```plantuml
{d_puml}
```

=== DIAGRAM B (ID {kept_id}: {kept_name}) ===
```plantuml
{k_puml}
```

**Previous Plan Analysis** (based on description only):
- Recommended: Drop A, Keep B
- Reason: {plan_reason}

**Your Task**: Analyze the ACTUAL diagram content.
1. Are these truly duplicates showing the same information?
2. If yes, which one provides better visual clarity and information density?
3. If they show different aspects/views, they are NOT duplicates.

Return JSON:
{{
    "are_duplicates": true/false,
    "winner": "A" or "B" or "BOTH" (if not duplicates or too similar),
    "confidence": "HIGH", "MEDIUM", or "LOW",
    "reason": "explanation"
}}"""

        # Use code_auditor gem for Phase 2 content comparison
        gem_id = get_gem_id("code_auditor")
        active_model = self.client.MODEL
        
        response = self.client.generate_content(
            prompt=prompt,
            system_prompt=None if gem_id else get_prompt("code_auditor", active_model),
            temperature=0.2,
            model_override=active_model,
            gem_id=gem_id,
        )
        
        try:
            clean_response = clean_json(response)
            result = json.loads(clean_response)
            
            are_dupes = result.get("are_duplicates", False)
            winner = result.get("winner", "BOTH")
            confidence = result.get("confidence", "LOW")
            reason = result.get("reason", "No reason provided")
            
            # Determine action
            if not are_dupes or winner == "BOTH":
                status = "KEEP_BOTH"
            elif confidence == "LOW":
                status = "KEEP_BOTH"  # Not confident enough to delete
            elif winner == "A":
                status = "DROP_B"  # Original plan was wrong, keep A instead
            else:
                status = "DROP_A"  # Original plan was right
            
            print(f"      🔍 Pair ({dropped_id} vs {kept_id}): {status} (confidence: {confidence})")
            
            return {
                "dropped_id": dropped_id,
                "kept_id": kept_id,
                "status": status,
                "are_duplicates": are_dupes,
                "winner": winner,
                "confidence": confidence,
                "reason": reason,
            }
            
        except json.JSONDecodeError as e:
            print(f"      ⚠ Content comparison parse error: {e}")
            return {
                "dropped_id": dropped_id,
                "kept_id": kept_id,
                "status": "KEEP_BOTH",
                "reason": f"Parse error: {e}",
            }
    
    def _execute_decisions(self, decisions: List[Dict]) -> Tuple[int, int]:
        """
        Execute the audit decisions.
        
        - DROP_A: Move dropped file to _deprecated
        - DROP_B: Move kept file to _deprecated (plan was wrong)
        - KEEP_BOTH: Do nothing
        - SKIPPED: Do nothing
        
        Returns (moved_count, kept_count).
        """
        moved = 0
        kept = 0
        
        for decision in decisions:
            status = decision.get("status")
            
            if status == "DROP_A" and decision.get("dropped_file"):
                self._move_to_deprecated(decision["dropped_file"])
                moved += 1
            elif status == "DROP_B" and decision.get("kept_file"):
                self._move_to_deprecated(decision["kept_file"])
                moved += 1
            else:
                kept += 1
        
        return moved, kept
    
    def _move_to_deprecated(self, file_path: str):
        """Move a file (and its PNG) to the _deprecated folder."""
        if not os.path.exists(file_path):
            return
        
        basename = os.path.basename(file_path)
        dest = os.path.join(self.deprecated_dir, basename)
        
        shutil.move(file_path, dest)
        print(f"         📁 Moved: {basename} -> _deprecated/")
        
        # Also move PNG if exists
        png_path = file_path.replace(".puml", ".png")
        if os.path.exists(png_path):
            png_basename = os.path.basename(png_path)
            png_dest = os.path.join(self.deprecated_dir, png_basename)
            shutil.move(png_path, png_dest)
    
    def _generate_report(self, decisions: List[Dict], moved: int, kept: int) -> str:
        """Generate audit_report.md summarizing the audit."""
        report_path = os.path.join(self.output_dir, "audit_report.md")
        
        lines = [
            "# Diagram Audit Report",
            "",
            f"**Total Pairs Analyzed:** {len(decisions)}",
            f"**Diagrams Deprecated:** {moved}",
            f"**Diagrams Kept:** {kept}",
            "",
            "---",
            "",
        ]
        
        for d in decisions:
            status = d.get("status", "UNKNOWN")
            dropped_id = d.get("dropped_id")
            kept_id = d.get("kept_id")
            reason = d.get("reason", "N/A")
            confidence = d.get("confidence", "N/A")
            
            if status == "SKIPPED":
                lines.append(f"## ⏭️ SKIPPED: Pair ({dropped_id}, {kept_id})")
                lines.append(f"**Reason:** {reason}")
            elif status == "KEEP_BOTH":
                lines.append(f"## ✅ KEPT BOTH: Pair ({dropped_id}, {kept_id})")
                lines.append(f"**Confidence:** {confidence}")
                lines.append(f"**Reason:** {reason}")
            elif status == "DROP_A":
                lines.append(f"## 🗑️ DEPRECATED ID {dropped_id}")
                lines.append(f"**Kept:** ID {kept_id}")
                lines.append(f"**Confidence:** {confidence}")
                lines.append(f"**Reason:** {reason}")
            elif status == "DROP_B":
                lines.append(f"## 🗑️ DEPRECATED ID {kept_id} (Plan Reversed)")
                lines.append(f"**Kept:** ID {dropped_id}")
                lines.append(f"**Confidence:** {confidence}")
                lines.append(f"**Reason:** {reason}")
            
            lines.append("")
        
        lines.append("---")
        lines.append("*Generated by AuditNode*")
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return report_path
    
    def exec(self, prep_res: dict) -> dict:
        """
        Execute the 2-Phase Audit.
        """
        diagram_plan = prep_res.get("diagram_plan", {})
        output_dir = prep_res.get("output_dir")
        
        print(f"\n🔍 Running Post-Generation Audit...")
        
        # Phase 1: Plan-based analysis
        print(f"\n   === Phase 1: Plan Audit ===")
        candidates = self._phase1_plan_audit(diagram_plan)
        
        if not candidates:
            print(f"      ✓ No potential duplicates found. All diagrams kept.")
            return {"decisions": [], "moved": 0, "kept": 0}
        
        # Phase 2: Content-based verification
        print(f"\n   === Phase 2: Content Audit ===")
        decisions = self._phase2_content_audit(candidates, diagram_plan, output_dir)
        
        # Execute decisions
        print(f"\n   === Executing Decisions ===")
        moved, kept = self._execute_decisions(decisions)
        
        # Generate report
        report_path = self._generate_report(decisions, moved, kept)
        print(f"\n   📄 Audit report saved to: {report_path}")
        
        return {"decisions": decisions, "moved": moved, "kept": kept}
    
    def post(self, shared: dict, prep_res: dict, exec_res: dict) -> str:
        """Store audit results."""
        shared["audit_result"] = exec_res
        
        moved = exec_res.get("moved", 0)
        kept = exec_res.get("kept", 0)
        
        print(f"\n✓ Audit complete: {moved} deprecated, {kept} kept")
        
        return "default"  # End of flow

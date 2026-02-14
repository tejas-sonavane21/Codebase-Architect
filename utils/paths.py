"""
Centralized Path Management for Codebase Architect.
Defines the directory structure for artifacts, analysis, and results.
"""

from pathlib import Path

# Project Root
ROOT_DIR = Path(__file__).parent.parent

# Base Artifacts Directory (Persistent Root)
ARTIFACTS_DIR = ROOT_DIR / "artifacts"

# Persistent Configuration
GEMS_CONFIG_PATH = ARTIFACTS_DIR / "gemini_gems" / "gems_config.json"

# Runtime Analysis (Temporary - Cleared per run)
ANALYSIS_DIR = ARTIFACTS_DIR / "analysis"
CLONE_DIR = ANALYSIS_DIR / "cloned_repo"
PROJECT_MAP_FILE = ANALYSIS_DIR / "project_map.txt"
FILE_INVENTORY_FILE = ANALYSIS_DIR / "file_inventory.json"
UPLOAD_CONFIG_FILE = ANALYSIS_DIR / "upload_config.json"
KNOWLEDGE_XML_FILE = ANALYSIS_DIR / "codebase_knowledge.xml"
ANALYSIS_LOG_FILE = ANALYSIS_DIR / "analysis_log.txt"
DIAGRAM_PLAN_FILE = ANALYSIS_DIR / "diagram_plan.json"

# Final Results (Persistent)
RESULTS_DIR = ARTIFACTS_DIR / "results"
DEPRECATED_DIR = RESULTS_DIR / "_deprecated"
AUDIT_REPORTS_DIR = ARTIFACTS_DIR / "audit_reports"

def ensure_dirs():
    """Ensure persistent directories exist."""
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    (ARTIFACTS_DIR / "gemini_gems").mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    AUDIT_REPORTS_DIR.mkdir(exist_ok=True)

# 🏯 Codebase Architect - Autonomous Diagram Generator

**An Agentic AI System** that reads code, understands architecture, and drafts professional PlantUML diagrams. Powered by Google Gemini 2.5 Flash, PocketFlow, and a dual-natured Architect agent.

![Banner](https://img.shields.io/badge/Status-Operational-green) ![Python](https://img.shields.io/badge/Python-3.11%2B-blue) ![License](https://img.shields.io/badge/License-MIT-purple)

## 🌟 Core Features

- **🔍 Intelligent Scouting**: Maps project structure, filtering noise and collapsing junk directories.
- **📚 Context Distillation**: Distills thousands of lines of code into a semantic knowledge base (`xml`) using a Map-Reduce approach with **Supervisor** validation.
- **🧠 Dual-Natured Architect**: A specialized agent that switches between "Structural" and "Behavioral" mindsets to plan complex diagrams.
- **🛡️ Audit & Supervision**: 
  - **ResponseSupervisor**: Validates LLM outputs (XML/JSON) in real-time during generation.
  - **AuditNode**: Post-generation critic that visually compares generated diagrams against the original code plan.
- **📝 Automated Drafting**: Generates strict, syntax-correct PlantUML code.
- **🎨 Modern CLI**: Rich terminal output with dynamic progress bars, spinners, and ANSI colors.

---

## 🏗️ Architecture (PocketFlow)

The system operates as a Directed Acyclic Graph (DAG) of specialized nodes:

1.  **Scout**: Clones the repo and builds a file map.
2.  **Surveyor**: "Interviews" the codebase to select the most relevant 50-100 files for analysis.
3.  **Uploader**: Uploads files to Gemini 1.5 Pro's context window (via Files API).
4.  **Summarizer**: Builds `codebase_knowledge.xml`.
    *   *Innovation*: Uses `generate_with_critique` loops to ensure valid XML.
5.  **Architect**: Plans the diagram suite.
    *   *Pass 1*: Structural Analysis (Classes, Components).
    *   *Pass 2*: Behavioral Analysis (Sequences, Activities).
    *   *Pass 3*: Deduplication & Feasibility Check.
6.  **Human Handshake**: Interactive menu for the user to select which diagrams to draft.
7.  **Drafter**: Writes the PlantUML code.
8.  **Audit**: (Optional) Reviews the final artifacts for hallucinations.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- A Google Account (for Gemini)
- `git`

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/tejas-sonavane21/Codebase-Architect.git
    cd Codebase-Architect
    ```

2.  Create virtual environment:
    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate  # Windows
    source .venv/bin/activate # Linux/Mac
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### 🔐 Authentication (Cookies)

This tool uses the `gemini_webapi` library which mimics a browser session. You need to export your Gemini cookies:

1.  Go to [gemini.google.com](https://gemini.google.com).
2.  Open Developer Tools (F12) -> Application -> Cookies.
3.  Copy the values for:
    - `__Secure-1PSID`
    - `__Secure-1PSIDTS`
4.  Create a `.env` file:
    ```ini
    # Authentication (Required)
    GEMINI_SECURE_1PSID=your_value_here
    GEMINI_SECURE_1PSIDTS=your_value_here
    
    # Model Configuration
    GEMINI_WEB_MODEL=gemini-3.0-pro
    
    # Development Options
    DEV_MODE=true           # Enable gem management commands
    DEBUG_FAILED_DIAGRAMS=false
    CONSOLE_VERBOSITY=1     # 0=Silent, 1=Normal, 2=Verbose
    ```

---

## 💻 Usage

### Initialization (First Run)
Before running the tool for the first time, you must create the necessary "Gems" (System Prompts) in your Gemini account:

```bash
# Enable developer mode temporarily to create gems
# Ensure DEV_MODE=true is set in your .env
python main.py --gems-create
```

This will create specialized agents like `codebase-architect`, `codebase-surveyor`, etc.

### Basic Run
Analyze a remote repository and generate diagrams:
```bash
python main.py https://github.com/tejas-sonavane21/VulnScraper
```

### Verbose Mode
Debug internal API calls and agent "thoughts":
```bash
python main.py https://github.com/user/repo --verbose
```

### Manage "Gems" (System Prompts)
The system uses persistent "Gems" on your Gemini account to store specialized agent personas.
```bash
# List all active gems
python main.py --gems-list

# Force update logic gems
python main.py --gems-update
```

---

### Output Structure

All artifacts are stored in the `artifacts/` directory:

```
artifacts/
├── gemini_gems/                # Persistent Gem configuration
│   └── gems_config.json
├── audit_reports/              # Diagram Audit Reports (Persistent)
│   └── <RepoName>-Audit.md     # Audit report for specific repo
├── analysis/                   # Temporary runtime analysis files (cleared each run)
│   ├── cloned_repo/            # Clone of the target repository
│   ├── codebase_knowledge.xml  # Distilled knowledge base
│   ├── project_map.txt         # File structure map
│   └── file_inventory.json     # File inventory
└── results/                    # Final output (Persistent)
    └── <repo_name>/            # Diagrams for specific repo
        ├── system_overview.png
        ├── detailed_flow.puml
        └── ...
```
```

---

## 🤝 Contributing

Contributions are welcome! Please follow the "Clean Console" standard for any new output.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

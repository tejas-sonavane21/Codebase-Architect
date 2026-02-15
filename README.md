# 🛡️ Codebase-Architect: Automated Whitebox Reconnaissance For Threat Modeling

> **"Enumeration is 90% of the battle. Visualize the attack surface before you audit it."**

**Codebase-Architect** is an automated **Whitebox Reconnaissance & Architecture Mapping utility** powered by **Google Gemini 3.0 Pro**, **PocketFlow**, and a **Dual-Natured Architect Agent**. It is designed to accelerate the "Mapping" phase of Source Code Reviews, Penetration Tests, and Threat Modeling sessions.

By leveraging Large Language Models (LLMs) with a Map-Reduce architecture, Codebase-Architect ingests complex repositories, distills their logic, and generates strict architectural diagrams (PlantUML). This allows security researchers to instantly visualize data flows, trust boundaries, and component interactions without spending hours manually tracing code.

![Banner](https://img.shields.io/badge/Status-Operational-green) ![Python](https://img.shields.io/badge/Python-3.11%2B-blue) ![License](https://img.shields.io/badge/License-MIT-purple)

---

## 🚀 Mission: Why this tool?

In complex **Whitebox Assessments** and **Secure Code Reviews**, auditors often struggle with "analysis paralysis" when facing large, unfamiliar codebases. Identifying logic vulnerabilities (Business Logic Errors, Race Conditions, Insecure Data Flows) requires a high-level mental model of the system.

**Codebase-Architect** bridges the gap between raw code and architectural understanding, enabling pentesters to:
* **Rapidly Onboard**: Instantly understand the architecture of legacy or complex targets.
* **Visualize Attack Surfaces**: Map entry points, API routes, and untrusted data flows.
* **Identify Design Flaws**: Focus on Architecture Analysis rather than just syntax errors.
* **Automate Threat Modeling**: Generate DFDs (Data Flow Diagrams) to identify STRIDE threats.

---

## ⚡ Key Capabilities

### 🔍 Automated Attack Surface Discovery
Instead of blindly scanning files, the **Surveyor Node** intelligently scans the project structure to identify high-value targets (Controllers, API endpoints, Auth middleware) versus noise (assets, configs), ensuring the analysis focuses on the logical core.

### ⚗️ Context Distillation (Map-Reduce)
Large codebases break standard LLM context windows. Codebase-Architect employs a **Map-Reduce "Summarizer"** to process files in batches. It distills thousands of lines of code into a semantic `codebase_knowledge.xml`—essentially creating a "cliff notes" version of the target's logic for the auditing agent.  A built-in **ResponseSupervisor** validates every LLM output (XML/JSON) in real-time, ensuring structural integrity before the data propagates downstream.

### 🧠 Dual-Natured Architect (Logic Flow & Sequence Mapping)
The **Architect Agent** doesn't just draw classes; it understands *behavior*. Using a specialized **dual-prompt strategy**, it switches between a "Structural" mindset (Classes, Components) and a "Behavioral" mindset (Sequences, Activities, State Machines) to draft diagrams that reveal how user input travels through the system (e.g., `User -> API -> Auth Middleware -> Database`), highlighting potential bottlenecks or insecure hand-offs.

### 🛡️ Post-Generation Audit & Semantic Validation
A dedicated **AuditNode** performs a 2-Phase post-generation review: first identifying potential duplicate diagrams from the plan, then comparing actual PUML content to verify. Inferior or redundant diagrams are automatically deprecated, ensuring the final output is a clean, reliable reference for the security assessment.

### 🎨 Modern CLI
Rich terminal output with dynamic progress bars, spinners, and ANSI colors for clear, real-time feedback during long-running assessments.

---

## 🛠️ Technical Architecture (PocketFlow DAG)

The tool operates as a Directed Acyclic Graph (DAG) of specialized AI agents, mimicking a security team's workflow:

1.  **Scout (Recon)**: Clones the target repo and maps the directory tree, filtering out non-functional artifacts.
2.  **Surveyor (Scope Definition)**: Analyzes the file tree to select the critical path for audit (e.g., identifying `routes/`, `models/`, `controllers/`).
3.  **Uploader (Data Ingestion)**: Batches and uploads target source code to the Gemini Files API with rate-limit handling.
4.  **Summarizer (Knowledge Distillation)**:
    * **Phase 1 (Map)**: Summarizes individual modules with `ResponseSupervisor` validation.
    * **Phase 2 (Reduce)**: Identifies cross-module dependencies and data flows.
5.  **Architect (Attack Surface Planner)**: Plans the diagram suite using a dual-prompt strategy:
    * *Pass 1*: Behavioral Analysis (Sequences, Activities, State Machines).
    * *Pass 2*: Structural Analysis (Classes, Components, ER Diagrams, DFDs with STRIDE).
    * *Pass 3*: AI-driven Deduplication & Feasibility Check.
6.  **Human Handshake**: Interactive CLI for the auditor to select specific areas of interest.
7.  **Drafter (Visualization)**: Generates strict PlantUML code representing the target architecture.
8.  **Critic (Quality Assurance)**: Validates the PlantUML syntax and renders the final visual assets via Kroki.
9.  **Auditor (Post-Generation Review)**: Detects and deprecates duplicate or redundant diagrams.

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

---

## 🤝 Contributing

Contributions are welcome! Please follow the "Clean Console" standard for any new output.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

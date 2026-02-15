# 🛡️ Codebase-Architect: Automated Whitebox Reconnaissance For Threat Modeling

> **"Enumeration is 90% of the battle. Visualize the attack surface before you audit it."**

**Codebase-Architect** is an automated **Whitebox Reconnaissance & Architecture Mapping utility** powered by **Google Gemini 2.5 Flash** and **PocketFlow**. It is designed to accelerate the "Mapping" phase of Source Code Reviews, Penetration Tests, and Threat Modeling sessions.

By leveraging Large Language Models (LLMs) with a Map-Reduce architecture, Codebase-Architect ingests complex repositories, distills their logic, and generates strict architectural diagrams (PlantUML). This allows security researchers to instantly visualize data flows, trust boundaries, and component interactions without spending hours manually tracing code.

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
Large codebases break standard LLM context windows. Codebase-Architect employs a **Map-Reduce "Summarizer"** to process files in batches. It distills thousands of lines of code into a semantic `codebase_knowledge.xml`—essentially creating a "cliff notes" version of the target's logic for the auditing agent.

### 🧠 Logic Flow & Sequence Mapping
The **Architect Agent** doesn't just draw classes; it understands *behavior*. It drafts **Sequence Diagrams** to visualize how user input travels through the system (e.g., `User -> API -> Auth Middleware -> Database`), highlighting potential bottlenecks or insecure hand-offs.

### 🛡️ Semantic Validation (The Critic)
A dedicated **Critic Node** validates the generated diagrams not just for syntax, but for architectural accuracy, ensuring the output is a reliable reference for the security assessment.

---

## 🛠️ Technical Architecture (PocketFlow DAG)

The tool operates as a Directed Acyclic Graph (DAG) of specialized AI agents, mimicking a security team's workflow:

1.  **Scout (Recon)**: Clones the target repo and maps the directory tree, filtering out non-functional artifacts.
2.  **Surveyor (Scope Definition)**: Analyzes the file tree to select the critical path for audit (e.g., identifying `routes/`, `models/`, `controllers/`).
3.  **Uploader (Data Ingestion)**: Batches and uploads target source code to the Gemini Files API with rate-limit handling.
4.  **Summarizer (Knowledge Distillation)**:
    * **Phase 1 (Map)**: Summarizes individual modules.
    * **Phase 2 (Reduce)**: Identifies cross-module dependencies and data flows.
5.  **Architect (Threat Modeler)**: Plans specific diagrams (Component, Sequence, Data Flow) based on the distilled knowledge base.
6.  **Human Handshake**: Interactive CLI for the auditor to select specific areas of interest.
7.  **Drafter (Visualization)**: Generates strict PlantUML code representing the target architecture.
8.  **Critic (Quality Assurance)**: Validates the PlantUML syntax and renders the final visual assets via Kroki.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Google Gemini API Key

### Installation

1.  Clone this repository:
    ```bash
    git clone https://github.com/tejas-sonavane21/Codebase-Architect.git
    cd Codebase-Architect
    ```

2.  Create a virtual environment:
    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate  # Windows
    source .venv/bin/activate # Linux/Mac
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  Configure environment:
    Create a `.env` file:
    ```ini
    GEMINI_API_KEY=your_gemini_api_key_here
    ```

### Usage

Run the tool with a GitHub repository URL:

```bash
python main.py https://github.com/tejas-sonavane21/VulnScraper
```

The tool will:
1.  Clone the repo to `cloned_repo/`.
2.  Analyze and upload files to Gemini.
3.  Build a knowledge base (`codebase_knowledge.xml`).
4.  Propose diagrams.
5.  Ask you which ones to generate.
6.  Save outcomes to `generated_diagrams/` (both `.puml` and `.png`).

## 📁 Output Structure

```
generated_diagrams/
├── vulnscraper_system_context.png
├── vulnscraper_system_context.puml
├── vulnscraper_exploit_generation_workflow.png
├── vulnscraper_exploit_generation_workflow.puml
...
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

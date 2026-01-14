# 🎨 BlackBook Builder - UML Diagram Generator (Codebase-Architect)

**Automated Architectural Diagram Generator** powered by Google Gemini 2.5 Flash, PocketFlow, and PlantUML.

BlackBook Builder - UML Diagram Generator is basically a Repo-to-UML Diagrams Generator. It automatically clones a repository, understands its codebase through **Context Distillation**, plans focused architectural diagrams, and drafts them in PlantUML. It uses a Map-Reduce approach to handle large codebases without hitting token limits or server errors.

## ✨ Features

- **🔍 Smart Analysis**: Scans project structure and intelligently selects source files.
- **⚗️ Context Distillation**: Uses a Map-Reduce "Summarizer Node" to distill thousands of lines of code into a compact `codebase_knowledge.xml`.
- **🧠 Intelligent Planning**: An "Architect" agent plans focused diagrams (Class, Sequence, Component) based on semantic understanding.
- **📝 Automated Drafting**: Generates strict PlantUML code.
- **🛡️ Self-Correction**: A "Critic" node validates syntax, complexity, and renders diagrams via Kroki.
- **🚀 Scalable**: Handles large repositories by batching uploads and using distilled knowledge for drafting.

## 🛠️ Architecture (PocketFlow)

The agent is built as a Directed Acyclic Graph (DAG) of nodes:

1.  **Scout**: Clones repo, maps structure, collapses junk directories.
2.  **Surveyor**: Uses LLM to identify key files for analysis.
3.  **Uploader**: Uploads files to Gemini Files API (with efficient batching & cleanup).
4.  **Summarizer**: **(Core Innovation)** 
    - Processes files 2-at-a-time (Map-Reduce).
    - Maintains full content for small files (<50 lines).
    - Summarizes large files.
    - Identifies cross-file relationships (Pass 2).
    - Produces `codebase_knowledge.xml`.
5.  **Architect**: Plans diagrams using the distilled knowledge XML (preventing 500 errors).
6.  **Human Handshake**: Interactive CLI for users to select diagrams.
7.  **Drafter**: Generates PlantUML.
8.  **Critic**: Validates & renders PNGs.

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

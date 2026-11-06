# 🌳 TSTA — Tree-Structured Thinking Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![CI](https://github.com/redam221/tsta/actions/workflows/ci.yml/badge.svg)](https://github.com/redam221/tsta/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**A new AI agent paradigm for AI-assisted self-education.**

TSTA models the learning process as a strict **single-parent, multi-child tree structure**, where each node represents a `(Question, Answer, Context)` knowledge unit. This solves the core pain points of linear AI assistants in self-education: lost branch questions, context chaos, untraceable knowledge sources, and hallucinations.

## The Problem

Traditional AI assistants use linear dialogue — a single thread of Q&A. But human learning is naturally tree-structured: you start from a core question, discover new questions from the answer, and explore multiple directions. Linear chat creates four problems:

| Pain Point | TSTA Solution |
|---|---|
| Branch questions get lost in history | Each question becomes a persistent node in the tree |
| Context becomes chaotic in long chats | Per-branch context isolation (Isolation Axiom) |
| Can't trace where knowledge came from | Full path tracing from root to any node |
| AI hallucinates unrelated information | Structural anti-hallucination constraints |

## Core Concepts

### Three Axioms

1. **Single-Parent Axiom**: Every node has exactly one parent → knowledge source is unique and traceable
2. **Expansion Axiom**: Any node can spawn child nodes → unlimited depth and breadth exploration
3. **Isolation Axiom**: Node contexts are independent per branch → no knowledge cross-contamination

### Paradigm Positioning

TSTA is a **foundational paradigm** at the same level as CoT, ReAct, and RAG:

| Paradigm | Focus |
|---|---|
| **CoT** (Chain-of-Thought) | How to reason — step-by-step reasoning |
| **ReAct** | How to act — reasoning + tool use |
| **RAG** | How to acquire knowledge — retrieval augmentation |
| **TSTA** | How to **structure, store, and trace** thinking — tree-shaped knowledge organization |

TSTA doesn't replace existing paradigms — it integrates with them (TSTA+CoT, TSTA+RAG, TSTA+ReAct).

## Architecture

```
┌──────────────────────────────────────────────┐
│         Human-Computer Interaction Layer      │
│  Expand/Collapse │ Right-click Ask │ Path    │
│                  │ Trace           │ Export  │
├──────────────────────────────────────────────┤
│              TSTA Core Layer                  │
│  ┌──────────┐ ┌────────┐ ┌───────────────┐  │
│  │Tree Mgr  │ │Node Mgr│ │Path Tracer    │  │
│  │(topology)│ │(Q,A,C) │ │(traceability) │  │
│  └──────────┘ └────────┘ └───────────────┘  │
│  ┌──────────────────────────────────────┐    │
│  │   Anti-Hallucination Controller      │    │
│  └──────────────────────────────────────┘    │
├──────────────────────────────────────────────┤
│    Paradigm Compatibility + LLM Layer         │
│   CoT / ReAct / RAG  │  OpenAI / 豆包 / ...  │
└──────────────────────────────────────────────┘
```

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/redam221/tsta.git
cd tsta

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install
pip install -e .
```

### 2. Configuration

```bash
cp .env.example .env
# Edit .env with your API key and preferences
```

Required: Set your OpenAI-compatible API key in `.env`:
```
OPENAI_API_KEY=your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

### 3. Launch

**Option A: Both API + UI (recommended)**
```bash
tsta run
# API: http://127.0.0.1:8000
# UI:  http://127.0.0.1:8501
```

**Option B: Separate terminals**
```bash
# Terminal 1: API server
tsta api --reload

# Terminal 2: Streamlit UI
tsta ui
```

### 4. Start Learning

1. Open http://127.0.0.1:8501 in your browser
2. Enter a root question (e.g., "What is reinforcement learning?")
3. Read the AI answer
4. Click **➕ Ask** on any node to branch into follow-up questions
5. Click **🔍 Path** to trace your learning journey
6. Explore multiple branches in parallel — they stay context-isolated!

### Desktop App (密米尔 Mimir)

TSTA also ships a native desktop app (**Mimir**) built on pywebview — no browser or server needed:

```bash
pip install -e ".[desktop]"
python launch.py          # or: pythonw.exe launch.py (console-free, Windows)
```

The desktop app adds:
- **Knowledge-base upload** — drag in PDF / Word / Excel / text files as reference context for any node (parsed locally)
- **Detachable chat window** — free-form assistant docked to your knowledge tree
- **Multi-provider settings** — DeepSeek / 豆包 / SiliconFlow / OpenAI / custom OpenAI-compatible endpoint, persisted locally in `~/.tsta/`

## Project Structure

```
tsta/
├── src/tsta/
│   ├── __init__.py          # Package entry, exports
│   ├── cli.py               # CLI interface
│   ├── core/
│   │   ├── node.py          # Node & Tree data models (Pydantic)
│   │   └── __init__.py
│   ├── engine/
│   │   ├── agent.py         # TSTAAgent — Algorithm 1 implementation
│   │   ├── llm.py           # LLM client (OpenAI-compatible)
│   │   └── __init__.py
│   ├── storage/
│   │   ├── file_storage.py  # JSON file persistence
│   │   └── __init__.py
│   ├── web/
│   │   ├── api.py           # FastAPI REST API
│   │   ├── streamlit_app.py # Streamlit interactive UI
│   │   └── __init__.py
│   ├── desktop/
│   │   ├── app.py           # Native desktop app (pywebview, "密米尔 Mimir")
│   │   ├── api.py           # Desktop API bridge (JS <-> engine)
│   │   ├── file_parser.py   # Parse PDF/docx/xlsx/txt into knowledge base
│   │   ├── settings.py      # LLM provider settings (DeepSeek/豆包/SiliconFlow/...)
│   │   ├── frontend/        # HTML/JS/CSS desktop UI
│   │   └── __init__.py
│   └── utils/
│       ├── config.py        # Configuration management
│       └── __init__.py
├── tests/
│   ├── test_node.py         # Core data model tests
│   ├── test_agent.py        # Agent engine tests
│   └── test_integration.py  # API integration tests
├── examples/
│   └── basic_usage.py       # End-to-end usage demo
├── paper/
│   └── paper.md             # Bilingual paper (Chinese/English)
├── docs/
├── .github/workflows/       # CI (runs pytest)
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## API Reference

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/trees` | Create new knowledge tree |
| `GET` | `/trees` | List all saved trees |
| `GET` | `/trees/{id}` | Load a tree |
| `DELETE` | `/trees/{id}` | Delete a tree |
| `POST` | `/trees/{id}/ask` | Add child node (follow-up question) |
| `GET` | `/trees/{id}/path/{node}` | Trace root-to-node path |
| `DELETE` | `/trees/{id}/nodes/{node}` | Delete a subtree |
| `PUT` | `/trees/{id}/nodes/{node}` | Edit a node |
| `GET` | `/trees/{id}/subtree/{node}` | Get subtree for rendering |
| `GET` | `/trees/{id}/export` | Export all knowledge paths |
| `GET` | `/trees/{id}/validate` | Validate against TSTA axioms |

## Python SDK Usage

```python
from tsta import TSTAAgent, FileStorage

# Initialize agent
agent = TSTAAgent()

# Create a knowledge tree
tree = agent.init("What is quantum computing?")

# Branch exploration
child1 = agent.ask(tree.root_id, "How do qubits work?")
child2 = agent.ask(tree.root_id, "What are quantum gates?")

# Deep dive
deep = agent.ask(child1.id, "What is superposition?")

# Trace learning path
print(agent.trace_path_text(deep.id))

# Save
storage = FileStorage()
storage.save(tree)

# Export
for path in agent.export_paths():
    print(path)
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov=tsta
```

## Design Decisions & Suggestions

### What's implemented
- Complete formal definitions: Node as `(Q, A, C)` and Tree as `(N, Root, Parent, Children)`
- All three TSTA axioms enforced (single-parent, expansion, isolation)
- Full Algorithm 1 (init, ask, trace path) as described in the paper
- Anti-hallucination prompt template that constrains answers to parent context
- Tree validation against formal constraints
- FastAPI REST API + Streamlit interactive UI
- JSON file persistence with tree listing/CRUD
- CLI for launching API, UI, or both

### Suggestions for future extensions
1. **Database storage**: Replace JSON files with PostgreSQL + pgvector for semantic search across knowledge trees
2. **Automatic branching**: Use the LLM to suggest follow-up questions automatically based on node content
3. **Multi-agent collaboration**: Different agents handle different subtrees, passing summaries between branches
4. **Knowledge graph integration**: Link tree nodes to external knowledge graphs (Wikidata, ConceptNet)
5. **Personalized recommendations**: Analyze learning paths to recommend next branches based on user patterns
6. **Collaboration**: Real-time collaborative tree editing (CRDT-based, like Figma for knowledge)
7. **Learning analytics**: Track which branches were explored, time spent, comprehension metrics
8. **Voice interface**: Speech-to-text for questions, TTS for answers — mobile learning
9. **Export formats**: Mind map (XMind), Anki flashcards, Obsidian vault, PDF reports
10. **Plugin system**: Allow community plugins for custom LLM backends, storage backends, UI themes

## Paper

The full paper (bilingual, Chinese/English) is available at
[`paper/paper.md`](paper/paper.md).

## Citation

If you use TSTA in your research, please cite:

```bibtex
@article{tsta2025,
  title   = {Tree-Structured Thinking Agent (TSTA): A Paradigm for AI-Assisted Self-Education},
  author  = {Xiheng Yuan},
  year    = {2025},
  note    = {Preprint}
}
```

## License

MIT License — see [LICENSE](LICENSE) for details.

# TSTA Architecture

## Design Philosophy

TSTA is designed around a single insight: **learning is naturally tree-structured, but AI assistants are linear**. The architecture bridges this gap by making the tree structure the fundamental data model, not an afterthought.

## Layer Architecture

### Layer 1: Core Data Models (`core/`)

The foundation: `Node` and `Tree` are Pydantic models that enforce the formal definitions from the paper.

- **Node**: A triple `(Q, A, C)` — question, answer, context
  - `context` inherits from parent, achieving the Isolation Axiom
  - Each node carries its full lineage context independently
- **Tree**: A quadruple `(N, Root, Parent, Children)`
  - `validate()` checks all four structural constraints
  - `trace_path()` implements Definition 4

### Layer 2: Agent Engine (`engine/`)

The runtime that orchestrates tree operations and LLM interactions.

- **TSTAAgent**: Implements Algorithm 1 from the paper
  - `init()` → TSTA_Init (lines 2-10)
  - `ask()` → TSTA_Ask (lines 12-27)
  - `trace_path()` → TSTA_TracePath (lines 29-36)
- **LLMClient**: OpenAI-compatible interface with built-in anti-hallucination prompts

### Layer 3: Persistence (`storage/`)

- **FileStorage**: JSON-based persistence. Each tree is one `.json` file.
- Designed for easy swap to SQLite/PostgreSQL — implement the same interface.

### Layer 4: Web Interface (`web/`)

- **FastAPI** (`api.py`): RESTful API for CRUD on trees and nodes
- **Streamlit** (`streamlit_app.py`): Interactive tree visualization

## Data Flow

```
User asks question (Streamlit)
    → POST /trees/{id}/ask (FastAPI)
        → TSTAAgent.ask() 
            → LLMClient.generate_answer() [anti-hallucination prompt]
            → LLM API (OpenAI / 豆包)
            → Node created with inherited context
            → Tree updated, saved to disk
        ← JSON response
    ← UI re-renders tree
```

## Context Isolation Mechanism

The key innovation for preventing cross-branch contamination:

```
         Root
        /    \
       A      B
      / \      \
     A1 A2     B1
```

- Node A1's context = Root context + A context + A1's own Q&A
- Node B1's context = Root context + B context + B1's own Q&A
- A1 and B1 share only Root context (their common ancestor)
- A1 knows nothing about A2 (siblings are isolated)

This is enforced by `Node.build_context()` which walks the ancestor chain, not sibling nodes.

## Anti-Hallucination Design

Rather than relying solely on the LLM to be honest, TSTA adds structural constraints:

1. **Prompt-level**: The system prompt strictly instructs the LLM to answer only from parent context + KB
2. **Context-level**: The user prompt explicitly lists the parent Q&A and KB, with no other information
3. **Structural-level**: Since each node only has access to its ancestor chain, the LLM cannot "see" irrelevant sibling branches

This three-layer approach significantly reduces hallucinations compared to linear chatbots where the entire chat history is always in context.

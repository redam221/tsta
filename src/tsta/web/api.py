"""FastAPI backend for TSTA.

Provides REST API for tree management and LLM interaction.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..engine.agent import TSTAAgent
from ..engine.llm import LLMConfig
from ..storage.file_storage import FileStorage


# ── Request/Response Models ───────────────────────────────────

class InitRequest(BaseModel):
    question: str = Field(..., description="Root question for the knowledge tree")
    knowledge_base: Optional[str] = Field(None, description="Optional external knowledge")


class AskRequest(BaseModel):
    parent_id: str = Field(..., description="ID of the parent node")
    question: str = Field(..., description="Follow-up question")
    knowledge_base: Optional[str] = None


class TreeResponse(BaseModel):
    id: str
    name: str
    root_id: Optional[str]
    node_count: int
    max_depth: int
    leaf_count: int
    nodes: list[dict]
    created_at: str
    updated_at: str


# ── App Setup ──────────────────────────────────────────────────

agent: TSTAAgent | None = None
storage: FileStorage | None = None


def get_agent() -> TSTAAgent:
    global agent
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    return agent


def get_storage() -> FileStorage:
    global storage
    if storage is None:
        raise HTTPException(status_code=500, detail="Storage not initialized")
    return storage


def create_app() -> FastAPI:
    app = FastAPI(
        title="TSTA — Tree-Structured Thinking Agent",
        description="A paradigm for AI-assisted self-education with tree-structured knowledge exploration.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    global agent, storage
    agent = TSTAAgent(LLMConfig())
    storage = FileStorage()

    # ── Tree Endpoints ──────────────────────────────────────

    @app.post("/trees", response_model=TreeResponse)
    async def create_tree(req: InitRequest):
        """Initialize a new TSTA tree with a root question."""
        tree = get_agent().init(req.question, req.knowledge_base)
        get_storage().save(tree)
        return _tree_response(tree)

    @app.get("/trees")
    async def list_trees():
        """List all saved trees."""
        return get_storage().list_trees()

    @app.get("/trees/{tree_id}")
    async def get_tree(tree_id: str):
        """Load a tree by ID."""
        tree = get_storage().load(tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Tree not found")
        get_agent().tree = tree
        return _tree_response(tree)

    @app.delete("/trees/{tree_id}")
    async def delete_tree(tree_id: str):
        """Delete a tree."""
        if get_storage().delete(tree_id):
            return {"status": "deleted"}
        raise HTTPException(status_code=404, detail="Tree not found")

    # ── Node Endpoints ──────────────────────────────────────

    @app.post("/trees/{tree_id}/ask")
    async def ask_question(tree_id: str, req: AskRequest):
        """Add a child node via follow-up question."""
        tree = get_storage().load(tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Tree not found")
        get_agent().tree = tree

        try:
            child = get_agent().ask(req.parent_id, req.question, req.knowledge_base)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        get_storage().save(get_agent().tree)
        return {
            "id": child.id,
            "parent_id": child.parent_id,
            "question": child.question,
            "answer": child.answer,
            "created_at": child.created_at,
        }

    @app.get("/trees/{tree_id}/path/{node_id}")
    async def trace_path(tree_id: str, node_id: str):
        """Trace the path from root to a specific node."""
        tree = get_storage().load(tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Tree not found")
        get_agent().tree = tree

        path = get_agent().trace_path(node_id)
        return {
            "node_id": node_id,
            "path": [
                {"id": n.id, "question": n.question, "answer": n.answer[:200]}
                for n in path
            ],
            "path_text": get_agent().trace_path_text(node_id),
        }

    @app.delete("/trees/{tree_id}/nodes/{node_id}")
    async def delete_node(tree_id: str, node_id: str):
        """Delete a node and its subtree."""
        tree = get_storage().load(tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Tree not found")
        get_agent().tree = tree
        get_agent().delete_node(node_id)
        get_storage().save(get_agent().tree)
        return {"status": "deleted"}

    @app.put("/trees/{tree_id}/nodes/{node_id}")
    async def edit_node(tree_id: str, node_id: str, question: Optional[str] = None, answer: Optional[str] = None):
        """Edit a node's question or answer."""
        tree = get_storage().load(tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Tree not found")
        get_agent().tree = tree
        node = get_agent().edit_node(node_id, question, answer)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        get_storage().save(get_agent().tree)
        return {"id": node.id, "question": node.question, "answer": node.answer}

    @app.get("/trees/{tree_id}/subtree/{node_id}")
    async def get_subtree(tree_id: str, node_id: str, max_depth: int = 3):
        """Get a subtree for rendering."""
        tree = get_storage().load(tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Tree not found")
        get_agent().tree = tree
        return get_agent().get_subtree(node_id, max_depth)

    @app.get("/trees/{tree_id}/export")
    async def export_paths(tree_id: str):
        """Export all root-to-leaf paths."""
        tree = get_storage().load(tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Tree not found")
        get_agent().tree = tree
        return {"paths": get_agent().export_paths()}

    @app.get("/trees/{tree_id}/validate")
    async def validate_tree(tree_id: str):
        """Validate a tree against TSTA axioms."""
        tree = get_storage().load(tree_id)
        if not tree:
            raise HTTPException(status_code=404, detail="Tree not found")
        get_agent().tree = tree
        violations = get_agent().validate()
        return {"valid": len(violations) == 0, "violations": violations}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


# ── Helpers ────────────────────────────────────────────────────

def _tree_response(tree) -> TreeResponse:
    return TreeResponse(
        id=tree.id,
        name=tree.name,
        root_id=tree.root_id,
        node_count=tree.node_count,
        max_depth=tree.max_depth,
        leaf_count=tree.leaf_count,
        nodes=[
            {
                "id": n.id,
                "parent_id": n.parent_id,
                "question": n.question,
                "answer": n.answer[:300] if n.answer else "",
                "children_ids": n.children_ids,
                "created_at": n.created_at,
            }
            for n in tree.nodes.values()
        ],
        created_at=tree.created_at,
        updated_at=tree.updated_at,
    )


# App instance — created lazily to avoid requiring API keys at import time.
# In production, use `from tsta.web.api import create_app; app = create_app()` instead.
_app: FastAPI | None = None


def get_app() -> FastAPI:
    global _app
    if _app is None:
        _app = create_app()
    return _app


app = create_app()

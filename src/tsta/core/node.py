"""Core data models for the Tree-Structured Thinking Agent.

Implements the formal definitions from the TSTA paper:
Definition 2 — Node as triple (Q, A, C)
Definition 1 — Tree as quadruple (N, Root, Parent, Children)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Node(BaseModel):
    """A single node in the TSTA tree.

    Corresponds to Definition 2: n = (Q(n), A(n), C(n))
    Each node represents one "question + answer" knowledge unit.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    question: str = Field(description="Q(n) — the question asked at this node")
    answer: str = Field(default="", description="A(n) — the LLM-generated answer")
    context: list[str] = Field(
        default_factory=list,
        description="C(n) — inherited parent context + current Q&A",
    )
    children_ids: list[str] = Field(default_factory=list)
    attachments: list[dict] = Field(
        default_factory=list,
        description="Reference files uploaded for this node: {name, content, note}",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict = Field(default_factory=dict)

    def build_context(self) -> list[str]:
        """Assemble the full context for this node (self-history + ancestors)."""
        base = self.context or []
        return base + [f"Q: {self.question}", f"A: {self.answer}"]

    def is_root(self) -> bool:
        return self.parent_id is None

    def is_leaf(self) -> bool:
        return len(self.children_ids) == 0

    def to_dict(self) -> dict:
        return self.model_dump()

    def __hash__(self) -> int:
        return hash(self.id)


class Tree(BaseModel):
    """The complete TSTA tree structure.

    Corresponds to Definition 1: T = (N, Root, Parent, Children)
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(default="Untitled Knowledge Tree")
    nodes: dict[str, Node] = Field(default_factory=dict)
    root_id: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Single-Parent Axiom helpers ──────────────────────────────

    def get_root(self) -> Optional[Node]:
        if self.root_id:
            return self.nodes.get(self.root_id)
        return None

    def get_children(self, node_id: str) -> list[Node]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children_ids if cid in self.nodes]

    def get_parent(self, node_id: str) -> Optional[Node]:
        node = self.nodes.get(node_id)
        if node and node.parent_id:
            return self.nodes.get(node.parent_id)
        return None

    # ── Path tracing ─────────────────────────────────────────────

    def trace_path(self, node_id: str) -> list[Node]:
        """Return the ordered path from root to the given node.

        Corresponds to Definition 4: Path(n) = [Root, ..., n]
        and Algorithm 1 lines 29-36.
        """
        path: list[Node] = []
        visited: set[str] = set()
        current = self.nodes.get(node_id)
        while current:
            if current.id in visited:
                break  # cycle detected — stop to avoid infinite loop
            visited.add(current.id)
            path.append(current)
            current = self.get_parent(current.id)
        path.reverse()
        return path

    def trace_path_str(self, node_id: str) -> str:
        """Human-readable path representation."""
        path = self.trace_path(node_id)
        lines = []
        for i, node in enumerate(path):
            indent = "  " * i
            lines.append(f"{indent}{i + 1}. Q: {node.question}")
            if node.answer:
                lines.append(f"{indent}   A: {node.answer[:120]}...")
        return "\n".join(lines)

    # ── Validation ───────────────────────────────────────────────

    def validate(self) -> list[str]:
        """Validate the tree against TSTA axioms. Returns list of violations."""
        violations: list[str] = []

        for nid, node in self.nodes.items():
            # Single parent: each non-root node must have exactly one parent
            if not node.is_root():
                parent = self.nodes.get(node.parent_id)
                if parent is None:
                    violations.append(
                        f"Node '{nid}' references missing parent '{node.parent_id}'"
                    )
                elif nid not in parent.children_ids:
                    violations.append(
                        f"Node '{nid}' is not in parent '{node.parent_id}' children_ids"
                    )

            # Children consistency
            for cid in node.children_ids:
                child = self.nodes.get(cid)
                if child is None:
                    violations.append(f"Node '{nid}' references missing child '{cid}'")
                elif child.parent_id != nid:
                    violations.append(
                        f"Child '{cid}' parent_id '{child.parent_id}' != '{nid}'"
                    )

            # No cycles (acyclic constraint) — trace_path now has built-in protection
            path = self.trace_path(nid)
            path_ids = {n.id for n in path}
            if any(path[i].id == path[j].id for i in range(len(path)) for j in range(i + 1, len(path))):
                violations.append(f"Cycle detected involving node '{nid}'")

            # Root reachability (completeness constraint)
            if node.parent_id is None and nid != self.root_id:
                violations.append(f"Multiple roots detected: '{nid}' and '{self.root_id}'")

        return violations

    # ── Serialization ────────────────────────────────────────────

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "Tree":
        return cls(**data)

    # ── Stats ────────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def max_depth(self) -> int:
        if not self.root_id:
            return 0
        return self._calc_depth(self.root_id)

    def _calc_depth(self, node_id: str) -> int:
        node = self.nodes.get(node_id)
        if not node or not node.children_ids:
            return 1
        return 1 + max(self._calc_depth(cid) for cid in node.children_ids)

    @property
    def leaf_count(self) -> int:
        return sum(1 for n in self.nodes.values() if n.is_leaf())

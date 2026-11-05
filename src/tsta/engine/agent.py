"""TSTA Agent — the core engine implementing the paper's algorithms.

Implements Algorithm 1: TSTA Core Algorithm
- TSTA_Init: Initialize tree with root node
- TSTA_Ask: Add a child node via follow-up question
- TSTA_TracePath: Trace path from root to any node
"""

from typing import Optional

from ..core.node import Node, Tree
from .llm import LLMClient, LLMConfig


class TSTAAgent:
    """The main Tree-Structured Thinking Agent.

    Manages the knowledge tree and orchestrates LLM interactions.
    """

    def __init__(self, llm_config: LLMConfig | None = None):
        self.llm = LLMClient(llm_config)
        self.tree: Tree | None = None

    # ── Algorithm 1: TSTA_Init (lines 2-10) ──────────────────────

    def init(self, root_question: str, knowledge_base: str | None = None) -> Tree:
        """Initialize a new TSTA tree with a root question.

        Corresponds to Algorithm 1, lines 2-10:
        TSTA_Init(Q_root, LLM, KB) -> Tree
        """
        # Generate answer for the root question
        answer = self.llm.generate_answer(
            question=root_question,
            knowledge_base=knowledge_base,
        )

        # Create root node: C_root = {Q_root, A_root}
        root = Node(
            question=root_question,
            answer=answer,
            context=[f"Q: {root_question}", f"A: {answer}"],
        )

        # Initialize tree structure
        tree = Tree(
            name=self._derive_tree_name(root_question),
            nodes={root.id: root},
            root_id=root.id,
        )

        self.tree = tree
        return tree

    # ── Algorithm 1: TSTA_Ask (lines 12-27) ──────────────────────

    def ask(self, parent_id: str, question: str, knowledge_base: str | None = None) -> Node:
        """Add a child node by asking a follow-up question.

        Corresponds to Algorithm 1, lines 12-27:
        TSTA_Ask(T, n, Q_new, LLM, KB) -> (T, n_new)

        Enforces:
        - Single-parent axiom (new node has exactly one parent)
        - Context isolation (inherits parent context only)
        - Anti-hallucination (answer constrained to parent content + KB)
        """
        if not self.tree:
            raise ValueError("Tree not initialized. Call init() first.")

        parent = self.tree.nodes.get(parent_id)
        if not parent:
            raise ValueError(f"Parent node '{parent_id}' not found.")

        # Generate answer with anti-hallucination constraints
        answer = self.llm.generate_answer(
            question=question,
            parent_question=parent.question,
            parent_answer=parent.answer,
            knowledge_base=knowledge_base,
        )

        # Build context: C_new = {Q_new, A_new} U C_parent
        child_context = parent.build_context() + [f"Q: {question}", f"A: {answer}"]

        child = Node(
            parent_id=parent_id,
            question=question,
            answer=answer,
            context=child_context,
        )

        # Update tree structure maintaining single-parent constraint
        self.tree.nodes[child.id] = child
        parent.children_ids.append(child.id)

        return child

    # ── Algorithm 1: TSTA_TracePath (lines 29-36) ────────────────

    def trace_path(self, node_id: str) -> list[Node]:
        """Trace the full thinking path from root to the given node.

        Corresponds to Algorithm 1, lines 29-36.
        """
        if not self.tree:
            raise ValueError("Tree not initialized.")
        return self.tree.trace_path(node_id)

    def trace_path_text(self, node_id: str) -> str:
        """Get a human-readable path trace."""
        if not self.tree:
            raise ValueError("Tree not initialized.")
        return self.tree.trace_path_str(node_id)

    # ── Tree management ─────────────────────────────────────────

    def delete_node(self, node_id: str) -> None:
        """Delete a node and all its descendants."""
        if not self.tree:
            return

        node = self.tree.nodes.get(node_id)
        if not node:
            return

        # Recursively collect descendant IDs
        to_delete: list[str] = []

        def collect_ids(nid: str):
            to_delete.append(nid)
            n = self.tree.nodes.get(nid)
            if n:
                for cid in n.children_ids:
                    collect_ids(cid)

        collect_ids(node_id)

        # Remove from parent's children list
        if node.parent_id:
            parent = self.tree.nodes.get(node.parent_id)
            if parent:
                parent.children_ids = [
                    cid for cid in parent.children_ids if cid != node_id
                ]

        # Delete all collected nodes
        for nid in to_delete:
            del self.tree.nodes[nid]

        # Clear root if deleted
        if node_id == self.tree.root_id:
            self.tree.root_id = None

    def edit_node(self, node_id: str, question: str | None = None, answer: str | None = None) -> Node | None:
        """Edit a node's question or answer."""
        if not self.tree:
            return None
        node = self.tree.nodes.get(node_id)
        if not node:
            return None
        if question is not None:
            node.question = question
        if answer is not None:
            node.answer = answer
        return node

    def get_subtree(self, node_id: str, max_depth: int = 3) -> dict:
        """Get a subtree rooted at node_id for rendering."""
        if not self.tree:
            return {}

        node = self.tree.nodes.get(node_id)
        if not node:
            return {}

        result = {
            "id": node.id,
            "question": node.question,
            "answer": node.answer[:200] if node.answer else "",
            "children": [],
        }

        if max_depth > 0:
            for cid in node.children_ids:
                child_data = self.get_subtree(cid, max_depth - 1)
                if child_data:
                    result["children"].append(child_data)

        return result

    def export_paths(self) -> list[str]:
        """Export all root-to-leaf paths as formatted text."""
        if not self.tree or not self.tree.root_id:
            return []
        paths: list[str] = []
        self._collect_paths(self.tree.root_id, [], paths)
        return paths

    def _collect_paths(self, node_id: str, current: list[str], paths: list[str]):
        node = self.tree.nodes.get(node_id)
        if not node:
            return
        current = current + [f"Q: {node.question}\nA: {node.answer}"]
        if not node.children_ids:
            paths.append("\n---\n".join(current))
        else:
            for cid in node.children_ids:
                self._collect_paths(cid, current, paths)

    # ── Validation ───────────────────────────────────────────────

    def validate(self) -> list[str]:
        if not self.tree:
            return ["No tree exists"]
        return self.tree.validate()

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _derive_tree_name(question: str) -> str:
        clean = question.strip().rstrip("?？")
        if len(clean) > 50:
            clean = clean[:47] + "..."
        return clean

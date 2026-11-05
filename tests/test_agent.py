"""Tests for TSTA agent engine (without real LLM calls)."""

import pytest
from unittest.mock import MagicMock, patch

from tsta.core.node import Node, Tree
from tsta.engine.agent import TSTAAgent
from tsta.engine.llm import LLMConfig


class TestTSTAAgent:
    @pytest.fixture
    def agent(self):
        """Create an agent with a mocked LLM."""
        with patch("tsta.engine.agent.LLMClient") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.generate_answer.return_value = "Mocked answer."
            mock_llm.return_value = mock_llm_instance
            agent = TSTAAgent(LLMConfig(api_key="test-key"))
            agent.llm = mock_llm_instance
            yield agent

    def test_init_creates_tree(self, agent):
        tree = agent.init("What is AI?")
        assert tree is not None
        assert tree.root_id is not None
        assert tree.node_count == 1
        root = tree.get_root()
        assert root.question == "What is AI?"
        assert root.answer == "Mocked answer."

    def test_ask_creates_child(self, agent):
        agent.init("What is AI?")
        root = agent.tree.get_root()

        child = agent.ask(root.id, "What is ML?")

        assert child.parent_id == root.id
        assert child.question == "What is ML?"
        assert child.answer == "Mocked answer."
        assert child.id in root.children_ids
        assert agent.tree.node_count == 2

    def test_ask_enforces_single_parent(self, agent):
        agent.init("Root")
        root = agent.tree.get_root()

        child = agent.ask(root.id, "Child Q")
        # Child should have exactly one parent
        assert child.parent_id == root.id
        # Verify single-parent axiom
        parent_count = sum(
            1 for n in agent.tree.nodes.values()
            if n.id == child.id and n.parent_id is not None
        )
        assert parent_count == 1

    def test_trace_path(self, agent):
        agent.init("Q0")
        root = agent.tree.get_root()
        child1 = agent.ask(root.id, "Q1")
        child2 = agent.ask(child1.id, "Q2")

        path = agent.trace_path(child2.id)
        assert len(path) == 3
        assert path[0].question == "Q0"
        assert path[1].question == "Q1"
        assert path[2].question == "Q2"

    def test_delete_node_removes_subtree(self, agent):
        agent.init("Root")
        root = agent.tree.get_root()
        child1 = agent.ask(root.id, "C1")
        child2 = agent.ask(child1.id, "C2")

        agent.delete_node(child1.id)
        assert child1.id not in agent.tree.nodes
        assert child2.id not in agent.tree.nodes
        assert child1.id not in root.children_ids
        assert agent.tree.node_count == 1

    def test_edit_node(self, agent):
        agent.init("Old Q")
        root = agent.tree.get_root()

        agent.edit_node(root.id, question="New Q", answer="New A")
        node = agent.tree.nodes[root.id]
        assert node.question == "New Q"
        assert node.answer == "New A"

    def test_context_isolation(self, agent):
        """Test that children from different branches have separate contexts."""
        agent.init("Root Q")
        root = agent.tree.get_root()

        # Branch A
        branch_a = agent.ask(root.id, "Branch A Q")
        leaf_a = agent.ask(branch_a.id, "Leaf A Q")

        # Branch B
        branch_b = agent.ask(root.id, "Branch B Q")
        leaf_b = agent.ask(branch_b.id, "Leaf B Q")

        # Contexts should be different (context isolation axiom)
        assert leaf_a.context != leaf_b.context

        # But both should contain "Root Q" (shared ancestor context)
        root_in_a = any("Root Q" in c for c in leaf_a.context)
        root_in_b = any("Root Q" in c for c in leaf_b.context)
        assert root_in_a
        assert root_in_b

    def test_export_paths(self, agent):
        agent.init("Root")
        root = agent.tree.get_root()
        child1 = agent.ask(root.id, "Branch 1")
        child2 = agent.ask(root.id, "Branch 2")

        paths = agent.export_paths()
        assert len(paths) == 2

    def test_validate_clean_tree(self, agent):
        agent.init("Root")
        root = agent.tree.get_root()
        agent.ask(root.id, "Child")
        violations = agent.validate()
        assert violations == []

    def test_ask_without_init_raises(self, agent):
        with pytest.raises(ValueError, match="Tree not initialized"):
            agent.ask("some-id", "Question?")

    def test_get_subtree(self, agent):
        agent.init("Root")
        root = agent.tree.get_root()
        child = agent.ask(root.id, "Child")

        subtree = agent.get_subtree(root.id, max_depth=2)
        assert subtree["question"] == "Root"
        assert len(subtree["children"]) == 1
        assert subtree["children"][0]["question"] == "Child"

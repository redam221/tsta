"""Tests for core data models."""

import pytest
from tsta.core.node import Node, Tree


class TestNode:
    def test_node_creation(self):
        node = Node(question="What is AI?")
        assert node.id
        assert node.question == "What is AI?"
        assert node.answer == ""
        assert node.is_root()
        assert node.is_leaf()

    def test_node_with_parent(self):
        node = Node(question="What is ML?", parent_id="root-1")
        assert not node.is_root()
        assert node.parent_id == "root-1"

    def test_build_context(self):
        node = Node(
            question="What is RL?",
            answer="RL is reinforcement learning.",
            context=["Q: What is AI?", "A: AI is artificial intelligence."],
        )
        ctx = node.build_context()
        assert len(ctx) == 4
        assert "Q: What is RL?" in ctx

    def test_node_children_tracking(self):
        node = Node(question="Parent")
        node.children_ids.append("child-1")
        node.children_ids.append("child-2")
        assert not node.is_leaf()
        assert len(node.children_ids) == 2


class TestTree:
    def _make_tree(self) -> Tree:
        """Create a simple tree for testing:
            root
           /    \
        child1  child2
          |
        grandchild
        """
        root = Node(question="Root Q", answer="Root A")
        tree = Tree(name="Test", nodes={root.id: root}, root_id=root.id)

        child1 = Node(question="Child1 Q", answer="Child1 A", parent_id=root.id)
        root.children_ids.append(child1.id)
        tree.nodes[child1.id] = child1

        child2 = Node(question="Child2 Q", answer="Child2 A", parent_id=root.id)
        root.children_ids.append(child2.id)
        tree.nodes[child2.id] = child2

        grandchild = Node(question="Grandchild Q", answer="Grandchild A", parent_id=child1.id)
        child1.children_ids.append(grandchild.id)
        tree.nodes[grandchild.id] = grandchild

        return tree

    def test_tree_creation(self):
        tree = self._make_tree()
        assert tree.node_count == 4
        assert tree.root_id is not None
        assert tree.max_depth == 3

    def test_get_root(self):
        tree = self._make_tree()
        root = tree.get_root()
        assert root is not None
        assert root.question == "Root Q"

    def test_get_children(self):
        tree = self._make_tree()
        root = tree.get_root()
        children = tree.get_children(root.id)
        assert len(children) == 2
        assert {c.question for c in children} == {"Child1 Q", "Child2 Q"}

    def test_get_parent(self):
        tree = self._make_tree()
        root = tree.get_root()
        children = tree.get_children(root.id)
        child1 = children[0]
        parent = tree.get_parent(child1.id)
        assert parent is not None
        assert parent.id == root.id

    def test_trace_path(self):
        tree = self._make_tree()
        # Find grandchild
        root = tree.get_root()
        children = tree.get_children(root.id)
        child1 = children[0]
        grandchildren = tree.get_children(child1.id)
        gc = grandchildren[0]

        path = tree.trace_path(gc.id)
        assert len(path) == 3
        assert path[0].question == "Root Q"
        assert path[1].question == "Child1 Q"
        assert path[2].question == "Grandchild Q"

    def test_valid_tree_passes_validation(self):
        tree = self._make_tree()
        violations = tree.validate()
        assert len(violations) == 0

    def test_orphan_node_detected(self):
        tree = self._make_tree()
        orphan = Node(question="Orphan", parent_id="nonexistent")
        tree.nodes[orphan.id] = orphan
        violations = tree.validate()
        assert len(violations) >= 1
        assert any("missing parent" in v.lower() for v in violations)

    def test_leaf_count(self):
        tree = self._make_tree()
        # child2 and grandchild are leaves
        assert tree.leaf_count == 2

    def test_max_depth(self):
        tree = self._make_tree()
        assert tree.max_depth == 3

    def test_empty_tree(self):
        tree = Tree()
        assert tree.node_count == 0
        assert tree.max_depth == 0
        assert tree.leaf_count == 0

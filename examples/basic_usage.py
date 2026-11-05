"""Basic usage example: TSTA for AI-assisted self-education.

This example demonstrates the core TSTA workflow:
1. Initialize a knowledge tree with a root question
2. Ask follow-up questions to explore branches
3. Trace the learning path
4. Export the knowledge tree

Usage:
    python examples/basic_usage.py
"""

import sys
import os

# Add parent to path so we can import tsta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tsta.engine.agent import TSTAAgent
from tsta.engine.llm import LLMConfig
from tsta.storage.file_storage import FileStorage


def demo():
    # Configure LLM — set your API key in .env or pass it here
    config = LLMConfig()
    if not config.api_key:
        print("No OPENAI_API_KEY found in environment.")
        print("Set it in .env file or export OPENAI_API_KEY=your-key")
        print("\nRunning with mock answers for demonstration...")
        print("=" * 60)

    agent = TSTAAgent(config)
    storage = FileStorage("./data/trees")

    # Step 1: Initialize the knowledge tree
    print("\n=== Step 1: Initialize Knowledge Tree ===")
    root_q = "What is a large language model (LLM) agent?"
    print(f"Root question: {root_q}")

    tree = agent.init(root_q)
    root = tree.get_root()
    print(f"\nAnswer: {root.answer[:300]}...")

    # Step 2: Explore branches
    print("\n=== Step 2: Branch Exploration ===")

    # Branch A: Agent architectures
    q1 = "What are the main architectures for LLM agents?"
    print(f"\n[Branch A] {q1}")
    branch_a = agent.ask(root.id, q1)
    print(f"Answer: {branch_a.answer[:200]}...")

    # Branch B: Agent paradigms
    q2 = "What are the classic paradigms for LLM agents?"
    print(f"\n[Branch B] {q2}")
    branch_b = agent.ask(root.id, q2)
    print(f"Answer: {branch_b.answer[:200]}...")

    # Step 3: Deep dive into a branch
    print("\n=== Step 3: Deep Dive ===")
    q1_1 = "Can you explain the ReAct paradigm in detail?"
    print(f"\n[Branch A → Deep Dive] {q1_1}")
    deep = agent.ask(branch_a.id, q1_1)
    print(f"Answer: {deep.answer[:200]}...")

    # Step 4: Path tracing
    print("\n=== Step 4: Knowledge Path Trace ===")
    print(f"Path from root to deep node:\n")
    print(agent.trace_path_text(deep.id))

    # Step 5: Save and export
    print("\n=== Step 5: Save and Export ===")
    path = storage.save(agent.tree)
    print(f"Saved to: {path}")

    # Export all paths
    paths = agent.export_paths()
    print(f"\nNumber of knowledge paths: {len(paths)}")

    # Stats
    print(f"\nTree stats:")
    print(f"  Total nodes: {agent.tree.node_count}")
    print(f"  Max depth: {agent.tree.max_depth}")
    print(f"  Leaf nodes: {agent.tree.leaf_count}")

    # Validate
    violations = agent.validate()
    if violations:
        print(f"\nViolations found: {violations}")
    else:
        print(f"\nTree is valid — all TSTA axioms satisfied.")

    print("\n" + "=" * 60)
    print("Demo complete! Tree has been saved and can be loaded in the web UI.")


if __name__ == "__main__":
    demo()

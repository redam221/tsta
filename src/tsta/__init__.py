"""TSTA — Tree-Structured Thinking Agent.

A paradigm for AI-assisted self-education with tree-structured knowledge exploration.
"""

__version__ = "0.1.0"
__all__ = ["TSTAAgent", "Node", "Tree", "LLMClient", "FileStorage"]

from .core.node import Node, Tree
from .engine.agent import TSTAAgent
from .engine.llm import LLMClient
from .storage.file_storage import FileStorage

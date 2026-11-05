"""File-based persistence for TSTA trees.

Supports JSON file storage with tree listing and CRUD operations.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.node import Tree


class FileStorage:
    """Persist TSTA trees to local JSON files."""

    def __init__(self, storage_path: str = "./data/trees"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save(self, tree: Tree) -> str:
        """Save a tree to disk. Returns the file path."""
        tree.updated_at = datetime.now(timezone.utc).isoformat()
        filepath = self.storage_path / f"{tree.id}.json"
        filepath.write_text(
            json.dumps(tree.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(filepath)

    def load(self, tree_id: str) -> Optional[Tree]:
        """Load a tree from disk by ID."""
        filepath = self.storage_path / f"{tree_id}.json"
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return Tree.from_dict(data)

    def delete(self, tree_id: str) -> bool:
        """Delete a tree file from disk."""
        filepath = self.storage_path / f"{tree_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def list_trees(self) -> list[dict]:
        """List all saved trees with metadata."""
        trees = []
        for filepath in sorted(
            self.storage_path.glob("*.json"), key=os.path.getmtime, reverse=True
        ):
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                trees.append(
                    {
                        "id": data.get("id", filepath.stem),
                        "name": data.get("name", "Untitled"),
                        "node_count": len(data.get("nodes", {})),
                        "root_id": data.get("root_id"),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return trees

    def get_filepath(self, tree_id: str) -> Path:
        return self.storage_path / f"{tree_id}.json"

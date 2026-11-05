"""DesktopAPI — the bridge between the frontend JS and the TSTA engine.

Exposed to JavaScript via pywebview's js_api. Every method returns plain
JSON-serialisable dicts/lists so they cross the bridge cleanly.
"""

from __future__ import annotations

from pathlib import Path

import webview

from ..core.node import Tree, Node
from ..engine.agent import TSTAAgent
from ..engine.llm import LLMConfig, LLMClient
from ..storage.file_storage import FileStorage
from .file_parser import parse_file
from .settings import (
    PROVIDERS,
    TREES_DIR,
    load_settings,
    save_settings,
)

MAX_FILE_CHARS = 20000   # per-file cap fed to the model
MAX_KB_CHARS = 60000     # total knowledge-base cap

FILE_TYPES = (
    "所有支持的文件 (*.txt;*.md;*.csv;*.json;*.pdf;*.docx;*.xlsx;*.py;*.log)",
    "文本文件 (*.txt;*.md;*.csv;*.json;*.py;*.log)",
    "PDF 文档 (*.pdf)",
    "Word 文档 (*.docx)",
    "Excel 表格 (*.xlsx)",
)

# Default directory for file-open dialogs (falls back to home if unavailable).
DESKTOP_DIR = Path.home() / "Desktop"
if not DESKTOP_DIR.is_dir():
    DESKTOP_DIR = Path.home()


def _config_from_settings(s: dict) -> LLMConfig:
    return LLMConfig(
        model=s.get("model") or "gpt-4o",
        api_key=s.get("api_key", ""),
        base_url=s.get("base_url") or "https://api.openai.com/v1",
        temperature=float(s.get("temperature", 0.3)),
        max_tokens=int(s.get("max_tokens", 2048)),
    )


class DesktopAPI:
    """Wraps TSTAAgent + FileStorage for the desktop UI."""

    def __init__(self):
        self._storage = FileStorage(str(TREES_DIR))
        s = load_settings()
        self._agent = TSTAAgent(_config_from_settings(s))
        self._apply_llm_config(s)
        self._window = None  # set by app.py after window creation
        self._chat_window = None  # detached chat window (set by app.py)
        self._pending: list[dict] = []  # files staged for the next root question
        self._last_dir = str(DESKTOP_DIR)  # dir remembered after each pick
        self._chat: list[dict] = []  # free-form chat history [{role, content}]

    def _apply_llm_config(self, s: dict) -> None:
        """Push latest settings into the live agent without losing tree state."""
        cfg = self._agent.llm.config
        cfg.model = s.get("model") or cfg.model
        cfg.api_key = s.get("api_key", "")
        cfg.base_url = s.get("base_url") or cfg.base_url
        cfg.temperature = float(s.get("temperature", cfg.temperature))
        cfg.max_tokens = int(s.get("max_tokens", cfg.max_tokens))
        self._agent.llm._client = None  # force client rebuild on next call

    # ── Settings ──────────────────────────────────────────────

    def get_settings(self) -> dict:
        s = load_settings()
        s["providers"] = PROVIDERS
        s["has_key"] = bool(s.get("api_key"))
        return s

    def save_settings(self, data: dict) -> dict:
        s = save_settings(data)
        self._apply_llm_config(s)
        return {"ok": True, "has_key": bool(s.get("api_key"))}

    def test_connection(self) -> dict:
        s = load_settings()
        if not s.get("api_key"):
            return {"ok": False, "message": "请先填写 API Key"}
        try:
            cfg = _config_from_settings(s)
            client = LLMClient(cfg)
            client.generate("You are a connectivity test.", "Reply with exactly: OK")
            return {"ok": True, "message": f"连接成功 — 模型 {cfg.model} 可用"}
        except Exception as e:  # noqa: BLE001 — surface any provider error to the user
            return {"ok": False, "message": _friendly_error(e)}

    # ── Chat (free-form conversation, dockable / detachable) ──

    def chat_send(self, message: str) -> dict:
        """Send a chat message; the model sees the full prior history."""
        message = (message or "").strip()
        if not message:
            return {"ok": False, "message": "消息不能为空"}
        if not self._agent.llm.config.api_key:
            return {"ok": False, "message": "请先在「设置」填写 API Key"}
        self._chat.append({"role": "user", "content": message})
        try:
            reply = self._agent.llm.chat(
                self._chat, system_prompt=self._chat_system_prompt()
            )
        except Exception as e:  # noqa: BLE001
            self._chat.pop()
            return {"ok": False, "message": _friendly_error(e)}
        self._chat.append({"role": "assistant", "content": reply})
        return {"ok": True, "messages": list(self._chat)}

    def _chat_system_prompt(self) -> str:
        prompt = (
            "你是一位博学、耐心、循循善诱的学习助手。请用清晰、准确的中文回答，"
            "适当使用标题、列表帮助理解；对不确定的内容要诚实说明。"
        )
        tree = self._agent.tree
        if tree and tree.root_id:
            root = tree.get_root()
            if root:
                prompt += (
                    f"\n用户当前正在研究知识树「{tree.name}」，"
                    f"根问题是：{root.question}。可结合这个主题进行对话。"
                )
        return prompt

    def chat_history(self) -> dict:
        return {"ok": True, "messages": list(self._chat)}

    def chat_clear(self) -> dict:
        self._chat = []
        return {"ok": True, "messages": []}

    def pop_chat(self) -> dict:
        """Detach the chat into its own native window."""
        if self._chat_window is None:
            return {"ok": False, "message": "聊天窗口尚未就绪"}
        try:
            self._chat_window.show()
        except Exception:  # noqa: BLE001
            pass
        _safe_eval(self._chat_window, "window.__refreshChat && window.__refreshChat()")
        _safe_eval(self._window, "window.__chatPoppedOut && window.__chatPoppedOut()")
        return {"ok": True}

    def merge_chat(self) -> dict:
        """Re-dock the chat back into the main window."""
        if self._chat_window is not None:
            try:
                self._chat_window.hide()
            except Exception:  # noqa: BLE001
                pass
        _safe_eval(self._window, "window.__chatMergedBack && window.__chatMergedBack()")
        return {"ok": True}

    def on_chat_window_closing(self):
        """Fired when the detached chat window's ✕ is clicked: don't destroy it,
        just hide it and re-dock the chat into the main window."""
        try:
            if self._chat_window is not None:
                self._chat_window.hide()
        except Exception:  # noqa: BLE001
            pass
        _safe_eval(self._window, "window.__chatMergedBack && window.__chatMergedBack()")
        return False  # cancel the actual close

    # ── Trees ────────────────────────────────────────────────

    def list_trees(self) -> list:
        return self._storage.list_trees()

    def new_tree(self, root_question: str) -> dict:
        self._agent.tree = None
        kb = _kb_from_files(self._pending)
        try:
            tree = self._agent.init(root_question, knowledge_base=kb)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": _friendly_error(e)}
        # attach staged files to the root node
        if self._pending:
            root = tree.get_root()
            if root:
                root.attachments = list(self._pending)
        self._pending = []
        self._storage.save(tree)
        return {"ok": True, "tree": self._tree_payload(tree)}

    def load_tree(self, tree_id: str) -> dict:
        tree = self._storage.load(tree_id)
        if not tree:
            return {"ok": False, "message": "未找到该知识树"}
        self._agent.tree = tree
        return {"ok": True, "tree": self._tree_payload(tree)}

    def delete_tree(self, tree_id: str) -> dict:
        self._storage.delete(tree_id)
        if self._agent.tree and self._agent.tree.id == tree_id:
            self._agent.tree = None
        return {"ok": True}

    def current_tree(self) -> dict:
        if not self._agent.tree:
            return {"tree": None}
        return {"tree": self._tree_payload(self._agent.tree)}

    # ── Node operations ──────────────────────────────────────

    def ask(self, parent_id: str, question: str) -> dict:
        if not self._agent.tree:
            return {"ok": False, "message": "请先创建或打开一个知识树"}
        try:
            child = self._agent.ask(
                parent_id, question, knowledge_base=self._knowledge_base_for_path(parent_id)
            )
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": _friendly_error(e)}
        self._storage.save(self._agent.tree)
        return {"ok": True, "node": child.to_dict(), "tree": self._tree_payload(self._agent.tree)}

    def delete_node(self, node_id: str) -> dict:
        if not self._agent.tree:
            return {"ok": False, "message": "无当前知识树"}
        self._agent.delete_node(node_id)
        self._storage.save(self._agent.tree)
        return {"ok": True, "tree": self._tree_payload(self._agent.tree)}

    def edit_node(self, node_id: str, question: str = None, answer: str = None) -> dict:
        if not self._agent.tree:
            return {"ok": False, "message": "无当前知识树"}
        node = self._agent.edit_node(node_id, question, answer)
        if not node:
            return {"ok": False, "message": "节点不存在"}
        self._storage.save(self._agent.tree)
        return {"ok": True, "node": node.to_dict()}

    def trace_path(self, node_id: str) -> dict:
        if not self._agent.tree:
            return {"ok": False, "message": "无当前知识树"}
        path = self._agent.tree.trace_path(node_id)
        return {"ok": True, "path": [n.to_dict() for n in path]}

    def export_paths(self) -> dict:
        if not self._agent.tree:
            return {"ok": False, "message": "无当前知识树"}
        paths = self._agent.export_paths()
        return {"ok": True, "paths": paths}

    # ── Attachments (per-node files → knowledge base) ──────

    def _dialog(self):
        if self._window is None:
            return None
        paths = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            directory=self._last_dir,
            allow_multiple=True,
            file_types=FILE_TYPES,
        )
        if paths:
            # remember the folder of the last picked file for the next dialog
            self._last_dir = str(Path(paths[0]).parent)
        return paths

    def _parse_paths(self, paths):
        """Parse selected paths -> (files, errors). files = [{name, content, note}]."""
        files, errors = [], []
        for path in paths:
            name = Path(path).name
            try:
                content = parse_file(path)[:MAX_FILE_CHARS]
                if not content.strip():
                    errors.append({"name": name, "error": "未能提取到文本内容"})
                    continue
                files.append({"name": name, "content": content, "note": ""})
            except Exception as e:  # noqa: BLE001
                errors.append({"name": name, "error": str(e)[:200]})
        return files, errors

    def _get_node(self, node_id: str) -> Node | None:
        if not self._agent.tree:
            return None
        return self._agent.tree.nodes.get(node_id)

    # stage files for a NEW root question
    def pick_files_to_pending(self) -> dict:
        if self._window is None:
            return {"ok": False, "message": "窗口尚未就绪"}
        paths = self._dialog()
        if not paths:
            return {"ok": False, "cancelled": True}
        files, errors = self._parse_paths(paths)
        self._pending.extend(files)
        return {
            "ok": True,
            "pending": _summarize_files(self._pending),
            "added": _summarize_files(files) + errors,
        }

    def list_pending(self) -> dict:
        return {"ok": True, "pending": _summarize_files(self._pending)}

    def remove_pending_file(self, index: int) -> dict:
        if 0 <= index < len(self._pending):
            self._pending.pop(index)
        return {"ok": True, "pending": _summarize_files(self._pending)}

    def clear_pending(self) -> dict:
        self._pending = []
        return {"ok": True, "pending": []}

    # node-level upload / note / remove
    def add_files_to_node(self, node_id: str) -> dict:
        node = self._get_node(node_id)
        if node is None:
            return {"ok": False, "message": "节点不存在"}
        if self._window is None:
            return {"ok": False, "message": "窗口尚未就绪"}
        paths = self._dialog()
        if not paths:
            return {"ok": False, "cancelled": True}
        files, errors = self._parse_paths(paths)
        node.attachments.extend(files)
        self._storage.save(self._agent.tree)
        return {
            "ok": True,
            "node": node.to_dict(),
            "tree": self._tree_payload(self._agent.tree),
            "added": _summarize_files(files) + errors,
        }

    def add_node_file_note(self, node_id: str, index: int, note: str) -> dict:
        node = self._get_node(node_id)
        if node is None:
            return {"ok": False, "message": "节点不存在"}
        if 0 <= index < len(node.attachments):
            node.attachments[index]["note"] = (note or "").strip()
            self._storage.save(self._agent.tree)
        return {"ok": True, "node": node.to_dict()}

    def remove_node_file(self, node_id: str, index: int) -> dict:
        node = self._get_node(node_id)
        if node is None:
            return {"ok": False, "message": "节点不存在"}
        if 0 <= index < len(node.attachments):
            node.attachments.pop(index)
            self._storage.save(self._agent.tree)
        return {"ok": True, "node": node.to_dict()}

    def _knowledge_base_for_path(self, node_id: str) -> str | None:
        """Knowledge base = files on the root→node path (root files apply tree-wide)."""
        if not self._agent.tree:
            return None
        files = []
        for n in self._agent.tree.trace_path(node_id):
            files.extend(n.attachments)
        return _kb_from_files(files)

    # ── Helpers ──────────────────────────────────────────────

    def _tree_payload(self, tree: Tree) -> dict:
        return {
            "id": tree.id,
            "name": tree.name,
            "nodes": {k: v.to_dict() for k, v in tree.nodes.items()},
            "root_id": tree.root_id,
            "node_count": tree.node_count,
            "max_depth": tree.max_depth,
            "leaf_count": tree.leaf_count,
            "created_at": tree.created_at,
            "updated_at": tree.updated_at,
        }


def _kb_from_files(files: list[dict]) -> str | None:
    """Assemble a knowledge-base string from parsed files (with optional notes)."""
    if not files:
        return None
    parts = []
    for a in files:
        header = f"=== 参考文件：{a['name']} ==="
        if a.get("note"):
            header += f"\n【说明】{a['note']}"
        parts.append(header + "\n" + a["content"])
    return "\n\n".join(parts)[:MAX_KB_CHARS]


def _summarize_files(files: list[dict]) -> list[dict]:
    return [{"name": f["name"], "chars": len(f["content"])} for f in files]


def _safe_eval(window, js: str) -> None:
    """Evaluate JS in a window, swallowing errors (e.g. not yet loaded)."""
    try:
        window.evaluate_js(js)
    except Exception:  # noqa: BLE001
        pass


def _friendly_error(e: Exception) -> str:
    msg = str(e) or e.__class__.__name__
    # Tidy the most common openai errors into plain Chinese.
    lowered = msg.lower()
    if "api key" in lowered or "authentication" in lowered or "401" in lowered:
        return "API Key 无效或未授权（401）——请到「设置」检查 Key"
    if "connection" in lowered or "timed out" in lowered or "timeout" in lowered:
        return "无法连接到 API 服务器——请检查 Base URL 与网络"
    if "not found" in lowered or "model" in lowered and "404" in lowered:
        return "模型不存在（404）——请检查「模型」名称是否填对"
    if "quota" in lowered or "insufficient" in lowered or "429" in lowered:
        return "额度不足或请求过快（429）——请检查账户余额"
    return f"请求失败：{msg[:300]}"

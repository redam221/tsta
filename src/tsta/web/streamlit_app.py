"""Streamlit web UI for TSTA — Tree-Structured Thinking Agent.

Provides an interactive tree visualization for AI-assisted self-education.
Features: expand/collapse, right-click follow-up, path tracing, export.
"""

import streamlit as st
import httpx
from datetime import datetime

# ── Page config ────────────────────────────────────────────────

st.set_page_config(
    page_title="TSTA — Tree-Structured Thinking Agent",
    page_icon="\U0001f332",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session State ──────────────────────────────────────────────

DEFAULTS = {
    "tree": None,
    "tree_id": None,
    "selected_node": None,
    "expanded_nodes": set(),
    "api_base": "http://127.0.0.1:8000",
    "show_path": None,
    "editing_node": None,
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── API Helpers ────────────────────────────────────────────────

def api() -> str:
    return st.session_state.api_base


def init_tree(question: str, kb: str | None = None) -> dict | None:
    try:
        r = httpx.post(
            f"{api()}/trees",
            json={"question": question, "knowledge_base": kb},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


def ask_question(tree_id: str, parent_id: str, question: str) -> dict | None:
    try:
        r = httpx.post(
            f"{api()}/trees/{tree_id}/ask",
            json={"parent_id": parent_id, "question": question},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


def trace_path(tree_id: str, node_id: str) -> dict | None:
    try:
        r = httpx.get(f"{api()}/trees/{tree_id}/path/{node_id}", timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


def delete_node(tree_id: str, node_id: str) -> bool:
    try:
        r = httpx.delete(f"{api()}/trees/{tree_id}/nodes/{node_id}", timeout=30)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def load_tree(tree_id: str) -> dict | None:
    try:
        r = httpx.get(f"{api()}/trees/{tree_id}", timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        st.error(f"API error: {e}")
        return None


def list_trees() -> list[dict]:
    try:
        r = httpx.get(f"{api()}/trees", timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return []


def export_paths(tree_id: str) -> list[str]:
    try:
        r = httpx.get(f"{api()}/trees/{tree_id}/export", timeout=30)
        r.raise_for_status()
        return r.json().get("paths", [])
    except httpx.HTTPError:
        return []


# ── Rendering ──────────────────────────────────────────────────

def render_node(node: dict, depth: int = 0) -> None:
    """Render a single node with expand/collapse and interaction controls."""
    nid = node["id"]
    children_ids = node.get("children_ids", [])
    has_children = len(children_ids) > 0
    is_expanded = nid in st.session_state.expanded_nodes

    # Determine indent based on depth
    indent = "  " * depth
    prefix = "│  " * (depth - 1) + "├─ " if depth > 0 else ""

    # Node container
    with st.container():
        # Question row
        cols = st.columns([0.5, 4, 0.7, 0.7, 0.5, 0.5])

        # Expand/collapse toggle
        if has_children:
            icon = "▼" if is_expanded else "▶"
            cols[0].button(
                f"{icon}",
                key=f"toggle_{nid}",
                on_click=lambda: _toggle_expand(nid),
                help="Expand/Collapse children",
                use_container_width=True,
            )
        else:
            cols[0].markdown("·")

        # Question (clickable to select)
        q_preview = node.get("question", "")[:80]
        if len(node.get("question", "")) > 80:
            q_preview += "..."
        clicked = cols[1].button(
            f"**Q: {q_preview}**",
            key=f"select_{nid}",
            help="Click to view details and path",
            use_container_width=True,
        )
        if clicked:
            st.session_state.selected_node = nid
            st.session_state.show_path = None

        # Answer preview
        a_preview = node.get("answer", "")[:60]
        if cols[2].button("\U0001f4ac", key=f"view_{nid}", help="View full answer"):
            st.session_state.selected_node = nid

        # Ask follow-up
        if cols[3].button("➕ Ask", key=f"ask_{nid}", help="Ask a follow-up question"):
            st.session_state[f"asking_{nid}"] = True

        # Path trace
        if cols[4].button("\U0001f50d Path", key=f"path_{nid}", help="Trace think path"):
            st.session_state.show_path = nid

        # Delete
        is_root = node.get("parent_id") is None
        if not is_root:
            if cols[5].button("✖", key=f"del_{nid}", help="Delete this subtree"):
                if delete_node(st.session_state.tree_id, nid):
                    st.success("Deleted")
                    st.rerun()

        # Show answer if selected
        if st.session_state.selected_node == nid:
            with st.expander(f"Answer — {node.get('question', '')[:60]}...", expanded=True):
                st.markdown(node.get("answer", "*No answer yet*"))
                st.caption(f"Node ID: `{nid}` | Created: {node.get('created_at', '')[:19]}")

        # Follow-up question input
        if st.session_state.get(f"asking_{nid}"):
            with st.form(key=f"form_{nid}"):
                follow_up = st.text_area(
                    "Your follow-up question:",
                    key=f"input_{nid}",
                    height=80,
                    placeholder="What else would you like to know about this?",
                )
                sub_cols = st.columns([1, 1])
                submitted = sub_cols[0].form_submit_button("➕ Ask")
                cancelled = sub_cols[1].form_submit_button("Cancel")
                if submitted and follow_up.strip():
                    result = ask_question(st.session_state.tree_id, nid, follow_up.strip())
                    if result:
                        st.success("New node created!")
                        st.session_state[f"asking_{nid}"] = False
                        # Auto-expand parent
                        st.session_state.expanded_nodes.add(nid)
                        st.rerun()
                if cancelled:
                    st.session_state[f"asking_{nid}"] = False
                    st.rerun()

        # Render children if expanded
        if is_expanded and has_children:
            # Load child nodes from tree data
            for cid in children_ids:
                child_node = _get_node_data(cid)
                if child_node:
                    render_node(child_node, depth + 1)


def _get_node_data(node_id: str) -> dict | None:
    """Get node data from the current tree in session."""
    tree = st.session_state.tree
    if not tree:
        return None
    for n in tree.get("nodes", []):
        if n["id"] == node_id:
            return n
    return None


def _toggle_expand(node_id: str) -> None:
    """Toggle expand/collapse for a node."""
    if node_id in st.session_state.expanded_nodes:
        st.session_state.expanded_nodes.discard(node_id)
    else:
        st.session_state.expanded_nodes.add(node_id)


def render_path_trace(node_id: str) -> None:
    """Render the path trace from root to the given node."""
    path_data = trace_path(st.session_state.tree_id, node_id)
    if not path_data:
        return

    st.divider()
    st.subheader("\U0001f50d Knowledge Path Trace")
    st.caption("From initial question to current knowledge — full derivation trace")

    for i, pn in enumerate(path_data["path"]):
        with st.container():
            st.markdown(f"**Step {i + 1}**")
            st.markdown(f"> Q: {pn['question']}")
            a = pn.get("answer", "")
            if a:
                with st.expander(f"A: {a[:100]}..." if len(a) > 100 else f"A: {a}"):
                    st.markdown(a)
            if i < len(path_data["path"]) - 1:
                st.markdown("↓ *led to...*")


# ── Sidebar ────────────────────────────────────────────────────

def render_sidebar() -> None:
    st.sidebar.title("\U0001f332 TSTA")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Trees")

    # New tree
    with st.sidebar.expander("➕ New Knowledge Tree", expanded=False):
        new_question = st.text_area(
            "Root question:",
            key="new_root_q",
            height=80,
            placeholder="e.g., What is a large language model agent?",
        )
        new_kb = st.text_area(
            "Knowledge base (optional):",
            key="new_kb",
            height=60,
            placeholder="Paste reference material...",
        )
        if st.button("Create Tree", use_container_width=True):
            if new_question.strip():
                with st.spinner("Initializing knowledge tree..."):
                    result = init_tree(new_question.strip(), new_kb.strip() or None)
                    if result:
                        st.session_state.tree = result
                        st.session_state.tree_id = result["id"]
                        st.session_state.expanded_nodes = {result["root_id"]}
                        st.session_state.selected_node = result["root_id"]
                        st.success(f"Tree created: {result['name']}")
                        st.rerun()

    # Load existing trees
    trees = list_trees()
    if trees:
        st.sidebar.markdown("### Saved Trees")
        for t in trees:
            cols = st.sidebar.columns([0.7, 0.15, 0.15])
            name = t.get("name", "Untitled")
            t_id = t["id"]
            n_count = t.get("node_count", 0)
            label = f"\U0001f332 {name} ({n_count} nodes)"

            if cols[0].button(label, key=f"load_{t_id}", use_container_width=True):
                tree_data = load_tree(t_id)
                if tree_data:
                    st.session_state.tree = tree_data
                    st.session_state.tree_id = t_id
                    st.session_state.expanded_nodes = {tree_data.get("root_id")}
                    st.session_state.selected_node = tree_data.get("root_id")
                    st.rerun()

            if cols[2].button("\U0001f5d1", key=f"sidebar_del_{t_id}", help="Delete tree"):
                try:
                    httpx.delete(f"{api()}/trees/{t_id}", timeout=30)
                    st.rerun()
                except httpx.HTTPError:
                    st.error("Failed to delete")

    # Export
    st.sidebar.markdown("---")
    if st.session_state.tree_id:
        if st.sidebar.button("\U0001f4e4 Export All Paths", use_container_width=True):
            paths = export_paths(st.session_state.tree_id)
            if paths:
                st.sidebar.download_button(
                    label="\U0001f4e5 Download Markdown",
                    data="\n\n# New Path\n\n".join(paths),
                    file_name="tsta_knowledge_tree.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

    # Stats
    if st.session_state.tree:
        tree = st.session_state.tree
        st.sidebar.markdown("### Tree Stats")
        st.sidebar.metric("Total Nodes", tree.get("node_count", 0))
        st.sidebar.metric("Max Depth", tree.get("max_depth", 0))
        st.sidebar.metric("Leaf Nodes", tree.get("leaf_count", 0))

    # Settings
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Settings")
    api_input = st.sidebar.text_input("API Base URL", value=st.session_state.api_base)
    if api_input != st.session_state.api_base:
        st.session_state.api_base = api_input
        st.rerun()


# ── Main Page ──────────────────────────────────────────────────

st.title("\U0001f332 Tree-Structured Thinking Agent")
st.caption("AI-assisted self-education through tree-structured knowledge exploration")

render_sidebar()

# Main area
if not st.session_state.tree:
    st.info("⬅ Start by creating or loading a knowledge tree from the sidebar.")
    st.markdown("""
    ### How TSTA Works

    TSTA (Tree-Structured Thinking Agent) organizes your learning as a **knowledge tree**:

    1. **Start with a root question** — your main learning topic
    2. **Read the AI answer** — concise, accurate, sourced
    3. **Ask follow-up questions** — click ➕ on any node to branch deeper
    4. **Explore multiple directions** — parallel branches don't interfere
    5. **Trace your learning path** — click \U0001f50d to see how you arrived at any insight

    This approach solves the core problems of linear AI chat:
    - Branch questions won't be lost
    - Context stays clean per branch
    - Knowledge sources are always traceable
    - Hallucinations are structurally suppressed
    """)
else:
    tree = st.session_state.tree
    root_id = tree.get("root_id")

    # Path trace section
    if st.session_state.show_path:
        render_path_trace(st.session_state.show_path)
    else:
        st.markdown(f"**\U0001f332 {tree.get('name', 'Knowledge Tree')}** — {tree.get('node_count', 0)} knowledge nodes")
        st.markdown("*Click ▶ to expand, ➕ Ask to branch, \U0001f50d Path to trace, ✖ to delete*")
        st.divider()

        # Render tree from root
        root_node = _get_node_data(root_id) if root_id else None
        if root_node:
            render_node(root_node, depth=0)
        else:
            st.warning("Tree is empty or corrupted")

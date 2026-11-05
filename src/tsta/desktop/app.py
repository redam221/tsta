"""Desktop entry point — launches the TSTA desktop app in a native window."""

from __future__ import annotations

import sys
from pathlib import Path

import webview

from .api import DesktopAPI
from .settings import DATA_DIR

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def main() -> None:
    api = DesktopAPI()

    window = webview.create_window(
        title="密米尔 Mimir",
        url=str(FRONTEND_DIR / "index.html"),
        js_api=api,
        width=1320,
        height=860,
        min_size=(980, 640),
        background_color="#001b1a",
    )
    api._window = window

    # Detached chat window — pre-created hidden, shown on demand via pop_chat().
    chat_window = webview.create_window(
        title="密米尔 · 对话",
        url=str(FRONTEND_DIR / "chat.html"),
        js_api=api,
        width=560,
        height=720,
        min_size=(360, 400),
        hidden=True,
        background_color="#001b1a",
    )
    api._chat_window = chat_window

    # Clicking ✕ hides + re-docks instead of destroying, so it can be re-shown.
    chat_window.events.closing += api.on_chat_window_closing

    # debug=True opens DevTools (handy while developing); off for normal use.
    debug = "--debug" in sys.argv
    webview.start(debug=debug)


if __name__ == "__main__":
    main()

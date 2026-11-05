"""Launcher for the TSTA desktop app.

Self-locating: adds the package ``src`` dir to sys.path and starts the
pywebview window. Run with ``pythonw.exe`` for a console-free launch.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "src"))

from tsta.desktop.app import main  # noqa: E402


if __name__ == "__main__":
    main()

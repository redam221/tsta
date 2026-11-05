"""CLI entry point for TSTA."""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="tsta",
        description="Tree-Structured Thinking Agent — AI-assisted self-education",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # api
    api_parser = subparsers.add_parser("api", help="Start the FastAPI server")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)
    api_parser.add_argument("--reload", action="store_true")

    # ui
    ui_parser = subparsers.add_parser("ui", help="Start the Streamlit UI")
    ui_parser.add_argument("--api-url", default="http://127.0.0.1:8000")

    # run both
    subparsers.add_parser("run", help="Start both API and UI")

    args = parser.parse_args()

    if args.command == "api":
        import uvicorn
        uvicorn.run(
            "tsta.web.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    elif args.command == "ui":
        import subprocess
        import sys
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "tsta/web/streamlit_app.py",
            "--server.address", "127.0.0.1",
            "--server.port", "8501",
        ])
    elif args.command == "run":
        import subprocess
        import time
        api_proc = subprocess.Popen([
            sys.executable, "-m", "uvicorn",
            "tsta.web.api:app",
            "--host", "127.0.0.1",
            "--port", "8000",
        ])
        time.sleep(2)
        ui_proc = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run",
            "tsta/web/streamlit_app.py",
            "--server.address", "127.0.0.1",
            "--server.port", "8501",
        ])
        print("\nTSTA is running!")
        print("  API: http://127.0.0.1:8000")
        print("  UI:  http://127.0.0.1:8501")
        print("\nPress Ctrl+C to stop.")
        try:
            ui_proc.wait()
        except KeyboardInterrupt:
            api_proc.terminate()
            ui_proc.terminate()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""One-command launcher for the whole project (backend + Vue frontend).

Usage
-----
    python run.py                 # build the frontend if needed, then serve everything on :8000
    python run.py --dev           # Vite dev server (:5173) + FastAPI with auto-reload (:8000)
    python run.py --rebuild       # force a fresh `npm run build` before serving
    python run.py --no-build      # serve an existing frontend/dist as-is
    python run.py --build-only    # build the frontend and exit (no server)
    python run.py --port 9000     # override the API / static port

Everything is started from Python; Node is only used as a build tool for the Vue
frontend and is invoked automatically.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

PYTHON_DEPS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "dotenv": "python-dotenv",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def log(message: str) -> None:
    print(f"[run] {message}", flush=True)


def fail(message: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    print(f"[run] ERROR: {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def _npm_command() -> str:
    """`npm` on POSIX, `npm.cmd` on Windows shells without the shim."""
    for name in ("npm.cmd", "npm"):
        if shutil.which(name):
            return name
    fail("npm was not found on PATH. Install Node.js 18+ to build the Vue frontend.")


def _run(cmd: list[str], cwd: Path) -> None:
    log("$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        fail(f"command failed with exit code {result.returncode}: {' '.join(cmd)}")


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    if ENV_EXAMPLE.exists():
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        log("created .env from .env.example - add your courier credentials to enable live tracking")
    else:  # pragma: no cover - defensive
        log("no .env found; falling back to environment variables / documented defaults")


def ensure_python_deps() -> None:
    missing = [
        package
        for module, package in PYTHON_DEPS.items()
        if importlib.util.find_spec(module) is None
    ]
    if not missing:
        return
    log(f"installing missing Python packages: {', '.join(missing)}")
    _run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], ROOT)


def ensure_node_deps() -> None:
    if (FRONTEND_DIR / "node_modules").is_dir():
        return
    log("installing frontend dependencies (first run only, this can take a minute)")
    _run([_npm_command(), "install"], FRONTEND_DIR)


def build_frontend() -> None:
    ensure_node_deps()
    log("building the Vue frontend into frontend/dist")
    _run([_npm_command(), "run", "build"], FRONTEND_DIR)


def ensure_frontend_build(force: bool, skip: bool) -> None:
    if skip:
        if not (DIST_DIR / "index.html").is_file():
            fail("--no-build was given but frontend/dist/index.html does not exist.")
        log("using the existing frontend build")
        return
    if force or not (DIST_DIR / "index.html").is_file():
        build_frontend()
    else:
        log("frontend build is up to date (use --rebuild to force)")


def start_vite_dev_server() -> subprocess.Popen:
    ensure_node_deps()
    npm = _npm_command()
    log("starting Vite dev server on http://localhost:5173 (Ctrl+C stops both processes)")
    return subprocess.Popen([npm, "run", "dev"], cwd=str(FRONTEND_DIR))


def run_api(host: str, port: int, reload: bool) -> None:
    sys.path.insert(0, str(BACKEND_DIR))
    import uvicorn

    log(f"API + UI available at http://{host}:{port}  (docs: /docs)")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(BACKEND_DIR)] if reload else None,
        log_level="info",
    )


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the order management assessment project.")
    parser.add_argument("--dev", action="store_true", help="Vite dev server + FastAPI auto-reload")
    parser.add_argument("--rebuild", action="store_true", help="force `npm run build` before serving")
    parser.add_argument("--no-build", action="store_true", help="serve the existing dist folder")
    parser.add_argument(
        "--build-only", action="store_true", help="build the frontend and exit without serving"
    )
    parser.add_argument("--host", default=os.getenv("APP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "8000")))
    parser.add_argument("--open", action="store_true", help="open the app in a browser once started")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    ensure_env_file()
    ensure_python_deps()

    vite: subprocess.Popen | None = None
    try:
        if args.dev:
            vite = start_vite_dev_server()
            if args.open:
                time.sleep(2)
                webbrowser.open("http://localhost:5173")
        else:
            ensure_frontend_build(force=args.rebuild, skip=args.no_build)
            if args.build_only:
                log("frontend build finished; exiting because --build-only was requested")
                return 0
            if args.open:
                webbrowser.open(f"http://{args.host}:{args.port}")

        run_api(args.host, args.port, reload=args.dev)
    except KeyboardInterrupt:
        log("shutting down")
    finally:
        if vite is not None:
            vite.terminate()
            try:
                vite.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover
                vite.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

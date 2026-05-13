from __future__ import annotations
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool


def _safe_resolve(base: Path, rel: str) -> Path:
    resolved = (base / rel).resolve()
    if not str(resolved).startswith(str(base)):
        raise PermissionError(f"Path '{rel}' escapes the sandbox root '{base}'.")
    return resolved


def _error(msg: str) -> dict:
    return {"content": [{"type": "text", "text": msg}], "is_error": True}


def _ok(msg: str) -> dict:
    return {"content": [{"type": "text", "text": msg}]}


def make_fs_tools(base_dir: str) -> list:
    """
    Factory that returns a fresh set of sandboxed filesystem @tool functions.
    Each job receives its own closure so base_dir is never shared across jobs.
    """
    base = Path(base_dir).resolve()

    @tool("read_file", "Read the text contents of a file.", {"path": str})
    async def read_file(args: dict[str, Any]) -> dict:
        try:
            text = _safe_resolve(base, args["path"]).read_text(encoding="utf-8")
            return _ok(text)
        except Exception as e:
            return _error(str(e))

    @tool("write_file", "Write text to a file, creating it if needed.", {"path": str, "content": str})
    async def write_file(args: dict[str, Any]) -> dict:
        try:
            path = _safe_resolve(base, args["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            return _ok(f"Written: {path}")
        except Exception as e:
            return _error(str(e))

    @tool("list_directory", "List entries in a directory.", {"path": str})
    async def list_directory(args: dict[str, Any]) -> dict:
        try:
            path = _safe_resolve(base, args.get("path", "."))
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name))
            text = "\n".join(
                f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in entries
            ) or "(empty)"
            return _ok(text)
        except Exception as e:
            return _error(str(e))

    @tool("delete_file", "Delete a file at the given path.", {"path": str})
    async def delete_file(args: dict[str, Any]) -> dict:
        try:
            _safe_resolve(base, args["path"]).unlink()
            return _ok(f"Deleted: {args['path']}")
        except Exception as e:
            return _error(str(e))

    @tool("file_exists", "Check whether a path exists.", {"path": str})
    async def file_exists(args: dict[str, Any]) -> dict:
        exists = _safe_resolve(base, args["path"]).exists()
        return _ok(str(exists))

    @tool("create_directory", "Create a directory and missing parents.", {"path": str})
    async def create_directory(args: dict[str, Any]) -> dict:
        try:
            path = _safe_resolve(base, args["path"])
            path.mkdir(parents=True, exist_ok=True)
            return _ok(f"Created: {path}")
        except Exception as e:
            return _error(str(e))

    return [read_file, write_file, list_directory, delete_file, file_exists, create_directory]

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class LocalTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[ToolExecutionResult]]

    def to_anthropic_tool(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    async def invoke(self, tool_input: dict[str, Any]) -> ToolExecutionResult:
        return await self.handler(tool_input)


def _safe_resolve(base: Path, rel: str) -> Path:
    resolved = (base / rel).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise PermissionError(f"Path '{rel}' escapes the sandbox root '{base}'.") from exc
    return resolved


def _schema(
    properties: dict[str, dict[str, Any]],
    *,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _error(msg: str) -> ToolExecutionResult:
    return ToolExecutionResult(content=msg, is_error=True)


def _ok(msg: str) -> ToolExecutionResult:
    return ToolExecutionResult(content=msg)


def make_fs_tools(base_dir: str) -> list[LocalTool]:
    base = Path(base_dir).resolve()

    async def read_file(args: dict[str, Any]) -> ToolExecutionResult:
        try:
            text = _safe_resolve(base, str(args["path"])).read_text(encoding="utf-8")
            return _ok(text)
        except Exception as exc:
            return _error(str(exc))

    async def write_file(args: dict[str, Any]) -> ToolExecutionResult:
        try:
            path = _safe_resolve(base, str(args["path"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(args["content"]), encoding="utf-8")
            return _ok(f"Written: {path}")
        except Exception as exc:
            return _error(str(exc))

    async def list_directory(args: dict[str, Any]) -> ToolExecutionResult:
        try:
            path = _safe_resolve(base, str(args.get("path", ".")))
            entries = sorted(path.iterdir(), key=lambda entry: (entry.is_file(), entry.name))
            text = "\n".join(
                f"{'DIR ' if entry.is_dir() else 'FILE'} {entry.name}" for entry in entries
            ) or "(empty)"
            return _ok(text)
        except Exception as exc:
            return _error(str(exc))

    async def delete_file(args: dict[str, Any]) -> ToolExecutionResult:
        try:
            _safe_resolve(base, str(args["path"])).unlink()
            return _ok(f"Deleted: {args['path']}")
        except Exception as exc:
            return _error(str(exc))

    async def file_exists(args: dict[str, Any]) -> ToolExecutionResult:
        try:
            exists = _safe_resolve(base, str(args["path"])).exists()
            return _ok(str(exists).lower())
        except Exception as exc:
            return _error(str(exc))

    async def create_directory(args: dict[str, Any]) -> ToolExecutionResult:
        try:
            path = _safe_resolve(base, str(args["path"]))
            path.mkdir(parents=True, exist_ok=True)
            return _ok(f"Created: {path}")
        except Exception as exc:
            return _error(str(exc))

    return [
        LocalTool(
            name="read_file",
            description="Read the UTF-8 text contents of a file inside the workspace.",
            input_schema=_schema(
                {"path": {"type": "string", "description": "Relative path to the file."}},
                required=["path"],
            ),
            handler=read_file,
        ),
        LocalTool(
            name="write_file",
            description="Write UTF-8 text to a file inside the workspace, creating parents if needed.",
            input_schema=_schema(
                {
                    "path": {"type": "string", "description": "Relative path to the file."},
                    "content": {"type": "string", "description": "Text content to write."},
                },
                required=["path", "content"],
            ),
            handler=write_file,
        ),
        LocalTool(
            name="list_directory",
            description="List files and directories inside a workspace directory.",
            input_schema=_schema(
                {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path. Use '.' for the workspace root.",
                    }
                }
            ),
            handler=list_directory,
        ),
        LocalTool(
            name="delete_file",
            description="Delete a file inside the workspace.",
            input_schema=_schema(
                {"path": {"type": "string", "description": "Relative path to the file."}},
                required=["path"],
            ),
            handler=delete_file,
        ),
        LocalTool(
            name="file_exists",
            description="Check whether a file or directory exists inside the workspace.",
            input_schema=_schema(
                {"path": {"type": "string", "description": "Relative path to check."}},
                required=["path"],
            ),
            handler=file_exists,
        ),
        LocalTool(
            name="create_directory",
            description="Create a directory inside the workspace, including any missing parents.",
            input_schema=_schema(
                {"path": {"type": "string", "description": "Relative directory path to create."}},
                required=["path"],
            ),
            handler=create_directory,
        ),
    ]

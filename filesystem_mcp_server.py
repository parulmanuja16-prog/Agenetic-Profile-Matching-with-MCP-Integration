"""MCP server exposing the resume filesystem to the matching agent."""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from tools.fs_tools import (
    SUPPORTED_READ_EXTENSIONS,
    list_files as _list_files,
    read_file as _read_file,
    search_in_file as _search_in_file,
    write_file as _write_file,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_RESUME_DIRECTORY = PROJECT_ROOT / "data" / "resumes"
mcp = FastMCP(
    "resume-filesystem",
    host=os.environ.get("FASTMCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("FASTMCP_PORT", "8000")),
)


def _resume_root() -> Path:
    """Resolve the configured resume directory."""
    configured = os.environ.get("RESUME_DIRECTORY")
    root = Path(configured).expanduser() if configured else DEFAULT_RESUME_DIRECTORY
    return root.resolve()


def _safe_path(path: str | None = None) -> Path:
    """Resolve a path while keeping all filesystem access inside the resume root."""
    root = _resume_root()
    candidate = Path(path).expanduser() if path else root
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path must be inside the configured resume directory: {root}")
    return resolved


def _require_directory(directory: str | None = None) -> Path:
    path = _safe_path(directory)
    if not path.is_dir():
        raise NotADirectoryError(f"Directory not found: {path}")
    return path


def _snapshot(directory: Path) -> set[str]:
    return {
        item.name
        for item in directory.iterdir()
        if item.is_file() and item.suffix.casefold() in SUPPORTED_READ_EXTENSIONS
    }


_directory_snapshots = {
    str(_resume_root()): (
        _snapshot(_resume_root()) if _resume_root().is_dir() else set()
    )
}


@mcp.resource("filesystem://config")
def configuration_resource() -> str:
    """Describe the active server configuration."""
    return json.dumps(
        {
            "server": "resume-filesystem",
            "resume_directory": str(_resume_root()),
            "supported_extensions": sorted(SUPPORTED_READ_EXTENSIONS),
        },
        indent=2,
    )


@mcp.resource("filesystem://resumes")
def resume_catalog_resource() -> str:
    """Return metadata for the supported resumes in the configured directory."""
    directory = _require_directory()
    return json.dumps(_list_files(str(directory)), indent=2)


@mcp.resource("filesystem://resumes/{filename}")
def resume_resource(filename: str) -> str:
    """Return the metadata and extracted text for one resume."""
    path = _safe_path(filename)
    result = _read_file(str(path))
    if not result["success"]:
        raise ValueError(result.get("error", f"Unable to read {filename}"))
    return json.dumps(result, indent=2)


@mcp.tool()
def get_server_config() -> dict[str, Any]:
    """Return the configured resume root and supported file extensions."""
    return json.loads(configuration_resource())


@mcp.tool()
def list_files(directory: str | None = None, extension: str | None = None) -> list[dict[str, Any]]:
    """List resume files in a directory under the configured resume root."""
    path = _require_directory(directory)
    return _list_files(str(path), extension)


@mcp.tool()
def read_file(filepath: str) -> dict[str, Any]:
    """Extract text and metadata from a supported resume file."""
    path = _safe_path(filepath)
    result = _read_file(str(path))
    if not result["success"]:
        raise ValueError(result.get("error", f"Unable to read {filepath}"))
    return result


@mcp.tool()
def write_file(filepath: str, content: str) -> dict[str, Any]:
    """Write UTF-8 text to a file under the configured resume root."""
    path = _safe_path(filepath)
    result = _write_file(str(path), content)
    if not result["success"]:
        raise OSError(result.get("error", f"Unable to write {filepath}"))
    return result


@mcp.tool()
def search_in_file(filepath: str, keyword: str) -> dict[str, Any]:
    """Search a supported resume for a case-insensitive keyword."""
    path = _safe_path(filepath)
    result = _search_in_file(str(path), keyword)
    if not result["success"]:
        raise ValueError(result.get("error", f"Unable to search {filepath}"))
    return result


@mcp.tool()
def batch_process(
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_workers: int = 4,
) -> dict[str, Any]:
    """Read multiple resume files concurrently and return extracted text and metadata."""
    if not 1 <= max_workers <= 16:
        raise ValueError("max_workers must be between 1 and 16.")
    path = _require_directory(directory)
    files = _list_files(str(path))
    normalized_extensions = (
        {
            extension.casefold()
            if extension.startswith(".")
            else f".{extension.casefold()}"
            for extension in extensions
        }
        if extensions is not None
        else SUPPORTED_READ_EXTENSIONS
    )
    selected = [
        item for item in files
        if Path(item["name"]).suffix.casefold() in normalized_extensions
    ]

    def process(metadata: dict[str, Any]) -> dict[str, Any]:
        source = _safe_path(metadata["path"])
        result = _read_file(str(source))
        if not result["success"]:
            raise OSError(result.get("error", f"Unable to read {source}"))
        return result

    processed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process, item): item for item in selected}
        for future in as_completed(futures):
            metadata = futures[future]
            try:
                processed.append(future.result())
            except OSError as exc:
                errors.append({"path": metadata["path"], "error": str(exc)})

    processed.sort(key=lambda item: item["metadata"]["name"].casefold())
    errors.sort(key=lambda item: item["path"].casefold())
    return {"files": processed, "count": len(processed), "errors": errors}


@mcp.tool()
def watch_directory(
    directory: str | None = None,
    interval_seconds: float = 1.0,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Wait for supported resumes added after this server process started."""
    if not 0.1 <= interval_seconds <= 60:
        raise ValueError("interval_seconds must be between 0.1 and 60.")
    if not 0 <= timeout_seconds <= 300:
        raise ValueError("timeout_seconds must be between 0 and 300.")

    path = _require_directory(directory)
    snapshot_key = str(path)
    known_files = _directory_snapshots.setdefault(snapshot_key, _snapshot(path))
    deadline = time.monotonic() + timeout_seconds
    while True:
        current = _snapshot(path)
        discovered = current - known_files
        known_files.update(current)
        if discovered:
            results = []
            for filename in sorted(discovered, key=str.casefold):
                result = _read_file(str(_safe_path(str(path / filename))))
                if result["success"]:
                    results.append(result)
                else:
                    raise OSError(result.get("error", f"Unable to read {filename}"))
            return {"files": results, "count": len(results), "timed_out": False}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"files": [], "count": 0, "timed_out": True}
        time.sleep(min(interval_seconds, remaining))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

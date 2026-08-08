from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence

from .http import SourceError, SourceUnavailable


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def command_prefix() -> tuple[str, ...] | None:
    """Resolve a WebCMD launcher without invoking a shell.

    WebCMD's browser runtime currently needs an x64 Node process on Windows
    ARM64. The setup script installs that runtime under the ignored `.tools`
    directory; every other platform uses the normal `webcmd` executable.
    Explicit paths always win so hosted deployments can provide their own
    runtime without matching this workstation's layout.
    """
    explicit_node = os.environ.get("WEBCMD_NODE_PATH", "").strip()
    explicit_main = os.environ.get("WEBCMD_MAIN_PATH", "").strip()
    if explicit_node and explicit_main:
        if Path(explicit_node).is_file() and Path(explicit_main).is_file():
            return explicit_node, explicit_main
        return None

    if os.name == "nt" and platform.machine().lower() in {"arm64", "aarch64"}:
        node = project_root() / ".tools" / "node-v24.11.1-win-x64" / "node.exe"
        appdata = Path(os.environ.get("APPDATA", ""))
        main = appdata / "npm" / "node_modules" / "@agentrhq" / "webcmd" / "dist" / "src" / "main.js"
        if node.is_file() and main.is_file():
            return str(node), str(main)

    executable = shutil.which(os.environ.get("WEBCMD_BIN", "webcmd"))
    return (executable,) if executable else None


def configured() -> bool:
    return command_prefix() is not None


def _error_detail(stderr: str, stdout: str) -> str:
    text = (stderr or stdout).strip()
    if not text:
        return "WebCMD returned no diagnostic output"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("message:"):
            value = stripped.removeprefix("message:").strip().strip("'\"")
            if value and value != ">-":
                return value
    return " ".join(text.split())[:500]


async def invoke_json(
    args: Sequence[str],
    *,
    source: str,
    timeout: float,
) -> Any:
    """Run one WebCMD command and return its JSON rows.

    Browser sessions, credentials, and cookies remain owned by WebCMD. The API
    receives only the command's normalized output and never shells user input.
    """
    prefix = command_prefix()
    if prefix is None:
        raise SourceUnavailable(source, "WebCMD is not installed or its configured runtime paths are invalid")

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = await asyncio.create_subprocess_exec(
        *prefix,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=creationflags,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise SourceError(source, f"WebCMD did not answer within {timeout:.0f}s") from exc

    stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
    combined = f"{stderr}\n{stdout}"
    if process.returncode != 0:
        detail = _error_detail(stderr, stdout)
        if any(
            marker in combined
            for marker in (
                "AUTH_REQUIRED",
                "BROWSER_CONNECT",
                "Unsupported platform",
                "Unknown command",
                "unknown command",
                "not found",
            )
        ):
            raise SourceUnavailable(source, detail)
        raise SourceError(source, detail)

    if not stdout:
        raise SourceError(source, "WebCMD completed without JSON output")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SourceError(source, "WebCMD returned malformed JSON") from exc


async def installed_commands(timeout: float = 6.0) -> set[str]:
    payload = await invoke_json(("list", "-f", "json"), source="webcmd", timeout=timeout)
    if not isinstance(payload, list):
        raise SourceError("webcmd", "command registry returned an unsupported shape")
    return {
        str(row.get("command", ""))
        for row in payload
        if isinstance(row, dict) and row.get("command")
    }

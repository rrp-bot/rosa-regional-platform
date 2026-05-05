"""
Claude SDK agent runner.

Implements a tool-use loop using the Anthropic Python SDK.
The agent receives a system prompt (persona) + task, then iterates
calling tools (Read, Edit, Write, Bash, Grep, Glob) until it signals
completion or hits the turn limit.
"""
from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import os

import anthropic
import httpx

log = logging.getLogger(__name__)

_VERTEX_PROJECT = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
_VERTEX_REGION = os.environ.get("CLOUD_ML_REGION", "us-east5")
# Proxy CA is in the system trust store; point httpx at it explicitly.
_CA_BUNDLE = os.environ.get("SSL_CERT_FILE", "/etc/pki/tls/cert.pem")

# Tools exposed to the agent
_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "Read",
        "description": "Read a file from disk. Returns the file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or workspace-relative file path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "Write",
        "description": "Write (overwrite) a file with new content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "Edit",
        "description": "Replace an exact string in a file with new text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string", "description": "Exact text to find (must be unique in file)"},
                "new_string": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "Bash",
        "description": "Run a shell command in the workspace directory. Use for read-only commands (ls, find, cat, python -m pytest, etc.). Do not run destructive commands.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "Grep",
        "description": "Search for a pattern in files recursively.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "description": "Directory or file to search (default: .)"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
            },
            "required": ["pattern"],
        },
    },
]

_DISALLOWED_BASH = re.compile(
    r"\b(rm\s+-rf|git\s+push|git\s+reset\s+--hard|chmod\s+777|curl\s+.*\|\s*sh|wget\s+.*\|\s*sh)\b"
)


class AgentRunner:
    """
    Runs a Claude agent session using the Anthropic SDK with a tool-use loop.
    """

    def __init__(
        self,
        workspace: Path,
        model: str = "claude-sonnet-4-6",
        max_turns: int = 50,
    ) -> None:
        self.workspace = Path(workspace)
        self.model = model
        self.max_turns = max_turns
        if _VERTEX_PROJECT:
            # CLAUDE_CODE_SKIP_VERTEX_AUTH=1: proxy injects real credentials at the network layer.
            # Pass a dummy access_token so AnthropicVertex skips google.auth ADC lookup.
            # Use system CA bundle so the proxy's TLS MITM cert is trusted.
            http_client = httpx.Client(verify=_CA_BUNDLE)
            self.client = anthropic.AnthropicVertex(
                project_id=_VERTEX_PROJECT,
                region=_VERTEX_REGION,
                access_token="proxy-injected",
                http_client=http_client,
            )
            # No version suffix — use model name as-is for Vertex
        else:
            self.client = anthropic.Anthropic()

    def run(self, system_prompt: str, task: str) -> str:
        """
        Drive the agent until it stops calling tools or hits max_turns.
        Returns the final text response.
        """
        messages: list[dict] = [{"role": "user", "content": task}]
        final_text = ""

        for turn in range(self.max_turns):
            log.debug("Agent turn %d", turn + 1)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8096,
                system=system_prompt,
                tools=_TOOL_DEFINITIONS,
                messages=messages,
            )

            # Collect text from this response
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            if text_parts:
                final_text = "\n".join(text_parts)
                log.debug("Agent: %s", final_text[:200])

            if response.stop_reason == "end_turn":
                log.info("Agent finished after %d turns", turn + 1)
                break

            if response.stop_reason != "tool_use":
                log.warning("Unexpected stop_reason=%r", response.stop_reason)
                break

            # Process tool calls and build tool results
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = self._dispatch_tool(block.name, block.input)
                log.debug("Tool %s → %s", block.name, str(result)[:120])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

            # Append assistant turn + tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            log.warning("Agent hit max_turns=%d without finishing", self.max_turns)

        return final_text

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _dispatch_tool(self, name: str, inputs: dict) -> Any:
        match name:
            case "Read":
                return self._tool_read(inputs["path"])
            case "Write":
                return self._tool_write(inputs["path"], inputs["content"])
            case "Edit":
                return self._tool_edit(inputs["path"], inputs["old_string"], inputs["new_string"])
            case "Bash":
                return self._tool_bash(inputs["command"])
            case "Grep":
                return self._tool_grep(inputs["pattern"], inputs.get("path", "."))
            case "Glob":
                return self._tool_glob(inputs["pattern"])
            case _:
                return f"Unknown tool: {name}"

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else self.workspace / p

    def _tool_read(self, path: str) -> str:
        try:
            return self._resolve(path).read_text()
        except Exception as e:
            return f"Error reading {path}: {e}"

    def _tool_write(self, path: str, content: str) -> str:
        try:
            p = self._resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Written {p} ({len(content)} chars)"
        except Exception as e:
            return f"Error writing {path}: {e}"

    def _tool_edit(self, path: str, old_string: str, new_string: str) -> str:
        try:
            p = self._resolve(path)
            text = p.read_text()
            count = text.count(old_string)
            if count == 0:
                return f"Error: string not found in {path}"
            if count > 1:
                return f"Error: found {count} occurrences of the string in {path} — be more specific"
            p.write_text(text.replace(old_string, new_string, 1))
            return f"Edited {p}"
        except Exception as e:
            return f"Error editing {path}: {e}"

    def _tool_bash(self, command: str) -> str:
        if _DISALLOWED_BASH.search(command):
            return f"Error: command blocked by policy: {command}"
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=60,
            )
            out = result.stdout + result.stderr
            return out[-4000:] if len(out) > 4000 else out
        except subprocess.TimeoutExpired:
            return "Error: command timed out after 60s"
        except Exception as e:
            return f"Error: {e}"

    def _tool_grep(self, pattern: str, path: str = ".") -> str:
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", pattern, path],
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=15,
            )
            return result.stdout[-3000:] or "(no matches)"
        except Exception as e:
            return f"Error: {e}"

    def _tool_glob(self, pattern: str) -> str:
        try:
            matches = sorted(self.workspace.glob(pattern))
            return "\n".join(str(m.relative_to(self.workspace)) for m in matches) or "(no matches)"
        except Exception as e:
            return f"Error: {e}"

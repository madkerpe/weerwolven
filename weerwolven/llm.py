"""Async wrapper rond `claude -p` (Claude Code CLI, abonnement van de host).

Altijd sonnet. Elke aanroep heeft een timeout; de aanroeper valt terug op
scripttekst als er None terugkomt.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil

log = logging.getLogger("weerwolven.llm")

MODEL = os.environ.get("WW_MODEL", "sonnet")
TIMEOUT = float(os.environ.get("WW_LLM_TIMEOUT", "30"))
DISABLED = os.environ.get("WW_NO_LLM") == "1"


def available() -> bool:
    return not DISABLED and shutil.which("claude") is not None


async def ask(prompt: str, schema: dict | None = None, timeout: float | None = None) -> str | dict | None:
    """Stelt een vraag aan claude -p. Geeft tekst (of dict bij schema) of None bij fout/timeout."""
    if not available():
        return None
    args = [
        "claude", "-p", prompt,
        "--model", MODEL,
        "--output-format", "json",
        "--tools", "",
        "--no-session-persistence",
    ]
    if schema:
        args += ["--json-schema", json.dumps(schema)]
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=os.path.expanduser("~"),
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout or TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            log.warning("claude -p timeout na %ss", timeout or TIMEOUT)
            return None
        if proc.returncode != 0:
            log.warning("claude -p faalde (%s): %s", proc.returncode, err.decode()[:300])
            return None
        data = json.loads(out.decode())
        if data.get("is_error"):
            log.warning("claude -p is_error: %s", str(data.get("result"))[:300])
            return None
        if schema:
            structured = data.get("structured_output")
            if structured is not None:
                return structured
            try:
                return json.loads(data.get("result") or "")
            except Exception:
                return None
        text = (data.get("result") or "").strip()
        return text or None
    except Exception as e:  # noqa: BLE001
        log.warning("claude -p uitzondering: %s", e)
        return None

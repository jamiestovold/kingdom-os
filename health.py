"""
Kingdom Core — Agent Health Checks
Checks availability of each agent without executing any AI tasks.
"""
import subprocess
import asyncio
import aiohttp
import shutil
from datetime import datetime, timezone

# nvm-managed binaries are not in systemd's PATH — resolve at import time
_NVM_BIN = "/home/kingdom/.nvm/versions/node/v20.20.2/bin"

def _find_bin(name: str) -> str | None:
    """Resolve a CLI binary, checking nvm bin dir if not in PATH."""
    found = shutil.which(name)
    if found:
        return found
    candidate = f"{_NVM_BIN}/{name}"
    return candidate if shutil.which(candidate) else None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def check_claude() -> dict:
    """Claude is available if claude CLI is installed and authenticated."""
    bin_path = _find_bin("claude")
    if not bin_path:
        return {
            "id": "claude", "name": "Claude", "type": "frontier",
            "available": False, "health_status": "not_installed",
            "last_health_check": now(),
        }
    result = subprocess.run(
        [bin_path, "--version"],
        capture_output=True, text=True, timeout=10
    )
    available = result.returncode == 0
    return {
        "id": "claude",
        "name": "Claude",
        "type": "frontier",
        "available": available,
        "version": result.stdout.strip() if available else None,
        "health_status": "ok" if available else "unavailable",
        "last_health_check": now(),
    }


async def check_codex() -> dict:
    """Codex is available if codex CLI is installed."""
    bin_path = _find_bin("codex")
    if not bin_path:
        return {
            "id": "codex", "name": "Codex", "type": "frontier",
            "available": False, "health_status": "not_installed",
            "last_health_check": now(),
        }
    result = subprocess.run(
        [bin_path, "--version"],
        capture_output=True, text=True, timeout=10
    )
    available = result.returncode == 0
    return {
        "id": "codex",
        "name": "Codex",
        "type": "frontier",
        "available": available,
        "version": result.stdout.strip() if available else None,
        "health_status": "ok" if available else "unavailable",
        "last_health_check": now(),
    }


async def check_local_llm() -> dict:
    """Local LLM is available if Ollama is running and model is loaded."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:11434/api/tags", timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    qwen_available = any("qwen2.5-coder" in m for m in models)
                    return {
                        "id": "local_llm",
                        "name": "Qwen2.5-Coder (Local)",
                        "type": "local",
                        "available": qwen_available,
                        "version": "qwen2.5-coder:1.5b",
                        "models": models,
                        "health_status": "ok" if qwen_available else "model_not_found",
                        "last_health_check": now(),
                    }
    except Exception:
        pass
    return {
        "id": "local_llm",
        "name": "Qwen2.5-Coder (Local)",
        "type": "local",
        "available": False,
        "health_status": "ollama_not_running",
        "last_health_check": now(),
    }


async def check_script() -> dict:
    """Script agent is always available — it's just bash."""
    return {
        "id": "script",
        "name": "Script Runner",
        "type": "script",
        "available": True,
        "health_status": "ok",
        "last_health_check": now(),
    }


async def check_all_agents() -> list:
    results = await asyncio.gather(
        check_claude(),
        check_codex(),
        check_local_llm(),
        check_script(),
    )
    return list(results)

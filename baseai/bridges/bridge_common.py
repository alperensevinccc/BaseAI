from __future__ import annotations
import os
import re
import json
import asyncio
import hashlib
import statistics
from typing import Any, Dict, Optional, Callable, Awaitable
import traceback

__all__ = [
    "json_strip_to_object",
    "safe_json_parse",
    "sha12",
    "save_json",
    "LatencyMeter",
    "retry_async",
    "endpoint_v1",
    "env",
]


def json_strip_to_object(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith("```"):
        parts = s.split("```")
        for p in parts:
            if "{" in p and "}" in p:
                s = p
                break
    s = re.sub(r"^[^{]*", "", s, flags=re.DOTALL)
    s = re.sub(r"[^}]*$", "", s, flags=re.DOTALL)
    return s.strip()


def safe_json_parse(txt: str) -> Dict[str, Any]:
    if not txt:
        return {}
    try:
        v = json.loads(txt)
        return v if isinstance(v, dict) else {}
    except Exception:
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if m:
            try:
                v = json.loads(m.group(0))
                return v if isinstance(v, dict) else {}
            except Exception:
                return {}
        return {}


def sha12(data: Dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]


def save_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class LatencyMeter:
    def __init__(self) -> None:
        self.samples: list[float] = []

    def add(self, v: float) -> None:
        self.samples.append(v)

    def snapshot(self) -> Dict[str, Any]:
        if not self.samples:
            return {"count": 0, "avg": None, "p95": None, "max": None}
        s = sorted(self.samples)
        p95 = s[int(0.95 * (len(s) - 1))]
        return {
            "count": len(self.samples),
            "avg": round(statistics.mean(self.samples), 4),
            "p95": round(p95, 4),
            "max": round(max(self.samples), 4),
        }


async def retry_async(fn: Callable[[], Awaitable[Any]], retries: int = 3, delay: float = 1.0):
    for attempt in range(retries):
        try:
            return await fn()
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay * (2**attempt))


def endpoint_v1() -> str:
    return os.getenv("GEMINI_API_BASE") or "https://generativelanguage.googleapis.com/v1"


def env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    return v if v not in ("", None) else default

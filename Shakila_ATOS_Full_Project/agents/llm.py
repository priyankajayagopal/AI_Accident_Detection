"""LLM client for language-only tasks (explanations, report narrative). Decisions are NEVER taken from LLM text.

Backends: rule (default, offline template) | anthropic | gemini.  Any failure returns the deterministic template.
"""
import json
import os
from pathlib import Path
from typing import Optional

import httpx

from config import cfg, path


class LLMClient:
    def __init__(self, backend: Optional[str] = None):
        self.backend = backend or os.environ.get("ATOS_LLM_BACKEND") or cfg("app")["llm"]["backend"]
        self.calls = 0
        self.failures = 0

    def _system(self, role: str) -> str:
        f = path("agents", "prompts", f"{role}_prompt.md")
        return f.read_text(encoding="utf-8") if f.exists() else "You are a traffic operations assistant."

    def explain(self, role: str, facts: dict, template: str, max_chars: int = 900) -> str:
        if self.backend == "rule":
            return template
        self.calls += 1
        c = cfg("app")["llm"]
        user = "Facts (JSON):\n" + json.dumps(facts, default=str)[:6000] + "\n\nWrite a concise explanation. Do not change any decision."
        try:
            if self.backend == "anthropic":
                key = os.environ["ANTHROPIC_API_KEY"]
                r = httpx.post("https://api.anthropic.com/v1/messages", timeout=c["timeout_s"],
                               headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                               json={"model": c["anthropic_model"], "max_tokens": 400, "system": self._system(role),
                                     "messages": [{"role": "user", "content": user}]})
                r.raise_for_status()
                text = r.json()["content"][0]["text"]
            elif self.backend == "gemini":
                key = os.environ["GEMINI_API_KEY"]
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{c['gemini_model']}:generateContent?key={key}"
                r = httpx.post(url, timeout=c["timeout_s"], json={"system_instruction": {"parts": [{"text": self._system(role)}]},
                                                                  "contents": [{"parts": [{"text": user}]}]})
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return template
            return text.strip()[:max_chars] or template
        except Exception:
            self.failures += 1
            return template

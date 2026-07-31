from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class LLMResult:
    text: str
    used_web_search: bool = False
    annotations: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class LLMGateway:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.chat_model = os.getenv("LOGISPACE_CHAT_MODEL", "gpt-5.6-luna")
        self.research_model = os.getenv("LOGISPACE_RESEARCH_MODEL", "gpt-5.6-sol")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def respond(self, *, instructions: str, input_text: str, research: bool = False, web_search: bool = False) -> LLMResult:
        if not self.available:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        payload: dict[str, Any] = {
            "model": self.research_model if research else self.chat_model,
            "instructions": instructions,
            "input": input_text,
            "reasoning": {"effort": "medium" if research else "low"},
            "text": {"verbosity": "high" if research else "low"},
        }
        if web_search:
            payload["tools"] = [{"type": "web_search"}]
        request = Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=180 if research else 45) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {error.code}: {detail[:500]}") from error
        except URLError as error:
            raise RuntimeError(f"OpenAI API unavailable: {error.reason}") from error
        text_parts: list[str] = []
        annotations: list[dict[str, Any]] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text_parts.append(content.get("text", ""))
                    annotations.extend(content.get("annotations", []))
        usage = data.get("usage", {})
        return LLMResult(
            text="\n".join(part for part in text_parts if part).strip(),
            used_web_search=web_search,
            annotations=annotations,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    def respond_json(self, *, instructions: str, input_text: str, research: bool = True) -> tuple[Any, LLMResult]:
        result = self.respond(instructions=instructions, input_text=input_text, research=research)
        value = result.text.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1].rsplit("```", 1)[0]
            if value.lstrip().startswith("json"):
                value = value.lstrip()[4:].lstrip()
        try:
            return json.loads(value), result
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Model did not return valid JSON: {error}") from error



gateway = LLMGateway()

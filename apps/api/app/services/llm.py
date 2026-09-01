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


class JSONResponseError(RuntimeError):
    def __init__(self, message: str, raw_text: str, result: LLMResult):
        super().__init__(message)
        self.raw_text = raw_text
        self.result = result


def _strict_response_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize Pydantic JSON Schema for Responses API strict outputs."""
    normalized = json.loads(json.dumps(schema))

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" or "properties" in node:
                properties = node.get("properties", {})
                node["additionalProperties"] = False
                node["required"] = list(properties)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(normalized)
    return normalized


class LLMGateway:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.chat_model = os.getenv("LOGISPACE_CHAT_MODEL", "gpt-5.6-luna")
        self.plan_model = os.getenv("LOGISPACE_PLAN_MODEL", self.chat_model)
        self.research_model = os.getenv("LOGISPACE_RESEARCH_MODEL", "gpt-5.6-sol")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def respond(
        self, *, instructions: str, input_text: str, research: bool = False,
        model: str | None = None,
        web_search: bool = False, max_output_tokens: int | None = None,
        max_tool_calls: int | None = None, reasoning_effort: str | None = None,
        verbosity: str | None = None, response_schema: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> LLMResult:
        if not self.available:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        payload: dict[str, Any] = {
            "model": model or (self.research_model if research else self.chat_model),
            "instructions": instructions,
            "input": input_text,
            "reasoning": {"effort": reasoning_effort or ("medium" if research else "low")},
            "text": {"verbosity": verbosity or ("high" if research else "low")},
        }
        if response_schema is not None:
            payload["text"]["format"] = {
                "type": "json_schema",
                "name": "logispace_response",
                "schema": _strict_response_schema(response_schema),
                "strict": True,
            }
        if web_search:
            payload["tools"] = [{"type": "web_search"}]
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens
        if max_tool_calls is not None:
            payload["max_tool_calls"] = max_tool_calls
        request = Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds or (180 if research else 45)) as response:
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

    def respond_json(
        self, *, instructions: str, input_text: str, research: bool = True,
        model: str | None = None,
        web_search: bool = False, max_tool_calls: int | None = None,
        max_output_tokens: int | None = None, reasoning_effort: str | None = None,
        verbosity: str | None = None, response_schema: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[Any, LLMResult]:
        result = self.respond(
            instructions=instructions, input_text=input_text, research=research, model=model,
            web_search=web_search, max_tool_calls=max_tool_calls,
            max_output_tokens=max_output_tokens, reasoning_effort=reasoning_effort,
            verbosity=verbosity, response_schema=response_schema,
            timeout_seconds=timeout_seconds,
        )
        value = result.text.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1].rsplit("```", 1)[0]
            if value.lstrip().startswith("json"):
                value = value.lstrip()[4:].lstrip()
        try:
            return json.loads(value), result
        except json.JSONDecodeError as error:
            raise JSONResponseError(f"Model did not return valid JSON: {error}", result.text, result) from error


gateway = LLMGateway()

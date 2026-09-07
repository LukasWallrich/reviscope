"""Small OpenRouter structured-output backend used by evaluation experiments."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import socket
from typing import Any, TypeVar

from pydantic import BaseModel

from .backend import Backend, SYSTEM_GUARD, _extract_json, _strict_schema

T = TypeVar("T", bound=BaseModel)


class OpenRouterBackend(Backend):
    name = "openrouter"
    INPUT_USD_PER_MILLION = 0.075
    OUTPUT_USD_PER_MILLION = 0.25

    def __init__(self, model: str, *, timeout: int = 900, max_tokens: int = 6000,
                 max_cost_usd: float = 0.025):
        if model != "z-ai/glm-5.3-flash":
            raise ValueError("evaluation OpenRouter backend currently supports only z-ai/glm-5.3-flash with pinned pricing")
        self.model, self.timeout, self.max_tokens = model, timeout, max_tokens
        self.max_cost_usd = max_cost_usd
        self.effort = None
        self.calls: list[dict[str, Any]] = []
        self.last_finish_reason: str | None = None

    def _request(self, prompt: str, response_model: type[T]) -> str:
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        estimated = ((len(prompt) / 3) * self.INPUT_USD_PER_MILLION
                     + self.max_tokens * self.OUTPUT_USD_PER_MILLION) / 1_000_000
        spent = sum(float(call.get("cost_usd") or 0) for call in self.calls)
        if spent + estimated > self.max_cost_usd:
            raise ValueError(f"OpenRouter request exceeds the ${self.max_cost_usd:.3f} command cost cap")
        schema = _strict_schema(response_model.model_json_schema())
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": 0,
            # GLM-5.3-Flash requires reasoning; low is its smallest supported
            # effort and the completion cap includes those billed tokens.
            "reasoning": {"effort": "low", "exclude": True},
            "provider": {"require_parameters": True},
            "usage": {"include": True},
            "response_format": {"type": "json_schema", "json_schema": {
                "name": response_model.__name__, "strict": True, "schema": schema}},
        }
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "User-Agent": "coarse-socpsy-evaluation/0.2"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"OpenRouter request failed with HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            raise RuntimeError("OpenRouter request failed due to a network error") from None
        if result.get("error") or not result.get("choices"):
            raise RuntimeError("OpenRouter returned an error response")
        choice_record = result["choices"][0]
        self.last_finish_reason = choice_record.get("finish_reason")
        choice = choice_record.get("message", {}).get("content")
        usage = result.get("usage", {})
        prompt_tokens, completion_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
        calculated_cost = None
        if prompt_tokens is not None and completion_tokens is not None:
            calculated_cost = (prompt_tokens * self.INPUT_USD_PER_MILLION
                               + completion_tokens * self.OUTPUT_USD_PER_MILLION) / 1_000_000
        self.calls.append({
            "generation_id": result.get("id"),
            "provider": result.get("provider"),
            "requested_model": self.model,
            "resolved_model": result.get("model"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "cost_usd": usage.get("cost", calculated_cost),
            "price_basis_usd_per_million": {"input": self.INPUT_USD_PER_MILLION,
                                             "output": self.OUTPUT_USD_PER_MILLION},
        })
        if self.last_finish_reason == "length":
            raise RuntimeError("OpenRouter response reached the output-token limit")
        if not isinstance(choice, str) or not choice.strip():
            raise RuntimeError("OpenRouter returned no structured content")
        return choice

    def generate(self, instruction: str, evidence: str, response_model: type[T]) -> T:
        schema = json.dumps(_strict_schema(response_model.model_json_schema()), ensure_ascii=False)
        prompt = f"{SYSTEM_GUARD}\n\nTASK\n{instruction}\n\nJSON SCHEMA\n{schema}\n\nUNTRUSTED EVIDENCE BEGIN\n{evidence}\nUNTRUSTED EVIDENCE END"
        raw = self._request(prompt, response_model)
        try:
            return response_model.model_validate(_extract_json(raw))
        except Exception as first:
            repair = (f"{prompt}\n\nThe following response failed schema validation. Re-extract from the full source above; "
                      f"do not invent or complete content absent from it. Return corrected JSON only.\nINVALID RESPONSE\n{raw}")
            try:
                return response_model.model_validate(_extract_json(self._request(repair, response_model)))
            except Exception as second:
                raise ValueError(f"invalid structured response after one repair: {second}") from first

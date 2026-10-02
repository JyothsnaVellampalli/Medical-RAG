"""Shared OpenRouter HTTP client, used by LLM.generation_registry (chat
completions, for generation) and Evaluation.llm_judge_metrics (the decisions
API, for judging). Two different OpenRouter products with two different
endpoints/schemas -- chat_completion() for ordinary models, decision() for
TypeSafe's "decisions" models (e.g. typesafe/jev-1.13), which score/classify
rather than generate text.

OpenRouter sometimes returns HTTP 200 with an error object in the body
instead of a proper HTTP error status (observed live on chat/completions:
"Upstream error from Nvidia: Service temporarily overloaded") -- both
helpers check the body explicitly since raise_for_status() alone can't catch
that.
"""

from typing import Any

import httpx

from config import settings


class OpenRouterError(Exception):
    pass


def chat_completion(model: str, messages: list[dict[str, str]], timeout: float) -> str:
    response = httpx.post(
        f"{settings.open_router_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.open_router_api_key}"},
        json={"model": model, "messages": messages},
        timeout=timeout,
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    if "error" in data:
        raise OpenRouterError(str(data["error"]))
    return str(data["choices"][0]["message"]["content"] or "")


def decision(
    model: str, state: dict[str, Any], questions: dict[str, Any], timeout: float
) -> dict[str, Any]:
    response = httpx.post(
        settings.open_router_decisions_url,
        headers={"Authorization": f"Bearer {settings.open_router_api_key}"},
        json={"model": model, "state": state, "questions": questions},
        timeout=timeout,
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    if "error" in data:
        raise OpenRouterError(str(data["error"]))
    return dict(data["answers"])

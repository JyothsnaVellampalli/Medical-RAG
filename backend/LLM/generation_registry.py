"""Generation providers. Each method is one backend; generate() is the
registry -- adding a new provider means adding a method below and one line
to the `providers` mapping, same pattern as Retrieval.RetrievalRegistry.

Ollama (local) stays the default and is never removed; OpenRouter is an
additional, opt-in provider selectable per-query from the Ask page.
"""

import ollama

from config import settings
from logger import get_logger
from openrouter_client import chat_completion

log = get_logger(__name__)

OPENROUTER_TIMEOUT_SECONDS = 120.0


class GenerationRegistry:
    def __init__(self) -> None:
        self._ollama_client = ollama.Client(host=settings.ollama_url)

    def ollama_generate(self, prompt: str, system: str) -> str:
        log.info("Generating via Ollama (model=%s)", settings.llm_model)
        result = self._ollama_client.generate(
            model=settings.llm_model, prompt=prompt, system=system, stream=False
        )
        return result.response or ""

    def openrouter_generate(self, prompt: str, system: str) -> str:
        log.info("Generating via OpenRouter (model=%s)", settings.open_router_generation_model)
        return chat_completion(
            model=settings.open_router_generation_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            timeout=OPENROUTER_TIMEOUT_SECONDS,
        )

    def generate(self, provider: str, prompt: str, system: str) -> str:
        providers = {
            "ollama": lambda: self.ollama_generate(prompt, system),
            "openrouter": lambda: self.openrouter_generate(prompt, system),
        }
        if provider not in providers:
            raise ValueError(f"Unknown generation provider: {provider!r}. Valid: {sorted(providers)}")
        return providers[provider]()


generation_registry = GenerationRegistry()

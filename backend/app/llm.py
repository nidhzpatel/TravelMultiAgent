"""LLM provider: Gemini primary, Ollama fallback.

All agents (CrewAI crews and the swarm) get their model from ``get_chat_llm()``.
When a Gemini API key is configured, calls go to Gemini first; if Gemini rate-limits
(429 / quota / resource exhausted), the call transparently falls back to the local
Ollama model. Without a key, Ollama is used directly.
"""

import logging
from functools import lru_cache
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_community.chat_models import ChatOllama

from app.config import get_settings

logger = logging.getLogger(__name__)


def _is_rate_limit(exc: Exception) -> bool:
    """Best-effort detection of rate-limit/quota errors across providers."""
    text = str(exc).lower()
    return any(
        marker in text
        for marker in ("429", "resource exhausted", "rate limit", "rate-limit", "quota", "too many requests")
    )


def _build_ollama() -> ChatOllama:
    settings = get_settings()
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=0.3,
    )


def _build_gemini() -> Optional[BaseChatModel]:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
        )
    except Exception as exc:  # missing package, bad key format at init, etc.
        logger.warning("Gemini unavailable (%s); using Ollama only.", type(exc).__name__)
        return None


class GeminiWithOllamaFallback(BaseChatModel):
    """Chat model that tries Gemini first and falls back to Ollama on rate limits."""

    primary: BaseChatModel
    fallback: BaseChatModel

    @property
    def _llm_type(self) -> str:
        return "gemini-with-ollama-fallback"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            return self.primary._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            if not _is_rate_limit(exc):
                raise
            logger.warning("Gemini rate-limited; falling back to Ollama for this call. (%s)", type(exc).__name__)
            return self.fallback._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            return await self.primary._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            if not _is_rate_limit(exc):
                raise
            logger.warning("Gemini rate-limited; falling back to Ollama for this call. (%s)", type(exc).__name__)
            return await self.fallback._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def bind_tools(self, tools: list, **kwargs: Any) -> "GeminiWithOllamaFallback":
        """Delegate tool binding so CrewAI tool-calling agents keep working."""
        return GeminiWithOllamaFallback(
            primary=self.primary.bind_tools(tools, **kwargs),
            fallback=self.fallback.bind_tools(tools, **kwargs),
        )


@lru_cache
def get_chat_llm() -> BaseChatModel:
    """Return the shared chat model for all agents (Gemini primary, Ollama fallback)."""
    ollama = _build_ollama()
    gemini = _build_gemini()
    if gemini is None:
        return ollama
    return GeminiWithOllamaFallback(primary=gemini, fallback=ollama)

import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from app.core.config import settings
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)


class FallbackChatModel:
    """
    A wrapper class that handles lazy tool binding for primary and fallback chat models.
    """
    def __init__(self, primary: BaseChatModel, fallback: BaseChatModel):
        self.primary = primary
        self.fallback = fallback

    def bind_tools(self, tools, **kwargs):
        """Binds tools to both models and returns a RunnableWithFallbacks."""
        bound_primary = self.primary.bind_tools(tools, **kwargs)
        bound_fallback = self.fallback.bind_tools(tools, **kwargs)
        return bound_primary.with_fallbacks([bound_fallback])


def create_llm(tier: str = "smart") -> BaseChatModel | FallbackChatModel:
    """
    Factory that returns a LangChain chat model based on the configured provider.
    Both ChatGroq and ChatOllama implement BaseChatModel — bind_tools(), ainvoke(),
    and response.tool_calls work identically regardless of which is returned.

    tier: "smart" (70B, main form filling) or "fast" (8B, classification/fallback)
    """
    if settings.LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq

        if tier == "smart":
            rate_limiter = InMemoryRateLimiter(
                requests_per_second=settings.GROQ_REQUESTS_PER_SECOND,
                check_every_n_seconds=0.05,
                max_bucket_size=settings.GROQ_MAX_BUCKET_SIZE,
            )
            logger.info(
                f"[LLM] Creating Groq smart model with fallback: "
                f"primary={settings.GROQ_MODEL_SMART}, fallback={settings.GROQ_MODEL_FAST}"
            )
            primary = ChatGroq(
                api_key=settings.GROQ_API_KEY,
                model=settings.GROQ_MODEL_SMART,
                temperature=0,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT_SECS,
                rate_limiter=rate_limiter,
            )
            fallback = ChatGroq(
                api_key=settings.GROQ_API_KEY,
                model=settings.GROQ_MODEL_FAST,
                temperature=0,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT_SECS,
                rate_limiter=rate_limiter,
            )
            return FallbackChatModel(primary, fallback)
        else:
            rate_limiter = InMemoryRateLimiter(
                requests_per_second=settings.GROQ_REQUESTS_PER_SECOND,
                check_every_n_seconds=0.05,
                max_bucket_size=settings.GROQ_MAX_BUCKET_SIZE,
            )
            logger.info(f"[LLM] Using Groq — model: {settings.GROQ_MODEL_FAST}, tier: {tier}")
            return ChatGroq(
                api_key=settings.GROQ_API_KEY,
                model=settings.GROQ_MODEL_FAST,
                temperature=0,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT_SECS,
                rate_limiter=rate_limiter,
            )

    elif settings.LLM_PROVIDER == "ollama":

        logger.info(f"[LLM] Using Ollama — model: {settings.OLLAMA_MODEL}")
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            temperature=0,
        )

    elif settings.LLM_PROVIDER == "openrouter":
        from langchain_openai import ChatOpenAI

        logger.info(f"[LLM] Using OpenRouter — model: {settings.OPENAI_MODEL}")
        # Note: OpenRouter uses OPENAI_API_KEY in this config
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            temperature=0,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}. "
        f"Valid options: 'groq', 'ollama', 'openrouter'"
    )

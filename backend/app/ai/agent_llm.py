import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from app.core.config import settings

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


def create_llm(tier: str = "smart") -> BaseChatModel:
    """
    Factory that returns a LangChain chat model pointing to Mistral.
    """
    import os
    from langchain_mistralai import ChatMistralAI

    api_key = os.environ.get("MISTRAL_API_KEY") or getattr(settings, "MISTRAL_API_KEY", "YOUR_MISTRAL_API_KEY")
    if not api_key or api_key == "YOUR_MISTRAL_API_KEY":
        logger.warning("[LLM] MISTRAL_API_KEY is not set in environment or settings.")

    logger.info(f"[LLM] Creating Mistral Chat model (model: mistral-small-2603)")
    return ChatMistralAI(
        model="open-mixtral-8x7b",
        api_key=api_key,
        temperature=0.1,
        max_tokens=4000
    )

def calculate_llm_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate estimated cost of LLM call based on model name and tokens.
    Pricing is per 1,000 tokens.
    """
    if not model_name:
        return 0.0
    
    m_clean = model_name.lower()
    
    # Groq pricing
    if "70b" in m_clean:
        input_rate = 0.00059 / 1000.0
        output_rate = 0.00079 / 1000.0
    elif "8b" in m_clean:
        input_rate = 0.00005 / 1000.0
        output_rate = 0.00008 / 1000.0
    # OpenAI general/default pricing
    elif "gpt-4" in m_clean:
        input_rate = 0.005 / 1000.0
        output_rate = 0.015 / 1000.0
    elif "gpt-3.5" in m_clean or "gpt-oss" in m_clean:
        input_rate = 0.0015 / 1000.0
        output_rate = 0.002 / 1000.0
    # Ollama / local is free
    elif "ollama" in m_clean or "local" in m_clean or "llama3" in m_clean:
        input_rate = 0.0
        output_rate = 0.0
    else:
        # Default fallback pricing
        input_rate = 0.00015 / 1000.0
        output_rate = 0.00015 / 1000.0
        
    return (input_tokens * input_rate) + (output_tokens * output_rate)


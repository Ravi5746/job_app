import asyncio
import logging
from app.core.config import settings
from app.ai.agent_tools import AGENT_TOOLS
from langchain_groq import ChatGroq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FallbackChatModel:
    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback

    def bind_tools(self, tools, **kwargs):
        bound_primary = self.primary.bind_tools(tools, **kwargs)
        bound_fallback = self.fallback.bind_tools(tools, **kwargs)
        return bound_primary.with_fallbacks([bound_fallback])

async def test():
    primary = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0,
    )
    fallback = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.1-8b-instant",
        temperature=0,
    )
    
    wrapper = FallbackChatModel(primary, fallback)
    bound = wrapper.bind_tools(AGENT_TOOLS)
    
    print("Bound successfully!")
    print("Bound object type:", type(bound))

if __name__ == "__main__":
    asyncio.run(test())

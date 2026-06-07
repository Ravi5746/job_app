import asyncio
import os
import sys

# Add backend directory to sys.path so we can import app
sys.path.append("d:/automation/Job Applied/backend")
sys.stdout.reconfigure(encoding='utf-8')

# Load env variables manually
with open("d:/automation/Job Applied/backend/.env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

async def test_ollama():
    from app.core.config import settings
    from app.ai.agent_llm import create_llm
    from app.ai.agent_tools import AGENT_TOOLS
    from app.ai.agent_prompts import agent_prompt

    print("--- Configuration ---")
    print(f"LLM Provider: {settings.LLM_PROVIDER}")
    print(f"Ollama Base URL: {settings.OLLAMA_BASE_URL}")
    print(f"Ollama Model: {settings.OLLAMA_MODEL}")

    # Create local LLM
    llm = create_llm("smart")
    bound_llm = llm.bind_tools(AGENT_TOOLS)

    # Simple sample form and profile to test the response
    html_input = '<input id="first_name" data-qa-idx="1" placeholder="First Name" type="text" required />'
    profile_data = {
        "full_name": "Ravi Kumar",
        "email": "ravi@example.com",
        "phone": "+91 9876543210",
        "location": "India",
        "total_years_experience": 5,
        "expected_salary": "Negotiable",
        "notice_period": "Immediate",
        "work_authorization": "Authorized",
        "willing_to_relocate": True,
        "skills": ["Python", "Playwright"],
        "linkedin_url": "https://linkedin.com/in/ravi",
        "github_url": "",
        "portfolio_url": "",
        "qa_answers": "None",
        "resume_snippet": "Software Engineer with 5 years experience in automation.",
        "step_num": 1,
        "html": html_input
    }

    messages = agent_prompt.format_messages(**profile_data)

    print("\nInvoking local Ollama model to generate answer tool calls...")
    try:
        response = await bound_llm.ainvoke(messages)
        print("\n--- Success! Response Received ---")
        print("Model Output Message:", response.content)
        print("Generated Tool Calls:")
        for idx, call in enumerate(response.tool_calls):
            print(f"  [{idx + 1}] Tool: {call['name']} - Args: {call['args']}")
    except Exception as e:
        print("\nError calling local Ollama model:", e)
        print("Please ensure your local Ollama server is running (ollama serve) and the model is pulled.")

if __name__ == "__main__":
    asyncio.run(test_ollama())

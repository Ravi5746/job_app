import os
import sys
import asyncio
import logging
import sqlite3
from typing import Dict, Any

# Ensure backend directory is in path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from app.services.automation.agent.application_agent import ApplicationAgent, ApplicationState
from app.services.automation.agent.langgraph_helpers import active_targets
from langchain_core.runnables import RunnableConfig

# Mock classes for verification
class MockPage:
    def __init__(self):
        self.url = "https://www.linkedin.com/jobs/view/12345/"

    async def screenshot(self, *args, **kwargs):
        logger.info("[MockPage] screenshot taken.")

    async def wait_for_timeout(self, ms):
        pass

class MockJob:
    def __init__(self):
        self.id = 12345
        self.url = "https://www.linkedin.com/jobs/view/12345/"
        self.title = "Mock Software Engineer"
        self.company = "Mock Corp"
        self.status = "open"

class MockQuery:
    def __init__(self, job):
        self.job = job
    def filter(self, *args, **kwargs):
        return self
    def first(self):
        return self.job

class MockDb:
    def __init__(self, job):
        self.job = job
    def query(self, *args):
        return MockQuery(self.job)
    def commit(self):
        pass

class MockHandler:
    def __init__(self):
        self.step_calls = 0

    async def dismiss_popups(self, page):
        pass

    async def get_active_target(self, page):
        return page, None

    async def detect_easy_apply_step(self, target):
        self.step_calls += 1
        if self.step_calls == 1:
            return "contact_info"
        elif self.step_calls == 2:
            return "review"
        else:
            return "success"

    async def click_next_or_review(self, target):
        logger.info("[MockHandler] click_next_or_review called.")

    async def handle_review_step(self, target, modal_locator, db, job):
        logger.info("[MockHandler] handle_review_step called. Submitting...")
        job.status = "applied"
        return True

    async def is_session_expired(self, page):
        return False

class MockDom:
    async def clean_and_tag(self, target, profile):
        return "<html><body>Tagged Content</body></html>"

    async def extract_tagged_fields(self, html):
        return [{"qa_idx": "1", "type": "text", "label": "Full Name", "value": ""}]

    async def check_required_empty(self, target):
        # Return empty list, meaning validation passes
        return []

    async def detect_success_element(self, target):
        return False

class MockSvc:
    def __init__(self):
        self._resume_path = "/tmp/resume.pdf"

    async def _wait_for_page_settle(self, target):
        pass

    async def _fill_field_robust(self, target, field_ans):
        logger.info(f"[MockSvc] _fill_field_robust: {field_ans}")
        return True

class MockLlm:
    async def ainvoke(self, *args, **kwargs):
        class MockResponse:
            tool_calls = []
        return MockResponse()

class MockTools:
    async def execute(self, *args, **kwargs):
        return True

async def verify_flow():
    # Remove any existing checkpoints.db to have a clean slate
    if os.path.exists("checkpoints.db"):
        try:
            os.remove("checkpoints.db")
            logger.info("Cleared existing checkpoints.db")
        except Exception as e:
            logger.warning(f"Could not remove checkpoints.db: {e}")

    job = MockJob()
    db = MockDb(job)
    page = MockPage()
    handler = MockHandler()
    dom = MockDom()
    svc = MockSvc()
    llm = MockLlm()
    tools = MockTools()

    profile = {
        "full_name": "Test User",
        "email": "test@example.com",
        "phone": "1234567890",
        "phone_country_code": "US",
        "questionnaire_answers": {}
    }

    # Instantiate ApplicationAgent
    agent = ApplicationAgent(
        llm=llm,
        dom=dom,
        tools=tools,
        profile=profile,
        resume_text="Mock resume text",
        job_id=job.id,
        user_id=42
    )

    logger.info("Starting isolated graph execution...")
    result = await agent.run(page, db, handler, svc)
    logger.info(f"Agent Run Result: {result}")
    logger.info(f"Job Status post-run: {job.status}")

    # Verify that Sqlite checkpointer saved states in checkpoints.db
    if os.path.exists("checkpoints.db"):
        logger.info("✓ checkpoints.db created successfully!")
        conn = sqlite3.connect("checkpoints.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logger.info(f"Tables in checkpoints.db: {[t[0] for t in tables]}")
        
        cursor.execute("PRAGMA table_info(checkpoints);")
        columns = cursor.fetchall()
        logger.info("Columns in checkpoints table:")
        for col in columns:
            logger.info(f" - {col[1]} ({col[2]})")
        
        cursor.execute("SELECT thread_id, checkpoint_id FROM checkpoints LIMIT 5;")
        checkpoints = cursor.fetchall()
        logger.info("Saved Checkpoints:")
        for cp in checkpoints:
            logger.info(f" - Thread: {cp[0]}, ID: {cp[1]}")
        conn.close()
    else:
        logger.error("✗ checkpoints.db not found!")

if __name__ == "__main__":
    asyncio.run(verify_flow())

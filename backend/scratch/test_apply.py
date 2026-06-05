import sys
import os
import asyncio
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from app.db.session import SessionLocal
from app.services.automation_service import automation_service

async def main():
    db = SessionLocal()
    try:
        # User ID is 2, Job ID is 277 (Full Stack Engineer @ Talink)
        result = await automation_service.apply_to_job(db, 277, 2)
        print("RESULT:", result)
    except Exception as e:
        logging.exception("Failed running apply_to_job")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())

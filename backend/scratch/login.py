import sys
import os
import asyncio
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from app.services.automation_service import automation_service

async def main():
    print("Launching browser for LinkedIn login... Please log in in the opened browser window.")
    await automation_service.launch_login_browser("linkedin")
    print("Browser closed.")

if __name__ == "__main__":
    asyncio.run(main())

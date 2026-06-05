import sys
import os
import asyncio
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from playwright.async_api import async_playwright
from app.db.session import SessionLocal
from app.models.job import Job
from app.core.config import settings

async def check_job_easy_apply(page, url):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)
        
        # Check for Easy Apply button
        apply_btn = page.locator("button.jobs-apply-button, button[aria-label*='Easy Apply'], button:has-text('Easy Apply')").first
        if await apply_btn.is_visible(timeout=1000):
            return True
        return False
    except Exception:
        return False

async def main():
    db = SessionLocal()
    jobs = db.query(Job).all()
    print(f"Scanning {len(jobs)} active jobs for Easy Apply...")
    
    async with async_playwright() as pw:
        user_data_dir = settings.USER_DATA_DIR
        context = await pw.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Anti-detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        easy_apply_jobs = []
        for j in jobs:
            print(f"Checking Job {j.id}: {j.title} @ {j.company}...")
            is_easy = await check_job_easy_apply(page, j.url)
            if is_easy:
                print(f"  -> FOUND Easy Apply for Job {j.id}!")
                easy_apply_jobs.append(j.id)
            else:
                print(f"  -> No Easy Apply.")
                
        print(f"\nScan complete! Easy Apply job IDs found: {easy_apply_jobs}")
        await context.close()
    db.close()

if __name__ == "__main__":
    asyncio.run(main())

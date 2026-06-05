import sys
import os
import asyncio
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from playwright.async_api import async_playwright
from app.core.config import settings

async def main():
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
        
        # Job ID 277 URL
        url = "https://www.linkedin.com/jobs/view/4411044711/"
        print("Navigating to job page...")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        
        # Click Easy Apply
        apply_btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
        if await apply_btn.is_visible():
            await apply_btn.click()
            print("Clicked Easy Apply button.")
            await page.wait_for_timeout(3000)
        else:
            print(f"Easy Apply button not found or already applied. URL: {page.url}")
            await context.close()
            return
            
        # Let's inspect the modal
        modal_selectors = [".artdeco-modal", "[role='dialog']", ".jobs-easy-apply-modal"]
        modal = None
        for m_sel in modal_selectors:
            el = page.locator(m_sel).first
            if await el.is_visible():
                modal = el
                print(f"Found modal using: {m_sel}")
                break
                
        if not modal:
            print("Modal not found.")
            await context.close()
            return
            
        # Loop to inspect steps
        for step in range(1, 10):
            print(f"\n--- STEP {step} ---")
            # Print title of the modal
            title_el = modal.locator("h2").first
            if await title_el.count() > 0:
                print("Modal Title:", await title_el.inner_text())
                
            # Print all button texts inside the modal
            buttons = await modal.locator("button").all()
            btn_texts = []
            for b in buttons:
                txt = (await b.inner_text()).strip()
                aria = await b.get_attribute("aria-label") or ""
                btn_texts.append(f"'{txt}' (aria: '{aria}')")
            print("Buttons found inside modal:", btn_texts)
            
            # Print all input labels/names
            inputs = await modal.locator("input, select, textarea").all()
            input_info = []
            for i in inputs:
                itype = await i.get_attribute("type") or "select/textarea"
                iid = await i.get_attribute("id") or ""
                name = await i.get_attribute("name") or ""
                placeholder = await i.get_attribute("placeholder") or ""
                # Try finding a label
                lbl_txt = ""
                if iid:
                    lbl = modal.locator(f"label[for='{iid}']").first
                    if await lbl.count() > 0:
                        lbl_txt = await lbl.inner_text()
                input_info.append(f"<{itype}> ID: '{iid}' | Name: '{name}' | Label: '{lbl_txt}' | PlaceHolder: '{placeholder}'")
            print("Inputs found inside modal:", input_info)
            
            # Find next/review/submit button and click it to advance
            clicked = False
            for text in ["Next", "Continue", "Review", "Submit application", "Submit"]:
                btn = modal.locator(f"button:has-text('{text}')").last
                if await btn.count() > 0 and await btn.is_visible() and await btn.is_enabled():
                    print(f"Clicking '{text}' button to advance...")
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    clicked = True
                    break
            if not clicked:
                print("No active next/review/submit button found to click.")
                break
                
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())

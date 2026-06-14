from playwright.async_api import Page

URL_PATTERNS = {
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
    "boards.greenhouse.io": "greenhouse",
    "myworkdayjobs.com": "workday",
    "icims.com": "icims",
    "smartrecruiters.com": "smartrecruiters",
    "taleo": "taleo",
    "bamboohr.com": "bamboohr",
    "apply.workable.com": "workable",
    "linkedin.com": "linkedin",
    "indeed.com": "indeed",
    "glassdoor.com": "glassdoor",
}

DOM_SIGNATURES = {
    "lever": "#application-form, .posting-page",
    "greenhouse": "#app_form, #application_form, [data-mapped-field]",
    "ashby": "[data-ashby-job-posting-brief]",
    "workday": "[data-automation-id], .WDFC",
    "icims": ".iCIMS_MainWrapper",
    "smartrecruiters": "[data-test='job-apply']",
}

def detect_ats(page: Page) -> str:
    url = page.url.lower()
    for domain, ats in URL_PATTERNS.items():
        if domain in url:
            return ats
    return "unknown"

async def detect_ats_dom(page: Page) -> str:
    ats_from_url = detect_ats(page)
    if ats_from_url != "unknown":
        return ats_from_url

    for ats, selector in DOM_SIGNATURES.items():
        try:
            locators = page.locator(selector)
            if await locators.count() > 0:
                return ats
        except Exception:
            continue
    return "unknown"

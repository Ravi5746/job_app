import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from app.services.scraper_service import scraper_service

print("RAPIDAPI_HOST:", settings.RAPIDAPI_HOST)
print("RAPIDAPI_KEY:", settings.RAPIDAPI_KEY[:10] + "..." if settings.RAPIDAPI_KEY else "None")

print("\nTesting JSearch search_jobs...")
jobs = scraper_service.search_jobs("Software Engineer", "India")
print("Jobs count:", len(jobs))
if jobs:
    print("\nPublishers in results:")
    for i, job in enumerate(jobs[:10]):
        print(f"{i+1}. Title: {job.get('job_title')}\n   Publisher: {job.get('job_publisher')}\n   Link: {job.get('job_apply_link')}\n")
else:
    print("No jobs found or JSearch API failed.")

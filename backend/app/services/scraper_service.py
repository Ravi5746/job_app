import requests
from typing import List, Dict, Any
from app.core.config import settings

class ScraperService:
    def __init__(self):
        self.url = f"https://{settings.RAPIDAPI_HOST}/search"
        self.headers = {
            "x-rapidapi-key": settings.RAPIDAPI_KEY,
            "x-rapidapi-host": settings.RAPIDAPI_HOST
        }

    def search_jobs(self, query: str, location: str = "India", page: int = 1, date_posted: str = "today") -> List[Dict[str, Any]]:
        # Search globally across all job boards
        querystring = {
            "query": query,
            "page": str(page),
            "num_pages": "5",
            "date_posted": date_posted,
            "location": location,
            "remote_jobs_only": "false"
        }
        try:
            response = requests.get(self.url, headers=self.headers, params=querystring)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            print(f"Error searching jobs via JSearch: {e}")
            return []

    def get_job_details(self, job_id: str) -> Dict[str, Any]:
        url = f"https://{settings.RAPIDAPI_HOST}/job-details"
        querystring = {"job_id": job_id, "extended_publisher_details": "false"}
        
        try:
            response = requests.get(url, headers=self.headers, params=querystring)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [{}])[0]
        except Exception as e:
            print(f"Error fetching job details for {job_id}: {e}")
            return {}

scraper_service = ScraperService()



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

    def _fetch_linkedin_desc(self, job_id: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        url = f"https://www.linkedin.com/jobs/view/{job_id}/"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html = response.text
            import re
            match = re.search(r'class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if match:
                description = re.sub(r'<[^>]+>', '\n', match.group(1))
                description = re.sub(r'\n+', '\n', description).strip()
                return description
        except:
            pass
        return ""

    def search_linkedin_guest(self, query: str, location: str = "India") -> List[Dict[str, Any]]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        import urllib.parse
        import re
        from concurrent.futures import ThreadPoolExecutor

        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={urllib.parse.quote(query)}&location={urllib.parse.quote(location)}"
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            html = response.text
            
            li_blocks = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
            jobs = []
            
            for li in li_blocks:
                url_match = re.search(r'href="([^"]*linkedin\.com/jobs/view/[^"]+)"', li)
                if not url_match:
                    continue
                url_raw = url_match.group(1).split("?")[0]
                job_id_match = re.search(r'-(\d+)$', url_raw) or re.search(r'/view/(\d+)', url_raw)
                if not job_id_match:
                    continue
                job_id = job_id_match.group(1)
                direct_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                
                title_match = re.search(r'class="[^"]*search-card__title[^"]*"[^>]*>\s*(.*?)\s*</h3>', li, re.DOTALL)
                title = title_match.group(1).strip() if title_match else "Unknown Title"
                title = re.sub(r'<[^>]+>', '', title).strip()
                
                company_match = re.search(r'class="[^"]*search-card__subtitle[^"]*"[^>]*>\s*(.*?)\s*</h4>', li, re.DOTALL)
                company = company_match.group(1).strip() if company_match else "Unknown Company"
                company = re.sub(r'<[^>]+>', '', company).strip()
                
                location_match = re.search(r'class="[^"]*search-card__location[^"]*"[^>]*>\s*(.*?)\s*</span>', li, re.DOTALL)
                loc = location_match.group(1).strip() if location_match else location
                loc = re.sub(r'<[^>]+>', '', loc).strip()
                
                jobs.append({
                    "job_id": job_id,
                    "job_title": title,
                    "employer_name": company,
                    "job_city": loc,
                    "job_country": "",
                    "job_description": "",
                    "job_apply_link": direct_url,
                    "job_publisher": "LinkedIn"
                })
                
            # Fetch descriptions concurrently for top 8 jobs
            top_jobs = jobs[:8]
            
            def load_desc(job):
                desc = self._fetch_linkedin_desc(job["job_id"])
                job["job_description"] = desc if desc else f"Job post for {job['job_title']} at {job['employer_name']}. Please see LinkedIn for more details."
                
            with ThreadPoolExecutor(max_workers=5) as executor:
                executor.map(load_desc, top_jobs)
                
            return top_jobs
        except Exception as e:
            print(f"Error in search_linkedin_guest: {e}")
            return []

scraper_service = ScraperService()



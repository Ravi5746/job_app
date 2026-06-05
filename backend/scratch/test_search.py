import requests
import re

def test_fetch_linkedin_public_description(job_id):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    url = f"https://www.linkedin.com/jobs/view/{job_id}/"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text
        
        # Look for description tags, e.g. <div class="show-more-less-html__markup ...">
        # Or search for description content using regex
        match = re.search(r'class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            description = re.sub(r'<[^>]+>', '\n', match.group(1))
            description = re.sub(r'\n+', '\n', description).strip()
            return description
        else:
            # Let's save html for debugging
            with open("scratch/job_view.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Description pattern not found. Saved HTML.")
            return ""
    except Exception as e:
        print(f"Error fetching description: {e}")
        return ""

if __name__ == "__main__":
    desc = test_fetch_linkedin_public_description("4418837779")
    print("Description length:", len(desc))
    print(desc[:500])

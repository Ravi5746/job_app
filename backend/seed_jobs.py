from app.db.session import SessionLocal
from app.models.job import Job

def seed_jobs():
    db = SessionLocal()
    jobs = [
        {
            "title": "Senior Frontend Engineer",
            "company": "Google",
            "location": "Mountain View, CA",
            "description": "We are looking for a Senior Frontend Engineer...",
            "source": "LinkedIn",
            "url": "https://google.com/jobs"
        },
        {
            "title": "AI Research Scientist",
            "company": "OpenAI",
            "location": "San Francisco, CA",
            "description": "Join our research team...",
            "source": "Indeed",
            "url": "https://openai.com/careers"
        },
        {
            "title": "Full Stack Developer",
            "company": "Meta",
            "location": "Menlo Park, CA",
            "description": "Help us build the metaverse...",
            "source": "LinkedIn",
            "url": "https://meta.com/jobs"
        }
    ]
    
    for job_data in jobs:
        db_job = Job(**job_data)
        db.add(db_job)
    
    db.commit()
    db.close()
    print("Seeded jobs successfully")

if __name__ == "__main__":
    seed_jobs()

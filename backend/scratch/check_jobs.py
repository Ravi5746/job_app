import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal
from app.models.job import Job

db = SessionLocal()
try:
    jobs = db.query(Job).all()
    print(f"Total jobs: {len(jobs)}")
    for j in jobs:
        print(f"ID: {j.id} | Title: {j.title} | Company: {j.company} | Status: {j.status} | URL: {j.url}")
finally:
    db.close()

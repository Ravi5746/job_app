import sys
import os
import asyncio
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.models.user import User
from app.routes.jobs import search_external_jobs

async def run_test():
    db = SessionLocal()
    try:
        # Get a user
        user = db.query(User).first()
        if not user:
            print("No user found in DB")
            return
        
        print(f"Running search for 'MERN Stack Developer' with user: {user.email}")
        
        # We need to mock background_tasks
        class MockBackgroundTasks:
            def add_task(self, func, *args, **kwargs):
                print(f"Background task added: {func.__name__} with args: {args}")
        
        bg_tasks = MockBackgroundTasks()
        
        # Call search_external_jobs
        jobs = await search_external_jobs(
            query="MERN Stack Developer",
            location="India",
            db=db,
            current_user=user,
            background_tasks=bg_tasks
        )
        
        print(f"Returned {len(jobs)} jobs")
        sources = {}
        for j in jobs:
            sources[j.source] = sources.get(j.source, 0) + 1
        print("Job sources in returned list:", sources)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test())

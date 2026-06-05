import asyncio
import os
import sys

sys.path.append("d:/automation/Job Applied/backend")
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/automation/Job Applied/backend/.env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

async def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.ai.hermes import hermes_agent

    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    from sqlalchemy import text
    result = db.execute(text("SELECT id, content FROM resumes ORDER BY id DESC LIMIT 1")).fetchone()
    resume_id, resume_content = result
    
    print(f"Testing hermes_agent with resume ID: {resume_id} ({len(resume_content)} chars)")
    
    try:
        profile = await hermes_agent.extract_profile_data(resume_content)
        print("SUCCESS! Profile extracted.")
        print("Name:", profile.get("full_name"))
        print("Email:", profile.get("email"))
        print("Phone:", profile.get("phone"))
        print("Skills (Count):", len(profile.get("skills", [])))
        print("Work Experience (Count):", len(profile.get("work_experience", [])))
        print("Education (Count):", len(profile.get("education", [])))
        print("Certifications (Count):", len(profile.get("certifications", [])))
    except Exception as e:
        print("Integration test failed:", e)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sys

# Add backend directory to sys.path so we can import app
sys.path.append("d:/automation/Job Applied/backend")
# Reconfigure stdout to avoid Windows charmap encoding issues
sys.stdout.reconfigure(encoding='utf-8')

# Load env variables manually before any imports
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
    if not result:
        print("No resumes found in database.")
        return
        
    resume_id, resume_content = result
    print(f"Testing direct hermes_agent with resume ID: {resume_id}")
    print(f"Default model configured: {hermes_agent.model_name}")
    
    try:
        profile_data = await hermes_agent.extract_profile_data(resume_content)
        print("SUCCESS! Hermes successfully extracted data.")
        print("Keys:", list(profile_data.keys()))
        print("Full Name:", profile_data.get("full_name"))
        print("Email:", profile_data.get("email"))
        print("Phone:", profile_data.get("phone"))
        print("Skills (Count):", len(profile_data.get("skills", [])))
        print("Work Experience (Count):", len(profile_data.get("work_experience", [])))
    except Exception as e:
        print("Error during direct extraction:", e)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())

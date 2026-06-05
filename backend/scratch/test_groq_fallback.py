import asyncio
import os
import json
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openai import AsyncOpenAI

sys.stdout.reconfigure(encoding='utf-8')

with open("d:/automation/Job Applied/backend/.env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

async def main():
    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    from sqlalchemy import text
    result = db.execute(text("SELECT id, content FROM resumes ORDER BY id DESC LIMIT 1")).fetchone()
    resume_id, resume_content = result
    
    groq_key = os.environ.get("GROQ_API_KEY")
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=groq_key
    )
    
    # Try llama-3.1-8b-instant
    model_name = "llama-3.1-8b-instant"
    
    prompt = f"""
    Extract ALL of the following structured data from this resume.
    Return a JSON object with EXACTLY these keys:
    {{
        "full_name": "string",
        "email": "string or null",
        "phone": "string or null",
        "current_location": "string or null",
        "linkedin_url": "string or null",
        "github_url": "string or null",
        "portfolio_url": "string or null (any other website/portfolio link)",
        "summary": "2-3 sentence professional summary of the candidate",
        "skills": ["list", "of", "technical", "and", "professional", "skills"],
        "work_experience": [
            {{
                "company": "Company Name",
                "role": "Job Title",
                "start": "MMM YYYY or YYYY",
                "end": "MMM YYYY or Present",
                "description": "1-2 sentence summary of responsibilities"
            }}
        ],
        "total_years_experience": 0,
        "education": [
            {{
                "degree": "Degree Name",
                "institution": "University/College Name",
                "year": "Graduation Year",
                "field": "Field of Study"
            }}
        ],
        "certifications": [
            {{
                "name": "Certification Name",
                "issuer": "Issuing Organization",
                "year": "Year or null"
            }}
        ],
        "languages": ["English", "Hindi"]
    }}
    RESUME:
    {resume_content[:10000]}
    """
    
    try:
        print(f"Sending extraction request to Groq model: {model_name}...")
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2000
        )
        raw_content = response.choices[0].message.content
        parsed = json.loads(raw_content)
        print("SUCCESSFULLY PARSED EXTRACTED PROFILE VIA GROQ LLAMA 8B!")
        print("Keys:", list(parsed.keys()))
        print("Name:", parsed.get("full_name"))
        print("Email:", parsed.get("email"))
        print("Skills (Count):", len(parsed.get("skills", [])))
        print("Work Experience (Count):", len(parsed.get("work_experience", [])))
    except Exception as e:
        print("Error with Llama 8B:", e)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())

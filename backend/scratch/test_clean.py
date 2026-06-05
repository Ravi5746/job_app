import os
import re

with open("d:/automation/Job Applied/backend/.env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    from sqlalchemy import text
    result = db.execute(text("SELECT id, content FROM resumes ORDER BY id DESC LIMIT 1")).fetchone()
    resume_id, resume_content = result
    
    print(f"Original length: {len(resume_content)}")
    
    # 1. Clean consecutive newlines
    cleaned = re.sub(r'\n+', '\n', resume_content)
    # 2. Clean consecutive spaces
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    # 3. Clean spaces around newlines
    cleaned = re.sub(r'\s*\n\s*', '\n', cleaned)
    
    print(f"Cleaned length: {len(cleaned)}")
    print(f"Ratio: {len(cleaned) / len(resume_content):.2%}")
    
    # Print the first 500 chars of cleaned text
    print("\nCleaned Sample:")
    print(cleaned[:500])
    
    db.close()

if __name__ == "__main__":
    main()

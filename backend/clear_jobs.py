import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def clear_jobs():
    try:
        # Get connection details from environment
        db_url = "postgresql://postgres:Sapan990@127.0.0.1:5432/job_automation"
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Execute delete
        print("Deleting all jobs from database...")
        cur.execute("TRUNCATE TABLE jobs RESTART IDENTITY CASCADE;")
        
        conn.commit()
        print("Successfully deleted all jobs.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error deleting jobs: {e}")

if __name__ == "__main__":
    clear_jobs()

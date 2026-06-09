import os
import sys

# Ensure backend directory is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.job import Job
from app.models.application import Application, ApplicationStep
from app.core.config import BASE_DIR

def clear_all_job_data():
    db = SessionLocal()
    try:
        print("Clearing application_steps...")
        db.query(ApplicationStep).delete()
        print("Clearing applications...")
        db.query(Application).delete()
        print("Clearing jobs...")
        db.query(Job).delete()
        db.commit()
        print("Database transaction committed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error occurred during database clearing: {e}")
    finally:
        db.close()

    # Also clear the LangGraph checkpoint SQLite DB
    checkpoint_db_path = os.path.join(BASE_DIR, "checkpoints.db")
    if os.path.exists(checkpoint_db_path):
        try:
            print(f"Removing checkpoints.db at {checkpoint_db_path}...")
            os.remove(checkpoint_db_path)
            # SQLite creates temporary -shm and -wal files sometimes, let's delete them if they exist
            for suffix in ["-shm", "-wal"]:
                p = checkpoint_db_path + suffix
                if os.path.exists(p):
                    os.remove(p)
            print("Checkpoints database files deleted successfully.")
        except Exception as e:
            print(f"Error removing checkpoints.db: {e}")

if __name__ == "__main__":
    clear_all_job_data()

from app.db.session import SessionLocal
from app.models.job import Job

def clear_jobs():
    db = SessionLocal()
    try:
        num_deleted = db.query(Job).delete()
        db.commit()
        print(f"Successfully deleted {num_deleted} jobs from the database.")
    except Exception as e:
        db.rollback()
        print(f"Error clearing jobs: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_jobs()

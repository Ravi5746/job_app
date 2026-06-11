import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.qa_cache import QACache

def clear_qa_cache():
    db = SessionLocal()
    try:
        print("Clearing Q&A cache (qa_cache table)...")
        count = db.query(QACache).delete()
        db.commit()
        print(f"Successfully deleted {count} cached Q&A entries.")
    except Exception as e:
        db.rollback()
        print(f"Error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_qa_cache()

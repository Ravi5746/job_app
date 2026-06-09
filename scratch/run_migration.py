import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import text
from app.db.session import engine

def main():
    print("Connecting to database...")
    with engine.begin() as conn:
        print("Checking if user_id column exists in qa_cache...")
        res = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='qa_cache' AND column_name='user_id';
        """)).fetchone()
        
        if not res:
            print("Adding user_id column to qa_cache...")
            conn.execute(text("ALTER TABLE qa_cache ADD COLUMN user_id INTEGER;"))
            conn.execute(text("CREATE INDEX ix_qa_cache_user_id ON qa_cache (user_id);"))
        else:
            print("user_id column already exists.")

        print("Removing unique constraint on question_text if it exists...")
        # Query postgres for unique or primary key constraints on the table
        constraints = conn.execute(text("""
            SELECT conname 
            FROM pg_constraint 
            WHERE conrelid = 'qa_cache'::regclass AND contype = 'u';
        """)).fetchall()
        
        for c in constraints:
            cname = c[0]
            if cname != 'uq_user_question':
                print(f"Dropping constraint: {cname}")
                try:
                    conn.execute(text(f"ALTER TABLE qa_cache DROP CONSTRAINT {cname};"))
                except Exception as e:
                    print(f"Error dropping constraint {cname}: {e}")

        # Try to drop index that might enforce uniqueness
        try:
            conn.execute(text("DROP INDEX IF EXISTS ix_qa_cache_question_text;"))
            # Recreate it as a regular index
            conn.execute(text("CREATE INDEX ix_qa_cache_question_text ON qa_cache (question_text);"))
        except Exception as e:
            print(f"Index check/recreate ignored: {e}")

        # Add composite unique constraint
        print("Adding composite unique constraint (user_id, question_text) if it doesn't exist...")
        try:
            conn.execute(text("ALTER TABLE qa_cache ADD CONSTRAINT uq_user_question UNIQUE (user_id, question_text);"))
            print("Successfully added uq_user_question constraint.")
        except Exception as e:
            print(f"uq_user_question constraint might already exist: {e}")

        print("Migration complete!")

if __name__ == "__main__":
    main()

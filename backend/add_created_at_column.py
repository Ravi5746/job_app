from sqlalchemy import text
from app.db.session import engine

def add_created_at_column():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now();"))
        conn.commit()

if __name__ == "__main__":
    add_created_at_column()

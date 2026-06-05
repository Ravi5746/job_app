from app.db.session import engine
from sqlalchemy import text

def add_columns():
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE jobs ADD COLUMN IF NOT EXISTS skills TEXT'))
            conn.execute(text('ALTER TABLE jobs ADD COLUMN IF NOT EXISTS requirements TEXT'))
            conn.execute(text('ALTER TABLE jobs ADD COLUMN IF NOT EXISTS category VARCHAR(255)'))
            conn.commit()
            print("Successfully added missing columns!")

    except Exception as e:
        print(f"Error adding columns: {e}")

if __name__ == "__main__":
    add_columns()

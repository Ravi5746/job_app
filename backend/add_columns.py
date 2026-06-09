from sqlalchemy import text
from app.db.session import engine

def main():
    print("Adding columns to users table...")
    columns = [
        ("gender", "VARCHAR"),
        ("disability_status", "VARCHAR"),
        ("requires_sponsorship", "BOOLEAN"),
        ("country_of_citizenship", "VARCHAR"),
        ("preferred_work_models", "JSON"),
        ("address_line_1", "VARCHAR"),
        ("address_line_2", "VARCHAR"),
        ("city", "VARCHAR"),
        ("state_province", "VARCHAR"),
        ("postal_code", "VARCHAR"),
        ("country", "VARCHAR"),
    ]
    with engine.connect() as conn:
        for col_name, col_type in columns:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};"))
                conn.commit()
                print(f"Added {col_name}")
            except Exception as e:
                print(f"Column {col_name} might already exist: {e}")
                conn.rollback()

if __name__ == "__main__":
    main()

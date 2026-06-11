import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from sqlalchemy import inspect, text
from app.db.session import engine


def main():
    print("Connecting to database...")
    inspector = inspect(engine)
    table_name = "work_experiences"

    if table_name not in inspector.get_table_names():
        print(f"Table '{table_name}' does not exist. Please ensure the backend database has been initialized.")
        return

    columns = [column["name"] for column in inspector.get_columns(table_name)]
    if "skills" in columns:
        print("Column 'skills' already exists on work_experiences. No action required.")
        return

    dialect = engine.dialect.name
    print(f"Detected database dialect: {dialect}")

    alter_sql = ""
    if dialect == "sqlite":
        alter_sql = "ALTER TABLE work_experiences ADD COLUMN skills TEXT;"
    elif dialect in ("postgresql", "postgres"):
        alter_sql = "ALTER TABLE work_experiences ADD COLUMN skills JSON;"
    else:
        alter_sql = "ALTER TABLE work_experiences ADD COLUMN skills JSON;"

    try:
        with engine.begin() as conn:
            conn.execute(text(alter_sql))
        print("Successfully added 'skills' column to work_experiences.")
    except Exception as err:
        print(f"Failed to add skills column: {err}")


if __name__ == "__main__":
    main()

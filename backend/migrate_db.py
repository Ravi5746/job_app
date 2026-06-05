from sqlalchemy import create_engine, text
from app.core.config import settings


def run_safe_migration(conn, description, check_sql, alter_sql):
    """Run a single migration step safely with its own transaction."""
    try:
        result = conn.execute(text(check_sql))
        if not result.fetchone():
            print(f"  Adding: {description}...")
            conn.execute(text(alter_sql))
            conn.commit()
            print(f"  [OK] {description} added.")
        else:
            print(f"  [SKIP] {description} already exists.")
    except Exception as e:
        conn.rollback()
        print(f"  [WARN] {description}: {e}")


def migrate():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:

        # ── Jobs table columns ──
        print("\n=== Jobs table ===")
        run_safe_migration(
            conn, "jobs.tailored_resume",
            "SELECT column_name FROM information_schema.columns WHERE table_name='jobs' AND column_name='tailored_resume'",
            "ALTER TABLE jobs ADD COLUMN tailored_resume TEXT"
        )
        run_safe_migration(
            conn, "jobs.expires_at",
            "SELECT column_name FROM information_schema.columns WHERE table_name='jobs' AND column_name='expires_at'",
            "ALTER TABLE jobs ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE"
        )

        # ── Resumes table columns ──
        print("\n=== Resumes table ===")
        run_safe_migration(
            conn, "resumes.search_suggestions",
            "SELECT column_name FROM information_schema.columns WHERE table_name='resumes' AND column_name='search_suggestions'",
            "ALTER TABLE resumes ADD COLUMN search_suggestions TEXT"
        )

        # ── Users table: basic profile columns ──
        print("\n=== Users table (profile columns) ===")
        basic_profile_columns = {
            "phone": "VARCHAR",
            "location": "VARCHAR",
            "linkedin_url": "VARCHAR",
            "github_url": "VARCHAR",
            "summary": "TEXT",
            "questionnaire": "JSON",
        }
        for col_name, col_type in basic_profile_columns.items():
            run_safe_migration(
                conn, f"users.{col_name}",
                f"SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='{col_name}'",
                f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"
            )

        # ── Users table: enrichment columns (skills, experience, etc.) ──
        print("\n=== Users table (enrichment columns) ===")
        enrichment_columns = {
            "skills": "JSON",
            "work_experience": "JSON",
            "projects": "JSON",
            "total_years_experience": "INTEGER",
            "education": "JSON",
            "certifications": "JSON",
            "desired_job_titles": "JSON",
            "expected_salary": "VARCHAR",
            "notice_period": "VARCHAR",
            "work_authorization": "VARCHAR",
            "willing_to_relocate": "BOOLEAN",
            "languages": "JSON",
            "portfolio_url": "VARCHAR",
        }
        for col_name, col_type in enrichment_columns.items():
            run_safe_migration(
                conn, f"users.{col_name}",
                f"SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='{col_name}'",
                f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"
            )

        # ── Migrate data from user_profiles to users (if table still exists) ──
        print("\n=== Cleanup: user_profiles migration ===")
        try:
            table_check = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_profiles')"
            ))
            if table_check.fetchone()[0]:
                print("  Migrating data from user_profiles to users...")
                conn.execute(text("""
                    UPDATE users u 
                    SET 
                        phone = COALESCE(u.phone, p.phone), 
                        location = COALESCE(u.location, p.location), 
                        linkedin_url = COALESCE(u.linkedin_url, p.linkedin_url), 
                        github_url = COALESCE(u.github_url, p.github_url), 
                        summary = COALESCE(u.summary, p.summary)
                    FROM user_profiles p 
                    WHERE u.id = p.user_id;
                """))
                conn.execute(text("DROP TABLE IF EXISTS user_profiles CASCADE;"))
                conn.commit()
                print("  [OK] user_profiles migrated and dropped.")
            else:
                print("  [SKIP] user_profiles table does not exist.")
        except Exception as e:
            conn.rollback()
            print(f"  [WARN] user_profiles cleanup: {e}")

        print("\n=== Migration complete ===")


if __name__ == "__main__":
    migrate()

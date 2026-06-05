import os
from app.db.session import SessionLocal
import json
from app.models.user import User

def get_user_info(email: str) -> dict:
    """Return a dict with user details for the given email, or empty dict if not found."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "created_at": str(user.created_at),
                "updated_at": str(user.updated_at),
                "profile": {
                    "full_name": user.full_name,
                    "phone": user.phone,
                    "location": user.location,
                    "linkedin_url": user.linkedin_url,
                    "github_url": user.github_url,
                },
            }
        return {}
    finally:
        db.close()
def user_exists(email: str) -> bool:
    """Return True if a user with the given email exists in the DB."""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first() is not None
    finally:
        db.close()

if __name__ == "__main__":
    target_email = "ravigamdha9@gmail.com"
    info = get_user_info(target_email)
    if info:
        print(f"User info for {target_email}:")
        print(json.dumps(info, indent=2))
    else:
        print(f"No user found with email {target_email}")
    target_email = "ravigamdha9@gmail.com"
    exists = user_exists(target_email)
    print(f"User with email {target_email} exists: {exists}")

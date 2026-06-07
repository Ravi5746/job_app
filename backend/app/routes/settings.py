from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.routes.auth import get_current_user
from app.models.user import User as UserModel
from app.services.automation_service import automation_service
from app.core.config import settings
import asyncio

router = APIRouter()

@router.post("/connect/{platform}")
async def connect_platform(
    platform: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Opens a browser window for the user to manually log in to a platform.
    """
    platforms = {
        "linkedin": "https://www.linkedin.com/login",
        "indeed": "https://www.indeed.com/auth",
        "naukri": "https://www.naukri.com/nlogin/login",
        "glassdoor": "https://www.glassdoor.com/profile/login_input.htm"
    }

    url = platforms.get(platform.lower())
    if not url:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    # Launch the browser in a background task so the API responds immediately
    asyncio.create_task(automation_service.launch_login_browser(platform, current_user.id))
    
    return {
        "status": "success", 
        "message": f"Login window launched for {platform}. Please log in there."
    }

@router.post("/disconnect/{platform}")
async def disconnect_platform(
    platform: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Disconnects a platform by removing its marker file and browser session directory.
    """
    import os
    import shutil
    user_platform_dir = os.path.join(settings.USER_DATA_DIR, str(current_user.id), platform.lower())
    marker_path = os.path.join(user_platform_dir, f"connected_{platform.lower()}.txt")
    
    deleted = False
    if os.path.exists(marker_path):
        try:
            os.remove(marker_path)
        except Exception:
            pass
        deleted = True
    if os.path.exists(user_platform_dir):
        try:
            shutil.rmtree(user_platform_dir)
        except Exception:
            pass
        deleted = True
        
    if deleted:
        return {"status": "success", "message": f"Disconnected from {platform} and wiped its session data"}
    return {"status": "error", "message": f"{platform} is not connected"}

@router.post("/disconnect-all")
async def disconnect_all(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Disconnects all platforms and wipes the browser data.
    """
    import os
    import shutil
    user_dir = os.path.join(settings.USER_DATA_DIR, str(current_user.id))
    
    if os.path.exists(user_dir):
        try:
            shutil.rmtree(user_dir)
            os.makedirs(user_dir, exist_ok=True)
            return {"status": "success", "message": "All platforms disconnected and data wiped"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to disconnect: {str(e)}"}
    return {"status": "success", "message": "Already disconnected"}

@router.get("/status")
async def get_connection_status(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Checks if browser session data exists for various platforms.
    """
    import os
    
    status = {}
    platforms = ["linkedin", "indeed", "naukri", "glassdoor"]
    
    for p in platforms:
        user_platform_dir = os.path.join(settings.USER_DATA_DIR, str(current_user.id), p)
        marker_path = os.path.join(user_platform_dir, f"connected_{p}.txt")
        if os.path.exists(marker_path):
            try:
                with open(marker_path, "r") as f:
                    status[p] = f.read().strip()
            except Exception:
                status[p] = p.capitalize()
        else:
            status[p] = False
        
    return status

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
    asyncio.create_task(automation_service.launch_login_browser(platform))
    
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
    user_data_dir = settings.USER_DATA_DIR
    marker_path = os.path.join(user_data_dir, f"connected_{platform.lower()}.txt")
    platform_dir = os.path.join(user_data_dir, platform.lower())
    
    deleted = False
    if os.path.exists(marker_path):
        os.remove(marker_path)
        deleted = True
    if os.path.exists(platform_dir):
        try:
            shutil.rmtree(platform_dir)
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
    user_data_dir = settings.USER_DATA_DIR
    
    if os.path.exists(user_data_dir):
        # We delete the entire folder for a clean slate
        shutil.rmtree(user_data_dir)
        os.makedirs(user_data_dir)
        return {"status": "success", "message": "All platforms disconnected and data wiped"}
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
    user_data_dir = settings.USER_DATA_DIR
    
    status = {}
    platforms = ["linkedin", "indeed", "naukri", "glassdoor"]
    
    for p in platforms:
        marker_path = os.path.join(user_data_dir, f"connected_{p}.txt")
        if os.path.exists(marker_path):
            with open(marker_path, "r") as f:
                status[p] = f.read().strip()
        else:
            status[p] = False
        
    return status

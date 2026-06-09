import os
import sys
import asyncio
import logging
import uuid
import threading
import time
from app.core.logger import trace_id_ctx

# Setup logging

logger = logging.getLogger(__name__)

# Fix for Playwright on Windows inside background processes
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass

# In-memory task registry
_tasks = {}

class AsyncResult:
    def __init__(self, task_id):
        self.task_id = task_id
    
    @property
    def state(self):
        task = _tasks.get(self.task_id)
        return task["state"] if task else "PENDING"
    
    @property
    def info(self):
        task = _tasks.get(self.task_id)
        if not task:
            return None
        messages = task.get("messages", [])
        return {"message": messages[-1]["message"]} if messages else None

class MockSelf:
    def __init__(self, task_id):
        self.request = type("Request", (), {"id": task_id})()
    
    def update_state(self, state, meta=None):
        if self.request.id in _tasks:
            _tasks[self.request.id]["state"] = state
            if meta and "message" in meta:
                _tasks[self.request.id]["messages"].append({
                    "status": state,
                    "message": meta["message"]
                })

class CustomTask:
    def __init__(self, func):
        self.func = func
        
    def delay(self, *args, **kwargs):
        task_id = str(uuid.uuid4())
        _tasks[task_id] = {"state": "PENDING", "messages": []}
        
        async def run_task():
            mock_self = MockSelf(task_id)
            token = trace_id_ctx.set(task_id)
            try:
                await self.func(mock_self, *args, **kwargs)
            except Exception as e:
                logger.exception(f"Task {task_id} failed with exception: {e}")
                mock_self.update_state("FAILED", {"message": str(e)})
            finally:
                trace_id_ctx.reset(token)

        def run_in_thread():
            if sys.platform == 'win32':
                try:
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                except AttributeError:
                    pass
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_task())
            finally:
                loop.close()
                
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
            
        loop.run_in_executor(None, run_in_thread)
        
        class DelayResult:
            def __init__(self, id):
                self.id = id
        return DelayResult(task_id)

class MockCeleryApp:
    def task(self, bind=False, name=None):
        def decorator(func):
            return CustomTask(func)
        return decorator

celery_app = MockCeleryApp()

@celery_app.task(bind=True, name="app.tasks.apply_to_job")
async def apply_to_job_task(self, job_id: int, user_id: int):
    """
    Task to run the browser automation flow asynchronously in the main event loop.
    Updates progress through local memory `_tasks` array.
    """
    from app.db.session import SessionLocal
    from app.services.automation_service import automation_service

    task_id = self.request.id
    logger.info(f"Starting auto-apply task {task_id} for job_id={job_id}, user_id={user_id}")

    def send_progress(status: str, msg: str):
        celery_state = status
        if status == "FAILURE":
            celery_state = "FAILED"
        elif status == "SUCCESS":
            celery_state = "COMPLETED"
            
        self.update_state(state=celery_state, meta={"message": msg})
        logger.info(f"Task progress update: {status} - {msg}")

    # Callback wrapper to bridge async service updates
    async def progress_callback(status: str, msg: str):
        send_progress(status, msg)

    db = SessionLocal()
    try:
        result = await automation_service.apply_to_job(db, job_id, user_id, progress_callback=progress_callback)
        if result.get("status") == "error":
            send_progress("FAILURE", result.get("message", "Automation failed"))
        else:
            send_progress("SUCCESS", result.get("message", "Automation completed"))
        return result
    except Exception as exc:
        logger.exception(f"Unhandled error in background task: {exc}")
        send_progress("FAILURE", str(exc))
        return {"status": "error", "message": str(exc)}
    finally:
        db.close()

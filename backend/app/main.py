import asyncio
import sys

# Fix for NotImplementedError when using Playwright on Windows
# MUST BE SET BEFORE ANY OTHER IMPORTS
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import (
    auth,
    jobs,
    resume as resume_routes,
    applications,
    settings as settings_routes
)
from app.core.config import settings
from app.middleware.error_handler import error_handler_middleware

from app.db.session import engine, Base

# Import models
from app.models import user, job, resume, application


# Create DB tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="AI Job Automation Platform API",
    description="Production-grade AI Job Automation Backend",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Error Middleware
app.middleware("http")(error_handler_middleware)


# Routes
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

app.include_router(
    jobs.router,
    prefix="/api/v1/jobs",
    tags=["Jobs"]
)

app.include_router(
    resume_routes.router,
    prefix="/api/v1/resumes",
    tags=["Resumes"]
)

app.include_router(
    applications.router,
    prefix="/api/v1/applications",
    tags=["Applications"]
)

app.include_router(
    settings_routes.router,
    prefix="/api/v1/settings",
    tags=["Settings"]
)


@app.get("/")
async def root():
    return {
        "message": "AI Job Automation Platform API Running 🚀",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
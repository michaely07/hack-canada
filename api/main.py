"""
StatuteLens — FastAPI application entry point.

Minimal setup for testing voice integration.
Run with: uvicorn api.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.config import settings
from api.routers.voice import router as voice_router

app = FastAPI(
    title="StatuteLens API",
    description="AI-Powered Legal Research Platform for Canadian Federal Law",
    version="0.1.0",
)

# CORS — allow frontend dev server and test page
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(voice_router)


@app.get("/api/health")
async def health():
    """Basic health check."""
    return {
        "status": "ok",
        "elevenlabs_configured": bool(settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_AGENT_ID),
    }


# Serve the voice test page at root
@app.get("/")
async def serve_test_page():
    return FileResponse("test_voice.html")

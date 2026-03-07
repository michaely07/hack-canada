"""
StatuteLens — FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.config import settings
from api.db import init_pool, close_pool
from api.services.embedder import init_embedder

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_pool(settings.DATABASE_URL)
    init_embedder(settings.EMBEDDING_MODEL)
    yield
    # Shutdown
    await close_pool()

app = FastAPI(
    title="StatuteLens API",
    description="AI-Powered Legal Research Platform for Canadian Federal Law",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from fastapi.responses import JSONResponse
import asyncpg

@app.exception_handler(asyncpg.exceptions.PostgresError)
async def postgres_error_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": f"Database error: {str(exc)}"})

# Import routers
from api.routers import query, laws, sections, graph, voice, conversations
app.include_router(query.router, prefix="/api")
app.include_router(laws.router, prefix="/api")
app.include_router(sections.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(voice.router)
app.include_router(conversations.router, prefix="/api")

@app.get("/api/health")
async def health():
    from api.db import get_pool
    from api.services.embedder import get_embedder
    try:
        pool = get_pool()
        laws_count = await pool.fetchval("SELECT COUNT(*) FROM laws")
        sections_count = await pool.fetchval("SELECT COUNT(*) FROM sections")
        return {
            "status": "ok",
            "db": True,
            "embedding_model": get_embedder() is not None,
            "laws_count": laws_count,
            "sections_count": sections_count,
            "elevenlabs_configured": bool(settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_AGENT_ID),
        }
    except Exception:
        return {"status": "ok", "db": False}

# Serve the voice test page at root
@app.get("/")
async def serve_test_page():
    import os
    if os.path.exists("test_voice.html"):
        return FileResponse("test_voice.html")
    return {"message": "StatuteLens API"}

# Serve React static build in production
import os
if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

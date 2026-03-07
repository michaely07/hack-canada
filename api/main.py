"""
StatuteLens — FastAPI application entry point.
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from api.config import settings
from api.db import init_pool, close_pool, get_pool
from api.services.embedder import init_embedder
import asyncpg

logger = logging.getLogger("statutelens")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set — /api/query endpoints will fail")
    if settings.CORS_ORIGINS == ["http://localhost:5173"]:
        logger.warning("CORS_ORIGINS is default localhost — update for production")

    await init_pool(settings.DATABASE_URL)

    # Auto-run migrations (all DDL is IF NOT EXISTS, safe to re-run)
    pool = get_pool()
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_init.sql")
    if os.path.exists(migration_path):
        migration_sql = open(migration_path).read()
        # asyncpg execute() only supports single statements — split on semicolons
        async with pool.acquire() as conn:
            for statement in migration_sql.split(";"):
                stmt = statement.strip()
                if stmt and not stmt.startswith("--"):
                    await conn.execute(stmt)
        logger.info("Migrations applied successfully")

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

# Serve React static build in production
if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

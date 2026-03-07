# WORKFLOW-2-BACKEND.md — API, Gemini Integration & RAG Pipeline

> **Owner:** Person 2
> **Depends on:** Person 1 (needs populated database by Saturday morning)
> **Delivers to:** Person 3 (frontend consumes all API endpoints), Person 4 (voice calls /api/voice/llm)

## Your Job

You own the FastAPI backend: the API layer, the Gemini integration, the hybrid search, the RAG prompt assembly, and the citation validator. You are the bridge between the database and the frontend.

## Prerequisites

- Python 3.12+
- Person 1's database running (or your own local postgres via docker-compose)
- Gemini API key (get from https://aistudio.google.com/apikey)
- `pip install fastapi uvicorn asyncpg httpx google-generativeai sentence-transformers sse-starlette pydantic-settings python-dotenv`

## Timeline

### Friday Evening (3-4 hours)

#### Hour 1: FastAPI Scaffold

**`api/config.py`**:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://dev:dev@localhost:5432/statutelens"
    gemini_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    embedding_model: str = "all-MiniLM-L6-v2"
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "info"

    class Config:
        env_file = ".env"

settings = Settings()
```

**`api/db.py`**:
```python
import asyncpg

pool: asyncpg.Pool | None = None

async def init_pool(database_url: str):
    global pool
    pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)

async def close_pool():
    global pool
    if pool:
        await pool.close()

def get_pool() -> asyncpg.Pool:
    assert pool is not None, "Database pool not initialized"
    return pool
```

**`api/main.py`**:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.config import settings
from api.db import init_pool, close_pool
from api.services.embedder import init_embedder

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_pool(settings.database_url)
    init_embedder(settings.embedding_model)
    yield
    # Shutdown
    await close_pool()

app = FastAPI(title="StatuteLens", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from api.routers import query, laws, sections, graph, voice, conversations
app.include_router(query.router, prefix="/api")
app.include_router(laws.router, prefix="/api")
app.include_router(sections.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")

@app.get("/api/health")
async def health():
    from api.db import get_pool
    from api.services.embedder import get_embedder
    pool = get_pool()
    laws_count = await pool.fetchval("SELECT COUNT(*) FROM laws")
    sections_count = await pool.fetchval("SELECT COUNT(*) FROM sections")
    return {
        "status": "ok",
        "db": True,
        "embedding_model": get_embedder() is not None,
        "laws_count": laws_count,
        "sections_count": sections_count,
    }

# Serve React static build in production
# app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

**`api/services/embedder.py`**:
```python
from sentence_transformers import SentenceTransformer

_embedder: SentenceTransformer | None = None

def init_embedder(model_name: str):
    global _embedder
    _embedder = SentenceTransformer(model_name)

def get_embedder() -> SentenceTransformer:
    assert _embedder is not None
    return _embedder

def embed_query(text: str) -> list[float]:
    return get_embedder().encode(text).tolist()
```

Run it: `uvicorn api.main:app --reload --port 8000`
Hit `http://localhost:8000/api/health` — should return stats.

**Checkpoint:** API boots, connects to DB, embedding model loads.

#### Hours 2-3: Core Retrieval + RAG

**`api/services/retrieval.py`**:
```python
import asyncpg
from api.services.embedder import embed_query
from dataclasses import dataclass

@dataclass
class SectionResult:
    id: int
    content_text: str
    content_xml: str | None
    label: str
    marginal_note: str | None
    lims_id: str
    law_id: int
    chunk_type: str
    definitions: list
    cross_refs: list
    law_code: str
    law_title: str
    combined_score: float

HYBRID_SEARCH_SQL = """
WITH vector_results AS (
    SELECT s.id, s.content_text, s.content_xml, s.label, s.marginal_note,
           s.lims_id, s.law_id, s.chunk_type, s.definitions, s.cross_refs,
           l.code AS law_code, l.short_title_en AS law_title,
           1 - (s.embedding <=> $1::vector) AS vector_score
    FROM sections s
    JOIN laws l ON s.law_id = l.id
    WHERE s.language = $2
      AND ($3::varchar IS NULL OR l.code = $3)
    ORDER BY s.embedding <=> $1::vector
    LIMIT 20
),
fts_results AS (
    SELECT s.id, s.content_text, s.content_xml, s.label, s.marginal_note,
           s.lims_id, s.law_id, s.chunk_type, s.definitions, s.cross_refs,
           l.code AS law_code, l.short_title_en AS law_title,
           ts_rank_cd(s.content_tsv, plainto_tsquery('english', $4)) AS fts_score
    FROM sections s
    JOIN laws l ON s.law_id = l.id
    WHERE s.content_tsv @@ plainto_tsquery('english', $4)
      AND s.language = $2
      AND ($3::varchar IS NULL OR l.code = $3)
    ORDER BY fts_score DESC
    LIMIT 20
),
combined AS (
    SELECT COALESCE(v.id, f.id) AS id,
           COALESCE(v.content_text, f.content_text) AS content_text,
           COALESCE(v.content_xml, f.content_xml) AS content_xml,
           COALESCE(v.label, f.label) AS label,
           COALESCE(v.marginal_note, f.marginal_note) AS marginal_note,
           COALESCE(v.lims_id, f.lims_id) AS lims_id,
           COALESCE(v.law_id, f.law_id) AS law_id,
           COALESCE(v.chunk_type, f.chunk_type) AS chunk_type,
           COALESCE(v.definitions, f.definitions) AS definitions,
           COALESCE(v.cross_refs, f.cross_refs) AS cross_refs,
           COALESCE(v.law_code, f.law_code) AS law_code,
           COALESCE(v.law_title, f.law_title) AS law_title,
           COALESCE(v.vector_score, 0) * 0.7
           + COALESCE(f.fts_score, 0) * 0.3 AS combined_score
    FROM vector_results v
    FULL OUTER JOIN fts_results f ON v.id = f.id
)
SELECT * FROM combined ORDER BY combined_score DESC LIMIT $5;
"""

async def hybrid_search(
    query: str,
    pool: asyncpg.Pool,
    top_k: int = 5,
    language: str = "en",
    law_code: str | None = None,
) -> list[SectionResult]:
    query_embedding = embed_query(query)
    rows = await pool.fetch(
        HYBRID_SEARCH_SQL,
        query_embedding, language, law_code, query, top_k
    )
    return [SectionResult(**dict(row)) for row in rows]
```

**`api/services/rag.py`**:
```python
import google.generativeai as genai
import json
from api.config import settings
from api.services.retrieval import SectionResult

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel("gemini-2.0-flash")

SYSTEM_PROMPT = """You are a legal research assistant analyzing Canadian federal statutes and regulations.

STRICT RULES:
1. Answer ONLY using the statutory excerpts provided in the CONTEXT BLOCKS below.
2. Every factual claim must cite the specific section using [Section X] notation.
3. If the provided excerpts do not contain enough information to answer the question,
   respond with: {"answer": null, "reason": "INSUFFICIENT_CONTEXT", "citations": []}
4. Do NOT synthesize information beyond what the excerpts explicitly state.
5. Use precise legal language, then explain in plain English.

RESPONSE FORMAT (strict JSON, no markdown fences):
{
  "answer": "Your answer with [Section X(Y)] citations inline...",
  "citations": [
    {"lims_id": "12345", "label": "37(1)", "law_code": "I-5", "relevance": "high"}
  ],
  "confidence": "high"
}

CONFIDENCE LEVELS:
- "high": Answer is directly stated in the excerpts
- "medium": Answer requires reasonable inference from the excerpts
- "low": Answer is partially supported; some aspects not covered"""


def build_prompt(query: str, sections: list[SectionResult]) -> str:
    context_blocks = "\n---\n".join(
        f"[{s.law_title} | Section {s.label} | lims_id: {s.lims_id}]\n{s.content_text}"
        for s in sections
    )
    return f"""{SYSTEM_PROMPT}

CONTEXT BLOCKS:
{context_blocks}

USER QUESTION: {query}"""


async def generate_response(query: str, sections: list[SectionResult]) -> dict:
    """Non-streaming: get complete response from Gemini."""
    prompt = build_prompt(query, sections)
    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown fences if Gemini wraps in ```json
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"answer": raw, "citations": [], "confidence": "low"}

    # Citation validation
    retrieved_lims_ids = {s.lims_id for s in sections}
    validated_citations = []
    for c in parsed.get("citations", []):
        c["hallucinated"] = c.get("lims_id") not in retrieved_lims_ids
        validated_citations.append(c)
    parsed["citations"] = validated_citations

    # Downgrade confidence if any hallucinated citations
    if any(c["hallucinated"] for c in validated_citations):
        parsed["confidence"] = "low"

    return parsed


async def generate_response_stream(query: str, sections: list[SectionResult]):
    """Streaming: yield tokens as they come from Gemini."""
    prompt = build_prompt(query, sections)
    response = model.generate_content(prompt, stream=True)
    full_text = ""
    for chunk in response:
        if chunk.text:
            full_text += chunk.text
            yield {"type": "token", "data": chunk.text}

    # Parse complete response for citations
    raw = full_text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(raw)
        retrieved_lims_ids = {s.lims_id for s in sections}
        for c in parsed.get("citations", []):
            c["hallucinated"] = c.get("lims_id") not in retrieved_lims_ids
        yield {"type": "citations", "data": parsed.get("citations", [])}
        yield {"type": "confidence", "data": parsed.get("confidence", "low")}
    except json.JSONDecodeError:
        yield {"type": "citations", "data": []}
        yield {"type": "confidence", "data": "low"}

    yield {"type": "done", "data": None}
```

#### Hour 4: Query Router

**`api/routers/query.py`**:
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from api.db import get_pool
from api.services.retrieval import hybrid_search
from api.services.rag import generate_response, generate_response_stream
import json

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    language: str = "en"
    law_code: str | None = None
    conversation_id: str | None = None

@router.post("/query")
async def query(req: QueryRequest):
    pool = get_pool()
    sections = await hybrid_search(req.query, pool, top_k=5, language=req.language, law_code=req.law_code)

    if not sections:
        return {"answer": None, "reason": "NO_RESULTS", "citations": [], "confidence": "low"}

    result = await generate_response(req.query, sections)
    result["retrieved_sections"] = [
        {"lims_id": s.lims_id, "label": s.label, "law_code": s.law_code, "score": s.combined_score}
        for s in sections
    ]
    return result

@router.post("/query/stream")
async def query_stream(req: QueryRequest):
    pool = get_pool()
    sections = await hybrid_search(req.query, pool, top_k=5, language=req.language, law_code=req.law_code)

    if not sections:
        async def empty():
            yield {"event": "message", "data": json.dumps({"type": "done", "data": {"answer": None}})}
        return EventSourceResponse(empty())

    async def event_generator():
        async for event in generate_response_stream(req.query, sections):
            yield {"event": "message", "data": json.dumps(event)}

    return EventSourceResponse(event_generator())
```

**Checkpoint:** `POST /api/query` with a real question returns a Gemini-generated answer with citations. Test with curl:
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the definition of reserve under the Indian Act?"}'
```

### Saturday (6-8 hours)

#### Build remaining routers

**`api/routers/laws.py`**:
```python
from fastapi import APIRouter
from api.db import get_pool

router = APIRouter()

@router.get("/laws")
async def list_laws():
    pool = get_pool()
    rows = await pool.fetch("""
        SELECT l.code, l.short_title_en, l.type, l.last_amended,
               COUNT(s.id) as section_count
        FROM laws l LEFT JOIN sections s ON s.law_id = l.id
        GROUP BY l.id ORDER BY l.code
    """)
    return [dict(row) for row in rows]

@router.get("/laws/{code}")
async def get_law(code: str):
    pool = get_pool()
    law = await pool.fetchrow("SELECT * FROM laws WHERE code = $1", code)
    if not law:
        from fastapi import HTTPException
        raise HTTPException(404, f"Law {code} not found")
    sections = await pool.fetch("""
        SELECT lims_id, label, marginal_note, chunk_type
        FROM sections WHERE law_id = $1 AND language = 'en'
        ORDER BY id
    """, law["id"])
    return {**dict(law), "sections": [dict(s) for s in sections]}
```

**`api/routers/sections.py`**:
```python
from fastapi import APIRouter, HTTPException
from api.db import get_pool

router = APIRouter()

@router.get("/sections/{lims_id}")
async def get_section(lims_id: str):
    pool = get_pool()
    row = await pool.fetchrow("""
        SELECT s.*, l.code AS law_code, l.short_title_en AS law_title
        FROM sections s JOIN laws l ON s.law_id = l.id
        WHERE s.lims_id = $1
    """, lims_id)
    if not row:
        raise HTTPException(404, f"Section {lims_id} not found")
    return dict(row)
```

**`api/routers/graph.py`**:
```python
from fastapi import APIRouter
from api.db import get_pool

router = APIRouter()

@router.get("/graph/{code}")
async def get_graph(code: str):
    pool = get_pool()
    # Get all cross-references from sections of this law
    rows = await pool.fetch("""
        SELECT DISTINCT
            l.code AS source_code, l.short_title_en AS source_title,
            cr->>'link' AS target_code, cr->>'text' AS ref_text
        FROM sections s
        JOIN laws l ON s.law_id = l.id,
        jsonb_array_elements(s.cross_refs) AS cr
        WHERE l.code = $1 AND cr->>'link' IS NOT NULL
    """, code)

    # Build nodes and edges
    nodes = {code: await pool.fetchval("SELECT short_title_en FROM laws WHERE code = $1", code)}
    edges = []
    for row in rows:
        target = row["target_code"]
        if target not in nodes:
            title = await pool.fetchval("SELECT short_title_en FROM laws WHERE code = $1", target)
            nodes[target] = title or target
        edges.append({"source": code, "target": target, "text": row["ref_text"]})

    return {
        "nodes": [{"code": k, "title": v} for k, v in nodes.items()],
        "edges": edges,
    }
```

**`api/routers/voice.py`**:
```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.config import settings
from api.db import get_pool
from api.services.retrieval import hybrid_search
from api.services.rag import build_prompt
import httpx
import json
import google.generativeai as genai

router = APIRouter()

genai.configure(api_key=settings.gemini_api_key)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")

@router.post("/voice/token")
async def get_voice_token():
    """Generate signed URL for ElevenLabs WebSocket (keeps API key server-side)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url",
            params={"agent_id": settings.elevenlabs_agent_id},
            headers={"xi-api-key": settings.elevenlabs_api_key},
        )
        resp.raise_for_status()
        return resp.json()

@router.post("/voice/llm")
async def voice_llm(request: Request):
    """Called BY ElevenLabs agent as 'custom LLM'. Receives transcript, returns streamed text."""
    body = await request.json()
    user_message = body.get("messages", [{}])[-1].get("content", "")

    pool = get_pool()
    sections = await hybrid_search(user_message, pool, top_k=5)

    prompt = build_prompt(user_message, sections)

    # ElevenLabs expects OpenAI-compatible SSE format
    async def generate():
        response = gemini_model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                # OpenAI SSE format for compatibility with ElevenLabs
                data = {"choices": [{"delta": {"content": chunk.text}}]}
                yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

**`api/routers/conversations.py`** — minimal stub:
```python
from fastapi import APIRouter
from api.db import get_pool

router = APIRouter()

@router.post("/conversations")
async def create_conversation():
    pool = get_pool()
    row = await pool.fetchrow("INSERT INTO conversations DEFAULT VALUES RETURNING id, created_at")
    return dict(row)
```

### Sunday: Polish & Integration

- Fix any issues Person 3 or 4 finds with API responses
- Tune the hybrid search weights if retrieval quality is poor
- Add error handling (try/except around Gemini calls, return 503 on failure)
- Help Person 4 debug the voice/llm endpoint format

## Files You Own

```
api/
  main.py
  config.py
  db.py
  routers/
    query.py
    laws.py
    sections.py
    graph.py
    voice.py
    conversations.py
  services/
    retrieval.py
    rag.py
    embedder.py
    voice.py
.env.example
requirements.txt
```

## Definition of Done

- [ ] `GET /api/health` returns law/section counts
- [ ] `POST /api/query` returns structured JSON with answer + citations
- [ ] `POST /api/query/stream` streams SSE events
- [ ] Citations are validated against retrieved sections (hallucinated flag)
- [ ] `GET /api/laws` returns list with section counts
- [ ] `GET /api/sections/{lims_id}` returns content_text + content_xml
- [ ] `GET /api/graph/{code}` returns nodes + edges from cross_refs
- [ ] `POST /api/voice/token` returns signed URL
- [ ] `POST /api/voice/llm` streams OpenAI-compatible SSE
- [ ] Gemini handles "I don't know" gracefully (INSUFFICIENT_CONTEXT)

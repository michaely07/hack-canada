# CHANGELOG

## Status: Full-stack integrated and running in Docker

### [2026-03-07] Frontend + Voice + Docker integration

- Merged `front-end` branch into `client/` subdirectory (React + Vite + Tailwind)
- Merged `elevenlabs` branch voice components (VoiceButton, VoiceSession, AudioVisualizer, voiceStore)
- Fixed Vite proxy from port 8000 to 8001
- Removed DummyTest component, cleaned up App.jsx
- Added SSE streaming support in chatStore (reads `/api/query/stream` events)
- Added law filter dropdown in QueryInput (fetches from `GET /api/laws`)
- Added auto-scroll on new messages and streaming content
- Added `api/services/voice.py` for ElevenLabs signed URL generation
- Added multi-stage Dockerfile (Node frontend build + Python backend)
- Added `api` service to `docker-compose.yml` with healthcheck on db
- Added `.dockerignore` for clean builds
- Added `.venv/` to `.gitignore`
- Enabled conditional static file serving in `api/main.py` (serves React build if `static/` exists)
- Verified: `docker compose up` runs both db + api, `/api/health` returns ok (6 laws, 2,767 sections)
- Verified: Frontend builds and is served at `/` by FastAPI in production mode

### [2026-03-07] Backend merge

- Merged `backend` branch into `database` — FastAPI API + RAG pipeline combined with ETL + schema
- Resolved port conflict: unified on port 5433, updated `config.py`, `docker-compose.yml`, `.env.example`
- Removed duplicate `init.sql` (using `migrations/001_init.sql` with `IF NOT EXISTS`)
- Removed committed `__pycache__/` files, added to `.gitignore`
- Fixed `LawSummarySchema.last_amended` type: `str` -> `date` (was causing /api/laws 500)
- Verified endpoints: `/api/health`, `/api/laws` (6 laws), `/api/sections/{lims_id}` all returning correct data

### [2026-03-07] Person 1 — Database & ETL setup

- Added `docker-compose.yml` — pgvector/pgvector:pg16 on port 5433
- Added `migrations/001_init.sql` — full schema: `laws`, `sections` (hnsw + FTS indexes), `conversations`, `messages`
- Added ETL pipeline: `__main__.py`, `ingest.py`, `xml_parser.py`, `text_extractor.py`, `embedder.py`
- Added `requirements.txt`, `.env.example`, `.gitignore`
- ETL `--start` complete: 6 laws, 2,767 sections, 100% embeddings + XML
- Hybrid search verified: vector (cosine) + FTS both return relevant Criminal Code sections

### Connection string for team
```
postgresql://dev:dev@localhost:5433/statutelens
```

### Working endpoints
- `GET /api/health` — DB + embedding model status
- `GET /api/laws` — all 6 laws with section counts
- `GET /api/laws/{code}` — single law with section list
- `GET /api/sections/{lims_id}` — full section with XML
- `POST /api/query` — RAG query
- `POST /api/query/stream` — SSE streaming RAG query
- `GET /api/graph/{code}` — cross-reference graph
- `POST /api/voice/token` — ElevenLabs signed URL
- `POST /api/voice/llm` — ElevenLabs custom LLM endpoint
- `POST /api/conversations` — create conversation

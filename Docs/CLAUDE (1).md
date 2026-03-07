# CLAUDE.md — StatuteLens

> AI-Powered Legal Research Platform for Canadian Federal Law
> Built on the Justice Canada `laws-lois-xml` GitHub repository

## Project Overview

StatuteLens is a split-screen legal research tool that answers questions about Canadian federal law using Retrieval-Augmented Generation (RAG). Every AI response is grounded in actual statutory text, with clickable citations that display the source material in a side-by-side auditor pane.

**Core differentiator:** Structural citation validation. The system doesn't just ask the LLM to cite sources — it cross-checks every cited section ID against the sections that were actually retrieved from the database. If the LLM cites something that wasn't in its context window, it's flagged as a hallucination.

**Voice feature:** Users can speak to the system and hear responses in an authoritative lawyer-style voice via ElevenLabs Conversational AI (bidirectional WebSocket).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Chat Pane   │  │ Auditor Pane │  │  Voice Session    │  │
│  │  (messages,  │  │ (section     │  │  (ElevenLabs WS)  │  │
│  │   citations) │  │  viewer, XML)│  │                   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘  │
│         │                 │                    │             │
│    Zustand stores    GET /sections/{id}   WS via signed URL │
└─────────┼─────────────────┼────────────────────┼────────────┘
          │                 │                    │
    POST /api/query    GET /api/...        POST /api/voice/token
          │                 │                    │
┌─────────▼─────────────────▼────────────────────▼────────────┐
│                    FastAPI Backend                           │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Retrieval   │  │  RAG Service │  │  Voice Service      │ │
│  │  (hybrid     │  │  (prompt +   │  │  (ElevenLabs token  │ │
│  │   search)    │  │   Gemini +   │  │   generation)       │ │
│  │              │  │   citation   │  │                     │ │
│  │              │  │   validator) │  │                     │ │
│  └──────┬───────┘  └──────┬───────┘  └─────────────────────┘ │
│         │                 │                                  │
│    SQL queries      Gemini API                               │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────────┐ │
│  │           PostgreSQL 16 + pgvector                      │ │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────────────────┐ │ │
│  │  │  laws     │  │ sections  │  │ conversations +      │ │ │
│  │  │  table    │  │ table     │  │ messages tables      │ │ │
│  │  │          │  │ (vectors, │  │                      │ │ │
│  │  │          │  │  FTS, XML)│  │                      │ │ │
│  │  └──────────┘  └───────────┘  └──────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

ETL Pipeline (run locally, one-time):
  laws-lois-xml repo → lxml parser → sentence-transformers → PostgreSQL
```

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Database | PostgreSQL + pgvector | 16 + pgvector 0.7+ |
| Backend | FastAPI + asyncpg | FastAPI 0.115+, asyncpg 0.30+ |
| LLM | Google Gemini API | gemini-2.0-flash |
| Embeddings | sentence-transformers | all-MiniLM-L6-v2 (384-dim) |
| Frontend | React + Vite + Tailwind CSS | React 19, Vite 6 |
| State | Zustand | v5 |
| Voice | ElevenLabs Conversational AI | WebSocket API |
| Deployment | Railway | PostgreSQL + FastAPI monorepo |

## Database Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Laws: one row per XML file (act or regulation)
CREATE TABLE laws (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(30) UNIQUE NOT NULL,    -- 'A-1', 'C-46', 'SOR-97-175'
    type            VARCHAR(20) NOT NULL,           -- 'act' or 'regulation'
    short_title_en  TEXT NOT NULL,
    short_title_fr  TEXT,
    long_title_en   TEXT,
    in_force        BOOLEAN DEFAULT TRUE,
    pit_date        DATE,
    last_amended    DATE,
    enabling_act_code VARCHAR(30),                  -- regulations: which act enables them
    xml_path        TEXT,
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Sections: one row per <Section> node, the core searchable unit
CREATE TABLE sections (
    id              SERIAL PRIMARY KEY,
    law_id          INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    lims_id         VARCHAR(50),                    -- unique within repo
    label           VARCHAR(50),                    -- '37', '2(1)', 'A.01.010'
    marginal_note   TEXT,                           -- human-readable section summary
    heading         TEXT,                           -- nearest parent Heading
    part_label      TEXT,
    part_title      TEXT,
    content_text    TEXT NOT NULL,                  -- flattened readable text
    content_xml     TEXT,                           -- raw XML for auditor pane
    chunk_type      VARCHAR(20) DEFAULT 'section',  -- section, definition, schedule
    definitions     JSONB DEFAULT '[]',
    cross_refs      JSONB DEFAULT '[]',
    embedding       vector(384),
    language        VARCHAR(3) DEFAULT 'en',
    token_count     INTEGER,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(lims_id, language)
);

-- Indexes
CREATE INDEX idx_sections_embedding ON sections
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200);
ALTER TABLE sections ADD COLUMN content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED;
CREATE INDEX idx_sections_fts ON sections USING gin(content_tsv);
CREATE INDEX idx_sections_law_id ON sections(law_id);
CREATE INDEX idx_sections_lims_id ON sections(lims_id);
CREATE INDEX idx_sections_language ON sections(language);

-- Conversations
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
    id              SERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL,           -- 'user' or 'assistant'
    content         TEXT NOT NULL,
    citations       JSONB DEFAULT '[]',
    confidence      VARCHAR(10),
    retrieved_ids   INTEGER[],
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

## API Endpoints

### Query
```
POST /api/query
  Body: { "query": string, "language": "en"|"fr", "law_code": string|null, "conversation_id": uuid|null }
  Response: { "answer": string, "citations": [...], "confidence": "high"|"medium"|"low", "conversation_id": uuid }

POST /api/query/stream
  Body: same as above
  Response: SSE stream, each event is JSON: { "type": "token"|"citations"|"done", "data": ... }
```

### Laws & Sections
```
GET /api/laws
  Response: [{ "code": "A-1", "short_title_en": "...", "type": "act", "section_count": 42 }, ...]

GET /api/laws/{code}
  Response: { "code": "A-1", "short_title_en": "...", "sections": [{ "label": "1", "marginal_note": "..." }] }

GET /api/sections/{lims_id}
  Response: { "lims_id": "...", "label": "...", "content_text": "...", "content_xml": "...", "law_code": "...", "law_title": "..." }
```

### Graph
```
GET /api/graph/{code}
  Response: { "nodes": [{ "code": "A-1", "title": "..." }], "edges": [{ "source": "A-1", "target": "C-46", "refs": [...] }] }
```

### Voice
```
POST /api/voice/token
  Response: { "signed_url": "wss://api.elevenlabs.io/..." }

POST /api/voice/llm
  (Called BY ElevenLabs agent, not by frontend)
  Body: { "messages": [{ "role": "user", "content": "transcribed speech" }] }
  Response: SSE stream of text for TTS
```

### Health
```
GET /api/health
  Response: { "status": "ok", "db": true, "embedding_model": true, "laws_count": 5, "sections_count": 1234 }
```

## Gemini API Integration

Model: `gemini-2.0-flash` (fast, cheap, good at structured output)

```python
import google.generativeai as genai

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# For streaming:
response = model.generate_content(prompt, stream=True)
for chunk in response:
    yield chunk.text
```

### System Prompt (RAG grounding contract)

```
You are a legal research assistant analyzing Canadian federal statutes and regulations.

STRICT RULES:
1. Answer ONLY using the statutory excerpts provided in the CONTEXT BLOCKS below.
2. Every factual claim must cite the specific section using [Section X] notation.
3. If the provided excerpts do not contain enough information to answer the question,
   respond with: {"answer": null, "reason": "INSUFFICIENT_CONTEXT", "citations": []}
4. Do NOT synthesize information beyond what the excerpts explicitly state.
5. Use precise legal language, then explain in plain English.

RESPONSE FORMAT (strict JSON):
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
- "low": Answer is partially supported; some aspects not covered
```

## Hybrid Search Query

```sql
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
```

## ElevenLabs Voice Architecture

**Flow:**
```
User speaks → mic capture → ElevenLabs WebSocket (STT)
  → transcript sent to our /api/voice/llm endpoint
  → FastAPI runs RAG pipeline → streams response text back
  → ElevenLabs converts to speech (TTS) → user hears answer
```

**Agent setup (in ElevenLabs dashboard):**
- Agent type: Custom LLM
- Server URL: https://your-railway-url.com/api/voice/llm
- Voice: Design via Voice Design ("confident male, 35-45, measured pace, professional")
- Language: English
- Enable interruption handling

**Frontend WebSocket connection:**
- Get signed URL from `POST /api/voice/token` (keeps API key server-side)
- Connect via `new WebSocket(signedUrl)`
- Send `user_audio_chunk` events (16kHz PCM, base64 encoded)
- Receive `agent_response` (text), `audio` (base64 audio chunks), `user_transcript`

## Project Structure

```
statutelens/
├── api/
│   ├── main.py                  # FastAPI app, CORS, static mount, lifespan
│   ├── config.py                # pydantic-settings
│   ├── db.py                    # asyncpg pool
│   ├── routers/
│   │   ├── query.py             # POST /api/query, /api/query/stream
│   │   ├── laws.py              # GET /api/laws, /api/laws/{code}
│   │   ├── sections.py          # GET /api/sections/{lims_id}
│   │   ├── graph.py             # GET /api/graph/{code}
│   │   ├── voice.py             # POST /api/voice/token, /api/voice/llm
│   │   └── conversations.py     # Conversation CRUD
│   └── services/
│       ├── retrieval.py         # hybrid_search() function
│       ├── rag.py               # prompt assembly + Gemini + citation validation
│       ├── embedder.py          # sentence-transformers singleton
│       └── voice.py             # ElevenLabs signed URL generation
├── etl/
│   ├── __main__.py              # CLI: python -m etl.ingest --start
│   ├── ingest.py                # Orchestrator
│   ├── xml_parser.py            # lxml: XML → structured dicts
│   ├── text_extractor.py        # Section → flat text with labels
│   └── embedder.py              # Batch embedding with progress bar
├── client/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/          # AppShell.jsx, Sidebar.jsx, StatusBar.jsx
│   │   │   ├── chat/            # ChatPane.jsx, MessageBubble.jsx, CitationBadge.jsx, QueryInput.jsx
│   │   │   ├── auditor/         # AuditorPane.jsx, SectionViewer.jsx, LegalGraph.jsx
│   │   │   └── voice/           # VoiceButton.jsx, VoiceSession.jsx, AudioVisualizer.jsx
│   │   ├── hooks/
│   │   │   ├── useRAGQuery.js   # POST /api/query/stream + SSE parsing
│   │   │   ├── useVoiceSession.js # ElevenLabs WebSocket lifecycle
│   │   │   └── useCitationFocus.js # Badge click → auditor scroll
│   │   ├── stores/
│   │   │   ├── chatStore.js     # Messages, active conversation
│   │   │   ├── auditorStore.js  # Active section, highlights
│   │   │   └── voiceStore.js    # Voice session state
│   │   ├── api/
│   │   │   └── client.js        # Fetch wrapper
│   │   └── App.jsx
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── migrations/
│   └── 001_init.sql             # Full schema (all tables + indexes)
├── tests/
│   ├── test_xml_parser.py
│   ├── test_retrieval.py
│   ├── test_citation_validation.py
│   └── golden_queries.json
├── docker-compose.yml           # Local dev: postgres + pgvector
├── Dockerfile                   # Production: FastAPI + static build
├── requirements.txt
├── .env.example
└── README.md
```

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://dev:dev@localhost:5432/statutelens

# LLM
GEMINI_API_KEY=AIza...

# Voice
ELEVENLABS_API_KEY=...
ELEVENLABS_AGENT_ID=...

# Embeddings (local, no key needed)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# App
CORS_ORIGINS=["http://localhost:5173"]
LOG_LEVEL=info
```

## Key Dependencies

### Python (requirements.txt)
```
fastapi==0.115.*
uvicorn[standard]==0.34.*
asyncpg==0.30.*
httpx==0.28.*
sentence-transformers==3.3.*
lxml==5.3.*
pydantic-settings==2.7.*
sse-starlette==2.2.*
google-generativeai==0.8.*
python-dotenv==1.0.*
tqdm==4.67.*
```

### Frontend (package.json)
```
react, react-dom (^19)
zustand (^5)
@reactflow/core (^12)
framer-motion (^11)
tailwindcss (^4)
vite (^6)
```

## Conventions

- **No ORM.** All database access is raw SQL via asyncpg.
- **No LangChain.** Direct Gemini API calls, direct pgvector queries.
- **Async everywhere.** All API handlers are async. Use asyncpg (not psycopg2).
- **Pydantic for all request/response models.** Define in `api/models/schemas.py` if needed.
- **Error handling:** Return proper HTTP status codes. 422 for bad input, 500 for LLM failures, 503 for DB connection issues.
- **Streaming:** Use `sse-starlette` for SSE responses. Each SSE event is `data: {json}\n\n`.
- **Local ingestion only.** ETL runs on developer's machine against local or remote DB. Not deployed as a service.

## 48-Hour Hackathon Timeline

See individual workflow files for detailed task breakdowns per person:
- `WORKFLOW-1-DATABASE.md` — Database, ETL, ingestion (Person 1)
- `WORKFLOW-2-BACKEND.md` — API, Gemini integration, RAG pipeline (Person 2)
- `WORKFLOW-3-FRONTEND.md` — React UI, split-screen, citations (Person 3)
- `WORKFLOW-4-VOICE.md` — ElevenLabs voice integration (Person 4)

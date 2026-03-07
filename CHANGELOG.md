# CHANGELOG

## Status: DB & ETL layer DONE — 6 laws, 2,767 sections, 100% embeddings

### [2026-03-07] Person 1 — Database & ETL setup

- Added `docker-compose.yml` — pgvector/pgvector:pg16 on port 5433 (5432 in use by another project)
- Added `migrations/001_init.sql` — full schema: `laws`, `sections` (hnsw + FTS indexes), `conversations`, `messages`; pgvector extension enabled
- Added `etl/__main__.py` — CLI entry point (`--small`, `--start`, `--full`, `--reset`, `--lang`)
- Added `etl/ingest.py` — async orchestrator using asyncpg; upserts laws + sections, batch embeds
- Added `etl/xml_parser.py` — lxml parser for Justice Canada XML; extracts metadata, sections, definitions, cross-refs
- Added `etl/text_extractor.py` — flattens `<Section>` trees into readable text (subsections, paragraphs, clauses)
- Added `etl/embedder.py` — `BatchEmbedder` wrapping `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- Added `requirements.txt` — pinned Python dependencies
- Added `.env.example` — environment variable template
- Added `.gitignore` — excludes `laws-lois-xml/`, `.env`, build artifacts (no .venv needed — no venv in spec)
- Database migrated: 4 tables created, pgvector 0.8.2 confirmed

- Cloned `justicecanada/laws-lois-xml` (15,505 files)
- ETL `--small` verified: 2 laws, 216 sections, 100% embeddings + XML
- ETL `--start` complete: 6 laws, 2,767 sections (Criminal Code 1605, Labour Code 504, IRPA 311, Access to Info 172, Indian Act 131, Child Support Regs 44)
- All 2,767 sections have non-null 384-dim embeddings and `content_xml`

### Connection string for team
```
postgresql://dev:dev@localhost:5433/statutelens
```

### Next steps
- [ ] Person 2: build FastAPI backend + hybrid search against this DB
- [ ] Run `--full` if more coverage needed for demo

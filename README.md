# SpecterBot

> Ask questions about Canadian federal law in plain English. Get answers grounded in real statutory text — with the receipts to prove it.

---

## How It Works

```
You ask a question
        ↓
  Hybrid search (vector + full-text) finds most relevant federal law sections based on real up-to-date data
        ↓
  Backend reads those sections and writes a cited answer
        ↓
  Click any citation badge to see the exact statutory source
        ↓
  Review plain english summaries of legal documents and statues in the "Analysis" tab
        ↓
  Inspect connections between citations using the "Legal Graph" tab

```

---

## The Stack

| Layer | What it does |
|-------|-------------|
| **ETL** | Parses the Justice Canada XML repo, stores in PostgreSQL + pgvector |
| **Backend** | FastAPI + RAG pipeline. Retrieves top sections, sends to API, validates citations against retrieved context |
| **Frontend** | React split-screen: 60% chat with citation badges, 40% source auditor showing exact statutory text + raw XML |
| **Voice** | ElevenLabs Conversational AI agent with a custom-designed voice, backed by the same RAG pipeline |

---

## The Anti-Hallucination Check

Every citation is validated against the sections actually retrieved from our database. If the API references a section that wasn't in the context window, it gets flagged and removes that context before it ever hits users screens. The law is right there and we're checking.

---

## Team

| Person | Owns |
|--------|------|
| Person 1 | Database, ETL, XML parser |
| Person 2 | FastAPI, RAG pipeline, Gemini |
| Person 3 | React frontend, citation UI |
| Person 4 | ElevenLabs voice integration |

---

*Not legal advice.*

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from api.db import get_pool
from api.services.retrieval import hybrid_search
from api.services.rag import generate_response, generate_response_stream
from api.services.conversation import get_or_create_conversation, get_conversation_history, save_message
from api.routers.voice import PERSONA_PROMPTS
from api.models.schemas import QueryRequest, QueryResponse, AnalyzeRequest
from groq import AsyncGroq
from api.config import settings
import json
import uuid

router = APIRouter()


async def _get_or_create_conversation(pool, conversation_id: str | None) -> uuid.UUID:
    if conversation_id:
        return uuid.UUID(conversation_id)
    row = await pool.fetchrow("INSERT INTO conversations DEFAULT VALUES RETURNING id")
    return row["id"]


async def _fetch_history(pool, conv_id: uuid.UUID) -> list[dict]:
    rows = await pool.fetch(
        "SELECT role, content FROM messages WHERE conversation_id = $1 ORDER BY created_at DESC LIMIT 10",
        conv_id,
    )
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


async def _save_message(pool, conv_id: uuid.UUID, role: str, content: str,
                        citations: list | None = None, confidence: str | None = None):
    await pool.execute(
        "INSERT INTO messages (conversation_id, role, content, citations, confidence) VALUES ($1, $2, $3, $4, $5)",
        conv_id, role, content,
        json.dumps(citations) if citations else None,
        confidence,
    )


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    pool = get_pool()
    conv_id = await _get_or_create_conversation(pool, req.conversation_id)
    history = await _fetch_history(pool, conv_id)

    await _save_message(pool, conv_id, "user", req.query)

    sections = await hybrid_search(req.query, pool, top_k=5, language=req.language, law_code=req.law_code)

    if not sections:
        return {"answer": None, "reason": "NO_RESULTS", "citations": [], "confidence": "low",
                "conversation_id": str(conv_id)}

    try:
        result = await generate_response(req.query, sections, history)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Groq API error: {str(e)}")

    # Save messages to conversation
    await save_message(pool, conv_id, "user", req.query)
    await save_message(pool, conv_id, "assistant", result.get("answer", ""), result.get("citations"), result.get("confidence"))

    await _save_message(pool, conv_id, "assistant", result.get("answer", ""),
                        result.get("citations", []), result.get("confidence", "low"))

    result["conversation_id"] = str(conv_id)
    result["retrieved_sections"] = [
        {"lims_id": s.lims_id, "label": s.label, "law_code": s.law_code, "score": s.combined_score}
        for s in sections
    ]
    return result


@router.post("/query/stream")
async def query_stream(req: QueryRequest):
    pool = get_pool()
    conv_id = await _get_or_create_conversation(pool, req.conversation_id)
    history = await _fetch_history(pool, conv_id)

    await _save_message(pool, conv_id, "user", req.query)

    sections = await hybrid_search(req.query, pool, top_k=5, language=req.language, law_code=req.law_code)

    if not sections:
        await save_message(pool, conv_id, "user", req.query)
        async def empty():
            yield {"event": "message", "data": json.dumps({"type": "conversation_id", "data": str(conv_id)})}
            yield {"event": "message", "data": json.dumps({
                "type": "done",
                "data": {"answer": None, "reason": "NO_RESULTS", "citations": [], "confidence": "low", "conversation_id": conv_id}
            })}
        return EventSourceResponse(empty())

    persona_prompt = PERSONA_PROMPTS.get(req.persona) if req.persona else None

    # Save user message before streaming
    await save_message(pool, conv_id, "user", req.query)

    async def event_generator():
        yield {"event": "message", "data": json.dumps({"type": "conversation_id", "data": str(conv_id)})}

        full_text = ""
        final_citations = []
        final_confidence = "low"

        try:
            async for event in generate_response_stream(req.query, sections, history):
                yield {"event": "message", "data": json.dumps(event)}
                if event["type"] == "token":
                    full_text += event["data"]
                elif event["type"] == "citations":
                    final_citations = event["data"]
                elif event["type"] == "confidence":
                    final_confidence = event["data"]
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"detail": f"Gemini API error: {str(e)}"})}
            return

        # Extract answer text from accumulated JSON
        answer_text = full_text
        try:
            raw = full_text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
            answer_text = parsed.get("answer", full_text)
        except (json.JSONDecodeError, IndexError):
            pass

        await _save_message(pool, conv_id, "assistant", answer_text,
                            final_citations, final_confidence)

    return EventSourceResponse(event_generator())

@router.post("/query/analyze")
async def analyze_section(req: AnalyzeRequest):
    pool = get_pool()
    section_text = await pool.fetchval("SELECT content_text FROM sections WHERE lims_id = $1", req.lims_id)
    
    if not section_text:
        raise HTTPException(status_code=404, detail="Section not found.")
        
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    
    prompt = f"""You are a helpful legal assistant for the general public.
Summarize the following legal statute into a 5th-grade reading level. 
Use plain English, no jargon. Provide a 1-sentence overarching summary, followed by 3 simple bullet points.

STATUTE TEXT:
{section_text}
"""
    try:
        completion = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        summary = completion.choices[0].message.content
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Groq API error: {str(e)}")

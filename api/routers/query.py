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

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    pool = get_pool()

    # Get or create conversation for memory
    conv_id = await get_or_create_conversation(pool, req.conversation_id)
    history = await get_conversation_history(pool, conv_id)

    # Reformulate query using conversation history for context
    from api.services.rag import reformulate_query
    search_query = await reformulate_query(req.query, history)

    sections = await hybrid_search(search_query, pool, top_k=5, language=req.language, law_code=req.law_code)

    if not sections:
        # Save the user message even if no results
        await save_message(pool, conv_id, "user", req.query)
        no_result_msg = "I couldn't find anything on that in the statutes I have loaded. Try rephrasing or ask about a specific act."
        await save_message(pool, conv_id, "assistant", no_result_msg, confidence="low")
        return {"answer": no_result_msg, "reason": "NO_RESULTS", "citations": [], "confidence": "low", "conversation_id": conv_id}

    persona_prompt = PERSONA_PROMPTS.get(req.persona) if req.persona else None

    try:
        result = await generate_response(req.query, sections, persona=persona_prompt, history=history)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Groq API error: {str(e)}")

    # Save messages to conversation
    await save_message(pool, conv_id, "user", req.query)
    await save_message(pool, conv_id, "assistant", result.get("answer", ""), result.get("citations"), result.get("confidence"))

    result["conversation_id"] = conv_id
    result["retrieved_sections"] = [
        {"lims_id": s.lims_id, "label": s.label, "law_code": s.law_code, "score": s.combined_score}
        for s in sections
    ]
    return result

@router.post("/query/stream")
async def query_stream(req: QueryRequest):
    pool = get_pool()

    # Get or create conversation for memory
    conv_id = await get_or_create_conversation(pool, req.conversation_id)
    history = await get_conversation_history(pool, conv_id)

    # Reformulate query using conversation history for context
    from api.services.rag import reformulate_query
    search_query = await reformulate_query(req.query, history)

    sections = await hybrid_search(search_query, pool, top_k=5, language=req.language, law_code=req.law_code)

    if not sections:
        await save_message(pool, conv_id, "user", req.query)
        async def empty():
            yield {"event": "message", "data": json.dumps({
                "type": "done",
                "data": {"answer": None, "reason": "NO_RESULTS", "citations": [], "confidence": "low", "conversation_id": conv_id}
            })}
        return EventSourceResponse(empty())

    persona_prompt = PERSONA_PROMPTS.get(req.persona) if req.persona else None

    # Save user message before streaming
    await save_message(pool, conv_id, "user", req.query)

    async def event_generator():
        full_text = ""
        try:
            # Emit retrieved sections immediately
            retrieved_data = [
                {"lims_id": s.lims_id, "label": s.label, "law_code": s.law_code, "score": s.combined_score}
                for s in sections
            ]
            yield {"event": "message", "data": json.dumps({"type": "retrieved_sections", "data": retrieved_data})}

            async for event in generate_response_stream(req.query, sections, persona=persona_prompt, history=history):
                if event["type"] == "token":
                    full_text += event["data"]
                yield {"event": "message", "data": json.dumps(event)}

            # After streaming completes, save the assistant's response
            try:
                parsed = json.loads(full_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
                await save_message(pool, conv_id, "assistant", parsed.get("answer", full_text), parsed.get("citations"), parsed.get("confidence"))
            except (json.JSONDecodeError, Exception):
                await save_message(pool, conv_id, "assistant", full_text)

            # Send conversation_id to frontend
            yield {"event": "message", "data": json.dumps({"type": "conversation_id", "data": conv_id})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"detail": f"Groq API error: {str(e)}"})}

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
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        summary = completion.choices[0].message.content
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Groq API error: {str(e)}")

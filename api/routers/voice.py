"""
Voice router — endpoints for ElevenLabs integration.

POST /api/voice/token  — signed WebSocket URL for Conversational AI
POST /api/voice/llm    — webhook called BY ElevenLabs agent
POST /api/voice/tts    — text-to-speech (type a question, hear it back)
GET  /api/voice/voices — list available ElevenLabs voices
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
import json

from api.services.voice import get_signed_url, text_to_speech, get_available_voices
from api.db import get_pool
from api.services.retrieval import hybrid_search
from api.services.rag import build_prompt
from api.config import settings
import json
from groq import AsyncGroq

router = APIRouter(prefix="/api/voice", tags=["voice"])

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.0-flash")

class TTSRequest(BaseModel):
    text: str
    voice_id: str | None = None


@router.post("/token")
async def voice_token():
    """Generate a signed WebSocket URL for ElevenLabs Conversational AI."""
    try:
        signed_url = await get_signed_url()
        return {"signed_url": signed_url}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to get signed URL: {str(e)}")


@router.post("/tts")
async def voice_tts(req: TTSRequest):
    """
    Convert text to speech using ElevenLabs TTS API.
    Returns raw MP3 audio that the browser can play directly.
    """
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")

    try:
        audio_bytes = await text_to_speech(req.text, req.voice_id)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS failed: {str(e)}")


@router.get("/voices")
async def list_voices():
    """List all available ElevenLabs voices (useful for finding voice IDs)."""
    try:
        voices = await get_available_voices()
        return {"voices": voices}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to list voices: {str(e)}")


@router.post("/llm")
async def voice_llm(request: Request):
    """Called BY ElevenLabs agent as 'custom LLM'. Receives transcript, returns streamed text."""
    body = await request.json()
    messages = body.get("messages", [])
    user_message = messages[-1].get("content", "") if messages else ""
    
    if not user_message.strip():
        # Empty audio or payload
        async def empty_generate():
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_generate(), media_type="text/event-stream")

    pool = get_pool()
    sections = await hybrid_search(user_message, pool, top_k=5)

    prompt = build_prompt(user_message, sections)

    # ElevenLabs expects OpenAI-compatible SSE format
    async def generate():
        try:
            stream = await groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    data = {"choices": [{"delta": {"content": content}}]}
                    yield f"data: {json.dumps(data)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'Groq API error: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@router.post("/chat")
async def voice_chat(request: Request):
    """
    Full chat endpoint: takes a text question, runs the RAG pipeline,
    and returns a JSON response. The frontend then calls /tts to hear it.
    """
    body = await request.json()
    question = body.get("question", "").strip()
    law_code = body.get("law_code")

    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")

    pool = get_pool()
    sections = await hybrid_search(question, pool, top_k=5, law_code=law_code)

    if not sections:
        return {"answer": "I couldn't find anything on that in the statutes I have loaded. Try rephrasing or ask about a specific act."}

    try:
        from api.services.rag import generate_response
        result = await generate_response(question, sections)
        return {"answer": result.get("answer", "")}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Groq API error: {str(e)}")

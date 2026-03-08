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

if settings.GROQ_API_KEY:
    groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# ── Lawyer Voice Presets ──────────────────────────────────────────────
VOICE_PRESETS = [
    {
        "id": "empathetic",
        "name": "The Counselor",
        "description": "Warm and approachable — explains in plain language",
        "voice_id": "ErXwobaYiN019PkySvjV",
        "persona_prompt": "TONE: You are warm and approachable. Explain legal concepts as if talking to a friend. Use phrases like \"In simple terms, what this means for you is...\" or \"Don't worry, let me walk you through this...\" Prioritize making the law accessible and understandable.",
    },
    {
        "id": "assertive",
        "name": "The Advocate",
        "description": "Confident and direct — gets straight to the point",
        "voice_id": settings.ELEVENLABS_VOICE_ID,
        "persona_prompt": "TONE: You are assertive and confident. Be direct and decisive. Use phrases like \"The law is clear on this...\" or \"Under the statute, there is no ambiguity...\" Keep explanations sharp and to the point. You project authority.",
    },
    {
        "id": "analytical",
        "name": "The Scholar",
        "description": "Calm and precise — methodical legal analysis",
        "voice_id": "TBt8U1ufDfjfOcYYUUrU",
        "persona_prompt": "TONE: You are methodical and scholarly. Break down the analysis step by step. Use phrases like \"Let us examine this carefully...\" or \"The statute can be broken down into three key elements...\" You value precision and thoroughness.",
    },
]

# Build a lookup for persona prompts
PERSONA_PROMPTS = {p["id"]: p["persona_prompt"] for p in VOICE_PRESETS}


@router.get("/presets")
async def get_voice_presets():
    """Return available lawyer voice presets."""
    return {"presets": VOICE_PRESETS}


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
                model="llama-3.1-8b-instant",
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

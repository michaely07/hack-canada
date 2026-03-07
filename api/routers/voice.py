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

from api.services.voice import get_signed_url, text_to_speech, get_available_voices

router = APIRouter(prefix="/api/voice", tags=["voice"])


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


@router.post("/chat")
async def voice_chat(request: Request):
    """
    Full chat endpoint: takes a text question, returns a JSON response
    with the answer text. The frontend then calls /tts to hear it.

    This is the text-input workaround when mic is unavailable.
    """
    body = await request.json()
    question = body.get("question", "").strip()

    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")

    # TODO: Wire to RAG pipeline when ready.
    # For now, return a placeholder legal-sounding response.
    answer = generate_placeholder_answer(question)

    return {"answer": answer}


def generate_placeholder_answer(question: str) -> str:
    """
    Placeholder answer generator until the RAG pipeline is connected.
    Gives a legal-counsel-style response to demonstrate the voice.
    """
    q = question.lower()

    if "criminal" in q or "crime" in q:
        return (
            "Under the Criminal Code of Canada, R.S.C. 1985, c. C-46, "
            "criminal offences are categorized as summary conviction offences "
            "and indictable offences. The classification determines the procedure, "
            "available penalties, and limitation periods. I'd recommend reviewing "
            "the specific provisions relevant to your inquiry."
        )
    elif "tax" in q or "income" in q:
        return (
            "The Income Tax Act, R.S.C. 1985, c. 1 (5th Supp.), governs federal "
            "taxation in Canada. It establishes the rules for computing income, "
            "deductions, credits, and the obligations of taxpayers. For specific "
            "tax questions, I'd need to examine the relevant sections more closely."
        )
    elif "charter" in q or "rights" in q or "freedom" in q:
        return (
            "The Canadian Charter of Rights and Freedoms, Part I of the "
            "Constitution Act, 1982, guarantees fundamental rights including "
            "freedom of expression under Section 2(b), the right to life, liberty "
            "and security of the person under Section 7, and equality rights under "
            "Section 15. These rights are subject to reasonable limits under Section 1."
        )
    elif "immigration" in q or "citizen" in q:
        return (
            "Immigration matters in Canada are primarily governed by the "
            "Immigration and Refugee Protection Act, S.C. 2001, c. 27. "
            "The Act establishes categories for permanent residents, foreign workers, "
            "refugees, and sets out inadmissibility grounds and removal procedures."
        )
    else:
        return (
            f"That's an excellent question regarding {question}. "
            "Under Canadian federal law, this area would require a thorough "
            "review of the relevant statutes and regulations. Once our full "
            "legal research database is connected, I'll be able to provide "
            "specific statutory references and detailed analysis. "
            "Is there a particular aspect you'd like me to focus on?"
        )

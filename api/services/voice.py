"""
ElevenLabs voice service — handles:
  1. Signed URL generation for Conversational AI WebSocket
  2. Text-to-Speech conversion via ElevenLabs TTS API
"""

import httpx

from api.config import settings


async def get_signed_url() -> str:
    """
    Request a signed WebSocket URL from ElevenLabs for the configured agent.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url"
            f"?agent_id={settings.ELEVENLABS_AGENT_ID}",
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["signed_url"]


async def text_to_speech(text: str, voice_id: str | None = None) -> bytes:
    """
    Convert text to speech using ElevenLabs TTS API.

    Args:
        text: The text to convert to speech.
        voice_id: ElevenLabs voice ID. Defaults to settings.ELEVENLABS_VOICE_ID.

    Returns:
        Raw audio bytes (mp3 format).
    """
    vid = voice_id or settings.ELEVENLABS_VOICE_ID

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.3,
                },
            },
        )
        response.raise_for_status()
        return response.content


async def get_available_voices() -> list[dict]:
    """
    Fetch all available voices from ElevenLabs.
    Useful for finding voice IDs.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
            },
        )
        response.raise_for_status()
        data = response.json()
        return [
            {"voice_id": v["voice_id"], "name": v["name"], "category": v.get("category", "")}
            for v in data.get("voices", [])
        ]

"""ElevenLabs voice service — signed URL generation for Conversational AI WebSocket."""

import httpx
from api.config import settings


async def get_signed_url() -> str:
    """Request a signed WebSocket URL from ElevenLabs for the configured agent."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url",
            params={"agent_id": settings.elevenlabs_agent_id},
            headers={"xi-api-key": settings.elevenlabs_api_key},
        )
        response.raise_for_status()
        data = response.json()
        return data["signed_url"]

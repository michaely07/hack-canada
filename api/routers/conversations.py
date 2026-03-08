from fastapi import APIRouter
from api.db import get_pool
import uuid

router = APIRouter()

@router.post("/conversations")
async def create_conversation():
    pool = get_pool()
    row = await pool.fetchrow("INSERT INTO conversations DEFAULT VALUES RETURNING id, created_at")
    return dict(row)


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT role, content, citations, confidence, created_at FROM messages "
        "WHERE conversation_id = $1 ORDER BY created_at ASC",
        uuid.UUID(conversation_id),
    )
    return [dict(r) for r in rows]

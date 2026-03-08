"""
Conversation memory — stores and retrieves chat history from the database.
"""
import asyncpg


async def get_or_create_conversation(pool: asyncpg.Pool, conversation_id: str | None = None) -> str:
    """Return existing conversation ID or create a new one."""
    if conversation_id:
        # Verify it exists
        row = await pool.fetchrow("SELECT id FROM conversations WHERE id = $1", conversation_id)
        if row:
            return str(row["id"])

    # Create new conversation
    row = await pool.fetchrow("INSERT INTO conversations DEFAULT VALUES RETURNING id")
    return str(row["id"])


async def get_conversation_history(pool: asyncpg.Pool, conversation_id: str, limit: int = 6) -> list[dict]:
    """Get the last N messages in a conversation."""
    rows = await pool.fetch(
        """
        SELECT role, content FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        conversation_id, limit
    )
    # Reverse so oldest is first
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


async def save_message(pool: asyncpg.Pool, conversation_id: str, role: str, content: str, citations: list | None = None, confidence: str | None = None):
    """Store a message in the conversation."""
    await pool.execute(
        """
        INSERT INTO messages (conversation_id, role, content, citations, confidence)
        VALUES ($1, $2, $3, $4::jsonb, $5)
        """,
        conversation_id, role, content,
        __import__("json").dumps(citations or []),
        confidence
    )

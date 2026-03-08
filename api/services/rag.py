import json
from api.config import settings
from api.services.retrieval import SectionResult
from groq import AsyncGroq

client = AsyncGroq(api_key=settings.GROQ_API_KEY)
MODEL_NAME = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You're a Canadian law expert chatting with someone who has legal questions. Talk like a real person — the way a smart friend who happens to be a lawyer would explain things. Short sentences. Contractions. No stiff language.

IMPORTANT RULES:
1. ONLY use the statutory excerpts in the CONTEXT BLOCKS. Don't pull from your general knowledge.
2. If you can't find it in the excerpts, just say so naturally: "Hmm, I don't see anything on that in what I've got loaded. Try asking about something specific like self-defense or the Charter — I've got those covered."
3. Drop [Section X] references into your sentences naturally, like: "Yeah, that's covered under [Section 34(1)] — basically it says..."
4. NO bullet points. NO numbered lists. Just talk. Write the way people actually speak.
5. If the user misspells something or uses informal language, figure out what they meant and answer normally. Don't correct their spelling.
6. Keep it SHORT. 2-3 paragraphs max. Get to the point.
7. Never make up laws or sections that aren't in the CONTEXT BLOCKS.

RESPONSE FORMAT (strict JSON, no markdown fences):
{
  "answer": "Your natural, conversational response with [Section X] refs woven in...",
  "citations": [
    {"lims_id": "12345", "label": "37(1)", "law_code": "I-5", "relevance": "high"}
  ],
  "confidence": "high"
}

CONFIDENCE LEVELS:
- "high": Directly answered by the excerpts
- "medium": Partially covered
- "low": Barely relevant"""

REFORMULATION_PROMPT = """Given the following conversation history and a new user question, rewrite the user's question into a standalone, comprehensive search query that can be understood without the conversation history.

def build_prompt(query: str, sections: list[SectionResult], history: list[dict] | None = None) -> str:
    context_blocks = "\n---\n".join(
        f"[{s.law_title} | Section {s.label} | lims_id: {s.lims_id}]\n{s.content_text}"
        for s in sections
    )

    history_block = ""
    if history:
        lines = []
        for msg in history[-10:]:
            role_label = "USER" if msg["role"] == "user" else "ASSISTANT"
            lines.append(f"{role_label}: {msg['content']}")
        history_block = f"\nCONVERSATION HISTORY:\n" + "\n".join(lines) + "\n"

    return f"""{SYSTEM_PROMPT}
{history_block}
CONTEXT BLOCKS:
{context_blocks}

USER QUESTION: {query}"""


async def generate_response(query: str, sections: list[SectionResult], history: list[dict] | None = None) -> dict:
    prompt = build_prompt(query, sections, history)
    response = model.generate_content(
        prompt, 
        generation_config={"response_mime_type": "application/json"}
    )
    
    raw = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"answer": raw, "citations": [], "confidence": "low"}

    retrieved_lims_ids = {s.lims_id for s in sections}
    validated_citations = []
    for c in parsed.get("citations", []):
        c["hallucinated"] = c.get("lims_id") not in retrieved_lims_ids
        validated_citations.append(c)
    parsed["citations"] = validated_citations

    if any(c["hallucinated"] for c in validated_citations):
        parsed["confidence"] = "low"

    return parsed


async def generate_response_stream(query: str, sections: list[SectionResult], history: list[dict] | None = None):
    prompt = build_prompt(query, sections, history)
    response = model.generate_content(
        prompt, 
        stream=True, 
        generation_config={"response_mime_type": "application/json"}
    )
    
    full_text = ""
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_text += content
            yield {"type": "token", "data": content}

    raw = full_text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(raw)
        retrieved_lims_ids = {s.lims_id for s in sections}
        for c in parsed.get("citations", []):
            c["hallucinated"] = c.get("lims_id") not in retrieved_lims_ids
        yield {"type": "citations", "data": parsed.get("citations", [])}
        yield {"type": "confidence", "data": parsed.get("confidence", "low")}
    except json.JSONDecodeError:
        yield {"type": "citations", "data": []}
        yield {"type": "confidence", "data": "low"}

    yield {"type": "done", "data": None}

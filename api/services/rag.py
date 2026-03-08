import json
from api.config import settings
from api.services.retrieval import SectionResult
from groq import AsyncGroq

client = AsyncGroq(api_key=settings.GROQ_API_KEY)
MODEL_NAME = "llama3-8b-8192"

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

DO NOT answer the question. ONLY output the rewritten search query.
If the new user question is already self-contained or is changing the topic entirely, just output the new question as-is.

Make sure to include implicit context (e.g., "taxes" -> "federal income tax", "assault" -> "criminal code assault")."""


async def reformulate_query(query: str, history: list[dict] | None = None) -> str:
    if not history:
        return query

    # Only look at the last few turns for context
    turns = []
    for msg in history[-4:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        turns.append(f"{role}: {msg['content']}")
    history_block = "\n".join(turns)

    prompt = f"{REFORMULATION_PROMPT}\n\nCONVERSATION HISTORY:\n{history_block}\n\nNEW QUESTION: {query}\n\nREWRITTEN QUERY:"
    
    try:
        response = await client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100
        )
        reformulated = response.choices[0].message.content.strip()
        # Clean up any quotes the LLM might have added
        if reformulated.startswith('"') and reformulated.endswith('"'):
            reformulated = reformulated[1:-1]
        return reformulated
    except Exception:
        # Fallback to the original query if the LLM fails
        return query


def build_prompt(query: str, sections: list[SectionResult], persona: str | None = None, history: list[dict] | None = None) -> str:
    context_blocks = "\n---\n".join(
        f"[{s.law_title} | Section {s.label} | lims_id: {s.lims_id}]\n{s.content_text}"
        for s in sections
    )
    persona_block = f"\n\n{persona}" if persona else ""

    # Include recent conversation history for context
    history_block = ""
    if history:
        turns = []
        for msg in history[-6:]:  # last 3 exchanges (6 messages)
            role = "User" if msg["role"] == "user" else "You"
            turns.append(f"{role}: {msg['content']}")
        history_block = f"\n\nRECENT CONVERSATION:\n" + "\n".join(turns)

    return f"""{SYSTEM_PROMPT}{persona_block}{history_block}

CONTEXT BLOCKS:
{context_blocks}

USER QUESTION: {query}"""


async def generate_response(query: str, sections: list[SectionResult], persona: str | None = None, history: list[dict] | None = None) -> dict:
    prompt = build_prompt(query, sections, persona, history)
    
    # Require JSON output in prompt to use json_object mode
    json_instruction = "\n\nYou must return your response in the requested strict JSON format."
    
    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt + json_instruction}],
        response_format={"type": "json_object"}
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


async def generate_response_stream(query: str, sections: list[SectionResult], persona: str | None = None, history: list[dict] | None = None):
    prompt = build_prompt(query, sections, persona, history)
    
    # Require JSON output in prompt to use json_object mode
    json_instruction = "\n\nYou must return your response in the requested strict JSON format."
    
    stream = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt + json_instruction}],
        response_format={"type": "json_object"},
        stream=True
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

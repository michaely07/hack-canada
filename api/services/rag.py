import google.generativeai as genai
import json
from api.config import settings
from api.services.retrieval import SectionResult

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

SYSTEM_PROMPT = """You are a legal research assistant specializing in Canadian federal statutes and regulations.

RULES:
1. Use the statutory excerpts in the CONTEXT BLOCKS below as your primary source.
2. You may supplement with your general legal knowledge to explain concepts, provide context, or clarify legal principles, but always prioritize the provided excerpts.
3. When citing specific statutory text, use [Section X] notation referencing the provided excerpts.
4. Clearly distinguish between what is stated in the excerpts and any additional context you provide.
5. Use precise legal language, then explain in plain English.
6. Always provide a helpful answer. If the excerpts are only partially relevant, use them as a starting point and supplement with your knowledge.

RESPONSE FORMAT (strict JSON, no markdown fences):
{
  "answer": "Your answer with [Section X(Y)] citations inline...",
  "citations": [
    {"lims_id": "12345", "label": "37(1)", "law_code": "I-5", "relevance": "high"}
  ],
  "confidence": "high"
}

CONFIDENCE LEVELS:
- "high": Answer is directly supported by the excerpts
- "medium": Answer uses excerpts supplemented with general legal knowledge
- "low": Answer relies mostly on general knowledge with limited excerpt support"""


def build_prompt(query: str, sections: list[SectionResult]) -> str:
    context_blocks = "\n---\n".join(
        f"[{s.law_title} | Section {s.label} | lims_id: {s.lims_id}]\n{s.content_text}"
        for s in sections
    )
    return f"""{SYSTEM_PROMPT}

CONTEXT BLOCKS:
{context_blocks}

USER QUESTION: {query}"""


async def generate_response(query: str, sections: list[SectionResult]) -> dict:
    prompt = build_prompt(query, sections)
    response = model.generate_content(
        prompt, 
        generation_config={"response_mime_type": "application/json"}
    )
    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

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


async def generate_response_stream(query: str, sections: list[SectionResult]):
    prompt = build_prompt(query, sections)
    response = model.generate_content(
        prompt, 
        stream=True, 
        generation_config={"response_mime_type": "application/json"}
    )
    full_text = ""
    for chunk in response:
        if chunk.text:
            full_text += chunk.text
            yield {"type": "token", "data": chunk.text}

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

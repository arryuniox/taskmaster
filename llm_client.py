import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ── config ───────────────────────────────────────────────────────────
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = "llama-3.3-70b-versatile"

OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODEL  = "qwen2.5:3b"

TASK_PROMPT = """You are a student productivity assistant. Read the brain dump carefully and extract EVERY distinct task or responsibility mentioned — do not merge them, do not skip any.

Rules:
- Extract one task per subject/deadline/responsibility mentioned
- Read tone carefully: "my groupmate is cracked" = they are skilled = low urgency for that task
- "will be a breeze" = low urgency, student feels confident
- Urgency is based on deadline AND how much work the student actually needs to do
- If a deadline is mentioned (e.g. "friday", "next wednesday") use it
- Return ONLY raw JSON — no markdown, no backticks, no explanation, nothing else

Brain dump: "{text}"

{gcal_context}

Return this exact JSON structure:
{{
  "summary": "2-sentence overview of their actual situation and stress level",
  "tasks": [
    {{
      "title": "short clear task title",
      "detail": "relevant context from what they said",
      "urgency": 5,
      "urgency_reason": "one sentence: deadline + effort needed",
      "size": "small|medium|large",
      "deadline": "e.g. this friday, next wednesday, or null",
      "category": "academic|admin|social|personal",
      "subtasks": ["concrete step 1", "concrete step 2"]
    }}
  ]
}}

Urgency scale:
5 = due very soon AND requires significant effort
4 = due this week
3 = due soon but low effort needed (e.g. groupmate is handling it, student feels confident)
2 = low priority
1 = someday / vague

Sort tasks array by urgency descending."""


def _clean_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _build_prompt(text: str, gcal_events: list) -> str:
    gcal_context = ""
    if gcal_events:
        lines = "\n".join(f"- {e['summary']} at {e['start']}" for e in gcal_events[:10])
        gcal_context = f"Upcoming calendar events for context:\n{lines}\n"
    return TASK_PROMPT.format(text=text, gcal_context=gcal_context)


async def _try_groq(prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        return _clean_json(raw)


async def _try_ollama(prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        return _clean_json(r.json()["response"])


async def extract_tasks(text: str, gcal_events: list = None) -> dict:
    """Try Groq first (fast, needs internet). Fall back to local Ollama."""
    prompt = _build_prompt(text, gcal_events or [])

    if GROQ_API_KEY:
        try:
            result = await _try_groq(prompt)
            print("[llm] used Groq")
            return result
        except Exception as e:
            print(f"[llm] Groq failed ({e}), falling back to Ollama")

    result = await _try_ollama(prompt)
    print("[llm] used Ollama (local)")
    return result
import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"  # fast on CPU — swap to "mistral" if you have a GPU

TASK_PROMPT = """You are a student productivity assistant. Extract every task from the brain dump below.
Return ONLY valid JSON — no markdown, no explanation, no backticks.

Brain dump: "{text}"

{gcal_context}

JSON structure:
{{
  "summary": "2-sentence overview of their situation",
  "tasks": [
    {{
      "title": "short task title",
      "detail": "extra context from what they said",
      "urgency": 5,
      "urgency_reason": "one sentence why",
      "size": "small|medium|large",
      "deadline": "deadline string or null",
      "category": "academic|admin|social|personal",
      "subtasks": ["step 1", "step 2"]
    }}
  ]
}}

Urgency: 5=due very soon, 4=this week, 3=soon, 2=low, 1=someday. Sort by urgency desc."""


async def extract_tasks(text: str, gcal_events: list = None) -> dict:
    gcal_context = ""
    if gcal_events:
        event_lines = "\n".join(
            f"- {e['summary']} at {e['start']}" for e in gcal_events[:10]
        )
        gcal_context = f"Upcoming calendar events for context:\n{event_lines}\n"

    prompt = TASK_PROMPT.format(text=text, gcal_context=gcal_context)

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False}
        )
        r.raise_for_status()
        raw = r.json()["response"].strip()

    # strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    import json
    return json.loads(raw.strip())
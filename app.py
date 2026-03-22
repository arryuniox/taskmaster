import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

import db
import gcal
from llm_client import extract_tasks

app = FastAPI()
db.init_db()

# ── serve the frontend ──────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def root():
    return FileResponse("frontend/index.html")


# ── models ──────────────────────────────────────────────────────────
class BrainDumpRequest(BaseModel):
    text: str
    use_gcal: bool = True

class TaskDoneRequest(BaseModel):
    task_id: int

class PushCalRequest(BaseModel):
    task_id: int
    date: str  # YYYY-MM-DD


# ── routes ──────────────────────────────────────────────────────────
@app.post("/api/extract")
async def extract(req: BrainDumpRequest):
    """Main endpoint: brain dump → parsed + saved tasks."""
    events = gcal.get_upcoming_events() if req.use_gcal else []
    try:
        result = await extract_tasks(req.text, events)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {e}")

    saved = db.save_tasks(result.get("tasks", []))
    return {"summary": result.get("summary", ""), "tasks": saved}


@app.get("/api/tasks")
def get_tasks(include_done: bool = False):
    return db.get_tasks(include_done)


@app.post("/api/tasks/done")
def mark_done(req: TaskDoneRequest):
    db.mark_done(req.task_id)
    return {"ok": True}


@app.delete("/api/tasks/{task_id}")
def delete(task_id: int):
    db.delete_task(task_id)
    return {"ok": True}


@app.get("/api/gcal/status")
def gcal_status():
    return {"available": gcal.is_available()}


@app.get("/api/gcal/events")
def gcal_events():
    return gcal.get_upcoming_events()


@app.post("/api/gcal/push")
def push_to_cal(req: PushCalRequest):
    tasks = db.get_tasks(include_done=True)
    task = next((t for t in tasks if t["id"] == req.task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    ok = gcal.create_event(task["title"], req.date, task.get("detail", ""))
    return {"ok": ok}


# ── run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
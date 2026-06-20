import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from converters.router import convert_document

app = FastAPI(title="DocStream")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# In-memory job registry: job_id -> asyncio.Queue
JOBS: dict[str, asyncio.Queue] = {}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    supported = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
                 ".txt", ".md", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    if suffix not in supported:
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    job_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{job_id}{suffix}"
    content = await file.read()
    dest.write_bytes(content)

    queue: asyncio.Queue = asyncio.Queue()
    JOBS[job_id] = queue

    asyncio.create_task(run_conversion(job_id, dest, queue))

    return {"job_id": job_id, "filename": file.filename}


async def run_conversion(job_id: str, path: Path, queue: asyncio.Queue):
    try:
        async for chunk in convert_document(path):
            await queue.put({"type": "chunk", **chunk})
        await queue.put({"type": "done"})
    except Exception as e:
        await queue.put({"type": "error", "message": str(e)})
    finally:
        await queue.put(None)  # sentinel to close stream
        path.unlink(missing_ok=True)


@app.get("/stream/{job_id}")
async def stream(job_id: str):
    queue = JOBS.get(job_id)
    if queue is None:
        raise HTTPException(404, "Unknown job_id")

    async def event_gen():
        while True:
            item = await queue.get()
            if item is None:
                JOBS.pop(job_id, None)
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

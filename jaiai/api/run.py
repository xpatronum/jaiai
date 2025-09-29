import asyncio as asio
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from jaiai.etc.io import source_from_dataset
from jaiai.etc.schema import IsDoneRequest
from jaiai.figures.prime import WordCloudFigure
from jaiai.jobs.registry import JobRegistry

BUILD_DIR = Path(__file__).parent.parent / "building"
STATIC_DIR = BUILD_DIR / "assets"
DEFAULT_SNAPSHOT_DIR = Path(__file__).parent.parent.parent / "snapshot"

app = FastAPI()

origins = [
    "http://127.0.0.1",
    "http://127.0.0.1:2288",
    "http://172.18.224.1",
    "http://172.18.224.1:2288",
    "http://localhost",
    "http://localhost:2288",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1) Отдаём статику (js/css/img) с кэшированием
app.mount(
    "/assets",
    StaticFiles(directory=STATIC_DIR),
    name="assets",
)


# 2) Главная страница
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(BUILD_DIR / "index.html", media_type="text/html")


def JobRedis():
    JobClient = JobRegistry("redis://localhost:6379/0")
    return JobClient


@app.on_event("startup")
async def startup_event():
    JobRedis()


@app.on_event("shutdown")
async def _shutdown():
    redis = JobRedis()
    if redis:
        await redis.r.aclose()


def io_stopwords() -> list[str]:
    stopwords = source_from_dataset(
        Path(os.getcwd()) / "jaiai" / "builtins" / "stopwords.txt", as_json=True
    )
    return list(set(stopwords))  # type: ignore


def check_io_and_maybe_raise(fpath, allowed_extensions, job_id):
    fpath = DEFAULT_SNAPSHOT_DIR / f"{job_id}" / Path(fpath.filename or "")
    extension = (fpath.suffix.lower().lstrip(".")) or ""
    logger.info(f"Received file with extension: .{extension or 'unknown'}")
    if extension not in allowed_extensions:
        logger.error(
            (
                f"Unsupported file type extension: .{extension or 'unknown'} "
                f"(Allowed: {', '.join(allowed_extensions)})"
            )
        )  # type: ignore
        return (
            False,
            HTTPException(
                status_code=415,
                detail=f"Unsupported file type extension: .{extension or 'unknown'} (Allowed: {', '.join(allowed_extensions)})",
            ),
        )
    from jaiai.etc.io import source_from_dataset

    try:
        js_docs = source_from_dataset(fpath, as_json=True)
    except Exception as e:
        logger.error(
            f"IO error reading incoming file {fpath}, please see more details in {e}"
        )
        return (False, None, e)
    return (True, js_docs, None)


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(..., description="Файл для загрузки"),
    meta: Optional[str] = Form(
        None, description="Опциональная мета в виде JSON-строки"
    ),
):

    content = await file.read()
    job_id = str(uuid.uuid4())
    save_path = DEFAULT_SNAPSHOT_DIR / f"{job_id}" / f"{file.filename}"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(content)
    logger.info(f"IO snapshot uuid={job_id} saved to {save_path}")

    allowed_extensions = {"csv", "json", "xlsx"}
    status, js_data, error = check_io_and_maybe_raise(file, allowed_extensions, job_id)

    if not status:
        raise error  # type: ignore

    pipeline = WordCloudFigure()
    wc_content = " ".join([" ".join(js_doc.values()) for js_doc in js_data])
    stopwords = io_stopwords()
    words, figure = pipeline.render(wc_content, stopwords=stopwords)

    payload = dict(uuid=job_id, num_records=len(js_data), wcloud_figure=words)

    redis = JobRedis()
    await redis.register(job_id, payload)
    asio.create_task(process_job(job_id))

    return Response(content=json.dumps(payload), media_type="application/json")


@app.post("/is_done")
async def is_done(req: IsDoneRequest):
    redis = JobRedis()
    done = await redis.is_done(str(req.uuid))
    return {"id": str(req.uuid), "done": done}


@app.post("/predict")
async def predict():
    pass


# Clustering on topics
async def process_job(job_id: str):
    redis = JobRedis()
    await asio.sleep(2.0)
    await redis.mark_done(job_id, result={"postprocess": "ok"})


@app.get("/ts_render")
async def ts_render(request: Request):
    async def event_generator():
        counter = 1
        while True:
            if await request.is_disconnected():
                break
            yield f"data: {counter}\n\n"
            counter += 1
            await asio.sleep(1)

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
    }
    return StreamingResponse(
        event_generator(), headers=headers, media_type="text/event-stream"
    )


# 3) SPA fallback: любые другие пути — отдаём index.html,
#    чтобы роутинг делал frontend (React Router и т.п.)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def maybe_fallback(full_path: str):
    return FileResponse(BUILD_DIR / "index.html", media_type="text/html")

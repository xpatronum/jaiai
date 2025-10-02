import asyncio as asio
import json
import os
import uuid
from functools import lru_cache, partial
from pathlib import Path
from typing import Optional

import numpy as np
import plotly
import polars as pl
from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from jaiai.configuring.prime import Config
from jaiai.etc.io import async_read_job_file, async_save_job_file, source_from_dataset
from jaiai.etc.schema import (
    ItemOut,
    PredictIn,
    PredictOut,
    RenderIn,
    TsRenderIn,
    TsRenderOut,
)
from jaiai.figures.helpers import prepare2d
from jaiai.figures.prime import PlotlyScatterChart, WordCloudFigure
from jaiai.jobs.registry import JobRegistry
from jaiai.jobs.runtime import GlobalModelRuntime
from jaiai.running.clusters import (
    DocEmbedder,
    IBTRunner,
    IHFWrapperBackend,
    IUMAPDimReducer,
)
from jaiai.running.instructions import InstructionForTopicExtraction, OpenAiTask
from jaiai.storing.store import PolarsDocStore

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
    "http://10.255.255.254",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=".*",
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


async def JobRedisCallback(completed: int, total: int, job_id: str):
    JobClient = JobRegistry("redis://localhost:6379/0")
    logger.info(f"OpenAIAsyncWrapper: completed {completed}/{total} tasks ({completed/total:.2%})")
    rounded_progress = int(completed * 1.0 / (total * 1.0) * 95)
    step = min(rounded_progress, 95)
    await JobClient.register(f"{job_id}_progress", step)  # type: ignore

    return JobClient


@app.on_event("startup")
async def startup_event():
    JobRedis()
    GlobalModelRuntime.call()


@app.on_event("shutdown")
async def _shutdown():
    redis = JobRedis()
    if redis:
        await redis.r.aclose()


@lru_cache(maxsize=1)
def io_stopwords() -> list[str]:
    stopwords = source_from_dataset(Path(os.getcwd()) / "jaiai" / "builtins" / "stopwords.txt", as_json=True)
    return list(set(stopwords))  # type: ignore


def check_io_and_maybe_raise(fpath, allowed_extensions, job_id):
    fpath = DEFAULT_SNAPSHOT_DIR / f"{job_id}" / Path(fpath.filename or "")
    extension = (fpath.suffix.lower().lstrip(".")) or ""
    logger.info(f"Received file with extension: .{extension or 'unknown'}")
    if extension not in allowed_extensions:
        logger.error(
            (f"Unsupported file type extension: .{extension or 'unknown'} " f"(Allowed: {', '.join(allowed_extensions)})")
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
        logger.error(f"IO error reading incoming file {fpath}, please see more details in {e}")
        return (False, None, e)
    return (True, js_docs, None)


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(..., description="Файл для загрузки"),
    meta: Optional[str] = Form(None, description="Опциональная мета в виде JSON-строки"),
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
    wc_content = " ".join([js_doc["text"] for js_doc in js_data])
    stopwords = io_stopwords()
    words, _ = pipeline.render(wc_content, stopwords=stopwords)

    payload = dict(uuid=job_id, num_records=len(js_data), wcloud_figure=words)

    redis = JobRedis()
    await redis.register(job_id, payload)
    asio.create_task(process_job(job_id, js_data))

    return Response(content=json.dumps(payload), media_type="application/json")


@app.post("/predict", response_model=PredictOut)
async def predict(payload: PredictIn = Body(...)):
    tasks = [OpenAiTask(id=item.id, text=item.text) for item in payload.data]
    pipeline = InstructionForTopicExtraction(
        system_prompt_fpath=Path(__file__).parent.parent / "builtins" / "entities_system_prompt.txt"
    )
    results = await asio.to_thread(pipeline.run, tasks)
    predictions = []
    for res in results:
        parsed_json = res.get("parsed_json", dict(topics=[], sentiments=[]))
        predictions.append(
            ItemOut(
                id=res.get("id", None),
                topics=parsed_json.get("topics", []),
                sentiments=parsed_json.get("sentiments", []),
            )
        )
    return PredictOut(predictions=predictions)


# Clustering on topics
async def process_job(job_id: str, js_data):
    redis = JobRedis()
    runtime = GlobalModelRuntime.call()
    assert runtime.backend["model"] is not None, logger.error(f"Error initializing model")
    assert runtime.backend["processor"] is not None, logger.error(f"Error initializing processor")
    tasks = [OpenAiTask(id=item["id"], text=item["text"]) for item in js_data]
    pipeline = InstructionForTopicExtraction(
        system_prompt_fpath=Path(__file__).parent.parent / "builtins" / "entities_system_prompt.txt"
    )

    # 0. Вызов LLM для присвоения топиков
    progress_cb = partial(JobRedisCallback, job_id=job_id)
    response = await pipeline.run_async(tasks, progress_cb=progress_cb)
    preds = []
    for r in response:
        llm_response = r["parsed_json"]
        topics, sentiments = llm_response["topics"], llm_response["sentiments"]
        preds.append({"id": r["id"], "topics": topics, "sentiments": sentiments})

    # 1. Преобразуем js_data в polars DataFrame для быстрого обогащения результата с LLM
    pl_preds = pl.from_dicts(preds)
    pl_docs = pl.from_dicts(js_data)
    pl_data = pl_docs.join(pl_preds, on="id", how="inner")
    js_data = pl_data.to_dicts()
    await redis.register(f"{job_id}_data", js_data)
    await async_save_job_file(job_id, js_data)
    # 2. Считаем статистику по топикам
    store = PolarsDocStore()
    stats = store.compute_stats(pl_data)
    # 3. Сохраняем статистику в Redis по ключу f"{job_id}_stats"
    await redis.register(f"{job_id}_stats", stats)
    # 4. Кластеризация по топикам с UMAP + HDBSCAN
    progress_bar = int(await redis.get(f"{job_id}_progress"))  # type: ignore
    model, processor, device = runtime.backend["model"], runtime.backend["processor"], runtime.backend["device"]
    embedder = DocEmbedder(model=model, processor=processor, device=device)
    backend_wrapper = IHFWrapperBackend(embedder, batch_size=4)

    clustering_config = Config.api["clustering"]["params"]

    bt_runner = IBTRunner(**clustering_config, model=backend_wrapper, verbose=True)
    logger.info(f"Computing embeddings for {len(js_data)} documents on device={device}")
    embeddings = list(embedder.encode(js_data, verbose=True, device=device, batch_size=1))
    logger.info(f"Embeddings computed, shape: {np.array(embeddings).shape}")
    await redis.register(f"{job_id}_progress", min(progress_bar + 10, 99))  # type: ignore
    topics, probs = bt_runner.fit_transform(docs=[doc["text"] for doc in js_data], embeddings=np.array(embeddings).squeeze())
    umap_config = Config.api["clustering"]["umap"]
    progress_bar = int(await redis.get(f"{job_id}_progress"))
    # Dimensionality reduction with UMAP
    reducer = IUMAPDimReducer(**umap_config)
    points = reducer.fit_transform(np.array(embeddings).squeeze())
    await redis.register(f"{job_id}_progress", min(progress_bar + 5, 99))  # type: ignore
    pl_view = prepare2d(
        docs=js_data,
        topics=topics,
        labels=[js_doc["topics"][0] if len(js_doc["topics"]) > 0 else "Общее" for js_doc in js_data],
        reduced_embeddings=points,
    )
    # 5. Сохраняем plotly.figure.json в Redis по ключу f"{job_id}_figure"
    chart = PlotlyScatterChart().view(pl_view, label_to_view="Тематика", logo_path=None)
    chart_payload = plotly.io.to_json(chart)
    await redis.register(f"{job_id}_figure", chart_payload)

    # 6. Финальный прогресс 100%
    await redis.register(f"{job_id}_progress", 100)

    await redis.mark_done(job_id, result={"postprocess": "ok"})


@app.get("/is_done")
async def is_done(request: Request, uuid: str):
    redis = JobRedis()
    job_id = str(uuid)
    logger.info(f"Checking is_done for job_id={job_id}")

    async def event_generator():
        last_progress = None
        while True:
            if await request.is_disconnected():
                logger.info("Client disconnected while checking is_done " f"for job_id={job_id}")
                break
            progress = await redis.get(f"{job_id}_progress")
            logger.info(f"Job {job_id} progress: {progress}")
            if progress != last_progress:
                yield f"data: {progress}\n\n"
                last_progress = progress
            await asio.sleep(0.1)

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
    }
    return StreamingResponse(event_generator(), headers=headers, media_type="text/event-stream")


@app.post("/render")
async def render(payload: RenderIn = Body(...)):
    # topics: list[str]
    # dates: list[int] - в timestamp
    # min_date: int - минимальная дата в timestamp
    # max_date: int - максимальная дата в timestamp

    redis = JobRedis()
    job_id = str(payload.uuid)
    logger.info(f"Rendering for job_id={job_id}")
    await redis.register(f"{job_id}_tsrender", payload=1)
    stats = await redis.get(f"{job_id}_stats")
    figure = await redis.get(f"{job_id}_figure")
    js_figure = json.loads(figure) if figure is not None else None
    if not stats or not figure:
        raise HTTPException(status_code=404, detail="Stats or figure not found for the given job ID")

    response_payload = {**stats, "figure": js_figure}

    return Response(content=json.dumps(response_payload), media_type="application/json")


@app.post("/ts_render", response_model=TsRenderOut)
async def ts_render(payload: TsRenderIn = Body(...)):
    redis = JobRedis()
    job_id, start_date, end_date = payload.uuid, payload.start_date, payload.end_date
    logger.info(f"Received job_id={job_id} for api [POST /ts_render] with dates {start_date} - {end_date}")
    stats = await redis.get(f"{job_id}_data")
    ts_counts = await redis.get(f"{job_id}_tsrender")
    logger.info(f"TS_COUNTS {ts_counts}")
    if not stats:
        raise HTTPException(status_code=404, detail="Stats not found for the given job ID")
    # stats["stats"]: list[dict] по топикам
    store = PolarsDocStore()
    if int(ts_counts) <= 1:
        start_date, end_date = 0, 999999999999999
    js_data = await async_read_job_file(job_id)
    ts_stats = store.compute_ts_stats_naive(js_data, start_date, end_date)
    positives, negatives, neutrals, dates = (
        ts_stats.get("positives", []),
        ts_stats.get("negatives", []),
        ts_stats.get("neutrals", []),
        ts_stats.get("dates", []),
    )
    logger.info(
        f"Computed ts_stats - start_date: {start_date}, end_date: {end_date}, len(positives): {len(positives)}  len(negatives): {len(negatives)} len(neutrals): {len(neutrals)}"
    )
    await redis.register(f"{job_id}_tsrender", int(ts_counts) + 1)
    return TsRenderOut(
        positives=positives,
        negatives=negatives,
        neutrals=neutrals,
        dates=dates,
        uuid=job_id,
    )


# 3) SPA fallback: любые другие пути — отдаём index.html,
#    чтобы роутинг делал frontend (React Router и т.п.)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def maybe_fallback(full_path: str):
    return FileResponse(BUILD_DIR / "index.html", media_type="text/html")

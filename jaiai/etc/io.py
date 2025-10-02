from datetime import datetime
from pathlib import Path

import aiofiles
import polars as pl
import simplejson as json

from jaiai.storing.dataset import API as DatasetApi


def source_from_dataset(dataset_name_or_path, as_json: bool = False, **props):

    maybe_df_or_iter = DatasetApi.named(dataset_name_or_path).iterator(**props)
    if isinstance(maybe_df_or_iter, pl.DataFrame) and not as_json:
        pl_data = maybe_df_or_iter
    elif isinstance(maybe_df_or_iter, pl.DataFrame):
        pl_data = maybe_df_or_iter.to_dicts()
    else:
        dataset = list(maybe_df_or_iter)
        if not as_json:
            pl_data = pl.from_dicts(dataset)
        else:
            pl_data = dataset
    return pl_data


def iso_to_timestamp(iso_str: str, ms: bool = False) -> int:
    dt = datetime.fromisoformat(iso_str)
    ts = int(dt.timestamp())
    return ts * 1000 if ms else ts


def delete_folder(pth):
    for sub in pth.iterdir():
        if sub.is_dir():
            delete_folder(sub)
        else:
            sub.unlink()
    pth.rmdir()


def io_snapshot(
    data,
    where=None,
    snapshot_number: str = "0",
    snapshot_prefix: str = None,
    snapshot_suffix: str = None,
):
    import os
    from pathlib import Path

    from loguru import logger

    where = Path(os.getcwd()) if not where else Path(where)
    snapshot_prefix = "" if snapshot_prefix is None else snapshot_prefix
    snapshot_suffix = "" if snapshot_suffix is None else snapshot_suffix
    filename = f"{snapshot_prefix}{str(snapshot_number)}{snapshot_suffix}.json"
    where_path = where / filename
    where.mkdir(parents=True, exist_ok=True)
    is_ok: bool = None
    try:
        with open(str(where_path), "w+") as fout:
            json.dump(data, fout, ensure_ascii=False)
    except:  # noqa
        logger.error(f"The data coming {data} is not JSON compliant")
        is_ok = False
    else:
        is_ok = True
    return is_ok


async def async_read_job_file(job_id: str, data_dir: str = "snapshot", ext: str = "json"):
    """
    Асинхронно читает файл по job_id из data_dir. Поддержка .json и .csv.
    Возвращает dict/list для json, polars.DataFrame для csv.
    """
    file_path = Path(data_dir) / job_id / f"{job_id}.{ext}"
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if ext == "json":
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    elif ext == "csv":
        return pl.read_csv(file_path)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


async def async_save_job_file(job_id: str, js_data, data_dir: str = "snapshot"):
    """
    Асинхронно сохраняет js_data (dict/list) в json-файл по job_id в data_dir.
    """
    from loguru import logger

    file_dir = Path(data_dir) / job_id
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{job_id}.json"
    try:
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(js_data, ensure_ascii=False))
        return True
    except Exception as e:
        logger.error(f"Failed to save job file {file_path}: {e}")
        return False


__all__ = ["delete_folder", "io_snapshot", "async_read_job_file", "async_save_job_file"]

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


__all__ = ["delete_folder", "io_snapshot"]

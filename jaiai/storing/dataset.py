import os
from collections.abc import Generator
from pathlib import Path

import polars as pl
import simplejson as json
from loguru import logger

from jaiai.etc.pattern import singleton
from jaiai.storing.mask import IDataset
from jaiai.tooling.stl import chunkify


class URLInJSONDataset(IDataset):
    """Dataset to fetch via url in json format"""

    def iterator(self, **kwargs) -> Generator:  # type: ignore
        pass


class TXTDataset(IDataset):
    def __init__(self, fp):
        self.fp = fp

    def iterator(self, **kwargs) -> Generator:
        with open(self.fp, "r") as fp:
            for line in chunkify(fp, sep="\n"):
                yield line.strip()


class JUSTATOMDataset(IDataset):
    def iterator(self, **kwargs) -> Generator:
        with open(Path(os.getcwd()) / ".data" / "polaroids.ai.data.json") as fp:
            docs = json.load(fp)
            for doc in docs:  # noqa: UP028
                yield doc


class JSONDataset(IDataset):
    def __init__(self, fp, **props):
        self.fp = fp

    def iterator(self, **kwargs) -> pl.DataFrame | list[dict]:
        with open(self.fp, "r") as fp:
            js_docs = json.load(fp)
        if kwargs.get("as_json", True):
            return js_docs
        return pl.from_dicts(js_docs)


class CSVDataset(IDataset):
    def __init__(self, fp):
        self.fp = fp

    def iterator(self, **kwargs) -> pl.DataFrame:
        pl_view = pl.read_csv(self.fp, **kwargs)
        return pl_view


class XLSXDataset(IDataset):
    def __init__(self, fp):
        self.fp = fp

    def iterator(self, **kwargs) -> pl.DataFrame:
        pl_view = pl.read_excel(self.fp, **kwargs)
        return pl_view


@singleton
class ByName:
    def named(self, name: str, **kwargs):
        OPS = ["url", "justatom"]

        if name == "justatom":
            klass = JUSTATOMDataset
        elif name == "url":
            klass = URLInJSONDataset
        else:
            fp = Path(name)
            if not fp.exists():
                msg = f"Unknown dataset_name_or_path=[{name}] to init IDataset instance. Use one of {','.join(OPS)} or provide valid dataset path"  # noqa: E501
                logger.error(msg)
                raise ValueError(msg)
            if fp.suffix in [".csv"]:
                return CSVDataset(fp=name, **kwargs)
            elif fp.suffix in [".xlsx"]:
                return XLSXDataset(fp=name, **kwargs)
            elif fp.suffix in [".json", ".jsonl"]:
                return JSONDataset(fp=name, **kwargs)
            elif fp.suffix in [".txt"]:
                return TXTDataset(fp=name, **kwargs)
            else:
                msg = f"File exists however loading from the [{fp.suffix}] file is not supported"
                logger.error(msg)
                raise ValueError(msg)
        return klass(**kwargs)


API = ByName()


__all__ = ["API"]

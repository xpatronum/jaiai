from collections import Counter
from datetime import datetime

import polars as pl
from loguru import logger


class PolarsDocStore:
    """TODO: Replace to normal JSON database for storing documents and computing stats"""

    def __init__(self):
        pass

    def compute_stats(self, pl_docs) -> dict:
        """
        Для каждой темы считает количество позитивных, негативных и нейтральных суждений.
        Возвращает словарь с ключами: stats (список словарей по темам), min_date, max_date
        min_date и max_date — в секундах.
        """
        stats = {}
        samples_positives = {}
        samples_negatives = {}
        samples_neutral = {}

        # Попробуем отсортировать документы по дате, если колонка есть
        try:
            if hasattr(pl_docs, "columns") and "date" in pl_docs.columns:
                pl_docs = pl_docs.sort("date")
        except Exception:
            # если сортировка не удалась — продолжаем без неё
            pass

        first_date = None
        last_date = None

        for row in pl_docs.iter_rows(named=True):
            topics = row.get("topics", [])
            sentiments = row.get("sentiments", [])
            text = row.get("text", "")

            # Собираем min/max дат по первой и последней строке (pl_docs уже отсортирован)
            raw_date = row.get("date")
            if raw_date is not None:
                try:
                    d = int(raw_date)
                    # если переданы миллисекунды — привести к секундам
                    if d > 1_000_000_000_000:
                        d = d // 1000
                    if first_date is None:
                        first_date = d
                    last_date = d
                except Exception:
                    pass

            for topic, sentiment in zip(topics, sentiments):
                if topic not in stats:
                    stats[topic] = Counter()
                    samples_positives[topic] = []
                    samples_negatives[topic] = []
                    samples_neutral[topic] = []
                s = (sentiment or "").lower()
                if s in ("положительно", "positive"):
                    stats[topic]["num_positives"] += 1
                    if len(samples_positives[topic]) < 3:
                        samples_positives[topic].append(text)
                elif s in ("отрицательно", "negative"):
                    stats[topic]["num_negatives"] += 1
                    if len(samples_negatives[topic]) < 3:
                        samples_negatives[topic].append(text)
                elif s in ("нейтрально", "neutral"):
                    stats[topic]["num_neutrals"] += 1
                    if len(samples_neutral[topic]) < 3:
                        samples_neutral[topic].append(text)

        min_date = int(first_date) if first_date is not None else -1
        max_date = int(last_date) if last_date is not None else 9999999999

        result = [
            {
                "topic": topic,
                "nums": {
                    "num_positives": cnt.get("num_positives", 0),
                    "num_negatives": cnt.get("num_negatives", 0),
                    "num_neutrals": cnt.get("num_neutrals", 0),
                },
                "samples_positives": samples_positives[topic],
                "samples_negatives": samples_negatives[topic],
                "samples_neutral": samples_neutral[topic],
            }
            for topic, cnt in stats.items()
        ]

        return dict(
            topics=[r["topic"] for r in result],
            nums=[r["nums"] for r in result],
            dates=[],
            min_date=min_date,
            max_date=max_date,
            samples=[
                dict(
                    samples_negatives=r["samples_negatives"],
                    samples_positives=r["samples_positives"],
                    samples_neutral=r["samples_neutral"],
                )
                for r in result
            ],
        )

    @staticmethod
    def iso_to_timestamp(iso_str: str) -> int:
        """
        Преобразует ISO-строку в timestamp (секунды).
        Если уже int, возвращает как есть.
        """
        if isinstance(iso_str, int):
            return iso_str
        if iso_str.endswith("Z"):
            iso_str = iso_str[:-1]
        try:
            dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S.%f")
            return int(dt.timestamp())
        except ValueError:
            dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S")
            try:
                return int(datetime.fromisoformat(iso_str).timestamp())
            except Exception:
                return -1

    def compute_ts_stats_naive(
        self, js_docs, start_date: str | int, end_date: str | int, topics: list[str] = None, max_baskets: int = 22
    ):
        start_date, end_date = int(self.iso_to_timestamp(start_date)), int(self.iso_to_timestamp(end_date))
        logger.info(f"start_date: {start_date}, end_date: {end_date}, topics: {topics}, max_baskets: {max_baskets}")

        pl_docs = pl.from_dicts(js_docs)
        if pl_docs["date"].dtype == pl.Utf8:
            pl_docs = pl_docs.with_columns(pl.col("date").apply(self.iso_to_timestamp).alias("date"))
        pl_docs = pl_docs.with_columns(pl.col("date").cast(pl.Int64)).sort("date")
        pl_docs_filtered = pl_docs.filter(((pl.col("date") >= int(start_date)) & (pl.col("date") <= int(end_date))))
        js_docs_dated = pl_docs_filtered.to_dicts()

        logger.info(f"Filtered documents count: {len(js_docs_dated)}")
        if topics is not None:
            topics_to_filter = set(pl_docs_filtered.select("topics").explode("topics").unique().to_series().to_list())
            js_docs_answer = [js_doc for js_doc in js_docs_dated if any([topic in topics_to_filter for topic in js_doc["topics"]])]
        else:
            js_docs_answer = js_docs_dated
        if not js_docs_answer:
            return dict(positives=[], negatives=[], neutrals=[], dates=[])
        # Сортируем по дате
        # js_docs_answer = sorted(js_docs_answer, key=lambda x: x["date"])
        L = len(js_docs_answer)
        N = min(L, max_baskets)
        logger.info(f"L: {L}, N: {N}")
        if L <= max_baskets:
            positives, negatives, neutrals, dates = [], [], [], []
            for doc in js_docs_answer:
                counter = Counter(doc.get("sentiments"))
                sentiment = counter.most_common(1)[0][0]
                if sentiment in ("положительно", "positive"):
                    positives.append(1)
                    negatives.append(0)
                    neutrals.append(0)
                elif sentiment in ("отрицательно", "negative"):
                    positives.append(0)
                    negatives.append(1)
                    neutrals.append(0)
                elif sentiment in ("нейтрально", "neutral"):
                    positives.append(0)
                    negatives.append(0)
                    neutrals.append(1)
                else:
                    positives.append(0)
                    negatives.append(0)
                    neutrals.append(0)
                dates.append(doc["date"])
            return dict(positives=positives, negatives=negatives, neutrals=neutrals, dates=dates)
        # Если строк много — бакетируем
        all_dates = [doc["date"] for doc in js_docs_answer if doc.get("date") is not None]
        min_date, max_date = min(all_dates), max(all_dates)
        step = max(1, (max_date - min_date + 1) // N)
        baskets = [(min_date + i * step, min(min_date + (i + 1) * step - 1, max_date)) for i in range(N)]
        positives = [0] * N
        negatives = [0] * N
        neutrals = [0] * N
        for doc in js_docs_answer:
            d = doc["date"]
            counter = Counter(doc.get("sentiments"))
            sentiment = counter.most_common(1)[0][0]
            idx = min((d - min_date) // step, N - 1)
            if sentiment in ("положительно", "positive"):
                positives[idx] += 1
            elif sentiment in ("отрицательно", "negative"):
                negatives[idx] += 1
            elif sentiment in ("нейтрально", "neutral"):
                neutrals[idx] += 1
        dates = [(start + end) // 2 for start, end in baskets]
        return dict(
            positives=positives,
            negatives=negatives,
            neutrals=neutrals,
            dates=dates,
        )

    def filter_by_datetime(self, pl_docs, start: str | int, end: str | int) -> pl.DataFrame:
        return pl_docs.filter((pl.col("date") >= int(start)) & (pl.col("date") <= int(end)))  # type: ignore

    async def write_documents(self, documents: list[dict]) -> None:
        pass


__all__ = ["PolarsDocStore"]

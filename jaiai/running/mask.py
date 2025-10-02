import abc
import asyncio
import inspect
import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from bertopic.backend import BaseEmbedder
from loguru import logger
from openai import AsyncOpenAI

from jaiai.etc.io import source_from_dataset


# ---------- OpenAI Task wrapper ----------
@dataclass(slots=True)
class OpenAiTask:
    id: int | str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class OpenAIAsyncWrapper:

    def __init__(
        self,
        model: str = "llama-3.1-8b-instruct",
        response_format: Optional[dict[str, Any]] = None,  # можно не использовать с llama.cpp
        api_call_timeout: float = 220,
        max_concurrent: int = 5,
        system_prompt_fpath: Optional[str] = None,
        system_prompt: Optional[str] | None = None,
        openai_token: Optional[str] = None,
        base_url: str | None = None,
        organization: Optional[str] = None,
        project: Optional[str] = None,
    ) -> None:
        self.model = model
        self.response_format = response_format  # для llama.cpp обычно не нужен
        self.api_call_timeout = float(api_call_timeout)
        self.max_concurrent = max(1, int(max_concurrent))

        # базовые настройки
        api_key = openai_token or os.getenv("OPENAI_API_KEY") or "sk-noauth"
        base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "http://localhost:1234").rstrip("/")
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
            project=project,
        )

        # итоговый системный промпт
        if system_prompt is None:
            assert system_prompt_fpath is not None, logger.error(
                "OpenAIAsyncWrapper: either system_prompt or system_prompt_fpath must be set"
            )
            lines: list[str] = source_from_dataset(system_prompt_fpath, as_json=True)  # type: ignore
            assert len(lines) > 0, logger.error(f"OpenAIAsyncWrapper: system_prompt_fpath is empty: {system_prompt_fpath}")
            self.system_prompt = "\n".join(lines).strip()
        else:
            self.system_prompt = system_prompt.strip()

    def run(self, tasks: Sequence[OpenAiTask]) -> list[dict[str, Any]]:
        if not tasks:
            return []
        return asyncio.run(self._arun(tasks))

    async def run_async(self, tasks: Sequence[OpenAiTask], progress_cb=None) -> Any:
        callback = self.logger_callback if progress_cb is None else progress_cb
        logger.info(f"run_async: starting {len(tasks)} tasks")
        results = await self._arun_with_progress(tasks, progress_cb=callback)
        logger.info(f"run_async: finished, got {len(results)} results")
        return results

    async def logger_callback(self, completed: int, total: int):
        logger.info(f"OpenAIAsyncWrapper: completed {completed}/{total} tasks ({completed/total:.2%})")

    async def _arun(self, tasks: Sequence[OpenAiTask], progress_cb=None) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(self.max_concurrent)

        async def one(t: OpenAiTask) -> dict[str, Any]:
            async with sem:
                try:
                    return await asyncio.wait_for(self._call(t), timeout=self.api_call_timeout)
                except asyncio.TimeoutError:
                    return {
                        "id": t.id,
                        "metadata": t.metadata,
                        "model": self.model,
                        "error": "timeout",
                        "text": None,
                        "parsed_json": None,
                        "raw": None,
                    }

        return await asyncio.gather(*(one(t) for t in tasks))

    async def _arun_with_progress(self, tasks: Sequence[OpenAiTask], progress_cb=None) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(self.max_concurrent)

        async def one(t: OpenAiTask) -> dict[str, Any]:
            async with sem:
                try:
                    result = await asyncio.wait_for(self._call(t), timeout=self.api_call_timeout)
                except asyncio.TimeoutError:
                    result = {
                        "id": t.id,
                        "metadata": t.metadata,
                        "model": self.model,
                        "error": "timeout",
                        "text": None,
                        "parsed_json": None,
                        "raw": None,
                    }
                return result

        total = len(tasks)
        results = []
        coros = [one(t) for t in tasks]

        for future in asyncio.as_completed(coros):
            resp = await future
            results.append(resp)
            if progress_cb:
                try:
                    maybe = progress_cb(len(results), total)
                    if inspect.isawaitable(maybe):
                        await maybe
                except Exception as e:
                    logger.error(f"progress_cb error: {e}")
        return results

    @abc.abstractmethod
    async def _call(self, task: OpenAiTask) -> dict[str, Any]:
        pass


class IDimReducer(abc.ABC):  # noqa: B024

    @abc.abstractmethod
    def fit_transform(self, embeddings: np.ndarray) -> np.ndarray:  # noqa: B027
        pass

    @abc.abstractmethod
    def transform(self, embeddings: np.ndarray) -> np.ndarray:  # noqa: B027
        pass


class IDocEmbedder(abc.ABC):
    """Abstract class for document embedder."""

    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def encode(self, texts: list[str], **kwargs) -> Iterator[np.ndarray]:
        pass


class ICLUSTERINGWrapperBackend(BaseEmbedder):
    def __init__(self, model: IDocEmbedder):
        self.model = model

    def embed(self, documents: list[str], verbose: bool = False) -> np.ndarray:  # type: ignore
        """Embed a list of n documents/words into an n-dimensional
        matrix of embeddings

        Arguments:
            documents: A list of documents or words to be embedded
            verbose: Controls the verbosity of the process

        Returns:
            Document/words embeddings with shape (n, m) with `n` documents/words
            that each have an embeddings size of `m`
        """
        pass


class ICLUSTERINGRunner(abc.ABC):
    """
    Pipeline for clustering using any custom embedding module.
    """

    def __init__(self, model: BaseEmbedder, **kwargs):
        self.model = model

    @abc.abstractmethod
    def fit_transform(self, docs, **kwargs) -> tuple[list[int], np.ndarray | None]:
        pass

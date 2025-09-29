import abc
import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from loguru import logger
from openai import AsyncOpenAI

from jaiai.etc.io import source_from_dataset


# ---------- Твои таски ----------
@dataclass(slots=True)
class OpenAiTask:
    id: int | str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class OpenAIAsyncWrapper:

    def __init__(
        self,
        model: str = "llama-3.1-8b-instruct",
        response_format: Optional[
            dict[str, Any]
        ] = None,  # можно не использовать с llama.cpp
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
        base_url = (
            base_url or os.getenv("OPENAI_BASE_URL") or "http://localhost:1234"
        ).rstrip("/")
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
            assert len(lines) > 0, logger.error(
                f"OpenAIAsyncWrapper: system_prompt_fpath is empty: {system_prompt_fpath}"
            )
            self.system_prompt = "\n".join(lines).strip()
        else:
            self.system_prompt = system_prompt.strip()

    def run(self, tasks: Sequence[OpenAiTask]) -> list[dict[str, Any]]:
        if not tasks:
            return []
        return asyncio.run(self._arun(tasks))

    async def _arun(self, tasks: Sequence[OpenAiTask]) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(self.max_concurrent)

        async def one(t: OpenAiTask) -> dict[str, Any]:
            async with sem:
                try:
                    return await asyncio.wait_for(
                        self._call(t), timeout=self.api_call_timeout
                    )
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

    @abc.abstractmethod
    async def _call(self, task: OpenAiTask) -> dict[str, Any]:
        pass

from typing import Any

from jaiai.running.helpers import _extract_md_pairs
from jaiai.running.mask import OpenAIAsyncWrapper, OpenAiTask


class InstructionForTopicExtraction(OpenAIAsyncWrapper):

    def __init__(self, **props) -> None:
        super().__init__(**props)

    async def _call(self, task: OpenAiTask) -> dict[str, Any]:
        """
        Основной вызов: chat.completions (совместимо с llama.cpp server).
        """
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Вот текст отзыва:\n{task.text}"},
                ],
                temperature=0.2,
                top_p=0.9,
                max_tokens=512,
                stream=False,
            )
            content = (
                resp.choices[0].message.content if resp and resp.choices else ""
            ) or ""
        except Exception as e:
            return {
                "id": task.id,
                "metadata": task.metadata,
                "model": self.model,
                "error": f"{type(e).__name__}: {e}",
                "text": None,
                "parsed_json": None,
                "raw": None,
            }

        # парсим 2 строки markdown → пары списков
        topics, sentiments = _extract_md_pairs(content)

        # опционально: собрать единый JSON для дублирования в redis
        parsed_json = (
            {"topics": topics, "sentiments": sentiments}
            if topics or sentiments
            else None
        )

        return {
            "id": task.id,
            "metadata": task.metadata,
            "model": self.model,
            "error": None,
            "text": content,
            "parsed_json": parsed_json,
            "raw": resp.model_dump() if hasattr(resp, "model_dump") else None,
        }


__all__ = ["InstructionForTopicExtraction"]

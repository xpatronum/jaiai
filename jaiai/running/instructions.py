from collections import Counter
from typing import Any

import json_repair
from loguru import logger

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
            content = (resp.choices[0].message.content if resp and resp.choices else "") or ""
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
        parsed_json = {"topics": topics, "sentiments": sentiments} if topics or sentiments else None

        answer = {
            "id": task.id,
            "metadata": task.metadata,
            "model": self.model,
            "error": None,
            "text": content,
            "parsed_json": parsed_json,
            "raw": resp.model_dump() if hasattr(resp, "model_dump") else None,
        }

        if parsed_json is None:
            answer["parsed_json"] = InstructionForTopicExtraction.formatted_response(answer)
        return answer

    @staticmethod
    def formatted_response(raw: dict):
        raw_answer = raw["text"]
        parsed_json = raw["parsed_json"]
        id_message = raw["id"]
        topics, sentiments = [], []
        if parsed_json is not None:
            topics, sentiments = parsed_json["topics"], parsed_json["sentiments"]
        else:
            js_res = json_repair.loads(raw_answer)
            if isinstance(js_res, list) and len(js_res) >= 2:
                topics: list[str] = js_res[0]
                sentiments: list[str] = js_res[1]
                if len(sentiments) > len(topics):
                    _counter = Counter(sentiments)
                    top_sentiment_per_topic = _counter.most_common(1)[0][0]
                    sentiments.extend([top_sentiment_per_topic] * (len(sentiments) - len(topics)))
                elif len(sentiments) < len(topics):
                    topics = topics[: len(sentiments)]
            else:
                logger.warning(
                    f"For response {raw_answer} neither `raw_json` is present and unable to hand-craft JSON compatable answer. Parsed json is not a list but {type(js_res)}"
                )
        return dict(topics=topics, sentiments=sentiments, id=id_message)


__all__ = ["InstructionForTopicExtraction"]
